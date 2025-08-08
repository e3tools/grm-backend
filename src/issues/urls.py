from django.urls import path

from .views import IssueCreateAPIView

app_name = "issues"
urlpatterns = [
    path('push/', IssueCreateAPIView.as_view(), name='create-issue'),
]
