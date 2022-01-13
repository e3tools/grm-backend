from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.views import generic

from client import get_db
from dashboard.mixins import AJAXRequestMixin, JSONResponseMixin, PageMixin
from grm.utils import get_base_administrative_id

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class HomeTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
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
        issues_by_region = grm_db.get_view_result('issues', 'group_by_administrative_region', group=True)[:]
        total_issues = sum((i['value'] for i in issues_by_region))
        issues_percentages = dict()
        eadl_db = get_db()
        for d in issues_by_region:
            key = get_base_administrative_id(eadl_db, d['key'])
            if key in issues_percentages:
                issues_percentages[key] = issues_percentages[key] + d['value']
            else:
                issues_percentages[key] = {
                    'count': d['value']
                }
        for k in issues_percentages:
            issues_percentages[k]['percentage'] = round(issues_percentages[k]['count'] * 100 / total_issues)
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
        administrative_level_docs = eadl_db.get_query_result(selector)
        for doc in administrative_level_docs:
            d = issues_percentages[doc['administrative_id']]
            d['name'] = doc['name']
            d['latitude'] = doc['latitude']
            d['longitude'] = doc['longitude']

        return self.render_to_json_response(issues_percentages)
