"""Forms for signup and login."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class SignupForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            "autocomplete": "email",
            "placeholder": "you@example.com",
        }),
    )
    username = forms.CharField(
        min_length=3,
        max_length=32,
        widget=forms.TextInput(attrs={
            "autocomplete": "username",
            "placeholder": "operator_handle",
        }),
    )
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
            "placeholder": "••••••••",
        }),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
            "placeholder": "••••••••",
        }),
    )
    agree_aup = forms.BooleanField(
        required=True,
        error_messages={
            "required": "You must accept the Acceptable Use Policy to register.",
        },
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("That email is already registered.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("That username is already taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                self.add_error("password", e)
        return cleaned

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
        )
        return user


class LoginForm(forms.Form):
    identifier = forms.CharField(
        label="Email or username",
        max_length=254,
        widget=forms.TextInput(attrs={
            "autocomplete": "username",
            "placeholder": "you@example.com",
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "autocomplete": "current-password",
            "placeholder": "••••••••",
        }),
    )
    remember_me = forms.BooleanField(required=False, initial=False)


class SubscriptionAgreementForm(forms.Form):
    """Ethical-use agreement gating subscription activation."""
    full_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Jane Q. Researcher"}),
    )
    organisation = forms.CharField(
        max_length=160,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "(optional) BlueLab Security"}),
    )
    role = forms.ChoiceField(
        choices=[
            ("", "— Select your role —"),
            ("av_researcher", "AV / EDR detection researcher"),
            ("red_team", "Authorised red-team / pentest"),
            ("academic", "Academic / education"),
            ("hobbyist", "Hobbyist / CTF"),
            ("other", "Other"),
        ],
    )
    confirm_authorised = forms.BooleanField(
        required=True,
        error_messages={"required": "You must confirm authorised use."},
    )
    confirm_no_target = forms.BooleanField(
        required=True,
        error_messages={"required": "You must confirm no third-party targeting."},
    )
    confirm_logging = forms.BooleanField(
        required=True,
        error_messages={"required": "You must accept session logging."},
    )
    confirm_aup = forms.BooleanField(
        required=True,
        error_messages={"required": "You must re-accept the Acceptable Use Policy."},
    )
    signature = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Type your full name to sign"}),
    )

    def clean(self):
        cleaned = super().clean()
        full_name = (cleaned.get("full_name") or "").strip().lower()
        signature = (cleaned.get("signature") or "").strip().lower()
        if full_name and signature and full_name != signature:
            self.add_error("signature", "Signature must match the full name above.")
        return cleaned


class SettingsForm(forms.Form):
    """Edit username + email."""
    username = forms.CharField(
        min_length=3, max_length=32,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = User.objects.filter(username__iexact=username)
        if self.user:
            qs = qs.exclude(pk=self.user.pk)
        if qs.exists():
            raise ValidationError("That username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.user:
            qs = qs.exclude(pk=self.user.pk)
        if qs.exists():
            raise ValidationError("That email is already in use.")
        return email


class PasswordChangeForm(forms.Form):
    """Change password; requires current password verification."""
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "autocomplete": "current-password",
            "placeholder": "••••••••",
        }),
    )
    new_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
            "placeholder": "••••••••",
        }),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
            "placeholder": "••••••••",
        }),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        pw = self.cleaned_data["current_password"]
        if self.user and not self.user.check_password(pw):
            raise ValidationError("Current password is incorrect.")
        return pw

    def clean(self):
        cleaned = super().clean()
        new_pw = cleaned.get("new_password")
        confirm = cleaned.get("confirm_password")
        if new_pw and confirm and new_pw != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        if new_pw:
            try:
                validate_password(new_pw, user=self.user)
            except ValidationError as e:
                self.add_error("new_password", e)
        return cleaned


class ForgotPasswordForm(forms.Form):
    """Request a password-reset email."""
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            "autocomplete": "email",
            "placeholder": "you@example.com",
        }),
    )


class TOTPSetupForm(forms.Form):
    """Confirm a freshly-generated TOTP secret with a 6-digit code."""
    code = forms.CharField(
        min_length=6, max_length=6,
        widget=forms.TextInput(attrs={
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "pattern": "[0-9]*",
            "placeholder": "123456",
        }),
    )


class TOTPChallengeForm(forms.Form):
    """Login-time 2FA challenge — accepts a 6-digit TOTP or a backup code."""
    code = forms.CharField(
        min_length=6, max_length=12,
        widget=forms.TextInput(attrs={
            "autocomplete": "one-time-code",
            "placeholder": "123456 or backup code",
        }),
    )


class TOTPDisableForm(forms.Form):
    """Require current password to disable 2FA."""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "autocomplete": "current-password",
            "placeholder": "••••••••",
        }),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        pw = self.cleaned_data["password"]
        if self.user is not None and not self.user.check_password(pw):
            raise ValidationError("Incorrect password.")
        return pw


class PasswordResetConfirmForm(forms.Form):
    """Set a new password from a reset link."""
    new_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
            "placeholder": "••••••••",
        }),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
            "placeholder": "••••••••",
        }),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        cleaned = super().clean()
        new_pw = cleaned.get("new_password")
        confirm = cleaned.get("confirm_password")
        if new_pw and confirm and new_pw != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        if new_pw:
            try:
                validate_password(new_pw, user=self.user)
            except ValidationError as e:
                self.add_error("new_password", e)
        return cleaned
