"""Subscription tier definitions — single source of truth.

Caps are enforced server-side in chat.views.api_chat. The same dict is used
to render the tier badge in Settings, the cap-exceeded error messages, and
the pricing-page CTA labels.

To change a cap, edit only this file. The migration that introduced the
Stripe fields on UserProfile uses the SNIFFER name as the default for
existing rows, so renaming SNIFFER would require a follow-up migration.
"""
from django.conf import settings


TIER_SNIFFER = "sniffer"
TIER_EXPLOIT = "exploit"
TIER_ZERODAY = "zeroday"


# IMPORTANT: cap values are deliberately conservative for the FYP demo.
# Bump them later — the chat backend reads these every request.
TIER_LIMITS = {
    TIER_SNIFFER: {
        "name":              "SNIFFER",
        "tag":               "TIER 01",
        "tagline":           "Just listening in",
        "price":             "$0",
        "price_amount":      0,
        "cta":               "Activate Sniffer",
        "max_tokens":        1024,
        "monthly_gens":      50,
        "languages":         {"asm"},          # ASM only
        "feature_compile":   False,
        "feature_api_keys":  False,
        "stripe_price_attr": None,             # free, no Stripe object
    },
    TIER_EXPLOIT: {
        "name":              "EXPLOIT",
        "tag":               "TIER 02",
        "tagline":           "Finding the gaps",
        "price":             "$29",
        "price_amount":      29,
        "cta":               "Activate Exploit",
        "max_tokens":        4096,
        "monthly_gens":      1000,
        "languages":         {"asm", "c"},
        "feature_compile":   True,
        "feature_api_keys":  False,
        "stripe_price_attr": "STRIPE_PRICE_EXPLOIT",
    },
    TIER_ZERODAY: {
        "name":              "ZERO DAY",
        "tag":               "TIER 03",
        "tagline":           "Unstoppable",
        "price":             "$149",
        "price_amount":      149,
        "cta":               "Activate Zero Day",
        "max_tokens":        8192,
        "monthly_gens":      None,             # None = unlimited
        "languages":         {"asm", "c"},
        "feature_compile":   True,
        "feature_api_keys":  True,
        "stripe_price_attr": "STRIPE_PRICE_ZERODAY",
    },
}


def get_tier(slug):
    """Return the tier dict for `slug`, falling back to SNIFFER."""
    return TIER_LIMITS.get((slug or TIER_SNIFFER).lower(), TIER_LIMITS[TIER_SNIFFER])


def stripe_price_id_for(slug):
    """Return the Stripe Price ID env-var value for a tier, or None for free."""
    tier = get_tier(slug)
    attr = tier.get("stripe_price_attr")
    if not attr:
        return None
    return getattr(settings, attr, "") or None


def slug_for_stripe_price(price_id):
    """Reverse lookup — given a Stripe price ID, return the tier slug.

    Used by the webhook to map an incoming Checkout Session back to a tier.
    """
    if not price_id:
        return None
    for slug, tier in TIER_LIMITS.items():
        attr = tier.get("stripe_price_attr")
        if not attr:
            continue
        if (getattr(settings, attr, "") or "") == price_id:
            return slug
    return None
