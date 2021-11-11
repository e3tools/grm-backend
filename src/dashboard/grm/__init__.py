from django.utils.translation import gettext_lazy as _

CHOICE_NIA = 'nia'
CHOICE_ANONYMOUS = 'anonymous'
CHOICE_CONTACT = 'contact'
MEDIUM_CHOICES = [
    (CHOICE_NIA, _('No information available')),
    (CHOICE_ANONYMOUS, _('Anonymous')),
    (CHOICE_CONTACT, _('Citizen can be alerted through:')),
]

CHOICE_EMAIL = 'email'
CHOICE_PHONE = 'phone_number'
CHOICE_WHATSAPP = 'whatsapp'
CONTACT_CHOICES = [
    ('', ''),
    (CHOICE_EMAIL, _('email')),
    (CHOICE_PHONE, _('phone number')),
    (CHOICE_WHATSAPP, 'whatsapp'),
]
