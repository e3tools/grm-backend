from django.utils.translation import gettext_lazy as _

CHOICE_FACILITATOR = 'facilitator'
CHOICE_ANONYMOUS = 'anonymous'
CHOICE_CONTACT = 'contact'
MEDIUM_CHOICES = [
    (CHOICE_ANONYMOUS, _('Remain anonymous')),
    (CHOICE_FACILITATOR, _('Receive updates from facilitator')),
    (CHOICE_CONTACT, _('Receive updates directly')),
]

CHOICE_EMAIL = _('email')
CHOICE_PHONE = _('phone number')
CHOICE_WHATSAPP = _('whatsapp')
CONTACT_CHOICES = [
    ('', ''),
    (CHOICE_EMAIL, _('email')),
    (CHOICE_PHONE, _('phone number')),
    (CHOICE_WHATSAPP, _('whatsapp')),
]

CHOICE_1 = 1
CHOICE_2 = 2
CHOICE_3 = 3
CITIZEN_TYPE_CHOICES = [
    (CHOICE_1, _('Keep name confidential. Only the person resolving the issue will see the name.')),
    (CHOICE_2, _('This is an individual filing on behalf of someone else.')),
    (CHOICE_3, _('This is an organization filing on behalf of someone else.')),
]

CHOICE_0_OR_1_LABEL = _('Complainant')
CITIZEN_TYPE_CHOICES_ALT = [
    (0, CHOICE_0_OR_1_LABEL),
    (CHOICE_1, CHOICE_0_OR_1_LABEL),
    (CHOICE_2, _('Citizen on behalf of others')),
    (CHOICE_3, _('Organization on behalf of others')),
]

CHOICE_MALE = _("Male")
CHOICE_FEMALE = _("Female")
CHOICE_OTHER = _("Other")
CHOICE_RNS = _("Rather not say")

GENDER_CHOICES = [
    ('', ''),
    (CHOICE_MALE, CHOICE_MALE),
    (CHOICE_FEMALE, CHOICE_FEMALE),
#    (CHOICE_OTHER, CHOICE_OTHER),
#    (CHOICE_RNS, CHOICE_RNS),
]
