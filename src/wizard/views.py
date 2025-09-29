import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, TemplateView, UpdateView, View
from django.views.generic.edit import FormView
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from dashboard.mixins import JSONResponseMixin, LoginRequiredAndAJAXRequestMixin
from dashboard.models import Project
from grm.constants import (
    ADMINISTRATIVE_LEVEL_EXCEL_WORKBOOK_TITLE,
    ADMINISTRATIVE_LEVEL_TOAST_ERROR_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_DUPLICATES_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_SUCCESS_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_UNCHANGEABLE_MESSAGE,
    COMPLETED_CHOICE,
    IN_PROGRESS_CHOICE,
    NOT_PERMITTED_TEXT,
    NOT_STARTED_CHOICE,
)
from issues.models import (
    AdministrativeLevel,
    AdministrativeRegion,
    Issue,
    IssueDepartmentAdministrativeLevel,
)
from wizard.forms import (
    AdministrativeLevelFormSet,
    ProjectForm,
    UploadAdministrativeRegionForm,
)
from wizard.models import WizardSection
from wizard.utils import AdministrativeRegionProcessor

logger = logging.getLogger(__name__)


class CustomizationWizardView(LoginRequiredMixin, TemplateView):
    template_name = "wizard/grm_customization.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sections = list(WizardSection.objects.values_list('id', flat=True))
        total_steps = len(sections)
        context['total_steps'] = total_steps
        in_progress_section = WizardSection.objects.filter(status=IN_PROGRESS_CHOICE).first()
        ips_id = in_progress_section.id if in_progress_section else None
        context['current_step'] = sections.index(ips_id) + 1 if ips_id else total_steps
        return context


class WizardSectionListView(LoginRequiredAndAJAXRequestMixin, ListView):
    template_name = "wizard/wizard_sections.html"
    context_object_name = "wizard_sections"
    model = WizardSection

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['step'] = int(self.request.GET.get("step"))
        return context


class WizardFormView(LoginRequiredAndAJAXRequestMixin, FormView):
    form_class = ProjectForm
    template_name = "wizard/form.html"
    step = 1

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['step'] = self.step
        context['total_steps'] = WizardSection.objects.count()
        return context

    def get_success_url(self):
        return reverse(f"wizard:setup_step_{self.step + 1}")

    def update_status(self, only_current_step=False):
        current_section = WizardSection.objects.all()[self.step - 1]
        WizardSection.objects.filter(id=current_section.id).update(status=COMPLETED_CHOICE)
        if not only_current_step:
            WizardSection.objects.filter(id=current_section.id + 1, status=NOT_STARTED_CHOICE).update(
                status=IN_PROGRESS_CHOICE
            )

    def form_valid(self, form):
        form.save()
        self.update_status()
        return super().form_valid(form)


class ProjectUpdateView(WizardFormView, UpdateView):

    def get_object(self, queryset=None):
        obj = Project.objects.first()
        if not obj:
            obj = Project()
        return obj


class AdministrativeLevelsFormView(WizardFormView):
    form_class = AdministrativeLevelFormSet
    template_name = "wizard/formset.html"
    step = 2

    def get_form(self, form_class=None):
        queryset = AdministrativeLevel.objects.annotate(
            has_issue=Exists(Issue.objects.filter(administrative_region__administrative_level=OuterRef("pk"))),
            has_issue_department=Exists(
                IssueDepartmentAdministrativeLevel.objects.filter(administrative_level=OuterRef("pk"))
            ),
        ).annotate(
            restricted_deletion=(
                Exists(Issue.objects.filter(administrative_region__administrative_level=OuterRef("pk")))
                | Exists(IssueDepartmentAdministrativeLevel.objects.filter(administrative_level=OuterRef("pk")))
            )
        )
        return AdministrativeLevelFormSet(queryset=queryset, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = context['form']  # Aliases for clarity in the template
        context['formset_label'] = _('Administrative Levels')
        context['toast_title'] = NOT_PERMITTED_TEXT
        context['toast_message'] = ADMINISTRATIVE_LEVEL_TOAST_ERROR_MESSAGE
        return context


class DownloadRegionsSampleView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        wb = Workbook()
        ws = wb.active
        ws.title = str(ADMINISTRATIVE_LEVEL_EXCEL_WORKBOOK_TITLE)

        # 1. Get levels
        levels = AdministrativeLevel.objects.all()
        headers = [level.name for level in levels]

        # 2. Writing headers
        ws.append(headers)

        # 3. Building rows with existing regions
        rows = self._build_region_rows(levels)
        for row in rows:
            ws.append(row)

        # 4. Adjust column width
        for col in ws.columns:
            max_length = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    pass
            adjusted_width = max_length + 2
            ws.column_dimensions[col_letter].width = adjusted_width

        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="administrative_levels_sample.xlsx"'
        wb.save(response)
        return response

    def _build_region_rows(self, levels):
        """
        Build the rows for Excel:
        Each row represents a chain of AdministrativeRegions from level 1 to the last.
        """
        if not levels.exists():
            return []

        rows = []

        # get root (there can only be one per model)
        root_region = AdministrativeRegion.objects.filter(parent__isnull=True).first()

        if root_region:
            self._add_region_recursive(root_region, [root_region.name], rows, levels, 1)

        return rows

    def _add_region_recursive(self, region, current_path, rows, levels, level_index):
        """
        Recursively traverses children and builds rows with full paths
        """
        if level_index == len(levels):  # last level reached
            rows.append(current_path + [""] * (len(levels) - len(current_path)))
            return

        children = list(region.children.all())
        if children:
            for child in children:
                self._add_region_recursive(child, current_path + [child.name], rows, levels, level_index + 1)
        else:
            # fill up to the number of levels with empty cells
            rows.append(current_path + [""] * (len(levels) - len(current_path)))


class AdministrativeRegionFormView(JSONResponseMixin, WizardFormView):
    step = 3
    template_name = "wizard/regions.html"
    form_class = UploadAdministrativeRegionForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["regions_summary"] = self.get_regions_summary()
        current_section = WizardSection.objects.all()[self.step - 1]
        context["section_status"] = current_section.status
        return context

    def get_regions_summary(self):
        """Returns a summary of regions by administrative level."""
        return (
            AdministrativeLevel.objects.annotate(region_count=Count("regions"))
            .order_by("id")
            .values("id", "name", "region_count")
        )

    def form_valid(self, form):
        file = form.cleaned_data["file"]

        try:
            """Parse Excel and create AdministrativeRegions in a hierarchical structure."""

            processor = AdministrativeRegionProcessor()

            created_count, duplicate_count, not_deleted_count = processor.process_excel(file)

            # Handle any processing errors
            if processor.stats['errors']:
                error_summary = f"Processing completed with {len(processor.stats['errors'])} errors. "
                error_summary += "Check logs for details."
                logger.warning(error_summary)

                for error in processor.stats['errors']:
                    messages.error(
                        self.request,
                        error,
                        extra_tags="danger",
                    )

            if created_count:
                messages.success(
                    self.request,
                    ADMINISTRATIVE_LEVEL_UPLOAD_SUCCESS_MESSAGE % {"count": created_count},
                    extra_tags="success",
                )
                self.update_status(only_current_step=True)
            if duplicate_count:
                messages.warning(
                    self.request,
                    ADMINISTRATIVE_LEVEL_UPLOAD_DUPLICATES_MESSAGE % {"count": duplicate_count},
                    extra_tags="warning",
                )
            if not_deleted_count > 0:
                messages.warning(
                    self.request,
                    ADMINISTRATIVE_LEVEL_UPLOAD_UNCHANGEABLE_MESSAGE % {"count": not_deleted_count},
                    extra_tags="warning",
                )
        except Exception as e:
            messages.error(
                self.request,
                _("There was an error processing the Excel file: %(error)s") % {"error": str(e)},
                extra_tags="danger",
            )

        context = {"msg": render(self.request, "common/messages.html").content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class NextStepView(LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, View):
    def post(self, request, *args, **kwargs):
        step = self.kwargs["step"]
        sections = WizardSection.objects.all()
        current_section = sections[step - 1]
        if current_section.status == COMPLETED_CHOICE:
            updated = WizardSection.objects.filter(id=current_section.id + 1).update(status=IN_PROGRESS_CHOICE)
            if updated:
                step += 1
        return self.render_to_json_response({"step": step}, safe=False)


class RolesAndResponsibilitiesFormView(WizardFormView):
    template_name = "wizard/example.html"
    step = 4
