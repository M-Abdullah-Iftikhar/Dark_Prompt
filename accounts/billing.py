"""Stripe service helpers — Checkout, customer portal, webhook handling.

Currently configured for Stripe TEST MODE (sk_test_… keys). Flip env vars
to live keys for production. Nothing in this module assumes a particular
mode — Stripe's own routing handles it based on the key prefix.

The single source of truth for tier configuration is `accounts/tiers.py`.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.utils import timezone

log = logging.getLogger("accounts.billing")

from . import tiers as tier_lib


# ---------------------------------------------------------------------------
# Stripe SDK lazy loader
# ---------------------------------------------------------------------------

def _stripe():
    """Return the configured `stripe` module, or None if not installed/keyed."""
    api_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not api_key:
        return None
    try:
        import stripe
    except ImportError:
        log.error("`stripe` package not installed — `pip install stripe`")
        return None
    stripe.api_key = api_key
    return stripe


def is_configured() -> bool:
    """True iff Stripe keys are present + the SDK is installed."""
    return _stripe() is not None


# ---------------------------------------------------------------------------
# Customer / Checkout
# ---------------------------------------------------------------------------

def get_or_create_customer(user) -> Optional[str]:
    """Return the Stripe customer id for `user`, creating one if missing.

    Idempotent — won't create duplicate customers across calls. Returns
    None if Stripe isn't configured OR the API call fails."""
    s = _stripe()
    if s is None:
        return None
    profile = user.profile
    if profile.stripe_customer_id:
        return profile.stripe_customer_id
    try:
        customer = s.Customer.create(
            email=user.email or None,
            name=user.username,
            metadata={"user_id": str(user.pk), "username": user.username},
        )
    except Exception:
        log.exception("Stripe customer create failed for user_id=%s", user.pk)
        return None
    profile.stripe_customer_id = customer.id
    profile.save(update_fields=["stripe_customer_id"])
    return customer.id


def create_checkout_session(user, tier_slug, *, success_url, cancel_url) -> Optional[str]:
    """Create a Stripe Checkout Session for the given tier.

    Returns the URL the user should be redirected to, or None on failure.
    Free tiers (no Stripe price id) are not handled here — the caller
    should activate them directly without Stripe."""
    s = _stripe()
    if s is None:
        return None
    price_id = tier_lib.stripe_price_id_for(tier_slug)
    if not price_id:
        return None

    customer_id = get_or_create_customer(user)
    if not customer_id:
        return None

    try:
        session = s.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            client_reference_id=str(user.pk),
            subscription_data={
                "metadata": {
                    "user_id":   str(user.pk),
                    "tier_slug": tier_slug,
                },
            },
            metadata={
                "user_id":   str(user.pk),
                "tier_slug": tier_slug,
            },
        )
    except Exception:
        log.exception(
            "Stripe Checkout Session create failed for user_id=%s tier=%s",
            user.pk, tier_slug,
        )
        return None
    return session.url


def create_billing_portal_url(user, *, return_url) -> Optional[str]:
    """Return a Stripe Customer Portal URL for the user, or None on failure.

    Used by the Settings page so a paid user can update card / cancel
    without leaving the site. Requires the user to already have a
    `stripe_customer_id` (which they will, after a successful Checkout)."""
    s = _stripe()
    if s is None:
        return None
    profile = user.profile
    if not profile.stripe_customer_id:
        return None
    try:
        portal = s.billing_portal.Session.create(
            customer=profile.stripe_customer_id,
            return_url=return_url,
        )
    except Exception:
        log.exception("Stripe billing portal create failed for user_id=%s", user.pk)
        return None
    return portal.url


# ---------------------------------------------------------------------------
# Webhook handling — keep our DB in sync with Stripe state
# ---------------------------------------------------------------------------

def parse_webhook_event(payload_bytes, sig_header):
    """Verify + return a Stripe event, or None if signature/secret invalid."""
    s = _stripe()
    if s is None:
        return None
    secret = (getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "").strip()
    if not secret:
        log.error("STRIPE_WEBHOOK_SECRET is not set; refusing to process webhook")
        return None
    try:
        return s.Webhook.construct_event(payload_bytes, sig_header, secret)
    except Exception:
        log.exception("Stripe webhook signature verification failed")
        return None


def _profile_for_customer(customer_id):
    """Look up a UserProfile by stripe_customer_id (or None)."""
    if not customer_id:
        return None
    from .models import UserProfile
    return UserProfile.objects.filter(stripe_customer_id=customer_id).first()


def _apply_subscription_to_profile(profile, subscription_obj, *, tier_hint=None):
    """Mirror a Stripe Subscription's state onto our local profile row."""
    from datetime import datetime, timezone as dt_tz

    # Pick the tier from the line item's price ID; fall back to the hint.
    tier_slug = tier_hint
    try:
        items = (subscription_obj.get("items") or {}).get("data") or []
        if items:
            price_id = (items[0].get("price") or {}).get("id")
            mapped = tier_lib.slug_for_stripe_price(price_id)
            if mapped:
                tier_slug = mapped
    except Exception:
        pass
    if not tier_slug:
        tier_slug = profile.subscription_tier or "sniffer"

    status = subscription_obj.get("status") or "none"
    period_end_ts = subscription_obj.get("current_period_end")
    period_end = None
    if period_end_ts:
        try:
            period_end = datetime.fromtimestamp(int(period_end_ts), tz=dt_tz.utc)
        except Exception:
            period_end = None

    sub_id = subscription_obj.get("id") or ""

    # If the subscription has been cancelled or expired, fall back to free tier.
    if status in {"canceled", "incomplete_expired", "unpaid"}:
        profile.subscription_tier   = "sniffer"
        profile.subscription_status = "canceled" if status == "canceled" else status
    else:
        profile.subscription_tier   = tier_slug
        profile.subscription_status = status

    profile.stripe_subscription_id = sub_id
    profile.current_period_end     = period_end
    profile.save(update_fields=[
        "subscription_tier", "subscription_status",
        "stripe_subscription_id", "current_period_end",
    ])


def resync_user_subscription(user) -> bool:
    """List the user's Stripe subscriptions and apply the active one (if any)
    to their profile. Used to recover from missed-webhook situations on
    local dev. Cheap (one API call), idempotent."""
    s = _stripe()
    if s is None:
        return False
    profile = getattr(user, "profile", None)
    if profile is None or not profile.stripe_customer_id:
        return False
    try:
        subs = s.Subscription.list(
            customer=profile.stripe_customer_id,
            status="all",
            limit=10,
        )
    except Exception:
        log.exception("Stripe sub list failed for customer %s", profile.stripe_customer_id)
        return False
    items = (subs.get("data") if isinstance(subs, dict) else getattr(subs, "data", None)) or []
    if not items:
        return False
    # Prefer active/trialing/past_due; fall back to whatever's most recent.
    PRIORITY = {"active": 0, "trialing": 1, "past_due": 2, "incomplete": 3}
    items_sorted = sorted(
        items,
        key=lambda it: (
            PRIORITY.get(it.get("status") or "", 99),
            -int(it.get("created") or 0),
        ),
    )
    chosen = items_sorted[0]
    _apply_subscription_to_profile(profile, chosen)
    return True


def activate_from_session(user, session_id: str) -> bool:
    """Pull a Checkout Session from Stripe and apply its subscription state
    to `user`'s profile. Used by the success-page landing handler so a
    subscription becomes active immediately even when the webhook hasn't
    been delivered yet (typical on local dev without `stripe listen`).

    Idempotent: re-applying the same state is safe. Returns True on success.
    """
    s = _stripe()
    if s is None or not session_id:
        return False
    try:
        session = s.checkout.Session.retrieve(session_id)
    except Exception:
        log.exception("Stripe session retrieve failed: %s", session_id)
        return False

    # Guard: the session must belong to this user. We compare client_reference_id
    # (set at create_checkout_session) against the user's pk to prevent a logged-in
    # attacker from activating someone else's session by guessing IDs.
    ref = str(session.get("client_reference_id") or "")
    if ref and ref != str(user.pk):
        log.warning("Session %s ref=%s but user=%s — refusing", session_id, ref, user.pk)
        return False

    # If the customer id is set on the session but missing on our profile (shouldn't
    # happen, but harmless to backfill), copy it over so portal links work.
    customer_id = session.get("customer")
    profile = user.profile
    if customer_id and not profile.stripe_customer_id:
        profile.stripe_customer_id = customer_id
        profile.save(update_fields=["stripe_customer_id"])

    subscription_id = session.get("subscription")
    if not subscription_id:
        # Either pending payment or a one-shot session — nothing to apply.
        return False
    try:
        sub = s.Subscription.retrieve(subscription_id)
    except Exception:
        log.exception("Stripe subscription retrieve failed: %s", subscription_id)
        return False

    tier_hint = (session.get("metadata") or {}).get("tier_slug")
    _apply_subscription_to_profile(profile, sub, tier_hint=tier_hint)
    return True


def handle_event(event) -> bool:
    """Apply a verified Stripe event to our DB. Returns True if handled."""
    s = _stripe()
    if s is None or event is None:
        return False
    etype = event.get("type") or ""
    obj   = (event.get("data") or {}).get("object") or {}

    if etype == "checkout.session.completed":
        # Session was paid + the subscription has been created.
        customer_id    = obj.get("customer")
        subscription_id = obj.get("subscription")
        tier_hint      = (obj.get("metadata") or {}).get("tier_slug")
        profile = _profile_for_customer(customer_id)
        if profile is None:
            log.warning("Webhook: no profile for customer %s", customer_id)
            return False
        if subscription_id:
            try:
                sub = s.Subscription.retrieve(subscription_id)
            except Exception:
                log.exception("Failed to retrieve subscription %s", subscription_id)
                return False
            _apply_subscription_to_profile(profile, sub, tier_hint=tier_hint)
        return True

    if etype in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        customer_id = obj.get("customer")
        profile = _profile_for_customer(customer_id)
        if profile is None:
            return False
        # `obj` here IS the subscription representation.
        if etype == "customer.subscription.deleted":
            obj["status"] = "canceled"
        _apply_subscription_to_profile(profile, obj)
        return True

    return False
