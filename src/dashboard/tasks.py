from django.conf import settings
from django.utils.translation import gettext as _

from client import get_db
from grm.celery import app
from grm.utils import get_auto_increment_id
from authentication.models import get_assignee, get_assignee_to_escalate
from sms_client import send_sms
from twilio.base.exceptions import TwilioRestException

from dashboard.grm import CHOICE_CONTACT, CHOICE_PHONE
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
            {
                "auto_increment_id": {
                    "$in": [
                        None,
                        ""
                    ]
                }
            },
            {
                "auto_increment_id": {
                    "$exists": False
                }
            },
            {
                "internal_code": {
                    "$in": [
                        None,
                        ""
                    ]
                }
            },
            {
                "internal_code": {
                    "$exists": False
                }
            },
            {
                "assignee": {
                    "$in": [
                        None,
                        ""
                    ]
                }
            },
            {
                "assignee": {
                    "$exists": False
                }
            }
        ]
    }

    issues = grm_db.get_query_result(selector)
    result = {
        'errors': [],
        'auto_increment_id_updated': [],
        'internal_code_updated': [],
        'assignee_updated': [],
    }
    updated_issues = 0
    for issue in issues:
        auto_increment_id_updated = False
        internal_code_updated = False
        assignee_updated = False

        issue_id = issue['_id']
        try:
            issue_doc = grm_db[issue_id]
        except Exception:
            error = f'Error trying to get issue document with id {issue_id}'
            result['errors'].append(error)
            continue

        if 'auto_increment_id' not in issue or not issue['auto_increment_id']:
            try:
                auto_increment_id = get_auto_increment_id(grm_db)
                issue_doc['auto_increment_id'] = auto_increment_id
                auto_increment_id_updated = True
                result['auto_increment_id_updated'].append(issue_id)
            except Exception:
                error = f'Error trying to set auto_increment_id of issue document with id {issue_id}'
                result['errors'].append(error)
        else:
            auto_increment_id = issue_doc['auto_increment_id']

        try:
            category_id = issue_doc['category']['id']
            doc_category = grm_db.get_query_result({
                "id": category_id,
                "type": 'issue_category'
            })[0][0]
        except Exception:
            error = f'Error trying to get the category of issue document with id {issue_id}'
            result['errors'].append(error)
            continue

        if 'internal_code' not in issue or not issue['internal_code']:
            try:
                administrative_id = issue_doc["administrative_region"]["administrative_id"]
                issue_doc['internal_code'] = f'{doc_category["abbreviation"]}-{administrative_id}-{auto_increment_id}'
                internal_code_updated = True
                result['internal_code_updated'].append(issue_id)
            except Exception:
                error = f'Error trying to set internal_code for issue document with id {issue_id}'
                result['errors'].append(error)

        if 'assignee' not in issue or not issue_doc['assignee']:
            try:
                eadl_db = get_db()
                assignee = get_assignee(grm_db, eadl_db, issue_doc, result['errors'])
                issue_doc['assignee'] = assignee
                if assignee:
                    assignee_updated = True
                    result['assignee_updated'].append(issue_id)
            except Exception:
                error = f'Error trying to set assignee for issue document with id {issue_id}'
                result['errors'].append(error)

        if auto_increment_id_updated or internal_code_updated or assignee_updated:
            issue_doc.save()
            updated_issues += 1
            grm_db = get_db(COUCHDB_GRM_DATABASE)  # refresh db

    result['updated_issues'] = updated_issues
    return result


@app.task
def escalate_issues():
    grm_db = get_db(COUCHDB_GRM_DATABASE)
    selector = {
        "type": "issue",
        "confirmed": True,
        "escalate_flag": True,
        "assignee": {"$ne": ""}
    }

    issues = grm_db.get_query_result(selector)
    result = {
        'errors': [],
        'issues_updated': [],
        'scale_is_not_available': [],
    }
    updated_issues = 0
    for issue in issues:
        issues_updated = False
        issue_id = issue['_id']
        try:
            issue_doc = grm_db[issue_id]
        except Exception:
            error = f'Error trying to get issue document with id {issue_id}'
            result['errors'].append(error)
            continue
        try:
            category_id = issue_doc['category']['id']
            doc_category = grm_db.get_query_result({
                "id": category_id,
                "type": 'issue_category'
            })[0][0]
            department_id = doc_category['assigned_department']['id']
            administrative_id = issue_doc['administrative_region']['administrative_id']
            eadl_db = get_db()
            assignee = get_assignee_to_escalate(eadl_db, department_id, administrative_id)
            if assignee:
                issue_doc['assignee'] = assignee
                issue_doc['escalate_flag'] = False
                result['issues_updated'].append(issue_id)
                issues_updated = True
            else:
                result['scale_is_not_available'].append(issue_id)

        except Exception:
            error = f'Error trying to escalate for issue document with id {issue_id}'
            result['errors'].append(error)
        if issues_updated:
            issue_doc.save()
            updated_issues += 1
            grm_db = get_db(COUCHDB_GRM_DATABASE)  # refresh db

    result['updated_issues'] = updated_issues
    return result


@app.task
def send_sms_message():
    messages = {
        'accepted_alert_message': _(
            "Your issue submitted has been accepted into the system with the code %s(tracking_code)s"),
        'rejected_alert_message': _(
            "Your issue %s(tracking_code)s has been rejected with the following response: %s(reason)s"),
        'closed_alert_message': _(
            "Your issue %s(tracking_code)s has been resolved with the following response: %s(resolution)s"),
    }
    grm_db = get_db(COUCHDB_GRM_DATABASE)
    selector = {
        "type": "issue",
        "confirmed": True,
        "assignee": {"$ne": ""},
        "tracking_code": {"$ne": ""},
        "contact_medium": CHOICE_CONTACT,
        "contact_information.type": CHOICE_PHONE,
        "contact_information.contact": {"$ne": ""},
        "$or": [
            {
                "accepted_alert_message": False,
            },
            {
                "accepted_alert_message": {
                    "$exists": False
                }
            },
            {
                "rejected_alert_message": False,
            },
            {
                "rejected_alert_message": {
                    "$exists": False
                }
            },
            {
                "closed_alert_message": False,
            },
            {
                "closed_alert_message": {
                    "$exists": False
                }
            },
        ]
    }

    issues = grm_db.get_query_result(selector)
    result = {
        'errors': [],
        'notified_issues': [],
    }
    updated_issues = 0
    for issue in issues:
        notified_issues = False
        issue_id = issue['_id']
        try:
            issue_doc = grm_db[issue_id]
        except Exception:
            error = f'Error trying to get issue document with id {issue_id}'
            result['errors'].append(error)
            continue
        try:
            status_id = issue_doc['status']['id']
            doc_status = grm_db.get_query_result({
                "id": status_id,
                "type": 'issue_status'
            })[0][0]
        except Exception:
            error = f'Error trying to get issue_status document with id {status_id}'
            result['errors'].append(error)
            continue

        tracking_code = issue_doc['tracking_code']
        phone = issue_doc['contact_information']['contact']

        no_alert = 'accepted_alert_message' not in issue_doc or not issue_doc['accepted_alert_message']
        if no_alert and doc_status['open_status']:
            msg = messages['accepted_alert_message'] % {'tracking_code': tracking_code}
            try:
                send_sms(phone, msg)
                notified_issues = True
                issue_doc['accepted_alert_message'] = True
            except TwilioRestException as e:
                result['errors'].append(e.msg)

        no_alert = 'rejected_alert_message' not in issue_doc or not issue_doc['rejected_alert_message']
        if no_alert and doc_status['rejected_status']:
            msg = messages['rejected_alert_message'] % {
                'tracking_code': tracking_code,
                'reason': issue_doc['rejected_alert_message'] if 'rejected_alert_message' in issue_doc else ''
            }
            try:
                send_sms(phone, msg)
                notified_issues = True
                issue_doc['rejected_alert_message'] = True
            except TwilioRestException as e:
                result['errors'].append(e.msg)

        no_alert = 'closed_alert_message' not in issue_doc or not issue_doc['closed_alert_message']
        if no_alert and doc_status['final_status']:
            msg = messages['closed_alert_message'] % {
                'tracking_code': tracking_code,
                'resolution': issue_doc['research_result'] if 'research_result' in issue_doc else ''
            }
            try:
                send_sms(phone, msg)
                notified_issues = True
                issue_doc['closed_alert_message'] = True
            except TwilioRestException as e:
                result['errors'].append(e.msg)

        if notified_issues:
            issue_doc.save()
            updated_issues += 1
            grm_db = get_db(COUCHDB_GRM_DATABASE)  # refresh db

    result['updated_issues'] = updated_issues
    return result


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Calls check_issues() every 5 minutes.
    sender.add_periodic_task(300, check_issues.s(), name='check issues every 5 minutes')

    # Calls escalate_issues() every 5 minutes.
    sender.add_periodic_task(300, escalate_issues.s(), name='escalate issues every 5 minutes')

    # Calls send_sms_message() every 5 minutes.
    sender.add_periodic_task(300, send_sms_message.s(), name='send sms every 5 minutes')
