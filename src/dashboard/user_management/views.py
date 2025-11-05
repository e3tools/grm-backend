from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from authentication.models import User
from authentication.utils import get_validation_code
from dashboard.mixins import (
    JSONResponseMixin,
    LoginRequiredAndAJAXRequestMixin,
    ModalFormMixin,
    PageMixin,
)
from dashboard.user_management.constants import (
    CASE_MANAGER_CHOICE,
    FACILITATOR_CHOICE,
    GRM_MANAGER_CHOICE,
    MAP_USER_TYPE,
    USER_CREATED_SUCCESS_MESSAGE,
    USER_UPDATED_SUCCESS_MESSAGE,
)
from dashboard.user_management.forms import (
    CaseManagerCreationForm,
    FacilitatorCreationForm,
    GRMManagerCreationForm,
    PasswordConfirmForm,
    UserProfileForm,
    UserUpdateForm,
)


class UserManagementTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    """Main user management view with tabs."""

    template_name = "user_management/user_management.html"
    title = _("User Management")
    active_level1 = "user_management"
    breadcrumb = [
        {"url": "", "title": title},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get active tab from URL parameter, default to grm_manager
        active_tab = self.request.GET.get("tab", GRM_MANAGER_CHOICE)
        if active_tab not in MAP_USER_TYPE.keys():
            active_tab = GRM_MANAGER_CHOICE
        context["active_tab"] = active_tab

        # Initialize forms
        context["grm_manager_form"] = GRMManagerCreationForm()
        context["case_manager_form"] = CaseManagerCreationForm()
        context["facilitator_form"] = FacilitatorCreationForm()

        return context


class UserListView(LoginRequiredAndAJAXRequestMixin, generic.ListView):
    """AJAX view for user list table filtered by user type."""

    template_name = "user_management/list.html"
    context_object_name = "users"

    def get_queryset(self):
        user_type = self.request.GET.get("user_type")
        queryset = User.objects.select_related('facilitator', 'governmentworker').all()

        if user_type == GRM_MANAGER_CHOICE:
            queryset = queryset.filter(grm_manager=True)
        elif user_type == CASE_MANAGER_CHOICE:
            queryset = queryset.filter(governmentworker__isnull=False)
        elif user_type == FACILITATOR_CHOICE:
            queryset = queryset.filter(facilitator__isnull=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_type = self.request.GET.get("user_type")

        # Annotate users with their type
        users_with_type = []
        for user in context['users']:
            role_info = None

            if user_type == GRM_MANAGER_CHOICE:
                role_info = _("All Departments")
            elif user_type == CASE_MANAGER_CHOICE and hasattr(user, 'governmentworker'):
                dept = user.governmentworker.department
                role_info = dept.name
                if dept.head == user:
                    role_info += f" ({_('Head')})"
            elif user_type == FACILITATOR_CHOICE and hasattr(user, 'facilitator'):
                role_info = (
                    user.facilitator.administrative_region.name
                    if user.facilitator.administrative_region
                    else _("Unassigned")
                )
                if user.facilitator.village_secretary:
                    role_info += f" ({_('Village Secretary')})"

            users_with_type.append(
                {
                    'user': user,
                    'user_type': user_type,
                    'role_info': role_info,
                }
            )

        context['users_with_type'] = users_with_type
        context['user_type'] = user_type
        context['facilitator_choice'] = FACILITATOR_CHOICE
        return context


class CreateUserView(LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, generic.View):
    """AJAX view for creating users."""

    def post(self, request, *args, **kwargs):
        user_type = request.POST.get("user_type")

        # Select appropriate form based on user type
        if user_type == GRM_MANAGER_CHOICE:
            form = GRMManagerCreationForm(request.POST)
        elif user_type == CASE_MANAGER_CHOICE:
            form = CaseManagerCreationForm(request.POST)
        elif user_type == FACILITATOR_CHOICE:
            form = FacilitatorCreationForm(request.POST)
        else:
            return JsonResponse({"success": False, "errors": {"user_type": [_("Invalid user type.")]}})

        if form.is_valid():
            try:
                user = form.save()
                messages.success(
                    request,
                    USER_CREATED_SUCCESS_MESSAGE % {"name": user.name},
                    extra_tags="success",
                )
                return JsonResponse(
                    {
                        "success": True,
                        "msg": render(request, "common/messages.html").content.decode("utf-8"),
                        "user_id": user.id,
                    }
                )
            except Exception as e:
                return JsonResponse(
                    {
                        "success": False,
                        "errors": {"__all__": [str(e)]},
                    }
                )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "errors": form.errors,
                }
            )


class UserDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    template_name = "user_management/profile.html"
    title = _("User Profile")
    context_object_name = "obj"
    active_level1 = "user_management"
    model = User
    breadcrumb = [
        {
            "url": reverse_lazy("dashboard:user_management:home"),
            "title": _("User Management"),
        },
        {"url": "", "title": title},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["password_confirm_form"] = PasswordConfirmForm()

        user = self.object
        user_type = None
        role_info = {}

        if user.grm_manager:
            user_type = GRM_MANAGER_CHOICE
            role_info = {
                'type_display': _("GRM Manager"),
                'description': _("Can view and create issues for all departments and add users."),
            }
        elif hasattr(user, 'governmentworker'):
            user_type = CASE_MANAGER_CHOICE
            worker = user.governmentworker
            role_info = {
                'type_display': _("Case Manager"),
                'description': _("Can create issues and view assigned issues."),
                'department': worker.department.name,
                'is_department_head': worker.department.head == user,
            }
        elif hasattr(user, 'facilitator'):
            user_type = FACILITATOR_CHOICE
            facilitator = user.facilitator
            role_info = {
                'type_display': _("Facilitator"),
                'description': _("Community representative for a specific region."),
                'administrative_region': (
                    facilitator.administrative_region.name if facilitator.administrative_region else _("Unassigned")
                ),
                'village_secretary': facilitator.village_secretary,
            }

        context['user_type'] = user_type
        context['role_info'] = role_info
        return context


class UserUpdateView(PageMixin, LoginRequiredMixin, generic.UpdateView):
    template_name = "user_management/update.html"
    form_class = UserUpdateForm
    model = User
    title = _("Update User")
    active_level1 = "user_management"

    def get_context_data(self, **kwargs):
        self.breadcrumb = self.get_breadcrumb()
        context = super().get_context_data(**kwargs)

        user = self.object
        user_type = None

        if user.grm_manager:
            user_type = GRM_MANAGER_CHOICE
        elif hasattr(user, 'governmentworker'):
            user_type = CASE_MANAGER_CHOICE
        elif hasattr(user, 'facilitator'):
            user_type = FACILITATOR_CHOICE

        context['user_type'] = user_type
        context['user_type_display'] = MAP_USER_TYPE.get(user_type)
        return context

    def get_breadcrumb(self):
        return [
            {
                "url": reverse_lazy("dashboard:user_management:home"),
                "title": _("User Management"),
            },
            {
                "url": reverse_lazy("dashboard:user_management:detail", kwargs={"pk": self.object.pk}),
                "title": _("User Profile"),
            },
            {"url": "", "title": self.title},
        ]

    def get_success_url(self):
        return reverse("dashboard:user_management:detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            USER_UPDATED_SUCCESS_MESSAGE % {"name": self.object.name},
            extra_tags="success",
        )
        return response


class ToggleUserStatusView(LoginRequiredMixin, generic.View):
    def post(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs["pk"])
        try:
            if user.is_active:
                form = PasswordConfirmForm(request.POST)
                if not form.is_valid():
                    raise PermissionDenied()

                current_user = request.user
                password = form.cleaned_data["password"]
                if not current_user.check_password(password):
                    raise PermissionDenied()

                user.is_active = False
                user.save()
                msg = _("The account was successfully deactivated.")
                messages.add_message(request, messages.SUCCESS, msg, extra_tags="success")
            else:
                user.is_active = True
                user.save()
                msg = _("The account was activated successfully.")
                messages.add_message(request, messages.SUCCESS, msg, extra_tags="success")

        except PermissionDenied:
            msg = _("The password was not correct, we could not proceed with action.")
            messages.add_message(request, messages.ERROR, msg, extra_tags="danger")
        except Exception:
            raise Http404

        return HttpResponseRedirect(reverse("dashboard:user_management:detail", kwargs={"pk": user.pk}))


class EditUserProfileFormView(
    LoginRequiredAndAJAXRequestMixin,
    ModalFormMixin,
    JSONResponseMixin,
    generic.UpdateView,
):
    queryset = User.objects.all()
    form_class = UserProfileForm
    title = _("Profile information")
    picture = static("images/default-avatar.jpg")
    picture_class = "edit-profile-user-img"
    submit_button = _("Save")

    def get_context_data(self, **kwargs):
        picture = self.object.photo
        if picture:
            self.picture = picture.url
        context = super().get_context_data(**kwargs)
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        user = self.object
        user_previous = User.objects.get(pk=user.pk)
        email = data["email"].lower()
        user_code = get_validation_code(email)
        if user_previous.email != email:
            msg = _("Please note that the Facilitator Code has changed due to the email change.")
            messages.add_message(self.request, messages.INFO, msg, extra_tags="info")
        form.save()

        msg = _("The profile information was successfully edited.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags="success")
        context = {
            "msg": render(self.request, "common/messages.html").content.decode("utf-8"),
            "user_code": user_code,
            "photo": user.photo.url if user.photo else self.picture,
        }
        return self.render_to_json_response(context, safe=False)
