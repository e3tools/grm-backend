from django.urls import path

from dashboard.performance_diagnostics import views

app_name = "performance_diagnostics"

urlpatterns = [
    path("", views.PerformanceDiagnosticsView.as_view(), name="dashboard"),
    path("api/metrics/", views.PerformanceMetricsAPIView.as_view(), name="api_metrics"),
    path('api/status-bottlenecks/', views.StatusBottleneckMetricsAPIView.as_view(), name='api_status_bottlenecks'),
    path("api/region-performance/", views.RegionPerformanceAPIView.as_view(), name="api_region_performance"),
    path("api/inactive-users/", views.InactiveUsersAPIView.as_view(), name="api_inactive_users"),
    path("api/get-selected-users/", views.GetSelectedUsersInfoAPIView.as_view(), name="api_get_selected_users"),
    path("api/send-bulk-notification/", views.SendBulkNotificationAPIView.as_view(), name="api_send_bulk_notification"),
]
