from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from authentication.models import Facilitator, GovernmentWorker, User
from common.utils.forms import FileValidationMixin
from dashboard.user_management.constants import (
    ADMINISTRATIVE_REGION_REQUIRED_MESSAGE,
    DEPARTMENT_ASSIGNMENT_ERROR_MESSAGE,
    DEPARTMENT_REQUIRED_MESSAGE,
)
from issues.models import AdministrativeRegion, IssueDepartment


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


class BaseUserCreationForm(forms.Form):
    """Base form for user creation with common fields."""

    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("First Name")}),
        label=_("First Name"),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Last Name")}),
        label=_("Last Name"),
    )
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Username")}),
        label=_("Username"),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": _("Email")}),
        label=_("Email"),
    )
    phone_number = forms.CharField(
        max_length=45,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Phone Number")}),
        label=_("Phone Number"),
    )
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": _("Password")}),
        label=_("Password"),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": _("Confirm Password")}),
        label=_("Confirm Password"),
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise ValidationError({"confirm_password": _("Passwords do not match.")})

        # Validate password strength using Django's built-in validators
        try:
            validate_password(password)
        except ValidationError as e:
            raise ValidationError({'password': list(e.messages)})

        return cleaned_data


class GRMManagerCreationForm(BaseUserCreationForm):
    """Form for creating GRM Manager users."""

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            phone_number=self.cleaned_data["phone_number"],
            grm_manager=True,
        )
        return user


class CaseManagerCreationForm(BaseUserCreationForm):
    """Form for creating Case Manager users."""

    department = forms.ModelChoiceField(
        queryset=IssueDepartment.objects.all(),
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Department"),
        empty_label=_("Select a department"),
    )
    is_department_head = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label=_("Is Department Head"),
    )

    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get("department")
        is_department_head = cleaned_data.get("is_department_head")

        if not department:
            raise ValidationError({"department": DEPARTMENT_REQUIRED_MESSAGE})

        # Check if department already has a head when trying to assign one
        if is_department_head and department and department.head:
            raise ValidationError(
                {
                    "is_department_head": DEPARTMENT_ASSIGNMENT_ERROR_MESSAGE
                    % {"dept": department.name, "head": department.head.name}
                }
            )

        return cleaned_data

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            phone_number=self.cleaned_data["phone_number"],
        )

        department = self.cleaned_data["department"]

        # Create GovernmentWorker
        GovernmentWorker.objects.create(
            user=user,
            department=department,
        )

        # Assign as department head if checked
        if self.cleaned_data.get("is_department_head"):
            department.head = user
            department.save(update_fields=["head"])

        return user


class FacilitatorCreationForm(BaseUserCreationForm):
    """Form for creating Facilitator users."""

    administrative_region = forms.ModelChoiceField(
        queryset=AdministrativeRegion.objects.none(),
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Administrative Level"),
    )
    village_secretary = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label=_("Is Village Secretary"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = getattr(self, "data", None)
        if data and data.get("administrative_region"):
            region_id = data.get("administrative_region")
            self.fields["administrative_region"].queryset = AdministrativeRegion.objects.filter(id=region_id)

    def clean_administrative_region(self):
        administrative_region = self.cleaned_data.get("administrative_region")
        if not administrative_region:
            raise ValidationError(ADMINISTRATIVE_REGION_REQUIRED_MESSAGE)
        return administrative_region

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            phone_number=self.cleaned_data["phone_number"],
        )

        Facilitator.objects.create(
            user=user,
            administrative_region=self.cleaned_data["administrative_region"],
            village_secretary=self.cleaned_data.get("village_secretary", False),
        )

        return user


class UserUpdateForm(forms.ModelForm):
    """Form for updating existing users."""

    # Case Manager fields
    department = forms.ModelChoiceField(
        queryset=IssueDepartment.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Department"),
    )
    is_department_head = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label=_("Is Department Head"),
    )

    # Facilitator fields
    administrative_region = forms.ModelChoiceField(
        queryset=AdministrativeRegion.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Administrative Level"),
    )
    village_secretary = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label=_("Is Village Secretary"),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone_number"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = kwargs.get("instance")

        if user:
            if hasattr(user, "governmentworker"):
                self.fields["department"].initial = user.governmentworker.department
                self.fields["is_department_head"].initial = (
                    user.governmentworker.department.head == user if user.governmentworker.department else False
                )
            elif hasattr(user, "facilitator"):
                self.fields["administrative_region"].initial = user.facilitator.administrative_region
                self.fields["village_secretary"].initial = user.facilitator.village_secretary

    def clean(self):
        cleaned_data = super().clean()
        user = self.instance

        # Validate Case Manager
        if hasattr(user, "governmentworker"):
            department = cleaned_data.get("department")
            if not department:
                self.add_error("department", DEPARTMENT_REQUIRED_MESSAGE)

            is_department_head = cleaned_data.get("is_department_head")
            if is_department_head and department and department.head and department.head != user:
                self.add_error(
                    "is_department_head",
                    DEPARTMENT_ASSIGNMENT_ERROR_MESSAGE % {"dept": department.name, "head": department.head.name},
                )

        # Validate Facilitator
        if hasattr(user, "facilitator"):
            administrative_region = cleaned_data.get("administrative_region")
            if not administrative_region:
                self.add_error("administrative_region", ADMINISTRATIVE_REGION_REQUIRED_MESSAGE)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)

        if commit:
            # Update Case Manager
            if hasattr(user, "governmentworker"):
                worker = user.governmentworker
                old_department = worker.department
                new_department = self.cleaned_data.get("department")

                worker.department = new_department
                worker.save()

                # Handle department head assignment
                is_department_head = self.cleaned_data.get("is_department_head")

                # Remove from old department if was head
                if old_department and old_department.head == user and old_department != new_department:
                    old_department.head = None
                    old_department.save(update_fields=["head"])

                # Assign/unassign as head of new department
                if new_department:
                    if is_department_head:
                        new_department.head = user
                        new_department.save(update_fields=["head"])
                    elif new_department.head == user:
                        # Was head but checkbox unchecked
                        new_department.head = None
                        new_department.save(update_fields=["head"])

            # Update Facilitator
            elif hasattr(user, "facilitator"):
                facilitator = user.facilitator
                facilitator.administrative_region = self.cleaned_data.get("administrative_region")
                facilitator.village_secretary = self.cleaned_data.get("village_secretary", False)
                facilitator.save()

        return user
