from django.urls import path

from dashboard.diagnostics import views

app_name = 'diagnostics'
urlpatterns = [
    path('', views.HomeFormView.as_view(), name='home'),
    path('issues-percentages/', views.IssuesPercentagesView.as_view(), name='issues_percentages'),
]
