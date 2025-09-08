from django.urls import path

from issues.views import (
    AssigneeIssueListAPIView,
    IssueCategoryListAPIView,
    IssueCommentCreateAPIView,
    IssueCommentsListAPIView,
    IssueCreateAPIView,
    IssueRetrieveAPIView,
    IssueStatusListAPIView,
    IssueTypeListAPIView,
    ReporterIssueListAPIView,
)

app_name = "issues"
urlpatterns = [
    path('create/', IssueCreateAPIView.as_view(), name='create-issue'),
    path("assignee/", AssigneeIssueListAPIView.as_view(), name="list-assigned-issues"),
    path("reporter/", ReporterIssueListAPIView.as_view(), name="list-reported-issues"),
    path('<int:id>/', IssueRetrieveAPIView.as_view(), name='issue-detail'),
    path('issue-statuses/', IssueStatusListAPIView.as_view(), name='list-issue-statuses'),
    path('issue-types/', IssueTypeListAPIView.as_view(), name='list-issue-types'),
    path('issue-categories/', IssueCategoryListAPIView.as_view(), name='list-issue-categories'),
    path('<int:id>/add-comment', IssueCommentCreateAPIView.as_view(), name='add-issue-comment'),
    path('<int:id>/comments/', IssueCommentsListAPIView.as_view(), name='list-issue-comments'),
]
