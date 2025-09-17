import pytest
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.reverse import reverse

from authentication.factories import UserFactory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class PasswordResetConfirmViewTest(TestCase):
    """Test the PasswordResetView with Django TestCase."""

    def setUp(self):
        """Set up test user and base URL for password reset confirmation."""
        self.user = UserFactory()
        self.uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = default_token_generator.make_token(self.user)
        self.url = reverse("authentication:password_reset_confirm", kwargs={"uidb64": self.uidb64, "token": self.token})

    def test_password_reset_confirm_success(self):
        """Valid token and strong password should reset the password and show success page."""
        response = self.client.post(
            self.url,
            {"new_password1": "newStrongPass123", "new_password2": "newStrongPass123"},
        )

        assert response.status_code == 200
        assert b"Password reset complete" in response.content

        self.user.refresh_from_db()
        assert self.user.check_password("newStrongPass123")

    def test_password_reset_invalid_token(self):
        """Invalid token should render the form with validlink = False."""
        bad_url = reverse(
            "authentication:password_reset_confirm",
            kwargs={"uidb64": self.user.pk, "token": "invalid-token"},
        )

        response = self.client.get(bad_url)
        assert response.status_code == 200
        assert response.context["validlink"] is False

    def test_password_reset_already_used_token(self):
        """A token cannot be reused once the password has been reset."""
        # First reset (valid)
        self.client.post(
            self.url,
            {"new_password1": "newStrongPass123", "new_password2": "newStrongPass123"},
        )

        # Refresh user to ensure token invalidation
        self.user.refresh_from_db()

        # Second reset attempt with same token
        response2 = self.client.get(self.url)
        assert response2.status_code == 200
        assert response2.context["validlink"] is False

    def test_password_mismatch(self):
        """Passwords that don't match should return form errors."""
        response = self.client.post(
            self.url,
            {"new_password1": "password123", "new_password2": "different123"},
        )

        assert response.status_code == 200
        form = response.context["form"]
        assert "new_password2" in form.errors

    def test_weak_password(self):
        """Weak passwords should trigger password validation errors."""
        response = self.client.post(
            self.url,
            {"new_password1": "12345678", "new_password2": "12345678"},  # purely numeric
        )

        assert response.status_code == 200
        form = response.context["form"]
        assert "new_password2" in form.errors
        assert any("numeric" in str(err).lower() for err in form.errors["new_password2"])

    def test_password_too_short(self):
        """Password shorter than 8 characters should be rejected by MinimumLengthValidator."""
        response = self.client.post(
            self.url,
            {"new_password1": "short_p", "new_password2": "short_p"},  # Only 7 chars
        )

        assert response.status_code == 200
        form = response.context["form"]

        # Ensure validation error is triggered
        assert "new_password2" in form.errors
        assert any("at least 8 characters" in str(err).lower() for err in form.errors["new_password2"])
