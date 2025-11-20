from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import generic

from dashboard.grm.forms import SearchIssueForm
from dashboard.mixins import PageMixin, UserManagementPermissionMixin
from dashboard.models import PerformanceMetrics
from issues.models import IssueCategory


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
        context['period_choices'] = PerformanceMetrics.PERIOD_CHOICES

        return context


class PerformanceMetricsAPIView(UserManagementPermissionMixin, generic.View):
    """
    AJAX endpoint to fetch KPI metrics based on filters.
    Returns JSON data for HTMX to render.
    """

    def get(self, request, *args, **kwargs):
        # Get filters from request
        period = request.GET.get('period', '7d')
        region_id = request.GET.get('administrative_region')
        category_id = request.GET.get('category')

        # Parse filters
        region = None
        category = None

        if region_id:
            try:
                from issues.models import AdministrativeRegion

                region = AdministrativeRegion.objects.get(id=region_id)
            except (AdministrativeRegion.DoesNotExist, ValueError):
                pass

        if category_id:
            try:
                category = IssueCategory.objects.get(id=category_id)
            except (IssueCategory.DoesNotExist, ValueError):
                pass

        # Get latest metrics from database
        metrics_obj = PerformanceMetrics.get_latest(period, region, category)
        if metrics_obj:
            metrics = metrics_obj.to_dict()
        elif region:
            agg = PerformanceMetrics.aggregate_metrics_from_children(period, region, category)
            if agg:
                metrics = agg
            else:
                metrics = None

        # If no metrics exist, return error message
        if not metrics:
            context = {'error': True, 'message': _('No metrics available for the selected filters.')}
            return render(request, 'performance_diagnostics/kpi_error.html', context)

        # Get metrics data and status
        user_adoption_status = metrics_obj.get_user_adoption_status()
        resolution_status = metrics_obj.get_resolution_status(target=10.0)
        satisfaction_status = metrics_obj.get_satisfaction_status(target=4.0)

        context = {
            'metrics': metrics,
            'user_adoption_status': user_adoption_status,
            'resolution_status': resolution_status,
            'satisfaction_status': satisfaction_status,
            'last_updated': metrics_obj.calculated_at,
        }

        # Return HTML fragment for HTMX
        return render(request, 'performance_diagnostics/kpi_cards.html', context)
