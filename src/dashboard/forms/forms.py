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
