from django.conf.urls import include
from django.urls import path

app_name = "dashboard"
urlpatterns = [
    path("", include("dashboard.authentication.urls")),
    path("diagnostics/", include("dashboard.diagnostics.urls")),
    path("grm/", include("dashboard.grm.urls")),
    path("search/", include("dashboard.search.urls")),
    path("user-management/", include("dashboard.user_management.urls")),
    path("performance-diagnostics/", include("dashboard.performance_diagnostics.urls")),
    # path('subprojects/', include('dashboard.subprojects.urls')),
    # path("couchdb-proxy/", include("dashboard.couchdb_proxy.urls")),
    path("settings/", include("dashboard.settings.urls")),
]
