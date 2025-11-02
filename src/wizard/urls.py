from django.urls import path

from wizard import views
from wizard.registry import get_all_wizard_steps

app_name = "wizard"

urlpatterns = [
    path("", views.CustomizationWizardView.as_view(), name="customization_wizard"),
    path("wizard-section-list", views.WizardSectionListView.as_view(), name="wizard_section_list"),
    path("download-regions-sample", views.DownloadRegionsSampleView.as_view(), name="download_regions_sample"),
    path("next-step/<int:step>/", views.NextStepView.as_view(), name="next_step"),
]

# Generate URLs dynamically from the registry
wizard_steps = get_all_wizard_steps()
for step_config in wizard_steps.values():
    step = step_config['step']
    view_class = step_config['view_class']
    urlpatterns.append(path(f"setup-step-{step}", view_class.as_view(), name=f"setup_step_{step}"))
