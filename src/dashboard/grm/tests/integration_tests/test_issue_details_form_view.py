from django.urls import reverse

from authentication.factories import GovernmentWorkerFactory, UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import AdministrativeLevelFactory, AdministrativeRegionFactory, IssueFactory


class IssueDetailsFormViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.issue = IssueFactory(confirmed=True, administrative_region=self.root_region)
        self.url = reverse("dashboard:grm:issue_detail", kwargs={"issue": self.issue.id})

    def test_get_allowed_for_manager(self):
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 200

    def test_get_denied_for_normal_user(self):
        resp = self.get(self.url, user=self.normal_user)
        assert resp.status_code == 403

    def test_get_shows_assignee_administrative_level_and_department(self):
        dept = self.issue.category.assigned_department.department
        dept.head = UserFactory()
        dept.save(update_fields=["head"])
        level = AdministrativeLevelFactory(name="DetailViewLevelUnique")
        worker_region = AdministrativeRegionFactory(administrative_level=level, parent=self.root_region)
        GovernmentWorkerFactory(
            user=self.issue.assignee,
            department=dept,
            administrative_region=worker_region,
        )
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "DetailViewLevelUnique" in body
        assert dept.name in body
