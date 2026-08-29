from django.utils.translation import gettext_lazy as _

# User Types
GRM_MANAGER_CHOICE = "grm_manager"
CASE_MANAGER_CHOICE = "case_manager"
FACILITATOR_CHOICE = "facilitator"
GRM_MANAGER_DISPLAY = _("GRM Manager")
CASE_MANAGER_DISPLAY = _("Case Manager")
FACILITATOR_DISPLAY = _("Facilitator")

USER_TYPE_CHOICES = [
    (GRM_MANAGER_CHOICE, GRM_MANAGER_DISPLAY),
    (CASE_MANAGER_CHOICE, CASE_MANAGER_DISPLAY),
    (FACILITATOR_CHOICE, FACILITATOR_DISPLAY),
]

MAP_USER_TYPE = {
    GRM_MANAGER_CHOICE: GRM_MANAGER_DISPLAY,
    CASE_MANAGER_CHOICE: CASE_MANAGER_DISPLAY,
    FACILITATOR_CHOICE: FACILITATOR_DISPLAY,
}

# Success Messages
USER_CREATED_SUCCESS_MESSAGE = _("User '%(name)s' was successfully created.")
USER_UPDATED_SUCCESS_MESSAGE = _("User '%(name)s' was successfully updated.")

# Error Messages
USER_CREATION_ERROR_MESSAGE = _("There was an error creating the user. Please try again.")
DEPARTMENT_REQUIRED_MESSAGE = _("Department is required for Case Managers.")
DEPARTMENT_ASSIGNMENT_ERROR_MESSAGE = _(
    "Department '%(dept)s' already has a head: %(head)s. You must unassign the current head first."
)
ADMINISTRATIVE_REGION_REQUIRED_MESSAGE = _("Administrative level is required.")
