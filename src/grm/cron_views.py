from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET

from grm.tasks import check_issues


def _is_authorized(request) -> bool:
    """
    Vercel Cron Jobs automatically send:
      Authorization: Bearer <CRON_SECRET>
    when CRON_SECRET is configured in the Vercel project.
    """
    cron_secret = (getattr(settings, "CRON_SECRET", "") or "").strip()
    if not cron_secret:
        return False
    auth = (request.headers.get("Authorization") or "").strip()
    return auth == f"Bearer {cron_secret}"


@require_GET
def cron_check_issues(request):
    if not _is_authorized(request):
        return HttpResponseForbidden("Forbidden")

    # Execute synchronously (no broker required). `check_issues` is a Celery task object.
    result = check_issues.run()
    return JsonResponse(result, safe=False)

