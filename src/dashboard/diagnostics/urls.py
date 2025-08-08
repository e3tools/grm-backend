from django.urls import path

from dashboard.diagnostics import views

app_name = "diagnostics"
urlpatterns = [
    path("", views.HomeFormView.as_view(), name="home"),
    path(
        "issues-statistics/",
        views.IssuesStatisticsView.as_view(),
        name="issues_statistics",
    ),
    path(
        "update-issues-data/",
        views.UpdateIssuesDataView.as_view(),
        name="update_issues_data",
    ),
]
