from django.utils.translation import gettext_lazy as _

STATUS_GOOD = {
    'status': 'good',
    'icon_class': 'far fa-check-circle',
    'badge_class': 'badge-primary',
    'badge_text': _('Good'),
    'sort_order': 3,
}

STATUS_AT_RISK = {
    'status': 'at_risk',
    'icon_class': 'fa fa-exclamation-circle',
    'badge_class': 'badge-warning',
    'badge_text': _('At Risk'),
    'sort_order': 2,
}

STATUS_CRITICAL = {
    'status': 'critical',
    'icon_class': 'fa fa-exclamation-circle',
    'badge_class': 'badge-danger',
    'badge_text': _('Critical'),
    'sort_order': 1,
}

STATUS_UNKNOWN = {
    'status': 'unknown',
    'icon_class': 'far fa-question-circle',
    'badge_class': 'badge-secondary',
    'badge_text': _('No Data'),
}

NOT_APPLICABLE = _('N/A')

STATUS_NA = {
    'status': 'na',
    'icon_class': 'fa fa-ban',
    'badge_class': 'badge-secondary',
    'badge_text': NOT_APPLICABLE,
}

WAU_ABBREV = 'WAU'
MAU_ABBREV = 'MAU'
QAU_ABBREV = 'QAU'

MAP_ACTIVE_USER_ABBREV = {WAU_ABBREV: _('WAU'), MAU_ABBREV: _('MAU'), QAU_ABBREV: _('QAU')}

MAP_ACTIVE_USER_TITLE = {
    WAU_ABBREV: _('Weekly Active User'),
    MAU_ABBREV: _('Monthly Active User'),
    QAU_ABBREV: _('Quarterly Active User'),
}

WEEKLY_CHOICE = '7d'
MONTHLY_CHOICE = '30d'
QUARTERLY_CHOICE = '90d'

PERIOD_CHOICES = [
    (WEEKLY_CHOICE, _('Last 7 Days')),
    (MONTHLY_CHOICE, _('Last 30 Days')),
    (QUARTERLY_CHOICE, _('Last 90 Days')),
]

COLOR_PRIMARY = 'primary'
COLOR_WARNING = 'warning'
COLOR_DANGER = 'danger'
COLOR_SECONDARY = 'secondary'
