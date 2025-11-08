from django.urls import reverse

from authentication.factories import GovernmentWorkerFactory, UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    IssueDepartmentFactory,
    IssueFactory,
)
from issues.models import Comment


class AddCommentToIssueViewTest(DashboardTestCase):
    """
    Integration tests for AddCommentToIssueView.
    """

    def setUp(self):
        super().setUp()
        self.region = AdministrativeRegionFactory(parent=self.root_region)
        self.department = IssueDepartmentFactory()
        self.issue = IssueFactory(confirmed=True, administrative_region=self.region)
        self.url = reverse("dashboard:grm:add_comment_to_issue", kwargs={"issue": self.issue.id})

    def test_post_creates_comment_by_grm_manager(self):
        grm_manager = UserFactory(grm_manager=True)
        data = {"comment": "Manager note."}
        resp = self.post(self.url, data=data, ajax=True, user=grm_manager)
        assert resp.status_code == 200
        assert Comment.objects.filter(issue=self.issue, user=grm_manager, comment="Manager note.").exists()

    def test_post_creates_comment_by_government_worker(self):
        GovernmentWorkerFactory(user=self.issue.assignee, administrative_region=self.root_region)

        data = {"comment": "Worker comment."}
        resp = self.post(self.url, data=data, ajax=True, user=self.issue.assignee)

        assert resp.status_code == 200
        assert Comment.objects.filter(issue=self.issue, user=self.issue.assignee, comment="Worker comment.").exists()

    def test_post_empty_comment_does_not_create(self):
        grm_manager = UserFactory(grm_manager=True)
        resp = self.post(self.url, data={"comment": ""}, ajax=True, user=grm_manager)
        assert resp.status_code == 200
        assert not Comment.objects.filter(issue=self.issue, user=grm_manager, comment="").exists()

    def test_post_forbidden_for_unrelated_user(self):
        outsider = UserFactory()
        resp = self.post(self.url, data={"comment": "No access"}, ajax=True, user=outsider)
        assert resp.status_code == 403
        assert not Comment.objects.filter(issue=self.issue, user=outsider).exists()
