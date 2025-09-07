from django.urls import path

from issues.views import (
    IssueAttachmentCreateAPIView,
    IssueAttachmentsListAPIView,
    IssueCategoryListAPIView,
    IssueCommentCreateAPIView,
    IssueCommentsListAPIView,
    IssueCreateAPIView,
    IssueListAPIView,
    IssueRetrieveAPIView,
    IssueStatusListAPIView,
    IssueTypeListAPIView,
)

app_name = "issues"
urlpatterns = [
    path('create/', IssueCreateAPIView.as_view(), name='create-issue'),
    path('list/', IssueListAPIView.as_view(), name='list-issues'),
    path('<int:id>/', IssueRetrieveAPIView.as_view(), name='issue-detail'),
    path('issue-statuses/', IssueStatusListAPIView.as_view(), name='list-issue-statuses'),
    path('issue-types/', IssueTypeListAPIView.as_view(), name='list-issue-types'),
    path('issue-categories/', IssueCategoryListAPIView.as_view(), name='list-issue-categories'),
    path('<int:id>/add-comment', IssueCommentCreateAPIView.as_view(), name='add-issue-comment'),
    path('<int:id>/comments/', IssueCommentsListAPIView.as_view(), name='list-issue-comments'),
    path('<int:id>/add-attachment', IssueAttachmentCreateAPIView.as_view(), name='add-issue-attachment'),
    path('<int:id>/attachments/', IssueAttachmentsListAPIView.as_view(), name='list-issue-attachments'),
]
