from django.contrib.auth import views as auth_views
from django.urls import path

from dashboard.authentication.views import CustomLoginView

app_name = "authentication"
urlpatterns = [
    path("", CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
