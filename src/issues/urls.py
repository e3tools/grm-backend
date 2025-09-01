from django.urls import path

from issues.views import (
    IssueCategoryListView,
    IssueCreateAPIView,
    IssueListAPIView,
    IssueRetrieveAPIView,
    IssueStatusListAPIView,
    IssueTypeListView,
)

app_name = "issues"
urlpatterns = [
    path('create/', IssueCreateAPIView.as_view(), name='create-issue'),
    path('list/', IssueListAPIView.as_view(), name='list-issues'),
    path('<int:id>/', IssueRetrieveAPIView.as_view(), name='issue-detail'),
    path('issue-statuses/', IssueStatusListAPIView.as_view(), name='list-issue-statuses'),
    path('issue-types/', IssueTypeListView.as_view(), name='list-issue-types'),
    path('issue-categories/', IssueCategoryListView.as_view(), name='list-issue-categories'),
]
