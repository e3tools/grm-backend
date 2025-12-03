from datetime import timedelta

from django.core.cache import cache
from django.db import models
from django.db.models import Avg, DurationField, ExpressionWrapper, F, Q
from django.utils import timezone
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from authentication.models import User
from dashboard.constants import (
    COLOR_DANGER,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_WARNING,
    MAU_ABBREV,
    MONTHLY_CHOICE,
    PERIOD_CHOICES,
    QAU_ABBREV,
    QUARTERLY_CHOICE,
    STATUS_AT_RISK,
    STATUS_CRITICAL,
    STATUS_GOOD,
    STATUS_UNKNOWN,
    WAU_ABBREV,
    WEEKLY_CHOICE,
)


class Project(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    description = models.TextField(null=True, blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")


class PerformanceMetrics(models.Model):
    """
    Stores calculated performance metrics for the GRM system.
    This model is updated periodically to provide efficient dashboard statistics.
    """

    # Period identification
    period = models.CharField(max_length=3, choices=PERIOD_CHOICES, db_index=True)
    start_date = models.DateTimeField(db_index=True)
    end_date = models.DateTimeField(db_index=True)

    # Filters
    administrative_region = models.ForeignKey(
        'issues.AdministrativeRegion',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='performance_metrics',
    )
    category = models.ForeignKey(
        'issues.IssueCategory', on_delete=models.CASCADE, null=True, blank=True, related_name='performance_metrics'
    )

    # User Adoption Metrics (neutral fields: usable for DAU/WAU/MAU/QAU)
    active_users_count = models.IntegerField(default=0, help_text="Number of active users in chosen window")
    active_users_metric = models.CharField(max_length=10, default=WAU_ABBREV, help_text="Metric name: DAU/WAU/MAU/QAU")
    active_users_change_percentage = models.FloatField(default=0.0, help_text="Percentage change from previous period")

    new_issues_count = models.IntegerField(default=0, help_text="Total new issues created in period")
    new_issues_change_percentage = models.FloatField(
        default=0.0, help_text="Percentage change of new issues count from previous period"
    )

    # Issue Resolution Metrics
    average_resolution_days = models.FloatField(default=0.0, help_text="Average days to resolve issues")
    resolution_rate = models.FloatField(default=0.0, help_text="Percentage of issues resolved vs total issues")
    total_resolved_issues = models.IntegerField(default=0)
    total_issues = models.IntegerField(default=0)
    resolution_change_percentage = models.FloatField(
        default=0.0, help_text="Percentage change in resolution time from previous period"
    )
    resolution_rate_change_percentage = models.FloatField(
        default=0.0, help_text="Percentage change of resolution rate from previous period"
    )

    # Citizen Satisfaction Metrics
    average_satisfaction_score = models.FloatField(default=0.0, help_text="Average rating score (1-5)")
    appeal_rate = models.FloatField(default=0.0, help_text="Percentage of issues appealed")
    total_appeals = models.IntegerField(default=0)
    total_rated_issues = models.IntegerField(default=0)
    satisfaction_change_percentage = models.FloatField(
        default=0.0, help_text="Percentage change in satisfaction from previous period"
    )
    appeal_rate_change_percentage = models.FloatField(
        default=0.0, help_text="Percentage change of appeal rate from previous period"
    )

    # Metadata
    calculated_at = models.DateTimeField(default=now, db_index=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Performance Metrics")
        verbose_name_plural = _("Performance Metrics")
        ordering = ['-calculated_at']
        indexes = [
            models.Index(fields=['period', 'administrative_region', 'category', '-calculated_at']),
        ]
        unique_together = ['period', 'start_date', 'end_date', 'administrative_region', 'category']

    def __str__(self):
        filters = []
        if self.administrative_region:
            filters.append(f"Region: {self.administrative_region.name}")
        if self.category:
            filters.append(f"Category: {self.category.name}")
        filter_str = ", ".join(filters) if filters else "All"
        return f"{self.get_period_display()} ({filter_str}) - {self.calculated_at.strftime('%Y-%m-%d %H:%M')}"

    @staticmethod
    def _user_adoption_window_for_period(period):
        """
        Map period value ('7d','30d','90d') to metric name and lookback days.
        Returns (metric_name, lookback_days)
        """
        metric = (WAU_ABBREV, 7)
        if period == MONTHLY_CHOICE:
            metric = (MAU_ABBREV, 30)
        elif period == QUARTERLY_CHOICE:
            metric = (QAU_ABBREV, 90)
        return metric

    @classmethod
    def calculate_and_save(cls, period, region=None, category=None, calculated_at=None):
        """
        Calculate metrics for the given period/filters and persist a PerformanceMetrics row.

        - If `calculated_at` is provided (timezone-aware datetime), it is used as the
          reference "now" to compute end_date and start_date. If not provided, timezone.now()
          is used.
        - The DB lookup for update_or_create uses the unique key (period, start_date, end_date,
          administrative_region, category). calculated_at is stored via defaults so repeated
          runs with the same calculated_at will update the same logical snapshot.
        """
        # Normalize calculated_at: use provided value or now, ensure timezone-aware
        if calculated_at is None:
            calculated_at = timezone.now()
        else:
            # If a naive datetime was passed, assume UTC (adjust if you prefer another default)
            if timezone.is_naive(calculated_at):
                calculated_at = timezone.make_aware(calculated_at, timezone=timezone.utc)

        # Use calculated_at as the reference "now" for start/end computation
        end_date = calculated_at
        if period == WEEKLY_CHOICE:
            start_date = end_date - timedelta(days=7)
        elif period == MONTHLY_CHOICE:
            start_date = end_date - timedelta(days=30)
        elif period == QUARTERLY_CHOICE:
            start_date = end_date - timedelta(days=90)
        else:
            raise ValueError(f"Invalid period: {period}. Must be one of '7d', '30d', '90d'")

        # Compute metrics using the explicit window
        metrics_data = cls._calculate_metrics(start_date, end_date, region, category, period)

        # Ensure calculated_at is saved but NOT used as part of the lookup keys
        defaults = metrics_data.copy()
        defaults['calculated_at'] = calculated_at

        # Update or create based on the model's unique key (period, start_date, end_date, region, category)
        metrics_obj, created = cls.objects.update_or_create(
            period=period,
            start_date=start_date,
            end_date=end_date,
            administrative_region=region,
            category=category,
            defaults=defaults,
        )

        return metrics_obj

    @classmethod
    def _calculate_metrics(cls, start_date, end_date, region, category, period):
        from issues.models import Issue

        # Base queryset for confirmed issues
        base_qs = Issue.objects.filter(confirmed=True)

        # Apply filters (region descendant logic already in get_descendant_ids)
        if region:
            base_qs = base_qs.filter(administrative_region_id__in=region.get_descendant_ids())

        if category:
            base_qs = base_qs.filter(category=category)

        # Issues in current period and previous period
        current_issues = base_qs.filter(intake_date__range=[start_date, end_date])

        period_duration = end_date - start_date
        prev_start_date = start_date - period_duration
        prev_end_date = start_date
        previous_issues = base_qs.filter(intake_date__range=[prev_start_date, prev_end_date])

        # --- USER ADOPTION METRICS (using User.last_login) ---
        metric_name, lookback_days = cls._user_adoption_window_for_period(period)

        lookback_start = end_date - timedelta(days=lookback_days)
        prev_lookback_start = lookback_start - timedelta(days=lookback_days)
        prev_lookback_end = lookback_start

        active_users = User.objects.filter(last_login__range=[lookback_start, end_date]).count()
        prev_active_users = User.objects.filter(last_login__range=[prev_lookback_start, prev_lookback_end]).count()
        active_change = cls._calculate_percentage_change(active_users, prev_active_users)

        # --- NEW ISSUES ---
        new_issues_count = current_issues.count()
        prev_new_issues_count = previous_issues.count()
        new_issues_change = cls._calculate_percentage_change(new_issues_count, prev_new_issues_count)

        # --- ISSUE RESOLUTION METRICS ---
        resolved_issues = current_issues.filter(
            status__final_status=True, resolution_date__isnull=False, resolution_date__range=[start_date, end_date]
        )

        total_resolved = resolved_issues.count()
        total_issues = current_issues.count()
        resolution_rate = (total_resolved / total_issues * 100) if total_issues > 0 else 0.0

        # average resolution time
        resolution_times = []
        for issue in resolved_issues:
            if issue.resolution_date and issue.intake_date:
                days = (issue.resolution_date - issue.intake_date).days
                if days >= 0:
                    resolution_times.append(days)
        avg_resolution_days = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0

        # previous period resolution rate and average
        prev_resolved = previous_issues.filter(
            status__final_status=True,
            resolution_date__isnull=False,
            resolution_date__range=[prev_start_date, prev_end_date],
        )
        prev_total_resolved = prev_resolved.count()
        prev_total_issues = previous_issues.count()
        prev_resolution_rate = (prev_total_resolved / prev_total_issues * 100) if prev_total_issues > 0 else 0.0

        prev_resolution_times = []
        for issue in prev_resolved:
            if issue.resolution_date and issue.intake_date:
                days = (issue.resolution_date - issue.intake_date).days
                if days >= 0:
                    prev_resolution_times.append(days)
        prev_avg_resolution = sum(prev_resolution_times) / len(prev_resolution_times) if prev_resolution_times else 0.0

        resolution_change = cls._calculate_percentage_change(
            avg_resolution_days, prev_avg_resolution, lower_is_better=True
        )

        resolution_rate_change = cls._calculate_percentage_change(resolution_rate, prev_resolution_rate)

        # --- CITIZEN SATISFACTION METRICS ---
        rated_issues = current_issues.filter(rating__gt=0)
        total_rated = rated_issues.count()
        avg_satisfaction = rated_issues.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0.0

        appealed_issues = current_issues.filter(appeal_status=True).count()
        appeal_rate = (appealed_issues / total_issues * 100) if total_issues > 0 else 0.0

        prev_appealed = previous_issues.filter(appeal_status=True).count()
        prev_appeal_rate = (prev_appealed / prev_total_issues * 100) if prev_total_issues > 0 else 0.0
        appeal_change = cls._calculate_percentage_change(appeal_rate, prev_appeal_rate)

        prev_rated = previous_issues.filter(rating__gt=0)
        prev_avg_satisfaction = prev_rated.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0.0
        satisfaction_change = cls._calculate_percentage_change(avg_satisfaction, prev_avg_satisfaction)

        return {
            'active_users_count': active_users,
            'active_users_metric': metric_name,
            'active_users_change_percentage': active_change,
            'new_issues_count': new_issues_count,
            'new_issues_change_percentage': new_issues_change,
            'average_resolution_days': round(avg_resolution_days, 1),
            'resolution_rate': round(resolution_rate, 1),
            'total_resolved_issues': total_resolved,
            'total_issues': total_issues,
            'resolution_change_percentage': resolution_change,
            'resolution_rate_change_percentage': resolution_rate_change,
            'average_satisfaction_score': round(avg_satisfaction, 2),
            'appeal_rate': round(appeal_rate, 1),
            'total_appeals': appealed_issues,
            'total_rated_issues': total_rated,
            'satisfaction_change_percentage': satisfaction_change,
            'appeal_rate_change_percentage': appeal_change,
        }

    @staticmethod
    def _calculate_percentage_change(current, previous, lower_is_better=False):
        if previous == 0:
            return 100.0 if current > 0 else 0.0

        change = ((current - previous) / previous) * 100

        if lower_is_better:
            change = -change

        return round(change, 1)

    @classmethod
    def get_latest(cls, period, region=None, category=None):
        """
        Return the most recent PerformanceMetrics row that was calculated
        for exactly the requested filter combination.

        Semantics:
        - region is None => administrative_region IS NULL (global metrics)
        - region is not None => administrative_region == region (the stored metric
          is expected to already include region + its descendants at calculation time)
        - category is None => category IS NULL (all categories)
        - category is not None => category == category

        This method performs an exact match on the saved filter columns and does
        NOT attempt to aggregate or fallback to descendant-region rows. Use a
        separate helper if fallback/aggregation is required.
        """

        filters = {'period': period}

        # administrative_region exact-match (NULL for global)

        if region is None:
            filters['administrative_region__isnull'] = True
        else:
            filters['administrative_region'] = region

        # category exact-match (NULL for global)

        if category is None:
            filters['category__isnull'] = True
        else:
            filters['category'] = category

        return cls.objects.filter(**filters).order_by('-calculated_at').first()

    def to_dict(self):
        return {
            'active_users_count': self.active_users_count,
            'active_users_metric': self.active_users_metric,
            'active_users_change_percentage': self.active_users_change_percentage,
            'new_issues_count': self.new_issues_count,
            'new_issues_change_percentage': self.new_issues_change_percentage,
            'average_resolution_days': self.average_resolution_days,
            'resolution_rate': self.resolution_rate,
            'total_resolved_issues': self.total_resolved_issues,
            'total_issues': self.total_issues,
            'resolution_change_percentage': self.resolution_change_percentage,
            'resolution_rate_change_percentage': self.resolution_rate_change_percentage,
            'average_satisfaction_score': self.average_satisfaction_score,
            'appeal_rate': self.appeal_rate,
            'appeal_rate_change_percentage': self.appeal_rate_change_percentage,
            'total_appeals': self.total_appeals,
            'total_rated_issues': self.total_rated_issues,
            'satisfaction_change_percentage': self.satisfaction_change_percentage,
            'calculated_at': self.calculated_at,
        }

    @staticmethod
    def _get_status(current_value, metric_type='adoption', target=None):
        """
        Factory method for determining status.
        Centralizes the logic and avoids repetition.

        Args:
            current_value: Current value to evaluate
            metric_type: 'adoption', 'resolution', 'satisfaction'
            target: Target value (for resolution and satisfaction)

        Returns:
            dict: Status dict con badge, icon, text, etc
        """

        if metric_type == 'adoption':
            # Positive change is good
            if current_value >= 0:
                return STATUS_GOOD
            elif current_value >= -10:
                return STATUS_AT_RISK
            else:
                return STATUS_CRITICAL

        elif metric_type == 'resolution' and target is not None:
            # Lower is better
            deviation = ((current_value - target) / target) * 100
            if deviation <= 10:
                return STATUS_GOOD
            elif deviation <= 20:
                return STATUS_AT_RISK
            else:
                return STATUS_CRITICAL

        elif metric_type == 'satisfaction' and target is not None:
            # Higher is better
            if current_value == 0:
                return STATUS_UNKNOWN

            deviation = ((target - current_value) / target) * 100
            if deviation <= 10:
                return STATUS_GOOD
            elif deviation <= 20:
                return STATUS_AT_RISK
            else:
                return STATUS_CRITICAL

        return STATUS_UNKNOWN

    def get_user_adoption_status(self):
        """Determines User Adoption status"""
        return self._get_status(self.active_users_change_percentage, metric_type='adoption')

    def get_resolution_status(self, target=10.0):
        """Determines Issue Resolution status"""
        return self._get_status(self.average_resolution_days, metric_type='resolution', target=target)

    def get_satisfaction_status(self, target=4.0):
        """Determine Citizen Satisfaction status"""
        return self._get_status(self.average_satisfaction_score, metric_type='satisfaction', target=target)


class StatusBottleneckMetrics(models.Model):
    """
    Snapshot metrics per IssueStatus used by the Performance Diagnostics table.

    Each row represents aggregated metrics for a single IssueStatus and a given
    (period, start_date, end_date, administrative_region, category) combination.
    """

    period = models.CharField(max_length=3, choices=PERIOD_CHOICES, db_index=True)
    start_date = models.DateTimeField(db_index=True)
    end_date = models.DateTimeField(db_index=True)

    administrative_region = models.ForeignKey(
        'issues.AdministrativeRegion', on_delete=models.CASCADE, null=True, blank=True
    )
    category = models.ForeignKey('issues.IssueCategory', on_delete=models.CASCADE, null=True, blank=True)
    issue_status = models.ForeignKey('issues.IssueStatus', on_delete=models.CASCADE)

    issues_count = models.IntegerField(default=0)
    average_time_in_status_days = models.FloatField(default=0.0)

    calculated_at = models.DateTimeField(default=now, db_index=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Status Bottleneck Metric")
        verbose_name_plural = _("Status Bottleneck Metrics")
        unique_together = [('period', 'start_date', 'end_date', 'administrative_region', 'category', 'issue_status')]
        indexes = [
            models.Index(fields=['period', 'administrative_region', 'category', 'issue_status', '-calculated_at']),
        ]

    def __str__(self):
        region = self.administrative_region.name if self.administrative_region else "All"
        cat = self.category.name if self.category else "All"
        return f"{self.get_period_display()} | {self.issue_status.name} | {region} | {cat} @ {self.calculated_at.isoformat()}"

    @classmethod
    def get_latest_for_filters(cls, period, region=None, category=None):
        """
        Return a queryset of StatusBottleneckMetrics ordered by -calculated_at for the given filters.
        Caller can further filter by calculated_at to get a single snapshot.
        """
        filters = {'period': period}
        if region is None:
            filters['administrative_region__isnull'] = True
        else:
            filters['administrative_region'] = region
        if category is None:
            filters['category__isnull'] = True
        else:
            filters['category'] = category
        return cls.objects.filter(**filters).order_by('-calculated_at')


class RegionPerformanceMetrics(models.Model):
    """
    Computed metrics for regions for fast queries in the performance by region table.
    Pre-computed and cached, updated via management command.
    """

    region = models.ForeignKey(
        'issues.AdministrativeRegion', on_delete=models.CASCADE, related_name='region_performance_metrics'
    )
    category = models.ForeignKey('issues.IssueCategory', on_delete=models.CASCADE, null=True, blank=True)
    period = models.CharField(max_length=3, choices=[('7d', '7d'), ('30d', '30d'), ('90d', '90d')])

    open_issues_count = models.IntegerField(default=0)
    avg_resolution_days = models.FloatField(default=0.0)
    active_workers_count = models.IntegerField(default=0)
    total_workers_in_region = models.IntegerField(default=0)

    # Calculated scores (0-100) for weighted formula
    open_issues_score = models.FloatField(default=100.0)
    resolution_score = models.FloatField(default=100.0)
    active_workers_score = models.FloatField(default=100.0)
    overall_performance_score = models.FloatField(default=100.0)

    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('region', 'category', 'period')
        verbose_name = "Region Performance Metrics"
        verbose_name_plural = "Region Performance Metrics"
        indexes = [
            models.Index(fields=['period', 'category', '-overall_performance_score']),
        ]

    @classmethod
    def get_workers_count_cached(cls, region_ids, start_date, end_date):
        from authentication.models import Facilitator, GovernmentWorker

        cache_key = f"workers_{hash(tuple(region_ids))}_{start_date.date()}_{end_date.date()}"
        cached = cache.get(cache_key)

        if cached is not None:
            return cached

        active_gov = GovernmentWorker.objects.filter(
            administrative_region_id__in=region_ids, user__last_login__gte=start_date, user__last_login__lte=end_date
        ).values_list('user_id', flat=True)

        active_fac = Facilitator.objects.filter(
            administrative_region_id__in=region_ids, user__last_login__gte=start_date, user__last_login__lte=end_date
        ).values_list('user_id', flat=True)

        active_users = set(active_gov) | set(active_fac)

        total_gov = GovernmentWorker.objects.filter(administrative_region_id__in=region_ids).values_list(
            'user_id', flat=True
        )

        total_fac = Facilitator.objects.filter(administrative_region_id__in=region_ids).values_list(
            'user_id', flat=True
        )

        total_users = set(total_gov) | set(total_fac)

        result = {'active': len(active_users), 'total': len(total_users)}

        cache.set(cache_key, result, 3600)  # 1 hora
        return result

    @classmethod
    def calculate_data(cls, region, category=None, period=None, days=7):
        """
        Efficient, pure calculation helper for RegionPerformanceMetrics.

        Returns a dict with keys matching the RegionPerformanceMetrics fields used
        by the bulk persistence flow. This method performs only read queries and
        pure Python calculations; it does NOT create or save any model instances.

        Parameters
        - region: AdministrativeRegion instance or None (for global)
        - category: IssueCategory instance or None
        - period: period key (not used for calculation but kept for signature parity)
        - days: integer number of days corresponding to period

        Returned dict keys:
          open_issues_count, avg_resolution_days,
          active_workers_count, total_workers_in_region,
          open_issues_score, resolution_score, active_workers_score,
          overall_performance_score, calculated_at
        """
        from issues.models import Issue

        now = timezone.now()
        end_date = now
        start_date = now - timedelta(days=days)

        # region -> region_ids (descendants) fallback to [region.id]
        region_ids = None
        if region is not None:
            try:
                region_ids = region.get_descendant_ids()
            except Exception:
                region_ids = [region.id]

        base_q = Q(confirmed=True)
        if region_ids is not None:
            base_q &= Q(administrative_region_id__in=region_ids)
        if category is not None:
            base_q &= Q(category=category)

        # 1) Open issues count
        open_issues_q = base_q & Q(intake_date__gte=start_date, intake_date__lte=end_date)
        open_issues_q &= ~Q(status__final_status=True) & ~Q(status__rejected_status=True)
        open_issues_count = int(Issue.objects.filter(open_issues_q).count() or 0)

        # 2) Average resolution days (safe handling when no rows)
        avg_resolution_days = None
        try:
            resolved_q = base_q & Q(
                status__final_status=True,
                resolution_date__isnull=False,
                intake_date__isnull=False,
                resolution_date__gte=start_date,
                resolution_date__lte=end_date,
            )
            duration_expr = ExpressionWrapper(F('resolution_date') - F('intake_date'), output_field=DurationField())
            avg_duration = Issue.objects.filter(resolved_q).aggregate(avg_duration=Avg(duration_expr))['avg_duration']

            if avg_duration is not None:
                # avg_duration is timedelta on most backends
                avg_seconds = getattr(avg_duration, 'total_seconds', None)
                if callable(avg_seconds):
                    avg_resolution_days = avg_seconds() / 86400.0
                else:
                    try:
                        avg_resolution_days = float(avg_duration) / 86400.0
                    except Exception:
                        avg_resolution_days = None
        except Exception:
            avg_resolution_days = None

        # Ensure a numeric default (DB expects NOT NULL)
        if avg_resolution_days is None:
            avg_resolution_days = 0.0
        else:
            avg_resolution_days = round(float(avg_resolution_days), 1)

        # 3 & 4) Workers counts via cached helper (fall back to zeros)
        try:
            workers = cls.get_workers_count_cached(region_ids or [], start_date, end_date)
            active_workers = int(workers.get('active', 0) or 0)
            total_workers = int(workers.get('total', 0) or 0)
        except Exception:
            active_workers = 0
            total_workers = 0

        # Scoring (mirror tu lógica)
        def clamp(v, lo=0.0, hi=100.0):
            return max(lo, min(hi, v))

        # open_issues_score
        try:
            if open_issues_count <= 20:
                open_issues_score = 100.0
            elif open_issues_count <= 50:
                open_issues_score = 100.0 - ((open_issues_count - 20) / 30.0) * 50.0
            else:
                open_issues_score = max(0.0, 50.0 - ((open_issues_count - 50) / 50.0) * 50.0)
            open_issues_score = clamp(open_issues_score)
        except Exception:
            open_issues_score = 0.0

        # resolution_score
        try:
            if avg_resolution_days <= 7:
                resolution_score = 100.0
            elif avg_resolution_days <= 15:
                resolution_score = 100.0 - ((avg_resolution_days - 7.0) / 8.0) * 50.0
            else:
                resolution_score = max(0.0, 50.0 - ((avg_resolution_days - 15.0) / 15.0) * 50.0)
            resolution_score = clamp(resolution_score)
        except Exception:
            resolution_score = 50.0

        # active_workers_score
        try:
            active_workers_pct = (active_workers / total_workers * 100.0) if total_workers > 0 else 0.0
            if active_workers_pct >= 50.0:
                active_workers_score = 100.0
            elif active_workers_pct >= 20.0:
                active_workers_score = 100.0 - ((50.0 - active_workers_pct) / 30.0) * 50.0
            else:
                active_workers_score = max(0.0, 50.0 - ((20.0 - active_workers_pct) / 20.0) * 50.0)
            active_workers_score = clamp(active_workers_score)
        except Exception:
            active_workers_score = 0.0

        overall_score = clamp(open_issues_score * 0.40 + resolution_score * 0.35 + active_workers_score * 0.25)

        calculated_at = timezone.now()

        return {
            'open_issues_count': open_issues_count,
            'avg_resolution_days': avg_resolution_days,
            'active_workers_count': active_workers,
            'total_workers_in_region': total_workers,
            'open_issues_score': round(open_issues_score, 1),
            'resolution_score': round(resolution_score, 1),
            'active_workers_score': round(active_workers_score, 1),
            'overall_performance_score': round(overall_score, 1),
            'calculated_at': calculated_at,
        }

    def get_performance_status(self):
        """Return performance status dict for template rendering."""
        score = self.overall_performance_score
        if score >= 70:
            return STATUS_GOOD
        elif score >= 40:
            return STATUS_AT_RISK
        else:
            return STATUS_CRITICAL

    def get_open_issues_color(self):
        """Return color coding for open issues."""
        count = self.open_issues_count
        if count < 20:
            return COLOR_PRIMARY
        elif count <= 50:
            return COLOR_WARNING
        else:
            return COLOR_DANGER

    def get_resolution_time_color(self):
        """Return color coding for resolution time."""
        days = self.avg_resolution_days
        if days < 7:
            return COLOR_PRIMARY
        elif days <= 15:
            return COLOR_WARNING
        else:
            return COLOR_DANGER

    def get_active_workers_color(self):
        """Return color coding for active workers percentage."""
        if self.total_workers_in_region == 0:
            return COLOR_SECONDARY
        pct = (self.active_workers_count / self.total_workers_in_region) * 100
        if pct >= 50:
            return COLOR_PRIMARY
        elif pct >= 20:
            return COLOR_WARNING
        else:
            return COLOR_DANGER

    def get_active_workers_percentage(self):
        """Calculate percentage of active workers."""
        if self.total_workers_in_region == 0:
            return 0
        return (self.active_workers_count / self.total_workers_in_region) * 100
