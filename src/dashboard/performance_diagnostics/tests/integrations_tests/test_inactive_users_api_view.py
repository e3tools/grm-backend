from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from authentication.factories import (
    FacilitatorFactory,
    GovernmentWorkerFactory,
    UserFactory,
)
from dashboard.constants import (
    COLOR_DANGER,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_WARNING,
    ICON_ALERT,
    LABEL_LOW_ACTIVITY,
)
from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    IssueFactory,
    IssueStatusFactory,
)


class InactiveUsersAPIViewTest(DashboardTestCase):
    """Integration tests for InactiveUsersAPIView (AJAX endpoint returning inactive users data)."""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()

        self.url = reverse("dashboard:performance_diagnostics:api_inactive_users")

        # Create child regions under root_region (from DashboardTestCase)
        self.region1 = AdministrativeRegionFactory(parent=self.root_region, name="Region 1")
        self.region2 = AdministrativeRegionFactory(parent=self.root_region, name="Region 2")
        self.region3 = AdministrativeRegionFactory(parent=self.root_region, name="Region 3")

        self.open_status = IssueStatusFactory(open_status=True, final_status=False)
        self.closed_status = IssueStatusFactory(open_status=False, final_status=True)

        self.now = timezone.now()

    def test_api_returns_json_response(self):
        """API should return valid JSON with data and pagination."""
        # Create inactive government worker (10 days inactive)
        user = UserFactory(first_name="John", last_name="Doe")
        user.last_activity = self.now - timedelta(days=10)
        user.save()
        GovernmentWorkerFactory(user=user, administrative_region=self.region1)

        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7},
            user=self.manager,
            ajax=True,
        )

        assert resp.status_code == 200

        data = resp.json()
        assert 'data' in data
        assert 'recordsTotal' in data
        assert 'recordsFiltered' in data
        assert len(data['data']) == 1

    def test_api_filters_by_inactivity_threshold(self):
        """API should return only users who meet the inactivity threshold."""
        # User 1: inactive for 5 days (should NOT appear with threshold=7)
        user1 = UserFactory(first_name="Active", last_name="User")
        user1.last_activity = self.now - timedelta(days=5)
        user1.save()
        GovernmentWorkerFactory(user=user1, administrative_region=self.region1)

        # User 2: inactive for 10 days (should appear with threshold=7)
        user2 = UserFactory(first_name="Inactive", last_name="User")
        user2.last_activity = self.now - timedelta(days=10)
        user2.save()
        GovernmentWorkerFactory(user=user2, administrative_region=self.region1)

        # User 3: inactive for 20 days (should appear with threshold=7)
        user3 = UserFactory(first_name="Very", last_name="Inactive")
        user3.last_activity = self.now - timedelta(days=20)
        user3.save()
        FacilitatorFactory(user=user3, administrative_region=self.region1)

        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        names = [f"{r['name']}" for r in data['data']]
        # Should include the 10-day and 20-day inactive users
        assert "Inactive User" in names
        assert "Very Inactive" in names
        # Should NOT include the 5-day inactive user
        assert "Active User" not in names
        # At minimum should have our 2 users (may have more from previous tests)
        assert data['recordsTotal'] >= 2

    def test_api_filters_by_role(self):
        """API should filter by role (government_worker or facilitator)."""
        # Create government worker (inactive)
        user1 = UserFactory(first_name="Gov", last_name="Worker")
        user1.last_activity = self.now - timedelta(days=10)
        user1.save()
        GovernmentWorkerFactory(user=user1, administrative_region=self.region1)

        # Create facilitator (inactive)
        user2 = UserFactory(first_name="Facilitator", last_name="User")
        user2.last_activity = self.now - timedelta(days=10)
        user2.save()
        FacilitatorFactory(user=user2, administrative_region=self.region1)

        # Filter by government_worker only
        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7, 'role_filter': 'government_worker'},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert data['recordsTotal'] == 1
        assert data['data'][0]['name'] == "Gov Worker"

        # Filter by facilitator only
        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7, 'role_filter': 'facilitator'},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert data['recordsTotal'] == 1
        assert data['data'][0]['name'] == "Facilitator User"

    def test_api_filters_by_administrative_region(self):
        """API should filter by administrative region and include descendants."""
        # Create users in different regions
        user1 = UserFactory(first_name="Region1", last_name="User")
        user1.last_activity = self.now - timedelta(days=10)
        user1.save()
        GovernmentWorkerFactory(user=user1, administrative_region=self.region1)

        user2 = UserFactory(first_name="Region2", last_name="User")
        user2.last_activity = self.now - timedelta(days=10)
        user2.save()
        GovernmentWorkerFactory(user=user2, administrative_region=self.region2)

        # Filter by region1 only
        resp = self.get(
            self.url,
            data={
                'inactivity_threshold': 7,
                'administrative_region': self.region1.id,
            },
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert data['recordsTotal'] == 1
        assert data['data'][0]['name'] == "Region1 User"

        # Filter by root region (should include all children)
        resp = self.get(
            self.url,
            data={
                'inactivity_threshold': 7,
                'administrative_region': self.root_region.id,
            },
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert data['recordsTotal'] == 2

    def test_api_filters_by_has_open_issues(self):
        """API should filter by whether user has open issues assigned."""
        # User with open issues
        user1 = UserFactory(first_name="With", last_name="Issues")
        user1.last_activity = self.now - timedelta(days=10)
        user1.save()
        GovernmentWorkerFactory(user=user1, administrative_region=self.region1)
        IssueFactory(assignee=user1, status=self.open_status, confirmed=True, administrative_region=self.region1)

        # User without open issues
        user2 = UserFactory(first_name="Without", last_name="Issues")
        user2.last_activity = self.now - timedelta(days=10)
        user2.save()
        GovernmentWorkerFactory(user=user2, administrative_region=self.region1)

        # Filter: users with open issues only
        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7, 'has_open_issues': 'true'},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert data['recordsTotal'] == 1
        assert data['data'][0]['name'] == "With Issues"

        # Filter: users without open issues only
        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7, 'has_open_issues': 'false'},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert data['recordsTotal'] == 1
        assert data['data'][0]['name'] == "Without Issues"

    def test_api_color_coding_last_activity(self):
        """API should return correct color codes for last activity."""
        # User inactive 10 days (7-14 days) -> secondary
        user1 = UserFactory(first_name="User", last_name="10days")
        user1.last_activity = self.now - timedelta(days=10)
        user1.save()
        GovernmentWorkerFactory(user=user1, administrative_region=self.region1)

        # User inactive 20 days (14-30 days) -> warning
        user2 = UserFactory(first_name="User", last_name="20days")
        user2.last_activity = self.now - timedelta(days=20)
        user2.save()
        GovernmentWorkerFactory(user=user2, administrative_region=self.region1)

        # User inactive 40 days (>30 days) -> danger
        user3 = UserFactory(first_name="User", last_name="40days")
        user3.last_activity = self.now - timedelta(days=40)
        user3.save()
        GovernmentWorkerFactory(user=user3, administrative_region=self.region1)

        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        colors = {r['name']: r['last_activity_color'] for r in data['data']}

        assert colors['User 10days'] == COLOR_SECONDARY
        assert colors['User 20days'] == COLOR_WARNING
        assert colors['User 40days'] == COLOR_DANGER

    def test_api_performance_rating(self):
        """API should calculate correct performance rating based on last_activity_days."""
        # User inactive 15 days (7-20) -> Low Activity
        user1 = UserFactory(first_name="Low", last_name="Activity")
        user1.last_activity = self.now - timedelta(days=15)
        user1.save()
        GovernmentWorkerFactory(user=user1, administrative_region=self.region1)

        # User inactive 25 days (>20) -> Inactive
        user2 = UserFactory(first_name="Inactive", last_name="User")
        user2.last_activity = self.now - timedelta(days=25)
        user2.save()
        GovernmentWorkerFactory(user=user2, administrative_region=self.region1)

        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert data['recordsTotal'] == 2

        perf_ratings = {r['name']: r['performance_rating'] for r in data['data']}
        assert "Low Activity" in perf_ratings['Low Activity']
        assert "Inactive" in perf_ratings['Inactive User']

    def test_api_open_issues_count(self):
        """API should correctly count open issues assigned to each user."""
        user = UserFactory(first_name="Worker", last_name="WithIssues")
        user.last_activity = self.now - timedelta(days=10)
        user.save()
        GovernmentWorkerFactory(user=user, administrative_region=self.region1)

        # Create 3 open issues
        IssueFactory(assignee=user, status=self.open_status, confirmed=True, administrative_region=self.region1)
        IssueFactory(assignee=user, status=self.open_status, confirmed=True, administrative_region=self.region1)
        IssueFactory(assignee=user, status=self.open_status, confirmed=True, administrative_region=self.region1)

        # Create 1 closed issue (should not count)
        IssueFactory(assignee=user, status=self.closed_status, confirmed=True, administrative_region=self.region1)

        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert data['data'][0]['open_issues_count'] == 3

    def test_api_includes_users_with_null_last_activity(self):
        """API should include users who have never been active (null last_activity)."""
        user = UserFactory(first_name="Never", last_name="Active")
        user.last_activity = None
        user.save()
        GovernmentWorkerFactory(user=user, administrative_region=self.region1)

        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert data['recordsTotal'] == 1
        assert data['data'][0]['name'] == "Never Active"
        assert "Never" in data['data'][0]['last_activity']

    def test_api_access_denied_for_non_manager(self):
        """Non-manager users should get 403."""
        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7},
            user=self.normal_user,
            ajax=True,
        )

        assert resp.status_code == 403

    def test_api_non_ajax_request_returns_404(self):
        """Non-AJAX requests should return 404 due to AJAXRequestMixin."""
        resp = self.get(self.url, data={'inactivity_threshold': 7}, user=self.manager)

        assert resp.status_code == 404

    def test_view_respects_pagination(self):
        """View should paginate users."""
        for i in range(25):
            user = UserFactory(first_name=f"User{i}", last_name="Test")
            user.last_activity = self.now - timedelta(days=10)
            user.save()
            GovernmentWorkerFactory(user=user, administrative_region=self.region1)

        resp = self.get(
            self.url,
            data={"inactivity_threshold": 7, "per_page": 10},
            user=self.manager,
            ajax=True,
        )

        assert resp.status_code == 200
        data = resp.json()

        pagination = data.get('pagination', {})
        assert pagination.get('current_page') == 1
        assert pagination.get('per_page') == 10
        assert pagination.get('total_pages') == 3
        assert pagination.get('total_records') == 25
        assert pagination.get('has_next') is True

    def test_api_accepts_page_param(self):
        """API should accept explicit 'page' parameter and return the requested page."""
        total_users = 25
        per_page = 10

        for i in range(total_users):
            user = UserFactory(first_name="User", last_name=f"Number{i}")
            user.last_activity = self.now - timedelta(days=10 + i)
            user.save()
            GovernmentWorkerFactory(user=user, administrative_region=self.region1)

        # Request page 2 explicitly
        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7, 'per_page': per_page, 'page': 2},
            user=self.manager,
            ajax=True,
        )

        assert resp.status_code == 200
        data = resp.json()

        pagination = data.get('pagination', {})
        assert pagination.get('current_page') == 2
        assert pagination.get('per_page') == per_page
        assert pagination.get('total_records') == total_users
        assert len(data.get('data', [])) == per_page

        # Request page beyond last page (should clamp to last page)
        resp2 = self.get(
            self.url,
            data={'inactivity_threshold': 7, 'per_page': per_page, 'page': 999},
            user=self.manager,
            ajax=True,
        )

        assert resp2.status_code == 200
        data2 = resp2.json()
        pagination2 = data2.get('pagination', {})
        assert pagination2.get('total_pages') == 3
        assert pagination2.get('current_page') == 3
        assert len(data2.get('data', [])) == (total_users - per_page * 2)

    def test_api_sorting_by_name(self):
        """API should support sorting by name."""
        user1 = UserFactory(first_name="Charlie", last_name="Brown")
        user1.last_activity = self.now - timedelta(days=10)
        user1.save()
        GovernmentWorkerFactory(user=user1, administrative_region=self.region1)

        user2 = UserFactory(first_name="Alice", last_name="Anderson")
        user2.last_activity = self.now - timedelta(days=10)
        user2.save()
        GovernmentWorkerFactory(user=user2, administrative_region=self.region1)

        user3 = UserFactory(first_name="Bob", last_name="Davis")
        user3.last_activity = self.now - timedelta(days=10)
        user3.save()
        GovernmentWorkerFactory(user=user3, administrative_region=self.region1)

        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7, 'sort_by': 'name', 'sort_dir': 'asc'},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        names = [r['name'] for r in data['data']]
        assert names == ["Alice Anderson", "Bob Davis", "Charlie Brown"]

    def test_api_sorting_by_last_activity(self):
        """API should support manual sorting by last_activity."""
        user1 = UserFactory(first_name="User", last_name="Recent")
        user1.last_activity = self.now - timedelta(days=8)
        user1.save()
        GovernmentWorkerFactory(user=user1, administrative_region=self.region1)

        user2 = UserFactory(first_name="User", last_name="Older")
        user2.last_activity = self.now - timedelta(days=20)
        user2.save()
        GovernmentWorkerFactory(user=user2, administrative_region=self.region1)

        user3 = UserFactory(first_name="User", last_name="Oldest")
        user3.last_activity = self.now - timedelta(days=40)
        user3.save()
        GovernmentWorkerFactory(user=user3, administrative_region=self.region1)

        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7, 'sort_by': 'last_activity', 'sort_dir': 'desc'},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        names = [r['name'] for r in data['data']]
        # Descending means most recent first (smallest days_inactive)
        assert names == ["User Recent", "User Older", "User Oldest"]

    def test_api_combined_filters(self):
        """API should handle multiple filters simultaneously."""
        # Government worker in region1, inactive 10 days, with open issues
        user1 = UserFactory(first_name="Target", last_name="User")
        user1.last_activity = self.now - timedelta(days=10)
        user1.save()
        GovernmentWorkerFactory(user=user1, administrative_region=self.region1)
        IssueFactory(assignee=user1, status=self.open_status, confirmed=True, administrative_region=self.region1)

        # Facilitator in region1, inactive 10 days, with open issues (wrong role)
        user2 = UserFactory(first_name="Wrong", last_name="Role")
        user2.last_activity = self.now - timedelta(days=10)
        user2.save()
        FacilitatorFactory(user=user2, administrative_region=self.region1)
        IssueFactory(assignee=user2, status=self.open_status, confirmed=True, administrative_region=self.region1)

        # Government worker in region2, inactive 10 days, with open issues (wrong region)
        user3 = UserFactory(first_name="Wrong", last_name="Region")
        user3.last_activity = self.now - timedelta(days=10)
        user3.save()
        GovernmentWorkerFactory(user=user3, administrative_region=self.region2)
        IssueFactory(assignee=user3, status=self.open_status, confirmed=True, administrative_region=self.region1)

        # Government worker in region1, inactive 10 days, without open issues (wrong issue count)
        user4 = UserFactory(first_name="No", last_name="Issues")
        user4.last_activity = self.now - timedelta(days=10)
        user4.save()
        GovernmentWorkerFactory(user=user4, administrative_region=self.region1)

        resp = self.get(
            self.url,
            data={
                'inactivity_threshold': 7,
                'role_filter': 'government_worker',
                'administrative_region': self.region1.id,
                'has_open_issues': 'true',
            },
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert data['recordsTotal'] == 1
        assert data['data'][0]['name'] == "Target User"

    def test_serialize_row_contains_all_expected_fields(self):
        """
        Ensure the API returns all fields produced by serialize_row with expected values.
        """
        from datetime import timedelta

        # Create a user inactive 10 days -> Low Activity
        user = UserFactory(first_name="Test", last_name="User")
        user.last_activity = self.now - timedelta(days=10)
        user.save()
        GovernmentWorkerFactory(user=user, administrative_region=self.region1)

        resp = self.get(
            self.url,
            data={'inactivity_threshold': 7},
            user=self.manager,
            ajax=True,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data['data'], "Expected at least one user in response"

        row = data['data'][0]

        # Keys existence
        expected_keys = [
            'id',
            'name',
            'photo_url',
            'role',
            'role_type',
            'last_activity',
            'last_activity_color',
            'open_issues_count',
            'open_issues_color',
            'performance_rating',
            'performance_color',
            'performance_icon',
        ]
        for k in expected_keys:
            assert k in row, f"Missing key in response row: {k}"

        # Values checks
        assert row['id'] == user.id
        assert row['name'] == "Test User"
        assert row['photo_url'] is None
        assert row['role'] == 'Government Worker'
        assert row['role_type'] == 'government_worker'
        assert row['last_activity'] == '10 days ago'
        assert row['last_activity_color'] == COLOR_SECONDARY
        assert row['open_issues_count'] == 0
        assert row['open_issues_color'] == COLOR_PRIMARY
        assert row['performance_rating'] == LABEL_LOW_ACTIVITY
        assert row['performance_color'] == COLOR_WARNING
        assert row['performance_icon'] == ICON_ALERT
