from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import IssueAttachmentFactory, IssueFactory


class IssueAttachmentListViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        # Unconfirmed issue where only reporter can view
        self.reporter = UserFactory()
        self.issue_unconfirmed = IssueFactory(
            reporter=self.reporter, confirmed=False, administrative_region=self.root_region
        )
        IssueAttachmentFactory(issue=self.issue_unconfirmed, uploaded_by=self.reporter)
        self.url_unconfirmed = reverse("dashboard:grm:issue_attachments", kwargs={"issue": self.issue_unconfirmed.id})

        # Confirmed issue where manager/PIU staff may view
        self.manager = UserFactory(grm_manager=True)
        self.issue_confirmed = IssueFactory(confirmed=True, administrative_region=self.root_region)
        IssueAttachmentFactory(issue=self.issue_confirmed, uploaded_by=self.manager)
        self.url_confirmed = reverse("dashboard:grm:issue_attachments", kwargs={"issue": self.issue_confirmed.id})

    def test_reporter_can_view_unconfirmed_issue_attachments_ajax(self):
        resp = self.get(self.url_unconfirmed, user=self.reporter, ajax=True)
        assert resp.status_code == 200

    def test_other_user_cannot_view_unconfirmed_issue_attachments(self):
        other = UserFactory()
        resp = self.get(self.url_unconfirmed, user=other, ajax=True)
        assert resp.status_code == 403

    def test_manager_can_view_confirmed_issue_attachments(self):
        resp = self.get(self.url_confirmed, user=self.manager, ajax=True)
        assert resp.status_code == 200
