from django.urls import path

from dashboard.wizard.views import CustomizationWizardView

app_name = "wizard"
urlpatterns = [
    path("", CustomizationWizardView.as_view(), name="customization_wizard"),
]
