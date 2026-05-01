from django.urls import path

from authentication.views import (
    CitizenDetailAPIView,
    CitizenLoginAPIView,
    CitizenRegistrationCreateAPIView,
    CitizenUpdateAPIView,
    FacilitatorLoginAPIView,
    FacilitatorProfileAPIView,
    LoginAPIView,
    PasswordResetAPIView,
    PasswordResetConfirmView,
    PasswordResetView,
)

app_name = "authentication"

urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='login'),
    path('citizen-login/', CitizenLoginAPIView.as_view(), name='citizen-login'),
    path('register/', CitizenRegistrationCreateAPIView.as_view(), name='citizen-register'),
    path("citizen-detail", CitizenDetailAPIView.as_view(), name="citizen-detail"),
    path("citizen-update/", CitizenUpdateAPIView.as_view(), name="citizen-update"),
    path('password-reset/', PasswordResetAPIView.as_view(), name='password-reset'),
    path('password-reset-form/', PasswordResetView.as_view(), name='password_reset'),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path('facilitator-profile/', FacilitatorProfileAPIView.as_view(), name='facilitator-profile'),
    path('facilitator-login/', FacilitatorLoginAPIView.as_view(), name='facilitator-login'),
]
