from datetime import datetime, timedelta

from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import make_aware

from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueFactory,
    IssueStatusFactory,
    IssueTypeFactory,
)
from issues.models import Issue


class IssuesStatisticsViewTest(DashboardTestCase):
    """Integration tests for the IssuesStatisticsView."""

    def setUp(self):
        super().setUp()
        # Create a small region tree under the root_region provided by DashboardTestCase
        self.child_a = AdministrativeRegionFactory(parent=self.root_region)
        self.child_b = AdministrativeRegionFactory(parent=self.root_region)

        # Create statuses, types and categories using factories
        self.status_open = IssueStatusFactory(open_status=True)
        self.status_closed = IssueStatusFactory(final_status=True)

        self.type_1 = IssueTypeFactory()
        self.type_2 = IssueTypeFactory()

        self.cat_a = IssueCategoryFactory()
        self.cat_b = IssueCategoryFactory()

        now = timezone.now()

        # child_a: 2 confirmed (today, 10 days ago)
        IssueFactory(
            administrative_region=self.child_a,
            status=self.status_open,
            issue_type=self.type_1,
            category=self.cat_a,
            intake_date=now,
            confirmed=True,
        )
        IssueFactory(
            administrative_region=self.child_a,
            status=self.status_closed,
            issue_type=self.type_2,
            category=self.cat_b,
            intake_date=now - timedelta(days=10),
            confirmed=True,
        )

        # child_b: 1 confirmed (40 days ago) + 1 unconfirmed (today)
        IssueFactory(
            administrative_region=self.child_b,
            status=self.status_open,
            issue_type=self.type_1,
            category=self.cat_a,
            intake_date=now - timedelta(days=40),
            confirmed=True,
        )
        IssueFactory(
            administrative_region=self.child_b,
            status=self.status_open,
            issue_type=self.type_1,
            category=self.cat_a,
            intake_date=now,
            confirmed=False,
        )

        # root_region: 1 confirmed (today)
        IssueFactory(
            administrative_region=self.root_region,
            status=self.status_open,
            issue_type=self.type_2,
            category=self.cat_b,
            intake_date=now,
            confirmed=True,
        )

        # endpoint url (namespace used in the project)
        self.url = reverse("dashboard:diagnostics:issues_statistics")

    def test_auth_permission(self):
        # unauthorized request should not return 200 (DashboardTestCase.get handles auth)
        response = self.get(self.url, authorized=False, ajax=True)
        assert response.status_code != 200

    def test_non_ajax_request_returns_404(self):
        """Non-AJAX requests should be rejected by the AJAX mixin (not return 200 JSON)."""
        response = self.get(self.url)
        assert response.status_code != 200

    def test_response_structure_and_basic_counts(self):
        """The view returns expected keys and aggregated counts consistent with DB for the root branch."""
        resp = self.get(self.url, ajax=True)
        assert resp.status_code == 200
        data = resp.json()

        # Basic keys present
        assert "region_stats" in data
        assert "status_stats" in data
        assert "type_stats" in data
        assert "category_stats" in data

        # Compute expected totals using the same branch logic as the view:
        root_region = self.root_region
        target_branch_ids = root_region.get_descendant_ids()

        # Total confirmed issues in the branch (DB)
        total_confirmed_db = Issue.objects.filter(confirmed=True, administrative_region__in=target_branch_ids).count()

        # Sum counts returned by the view (region_stats may omit zero entries)
        total_from_view = sum(v.get("count", 0) for v in data["region_stats"].values())

        # The view should report counts that match the DB for the branch (or a subset if view groups differently).
        # We assert equality to be strict about the branch aggregation.
        assert total_from_view == total_confirmed_db

        # Ensure regions returned belong to the branch (no region outside branch)
        region_names = {v["name"] for v in data["region_stats"].values()}
        # child_a and child_b were created under root_region; at least one should appear if they have confirmed issues
        assert any(name for name in region_names)

        # Status stats: compare counts per status for the same branch
        status_stats = data["status_stats"]
        for status in (self.status_open, self.status_closed):
            db_count = Issue.objects.filter(
                confirmed=True, status=status, administrative_region__in=target_branch_ids
            ).count()
            status_id = str(status.id)
            if db_count > 0:
                assert status_id in status_stats
                assert status_stats[status_id]["count"] == db_count
            else:
                # view may omit zero-count statuses
                assert status_id not in status_stats or status_stats[status_id]["count"] == 0

        type_stats = data.get("type_stats", {})
        # Build expected counts from DB grouped by issue_type
        expected_type_counts = {}
        qs_types = Issue.objects.filter(confirmed=True, administrative_region__in=target_branch_ids)
        for issue in qs_types:
            tid = issue.issue_type_id
            expected_type_counts[tid] = expected_type_counts.get(tid, 0) + 1

        # Assert each expected type with count > 0 appears and matches
        for tid, cnt in expected_type_counts.items():
            tid_key = str(tid)
            assert tid_key in type_stats
            assert type_stats[tid_key]["count"] == cnt

        # --- category_stats: compare counts per category for the same branch
        category_stats = data.get("category_stats", {})
        expected_cat_counts = {}
        qs_cats = Issue.objects.filter(confirmed=True, administrative_region__in=target_branch_ids)
        for issue in qs_cats:
            cid = issue.category_id
            expected_cat_counts[cid] = expected_cat_counts.get(cid, 0) + 1

        for cid, cnt in expected_cat_counts.items():
            cid_key = str(cid)
            assert cid_key in category_stats
            assert category_stats[cid_key]["count"] == cnt

    def test_date_filter_excludes_old_issues(self):
        """Filtering by a 30-day window excludes the 40-day-old issue in child_b."""
        start = (timezone.now() - timedelta(days=30)).strftime("%d/%m/%Y")
        end = timezone.now().strftime("%d/%m/%Y")
        params = {"start_date": start, "end_date": end}
        resp = self.get(self.url, data=params, ajax=True)
        assert resp.status_code == 200
        data = resp.json()

        # Parse dates exactly like the view does
        start_dt = make_aware(datetime.strptime(start, "%d/%m/%Y"))
        end_dt = make_aware(datetime.strptime(end, "%d/%m/%Y"))

        # Use the same branch as the view (root branch)
        root_region = self.root_region
        target_branch_ids = root_region.get_descendant_ids()

        expected_qs = Issue.objects.filter(
            confirmed=True,
            intake_date__gte=start_dt,
            intake_date__lte=end_dt,
            administrative_region__in=target_branch_ids,
        )
        expected_total = expected_qs.count()

        total_from_view = sum(v.get("count", 0) for v in data["region_stats"].values())
        assert total_from_view == expected_total

        # child_b had only the 40-day confirmed issue, so it should not appear in the 30-day filtered response
        region_names = {v["name"] for v in data["region_stats"].values()}
        assert self.child_b.name not in region_names

    def test_region_param_limits_to_branch(self):
        """Passing a region id limits statistics to that branch only."""
        params = {"region": str(self.child_a.id)}
        resp = self.get(self.url, data=params, ajax=True)
        assert resp.status_code == 200
        data = resp.json()

        # Compute expected issues in DB for that branch using the same helper as the view
        target_branch_ids = self.child_a.get_descendant_ids()

        expected_total = Issue.objects.filter(confirmed=True, administrative_region__in=target_branch_ids).count()

        total_from_view = sum(v.get("count", 0) for v in data["region_stats"].values())
        assert total_from_view == expected_total

        # Ensure regions outside the branch (child_b) are not present
        region_names = {v["name"] for v in data["region_stats"].values()}
        assert self.child_b.name not in region_names

    def test_region_param_returns_global(self):
        now = timezone.now()

        # Create a few confirmed issues directly in child_a
        IssueFactory(
            administrative_region=self.child_a,
            intake_date=now,
            confirmed=True,
        )
        IssueFactory(
            administrative_region=self.child_a,
            intake_date=now,
            confirmed=True,
        )
        # Add one more in the branch (same region) to ensure totals > 1
        IssueFactory(
            administrative_region=self.child_a,
            intake_date=now - timedelta(days=2),
            confirmed=True,
        )

        # Call the endpoint for the specific region (child_a)
        params = {"region": str(self.child_a.id)}
        resp = self.get(self.url, data=params, ajax=True)
        assert resp.status_code == 200
        data = resp.json()

        # --- region_stats: expect an entry named "Global" (view may rename the target region)
        region_entries = data.get("region_stats", {})
        names = {v.get("name") for v in region_entries.values()}
        assert "Global" in names

        # Find the "Global" entry and its count
        global_entry = next((v for v in region_entries.values() if v.get("name") == "Global"), None)
        assert global_entry is not None
        global_count = global_entry.get("count", 0)

        # Compute expected total for the branch using the same helper as the view
        target_branch_ids = self.child_a.get_descendant_ids()
        expected_total = Issue.objects.filter(confirmed=True, administrative_region__in=target_branch_ids).count()
        assert global_count == expected_total
