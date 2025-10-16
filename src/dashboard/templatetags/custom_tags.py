from django import template
from django.utils import timezone

from authentication.utils import get_validation_code
from grm.constants import (
    CITIZEN_TYPE_CHOICES,
    CITIZEN_TYPE_CHOICES_ALT,
    CONTACT_CHOICES,
    MAP_STATUS,
    MAP_WIZARD_SECTION,
    MEDIUM_CHOICES,
)

register = template.Library()


@register.filter
def get(dictionary, key):
    return dictionary.get(key, None)


@register.simple_tag
def get_code(email):
    code = "-"
    if email:
        code = get_validation_code(email)
    return code


@register.simple_tag
def get_status_phase(tasks):
    len_tasks = len(tasks)
    status = "in-progress"
    completed = len([task for task in tasks if task["status"] == "completed"])
    not_started = len([task for task in tasks if task["status"] == "not-started"])
    if completed == len_tasks:
        status = "completed"
    elif not_started == len_tasks:
        status = "not-started"
    return status


@register.simple_tag
def get_completed_tasks(tasks):
    len_tasks = len(tasks)
    completed = len([task for task in tasks if task["status"] == "completed"])
    return f"{completed}/{len_tasks}"


@register.simple_tag
def date_order_format(date):
    data = date.split("-") if date else []
    return f"{data[2]}{data[1]}{data[0]}" if len(data) > 2 else ""


@register.simple_tag
def get_date(date_time):
    data = date_time.split("T") if date_time else ""
    if data:
        data = data[0].split("-")
        data = f"{data[2]}-{data[1]}-{data[0]}" if len(data) > 2 else ""
    return data


@register.simple_tag
def get_days_until_today(date_time):
    delta = timezone.now() - date_time
    return delta.days


@register.simple_tag
def get_percentage_style(percentage):
    style = "danger"
    percentage = int(percentage)
    if percentage > 19:
        style = "yellow"
    if percentage > 49:
        style = "primary"
    return style


@register.filter
def next_in_circular_list(items, i):
    if i >= len(items):
        i %= len(items)
    return items[i]


@register.simple_tag
def get_citizen_type_display(value):
    for key, label in CITIZEN_TYPE_CHOICES:
        if key == value:
            return label


@register.simple_tag
def get_citizen_type_alt_display(value):
    for key, label in CITIZEN_TYPE_CHOICES_ALT:
        if key == value:
            return label


@register.simple_tag
def get_contact_type_display(value):
    for key, label in CONTACT_CHOICES:
        if key == value:
            return label


@register.simple_tag
def get_contact_medium_display(value):
    for key, label in MEDIUM_CHOICES:
        if key == value:
            return label


@register.simple_tag
def get_status_display(value):
    return MAP_STATUS[value]


@register.simple_tag
def get_wizard_section_display(value):
    return MAP_WIZARD_SECTION.get(value)


@register.simple_tag
def get_initials(string):
    return "".join(w[0] for w in string.split(" ") if w).upper()


@register.filter
def get_item(list_obj, index):
    """
    Get item from list by index.

    Usage: {{ formset.subformsets|get_item:forloop.counter0 }}
    """
    try:
        return list_obj[int(index)]
    except (IndexError, ValueError, TypeError, AttributeError):
        return None
