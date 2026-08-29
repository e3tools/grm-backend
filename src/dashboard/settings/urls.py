from django.urls import path

from dashboard.settings import views

app_name = "settings"
urlpatterns = [
    path("", views.SettingsTemplateView.as_view(), name="main"),
    path("by-status", views.SettingsByIssueStatusFormView.as_view(), name="by_status"),
]
