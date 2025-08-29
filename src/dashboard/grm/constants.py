from django.utils.translation import gettext_lazy as _

CHOICE_ANONYMOUS = "anonymous"
CHOICE_FACILITATOR = "facilitator"
CHOICE_ALERT = "channel-alert"
MEDIUM_CHOICES = [
    (CHOICE_ANONYMOUS, _("Remain anonymous")),
    (CHOICE_FACILITATOR, _("Receive updates from facilitator")),
    (CHOICE_ALERT, _("Receive updates directly")),
]

CHOICE_EMAIL = "email"
CHOICE_PHONE = "phone_number"
CHOICE_WHATSAPP = "whatsapp"
CONTACT_CHOICES = [
    ("", ""),
    (CHOICE_EMAIL, _("email")),
    (CHOICE_PHONE, _("phone number")),
    (CHOICE_WHATSAPP, _("whatsapp")),
]
CHOICE_CONFIDENTIAL = 'keep_name_confidential'
CHOICE_INDIVIDUAL = 'on_behalf_of_someone'
CHOICE_ORGANIZATION = 'organization_behalf_someone'

CITIZEN_TYPE_CHOICES = [
    (
        CHOICE_CONFIDENTIAL,
        _("Keep name confidential. Only the person resolving the issue will see the name."),
    ),
    (CHOICE_INDIVIDUAL, _("This is an individual filing on behalf of someone else.")),
    (CHOICE_ORGANIZATION, _("This is an organization filing on behalf of someone else.")),
]

CHOICE_0_OR_1_LABEL = _("Complainant")
CITIZEN_TYPE_CHOICES_ALT = [
    (None, CHOICE_0_OR_1_LABEL),
    (CHOICE_CONFIDENTIAL, CHOICE_0_OR_1_LABEL),
    (CHOICE_INDIVIDUAL, _("Citizen on behalf of others")),
    (CHOICE_ORGANIZATION, _("Organization on behalf of others")),
]

CHOICE_MALE = "male"
CHOICE_FEMALE = "female"
CHOICE_OTHER = "other"
CHOICE_RNS = "rather_not_say"
GENDER_CHOICES = [
    ("", ""),
    (CHOICE_MALE, _("Male")),
    (CHOICE_FEMALE, _("Female")),
    #    (CHOICE_OTHER, _("Other")),
    #    (CHOICE_RNS, _("Rather not say")),
]

CHOICE_ACCEPTED = "accepted"
CHOICE_REJECTED = "rejected"
CHOICE_CLOSED = "closed"

ALERT_CHOICES = [
    ("", ""),
    (CHOICE_ACCEPTED, CHOICE_ACCEPTED),
    (CHOICE_REJECTED, CHOICE_REJECTED),
    (CHOICE_CLOSED, CHOICE_CLOSED),
]

CHOICE_CITIZEN_GROUP = "citizen_group"
CHOICE_CITIZEN_GROUP2 = "citizen_group_2"

CITIZEN_GROUP_CHOICES = (
    (CHOICE_CITIZEN_GROUP, _('Citizen group')),
    (CHOICE_CITIZEN_GROUP2, _('Citizen group 2')),
)

TEXTAREA_MAX_LENGTH = 65000

CONTACT_MEDIUM_ERROR_MESSAGE = _("You must define the contact method is your contact medium is channel alert")
CONTACT_INFO_EMAIL_ERROR_MESSAGE = _("If email contact method is selected, provide a valid email")
CONTACT_INFO_NO_EMAIL_ERROR_MESSAGE = _("If phone or whatsapp contact method is selected, provide a valid phone number")
