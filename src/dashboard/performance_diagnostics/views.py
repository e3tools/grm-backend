from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import generic

from dashboard.constants import PERIOD_CHOICES, WEEKLY_CHOICE
from dashboard.grm.forms import SearchIssueForm
from dashboard.mixins import PageMixin, UserManagementPermissionMixin
from dashboard.models import PerformanceMetrics
from issues.models import AdministrativeRegion, IssueCategory


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


class PerformanceMetricsAPIView(UserManagementPermissionMixin, generic.View):
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
                'performance_diagnostics/kpi_error.html',
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
