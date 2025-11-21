from datetime import datetime, timedelta

import cryptocode
from celery import shared_task
from celery.schedules import crontab
from django.conf import settings
from django.core.management import call_command
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from twilio.base.exceptions import TwilioRestException

from authentication.models import Cdata
from dashboard.constants import MONTHLY_CHOICE, QUARTERLY_CHOICE, WEEKLY_CHOICE
from grm.celery_app import app
from grm.constants import (
    ACCEPTED_CHOICE,
    ALERT_CHOICE,
    CLOSED_CHOICE,
    EMAIL_CHOICE,
    PHONE_CHOICE,
    REJECTED_CHOICE,
)
from grm.utils import normalize_phone_number
from issues.models import Comment, Issue
from mail_client import send_mail_notification
from sms_client import send_sms

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


@app.task
def check_issues():
    """
    Check the issues without internal_code, citizen information anonymization
    or assignee, and try to set a value for these fields
    """

    issues = Issue.objects.filter(
        Q(confirmed=True)
        & (
            Q(internal_code_in=[None, ""])
            | ~Q(citizen_in=[None, ""])
            | ~Q(contact_information__in=[None, "", "*"])
            | Q(assignee_in=[None, ""])
        )
    ).select_related('administrative_region', 'category')
    result = {
        "errors": [],
        "internal_code_updated": [],
        "anonymized_data": [],
        "assignee_updated": [],
    }
    updated_issues = 0
    for issue in issues:
        internal_code_updated = False
        anonymized_data = False
        assignee_updated = False

        # set internal_code if needed
        if not issue.internal_code:
            issue.internal_code = issue.get_internal_code()
            internal_code_updated = True
            result["internal_code_updated"].append(issue.id)

        # anonimyzed when indicated
        contact_information = issue.contact_information
        citizen = issue.citizen
        if citizen and citizen.name != "*" or (contact_information and contact_information != "*"):
            try:
                issue.anonymize_issue_data()
                anonymized_data = True
                result["anonymized_data"].append(issue.id)
            except Exception:
                error = f"Error trying to anonymize issue document with id {issue.id}"
                result["errors"].append(error)

        # set assignee if not define yet
        if not issue.assignee:
            try:
                assignee = issue.get_assignee()
                issue.assignee = assignee
                if assignee:
                    assignee_updated = True
                    result["assignee_updated"].append(issue.id)

                    # Add comment to the issue
                    Comment.objects.create(
                        user=None,  # take None like user system
                        comment=_("The issue has been assigned to %s.") % assignee.name,
                        issue=issue,
                    )
            except Exception:
                error = f"Error trying to set assignee for issue document with id {issue.id}"
                result["errors"].append(error)

        if internal_code_updated or anonymized_data or assignee_updated:
            issue.save()
            updated_issues += 1

    result["updated_issues"] = updated_issues
    return result


@app.task
def escalate_issues():
    issues = Issue.objects.filter(confirmed=True, escalate_flag=True, assignee__isnull=False)
    result = {
        "errors": [],
        "issues_updated": [],
        "scale_is_not_available": [],
    }
    updated_issues = 0
    for issue in issues:
        issues_updated = False
        assignee = issue.get_assignee_to_escalate(issue.administrative_region)
        if assignee:
            issue.assignee = assignee
            issue.escalate_flag = False
            result["issues_updated"].append(issue.id)
            issues_updated = True
        else:
            result["scale_is_not_available"].append(issue.id)

        if issues_updated:
            issue.save()
            updated_issues += 1

    result["updated_issues"] = updated_issues
    return result


@app.task
def escalate_old_issues():
    """
    Browse confirmed issues. If an issue is not closed (not status.final_status)
    and was created or last escalated more than 3.5 days ago, it is marked for escalation
    by adding `escalate_flag: True` and updating `escalated_date`.
    Additionally, a comment is added to the issue history to document the escalation.
    """

    issues = Issue.objects.filter(confirmed=True)
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=3, hours=12)

    updated_issues = 0
    errors = []

    for issue in issues:
        # Check if the issue is already closed
        if not issue.status.final_status:

            # Retrieve the issue creation date
            created_date = issue.created_date

            # Retrieve the last escalation date, if any
            escalated_date = issue.escalated_date

            # Determine if the issue should be escalated
            should_escalate = False
            if escalated_date:  # Issue has been escalated before
                if escalated_date < threshold:
                    should_escalate = True
            else:  # First escalation
                if created_date < threshold:
                    should_escalate = True

            if should_escalate:
                issue.escalated_date = now
                issue.escalate_flag = True

                Comment.objects.create(
                    user=None,  # take None like user system
                    comment=_("The complaint has been escalated automatically because the processing time has passed."),
                    issue=issue,
                )

                issue.save()
                updated_issues += 1

    return {"updated_issues": updated_issues, "errors": errors}


@app.task
def reassign_issues_to_appeal():
    issues = Issue.objects.filter(confirmed=True, appeal_status=True).select_related(
        'category__assigned_appeal_department__department__head'
    )
    result = {
        "errors": [],
        "issues_updated": [],
        "appeal_is_not_available": [],
    }
    updated_issues = 0
    for issue in issues:
        try:
            assignee = issue.category.assigned_appeal_department.department.head
            issue.assignee = assignee
            if assignee:
                issue.appeal_status = False
                result["issues_updated"].append(issue.id)
                issue.save()
                updated_issues += 1
            else:
                result["appeal_is_not_available"].append(issue.id)
        except Exception:
            result["appeal_is_not_available"].append(issue.id)

    result["updated_issues"] = updated_issues
    return result


@app.task
def send_sms_message():
    messages = {
        "accepted_alert_message": _("Your issue submitted has been accepted into the system with the tracking code %s"),
        "rejected_alert_message": _("Your issue %s(tracking_code)s has been rejected with the following response: %s"),
        "closed_alert_message": _("Your issue %s has been resolved with the following response: %s"),
    }
    issues = Issue.objects.filter(
        confirmed=True,
        assigned__isnull=False,
        contact_medium=ALERT_CHOICE,
        contact_method=PHONE_CHOICE,
        alert_message_status="",
    ).exclude(Q(contact_information="") | Q(tracking_code=""))

    result = {"errors": [], "notified_issues": [], "updated_issues": 0}
    updated_issues = 0
    for issue in issues:
        notified_issues = False
        status = issue.status
        tracking_code = issue.tracking_code
        phone = issue.contact_information
        if phone:
            if phone == "*":
                contact = Cdata.objects.filter(key=issue.id).first()
                phone = cryptocode.decrypt(contact.data, issue.id) if contact else None

            phone = normalize_phone_number(phone)
            no_alert = not issue.alert_message_status or issue.alert_message_status != ACCEPTED_CHOICE
            if no_alert and status.open_status:
                msg = messages["accepted_alert_message"] % tracking_code
                try:
                    send_sms(to=phone, body=msg)
                    notified_issues = True
                    issue.alert_message_status = ACCEPTED_CHOICE
                except TwilioRestException as e:
                    result["errors"].append(e.msg)

            no_alert = not issue.alert_message_status or issue.alert_message_status != REJECTED_CHOICE
            if no_alert and status.rejected_status:
                msg = messages["rejected_alert_message"] % (tracking_code, issue.reject_reason)
                try:
                    send_sms(to=phone, body=msg)
                    notified_issues = True
                    issue.alert_message_status = REJECTED_CHOICE
                except TwilioRestException as e:
                    result["errors"].append(e.msg)

            no_alert = not issue.alert_message_status or issue.alert_message_status != CLOSED_CHOICE
            if no_alert and status.final_status:
                msg = messages["closed_alert_message"] % (tracking_code, issue.research_result)
                try:
                    send_sms(to=phone, body=msg)
                    notified_issues = True
                    issue.alert_message_status = CLOSED_CHOICE
                except TwilioRestException as e:
                    result["errors"].append(e.msg)

            if notified_issues:
                issue.save()
                updated_issues += 1

    result["updated_issues"] = updated_issues
    return result


@app.task
def send_mail_message():
    messages = {
        "accepted_alert_message": _("Your issue submitted has been accepted into the system with the tracking code %s"),
        "rejected_alert_message": _("Your issue %s has been rejected with the following response: %s"),
        "closed_alert_message": _("Your issue %s has been resolved with the following response: %s"),
    }
    issues = Issue.objects.filter(
        confirmed=True,
        assigned__isnull=False,
        contact_medium=ALERT_CHOICE,
        contact_method=EMAIL_CHOICE,
        alert_message_status="",
    ).exclude(Q(contact_information="") | Q(tracking_code=""))

    result = {"errors": [], "notified_issues": [], "updated_issues": 0}
    updated_issues = 0
    for issue in issues:
        notified_issues = False
        status = issue.status
        tracking_code = issue.tracking_code
        recipient = issue.contact_information

        if recipient == "*":
            contact = Cdata.objects.get(key=issue.id) if Cdata.objects.filter(key=issue.id).exists() else None
            recipient = cryptocode.decrypt(contact.data, issue.id) if contact else None

        no_alert = not issue.alert_message_status or issue.alert_message_status != ACCEPTED_CHOICE
        if no_alert and status.open_status:
            msg = messages["accepted_alert_message"] % tracking_code
            try:
                subject = "open_status"
                send_mail_notification(subject, msg, recipient)
                notified_issues = True
                issue.alert_message_status = ACCEPTED_CHOICE
            except Exception as e:
                result["errors"].append(str(e))

        no_alert = not issue.alert_message_status or issue.alert_message_status != REJECTED_CHOICE
        if no_alert and status.rejected_status:
            msg = messages["rejected_alert_message"] % (tracking_code, issue.reject_reason)
            try:
                subject = "rejected_status"
                send_mail_notification(subject, msg, recipient)
                notified_issues = True
                issue.alert_message_status = REJECTED_CHOICE
            except Exception as e:
                result["errors"].append(str(e))

        no_alert = not issue.alert_message_status or issue.alert_message_status != CLOSED_CHOICE
        if no_alert and status.final_status:
            msg = messages["closed_alert_message"] % (tracking_code, issue.research_result)
            try:
                subject = "final_status"
                send_mail_notification(subject, msg, recipient)
                notified_issues = True
                issue.alert_message_status = CLOSED_CHOICE
            except Exception as e:
                result["errors"].append(str(e))

        if notified_issues:
            issue.save()
            updated_issues += 1

    result["updated_issues"] = updated_issues
    return result


# test tasks
@app.task
def task_one():
    print(" task one called and worker is running good")
    return "success"


@shared_task
def task_two(x, y):
    print(f" task two called with the arguments {x} and {y}. Worker is running good")
    return x + y


@shared_task
def update_performance_metrics(
    periods=None,
    create_global=False,
    create_regions=True,
    create_categories=False,
    create_region_category=False,
    limit_regions=0,
    offset_regions=0,
    limit_categories=0,
    offset_categories=0,
    batch_size=50,
    no_progress=True,
    dry_run=False,
):
    """
    Wrapper task that calls the management command `populate_performance_metrics`.
    Arguments mirror the command flags; pass them as kwargs when calling the task.

    Examples:
      # Full update (may be heavy)
      update_performance_metrics.delay(periods=['7d','30d','90d'], create_global=True, create_regions=True, create_categories=True, create_region_category=False)

      # Sharded update for worker 1
      update_performance_metrics.delay(create_regions=True, limit_regions=100, offset_regions=0)

      # Sharded update for worker 2
      update_performance_metrics.delay(create_regions=True, limit_regions=100, offset_regions=100)
    """
    periods = periods or [WEEKLY_CHOICE, MONTHLY_CHOICE, QUARTERLY_CHOICE]

    cmd_args = []
    for p in periods:
        cmd_args.extend(['--periods', p])

    if create_global:
        cmd_args.append('--create-global')
    if create_regions:
        cmd_args.append('--create-regions')
    if create_categories:
        cmd_args.append('--create-categories')
    if create_region_category:
        cmd_args.append('--create-region-category')

    if limit_regions:
        cmd_args.extend(['--limit-regions', str(limit_regions)])
    if offset_regions:
        cmd_args.extend(['--offset-regions', str(offset_regions)])
    if limit_categories:
        cmd_args.extend(['--limit-categories', str(limit_categories)])
    if offset_categories:
        cmd_args.extend(['--offset-categories', str(offset_categories)])

    if batch_size and int(batch_size) != 50:
        cmd_args.extend(['--batch-size', str(batch_size)])
    if no_progress:
        cmd_args.append('--no-progress')
    if dry_run:
        cmd_args.append('--dry-run')

    start = timezone.now()
    try:
        # call_command handles management command invocation in-process
        call_command('populate_performance_metrics', *cmd_args)
    except Exception:
        # Re-raise or fail the task depending on your retry policy; here we mark as failure.
        raise

    elapsed = timezone.now() - start
    return {
        'status': 'ok',
        'started_at': start.isoformat(),
        'elapsed_seconds': elapsed.total_seconds(),
    }


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Calls check_issues() every 5 minutes.
    sender.add_periodic_task(300, check_issues.s(), name="check issues every 5 minutes")

    # Calls escalate_issues() every 5 minutes.
    sender.add_periodic_task(300, escalate_issues.s(), name="escalate issues every 5 minutes")

    # Calls send_sms_message() every 5 minutes.
    sender.add_periodic_task(300, send_sms_message.s(), name="send sms every 5 minutes")

    # Calls send_mail_message() every 5 minutes.
    sender.add_periodic_task(300, send_mail_message.s(), name="send mail every 5 minutes")

    # Calls escalate_old_issues() every day
    sender.add_periodic_task(86400, escalate_old_issues.s(), name="escalate old issues every day")

    # Calls reassign_issues_to_appeal() every hour.
    sender.add_periodic_task(3600, reassign_issues_to_appeal.s(), name="reassign issues to appeal every hour")

    # === Frequent small-window updates (7d) every 15 minutes, sharded ===
    # Now that we process ancestors, the regions set grows. Use smaller shards.
    # Example: 20 shards, each handles 50 regions (20 * 50 = 1000 regions covered)
    shards_7d = 20
    limit_per_shard = 50
    for i in range(shards_7d):
        sender.add_periodic_task(
            900,  # 15 minutes
            update_performance_metrics.s(
                periods=[WEEKLY_CHOICE],
                create_global=True,
                create_regions=True,
                create_categories=True,
                create_region_category=False,
                limit_regions=limit_per_shard,
                offset_regions=i * limit_per_shard,
                no_progress=True,
            ),
            name=f"update metrics 7d shard {i}",
        )

    # === Medium-window updates (30d) every hour, fewer shards but still safe ===
    shards_30d = 8
    limit_30 = 125  # approx 1000 / 8
    for i in range(shards_30d):
        sender.add_periodic_task(
            3600,  # every hour
            update_performance_metrics.s(
                periods=[MONTHLY_CHOICE],
                create_global=True,
                create_regions=True,
                create_categories=True,
                create_region_category=False,
                limit_regions=limit_30,
                offset_regions=i * limit_30,
                no_progress=True,
            ),
            name=f"update metrics 30d shard {i}",
        )

    # === Long-window updates (90d) daily ===
    # Daily recalculation can be heavier; run with fewer shards or single run.
    # If you expect >2000 regions+ancestors, consider 2 shards instead.
    sender.add_periodic_task(
        crontab(hour=2, minute=30),
        update_performance_metrics.s(
            periods=[QUARTERLY_CHOICE],
            create_global=True,
            create_regions=True,
            create_categories=True,
            create_region_category=False,
            no_progress=True,
        ),
        name="update metrics 90d daily",
    )
