import string
from datetime import datetime
from operator import itemgetter

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import connection
from django.template.defaultfilters import date as _date

# from openpyxl import load_workbook
# from openpyxl.utils.cell import range_boundaries
# note that we import 'Workbook' from spire
# keep in mind in case you want to import a class wih the same name from another package
# from spire.xls import *
# from spire.xls.common import *


def sort_dictionary_list_by_field(list_to_be_sorted, field, reverse=False):
    return sorted(list_to_be_sorted, key=itemgetter(field), reverse=reverse)


def get_month_range(start, end=datetime.now(), fmt="Y F"):
    start = start.month + 12 * start.year
    end = end.month + 12 * end.year
    months = list()
    for month in range(start - 1, end):
        y, m = divmod(month, 12)
        months.insert(0, (f"{y}-{m + 1}", _date(datetime(y, m + 1, 1), fmt)))
    return months


def unix_time_millis(dt):
    epoch = datetime.utcfromtimestamp(0)
    return int((dt - epoch).total_seconds() * 1000)


def get_choices(query_result, empty_choice=True):
    choices = [(i.id, i.name) for i in query_result]
    if empty_choice:
        choices = [("", "")] + choices
    return choices


def get_choices_select2(query_result, empty_choice=True):
    choices = [{"id": i.id, "value": i.name} for i in query_result]
    if empty_choice:
        choices = [{"id": "", "value": ""}] + choices
    return choices


def get_issue_select_options_choices(model_class, parent_id=None, empty_choice=True):
    from django.apps import apps

    query_result = apps.get_model("issues", model_class).objects.filter(parent=parent_id)
    return get_choices_select2(query_result, empty_choice)


def get_issue_subproject_group_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": "issue_subproject_group"})
    return get_choices(query_result, empty_choice)


def get_issue_options_choices(grm_db, type, empty_choice=True):
    query_result = grm_db.get_query_result({"type": type})
    return get_choices(query_result, empty_choice)


def get_administrative_region_name(eadl_db, administrative_id):
    not_found_message = f'[Missing region with administrative_id "{administrative_id}"]'
    if not administrative_id:
        return not_found_message

    region_names = []
    has_parent = True

    while has_parent:
        docs = eadl_db.get_query_result({"administrative_id": administrative_id, "type": "administrative_level"})

        try:
            doc = eadl_db[docs[0][0]["_id"]]
            region_names.append(doc["name"])
            administrative_id = doc["parent_id"]
            has_parent = administrative_id is not None
        except Exception:
            region_names.append(not_found_message)
            has_parent = False

    return ", ".join(region_names)


def get_administrative_level_descendants(eadl_db, parent_id, ids):
    data = eadl_db.get_query_result(
        {
            "type": "administrative_level",
            "parent_id": {"$in": parent_id if isinstance(parent_id, list) else [parent_id]},
        }
    )

    data = [doc for doc in data]
    if len(data) > 0:
        descendants_ids = [region["administrative_id"] for region in data]
        for descendant in descendants_ids:
            ids.append(descendant)
        get_administrative_level_descendants(eadl_db, descendants_ids, ids)

    return ids


def get_parent_administrative_level(eadl_db, administrative_id):
    parent = None
    docs = eadl_db.get_query_result({"administrative_id": administrative_id, "type": "administrative_level"})

    try:
        doc = eadl_db[docs[0][0]["_id"]]
        if "parent_id" in doc and doc["parent_id"]:
            administrative_id = doc["parent_id"]
            docs = eadl_db.get_query_result({"administrative_id": administrative_id, "type": "administrative_level"})
            parent = eadl_db[docs[0][0]["_id"]]
    except Exception:
        pass
    return parent


def get_auto_increment_id(grm_db):
    try:
        max_auto_increment_id = grm_db.get_view_result("issues", "auto_increment_id_stats")[0][0]["value"]["max"]
    except Exception:
        max_auto_increment_id = 0
    return max_auto_increment_id + 1


def normalize_phone_number(phone_number):
    contact = phone_number.translate({ord(c): None for c in string.whitespace})
    if contact.startswith("00"):
        contact = contact.replace("00", "+", 1)

    country_calling_code = settings.COUNTRY_CALLING_CODE
    if not contact.startswith(country_calling_code):
        contact = f"{country_calling_code}{contact}"
    return contact


def reset_sequences():
    with connection.cursor() as cursor:
        for table_name in [
            'issues_administrativelevel',
            'issues_issuedepartment',
            'issues_issuedepartmentadministrativelevel',
        ]:
            cursor.execute(
                f"""
                SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), 
                              (SELECT COALESCE(MAX(id), 1) FROM {table_name}));
            """
            )


def email_is_valid(email):
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False
