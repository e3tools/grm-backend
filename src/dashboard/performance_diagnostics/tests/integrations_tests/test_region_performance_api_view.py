from django.urls import reverse

from authentication.factories import UserFactory
from dashboard.constants import (
    COLOR_DANGER,
    COLOR_PRIMARY,
    COLOR_WARNING,
    MONTHLY_CHOICE,
    WEEKLY_CHOICE,
)
from dashboard.models import RegionPerformanceMetrics
from grm.tests.base import DashboardTestCase
from issues.factories import AdministrativeRegionFactory, IssueCategoryFactory


class RegionPerformanceAPIViewTest(DashboardTestCase):
    """Integration tests for RegionPerformanceAPIView (AJAX endpoint returning region performance data)."""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()

        self.url = reverse("dashboard:performance_diagnostics:api_region_performance")

        # Create child regions under root_region (from DashboardTestCase)
        self.region1 = AdministrativeRegionFactory(parent=self.root_region, name="Region 1")
        self.region2 = AdministrativeRegionFactory(parent=self.root_region, name="Region 2")
        self.region3 = AdministrativeRegionFactory(parent=self.root_region, name="Region 3 (Leaf)")

        self.category = IssueCategoryFactory()

        # Clear existing metrics
        RegionPerformanceMetrics.objects.all().delete()

    def test_api_returns_json_response(self):
        """API should return valid JSON with data and pagination."""
        # Create metric for region1
        RegionPerformanceMetrics.objects.create(
            region=self.region1,
            category=None,
            period=WEEKLY_CHOICE,
            open_issues_count=10,
            avg_resolution_days=5.0,
            active_workers_count=5,
            total_workers_in_region=10,
            overall_performance_score=85.0,
        )

        resp = self.get(
            self.url,
            data={'period': WEEKLY_CHOICE},
            user=self.manager,
            ajax=True,
        )

        assert resp.status_code == 200

        data = resp.json()
        assert 'data' in data
        assert 'recordsTotal' in data
        assert 'recordsFiltered' in data
        assert len(data['data']) == 1

    def test_api_filters_by_period(self):
        """API should return metrics only for requested period."""
        RegionPerformanceMetrics.objects.create(
            region=self.region1,
            category=None,
            period=WEEKLY_CHOICE,
            open_issues_count=10,
            avg_resolution_days=5.0,
            active_workers_count=5,
            total_workers_in_region=10,
            overall_performance_score=85.0,
        )
        RegionPerformanceMetrics.objects.create(
            region=self.region1,
            category=None,
            period=MONTHLY_CHOICE,
            open_issues_count=20,
            avg_resolution_days=8.0,
            active_workers_count=8,
            total_workers_in_region=10,
            overall_performance_score=70.0,
        )

        resp = self.get(
            self.url,
            data={'period': WEEKLY_CHOICE},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert len(data['data']) == 1
        assert data['data'][0]['open_issues_count'] == 10

    def test_api_shows_children_when_region_selected(self):
        """When region filter is applied, API should show children of that region."""
        # Create metrics for child regions
        RegionPerformanceMetrics.objects.create(
            region=self.region1,
            category=None,
            period=WEEKLY_CHOICE,
            open_issues_count=10,
            avg_resolution_days=5.0,
            active_workers_count=5,
            total_workers_in_region=10,
            overall_performance_score=85.0,
        )
        RegionPerformanceMetrics.objects.create(
            region=self.region2,
            category=None,
            period=WEEKLY_CHOICE,
            open_issues_count=25,
            avg_resolution_days=12.0,
            active_workers_count=3,
            total_workers_in_region=10,
            overall_performance_score=45.0,
        )

        resp = self.get(
            self.url,
            data={
                'period': WEEKLY_CHOICE,
                'administrative_region': self.root_region.id,
            },
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        assert data['recordsTotal'] == 2
        region_names = [r['region_name'] for r in data['data']]
        assert 'Region 1' in region_names
        assert 'Region 2' in region_names

    def test_api_returns_no_children_message_when_leaf_region(self):
        """API should return no_children flag and show metrics for the selected leaf region."""
        # Create a metric for the leaf region (region3 has no children)
        RegionPerformanceMetrics.objects.create(
            region=self.region3,
            category=None,
            period=WEEKLY_CHOICE,
            open_issues_count=7,
            avg_resolution_days=4.0,
            active_workers_count=2,
            total_workers_in_region=5,
            overall_performance_score=60.0,
        )

        resp = self.get(
            self.url,
            data={
                'period': WEEKLY_CHOICE,
                'administrative_region': self.region3.id,
            },
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        # API should indicate no_children but still return metrics for the selected region
        assert data.get('no_children') is True
        assert 'message' in data
        assert 'No administrative sublevel is available' in data['message']
        # The table data should include the metric for the selected region
        assert data['recordsTotal'] == 1
        assert len(data['data']) == 1
        assert data['data'][0]['region_name'] == self.region3.name
        assert data['data'][0]['open_issues_count'] == 7

    def test_api_color_coding_open_issues(self):
        """API should return correct color codes for open issues."""
        RegionPerformanceMetrics.objects.create(
            region=self.region1,
            category=None,
            period=WEEKLY_CHOICE,
            open_issues_count=15,  # < 20 -> primary
            avg_resolution_days=5.0,
            active_workers_count=5,
            total_workers_in_region=10,
            overall_performance_score=85.0,
        )
        RegionPerformanceMetrics.objects.create(
            region=self.region2,
            category=None,
            period=WEEKLY_CHOICE,
            open_issues_count=35,  # 20-50 -> warning
            avg_resolution_days=5.0,
            active_workers_count=5,
            total_workers_in_region=10,
            overall_performance_score=70.0,
        )
        RegionPerformanceMetrics.objects.create(
            region=self.region3,
            category=None,
            period=WEEKLY_CHOICE,
            open_issues_count=65,  # > 50 -> danger
            avg_resolution_days=5.0,
            active_workers_count=5,
            total_workers_in_region=10,
            overall_performance_score=50.0,
        )

        resp = self.get(
            self.url,
            data={'period': WEEKLY_CHOICE},
            user=self.manager,
            ajax=True,
        )

        data = resp.json()
        colors = {r['region_name']: r['open_issues_color'] for r in data['data']}

        assert colors['Region 1'] == COLOR_PRIMARY
        assert colors['Region 2'] == COLOR_WARNING
        assert colors['Region 3 (Leaf)'] == COLOR_DANGER

    def test_api_access_denied_for_non_manager(self):
        """Non-manager users should get 403."""
        resp = self.get(
            self.url,
            data={'period': WEEKLY_CHOICE},
            user=self.normal_user,
            ajax=True,
        )

        assert resp.status_code == 403

    def test_api_non_ajax_request_returns_404(self):
        """Non-AJAX requests should return 404 due to AJAXRequestMixin."""
        resp = self.get(self.url, data={'period': WEEKLY_CHOICE}, user=self.manager)

        assert resp.status_code == 404

    def test_view_respects_pagination(self):
        """View should paginate regions."""
        for i in range(15):
            region = AdministrativeRegionFactory(parent=self.root_region)
            RegionPerformanceMetrics.objects.create(
                region=region,
                category=None,
                period=WEEKLY_CHOICE,
                open_issues_count=10,
                avg_resolution_days=5.0,
                active_workers_count=5,
                total_workers_in_region=10,
            )

        resp = self.get(self.url, data={"per_page": 10}, user=self.manager, ajax=True)
        assert resp.status_code == 200
        data = resp.json()
        # Keep a tolerant assertion for pagination structure while checking key values
        pagination = data.get('pagination', {})
        assert pagination.get('current_page') == 1
        assert pagination.get('per_page') == 10
        assert pagination.get('total_pages') == 2
        assert pagination.get('total_records') == 15
        assert pagination.get('has_next') is True

    def test_api_accepts_page_param(self):
        """API should accept explicit 'page' parameter and return the requested page."""
        total_metrics = 25
        per_page = 10
        # create regions and metrics
        regions = []
        for i in range(total_metrics):
            region = AdministrativeRegionFactory(parent=self.root_region, name=f"PRegion {i+1}")
            regions.append(region)
            RegionPerformanceMetrics.objects.create(
                region=region,
                category=None,
                period=WEEKLY_CHOICE,
                open_issues_count=5 + (i % 10),
                avg_resolution_days=3.0 + (i % 5),
                active_workers_count=2 + (i % 4),
                total_workers_in_region=10,
                overall_performance_score=80.0 - i,  # vary score so ordering is deterministic-ish
            )

        # Request page 2 explicitly
        resp = self.get(
            self.url,
            data={'period': WEEKLY_CHOICE, 'per_page': per_page, 'page': 2},
            user=self.manager,
            ajax=True,
        )
        assert resp.status_code == 200
        data = resp.json()

        pagination = data.get('pagination', {})
        assert pagination.get('current_page') == 2
        assert pagination.get('per_page') == per_page
        assert pagination.get('total_records') == total_metrics
        # page 2 should contain 'per_page' items (except possibly the last page)
        assert len(data.get('data', [])) == per_page

        # Also request a page beyond the last page and ensure it clamps to last page
        resp2 = self.get(
            self.url,
            data={'period': WEEKLY_CHOICE, 'per_page': per_page, 'page': 999},
            user=self.manager,
            ajax=True,
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        pagination2 = data2.get('pagination', {})
        # last page should be 3 for 25 items with per_page=10
        assert pagination2.get('total_pages') == 3
        assert pagination2.get('current_page') == 3
        # last page should have remaining items (25 - 10*2 = 5)
        assert len(data2.get('data', [])) == (total_metrics - per_page * 2)
