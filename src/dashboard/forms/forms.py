from django import forms
from django.template.defaultfilters import filesizeformat

from dashboard.grm.constants import (
    FILE_HELP_TEXT,
    FILE_SIZE_ERROR_MESSAGE,
    MAX_UPLOAD_SIZE,
)


class FileForm(forms.Form):
    file = forms.FileField(label="", help_text=FILE_HELP_TEXT)

    default_error_messages = {"file_size": FILE_SIZE_ERROR_MESSAGE}

    def clean_file(self):
        value = self.cleaned_data.get("file")
        if value and value.size > MAX_UPLOAD_SIZE:
            raise forms.ValidationError(self.default_error_messages["file_size"] % filesizeformat(value.size))
        return value
