from django.urls import path

from authentication import views

app_name = 'authentication'

urlpatterns = [
    path('register/', views.RegisterAPIView.as_view(), name='register'),
    path('obtain-auth-credentials/', views.AuthenticateAPIView.as_view(), name='obtain_auth_credentials'),
    path('check-adl-status/', views.ADLActiveAPIView.as_view(), name='check_adl_status'),
    path('get-adl-administrative-region/', views.ADLAdministrativeRegionAPIView.as_view(), name='get_adl_administrative_region'),
]
