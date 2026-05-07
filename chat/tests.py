"""Chat-side tests: conversation actions are scoped to their owner."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from .models import Conversation, Message

User = get_user_model()


class ConversationOwnershipTest(TestCase):
    """Delete / rename / export must reject access to other users' rows."""

    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="Untrivial-Pass-9!"
        )
        cls.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="Untrivial-Pass-9!"
        )
        # Both users need a verified profile to bypass the chat gate.
        for u in (cls.alice, cls.bob):
            profile, _ = UserProfile.objects.get_or_create(user=u)
            from django.utils import timezone as _tz
            profile.email_verified_at = _tz.now()
            profile.save(update_fields=["email_verified_at"])

        cls.alices_convo = Conversation.objects.create(
            user=cls.alice, title="alice's plans"
        )
        Message.objects.create(
            conversation=cls.alices_convo, role=Message.USER, content="hello"
        )

    def _login(self, user):
        self.client.force_login(user)

    # --- delete ---------------------------------------------------------

    def test_owner_can_delete_their_conversation(self):
        self._login(self.alice)
        url = reverse("chat:api_delete_conversation", args=[self.alices_convo.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Conversation.objects.filter(id=self.alices_convo.id).exists()
        )

    def test_other_user_cannot_delete_anothers_conversation(self):
        self._login(self.bob)
        url = reverse("chat:api_delete_conversation", args=[self.alices_convo.id])
        response = self.client.post(url)
        self.assertEqual(
            response.status_code, 404,
            "delete should 404 for a conversation that doesn't belong to the user",
        )
        self.assertTrue(
            Conversation.objects.filter(id=self.alices_convo.id).exists(),
            "alice's conversation must survive bob's request",
        )

    def test_anonymous_cannot_delete(self):
        # No login; request must redirect to login (302) rather than delete.
        url = reverse("chat:api_delete_conversation", args=[self.alices_convo.id])
        response = self.client.post(url)
        self.assertIn(response.status_code, (302, 401, 403))
        self.assertTrue(
            Conversation.objects.filter(id=self.alices_convo.id).exists()
        )

    # --- rename ---------------------------------------------------------

    def test_other_user_cannot_rename_anothers_conversation(self):
        self._login(self.bob)
        url = reverse("chat:api_rename_conversation", args=[self.alices_convo.id])
        response = self.client.post(
            url, data='{"title":"hijacked"}', content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)
        self.alices_convo.refresh_from_db()
        self.assertEqual(self.alices_convo.title, "alice's plans")

    def test_owner_can_rename(self):
        self._login(self.alice)
        url = reverse("chat:api_rename_conversation", args=[self.alices_convo.id])
        response = self.client.post(
            url, data='{"title":"renamed"}', content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.alices_convo.refresh_from_db()
        self.assertEqual(self.alices_convo.title, "renamed")

    # --- export ---------------------------------------------------------

    def test_other_user_cannot_export_anothers_conversation(self):
        self._login(self.bob)
        url = reverse("chat:api_export_conversation", args=[self.alices_convo.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_owner_can_export_markdown(self):
        self._login(self.alice)
        url = reverse("chat:api_export_conversation", args=[self.alices_convo.id])
        response = self.client.get(url + "?format=md")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"alice", response.content.lower())
        self.assertIn("text/markdown", response["Content-Type"])

    # --- chat_page gate -------------------------------------------------

    def test_unverified_user_redirected_from_chat_page(self):
        carol = User.objects.create_user(
            username="carol", email="carol@example.com", password="Untrivial-Pass-9!"
        )
        # carol's profile is auto-created via signal but unverified by default.
        profile, _ = UserProfile.objects.get_or_create(user=carol)
        profile.email_verified_at = None
        profile.save(update_fields=["email_verified_at"])
        self.client.force_login(carol)
        response = self.client.get(reverse("chat:chat"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:verify_pending"), response["Location"])
