from django.utils.translation import gettext_lazy as _

from grm.utils import filesizeformat_en

ANONYMOUS_CHOICE = "anonymous"
FACILITATOR_CHOICE = "facilitator"
ALERT_CHOICE = "channel-alert"
MEDIUM_CHOICES = [
    (ANONYMOUS_CHOICE, _("Remain anonymous")),
    (FACILITATOR_CHOICE, _("Receive updates from facilitator")),
    (ALERT_CHOICE, _("Receive updates directly")),
]

EMAIL_CHOICE = "email"
PHONE_CHOICE = "phone_number"
WHATSAPP_CHOICE = "whatsapp"
CONTACT_CHOICES = [
    ("", ""),
    (EMAIL_CHOICE, _("email")),
    (PHONE_CHOICE, _("phone number")),
    (WHATSAPP_CHOICE, _("whatsapp")),
]
CONFIDENTIAL_CHOICE = 'keep_name_confidential'
INDIVIDUAL_CHOICE = 'on_behalf_of_someone'
ORGANIZATION_CHOICE = 'organization_behalf_someone'

CITIZEN_TYPE_CHOICES = [
    (
        CONFIDENTIAL_CHOICE,
        _("Keep name confidential. Only the person resolving the issue will see the name."),
    ),
    (INDIVIDUAL_CHOICE, _("This is an individual filing on behalf of someone else.")),
    (ORGANIZATION_CHOICE, _("This is an organization filing on behalf of someone else.")),
]

CONFIDENTIAL_LABEL_CHOICE = _("Complainant")
CITIZEN_TYPE_CHOICES_ALT = [
    (None, CONFIDENTIAL_LABEL_CHOICE),
    (CONFIDENTIAL_CHOICE, CONFIDENTIAL_LABEL_CHOICE),
    (INDIVIDUAL_CHOICE, _("Citizen on behalf of others")),
    (ORGANIZATION_CHOICE, _("Organization on behalf of others")),
]

MALE_CHOICE = "male"
FEMALE_CHOICE = "female"
OTHER_CHOICE = "other"
RNS_CHOICE = "rather_not_say"
GENDER_CHOICES = [
    ("", ""),
    (MALE_CHOICE, _("Male")),
    (FEMALE_CHOICE, _("Female")),
    #    (CHOICE_OTHER, _("Other")),
    #    (CHOICE_RNS, _("Rather not say")),
]

ACCEPTED_CHOICE = "accepted"
REJECTED_CHOICE = "rejected"
CLOSED_CHOICE = "closed"

ALERT_CHOICES = [
    ("", ""),
    (ACCEPTED_CHOICE, ACCEPTED_CHOICE),
    (REJECTED_CHOICE, REJECTED_CHOICE),
    (CLOSED_CHOICE, CLOSED_CHOICE),
]

CITIZEN_GROUP_CHOICE = "citizen_group"
CITIZEN_GROUP2_CHOICE = "citizen_group_2"

CITIZEN_GROUP_CHOICES = (
    (CITIZEN_GROUP_CHOICE, _('Citizen group')),
    (CITIZEN_GROUP2_CHOICE, _('Citizen group 2')),
)

TEXTAREA_MAX_LENGTH = 65000
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
MAX_UPLOAD_SIZE_FILE_FORMAT = filesizeformat_en(MAX_UPLOAD_SIZE)
MAX_ATTACHMENTS = 20
FILE_HELP_TEXT = _("Allowed file size less than or equal to %s") % MAX_UPLOAD_SIZE_FILE_FORMAT
FILE_SIZE_ERROR_MESSAGE = _("Select a file with a size less than or equal to %s. The selected file is %s in size.") % (
    MAX_UPLOAD_SIZE_FILE_FORMAT,
    "%s",
)
VALIDATION_FAILED_MESSAGE = _('Validation failed.')
NOT_FOUND_MESSAGE = _('Not found.')
CONTACT_MEDIUM_ERROR_MESSAGE = _("You must define the contact method is your contact medium is channel alert")
CONTACT_INFO_EMAIL_ERROR_MESSAGE = _("If email contact method is selected, provide a valid email")
CONTACT_INFO_NO_EMAIL_ERROR_MESSAGE = _("If phone or whatsapp contact method is selected, provide a valid phone number")
ISSUE_CREATE_SUCCESS_MESSAGE = _('Issue created successfully.')
ISSUE_CREATE_ERROR_MESSAGE = _('An error occurred while creating the issue.')
ISSUE_UPDATE_SUCCESS_MESSAGE = _('Issue updated successfully.')
ISSUE_UPDATE_ERROR_MESSAGE = _('An error occurred while updating the issue.')
ISSUE_RETRIEVE_ERROR_MESSAGE = _('An error occurred while retrieving the issue.')
RATING_ERROR_MESSAGE = _("Rating must be between 1 and 5.")
COMMENT_CREATE_SUCCESS_MESSAGE = _('Comment added successfully.')
COMMENT_CREATE_ERROR_MESSAGE = _('An error occurred while creating the comment.')
COMMENT_RETRIEVE_ERROR_MESSAGE = _('An error occurred while retrieving issue comments.')
COMMENT_DELETE_ERROR_MESSAGE = _("An error occurred while deleting the comment.")
EMPTY_COMMENT_ERROR_MESSAGE = _("Comment cannot be empty.")
ATTACHMENT_CREATE_SUCCESS_MESSAGE = _('Attachment uploaded successfully.')
ATTACHMENT_CREATE_ERROR_MESSAGE = _('An error occurred during file upload.')
ATTACHMENT_RETRIEVE_ERROR_MESSAGE = _('An error occurred while retrieving issue attachments.')
CITIZEN_SUCCESS_MESSAGE = _('Citizen registered successfully.')
USERNAME_ERROR_MESSAGE = _("A user with that username already exists.")
EMAIL_ERROR_MESSAGE = _("user with this email address already exists.")


WELCOME_CHOICE = "welcome"
ADMIN_LEVELS_CHOICE = "admin_levels"
ROLES_CHOICE = "roles"
ENTRY_TYPES_CHOICE = "entry_types"
CATEGORIES_CHOICE = "categories"
FEEDBACK_CHOICE = "feedback"
COMPLETE_CHOICE = "complete"
STATE_CHOICES = [
    (WELCOME_CHOICE, _("Welcome")),
    (ADMIN_LEVELS_CHOICE, _("Admin Levels")),
    (ROLES_CHOICE, _("Roles")),
    (ENTRY_TYPES_CHOICE, _("Entry Types")),
    (CATEGORIES_CHOICE, _("Categories")),
    (FEEDBACK_CHOICE, _("Feedback")),
    (COMPLETE_CHOICE, _("Complete")),
]
