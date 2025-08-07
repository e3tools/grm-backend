from django.conf import settings
from django.utils.translation import gettext as _
from twilio.base.exceptions import TwilioRestException

from authentication.models import (
    anonymize_issue_data,
    get_assignee,
    get_assignee_to_escalate,
    Cdata,
)
from client import get_db
from dashboard.grm.constants import CHOICE_CONTACT, CHOICE_EMAIL, CHOICE_PHONE
from grm.celery_app import app
from grm.utils import get_auto_increment_id, normalize_phone_number
from sms_client import send_sms
from mail_client import send_mail_notification
import cryptocode
from datetime import datetime
from celery import shared_task
from datetime import datetime, timedelta, timezone

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


@app.task
def check_issues():
    """
    Check the issues without 'auto_increment_id', 'internal_code' or 'assignee', and try to set a value for these fields
    """
    grm_db = get_db(COUCHDB_GRM_DATABASE)
    selector = {
        "type": "issue",
        "confirmed": True,
        "$or": [
            {"auto_increment_id": {"$in": [None, ""]}},
            {"auto_increment_id": {"$exists": False}},
            {"internal_code": {"$in": [None, ""]}},
            {"internal_code": {"$exists": False}},
            {"citizen": {"$nin": [None, "", "*"]}},
            {"contact_information.contact": {"$nin": [None, "", "*"]}},
            {"assignee": {"$in": [None, ""]}},
            {"assignee": {"$exists": False}},
        ],
    }

    issues = grm_db.get_query_result(selector)
    result = {
        "errors": [],
        "auto_increment_id_updated": [],
        "internal_code_updated": [],
        "anonymized_data": [],
        "assignee_updated": [],
    }
    updated_issues = 0
    for issue in issues:
        auto_increment_id_updated = False
        internal_code_updated = False
        anonymized_data = False
        assignee_updated = False

        issue_id = issue["_id"]
        try:
            issue_doc = grm_db[issue_id]
        except Exception:
            error = f"Error trying to get issue document with id {issue_id}"
            result["errors"].append(error)
            return result

        # set auto_increment_id if needed
        if "auto_increment_id" not in issue_doc or not issue_doc["auto_increment_id"]:
            try:
                auto_increment_id = get_auto_increment_id(grm_db)
                issue_doc["auto_increment_id"] = auto_increment_id
                auto_increment_id_updated = True
                result["auto_increment_id_updated"].append(issue_id)
            except Exception:
                error = f"Error trying to set auto_increment_id of issue document with id {issue_id}"
                result["errors"].append(error)
        else:
            auto_increment_id = issue_doc["auto_increment_id"]

        try:
            category_id = issue_doc["category"]["id"]
            doc_category = grm_db.get_query_result(
                {"id": category_id, "type": "issue_category"}
            )[0][0]
        except Exception:
            error = (
                f"Error trying to get the category of issue document with id {issue_id}"
            )
            result["errors"].append(error)
            continue

        # set internal_code if needed
        if "internal_code" not in issue_doc or not issue_doc["internal_code"]:
            try:
                administrative_id = issue_doc["administrative_region"][
                    "administrative_id"
                ]
                issue_doc["internal_code"] = (
                    f'{doc_category["abbreviation"]}-{administrative_id}-{auto_increment_id}'
                )
                internal_code_updated = True
                result["internal_code_updated"].append(issue_id)
            except Exception:
                error = f"Error trying to set internal_code for issue document with id {issue_id}"
                result["errors"].append(error)

        # anonimyzed when indicated
        contact_information = issue_doc["contact_information"]
        if issue_doc["citizen"] != "*" or (
            contact_information and contact_information["contact"] != "*"
        ):
            try:
                anonymize_issue_data(issue_doc)
                anonymized_data = True
                result["anonymized_data"].append(issue_id)
            except Exception:
                error = f"Error trying to anonymize issue document with id {issue_id}"
                result["errors"].append(error)

        # set assignee if not define yet
        if "assignee" not in issue_doc or not issue_doc["assignee"]:
            try:
                eadl_db = get_db()
                adm_lvl_id = issue_doc["location_info"]["issue_location"][
                    "administrative_id"
                ]
                assignee = get_assignee(
                    grm_db, eadl_db, issue_doc, adm_lvl_id, result["errors"]
                )
                issue_doc["assignee"] = assignee
                if assignee:
                    assignee_updated = True
                    result["assignee_updated"].append(issue_id)

                    # Add comment to the issue
                    comments = (
                        issue_doc["comments"] if "comments" in issue_doc else list()
                    )
                    comment = _("The issue has been assigned to %s.") % assignee["name"]
                    comment_obj = {
                        "name": "eMGP",
                        "id": f"emgp-2024-BJ",
                        "comment": f"{comment}",
                        "due_at": f"{datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')}",
                    }
                    comments.insert(0, comment_obj)
                    issue_doc["comments"] = comments
            except Exception:
                error = f"Error trying to set assignee for issue document with id {issue_id}"
                result["errors"].append(error)

        if (
            auto_increment_id_updated
            or internal_code_updated
            or anonymized_data
            or assignee_updated
        ):
            issue_doc.save()
            updated_issues += 1
            grm_db = get_db(COUCHDB_GRM_DATABASE)  # refresh db

    result["updated_issues"] = updated_issues
    return result


@app.task
def escalate_issues():
    grm_db = get_db(COUCHDB_GRM_DATABASE)
    eadl_db = get_db()
    selector = {
        "type": "issue",
        "confirmed": True,
        "escalate_flag": True,
        "assignee": {"$ne": ""},
    }

    issues = grm_db.get_query_result(selector)
    result = {
        "errors": [],
        "issues_updated": [],
        "scale_is_not_available": [],
    }
    updated_issues = 0
    for issue in issues:
        issues_updated = False
        issue_id = issue["_id"]
        try:
            issue_doc = grm_db[issue_id]
        except Exception:
            error = f"Error trying to get issue document with id {issue_id}"
            result["errors"].append(error)
            continue
        try:
            old_assignee_id = issue_doc["assignee"]["id"]
            escalate_old_issues_doc = eadl_db.get_query_result(
                {"_id": old_assignee_id, "type": "adl"}
            )[0][0]
            department_id = escalate_old_issues_doc["department"]
            administrative_id = issue_doc["administrative_region"]["administrative_id"]
            assignee = get_assignee_to_escalate(
                eadl_db, department_id, administrative_id
            )
            if assignee:
                issue_doc["assignee"] = assignee
                issue_doc["escalate_flag"] = False
                result["issues_updated"].append(issue_id)
                issues_updated = True
            else:
                result["scale_is_not_available"].append(issue_id)

        except Exception:
            error = f"Error trying to escalate for issue document with id {issue_id}"
            result["errors"].append(error)
        if issues_updated:
            issue_doc.save()
            updated_issues += 1
            grm_db = get_db(COUCHDB_GRM_DATABASE)  # refresh db

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
    grm_db = get_db(COUCHDB_GRM_DATABASE)

    selector = {"type": "issue", "confirmed": True}
    issues = grm_db.get_query_result(selector)

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=3, hours=12)

    updated_issues = 0
    errors = []

    for issue in issues:
        issue_id = issue["_id"]
        try:
            issue_doc = grm_db[issue_id]
        except Exception:
            errors.append(f"Error retrieving issue {issue_id}")
            continue

        # Check if the issue is already closed
        # and skip closed issues
        status = issue_doc.get("status", {})
        if status.get("id") == 4 and status.get("name") == "Terminée":
            continue

        # Retrieve the issue creation date
        created_date_str = issue_doc.get("created_date")
        if not created_date_str:
            errors.append(f"Issue {issue_id} has no valid created_date.")
            continue

        try:
            created_date = datetime.strptime(
                created_date_str, "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            errors.append(
                f"Issue {issue_id} has a poorly formatted creation date: {created_date_str}"
            )
            continue

        # Retrieve the last escalation date, if any
        escalated_date_str = issue_doc.get("escalated_date")
        escalated_date = None

        if escalated_date_str:
            try:
                escalated_date = datetime.strptime(
                    escalated_date_str, "%Y-%m-%dT%H:%M:%S.%fZ"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                errors.append(
                    f"Issue {issue_id} has a poorly formatted escalated_date: {escalated_date_str}"
                )
                continue

        # Determine if the issue should be escalated
        should_escalate = False
        if escalated_date:  # Issue has been escalated before
            if escalated_date < threshold:
                should_escalate = True
        else:  # First escalation
            if created_date < threshold:
                should_escalate = True

        if should_escalate:
            issue_doc["escalated_date"] = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            issue_doc["escalate_flag"] = True

            # Add an escalation comment
            comments = issue_doc.get("comments", [])
            last_comment = (
                comments[-1] if comments else {"name": "System", "id": "system"}
            )

            escalation_comment = {
                "name": "Système eMGP",
                "id": last_comment["id"],
                "comment": "La plainte a été escaladée/remontée automatiquement car le délai de traitement est dépassé.",
                "due_at": issue_doc["escalated_date"],
            }
            comments.append(escalation_comment)
            issue_doc["comments"] = comments

            try:
                issue_doc.save()
                updated_issues += 1
            except Exception:
                errors.append(f"Error updating issue {issue_id}")

    return {"updated_issues": updated_issues, "errors": errors}


@app.task
def send_sms_message():
    messages = {
        "accepted_alert_message": _(
            "Your issue submitted has been accepted into the system with the tracking code %s"
        ),
        "rejected_alert_message": _(
            "Your issue %s(tracking_code)s has been rejected with the following response: %s"
        ),
        "closed_alert_message": _(
            "Your issue %s has been resolved with the following response: %s"
        ),
    }
    grm_db = get_db(COUCHDB_GRM_DATABASE)
    selector = {
        "type": "issue",
        "confirmed": True,
        "assignee": {"$ne": ""},
        "tracking_code": {"$ne": ""},
        "contact_medium": {"$in": [f"{CHOICE_CONTACT}", "channel-alert"]},
        "contact_information.type": {"$in": [f"{CHOICE_PHONE}", "phone_number"]},
        "contact_information.contact": {"$ne": ""},
        "$or": [
            {
                "accepted_alert_message": False,
            },
            {"accepted_alert_message": {"$exists": False}},
            {
                "rejected_alert_message": False,
            },
            {"rejected_alert_message": {"$exists": False}},
            {
                "closed_alert_message": False,
            },
            {"closed_alert_message": {"$exists": False}},
        ],
    }

    issues = grm_db.get_query_result(selector)
    result = {"errors": [], "notified_issues": [], "updated_issues": 0}
    updated_issues = 0
    for issue in issues:
        notified_issues = False
        issue_id = issue["_id"]
        try:
            issue_doc = grm_db[issue_id]
        except Exception:
            error = f"Error trying to get issue document with id {issue_id}"
            result["errors"].append(error)
            continue
        try:
            status_id = issue_doc["status"]["id"]
            doc_status = grm_db.get_query_result(
                {"id": status_id, "type": "issue_status"}
            )[0][0]
        except Exception:
            error = f"Error trying to get issue_status document with id {status_id}"
            result["errors"].append(error)
            continue

        tracking_code = issue_doc["tracking_code"]
        phone = issue_doc["contact_information"]["contact"]
        if phone:
            if phone == "*":
                contact = (
                    Cdata.objects.get(key=issue_id)
                    if Cdata.objects.filter(key=issue_id).exists()
                    else None
                )
                phone = cryptocode.decrypt(contact.data, issue_id) if contact else None

            phone = normalize_phone_number(phone)
            no_alert = (
                "accepted_alert_message" not in issue_doc
                or not issue_doc["accepted_alert_message"]
            )
            if no_alert and doc_status["open_status"]:
                msg = messages["accepted_alert_message"] % (tracking_code)
                try:
                    send_sms(to=phone, body=msg)
                    notified_issues = True
                    issue_doc["accepted_alert_message"] = True
                except TwilioRestException as e:
                    result["errors"].append(e.msg)

            no_alert = (
                "rejected_alert_message" not in issue_doc
                or not issue_doc["rejected_alert_message"]
            )
            if no_alert and doc_status["rejected_status"]:
                reason = (
                    issue_doc["rejected_alert_message"]
                    if "rejected_alert_message" in issue_doc
                    else ""
                )
                msg = messages["rejected_alert_message"] % (tracking_code, reason)
                try:
                    send_sms(to=phone, body=msg)
                    notified_issues = True
                    issue_doc["rejected_alert_message"] = True
                except TwilioRestException as e:
                    result["errors"].append(e.msg)

            no_alert = (
                "closed_alert_message" not in issue_doc
                or not issue_doc["closed_alert_message"]
            )
            if no_alert and doc_status["final_status"]:
                resolution = (
                    issue_doc["research_result"]
                    if "research_result" in issue_doc
                    else ""
                )
                msg = messages["closed_alert_message"] % (tracking_code, resolution)
                try:
                    send_sms(to=phone, body=msg)
                    notified_issues = True
                    issue_doc["closed_alert_message"] = True
                except TwilioRestException as e:
                    result["errors"].append(e.msg)

            if notified_issues:
                issue_doc.save()
                updated_issues += 1
                grm_db = get_db(COUCHDB_GRM_DATABASE)  # refresh db

    result["updated_issues"] = updated_issues
    return result


@app.task
def send_mail_message():
    messages = {
        "accepted_alert_message": _(
            "Your issue submitted has been accepted into the system with the tracking code %s"
        ),
        "rejected_alert_message": _(
            "Your issue %s has been rejected with the following response: %s"
        ),
        "closed_alert_message": _(
            "Your issue %s has been resolved with the following response: %s"
        ),
    }
    grm_db = get_db(COUCHDB_GRM_DATABASE)
    selector = {
        "type": "issue",
        "confirmed": True,
        "assignee": {"$ne": ""},
        "tracking_code": {"$ne": ""},
        "contact_medium": {"$in": [f"{CHOICE_CONTACT}", "channel-alert"]},
        "contact_information.type": {"$in": [f"{CHOICE_EMAIL}", "email"]},
        "contact_information.contact": {"$ne": ""},
        "$or": [
            {"accepted_alert_message": False},
            {"accepted_alert_message": {"$exists": False}},
            {"rejected_alert_message": False},
            {"rejected_alert_message": {"$exists": False}},
            {"closed_alert_message": False},
            {"closed_alert_message": {"$exists": False}},
        ],
    }

    issues = grm_db.get_query_result(selector)
    result = {"errors": [], "notified_issues": [], "updated_issues": 0}
    updated_issues = 0
    for issue in issues:
        notified_issues = False
        issue_id = issue["_id"]
        try:
            issue_doc = grm_db[issue_id]
        except Exception:
            error = f"Error trying to get issue document with id {issue_id}"
            result["errors"].append(error)
            continue
        try:
            status_id = issue_doc["status"]["id"]
            doc_status = grm_db.get_query_result(
                {"id": status_id, "type": "issue_status"}
            )[0][0]
        except Exception:
            error = f"Error trying to get issue_status document with id {status_id}"
            result["errors"].append(error)
            continue

        tracking_code = issue_doc["tracking_code"]
        recipient = issue_doc["contact_information"]["contact"]

        if recipient == "*":
            contact = (
                Cdata.objects.get(key=issue_id)
                if Cdata.objects.filter(key=issue_id).exists()
                else None
            )
            recipient = cryptocode.decrypt(contact.data, issue_id) if contact else None

        no_alert = (
            "accepted_alert_message" not in issue_doc
            or not issue_doc["accepted_alert_message"]
        )
        if no_alert and doc_status["open_status"]:
            msg = messages["accepted_alert_message"] % (tracking_code)
            try:
                subject = "open_status"
                send_mail_notification(subject, msg, recipient)
                notified_issues = True
                issue_doc["accepted_alert_message"] = True
            except Exception as e:
                result["errors"].append(e.msg)

        no_alert = (
            "rejected_alert_message" not in issue_doc
            or not issue_doc["rejected_alert_message"]
        )
        if no_alert and doc_status["rejected_status"]:
            reason = (
                issue_doc["rejected_alert_message"]
                if "rejected_alert_message" in issue_doc
                else ""
            )
            msg = messages["rejected_alert_message"] % (tracking_code, reason)
            try:
                subject = "rejected_status"
                send_mail_notification(subject, msg, recipient)
                notified_issues = True
                issue_doc["rejected_alert_message"] = True
            except Exception as e:
                result["errors"].append(e.msg)

        no_alert = (
            "closed_alert_message" not in issue_doc
            or not issue_doc["closed_alert_message"]
        )
        if no_alert and doc_status["final_status"]:
            resolution = (
                issue_doc["research_result"] if "research_result" in issue_doc else ""
            )
            msg = messages["closed_alert_message"] % (tracking_code, resolution)
            try:
                subject = "final_status"
                send_mail_notification(subject, msg, recipient)
                notified_issues = True
                issue_doc["closed_alert_message"] = True
            except Exception as e:
                result["errors"].append(e.msg)

        if notified_issues:
            issue_doc.save()
            updated_issues += 1
            grm_db = get_db(COUCHDB_GRM_DATABASE)  # refresh db

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
    sender.add_periodic_task(
        300, escalate_issues.s(), name="escalate issues every 5 minutes"
    )

    # Calls send_sms_message() every 5 minutes.
    sender.add_periodic_task(300, send_sms_message.s(), name="send sms every 5 minutes")

    # Calls send_mail_message() every 5 minutes.
    sender.add_periodic_task(
        300, send_mail_message.s(), name="send mail every 5 minutes"
    )

    # Calls escalate_old_issues() every day
    sender.add_periodic_task(
        86400, escalate_old_issues.s(), name="escalate old issues every day"
    )
