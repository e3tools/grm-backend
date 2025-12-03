from django.core.paginator import Paginator
from django.db.models import DateTimeField, FloatField, IntegerField, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import generic

from dashboard.constants import (
    NOT_APPLICABLE,
    PERIOD_CHOICES,
    STATUS_AT_RISK,
    STATUS_CRITICAL,
    STATUS_GOOD,
    STATUS_NA,
    WEEKLY_CHOICE,
)
from dashboard.grm.forms import SearchIssueForm
from dashboard.mixins import (
    PageMixin,
    UserManagementAndAJAXMixin,
    UserManagementPermissionMixin,
)
from dashboard.models import (
    PerformanceMetrics,
    RegionPerformanceMetrics,
    StatusBottleneckMetrics,
)
from issues.models import AdministrativeRegion, Issue, IssueCategory, IssueStatus


class PerformanceDiagnosticsView(PageMixin, UserManagementPermissionMixin, generic.TemplateView):
    """
    Main performance diagnostics dashboard view.
    Only accessible by GRM Managers.
    """

    template_name = "performance_diagnostics/dashboard.html"
    title = _("Performance Diagnostics")
    active_level1 = "performance_diagnostics"
    breadcrumb = [
        {"url": "", "title": title},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get available categories from confirmed issues
        available_categories = IssueCategory.objects.filter(issues__confirmed=True).distinct().order_by('name')

        context['form'] = SearchIssueForm()
        context['available_categories'] = available_categories
        context['period_choices'] = PERIOD_CHOICES

        return context


class PerformanceMetricsAPIView(UserManagementAndAJAXMixin, generic.View):
    """
    AJAX endpoint to fetch KPI metrics based on filters.
    Returns HTML fragment for HTMX to render.

    This view ONLY retrieves pre-calculated metrics.
    It does not calculate or modify data.
    """

    def get(self, request, *args, **kwargs):
        # Get and validate filters
        period = request.GET.get('period', WEEKLY_CHOICE)
        if period not in dict(PERIOD_CHOICES):
            period = WEEKLY_CHOICE

        region = self._get_region(request.GET.get('administrative_region'))
        category = self._get_category(request.GET.get('category'))

        # Try to get exact metrics (we assume populate has created rows for ancestors)
        metrics_obj = PerformanceMetrics.get_latest(period, region, category)

        # If still no metrics, show error
        if not metrics_obj:
            return render(
                request,
                'performance_diagnostics/no_metrics.html',
                {'error': True, 'message': _('No metrics available for the selected filters.')},
            )

        # Render success with metrics object
        context = {
            'metrics': metrics_obj.to_dict(),
            'user_adoption_status': metrics_obj.get_user_adoption_status(),
            'resolution_status': metrics_obj.get_resolution_status(target=10.0),
            'satisfaction_status': metrics_obj.get_satisfaction_status(target=4.0),
            'last_updated': metrics_obj.calculated_at,
        }

        return render(request, 'performance_diagnostics/kpi_cards.html', context)

    def _get_region(self, region_id):
        """Parse and validate region ID from request"""
        if not region_id:
            return None

        try:
            return AdministrativeRegion.objects.get(id=region_id)
        except (AdministrativeRegion.DoesNotExist, ValueError):
            return None

    def _get_category(self, category_id):
        """Parse and validate category ID from request"""
        if not category_id:
            return None

        try:
            return IssueCategory.objects.get(id=category_id)
        except (IssueCategory.DoesNotExist, ValueError):
            return None


class StatusBottleneckMetricsAPIView(UserManagementAndAJAXMixin, generic.View):
    """
    AJAX endpoint to fetch Status Bottleneck table fragment based on filters.

    This view retrieves pre-calculated StatusBottleneckMetrics snapshots.
    It returns one row per IssueStatus, using the latest snapshot per status
    for the requested (period, region, category) filters.
    """

    def get(self, request, *args, **kwargs):
        period = request.GET.get('period', WEEKLY_CHOICE)
        # validate period against model choices if needed
        valid_periods = {c[0] for c in PERIOD_CHOICES}
        if period not in valid_periods:
            period = WEEKLY_CHOICE

        region = self._get_region(request.GET.get('administrative_region'))
        category = self._get_category(request.GET.get('category'))

        # Subquery: latest StatusBottleneckMetrics row for a given IssueStatus (OuterRef('pk'))
        base_metrics_qs = StatusBottleneckMetrics.objects.filter(period=period, issue_status=OuterRef('pk')).order_by(
            '-calculated_at'
        )

        # explicit null handling for region/category
        if region is None:
            base_metrics_qs = base_metrics_qs.filter(administrative_region__isnull=True)
        else:
            base_metrics_qs = base_metrics_qs.filter(administrative_region=region)

        if category is None:
            base_metrics_qs = base_metrics_qs.filter(category__isnull=True)
        else:
            base_metrics_qs = base_metrics_qs.filter(category=category)

        # Subqueries to pull the desired fields from the latest snapshot per status
        sub_issues_count = Subquery(base_metrics_qs.values('issues_count')[:1], output_field=IntegerField())
        sub_avg_days = Subquery(base_metrics_qs.values('average_time_in_status_days')[:1], output_field=FloatField())
        sub_calculated_at = Subquery(base_metrics_qs.values('calculated_at')[:1], output_field=DateTimeField())

        # Annotate IssueStatus queryset with the latest snapshot values (if any)
        statuses_qs = IssueStatus.objects.order_by('id').annotate(
            snapshot_issues_count=sub_issues_count,
            snapshot_avg_days=sub_avg_days,
            snapshot_calculated_at=sub_calculated_at,
        )

        # Helper to count confirmed issues for terminal statuses (only used when snapshot missing)
        def _count_confirmed_issues_for_status(status_obj):
            qs = Issue.objects.filter(confirmed=True, status=status_obj)
            if region:
                try:
                    descendant_ids = region.get_descendant_ids()
                    qs = qs.filter(administrative_region_id__in=descendant_ids)
                except Exception:
                    qs = qs.filter(administrative_region=region)
            if category:
                qs = qs.filter(category=category)
            return qs.count()

        def _performance_bucket(avg_days, status_obj):
            if avg_days is None:
                return STATUS_NA
            try:
                avg = float(avg_days)
            except Exception:
                return STATUS_NA
            threshold = getattr(status_obj, 'threshold_days', None) or 1.0
            if avg > threshold * 1.5:
                return STATUS_CRITICAL
            if avg > threshold * 1.2:
                return STATUS_AT_RISK
            return STATUS_GOOD

        # Build rows: one per IssueStatus using annotated snapshot fields
        rows = []
        for s in statuses_qs:
            # snapshot fields come from the Subquery; may be None if no snapshot exists
            snap_count = s.snapshot_issues_count
            snap_avg = s.snapshot_avg_days

            if snap_count is not None:
                # We have a snapshot row for this status
                issues_count = int(snap_count) if snap_count is not None else 0
                if s.final_status or s.rejected_status:
                    avg_display = NOT_APPLICABLE
                    perf = STATUS_NA
                else:
                    if issues_count == 0:
                        avg_display = NOT_APPLICABLE
                        perf = STATUS_NA
                    else:
                        avg_val = float(snap_avg or 0.0)
                        avg_display = f"{avg_val:.1f}"
                        perf = _performance_bucket(avg_val, s)
                rows.append(
                    {
                        'issue_status': s,
                        'issues_count': issues_count,
                        'average_time_in_status_days': avg_display,
                        'performance': perf,
                    }
                )
            else:
                # No snapshot for this status for the requested filters
                if s.final_status or s.rejected_status:
                    issues_count = _count_confirmed_issues_for_status(s)
                    rows.append(
                        {
                            'issue_status': s,
                            'issues_count': issues_count,
                            'average_time_in_status_days': NOT_APPLICABLE,
                            'performance': STATUS_NA,
                        }
                    )
                else:
                    rows.append(
                        {
                            'issue_status': s,
                            'issues_count': NOT_APPLICABLE,
                            'average_time_in_status_days': NOT_APPLICABLE,
                            'performance': STATUS_NA,
                        }
                    )

        # Insight: first numeric avg that is critical
        status_insight = None
        for r in rows:
            avg = r.get('average_time_in_status_days')
            perf = r.get('performance') or {}
            try:
                avg_num = float(avg) if avg != NOT_APPLICABLE else None
            except Exception:
                avg_num = None
            if avg_num is not None and perf.get('badge_text') == STATUS_CRITICAL['badge_text']:
                status_insight = _(
                    "The red flag on '%(status)s' immediately tells the admin that this status is a major bottleneck. "
                    "Issues are waiting %(days).1f days on average."
                ) % {'status': r['issue_status'].name, 'days': avg_num}
                break

        context = {
            'status_bottlenecks': rows,
            'status_insight': status_insight,
        }
        return render(request, 'performance_diagnostics/status_bottlenecks.html', context)

    def _get_region(self, region_id):
        """Parse and validate region ID from request"""
        if not region_id:
            return None
        try:
            return AdministrativeRegion.objects.get(id=region_id)
        except (AdministrativeRegion.DoesNotExist, ValueError):
            return None

    def _get_category(self, category_id):
        """Parse and validate category ID from request"""
        if not category_id:
            return None
        try:
            return IssueCategory.objects.get(id=category_id)
        except (IssueCategory.DoesNotExist, ValueError):
            return None


class RegionPerformanceAPIView(UserManagementAndAJAXMixin, generic.View):
    """
    AJAX endpoint that returns JSON for DataTables.
    Accepts filters: period, category, administrative_region.
    Behavior:
      - region with children -> return metrics for children
      - region without children -> return metrics for the selected region, set no_children=True and message
      - no region -> return metrics for children of the root_region (parent IS NULL)
    """

    def get(self, request, *args, **kwargs):
        draw = request.GET.get('draw')
        try:
            draw = int(draw) if draw is not None else None
        except (TypeError, ValueError):
            draw = None

        period = request.GET.get('period', WEEKLY_CHOICE)
        valid_periods = {c[0] for c in PERIOD_CHOICES}
        if period not in valid_periods:
            period = WEEKLY_CHOICE

        category_id = request.GET.get('category')
        region_id = request.GET.get('administrative_region')

        try:
            per_page = int(request.GET.get('length') or request.GET.get('per_page') or 10)
        except (TypeError, ValueError):
            per_page = 10

        # Pagination: prefer explicit 'page' param; fallback to 'start' offset
        try:
            page_param = request.GET.get('page')
            if page_param is not None:
                page_num = int(page_param)
                if page_num < 1:
                    page_num = 1
            else:
                try:
                    start = int(request.GET.get('start', 0))
                except (TypeError, ValueError):
                    start = 0
                page_num = (start // per_page) + 1
        except (TypeError, ValueError):
            page_num = 1

        # Sorting
        sort_by = request.GET.get('sort_by')
        sort_dir = request.GET.get('sort_dir', 'desc')
        if not sort_by and request.GET.get('order[0][column]') is not None:
            try:
                col_idx = int(request.GET.get('order[0][column]'))
                sort_dir = request.GET.get('order[0][dir]', 'asc')
                idx_map = {0: 'region', 1: 'open_issues', 2: 'resolution', 3: 'workers', 4: 'performance'}
                sort_by = idx_map.get(col_idx, 'performance')
            except Exception:
                sort_by = 'performance'
        if not sort_by:
            sort_by = 'performance'

        sort_map = {
            'region': 'region__name',
            'open_issues': 'open_issues_count',
            'resolution': 'avg_resolution_days',
            'workers': 'active_workers_count',
            'performance': '-overall_performance_score',
        }
        sort_field = sort_map.get(sort_by, '-overall_performance_score')
        if sort_dir == 'desc':
            if not sort_field.startswith('-'):
                sort_field = '-' + sort_field
        else:
            if sort_field.startswith('-'):
                sort_field = sort_field[1:]

        qs = (
            RegionPerformanceMetrics.objects.filter(period=period)
            .select_related('region', 'category')
            .only(
                'id',
                'region__id',
                'region__name',
                'category__id',
                'category__name',
                'open_issues_count',
                'avg_resolution_days',
                'active_workers_count',
                'total_workers_in_region',
                'overall_performance_score',
                'open_issues_score',
                'resolution_score',
                'active_workers_score',
            )
        )

        # category filter
        if category_id:
            try:
                qs = qs.filter(category_id=int(category_id))
            except (ValueError, TypeError):
                return JsonResponse({'data': [], 'recordsTotal': 0, 'recordsFiltered': 0, 'draw': draw})
        else:
            qs = qs.filter(category__isnull=True)

        no_children = False
        message = None
        no_sublevel_available_msg = _(
            'No administrative sublevel is available. Showing current selected administrative level.'
        )

        if region_id:
            try:
                region = AdministrativeRegion.objects.get(id=region_id)
            except (AdministrativeRegion.DoesNotExist, ValueError):
                return JsonResponse({'data': [], 'recordsTotal': 0, 'recordsFiltered': 0, 'draw': draw})

            children_qs = region.get_children() if hasattr(region, 'get_children') else region.children.all()
            if not children_qs.exists():
                # Selected region has no children -> show metrics for the selected region itself
                no_children = True
                message = no_sublevel_available_msg
                qs = qs.filter(region=region)
            else:
                child_ids = list(children_qs.values_list('id', flat=True))
                qs = qs.filter(region__in=child_ids)
        else:
            # No administrative_region provided: use children of the single root_region (parent IS NULL)
            root_region = AdministrativeRegion.objects.filter(parent__isnull=True).first()
            if root_region:
                children_qs = (
                    root_region.get_children() if hasattr(root_region, 'get_children') else root_region.children.all()
                )
                if not children_qs.exists():
                    no_children = True
                    message = no_sublevel_available_msg
                    qs = qs.filter(region=root_region)
                else:
                    child_ids = list(children_qs.values_list('id', flat=True))
                    qs = qs.filter(region__in=child_ids)
            else:
                qs = qs.filter(region__parent__isnull=True)

        qs = qs.order_by(sort_field)

        total_count = qs.count()
        paginator = Paginator(qs, per_page)
        # clamp page_num to available pages
        if page_num > paginator.num_pages and paginator.num_pages > 0:
            page_num = paginator.num_pages
        page_obj = paginator.get_page(page_num)

        data = []
        for metric in page_obj.object_list:
            perf_status = metric.get_performance_status()
            data.append(
                {
                    'id': metric.region.id,
                    'region_name': metric.region.name,
                    'open_issues_count': metric.open_issues_count,
                    'open_issues_color': metric.get_open_issues_color(),
                    'avg_resolution_days': metric.avg_resolution_days,
                    'resolution_color': metric.get_resolution_time_color(),
                    'active_workers_count': metric.active_workers_count,
                    'total_workers_in_region': metric.total_workers_in_region,
                    'workers_percentage': round(metric.get_active_workers_percentage(), 1),
                    'workers_color': metric.get_active_workers_color(),
                    'performance_status': perf_status.get('status') if isinstance(perf_status, dict) else perf_status,
                    'performance_badge_class': perf_status.get('badge_class') if isinstance(perf_status, dict) else '',
                    'performance_icon': perf_status.get('icon_class') if isinstance(perf_status, dict) else '',
                    'performance_badge_text': perf_status.get('badge_text') if isinstance(perf_status, dict) else '',
                    'performance_sort_order': perf_status.get('sort_order') if isinstance(perf_status, dict) else 0,
                }
            )

        pagination = {
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_records': total_count,
            'per_page': per_page,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
        }

        response = {
            'data': data,
            'recordsTotal': total_count,
            'recordsFiltered': total_count,
            'pagination': pagination,
            'no_children': no_children,
            'message': message,
            'draw': draw,
        }
        return JsonResponse(response)
