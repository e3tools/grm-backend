from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from authentication.factories import UserFactory
from grm.constants import MAX_ATTACHMENTS
from grm.tests.base import DashboardTestCase
from issues.factories import IssueFactory
from issues.models import Comment, IssueAttachment


class UploadIssueAttachmentFormViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        # Reporter owns an unconfirmed issue
        self.reporter = UserFactory()
        self.issue = IssueFactory(
            reporter=self.reporter,
            confirmed=False,
            administrative_region=self.root_region,
        )
        self.url = reverse("dashboard:grm:upload_issue_attachment", kwargs={"issue": self.issue.id})

    def test_reporter_can_upload_attachment_ajax(self):
        file = SimpleUploadedFile("test.txt", b"hello", content_type="text/plain")
        count_before = IssueAttachment.objects.filter(issue=self.issue).count()
        resp = self.post(self.url, {"file": file}, user=self.reporter, ajax=True)
        assert resp.status_code == 200
        assert IssueAttachment.objects.filter(issue=self.issue).count() == count_before + 1

    def test_other_user_cannot_upload_to_unconfirmed_issue(self):
        other = UserFactory()
        file = SimpleUploadedFile("test.txt", b"hello", content_type="text/plain")
        resp = self.post(self.url, {"file": file}, user=other, ajax=True)
        # PermissionDenied returns 403 via handler
        assert resp.status_code == 403

    def test_upload_creates_comment(self):
        """
        When an attachment is uploaded successfully, a Comment should be created
        describing the action.
        """
        file = SimpleUploadedFile("test2.txt", b"hello", content_type="text/plain")
        resp = self.post(self.url, {"file": file}, user=self.reporter, ajax=True)
        assert resp.status_code == 200
        comments = Comment.objects.filter(issue=self.issue, user=self.reporter)
        assert comments.exists()
        assert "attachment" in comments.last().comment.lower()

    def test_upload_reaches_max_attachments(self):
        """
        If the issue already has MAX_ATTACHMENTS, uploading should not create a new one
        and should return an error message.
        """
        for i in range(MAX_ATTACHMENTS):
            IssueAttachment.objects.create(issue=self.issue, file=f"f{i}.txt", uploaded_by=self.reporter)
        file = SimpleUploadedFile("overflow.txt", b"hello", content_type="text/plain")
        count_before = IssueAttachment.objects.filter(issue=self.issue).count()
        resp = self.post(self.url, {"file": file}, user=self.reporter, ajax=True)
        assert resp.status_code == 200
        # No new attachment created
        assert IssueAttachment.objects.filter(issue=self.issue).count() == count_before
        # Response should contain error message
        assert "limit" in resp.content.decode().lower()

    @patch("issues.views.IssueAttachment.objects.create", side_effect=Exception("DB error"))
    def test_upload_handles_exception(self, mock_create):
        """
        If creating the IssueAttachment raises an exception, the view should
        add an error message and not crash.
        """
        file = SimpleUploadedFile("error.txt", b"hello", content_type="text/plain")
        resp = self.post(self.url, {"file": file}, user=self.reporter, ajax=True)
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "error" in content.lower()
