from django.urls import path

from wizard.views import (
    AdministrativeLevelsFormView,
    AdministrativeRegionFormView,
    CustomizationWizardView,
    DownloadRegionsSampleView,
    FeedbackAndAppealFormView,
    IssueCategoriesFormView,
    IssueDepartmentsFormView,
    NextStepView,
    ProjectUpdateView,
    ResolutionProcessFormView,
    WizardSectionListView,
)

app_name = "wizard"
urlpatterns = [
    path("", CustomizationWizardView.as_view(), name="customization_wizard"),
    path("wizard-section-list", WizardSectionListView.as_view(), name="wizard_section_list"),
    path("download-regions-sample", DownloadRegionsSampleView.as_view(), name="download_regions_sample"),
    path("next-step<int:step>/", NextStepView.as_view(), name="next_step"),
    path("setup-step-1", ProjectUpdateView.as_view(), name="setup_step_1"),
    path("setup-step-2", AdministrativeLevelsFormView.as_view(), name="setup_step_2"),
    path("setup-step-3", AdministrativeRegionFormView.as_view(), name="setup_step_3"),
    path("setup-step-4", IssueDepartmentsFormView.as_view(), name="setup_step_4"),
    path("setup-step-5", IssueCategoriesFormView.as_view(), name="setup_step_5"),
    path("setup-step-6", ResolutionProcessFormView.as_view(), name="setup_step_6"),
    path("setup-step-7", FeedbackAndAppealFormView.as_view(), name="setup_step_7"),
]
