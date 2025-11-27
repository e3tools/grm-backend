from django.urls import path

from dashboard.performance_diagnostics import views
from dashboard.performance_diagnostics.views import StatusBottleneckMetricsAPIView

app_name = "performance_diagnostics"

urlpatterns = [
    path("", views.PerformanceDiagnosticsView.as_view(), name="dashboard"),
    path("api/metrics/", views.PerformanceMetricsAPIView.as_view(), name="api_metrics"),
    path('api/status-bottlenecks/', StatusBottleneckMetricsAPIView.as_view(), name='api_status_bottlenecks'),
]
