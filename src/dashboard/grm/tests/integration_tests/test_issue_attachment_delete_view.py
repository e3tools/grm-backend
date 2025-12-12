from django.urls import reverse
from django.utils import timezone

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import IssueAttachmentFactory, IssueFactory
from issues.models import Comment, IssueAttachment


class IssueAttachmentDeleteViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        # Reporter owns an unconfirmed issue
        self.reporter = UserFactory()
        self.issue = IssueFactory(
            reporter=self.reporter,
            confirmed=False,
            administrative_region=self.root_region,
        )
        # Create an attachment owned by reporter
        self.attachment = IssueAttachmentFactory(issue=self.issue, uploaded_by=self.reporter)
        self.url = reverse(
            "dashboard:grm:delete_issue_attachment",
            kwargs={"issue": self.issue.id, "attachment": self.attachment.id},
        )

    def test_reporter_can_delete_attachment_ajax(self):
        before = timezone.now()
        count_before = IssueAttachment.objects.filter(issue=self.issue).count()
        resp = self.post(self.url, {}, user=self.reporter, ajax=True)
        assert resp.status_code == 200
        assert IssueAttachment.objects.filter(issue=self.issue).count() == count_before - 1

        # Check last_activity was updated
        self.reporter.refresh_from_db()
        assert self.reporter.last_activity >= before

    def test_other_user_cannot_delete_attachment_from_unconfirmed_issue(self):
        other = UserFactory()
        resp = self.post(self.url, {}, user=other, ajax=True)
        assert resp.status_code == 403

    def test_delete_creates_comment(self):
        """
        When an attachment is deleted successfully, a Comment should be created
        describing the action.
        """
        resp = self.post(self.url, {}, user=self.reporter, ajax=True)
        assert resp.status_code == 200
        comments = Comment.objects.filter(issue=self.issue, user=self.reporter)
        assert comments.exists()
        assert "deleted" in comments.last().comment.lower()

    def test_delete_nonexistent_attachment_still_returns_success(self):
        """
        If the attachment id does not exist, the view should still return 200
        and not crash, but no Comment is created.
        """
        bad_url = reverse(
            "dashboard:grm:delete_issue_attachment",
            kwargs={"issue": self.issue.id, "attachment": 99999},
        )
        resp = self.post(bad_url, {}, user=self.reporter, ajax=True)
        assert resp.status_code == 200
        # No new comments created
        assert not Comment.objects.filter(issue=self.issue, user=self.reporter).exists()
        # Response should contain success message
        assert "successfully deleted" in resp.content.decode().lower()
