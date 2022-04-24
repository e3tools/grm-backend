from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.views import generic

from client import get_db
from dashboard.grm.forms import SearchIssueForm
from dashboard.mixins import AJAXRequestMixin, JSONResponseMixin, PageMixin
from grm.utils import get_base_administrative_id

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class HomeFormView(PageMixin, LoginRequiredMixin, generic.FormView):
    form_class = SearchIssueForm
    template_name = 'diagnostics/home.html'
    title = _('Diagnostics')
    active_level1 = 'diagnostics'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_token'] = settings.MAPBOX_ACCESS_TOKEN
        context['lat'] = settings.DIAGNOSTIC_MAP_LATITUDE
        context['lng'] = settings.DIAGNOSTIC_MAP_LONGITUDE
        context['zoom'] = settings.DIAGNOSTIC_MAP_ZOOM
        context['ws_bound'] = settings.DIAGNOSTIC_MAP_WS_BOUND
        context['en_bound'] = settings.DIAGNOSTIC_MAP_EN_BOUND
        context['country_iso_code'] = settings.DIAGNOSTIC_MAP_ISO_CODE
        return context


class IssuesPercentagesView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        grm_db = get_db(COUCHDB_GRM_DATABASE)

        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        category = self.request.GET.get('category')
        issue_type = self.request.GET.get('type')
        region_level = self.request.GET.get('region_level')

        issues_by_region = grm_db.get_view_result('issues', 'group_by_administrative_region', group=True)[:]
        total_issues = sum((i['value'] for i in issues_by_region))
        issues_percentages = dict()
        eadl_db = get_db()
        for d in issues_by_region:
            key = get_base_administrative_id(eadl_db, d['key'], region_level)
            if key in issues_percentages:
                issues_percentages[key]['count'] = issues_percentages[key]['count'] + d['value']
            else:
                issues_percentages[key] = {
                    'count': d['value']
                }
        for k in issues_percentages:
            issues_percentages[k]['percentage'] = round(issues_percentages[k]['count'] * 100 / total_issues)
            issues_percentages[k]['issues'] = issues_percentages[k]['count']
        regions = [k for k in issues_percentages]
        selector = {
            "$and": [
                {
                    "type": "administrative_level"
                },
                {
                    "administrative_id": {
                        "$in": regions
                    }
                }
            ]
        }

        date_range = dict()
        if start_date:
            start_date = datetime.strptime(start_date, '%d/%m/%Y').strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            date_range["$gte"] = start_date
            selector["intake_date"] = date_range
        if end_date:
            end_date = (datetime.strptime(end_date, '%d/%m/%Y') + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            date_range["$lte"] = end_date
            selector["intake_date"] = date_range
        if category:
            selector["category.id"] = int(category)
        if issue_type:
            selector["issue_type.id"] = int(issue_type)

        administrative_level_docs = eadl_db.get_query_result(selector)
        print(administrative_level_docs[:])
        if administrative_level_docs[:]:
            for doc in administrative_level_docs:
                d = issues_percentages[doc['administrative_id']]
                d['name'] = doc['name']
                d['latitude'] = doc['latitude']
                d['longitude'] = doc['longitude']
        else:
            issues_percentages = dict()
        # print(issues_percentages)
        return self.render_to_json_response(issues_percentages)
