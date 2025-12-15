import math

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
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


class DataTableMixin:
    default_per_page = 10

    def parse_int(self, value, default=None):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_request_params(self, request):
        per_page = self.parse_int(request.GET.get('length') or request.GET.get('per_page'), self.default_per_page)
        if not per_page or per_page <= 0:
            per_page = self.default_per_page

        page_param = request.GET.get('page')
        if page_param is not None:
            page_num = self.parse_int(page_param, 1)
            if page_num < 1:
                page_num = 1
        else:
            start = self.parse_int(request.GET.get('start', 0), 0)
            page_num = (start // per_page) + 1

        draw = self.parse_int(request.GET.get('draw'), None)
        sort_dir = request.GET.get('sort_dir', 'desc')
        sort_by = request.GET.get('sort_by')
        if not sort_by and request.GET.get('order[0][column]') is not None:
            try:
                col_idx = int(request.GET.get('order[0][column]'))
                sort_dir = request.GET.get('order[0][dir]', 'asc')
                sort_by = self.get_column_key_from_index(col_idx)
            except Exception:
                sort_by = None

        return {
            'per_page': per_page,
            'page_num': page_num,
            'draw': draw,
            'sort_by': sort_by,
            'sort_dir': sort_dir,
            'raw': request.GET,
        }

    def get_column_key_from_index(self, idx):
        return None

    def get_base_queryset(self, request):
        raise NotImplementedError

    def apply_filters(self, qs, params):
        return qs

    def get_sort_map(self):
        return {}

    def get_sort_field(self, sort_by, sort_dir):
        sort_map = self.get_sort_map()
        sort_field = sort_map.get(sort_by, None)
        if not sort_field:
            return None
        if sort_dir == 'desc':
            if not str(sort_field).startswith('-'):
                return '-' + str(sort_field)
        else:
            if str(sort_field).startswith('-'):
                return str(sort_field)[1:]
        return sort_field

    def manual_sort(self, qs_or_list, sort_by, sort_dir):
        return None

    def serialize_row(self, obj):
        raise NotImplementedError

    def build_pagination(self, total_count, per_page, page_num):
        # Use math.ceil to compute pages; allow 0 pages when total_count == 0
        if per_page and per_page > 0:
            num_pages = math.ceil(total_count / per_page) if total_count > 0 else 0
        else:
            num_pages = 1 if total_count > 0 else 0

        return {
            'current_page': page_num,
            'total_pages': num_pages,
            'total_records': total_count,
            'per_page': per_page,
            'has_previous': page_num > 1,
            'has_next': page_num < num_pages,
        }

    def get_response(self, page_objects, total_count, pagination, draw):
        data = [self.serialize_row(o) for o in page_objects]

        # Include optional metadata flags if set by apply_filters in the view
        no_children = getattr(self, '_no_children', False)
        message = getattr(self, '_message', None)

        payload = {
            'data': data,
            'recordsTotal': total_count,
            'recordsFiltered': total_count,
            'pagination': pagination,
            'draw': draw,
            # metadata for RegionPerformanceAPIView tests
            'no_children': no_children,
            'message': message,
        }
        return JsonResponse(payload)

    def handle(self, request, *args, **kwargs):
        params = self.get_request_params(request)
        # reset metadata flags
        self._no_children = False
        self._message = None

        qs = self.get_base_queryset(request)
        qs = self.apply_filters(qs, params)

        sort_field = None
        if params['sort_by']:
            sort_field = self.get_sort_field(params['sort_by'], params['sort_dir'])

        total_count = qs.count()

        manual = None
        if params['sort_by']:
            manual = self.manual_sort(qs, params['sort_by'], params['sort_dir'])

        if manual is not None:
            objects_list = manual
            per_page = params['per_page']
            page_num = params['page_num']
            start = (page_num - 1) * per_page
            end = start + per_page
            page_objects = objects_list[start:end]
            pagination = self.build_pagination(len(objects_list), per_page, page_num)
            return self.get_response(page_objects, len(objects_list), pagination, params['draw'])

        if sort_field:
            qs = qs.order_by(sort_field)
        per_page = params['per_page']
        paginator = Paginator(qs, per_page)
        page_num = params['page_num']
        if page_num > paginator.num_pages and paginator.num_pages > 0:
            page_num = paginator.num_pages
        page_obj = paginator.get_page(page_num)
        pagination = self.build_pagination(total_count, per_page, page_num)
        return self.get_response(page_obj.object_list, total_count, pagination, params['draw'])
