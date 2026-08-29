from datetime import datetime, timedelta

from django.urls import reverse

from authentication.factories import UserFactory
from authentication.models import GovernmentWorker
from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueDepartmentAdministrativeLevelFactory,
    IssueDepartmentFactory,
    IssueFactory,
    IssueStatusFactory,
)
from issues.models import Issue


class IssueListViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("dashboard:grm:issue_list")
        self.child_region = AdministrativeRegionFactory(parent=self.root_region)
        self.dept = IssueDepartmentFactory()
        self.dep_level = IssueDepartmentAdministrativeLevelFactory(department=self.dept)
        self.category = IssueCategoryFactory(assigned_department=self.dep_level)
        self.status = IssueStatusFactory()
        # Keep DB clean for deterministic assertions
        Issue.objects.all().delete()

    def _make_head_worker(self, region=None):
        if region is None:
            region = self.root_region
        head_user = UserFactory()
        department = IssueDepartmentFactory(head=head_user)
        GovernmentWorker.objects.create(
            user=head_user,
            department=department,
            administrative_region=region,
        )
        return head_user, department

    def _make_category_for_department(self, department):
        dep_level = IssueDepartmentAdministrativeLevelFactory(department=department)
        return IssueCategoryFactory(assigned_department=dep_level)

    def _make_worker(self, region=None, is_head=False):
        user = UserFactory()
        region = region or self.root_region
        dept = IssueDepartmentFactory()
        if is_head:
            dept.head = user
            dept.save()
        GovernmentWorker.objects.create(user=user, department=dept, administrative_region=region)
        return user, dept

    def test_assignee_sees_own_confirmed_issue(self):
        assignee = UserFactory()
        # Not a government worker, but being assignee should be enough per list rule
        issue = IssueFactory(assignee=assignee, confirmed=True, administrative_region=self.root_region)

        resp = self.get(self.url, ajax=True, user=assignee)
        assert resp.status_code == 200
        data = resp.json()
        assert issue.tracking_code in data.get("html", "")

    def test_head_sees_issue_only_when_category_and_region_match(self):
        # Head at parent region
        head_user, dept = self._make_head_worker(region=self.root_region)
        child_region = AdministrativeRegionFactory(parent=self.root_region)

        # Category matches department
        matching_category = self._make_category_for_department(dept)
        # Another category not for this department
        other_dept = IssueDepartmentFactory()
        non_matching_category = self._make_category_for_department(other_dept)

        # Issue that SHOULD appear (category matches AND region is descendant)
        should_appear = IssueFactory(
            confirmed=True,
            administrative_region=child_region,
            category=matching_category,
            assignee=None,
        )
        # Issue that should NOT appear (category does not belong to head's department)
        should_not_appear = IssueFactory(
            confirmed=True,
            administrative_region=child_region,
            category=non_matching_category,
            assignee=None,
        )

        resp = self.get(self.url, ajax=True, user=head_user)
        assert resp.status_code == 200
        html = resp.json().get("html", "")
        assert should_appear.tracking_code in html
        assert should_not_appear.tracking_code not in html

    def test_head_does_not_see_issue_if_region_outside_hierarchy(self):
        worker_region = AdministrativeRegionFactory(parent=self.root_region)
        head_user, dept = self._make_head_worker(region=worker_region)
        other_region = AdministrativeRegionFactory(parent=self.root_region)
        matching_category = self._make_category_for_department(dept)

        outside_issue = IssueFactory(
            confirmed=True,
            administrative_region=other_region,
            category=matching_category,
            assignee=None,
        )

        resp = self.get(self.url, ajax=True, user=head_user)
        assert resp.status_code == 200
        html = resp.json().get("html", "")
        assert outside_issue.tracking_code not in html

    def test_grm_manager_sees_all_issues(self):
        manager = UserFactory(grm_manager=True)
        issue1 = IssueFactory(confirmed=True, administrative_region=self.root_region)
        issue2 = IssueFactory(confirmed=True, administrative_region=self.child_region)
        resp = self.get(self.url, ajax=True, user=manager)
        html = resp.json().get("html", "")
        assert issue1.tracking_code in html
        assert issue2.tracking_code in html

    def test_case_manager_non_head_sees_only_assigned_issues(self):
        user, dept = self._make_worker(is_head=False)
        assigned = IssueFactory(assignee=user, confirmed=True, administrative_region=self.root_region)
        not_assigned = IssueFactory(confirmed=True, administrative_region=self.root_region)
        resp = self.get(self.url, ajax=True, user=user)
        html = resp.json().get("html", "")
        assert assigned.tracking_code in html
        assert not_assigned.tracking_code not in html

    def test_head_sees_only_department_and_region_descendants(self):
        head, dept = self._make_worker(is_head=True)
        matching_category = IssueCategoryFactory(assigned_department__department=dept)
        visible_issue = IssueFactory(
            confirmed=True, category=matching_category, administrative_region=self.child_region
        )
        hidden_issue = IssueFactory(confirmed=True, administrative_region=self.root_region)
        resp = self.get(self.url, ajax=True, user=head)
        html = resp.json().get("html", "")
        assert visible_issue.tracking_code in html
        assert hidden_issue.tracking_code not in html

    def test_filter_by_date_range(self):
        user = UserFactory(grm_manager=True)
        today = datetime.today()
        issue_recent = IssueFactory(confirmed=True, intake_date=today, administrative_region=self.root_region)
        issue_old = IssueFactory(
            confirmed=True, intake_date=today - timedelta(days=5), administrative_region=self.root_region
        )
        start = (today - timedelta(days=2)).strftime("%d/%m/%Y")
        resp = self.get(f"{self.url}?start_date={start}", ajax=True, user=user)
        html = resp.json().get("html", "")
        assert issue_recent.tracking_code in html
        assert issue_old.tracking_code not in html

    def test_filter_by_assignee(self):
        manager = UserFactory(grm_manager=True)
        worker = UserFactory()
        issue_assigned = IssueFactory(confirmed=True, assignee=worker, administrative_region=self.root_region)
        issue_other = IssueFactory(confirmed=True, administrative_region=self.root_region)
        resp = self.get(f"{self.url}?assigned_to={worker.id}", ajax=True, user=manager)
        html = resp.json().get("html", "")
        assert issue_assigned.tracking_code in html
        assert issue_other.tracking_code not in html

    def test_filter_by_code_partial_match(self):
        manager = UserFactory(grm_manager=True)
        issue = IssueFactory(confirmed=True, tracking_code="ABC123", administrative_region=self.root_region)
        resp = self.get(f"{self.url}?code=ABC", ajax=True, user=manager)
        html = resp.json().get("html", "")
        assert issue.tracking_code in html

    def test_filter_by_category(self):
        manager = UserFactory(grm_manager=True)
        issue_ok = IssueFactory(confirmed=True, category=self.category, administrative_region=self.root_region)
        issue_wrong = IssueFactory(confirmed=True, administrative_region=self.root_region)
        resp = self.get(f"{self.url}?category={self.category.id}", ajax=True, user=manager)
        html = resp.json().get("html", "")
        assert issue_ok.tracking_code in html
        assert issue_wrong.tracking_code not in html

    def test_pagination_next_and_previous(self):
        manager = UserFactory(grm_manager=True)
        IssueFactory(
            confirmed=True, intake_date=datetime.now() - timedelta(days=2), administrative_region=self.root_region
        )
        issue2 = IssueFactory(
            confirmed=True, intake_date=datetime.now() - timedelta(days=1), administrative_region=self.root_region
        )
        cursor_date = issue2.intake_date.isoformat()
        resp_next = self.get(
            f"{self.url}?cursor_date={cursor_date}&cursor_id={issue2.id}&direction=next", ajax=True, user=manager
        )
        assert resp_next.status_code == 200
        resp_prev = self.get(
            f"{self.url}?cursor_date={cursor_date}&cursor_id={issue2.id}&direction=previous", ajax=True, user=manager
        )
        assert resp_prev.status_code == 200
