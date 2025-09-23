from django.urls import path

from wizard.views import (
    AdministrativeLevelsFormView,
    CustomizationWizardView,
    ProjectUpdateView,
    WizardSectionListView,
)

app_name = "wizard"
urlpatterns = [
    path("", CustomizationWizardView.as_view(), name="customization_wizard"),
    path("wizard-section-list", WizardSectionListView.as_view(), name="wizard_section_list"),
    path("setup-step-1", ProjectUpdateView.as_view(), name="setup_step_1"),
    path("setup-step-2", AdministrativeLevelsFormView.as_view(), name="setup_step_2"),
]
