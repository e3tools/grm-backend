from django.urls import path

from dashboard.couchdb_proxy import views

app_name = "couchdb_proxy"
urlpatterns = [
    path(
        "statistics-region-updated-tasks",
        views.StatisticsOfTasksUpdatedByRegionView.as_view(),
        name="statistics_region_updated_tasks",
    )
]
