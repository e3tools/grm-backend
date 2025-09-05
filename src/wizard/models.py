from django.db import models

from dashboard.grm.constants import STATE_CHOICES, WELCOME_CHOICE


class WizardSession(models.Model):
    """
    Model for storing the wizard's global state.
    The table is expected to have only one row.
    """

    state = models.CharField(max_length=50, choices=STATE_CHOICES, default=WELCOME_CHOICE)
    data = models.JSONField(default=dict)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wizard Session"
        verbose_name_plural = "Wizard Sessions"

    @classmethod
    def get_wizard_session(cls):
        """
        Returns the global instance of the wizard.
        If it doesn't exist, creates it with the initial state.
        """
        session, created = cls.objects.get_or_create(pk=1)
        return session

    @classmethod
    def update_state(cls, state: str):
        session = cls.get_wizard_session()
        session.state = state
        session.save()
