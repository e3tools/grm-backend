from django.urls import path

from issues.views import IssueCreateAPIView, IssueStatusListAPIView

app_name = "issues"
urlpatterns = [
    path('push/', IssueCreateAPIView.as_view(), name='create-issue'),
    path('issue-statuses/', IssueStatusListAPIView.as_view(), name='list-issue-statuses'),
]
