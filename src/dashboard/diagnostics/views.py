from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.timezone import make_aware
from django.utils.translation import gettext_lazy as _
from django.views import generic

from dashboard.grm.forms import NewSearchIssueForm
from dashboard.mixins import AJAXRequestMixin, JSONResponseMixin, PageMixin
from etl.models import ETLExecutionLog
from issues.models import (
    AdministrativeRegion,
    Issue,
    IssueCategory,
    IssueStatus,
    IssueType,
)

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class HomeFormView(PageMixin, LoginRequiredMixin, generic.FormView):
    form_class = NewSearchIssueForm
    template_name = "diagnostics/home.html"
    title = _("Diagnostics")
    active_level1 = "diagnostics"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["access_token"] = settings.MAPBOX_ACCESS_TOKEN
        context["lat"] = settings.DIAGNOSTIC_MAP_LATITUDE
        context["lng"] = settings.DIAGNOSTIC_MAP_LONGITUDE
        context["zoom"] = settings.DIAGNOSTIC_MAP_ZOOM
        context["ws_bound"] = settings.DIAGNOSTIC_MAP_WS_BOUND
        context["en_bound"] = settings.DIAGNOSTIC_MAP_EN_BOUND
        context["country_iso_code"] = settings.DIAGNOSTIC_MAP_ISO_CODE
        context["last_update"] = ETLExecutionLog.objects.filter(status='SUCCESS').first()
        return context


class UpdateIssuesDataView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):

    def post(self, request, *args, **kwargs):
        from django.core.management import call_command

        last_success = ETLExecutionLog.objects.filter(status='SUCCESS').first()
        call_command("etl_fetch_issue_data")
        log_entry = ETLExecutionLog.objects.first()
        if log_entry and last_success != log_entry and log_entry.status == 'SUCCESS':
            msg = _(f"The data was successfully updated.<br>Records processed: {log_entry.records_processed}")
            level = messages.SUCCESS
            extra_tags = "success"
            finished_at = log_entry.finished_at
        else:
            if not log_entry or last_success == log_entry or log_entry.status == 'RUNNING':
                error = _(
                    "Internal error while running etl_fetch_issue_data. " "For more details, check the server logs."
                )
            else:
                error = log_entry.error_message.split("Traceback (most recent call last)")[0].strip()
            msg = _(f"Data update failed.<br>Error: {error}")
            level = messages.ERROR
            extra_tags = "danger"
            finished_at = last_success.finished_at if last_success else None

        if finished_at:
            # Convert to local time zone based on settings.TIME_ZONE
            finished_at = timezone.localtime(finished_at)

            # Use Django's format (SHORT_DATETIME_FORMAT by default in templates)
            finished_at = date_format(finished_at, format='DATETIME_FORMAT', use_l10n=True)

        messages.add_message(self.request, level, msg, extra_tags=extra_tags)
        context = {
            "msg": render(self.request, "common/messages.html").content.decode("utf-8"),
            "finished_at": finished_at,
        }
        return self.render_to_json_response(context, safe=False)


class IssuesStatisticsView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        category = request.GET.get('category')
        issue_type = request.GET.get('type')
        region_id = request.GET.get('region')

        # Get base/root region with prefetch
        if region_id:
            try:
                root_region = AdministrativeRegion.objects.select_related('parent').get(id=region_id)
            except AdministrativeRegion.DoesNotExist:
                return self.render_to_json_response({"error": "Region not found"})
        else:
            root_region = AdministrativeRegion.objects.get(parent__isnull=True)

        # Build filters for issues
        filters = Q()

        if start_date:
            filters &= Q(intake_date__gte=make_aware(datetime.strptime(start_date, "%d/%m/%Y")))
        if end_date:
            filters &= Q(intake_date__lte=make_aware(datetime.strptime(end_date, "%d/%m/%Y")))
        if category:
            filters &= Q(category=category)
        if issue_type:
            filters &= Q(issue_type=issue_type)

        # Get all descendant regions efficiently using CTE or optimized query
        if region_id:
            # Usar raw SQL con CTE para mejor performance en regiones grandes
            descendant_ids = self.get_descendant_ids_optimized(root_region.id)
            filters &= Q(administrative_region__in=descendant_ids)

        # Single query to get all statistics using annotations
        issues_stats = Issue.objects.filter(filters).aggregate(
            total_count=Count('id'),
            # Status stats
            **{
                f'status_{status.id}_count': Count('id', filter=Q(status_id=status.id))
                for status in IssueStatus.objects.all()
            },
            # Type stats
            **{
                f'type_{issue_type.id}_count': Count('id', filter=Q(issue_type_id=issue_type.id))
                for issue_type in IssueType.objects.all()
            },
            # Category stats
            **{
                f'category_{cat.id}_count': Count('id', filter=Q(category_id=cat.id))
                for cat in IssueCategory.objects.all()
            },
        )

        total_issues = issues_stats['total_count']

        if total_issues == 0:
            return self.render_to_json_response(
                {
                    "region_stats": {},
                    "status_stats": {},
                    "type_stats": {},
                    "category_stats": {},
                }
            )

        # Get region stats efficiently - solo regiones con issues
        region_stats = self.get_region_stats_optimized(filters, root_region, total_issues)

        # Single query to get all statistics using annotations (for the filtered branch)
        issues_stats = Issue.objects.filter(filters).aggregate(
            total_count=Count('id'),
            # Status stats
            **{
                f'status_{status.id}_count': Count('id', filter=Q(status_id=status.id))
                for status in IssueStatus.objects.all()
            },
            # Type stats
            **{
                f'type_{issue_type.id}_count': Count('id', filter=Q(issue_type_id=issue_type.id))
                for issue_type in IssueType.objects.all()
            },
            # Category stats
            **{
                f'category_{cat.id}_count': Count('id', filter=Q(category_id=cat.id))
                for cat in IssueCategory.objects.all()
            },
        )

        # Process other stats from the aggregated data
        status_stats = self.process_status_stats(issues_stats, total_issues)
        type_stats = self.process_type_stats(issues_stats, total_issues)
        category_stats = self.process_category_stats(issues_stats, total_issues)

        statistics = {
            "region_stats": region_stats,
            "status_stats": status_stats,
            "type_stats": type_stats,
            "category_stats": category_stats,
        }

        return self.render_to_json_response(statistics)

    def get_descendant_ids_optimized(self, root_id):
        """Gets descendant IDs using CTE for better performance"""
        from django.db import connection

        with connection.cursor() as cursor:
            # Get the real name of the table
            table_name = AdministrativeRegion._meta.db_table

            cursor.execute(
                f"""
                WITH RECURSIVE region_tree AS (
                    SELECT id, parent_id, name
                    FROM {table_name}
                    WHERE id = %s

                    UNION ALL

                    SELECT ar.id, ar.parent_id, ar.name
                    FROM {table_name} ar
                    INNER JOIN region_tree rt ON ar.parent_id = rt.id
                )
                SELECT id FROM region_tree
            """,
                [root_id],
            )

            return [row[0] for row in cursor.fetchall()]

    def get_region_stats_optimized(self, filters, target_region, total_issues):
        """
        Retrieves issue statistics for a specific region and its direct children in an optimized way.

        This method is designed to efficiently calculate aggregated issue counts and percentages
        for a target region and its immediate subregions (direct children), while also including
        all issues from the entire branch (the target region and all its descendants).
        It minimizes database queries by:
          - Using a single filtered query to fetch issue counts per region.
          - Mapping each region's issues to either the target region or one of its direct children.

        The returned dictionary includes only regions with at least one issue, and for the target
        region itself, the name will be displayed as "Global" if it contains direct issues.
        If the target region has no direct issues, it is omitted from the results.

        Args:
            filters (Q): A Django Q object containing the filter conditions for issues.
            target_region (AdministrativeRegion): The region whose statistics will be retrieved.
            total_issues (int): The total number of issues that match the filters.

        Returns:
            dict:
                A mapping where keys are region IDs and values are dictionaries with:
                    - count (int): Number of issues for that region (including its descendants).
                    - percentage (int): Percentage of total_issues represented by this count.
                    - name (str): Display name of the region ("Global" for target_region with issues).
                    - latitude (float or None): Latitude of the region center.
                    - longitude (float or None): Longitude of the region center.
                    - level (str): Capitalized administrative level of the region.
        """

        # Get the direct children of the target region + the region itself
        target_regions = [target_region.id]  # Include the target region
        direct_children = list(
            AdministrativeRegion.objects.filter(parent_id=target_region.id).values_list('id', flat=True)
        )
        target_regions.extend(direct_children)

        # Get all descendants of the target region (to filter issues that belong to this branch)
        if hasattr(self, 'get_descendant_ids_optimized'):
            target_branch_ids = self.get_descendant_ids_optimized(target_region.id)
        else:
            target_branch_ids = self.get_descendant_ids_fallback(target_region.id)

        # Filter issues only from the target region branch
        branch_filter = filters & Q(administrative_region__in=target_branch_ids)

        # Optimized query that only includes regions with issues in this branch
        region_data = (
            Issue.objects.filter(branch_filter)
            .select_related('administrative_region')
            .values(
                'administrative_region__id',
                'administrative_region__name',
                'administrative_region__latitude',
                'administrative_region__longitude',
                'administrative_region__administrative_level',
                'administrative_region__parent_id',
            )
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # Create a mapping from each region with issues to its target region (target_region or direct children)
        region_counts = {region_id: 0 for region_id in target_regions}

        # Target region information cache
        target_regions_info = {}
        for region in AdministrativeRegion.objects.filter(id__in=target_regions):
            target_regions_info[region.id] = {
                'name': region.name,
                'latitude': region.latitude,
                'longitude': region.longitude,
                'level': region.administrative_level.capitalize() if region.administrative_level else '',
            }

        for item in region_data:
            region_id = item['administrative_region__id']
            count = item['count']

            # Determine which target region this issue belongs to
            target_region_id = self.find_target_region(region_id, target_region.id, direct_children)

            if target_region_id and target_region_id in region_counts:
                region_counts[target_region_id] += count

        # Build final result only with regions that have issues
        base_region_counts = {}
        for region_id, count in region_counts.items():
            if count > 0:  # Only include regions with issues
                percentage = round((count / total_issues) * 100) if total_issues else 0

                # Determine the display name
                region_name = target_regions_info[region_id]['name']

                # Only show "Global" if it is the target region AND has direct issues
                if region_id == target_region.id:
                    # Check if there are direct issues in the target region
                    direct_issues_count = sum(
                        1 for item in region_data if item['administrative_region__id'] == target_region.id
                    )
                    if direct_issues_count > 0:
                        region_name = "Global"
                    else:
                        # If there are no direct issues, do not include the target region in the results
                        continue

                base_region_counts[region_id] = {
                    'count': count,
                    'percentage': percentage,
                    'name': region_name,
                    'latitude': target_regions_info[region_id]['latitude'],
                    'longitude': target_regions_info[region_id]['longitude'],
                    'level': target_regions_info[region_id]['level'],
                }

        return base_region_counts

    def find_target_region(self, region_id, root_region_id, direct_children_ids):
        """
        Find which "target region" a given region_id belongs to.

        A "target region" is either:
          - the root_region itself (root_region_id), or
          - one of the direct children of root_region.

        This function returns the id of the direct child of root_region that is an
        ancestor of `region_id`. If `region_id` is itself the root_region, returns
        root_region_id. If no ancestor under root is found, returns None.

        Implementation notes:
          - Uses a recursive CTE to climb the parent chain (efficient in Postgres).
          - First tries to find the ancestor whose parent_id == root_region_id
            (this is the direct child of root).
          - If none found, falls back to checking if region_id == root_region_id.
          - Caches results on self._region_ancestry_cache to avoid repeated DB calls.
        """
        # Quick checks
        if region_id == root_region_id:
            return root_region_id
        if region_id in direct_children_ids:
            return region_id

        # Cache
        if not hasattr(self, "_region_ancestry_cache"):
            self._region_ancestry_cache = {}

        if region_id in self._region_ancestry_cache:
            return self._region_ancestry_cache[region_id]

        from django.db import connection

        table = AdministrativeRegion._meta.db_table

        with connection.cursor() as cursor:
            # 1) Try to find the ancestor whose parent is the root (the direct child of root)
            cursor.execute(
                f"""
                WITH RECURSIVE region_path AS (
                    SELECT id, parent_id, 0 AS lvl
                    FROM {table}
                    WHERE id = %s

                    UNION ALL

                    SELECT ar.id, ar.parent_id, rp.lvl + 1
                    FROM {table} ar
                    JOIN region_path rp ON ar.id = rp.parent_id
                )
                SELECT id
                FROM region_path
                WHERE parent_id = %s
                LIMIT 1;
            """,
                [region_id, root_region_id],
            )
            row = cursor.fetchone()
            if row:
                target = row[0]
                self._region_ancestry_cache[region_id] = target
                return target

            # 2) If none found, maybe region is the root or an error — check if root is in path
            cursor.execute(
                f"""
                WITH RECURSIVE region_path AS (
                    SELECT id, parent_id
                    FROM {table}
                    WHERE id = %s

                    UNION ALL

                    SELECT ar.id, ar.parent_id
                    FROM {table} ar
                    JOIN region_path rp ON ar.id = rp.parent_id
                )
                SELECT 1 FROM region_path WHERE id = %s LIMIT 1;
            """,
                [region_id, root_region_id],
            )
            row = cursor.fetchone()
            if row:
                # root is an ancestor (and since we didn't find a direct child, region must be root)
                self._region_ancestry_cache[region_id] = root_region_id
                return root_region_id

        # Not found — return None
        self._region_ancestry_cache[region_id] = None
        return None

    def find_target_region_fallback(self, region_id, root_region_id, direct_children_ids):
        """
        Fallback: climb the parents using a cached parent map. Efficient when
        you prefetch a small subtree or can load parent relations for relevant nodes.
        """
        # quick checks
        if region_id == root_region_id:
            return root_region_id
        if region_id in direct_children_ids:
            return region_id

        # build cache mapping id -> parent_id for the branch up to root
        if not hasattr(self, "_parent_cache"):
            self._parent_cache = {}

        # walk upward until we hit root or we can't go further
        current = region_id
        while current and current != root_region_id:
            parent = self._parent_cache.get(current)
            if parent is None:
                # load parent from DB
                try:
                    parent = AdministrativeRegion.objects.filter(id=current).values_list('parent_id', flat=True).first()
                except Exception:
                    parent = None
                self._parent_cache[current] = parent

            if parent == root_region_id:
                # current is the direct child of root
                self._region_ancestry_cache[region_id] = current
                return current

            current = parent

        # If we reached root
        if current == root_region_id:
            self._region_ancestry_cache[region_id] = root_region_id
            return root_region_id

        self._region_ancestry_cache[region_id] = None
        return None

    def process_status_stats(self, issues_stats: dict, total_issues: int) -> dict:
        """Wrapper for processing status statistics."""
        return self._process_aggregated_stats(issues_stats, total_issues, "status", IssueStatus)

    def process_type_stats(self, issues_stats: dict, total_issues: int) -> dict:
        """Wrapper for processing type statistics."""
        return self._process_aggregated_stats(issues_stats, total_issues, "type", IssueType)

    def process_category_stats(self, issues_stats: dict, total_issues: int) -> dict:
        """Wrapper for processing category statistics."""
        return self._process_aggregated_stats(issues_stats, total_issues, "category", IssueCategory)

    def _process_aggregated_stats(self, issues_stats: dict, total_issues: int, prefix: str, model: type) -> dict:
        """
        Processes aggregated statistics for a given model and field prefix.

        Args:
            issues_stats (dict): Dictionary with aggregated counts returned by Django's aggregate().
                                 Keys are in the format "{prefix}_{id}_count".
            total_issues (int): Total number of issues after filtering.
            prefix (str): The prefix used in the aggregated keys (e.g., "status", "type", "category").
            model (type): Django model class containing 'id' and 'name' fields.

        Returns:
            dict: A dictionary mapping each model ID to its statistics:
                  {
                      id: {
                          "count": <int>,
                          "name": <str>,
                          "percentage": <int>
                      },
                      ...
                  }
                  Only entries with count > 0 are included.
        """
        stats = {}
        name_cache = {obj.id: obj.name for obj in model.objects.all()}

        for obj_id, name in name_cache.items():
            count = issues_stats.get(f"{prefix}_{obj_id}_count", 0)
            if count > 0:
                percentage = round((count / total_issues) * 100) if total_issues else 0
                stats[obj_id] = {
                    "count": count,
                    "name": name,
                    "percentage": percentage,
                }

        return stats
