from django.urls import path

from authentication.views import (
    CitizenLoginView,
    CitizenRegistrationCreateAPIView,
    LoginView,
)

app_name = "authentication"

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('citizen-login/', CitizenLoginView.as_view(), name='citizen-login'),
    path('register/', CitizenRegistrationCreateAPIView.as_view(), name='citizen-register'),
]
