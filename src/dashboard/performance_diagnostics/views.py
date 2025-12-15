from django.db.models import (
    Count,
    DateTimeField,
    FloatField,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
)
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import generic

from authentication.models import Facilitator, GovernmentWorker, User
from dashboard.constants import (
    COLOR_DANGER,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_WARNING,
    ICON_ALERT,
    ICON_CHECK,
    LABEL_ACTIVE,
    LABEL_INACTIVE,
    LABEL_LOW_ACTIVITY,
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
    DataTableMixin,
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


class RegionPerformanceAPIView(UserManagementAndAJAXMixin, DataTableMixin, generic.View):
    """
    AJAX endpoint that returns JSON for DataTables.
    Accepts filters: period, category, administrative_region.
    Behavior:
      - region with children -> return metrics for children
      - region without children -> return metrics for the selected region, set no_children=True and message
      - no region -> return metrics for children of the root_region (parent IS NULL)
    """

    def get(self, request, *args, **kwargs):
        return self.handle(request, *args, **kwargs)

    def get_column_key_from_index(self, idx):
        idx_map = {0: 'region', 1: 'open_issues', 2: 'resolution', 3: 'workers', 4: 'performance'}
        return idx_map.get(idx)

    def get_base_queryset(self, request):
        period = request.GET.get('period', WEEKLY_CHOICE)
        valid_periods = {c[0] for c in PERIOD_CHOICES}
        if period not in valid_periods:
            period = WEEKLY_CHOICE
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
        return qs

    def apply_filters(self, qs, params):
        raw = params['raw']
        category_id = raw.get('category')
        region_id = raw.get('administrative_region')

        # reset flags (por si se reutiliza la instancia)
        self._no_children = False
        self._message = None

        if category_id:
            try:
                qs = qs.filter(category_id=int(category_id))
            except Exception:
                return qs.none()
        else:
            qs = qs.filter(category__isnull=True)

        no_sublevel_available_msg = _(
            'No administrative sublevel is available. Showing current selected administrative level.'
        )

        if region_id:
            try:
                region = AdministrativeRegion.objects.get(id=region_id)
            except (AdministrativeRegion.DoesNotExist, ValueError):
                return qs.none()

            children_qs = region.children.all()
            if not children_qs.exists():
                self._no_children = True
                self._message = no_sublevel_available_msg
                qs = qs.filter(region=region)
            else:
                child_ids = list(children_qs.values_list('id', flat=True))
                qs = qs.filter(region__in=child_ids)
        else:
            root_region = AdministrativeRegion.objects.filter(parent__isnull=True).first()
            if root_region:
                children_qs = root_region.children.all()
                if not children_qs.exists():
                    self._no_children = True
                    self._message = no_sublevel_available_msg
                    qs = qs.filter(region=root_region)
                else:
                    child_ids = list(children_qs.values_list('id', flat=True))
                    qs = qs.filter(region__in=child_ids)
            else:
                qs = qs.filter(region__parent__isnull=True)

        return qs

    def get_sort_map(self):
        return {
            'region': 'region__name',
            'open_issues': 'open_issues_count',
            'resolution': 'avg_resolution_days',
            'workers': 'active_workers_count',
            'performance': '-overall_performance_score',
        }

    def serialize_row(self, metric):
        perf_status = metric.get_performance_status()
        return {
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


class InactiveUsersAPIView(UserManagementAndAJAXMixin, DataTableMixin, generic.View):
    """
    AJAX endpoint that returns JSON data for inactive government workers and facilitators.
    Returns users who have not logged in for 7+ days (configurable via inactivity_threshold parameter).
    """

    def get(self, request, *args, **kwargs):
        return self.handle(request, *args, **kwargs)

    def get_column_key_from_index(self, idx):
        idx_map = {0: 'name', 1: 'role', 2: 'last_activity', 3: 'open_issues', 4: 'performance'}
        return idx_map.get(idx)

    def get_base_queryset(self, request):
        role_filter = request.GET.get('role_filter')
        if role_filter == 'government_worker':
            ids = list(GovernmentWorker.objects.values_list('user_id', flat=True))
        elif role_filter == 'facilitator':
            ids = list(Facilitator.objects.values_list('user_id', flat=True))
        else:
            gw = set(GovernmentWorker.objects.values_list('user_id', flat=True))
            fac = set(Facilitator.objects.values_list('user_id', flat=True))
            ids = list(gw | fac)

        cutoff = timezone.now() - timezone.timedelta(days=self.parse_int(request.GET.get('inactivity_threshold'), 7))
        qs = (
            User.objects.filter(id__in=ids)
            .filter(Q(last_activity__lt=cutoff) | Q(last_activity__isnull=True))
            .select_related(
                'governmentworker',
                'governmentworker__administrative_region',
                'facilitator',
                'facilitator__administrative_region',
            )
            .annotate(
                open_issues_count=Count(
                    'assigned_issues',
                    filter=Q(assigned_issues__status__open_status=True, assigned_issues__confirmed=True),
                )
            )
        )

        region_id = request.GET.get('administrative_region')
        if region_id:
            try:
                region = AdministrativeRegion.objects.get(id=region_id)
                descendant_ids = region.get_descendant_ids(include_self=True)
                gw_ids = GovernmentWorker.objects.filter(administrative_region_id__in=descendant_ids).values_list(
                    'user_id', flat=True
                )
                fac_ids = Facilitator.objects.filter(administrative_region_id__in=descendant_ids).values_list(
                    'user_id', flat=True
                )
                qs = qs.filter(id__in=list(set(list(gw_ids) + list(fac_ids))))
            except Exception:
                pass

        has_open = request.GET.get('has_open_issues')
        if has_open == 'true':
            qs = qs.filter(open_issues_count__gt=0)
        elif has_open == 'false':
            qs = qs.filter(open_issues_count=0)
        return qs

    def get_sort_map(self):
        return {
            'name': 'first_name',
            'open_issues': 'open_issues_count',
        }

    def manual_sort(self, qs_or_list, sort_by, sort_dir):
        if sort_by not in ('role', 'last_activity', 'performance'):
            return None
        users = list(qs_or_list)
        if sort_by == 'role':
            users.sort(
                key=lambda u: ('facilitator' if getattr(u, 'facilitator', None) else 'government_worker'),
                reverse=(sort_dir == 'desc'),
            )
            return users
        if sort_by == 'last_activity':
            users.sort(
                key=lambda u: (
                    u.last_activity
                    if u.last_activity is not None
                    else timezone.datetime.min.replace(tzinfo=timezone.utc)
                ),
                reverse=(sort_dir == 'desc'),
            )
            return users
        if sort_by == 'performance':

            def perf_value(u):
                last_activity_days = self._calculate_last_activity_days(u)
                perf = self._calculate_performance_rating(last_activity_days)
                label = perf.get('label', '')
                if 'Active' in str(label):
                    return 3
                if 'Low' in str(label):
                    return 2
                return 1

            users.sort(key=lambda u: perf_value(u), reverse=(sort_dir == 'desc'))
            return users

    def serialize_row(self, user):
        role = None
        role_type = None
        if getattr(user, 'governmentworker', None):
            role = _("Government Worker")
            role_type = 'government_worker'
        elif getattr(user, 'facilitator', None):
            role = _("Facilitator")
            role_type = 'facilitator'

        last_activity_days = self._calculate_last_activity_days(user)
        last_activity_display = self._format_last_activity(last_activity_days)
        last_activity_color = self._get_last_activity_color(last_activity_days)

        # Use getattr to be safe if annotation is missing
        open_issues_count = int(getattr(user, 'open_issues_count', 0))
        open_issues_color = self._get_open_issues_color(open_issues_count)

        performance_rating = self._calculate_performance_rating(last_activity_days)

        return {
            'id': user.id,
            'name': user.name,
            'photo_url': user.photo.url if getattr(user, 'photo', None) else None,
            'role': role,
            'role_type': role_type,
            'last_activity': last_activity_display,
            'last_activity_color': last_activity_color,
            'open_issues_count': open_issues_count,
            'open_issues_color': open_issues_color,
            'performance_rating': performance_rating.get('label'),
            'performance_color': performance_rating.get('color'),
            'performance_icon': performance_rating.get('icon'),
        }

    def _calculate_last_activity_days(self, user):
        """
        Calculate days since last activity using the dedicated last_activity field.
        Returns the number of days since the most recent activity.
        """
        if not user.last_activity:
            return None

        now = timezone.now()
        duration = now - user.last_activity
        return duration.days

    def _format_last_activity(self, days):
        """Format last activity for display"""
        if days is None:
            return _("Never")

        if days == 0:
            return _("Today")
        elif days == 1:
            return _("1 day ago")
        else:
            return _("%(days)s days ago") % {'days': days}

    def _get_last_activity_color(self, days):
        """
        Get color coding for last activity:
        - 7-14 days: secondary
        - 14-30 days: warning
        - >30 days: danger
        """
        if days is None or days > 30:
            return COLOR_DANGER
        elif days >= 14:
            return COLOR_WARNING
        else:
            # 7-13 days (since threshold is 7)
            return COLOR_SECONDARY

    def _get_open_issues_color(self, count):
        """Get color coding for open issues"""
        if count > 10:
            return COLOR_DANGER
        elif count >= 5:
            return COLOR_WARNING
        else:
            return COLOR_PRIMARY

    def _calculate_performance_rating(self, last_activity_days):
        """
        Calculate performance rating based on last activity days.
        Active: < 7 days, Low Activity: 7-20 days, Inactive: > 20 days
        """

        if last_activity_days is None or last_activity_days > 20:
            return {'label': LABEL_INACTIVE, 'color': COLOR_SECONDARY, 'icon': ICON_ALERT}
        elif last_activity_days < 7:
            return {'label': LABEL_ACTIVE, 'color': COLOR_PRIMARY, 'icon': ICON_CHECK}

        # Low Activity: 7-20 days
        return {'label': LABEL_LOW_ACTIVITY, 'color': COLOR_WARNING, 'icon': ICON_ALERT}
