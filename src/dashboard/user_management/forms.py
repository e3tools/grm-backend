from django import forms
from django.utils.translation import gettext_lazy as _

from authentication.models import User
from common.utils.forms import FileValidationMixin


class PasswordConfirmForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Password",
                "autocomplete": "off",
            }
        ),
        required=True,
        label=_("Password"),
    )


class UserProfileForm(FileValidationMixin, forms.ModelForm):
    file_field_name = "photo"

    class Meta:
        model = User
        fields = ["photo", "first_name", "last_name", "email", "phone_number"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photo"].required = False
        self.fields["photo"].label = ""
        self.fields["photo"].widget.attrs["class"] = "hidden"
