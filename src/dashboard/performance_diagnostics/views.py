from django.db.models import DateTimeField, FloatField, IntegerField, OuterRef, Subquery
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
from dashboard.models import PerformanceMetrics, StatusBottleneckMetrics
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
