from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse


class PageMixin:
    title = None
    active_level1 = None
    active_level2 = None
    breadcrumb = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("title", self.title)
        ctx.setdefault("active_level1", self.active_level1)
        ctx.setdefault("active_level2", self.active_level2)
        ctx.setdefault("breadcrumb", self.breadcrumb)
        return ctx


class ModalFormMixin:
    template_name = "common/modal_form.html"
    id_form = "form"
    title = None
    subtitle = None
    picture = None
    picture_class = None
    submit_button = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("id_form", self.id_form)
        ctx.setdefault("title", self.title)
        ctx.setdefault("subtitle", self.subtitle)
        ctx.setdefault("picture", self.picture)
        ctx.setdefault("picture_class", self.picture_class)
        ctx.setdefault("submit_button", self.submit_button)
        return ctx


class LoginRequiredAndAJAXRequestMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.headers.get("x-requested-with") != "XMLHttpRequest":
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class JSONResponseMixin:
    def render_to_json_response(self, context, **response_kwargs):
        return JsonResponse(self.get_data(context), **response_kwargs)

    def get_data(self, context):
        return context


class UserManagementPermissionMixin(AccessMixin):
    """
    Mixin that requires the user to have user management permissions.

    Only GRM Managers can access user management views.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Only GRM Managers can manage users
        if not request.user.grm_manager:
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)


class UserManagementAndAJAXMixin(AccessMixin):
    """
    Mixin that combines AJAX request validation with user management permissions.

    Only GRM Managers can access these AJAX views.
    Raises Http404 if not AJAX or not authenticated.
    Raises PermissionDenied if not GRM Manager.
    """

    def dispatch(self, request, *args, **kwargs):
        # Check AJAX and authentication
        if not request.user.is_authenticated or request.headers.get("x-requested-with") != "XMLHttpRequest":
            raise Http404

        # Only GRM Managers can manage users
        if not request.user.grm_manager:
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)
