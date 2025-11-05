from django.utils.translation import gettext_lazy as _

# User Types
GRM_MANAGER_CHOICE = "grm_manager"
CASE_MANAGER_CHOICE = "case_manager"
FACILITATOR_CHOICE = "facilitator"

USER_TYPE_CHOICES = [
    (GRM_MANAGER_CHOICE, _("GRM Manager")),
    (CASE_MANAGER_CHOICE, _("Case Manager")),
    (FACILITATOR_CHOICE, _("Facilitator")),
]

MAP_USER_TYPE = {
    GRM_MANAGER_CHOICE: _("GRM Manager"),
    CASE_MANAGER_CHOICE: _("Case Manager"),
    FACILITATOR_CHOICE: _("Facilitator"),
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
ADMINISTRATIVE_REGION_REQUIRED_MESSAGE = _("Administrative region is required for Facilitators.")
