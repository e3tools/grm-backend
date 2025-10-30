import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View

from common.utils.pinecone_connector import PineconeConnector
from issues.models import AdministrativeRegion, CitizenAgeGroup, Issue, IssueType

logger = logging.getLogger(__name__)


class SemanticSearchView(LoginRequiredMixin, View):
    """
    Semantic search view powered by Pinecone (SDK 7.3.0).
    Supports HTMX for live updates (query, filters, pagination).
    """

    template_name = "search/semantic_search.html"
    results_partial = "search/_results.html"
    search_container_partial = "search/_search_container.html"
    connector = PineconeConnector()

    def get(self, request: HttpRequest) -> HttpResponse:
        query = request.GET.get("q", "").strip()
        administrative_region = request.GET.get("administrative_region")
        issue_type = request.GET.get("issue_type")
        age_group = request.GET.get("age_group")
        group = request.GET.get("group")
        group_2 = request.GET.get("group_2")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")
        page = int(request.GET.get("page", 1))
        per_page = int(request.GET.get("per_page", 10))

        search_active = bool(query)
        results, total_results = [], 0

        try:
            if search_active:
                pinecone_results = self.connector.query_text(query_text=query, top_k=100)

                filtered = []
                for item in pinecone_results:
                    # In SDK 7.3.0, metadata is expanded as flat keys
                    fields = item.get("fields", {})

                    if (
                        administrative_region
                        and str(fields.get("administrative_region_id", "")).replace('.0', '') != administrative_region
                    ):
                        continue
                    if issue_type and str(fields.get("issue_type_id", "")).replace('.0', '') != issue_type:
                        continue
                    if age_group and str(fields.get("age_group_id", "")).replace('.0', '') != age_group:
                        continue
                    if group and str(fields.get("group_id", "")).replace('.0', '') != group:
                        continue
                    if group_2 and str(fields.get("group_2_id", "")).replace('.0', '') != group_2:
                        continue

                    issue_date = fields.get("issue_date")
                    if start_date and (not issue_date or issue_date < start_date):
                        continue
                    if end_date and (not issue_date or issue_date > end_date):
                        continue

                    filtered.append(item)

                paginator = Paginator(filtered, per_page)
                results = paginator.get_page(page)
                total_results = len(filtered)

        except Exception as e:
            logger.error(f"Error during semantic search: {e}")

        confirmed_issues = Issue.objects.filter(confirmed=True)
        if hasattr(results, 'object_list'):
            filtered_issues = [int(item.get('_id')) for item in results.object_list]
            issues_status = confirmed_issues.filter(id__in=filtered_issues).values_list(
                'id', 'status_id', 'status__name'
            )
            issues_status = {
                issue_id: {"id": status_id, "name": status_name} for issue_id, status_id, status_name in issues_status
            }
            for item in results.object_list:
                item['status'] = issues_status.get(int(item.get('_id')))

        context = {
            "title": _("Search Issues"),
            "query": query,
            "total_results": total_results,
            "page_obj": results,
            "search_active": search_active,
            "filters": {
                "administrative_region": administrative_region,
                "issue_type": issue_type,
                "age_group": age_group,
                "group": group,
                "group_2": group_2,
                "start_date": start_date,
                "end_date": end_date,
            },
            "administrative_regions": AdministrativeRegion.objects.filter(
                id__in=confirmed_issues.values_list("administrative_region_id", flat=True)
            )
            .select_related("parent", "administrative_level")
            .order_by("name")
            .distinct(),
            "types": IssueType.objects.filter(id__in=confirmed_issues.values_list("issue_type_id", flat=True))
            .order_by("name")
            .distinct(),
            "age_groups": CitizenAgeGroup.objects.filter(
                id__in=confirmed_issues.values_list("citizen__age_group_id", flat=True)
            )
            .order_by("name")
            .distinct(),
            "groups": CitizenAgeGroup.objects.filter(
                id__in=confirmed_issues.values_list("citizen__group_id", flat=True)
            )
            .order_by("name")
            .distinct(),
            "groups_2": CitizenAgeGroup.objects.filter(
                id__in=confirmed_issues.values_list("citizen__group_2_id", flat=True)
            )
            .order_by("name")
            .distinct(),
        }

        # HTMX behavior
        if request.headers.get("HX-Request"):
            hx_target = request.headers.get("HX-Target", "")

            if search_active and hx_target == "search-container":
                return render(request, self.search_container_partial, context)

            if search_active and hx_target == "results":
                return render(request, self.results_partial, context)

            return render(request, self.search_container_partial, context)

        return render(request, self.template_name, context)
