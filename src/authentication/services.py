from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from authentication.models import User
from grm.settings import EMAIL_HOST_USER


class PasswordResetService:
    """
    Service class to encapsulate password reset logic,
    shared between DRF and Django views.
    """

    @staticmethod
    def handle_password_reset_request(request, email):
        """
        Generate password reset token and send email if user exists.

        Args:
            request: HttpRequest (Django or DRF request, both provide scheme & host).
            email (str): User email.
        """
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Security best practice: always respond with success message
            return

        # Generate token and uid
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_path = reverse("authentication:password_reset_confirm", kwargs={"uidb64": uid, "token": token})
        reset_link = f"{request.scheme}://{request.get_host()}{reset_path}"

        # Send email
        send_mail(
            subject="Password Reset Request",
            message=f"Please click the following link to reset your password: {reset_link}",
            from_email=EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=True,
        )
