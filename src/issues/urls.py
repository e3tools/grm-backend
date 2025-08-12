from django.urls import path

from issues.views import (
    IssueCategoryListView,
    IssueCreateAPIView,
    IssueStatusListAPIView,
    IssueTypeListView,
)

app_name = "issues"
urlpatterns = [
    path('push/', IssueCreateAPIView.as_view(), name='create-issue'),
    path('issue-statuses/', IssueStatusListAPIView.as_view(), name='list-issue-statuses'),
    path('issue-types/', IssueTypeListView.as_view(), name='list-issue-types'),
    path('issue-categories/', IssueCategoryListView.as_view(), name='list-issue-categories'),
]
