"""
Base management command that conditionally enforces a language context
based on the Django local_settings variable `CMD_LANGUAGE_CODE`.

If `local_settings.CMD_LANGUAGE_CODE` is defined, this command will activate
that language for the entire execution of the management command.

Otherwise, it runs without altering the default language configuration.

Usage:
    from core.management.commands.base_translated_command import TranslatedBaseCommand

    class Command(TranslatedBaseCommand):
        help = "Example management command that respects CMD_LANGUAGE_CODE."

        def handle_translated(self, *args, **options):
            # Command logic here
            self.stdout.write("Running with language context applied (if configured).")
"""

from django.core.management.base import BaseCommand
from django.utils import translation

try:
    from grm import local_settings  # noqa: F403
except ImportError:
    from grm import local_settings_template as local_settings  # noqa: F403


class TranslatedBaseCommand(BaseCommand):
    """
    A reusable Django management command base class that ensures commands
    are executed under a specific translation language context, if defined.

    It looks for `CMD_LANGUAGE_CODE` in Django local_settings.
    If found, it activates that language for the duration of the command.
    """

    def handle(self, *args, **options):
        """
        Entry point for management command execution.
        Wraps execution in an optional translation context.
        """
        cmd_language = getattr(local_settings, "CMD_LANGUAGE_CODE", None)
        previous_language = translation.get_language()

        if cmd_language:
            translation.activate(cmd_language)
            self.stdout.write(f"Activated command language: '{cmd_language}' (was '{previous_language}')")
        else:
            self.stdout.write("No CMD_LANGUAGE_CODE set — running with default language.")

        try:
            # Delegate logic to subclass
            return self.handle_translated(*args, **options)
        finally:
            # Restore previous language if it was changed
            if cmd_language:
                translation.activate(previous_language)
                self.stdout.write(f"Restored previous language: '{previous_language}' after command.")

    def handle_translated(self, *args, **options):
        """
        Abstract method to be implemented by subclasses.
        Command logic should go here instead of overriding `handle()`.
        """
        raise NotImplementedError("Subclasses must implement handle_translated() instead of handle().")
