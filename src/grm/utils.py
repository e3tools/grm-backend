from datetime import datetime
from operator import itemgetter

from django.template.defaultfilters import date as _date

from authentication.models import GovernmentWorker


def sort_dictionary_list_by_field(list_to_be_sorted, field, reverse=False):
    return sorted(list_to_be_sorted, key=itemgetter(field), reverse=reverse)


def get_month_range(start, end=datetime.now(), fmt="Y F"):
    start = start.month + 12 * start.year
    end = end.month + 12 * end.year
    months = list()
    for month in range(start - 1, end):
        y, m = divmod(month, 12)
        months.insert(0, (f'{y}-{m+1}', _date(datetime(y, m + 1, 1), fmt)))
    return months


def get_administrative_region_choices(eadl_db, empty_choice=True):
    query_result = eadl_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": None,
        }
    )
    choices = list()
    for i in query_result:
        choices.append((i['administrative_id'], f"{i['name']}"))
    if empty_choice:
        choices = [('', '')] + choices
    return choices


def get_issue_type_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_type'})
    choices = [(i['id'], i['name']) for i in query_result]
    if empty_choice:
        choices = [('', '')] + choices
    return choices


def get_issue_category_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_category'})
    choices = [(i['id'], i['name']) for i in query_result]
    if empty_choice:
        choices = [('', '')] + choices
    return choices


def get_issue_status_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_status'})
    choices = [(i['id'], i['name']) for i in query_result]
    if empty_choice:
        choices = [('', '')] + choices
    return choices


def get_government_worker_choices(empty_choice=True):
    query = GovernmentWorker.objects.select_related('user')
    choices = [(i.user.id, f'{i.user.first_name} {i.user.last_name}') for i in query]
    if empty_choice:
        choices = [('', '')] + choices
    return choices


def get_administrative_region_name(eadl_db, administrative_id):
    not_found_message = f'[Missing region with administrative_id "{administrative_id}"]'
    if not administrative_id:
        return not_found_message

    region_names = []
    has_parent = True

    while has_parent:
        docs = eadl_db.get_query_result({
            "administrative_id": administrative_id,
            "type": 'administrative_level'
        })

        try:
            doc = eadl_db[docs[0][0]['_id']]

            region_names.append(doc['name'])
            administrative_id = doc['parent_id']
            has_parent = administrative_id is not None
        except Exception:
            region_names.append(not_found_message)
            has_parent = False

    return ', '.join(region_names)


def get_base_administrative_id(eadl_db, administrative_id):
    has_parent = True
    while has_parent:
        parent = get_parent_administrative_level(eadl_db, administrative_id)
        if parent:
            administrative_id = parent['administrative_id']
        else:
            has_parent = False

    return administrative_id


def get_child_administrative_levels(eadl_db, parent_id):
    data = eadl_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": parent_id,
        }
    )
    return data[:]


def get_parent_administrative_level(eadl_db, administrative_id):
    parent = None
    docs = eadl_db.get_query_result({
        "administrative_id": administrative_id,
        "type": 'administrative_level'
    })

    try:
        doc = eadl_db[docs[0][0]['_id']]
        if 'parent_id' in doc and doc['parent_id']:
            administrative_id = doc['parent_id']
            docs = eadl_db.get_query_result({
                "administrative_id": administrative_id,
                "type": 'administrative_level'
            })
            parent = eadl_db[docs[0][0]['_id']]
    except Exception:
        pass
    return parent


def get_auto_increment_id(grm_db):
    try:
        max_auto_increment_id = grm_db.get_view_result('issues', 'auto_increment_id_stats')[0][0]['value']['max']
    except Exception:
        max_auto_increment_id = 0
    return max_auto_increment_id + 1


def get_assignee(grm_db, doc_category):

    try:
        department_id = doc_category['assigned_department']['id']
        doc_department = grm_db.get_query_result({
            "id": department_id,
            "type": 'issue_department'
        })[0][0]
    except Exception:
        raise

    if doc_category['redirection_protocol']:
        startkey = [department_id, None, None]
        endkey = [department_id, {}, {}]
        result = grm_db.get_view_result('issues', 'group_by_assignee', group=True, startkey=startkey,
                                        endkey=endkey)[:]
        department_workers = set(
            GovernmentWorker.objects.filter(department=department_id).values_list('user', flat=True))
        department_workers_with_assignment = {w['key'][1] for w in result}
        department_workers_without_assignment = department_workers - department_workers_with_assignment
        if department_workers_without_assignment:
            worker_id = list(department_workers_without_assignment)[0]
            worker_without_assignment = GovernmentWorker.objects.get(user=worker_id)
            assignee = {
                "id": worker_id,
                "name": worker_without_assignment.get_name()
            }
        else:
            if result:
                result = sort_dictionary_list_by_field(result, 'value')
                assignee = {
                    "id": result[0]['key'][1],
                    "name": result[0]['key'][2]
                }
            elif department_workers:
                worker = GovernmentWorker.objects.filter(department=department_id).first()
                assignee = {
                    "id": worker.user.id,
                    "name": worker.get_name()
                }
            else:
                assignee = ""
    else:
        assignee = doc_department['head']
    return assignee
