from datetime import datetime
from operator import itemgetter

from django.template.defaultfilters import date as _date


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


def get_choices(query_result, empty_choice=True):
    choices = [(i['id'], i['name']) for i in query_result]
    if empty_choice:
        choices = [('', '')] + choices
    return choices


def get_issue_age_group_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_age_group'})
    return get_choices(query_result, empty_choice)


def get_issue_citizen_group_1_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_citizen_group_1'})
    return get_choices(query_result, empty_choice)


def get_issue_citizen_group_2_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_citizen_group_2'})
    return get_choices(query_result, empty_choice)


def get_issue_type_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_type'})
    return get_choices(query_result, empty_choice)


def get_issue_category_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_category'})
    return get_choices(query_result, empty_choice)


def get_issue_status_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_status'})
    return get_choices(query_result, empty_choice)


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


def get_related_region_with_specific_level(eadl_db, region_doc, level):
    has_parent = True
    administrative_id = region_doc['administrative_id']
    while has_parent and region_doc['administrative_level'] != level:
        region_doc = get_parent_administrative_level(eadl_db, administrative_id)
        if region_doc:
            administrative_id = region_doc['administrative_id']
        else:
            has_parent = False

    return region_doc


def belongs_to_region(eadl_db, child_administrative_id, parent_administrative_id):
    belongs = parent_administrative_id == child_administrative_id
    has_parent = True
    while has_parent and not belongs:
        region_doc = get_parent_administrative_level(eadl_db, child_administrative_id)
        if region_doc:
            belongs = parent_administrative_id == region_doc['administrative_id']
        else:
            has_parent = False

    return belongs


def get_auto_increment_id(grm_db):
    try:
        max_auto_increment_id = grm_db.get_view_result('issues', 'auto_increment_id_stats')[0][0]['value']['max']
    except Exception:
        max_auto_increment_id = 0
    return max_auto_increment_id + 1
