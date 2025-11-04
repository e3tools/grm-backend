from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
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
from dashboard.user_management.forms import PasswordConfirmForm, UserProfileForm


class UserListView(PageMixin, LoginRequiredMixin, generic.ListView):
    template_name = "user_management/list.html"
    context_object_name = "users"
    title = _("User Management")
    active_level1 = "user_management"
    breadcrumb = [
        {"url": "", "title": title},
    ]
    queryset = User.objects.all()


class UserDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    template_name = "user_management/profile.html"
    title = _("Facilitator Profile")
    context_object_name = "obj"
    active_level1 = "user_management"
    model = User
    breadcrumb = [
        {
            "url": reverse_lazy("dashboard:user_management:list"),
            "title": _("User Management"),
        },
        {"url": "", "title": title},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["password_confirm_form"] = PasswordConfirmForm()
        return context


class ToggleUserStatusView(LoginRequiredMixin, generic.View):
    def post(self, request, *args, **kwargs):
        user = get_object_or_404(User, id=kwargs["pk"])
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
