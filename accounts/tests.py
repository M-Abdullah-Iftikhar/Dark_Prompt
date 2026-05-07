"""Account-side tests: AUP gate on signup + email-or-username login backend."""
from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import UserProfile

User = get_user_model()


VALID_SIGNUP = {
    "email":            "operator@example.com",
    "username":         "operator",
    "password":         "Untrivial-Pass-9!",
    "confirm_password": "Untrivial-Pass-9!",
    "agree_aup":        "on",
}


class SignupAUPTest(TestCase):
    """The Acceptable Use Policy checkbox is mandatory for signup."""

    def test_signup_succeeds_when_aup_checked(self):
        response = self.client.post(reverse("accounts:signup"), VALID_SIGNUP)
        self.assertEqual(response.status_code, 302, "signup should redirect on success")
        self.assertTrue(User.objects.filter(email="operator@example.com").exists())

    def test_signup_rejected_without_aup(self):
        payload = dict(VALID_SIGNUP)
        payload.pop("agree_aup")
        response = self.client.post(reverse("accounts:signup"), payload)
        self.assertEqual(response.status_code, 200, "should re-render the form")
        self.assertFalse(User.objects.filter(email="operator@example.com").exists())
        # Form-level error must mention the AUP — exact wording lives in
        # SignupForm.error_messages["agree_aup"]["required"].
        self.assertContains(response, "Acceptable Use Policy")

    def test_signup_creates_user_profile(self):
        self.client.post(reverse("accounts:signup"), VALID_SIGNUP)
        user = User.objects.get(email="operator@example.com")
        self.assertTrue(
            UserProfile.objects.filter(user=user).exists(),
            "signup signal should auto-create a UserProfile row",
        )


class EmailOrUsernameBackendTest(TestCase):
    """EmailOrUsernameBackend resolves either identifier to the right user."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="operator",
            email="operator@example.com",
            password="Untrivial-Pass-9!",
        )

    def test_authenticate_by_username(self):
        u = authenticate(username="operator", password="Untrivial-Pass-9!")
        self.assertEqual(u, self.user)

    def test_authenticate_by_email(self):
        u = authenticate(username="operator@example.com", password="Untrivial-Pass-9!")
        self.assertEqual(u, self.user)

    def test_authenticate_by_email_is_case_insensitive(self):
        u = authenticate(username="OPERATOR@example.com", password="Untrivial-Pass-9!")
        self.assertEqual(u, self.user)

    def test_authenticate_rejects_wrong_password(self):
        self.assertIsNone(
            authenticate(username="operator", password="wrong-password")
        )

    def test_authenticate_rejects_unknown_identifier(self):
        self.assertIsNone(
            authenticate(username="nobody", password="Untrivial-Pass-9!")
        )

    def test_authenticate_rejects_missing_credentials(self):
        self.assertIsNone(authenticate(username=None, password=None))
        self.assertIsNone(authenticate(username="operator", password=None))
