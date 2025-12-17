from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    CommentFactory,
    IssueDepartmentFactory,
    IssueFactory,
)


class IssueCommentListViewTest(DashboardTestCase):
    """
    Integration tests for IssueCommentListView.
    Validates GET (list) and POST (create) behaviors under permissions.
    """

    def setUp(self):
        super().setUp()
        self.region = AdministrativeRegionFactory(parent=self.root_region)
        self.department = IssueDepartmentFactory()
        self.issue = IssueFactory(confirmed=True, administrative_region=self.region)
        # Note: IssueCommentListView is mapped with 'issue' kwarg
        self.url = reverse("dashboard:grm:issue_comments", kwargs={"issue": self.issue.id})

    def test_get_returns_existing_comments_html(self):
        """GET returns the rendered HTML containing existing comment texts."""
        user1 = UserFactory()
        c1 = CommentFactory(user=user1, comment="First comment", issue=self.issue)
        c2 = CommentFactory(user=user1, comment="Second comment", issue=self.issue)

        grm_manager = UserFactory(grm_manager=True)
        resp = self.get(self.url, ajax=True, user=grm_manager)
        assert resp.status_code == 200
        context_data = resp.context_data
        assert {comment.id for comment in context_data['comments']} == {c1.id, c2.id}

    def test_get_forbidden_for_unauthenticated_or_unrelated_user(self):
        """A user without access should be denied (403)."""
        # not logged in (client without user) -> our helper 403
        resp = self.get(self.url, authorized=False, ajax=True)
        assert resp.status_code == 403

        # logged user with no permissions (plain user)
        plain_user = UserFactory()
        resp2 = self.get(self.url, ajax=True, user=plain_user)
        # permission logic may return 403
        assert resp2.status_code == 403
