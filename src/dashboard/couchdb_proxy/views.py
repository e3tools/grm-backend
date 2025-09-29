from django.conf import settings
from django.views import generic

from client import get_db
from dashboard.mixins import JSONResponseMixin, LoginRequiredAndAJAXRequestMixin

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class StatisticsOfTasksUpdatedByRegionView(LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        eadl_db = get_db()
        administrative_id = self.request.GET.get("administrative_id", None)
        if administrative_id:
            stats = eadl_db.get_view_result("tasks", "updated_by_administrative_region_stats", key=administrative_id)
        else:
            stats = eadl_db.get_view_result("tasks", "updated_by_administrative_region_stats")

        if stats[0]:
            stats = stats[0][0]["value"]
        else:
            stats = {"count": 0}

        return self.render_to_json_response(stats, safe=False)
