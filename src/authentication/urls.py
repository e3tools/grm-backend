from django.urls import path

from authentication.views import (
    CitizenLoginAPIView,
    CitizenRegistrationCreateAPIView,
    LoginAPIView,
    PasswordResetAPIView,
)

app_name = "authentication"

urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='login'),
    path('citizen-login/', CitizenLoginAPIView.as_view(), name='citizen-login'),
    path('register/', CitizenRegistrationCreateAPIView.as_view(), name='citizen-register'),
    path('password-reset/', PasswordResetAPIView.as_view(), name='password-reset'),
]
