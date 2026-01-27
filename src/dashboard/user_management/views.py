from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import generic

from authentication.models import User
from authentication.utils import get_validation_code
from dashboard.constants import (
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_WARNING,
    ICON_ALERT,
    ICON_CHECK,
    LABEL_ACTIVE,
    LABEL_INACTIVE,
    LABEL_LOW_ACTIVITY,
)
from dashboard.mixins import (
    ModalFormMixin,
    PageMixin,
    UserManagementAndAJAXMixin,
    UserManagementPermissionMixin,
)
from dashboard.user_management.constants import (
    CASE_MANAGER_CHOICE,
    CASE_MANAGER_DISPLAY,
    FACILITATOR_CHOICE,
    FACILITATOR_DISPLAY,
    GRM_MANAGER_CHOICE,
    GRM_MANAGER_DISPLAY,
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


class UserManagementTemplateView(PageMixin, UserManagementPermissionMixin, generic.TemplateView):
    """Main user management view with tabs. Only accessible by GRM Managers."""

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


class UserListView(UserManagementAndAJAXMixin, generic.ListView):
    """AJAX view for user list table filtered by user type. Only accessible by GRM Managers."""

    template_name = "user_management/list.html"
    context_object_name = "users"

    def get_queryset(self):
        user_type = self.request.GET.get("user_type")
        queryset = User.objects.select_related(
            'facilitator__administrative_region',
            'governmentworker__administrative_region',
            'governmentworker__department',
        ).all()

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

            if user_type == CASE_MANAGER_CHOICE and hasattr(user, 'governmentworker'):
                dept = user.governmentworker.department
                role_info = dept.name
                if dept.head == user:
                    role_info += f" ({_('Head')})"
            elif user_type == FACILITATOR_CHOICE and hasattr(user, 'facilitator'):
                role_info = f"{_('Village Secretary')}: {_('Yes') if user.facilitator.village_secretary else _('No')}"

            users_with_type.append(
                {
                    'user': user,
                    'user_type': user_type,
                    'role_info': role_info,
                }
            )

        context['users_with_type'] = users_with_type
        context['user_type'] = user_type
        context['grm_manager'] = GRM_MANAGER_CHOICE
        return context


class CreateUserView(UserManagementAndAJAXMixin, generic.View):
    """AJAX view for creating users. Only accessible by GRM Managers."""

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


class UserDetailView(PageMixin, UserManagementPermissionMixin, generic.DetailView):
    """User profile detail view with activity statistics. Only accessible by GRM Managers."""

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

    def dispatch(self, request, *args, **kwargs):
        # Check if user is GRM Manager
        if hasattr(request.user, 'grm_manager') and not request.user.grm_manager:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Optimize query with annotations for issue statistics."""
        return User.objects.annotate(
            assigned_issues_count=Count('assigned_issues', filter=Q(assigned_issues__confirmed=True), distinct=True),
            open_issues_count=Count(
                'assigned_issues',
                filter=Q(assigned_issues__confirmed=True, assigned_issues__status__open_status=True),
                distinct=True,
            ),
            resolved_issues_count=Count(
                'assigned_issues',
                filter=Q(assigned_issues__confirmed=True, assigned_issues__status__final_status=True),
                distinct=True,
            ),
            rejected_issues_count=Count(
                'assigned_issues',
                filter=Q(assigned_issues__confirmed=True, assigned_issues__status__rejected_status=True),
                distinct=True,
            ),
        ).select_related(
            'governmentworker__department',
            'governmentworker__administrative_region',
            'facilitator__administrative_region',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["password_confirm_form"] = PasswordConfirmForm()

        user = self.object
        user_type = None
        role_info = {}

        # Determine user type and basic role info
        if user.grm_manager:
            user_type = GRM_MANAGER_CHOICE
            role_info = {
                'badge_color': 'badge-secondary',
                'type_display': GRM_MANAGER_DISPLAY,
                'description': _("Can view and create issues for all departments and add users."),
            }
        elif hasattr(user, 'governmentworker'):
            user_type = CASE_MANAGER_CHOICE
            worker = user.governmentworker
            role_info = {
                'badge_color': 'badge-blue',
                'type_display': CASE_MANAGER_DISPLAY,
                'administrative_region': worker.administrative_region.hierarchical_name,
                'description': _("Can create issues and view assigned issues."),
                'department': worker.department.name,
                'is_department_head': worker.department.head == user,
            }
        elif hasattr(user, 'facilitator'):
            user_type = FACILITATOR_CHOICE
            facilitator = user.facilitator
            role_info = {
                'badge_color': 'badge-purple',
                'type_display': FACILITATOR_DISPLAY,
                'description': _("Community representative for a specific region."),
                'administrative_region': facilitator.administrative_region.hierarchical_name,
                'village_secretary': facilitator.village_secretary,
            }

        context['user_type'] = user_type
        context['role_info'] = role_info

        # Add activity statistics
        context['activity_stats'] = self._get_activity_statistics(user)

        return context

    def _get_activity_statistics(self, user):
        """
        Calculate comprehensive activity statistics for the user.

        Returns:
            dict: Activity statistics including issue counts and activity level
        """
        # Get issue counts from annotations (if available) or query directly
        assigned_count = getattr(user, 'assigned_issues_count', None)
        if assigned_count is None:
            assigned_count = user.assigned_issues.filter(confirmed=True).count()

        open_count = getattr(user, 'open_issues_count', None)
        if open_count is None:
            open_count = user.assigned_issues.filter(confirmed=True, status__open_status=True).count()

        resolved_count = getattr(user, 'resolved_issues_count', None)
        if resolved_count is None:
            resolved_count = user.assigned_issues.filter(confirmed=True, status__final_status=True).count()

        rejected_count = getattr(user, 'rejected_issues_count', None)
        if rejected_count is None:
            rejected_count = user.assigned_issues.filter(confirmed=True, status__rejected_status=True).count()

        # Calculate activity metrics
        last_activity_days = self._calculate_last_activity_days(user)
        last_activity_display = self._format_last_activity(last_activity_days)
        activity_level = self._calculate_activity_level(last_activity_days)

        # Calculate resolution rate if user has assigned issues
        resolution_rate = None
        if assigned_count > 0:
            closed_count = resolved_count + rejected_count
            resolution_rate = round((closed_count / assigned_count) * 100, 1)

        return {
            'assigned_issues': assigned_count,
            'open_issues': open_count,
            'resolved_issues': resolved_count,
            'rejected_issues': rejected_count,
            'resolution_rate': resolution_rate,
            'last_activity_display': last_activity_display,
            'last_activity_days': last_activity_days,
            'activity_level': activity_level,
        }

    def _calculate_last_activity_days(self, user):
        """
        Calculate days since last activity.

        Returns:
            int or None: Number of days since last activity, None if never active
        """
        if not user.last_activity:
            return None

        now = timezone.now()
        duration = now - user.last_activity
        return duration.days

    def _format_last_activity(self, days):
        """
        Format last activity for display.

        Returns:
            str: Formatted last activity string
        """
        if days is None:
            return _("Never")

        if days == 0:
            return _("Today")
        elif days == 1:
            return _("1 day ago")
        else:
            return _("%(days)s days ago") % {'days': days}

    def _calculate_activity_level(self, last_activity_days):
        """
        Calculate activity level based on last activity days.
        Same logic as InactiveUsersAPIView.

        Returns:
            dict: Activity level with label, color, and icon
        """
        if last_activity_days is None or last_activity_days > 20:
            return {
                'label': LABEL_INACTIVE,
                'color': COLOR_SECONDARY,
                'badge_color': 'badge-secondary',
                'icon': ICON_ALERT,
            }
        elif last_activity_days < 7:
            return {'label': LABEL_ACTIVE, 'color': COLOR_PRIMARY, 'badge_color': 'badge-primary', 'icon': ICON_CHECK}
        else:
            # Low Activity: 7-20 days
            return {
                'label': LABEL_LOW_ACTIVITY,
                'color': COLOR_WARNING,
                'badge_color': 'badge-warning',
                'icon': ICON_ALERT,
            }


class UserUpdateView(PageMixin, UserManagementPermissionMixin, generic.UpdateView):
    """User update view. Only accessible by GRM Managers."""

    template_name = "user_management/update.html"
    form_class = UserUpdateForm
    model = User
    title = _("Update User")
    active_level1 = "user_management"

    def dispatch(self, request, *args, **kwargs):
        # Check if user is GRM Manager
        if hasattr(request.user, 'grm_manager') and not request.user.grm_manager:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

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


class ToggleUserStatusView(UserManagementPermissionMixin, generic.View):
    """Toggle user active status. Only accessible by GRM Managers."""

    def dispatch(self, request, *args, **kwargs):
        # Check if user is GRM Manager
        if hasattr(request.user, 'grm_manager') and not request.user.grm_manager:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

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
    UserManagementAndAJAXMixin,
    ModalFormMixin,
    generic.UpdateView,
):
    """Edit user profile form. Only accessible by GRM Managers."""

    queryset = User.objects.all()
    form_class = UserProfileForm
    title = _("Profile information")
    picture = static("images/default-avatar.jpg")
    picture_class = "edit-profile-user-img"
    submit_button = _("Save")

    def dispatch(self, request, *args, **kwargs):
        # Check if user is GRM Manager
        if hasattr(request.user, 'grm_manager') and not request.user.grm_manager:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

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
        return JsonResponse(context, safe=False)
