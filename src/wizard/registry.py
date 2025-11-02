"""
Wizard Steps Registry

This module provides a registry pattern to manage wizard steps configuration
without circular imports. Views register themselves with the registry during
module loading.
"""

from django.views import View


class WizardStepsRegistry:
    """Registry for wizard steps configuration."""

    def __init__(self):
        self._views: dict[str, type[View]] = {}
        self._steps_cache: dict | None = None

    def register(self, step_name: str, view_class: type[View]):
        """
        Register a view class for a wizard step.

        Args:
            step_name: Unique identifier for the step (e.g., 'project', 'departments')
            view_class: The view class to handle this step
        """
        self._views[step_name] = view_class
        # Invalidate cache when registering new views
        self._steps_cache = None

    def get_view_class(self, step_name: str) -> type[View] | None:
        """Get the view class for a given step name."""
        return self._views.get(step_name)

    def get_all_steps(self) -> dict:
        """
        Get complete wizard steps configuration.

        This method lazily loads WizardSection data to avoid import issues.
        Results are cached for performance.
        """
        if self._steps_cache is not None:
            return self._steps_cache

        # Import here to avoid circular dependency
        from wizard.constants import MAP_WIZARD_SECTION
        from wizard.models import WizardSection

        steps = {}
        for wizard_section in WizardSection.objects.all():
            view_class = self._views.get(wizard_section.name)
            if view_class:
                steps[wizard_section.name] = {
                    'step': wizard_section.step,
                    'view_class': view_class,
                    'display_name': MAP_WIZARD_SECTION.get(wizard_section.name, ''),
                }

        self._steps_cache = steps
        return steps

    def clear_cache(self):
        """Clear the steps cache. Useful when WizardSection data changes."""
        self._steps_cache = None


# Global registry instance
wizard_registry = WizardStepsRegistry()


def register_wizard_step(step_name: str):
    """
    Decorator to register a view class as a wizard step.

    Usage:
        @register_wizard_step('departments')
        class IssueDepartmentsFormView(WizardFormView):
            ...
    """

    def decorator(view_class: type[View]):
        wizard_registry.register(step_name, view_class)
        return view_class

    return decorator


# Helper functions that use the registry
def get_step_by_name(step_name: str) -> dict | None:
    """Get step configuration by name."""
    steps = wizard_registry.get_all_steps()
    return steps.get(step_name)


def get_step_by_number(step_number: int) -> dict | None:
    """Get step configuration by step number."""
    steps = wizard_registry.get_all_steps()
    for step_config in steps.values():
        if step_config['step'] == step_number:
            return step_config
    return None


def get_next_step(current_step_name: str) -> dict | None:
    """Get the next step configuration."""
    current = get_step_by_name(current_step_name)
    if not current:
        return None

    next_step_number = current['step'] + 1
    return get_step_by_number(next_step_number)


def get_previous_step(current_step_name: str) -> dict | None:
    """Get the previous step configuration."""
    current = get_step_by_name(current_step_name)
    if not current:
        return None

    prev_step_number = current['step'] - 1
    if prev_step_number < 1:
        return None

    return get_step_by_number(prev_step_number)


def get_total_steps() -> int:
    """Get total number of steps in the wizard."""
    steps = wizard_registry.get_all_steps()
    return len(steps)


def get_all_wizard_steps() -> dict:
    """Get all wizard steps. Alias for backward compatibility."""
    return wizard_registry.get_all_steps()
