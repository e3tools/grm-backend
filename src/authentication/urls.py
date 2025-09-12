from django.urls import path

from authentication.views import CitizenRegistrationCreateAPIView, LoginView

app_name = "authentication"

urlpatterns = [
    path('login/', LoginView.as_view(), name='auth-login'),
    path('register/', CitizenRegistrationCreateAPIView.as_view(), name='citizen-register'),
]
