from django.core.mail import send_mail
from django.conf import settings

EMAIL_HOST_USER = settings.EMAIL_HOST_USER

def send_mail_notification(subject, message, recipient):
    send_mail(
        subject=subject,
        message=message,
        from_email=EMAIL_HOST_USER,
        recipient_list=[recipient,]
    )