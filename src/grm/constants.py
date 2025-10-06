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

NOT_STARTED_CHOICE = "not_started"
IN_PROGRESS_CHOICE = "in_progress"
COMPLETED_CHOICE = "completed"
STATUS_CHOICES = [
    (NOT_STARTED_CHOICE, _("Not Started")),
    (IN_PROGRESS_CHOICE, _("In Progress")),
    (COMPLETED_CHOICE, _("Completed")),
]

DEPARTMENT_HEAD_CHOICE = "department_head"
FEWER_ISSUES_CHOICE = "fewer_issues"
REDIRECTION_PROTOCOL_CHOICES = [
    (DEPARTMENT_HEAD_CHOICE, _("Department head")),
    (FEWER_ISSUES_CHOICE, _("Person with fewer issues")),
]

LOW_CHOICE = "low"
CONFIDENTIALITY_LEVEL_CHOICES = [
    (LOW_CHOICE, _("Low")),
    (ANONYMOUS_CHOICE, _("Anonymous")),
]

TEXTAREA_MAX_LENGTH = 65000
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
MAX_UPLOAD_SIZE_FILE_FORMAT = filesizeformat_en(MAX_UPLOAD_SIZE)
MAX_ATTACHMENTS = 20
FILE_HELP_TEXT = _("Allowed file size less than or equal to %s")
FILE_SIZE_ERROR_MESSAGE = _("Select a file with a size less than or equal to %s. The selected file is %s in size.")
VALIDATION_FAILED_MESSAGE = _('Validation failed.')
NOT_FOUND_MESSAGE = _('Not found.')
NOT_PERMITTED_TEXT = _('Action not permitted')
CONTACT_MEDIUM_ERROR_MESSAGE = _("You must define the contact method is your contact medium is channel alert")
CONTACT_INFO_EMAIL_ERROR_MESSAGE = _("If email contact method is selected, provide a valid email")
CONTACT_INFO_NO_EMAIL_ERROR_MESSAGE = _("If phone or whatsapp contact method is selected, provide a valid phone number")
ISSUE_CREATE_SUCCESS_MESSAGE = _('Issue created successfully.')
ISSUE_CREATE_ERROR_MESSAGE = _('An error occurred while creating the issue.')
ISSUE_UPDATE_SUCCESS_MESSAGE = _('Issue updated successfully.')
ISSUE_UPDATE_ERROR_MESSAGE = _('An error occurred while updating the issue.')
ISSUE_UPDATE_STATUS_ERROR_MESSAGE = _('Only assignees can update the status field.')
ISSUE_UPDATE_RATING_ERROR_MESSAGE = _('Only reporters can update the rating field.')
ISSUE_RETRIEVE_ERROR_MESSAGE = _('An error occurred while retrieving the issue.')
ISSUE_LIST_ERROR_MESSAGE = _("Invalid datetime format. Use ISO 8601 (e.g. 2021-03-23T10:30:45Z).")
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
ADMINISTRATIVE_LEVEL_DELETE_ERROR_MESSAGE = _(
    "You cannot delete '%(name)s' because it is linked to issues or departments."
)
ADMINISTRATIVE_LEVEL_TOAST_ERROR_MESSAGE = _('This administrative level cannot be deleted because it is in use.')
ADMINISTRATIVE_LEVEL_EXCEL_WORKBOOK_TITLE = _("Administrative Level Instances")
ADMINISTRATIVE_LEVEL_UPLOAD_SUCCESS_MESSAGE = _("Successfully created %(count)d administrative level instances.")
ADMINISTRATIVE_LEVEL_UPLOAD_DUPLICATES_MESSAGE = _("Skipped %(count)d duplicates that already existed.")
ADMINISTRATIVE_LEVEL_UPLOAD_UNCHANGEABLE_MESSAGE = _(
    "%(count)d administrative level instances could not be modified because they are already in use."
)
ADMINISTRATIVE_LEVEL_UPLOAD_DELETE_MESSAGE = _("All administrative level instances have been deleted.")
ADMINISTRATIVE_LEVEL_UPLOAD_NOT_FOUND_MESSAGE = _("Administrative level %(level)s not found in database")
ADMINISTRATIVE_LEVEL_UPLOAD_NO_HEADER_MESSAGE = _("The Excel file must contain a header row.")
ADMINISTRATIVE_LEVEL_UPLOAD_ROOT_ALREADY_EXISTS_MESSAGE = _(
    "The first administrative level instance already exists with the name %(root)s. "
    "The instance with the value %(new)s does not match this level in the Excel file."
)
ADMINISTRATIVE_LEVEL_UPLOAD_ROOT_UNIQUE_MESSAGE = _(
    "The value of the instance of the first administrative level (first column) must be the same value for all cells "
    "in the column. Expected %(root)s, found %(new)s."
)
ONLY_EXCEL_FILE_EXTENSIONS_ERROR_MESSAGE = _("Only Excel files (.xls, .xlsx) are allowed.")
INVALID_EXCEL_FILE_ERROR_MESSAGE = _("The uploaded file is not a valid Excel file.")
DEPARTMENT_DELETE_ERROR_MESSAGE = _("You cannot delete '%(name)s' because it is linked to administrative level.")
DEPARTMENT_TOAST_ERROR_MESSAGE = _('This department cannot be deleted because it is in use.')
CATEGORY_DELETE_ERROR_MESSAGE = _("You cannot delete '%(name)s' because it is linked to issues.")
CATEGORY_TOAST_ERROR_MESSAGE = _('This category cannot be deleted because it is in use.')
