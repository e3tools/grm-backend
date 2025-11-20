from datetime import timedelta

from django.db import models
from django.db.models import Avg
from django.utils import timezone
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from authentication.models import User
from dashboard.constants import (
    STATUS_AT_RISK,
    STATUS_CRITICAL,
    STATUS_GOOD,
    STATUS_UNKNOWN,
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

    PERIOD_CHOICES = [
        ('7d', _('Last 7 Days')),
        ('30d', _('Last 30 Days')),
        ('90d', _('Last 90 Days')),
    ]

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
    active_users_metric = models.CharField(max_length=10, default='WAU', help_text="Metric name: DAU/WAU/MAU/QAU")
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
        metric = ('WAU', 7)
        if period == '30d':
            metric = ('MAU', 30)
        elif period == '90d':
            metric = ('QAU', 90)
        return metric

    @classmethod
    def calculate_and_save(cls, period, region=None, category=None):
        end_date = timezone.now()
        if period == '7d':
            start_date = end_date - timedelta(days=7)
        elif period == '30d':
            start_date = end_date - timedelta(days=30)
        elif period == '90d':
            start_date = end_date - timedelta(days=90)
        else:
            raise ValueError(f"Invalid period: {period}. Must be one of '7d', '30d', '90d'")

        metrics_data = cls._calculate_metrics(start_date, end_date, region, category, period)

        metrics_obj, created = cls.objects.update_or_create(
            period=period,
            start_date=start_date,
            end_date=end_date,
            administrative_region=region,
            category=category,
            defaults={**metrics_data, 'calculated_at': timezone.now()},
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

    @classmethod
    def get_latest_with_fallback(cls, period, region=None, category=None, fallback_to_children=False):
        """
        Try exact match first. If not present and fallback_to_children=True and region given,
        return the most recent metric recorded for any descendant region.
        """
        exact = cls.get_latest(period=period, region=region, category=category)
        if exact or not fallback_to_children:
            return exact

        # fallback search among descendants
        if region is None:
            return None

        descendant_ids = region.get_descendant_ids()
        if not descendant_ids:
            return None

        filters = {'period': period, 'administrative_region_id__in': descendant_ids}
        if category is None:
            filters['category__isnull'] = True
        else:
            filters['category'] = category

        return cls.objects.filter(**filters).order_by('-calculated_at').first()

    @classmethod
    def aggregate_metrics_from_children(cls, period, region, category=None):
        """
        Aggregate numeric fields from PerformanceMetrics rows computed for descendants of region.
        Returns a dict with aggregated values (same shape as to_dict()) or None if no children rows.
        Rules:
          - Sum counters: active_users_count, new_issues_count, total_resolved_issues, total_issues, total_appeals, total_rated_issues
          - For averages: compute weighted averages where appropriate:
              * average_resolution_days: weight by total_resolved_issues
              * average_satisfaction_score: weight by total_rated_issues
          - For rates: recompute as (sum_resolved / sum_total_issues)*100 and (sum_appeals / sum_total_issues)*100
          - For change percentages: not meaningful to aggregate reliably; set to None (or compute if desired separately)
        """
        descendant_ids = region.get_descendant_ids()
        qs = cls.objects.filter(period=period, administrative_region_id__in=descendant_ids)
        if category is None:
            qs = qs.filter(category__isnull=True)
        else:
            qs = qs.filter(category=category)

        if not qs.exists():
            return None

        # aggregate counters
        sum_active_users = qs.aggregate(total_active=models.Sum('active_users_count'))['total_active'] or 0
        sum_new_issues = qs.aggregate(total_new=models.Sum('new_issues_count'))['total_new'] or 0
        sum_total_resolved = qs.aggregate(total_resolved=models.Sum('total_resolved_issues'))['total_resolved'] or 0
        sum_total_issues = qs.aggregate(total_issues=models.Sum('total_issues'))['total_issues'] or 0
        sum_total_appeals = qs.aggregate(total_appeals=models.Sum('total_appeals'))['total_appeals'] or 0
        sum_total_rated = qs.aggregate(total_rated=models.Sum('total_rated_issues'))['total_rated'] or 0

        # weighted averages
        # avg resolution days weighted by resolved issues
        total_weighted_resolution = 0.0
        for row in qs:
            if row.total_resolved_issues and row.average_resolution_days:
                total_weighted_resolution += row.average_resolution_days * row.total_resolved_issues
        avg_resolution_days = (total_weighted_resolution / sum_total_resolved) if sum_total_resolved else 0.0

        # avg satisfaction weighted by rated issues
        total_weighted_satisfaction = 0.0
        for row in qs:
            if row.total_rated_issues and row.average_satisfaction_score:
                total_weighted_satisfaction += row.average_satisfaction_score * row.total_rated_issues
        avg_satisfaction = (total_weighted_satisfaction / sum_total_rated) if sum_total_rated else 0.0

        # recompute rates
        resolution_rate = (sum_total_resolved / sum_total_issues * 100) if sum_total_issues else 0.0
        appeal_rate = (sum_total_appeals / sum_total_issues * 100) if sum_total_issues else 0.0

        return {
            'active_users_count': int(sum_active_users),
            'active_users_metric': None,
            'active_users_change_percentage': None,
            'new_issues_count': int(sum_new_issues),
            'new_issues_change_percentage': None,
            'average_resolution_days': float(round(avg_resolution_days, 1)),
            'resolution_rate': float(round(resolution_rate, 1)),
            'total_resolved_issues': int(sum_total_resolved),
            'total_issues': int(sum_total_issues),
            'resolution_change_percentage': None,
            'resolution_rate_change_percentage': None,
            'average_satisfaction_score': float(round(avg_satisfaction, 2)),
            'appeal_rate': float(round(appeal_rate, 1)),
            'total_appeals': int(sum_total_appeals),
            'total_rated_issues': int(sum_total_rated),
            'satisfaction_change_percentage': None,
            'appeal_rate_change_percentage': None,
        }

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

    def get_user_adoption_status(self):
        current_value = self.active_users_change_percentage

        # For adoption, positive change is good
        if current_value >= 0:
            return STATUS_GOOD
        elif current_value >= -10:
            return STATUS_AT_RISK
        else:
            return STATUS_CRITICAL

    def get_resolution_status(self, target=10.0):
        current_value = self.average_resolution_days
        deviation = ((current_value - target) / target) * 100

        if deviation <= 10:
            return STATUS_GOOD
        elif deviation <= 20:
            return STATUS_AT_RISK
        else:
            return STATUS_CRITICAL

    def get_satisfaction_status(self, target=4.0):
        current_value = self.average_satisfaction_score

        if current_value == 0:
            return STATUS_UNKNOWN

        deviation = ((target - current_value) / target) * 100

        if deviation <= 10:
            return STATUS_GOOD
        elif deviation <= 20:
            return STATUS_AT_RISK
        else:
            return STATUS_CRITICAL
