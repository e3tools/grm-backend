from django.utils.translation import gettext_lazy as _

STATUS_GOOD = {
    'status': 'good',
    'icon_class': 'far fa-check-circle',
    'badge_class': 'badge-primary',
    'badge_text': _('Good Performance'),
}

STATUS_AT_RISK = {
    'status': 'at_risk',
    'icon_class': 'fa fa-exclamation-circle',
    'badge_class': 'badge-warning',
    'badge_text': _('At Risk'),
}

STATUS_CRITICAL = {
    'status': 'critical',
    'icon_class': 'fa fa-exclamation-circle',
    'badge_class': 'badge-danger',
    'badge_text': _('Critical'),
}

STATUS_UNKNOWN = {
    'status': 'unknown',
    'icon_class': 'far fa-question-circle',
    'badge_class': 'badge-secondary',
    'badge_text': _('No Data'),
}
