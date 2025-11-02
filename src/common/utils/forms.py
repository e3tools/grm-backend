# forms.py

from django import forms
from django.template.defaultfilters import filesizeformat

from grm.constants import (
    FILE_HELP_TEXT,
    FILE_SIZE_ERROR_MESSAGE,
    MAX_UPLOAD_SIZE,
    MAX_UPLOAD_SIZE_FILE_FORMAT,
)


class FileForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].help_text = FILE_HELP_TEXT % MAX_UPLOAD_SIZE_FILE_FORMAT

    file = forms.FileField(label="")

    def clean_file(self):
        value = self.cleaned_data.get("file")
        if value and value.size > MAX_UPLOAD_SIZE:
            error_msg = FILE_SIZE_ERROR_MESSAGE % (MAX_UPLOAD_SIZE_FILE_FORMAT, filesizeformat(value.size))
            raise forms.ValidationError(error_msg)
        return value


class WritableModelChoiceField(forms.ModelChoiceField):
    """Custom ModelChoiceField that also accepts arbitrary strings."""

    def to_python(self, value):
        if value in self.empty_values:
            return None

        model = self.queryset.model
        key = self.to_field_name or "pk"

        # Case: is already an instance of the model
        if isinstance(value, model):
            return value

        # Case: Try to resolve it as a PK in the queryset
        try:
            return self.queryset.get(**{key: value})
        except (ValueError, TypeError, model.DoesNotExist):
            # If it fails → we return the raw string
            return str(value)

    def validate(self, value):
        """Allow values outside the queryset (new strings)."""
        if value in self.empty_values:
            return
        if isinstance(value, self.queryset.model):
            # We only validate queryset if it is a real instance
            return super().validate(value)
        if isinstance(value, str):
            # If it's a string, we let it pass.
            return
        return super().validate(value)


class WritableModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Custom ModelMultipleChoiceField that also accepts arbitrary strings."""

    def clean(self, value):
        """
        Override clean to ensure to_python() and validate() run
        even for non-integer or custom string values.
        """
        value = self.to_python(value)

        self.validate(value)

        return value

    def to_python(self, value):
        """Convert each item: try to resolve to instance or keep as string."""
        if value in self.empty_values:
            return []
        if isinstance(value, str):
            value = [value]

        model = self.queryset.model
        key = self.to_field_name or "pk"
        result = []

        for item in value:
            if item in self.empty_values:
                continue

            if isinstance(item, model):
                result.append(item)
                continue

            try:
                obj = self.queryset.get(**{key: item})
                result.append(obj)
            except (ValueError, TypeError, model.DoesNotExist):
                # Save as string literal if not found
                result.append(str(item))

        return result

    def validate(self, value):
        """Allow values outside queryset (new strings)."""
        if value in self.empty_values or not value:
            if self.required:
                raise forms.ValidationError(self.error_messages["required"], code="required")
            return

        model = self.queryset.model
        for v in value:
            if isinstance(v, model):
                super(forms.ModelMultipleChoiceField, self).validate([v])
            elif isinstance(v, str):
                # Allow new strings
                continue
            else:
                super(forms.ModelMultipleChoiceField, self).validate([v])
