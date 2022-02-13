from django.conf import settings

from client import get_db
from grm.celery import app
from grm.utils import get_assignee, get_assignee_to_escalate, get_auto_increment_id

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


@app.task
def check_issues():
    grm_db = get_db(COUCHDB_GRM_DATABASE)
    selector = {
        "type": "issue",
        "confirmed": True,
        "$or": [
            {"auto_increment_id": ""},
            {"assignee": ""}
        ]
    }

    issues = grm_db.get_query_result(selector)
    result = {
        'errors': [],
        'auto_increment_id_updated': [],
        'assignee_updated': [],
    }
    updated_issues = 0
    for issue in issues:
        auto_increment_id_updated = False
        assignee_updated = False
        issue_id = issue['_id']
        try:
            issue_doc = grm_db[issue_id]
        except Exception:
            error = f'Error trying to get issue document with id {issue_id}'
            result['errors'].append(error)
            continue
        if not issue['auto_increment_id']:
            issue_doc['auto_increment_id'] = get_auto_increment_id(grm_db)
            auto_increment_id_updated = True
            result['auto_increment_id_updated'].append(issue_id)
        if not issue_doc['assignee']:
            try:
                category_id = issue_doc['category']['id']
                doc_category = grm_db.get_query_result({
                    "id": category_id,
                    "type": 'issue_category'
                })[0][0]
                assignee = get_assignee(grm_db, doc_category)
                issue_doc['assignee'] = assignee
                if assignee:
                    assignee_updated = True
                    result['assignee_updated'].append(issue_id)
            except Exception:
                error = f'Error trying to get an assignee for issue document with id {issue_id}'
                result['errors'].append(error)
        if auto_increment_id_updated or assignee_updated:
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


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Calls check_issues() every 5 minutes.
    sender.add_periodic_task(300, check_issues.s(), name='check issues every 5 minutes')

    # Calls escalate_issues() every 5 minutes.
    sender.add_periodic_task(300, escalate_issues.s(), name='escalate issues every 5 minutes')
