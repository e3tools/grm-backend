from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from authentication.factories import UserFactory


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    LANGUAGE_CODE="en-us",
)
class PasswordResetViewTest(TestCase):
    """Test the PasswordResetView with Django TestCase."""

    def setUp(self):
        self.url = reverse("authentication:password_reset")
        self.user = UserFactory(email="user@example.com")

    def test_get_renders_form(self):
        """GET request should render the password reset form."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        template_names = [t.name for t in response.templates]
        self.assertIn("authentication/password_reset_form.html", template_names)
        self.assertIn("<form", response.content.decode())

    def test_successful_password_reset_request(self):
        """Test sending a password reset request with a valid email."""
        response = self.client.post(self.url, {"email": self.user.email})
        self.assertEqual(response.status_code, 200)

        # Check that the done template was rendered
        template_names = [t.name for t in response.templates]
        self.assertIn("authentication/password_reset_done.html", template_names)

        # Verify that one email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]

        self.assertIn(self.user.email, email.to)
        self.assertIn("reset", email.subject.lower())
        self.assertIn("http", email.body)  # Reset link present

        # Extract uid and token from email body (basic check)
        body = email.body
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.assertIn(uid, body)

        # Extract token from body (last segment of the URL)
        token = body.strip().split("/")[-2]
        self.assertTrue(default_token_generator.check_token(self.user, token))

    def test_post_valid_email_sends_email_and_shows_done_page(self):
        """POST with a valid email should send a reset email and show done template."""
        response = self.client.post(self.url, {"email": self.user.email})
        self.assertEqual(response.status_code, 200)
        template_names = [t.name for t in response.templates]
        self.assertIn("authentication/password_reset_done.html", template_names)

        # Check that one email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)
        self.assertIn("Password Reset Request", mail.outbox[0].subject)

    def test_post_invalid_email_still_shows_done_page(self):
        """
        POST with unknown email should not reveal user existence,
        but should still show the done template.
        """
        response = self.client.post(self.url, {"email": "notfound@example.com"})
        self.assertEqual(response.status_code, 200)
        template_names = [t.name for t in response.templates]
        self.assertIn("authentication/password_reset_done.html", template_names)

        # No email should be sent
        self.assertEqual(len(mail.outbox), 0)

    def test_post_empty_email_re_renders_form_with_errors(self):
        """POST with empty email should re-render the form with validation errors."""
        response = self.client.post(self.url, {"email": ""})
        self.assertEqual(response.status_code, 200)
        template_names = [t.name for t in response.templates]
        self.assertIn("authentication/password_reset_form.html", template_names)
        self.assertIn("This field is required", response.content.decode())
