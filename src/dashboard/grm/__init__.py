from django.utils.translation import gettext_lazy as _

CHOICE_FACILITATOR = 'facilitator'
CHOICE_ANONYMOUS = 'anonymous'
CHOICE_CONTACT = 'contact'
MEDIUM_CHOICES = [
    (CHOICE_ANONYMOUS, _('Remain anonymous')),
    (CHOICE_FACILITATOR, _('Receive updates from facilitator')),
    (CHOICE_CONTACT, _('Receive updates directly')),
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

CHOICE_1 = 1
CHOICE_2 = 2
CHOICE_3 = 3
CITIZEN_TYPE_CHOICES = [
    (CHOICE_1, _('Keep name confidential.  Only the person resolving the issue will see the name.')),
    (CHOICE_2, _('This is an individual filing on behalf of someone else.')),
    (CHOICE_3, _('This is an organization filing on behalf of someone else.')),
]

CHOICE_MALE = "Male"
CHOICE_FEMALE = "Female"
CHOICE_OTHER = "Other"
CHOICE_RNS = "Rather not say"

GENDER_CHOICES = [
    ('', ''),
    (CHOICE_MALE, _(CHOICE_MALE)),
    (CHOICE_FEMALE, _(CHOICE_FEMALE)),
    (CHOICE_OTHER, _(CHOICE_OTHER)),
    (CHOICE_RNS, _(CHOICE_RNS)),
]
