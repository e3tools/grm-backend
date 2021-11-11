from django.urls import path

from dashboard.diagnostics import views

app_name = 'diagnostics'
urlpatterns = [
    path('', views.HomeTemplateView.as_view(), name='home'),
]
