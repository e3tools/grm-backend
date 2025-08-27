from datetime import datetime, timedelta, timezone

import cryptocode
from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils.translation import gettext as _
from twilio.base.exceptions import TwilioRestException

from authentication.models import (
    Cdata,
    anonymize_issue_data,
    get_assignee,
    get_assignee_to_escalate,
)
from dashboard.grm.constants import (
    CHOICE_ACCEPTED,
    CHOICE_ALERT,
    CHOICE_CLOSED,
    CHOICE_EMAIL,
    CHOICE_PHONE,
    CHOICE_REJECTED,
)
from grm.celery_app import app
from grm.utils import normalize_phone_number
from issues.models import Comment, Issue
from mail_client import send_mail_notification
from sms_client import send_sms

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


@app.task
def check_issues():
    """
    Check the issues without 'auto_increment_id', 'internal_code' or 'assignee', and try to set a value for these fields
    """

    issues = Issue.objects.filter(
        Q(confirmed=True)
        & (
            ~Q(internal_code_in=[None, ""])
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
                anonymize_issue_data(issue)
                anonymized_data = True
                result["anonymized_data"].append(issue.id)
            except Exception:
                error = f"Error trying to anonymize issue document with id {issue.id}"
                result["errors"].append(error)

        # set assignee if not define yet
        if not issue.assignee:
            try:
                adm_lvl_id = issue.issue_location.id
                assignee = get_assignee(issue, adm_lvl_id)
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
        department_id = issue.assignee.governmentworker.department
        region_id = issue.administrative_region.id
        assignee = get_assignee_to_escalate(department_id, region_id)
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
    Browse confirmed issues. If an issue is not closed (status.id != 4 or status.name != 'Terminée')
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
        # and skip closed issues
        status = issue.status
        if status.id == 4 and status.name == "Terminée":
            continue

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
def send_sms_message():
    messages = {
        "accepted_alert_message": _("Your issue submitted has been accepted into the system with the tracking code %s"),
        "rejected_alert_message": _("Your issue %s(tracking_code)s has been rejected with the following response: %s"),
        "closed_alert_message": _("Your issue %s has been resolved with the following response: %s"),
    }
    issues = Issue.objects.filter(
        confirmed=True,
        assigned__isnull=False,
        contact_medium=CHOICE_ALERT,
        contact_method=CHOICE_PHONE,
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
            no_alert = not issue.alert_message_status or issue.alert_message_status != CHOICE_ACCEPTED
            if no_alert and status.open_status:
                msg = messages["accepted_alert_message"] % tracking_code
                try:
                    send_sms(to=phone, body=msg)
                    notified_issues = True
                    issue.alert_message_status = CHOICE_ACCEPTED
                except TwilioRestException as e:
                    result["errors"].append(e.msg)

            no_alert = not issue.alert_message_status or issue.alert_message_status != CHOICE_REJECTED
            if no_alert and status.rejected_status:
                msg = messages["rejected_alert_message"] % (tracking_code, issue.reject_reason)
                try:
                    send_sms(to=phone, body=msg)
                    notified_issues = True
                    issue.alert_message_status = CHOICE_REJECTED
                except TwilioRestException as e:
                    result["errors"].append(e.msg)

            no_alert = not issue.alert_message_status or issue.alert_message_status != CHOICE_CLOSED
            if no_alert and status.final_status:
                msg = messages["closed_alert_message"] % (tracking_code, issue.research_result)
                try:
                    send_sms(to=phone, body=msg)
                    notified_issues = True
                    issue.alert_message_status = CHOICE_CLOSED
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
        contact_medium=CHOICE_ALERT,
        contact_method=CHOICE_EMAIL,
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

        no_alert = not issue.alert_message_status or issue.alert_message_status != CHOICE_ACCEPTED
        if no_alert and status.open_status:
            msg = messages["accepted_alert_message"] % tracking_code
            try:
                subject = "open_status"
                send_mail_notification(subject, msg, recipient)
                notified_issues = True
                issue.alert_message_status = CHOICE_ACCEPTED
            except Exception as e:
                result["errors"].append(str(e))

        no_alert = not issue.alert_message_status or issue.alert_message_status != CHOICE_REJECTED
        if no_alert and status.rejected_status:
            msg = messages["rejected_alert_message"] % (tracking_code, issue.reject_reason)
            try:
                subject = "rejected_status"
                send_mail_notification(subject, msg, recipient)
                notified_issues = True
                issue.alert_message_status = CHOICE_REJECTED
            except Exception as e:
                result["errors"].append(str(e))

        no_alert = not issue.alert_message_status or issue.alert_message_status != CHOICE_CLOSED
        if no_alert and status.final_status:
            msg = messages["closed_alert_message"] % (tracking_code, issue.research_result)
            try:
                subject = "final_status"
                send_mail_notification(subject, msg, recipient)
                notified_issues = True
                issue.alert_message_status = CHOICE_CLOSED
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
