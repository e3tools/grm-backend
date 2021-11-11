from django.urls import path

from dashboard.grm import views

app_name = 'grm'
urlpatterns = [
    path('', views.DashboardTemplateView.as_view(), name='dashboard'),
    path('start-new-issue', views.StartNewIssueView.as_view(), name='start_new_issue'),
    path('upload-issue-attachment/<int:issue>/', views.UploadIssueAttachmentFormView.as_view(),
         name='upload_issue_attachment'),
    path('delete-issue-attachment/<int:issue>/<str:attachment>/', views.IssueAttachmentDeleteView.as_view(),
         name='delete_issue_attachment'),
    path('issue-attachments/<int:issue>/', views.IssueAttachmentListView.as_view(), name='issue_attachments'),
    path('new-issue-step-1/<int:issue>/', views.NewIssueStep1FormView.as_view(), name='new_issue_step_1'),
    path('new-issue-step-2/<int:issue>/', views.NewIssueStep2FormView.as_view(), name='new_issue_step_2'),
    path('new-issue-step-3/<int:issue>/', views.NewIssueStep3FormView.as_view(), name='new_issue_step_3'),
    path('new-issue-step-4/<int:issue>/', views.NewIssueStep4FormView.as_view(), name='new_issue_step_4'),
    path('new-issue-step-5/<int:issue>/', views.NewIssueStep5FormView.as_view(), name='new_issue_step_5'),
    path('review-issues', views.ReviewIssuesFormView.as_view(), name='review_issues'),
    path('issue-list', views.IssueListView.as_view(), name='issue_list'),
    path('issue-detail/<int:issue>/', views.IssueDetailFormView.as_view(), name='issue_detail'),
    path('edit-issue/<int:issue>/', views.EditIssueView.as_view(), name='edit_issue'),
    path('add-comment-to-issue/<int:issue>/', views.AddCommentToIssueView.as_view(), name='add_comment_to_issue'),
    path('issue-comments/<int:issue>/', views.IssueCommentListView.as_view(), name='issue_comments'),
    path('submit-issue-result/<int:issue>/', views.SubmitIssueResearchResultFormView.as_view(),
         name='submit_issue_result'),
]
