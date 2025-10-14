import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponse, HttpResponseRedirect
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
    ADMINISTRATIVE_LEVEL_UPLOAD_DELETE_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_DUPLICATES_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_SUCCESS_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_UNCHANGEABLE_MESSAGE,
    CATEGORY_TOAST_ERROR_MESSAGE,
    COMPLETED_CHOICE,
    COMPONENT_TOAST_ERROR_MESSAGE,
    DEPARTMENT_TOAST_ERROR_MESSAGE,
    GROUP_TOAST_ERROR_MESSAGE,
    IN_PROGRESS_CHOICE,
    NOT_PERMITTED_TEXT,
    NOT_STARTED_CHOICE,
)
from issues.models import (
    AdministrativeLevel,
    AdministrativeRegion,
    Citizen,
    CitizenAgeGroup,
    CitizenGroup,
    Component,
    Issue,
    IssueCategory,
    IssueDepartment,
    IssueDepartmentAdministrativeLevel,
    IssueStatus,
    SubComponent,
)
from wizard.forms import (
    DEFAULT_CITIZEN_AGE_GROUPS,
    ISSUE_STATUS_DEFINITIONS,
    AdministrativeLevelFormSet,
    ExistingCitizenAgeGroupFormSet,
    ExistingCitizenGroupFormSet,
    ExistingComponentFormSet,
    ExistingIssueStatusFormSet,
    IssueCategoryFormSet,
    IssueDepartmentFormSet,
    NewCitizenAgeGroupFormSet,
    NewCitizenGroupFormSet,
    NewComponentFormSet,
    NewIssueStatusFormSet,
    ProjectForm,
    SubComponentFormSet,
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
        in_progress_section = WizardSection.objects.filter(status=IN_PROGRESS_CHOICE).first()
        ips_id = in_progress_section.id if in_progress_section else None
        in_progress_step = sections.index(ips_id) + 1 if ips_id else total_steps

        current_step = self.request.GET.get('step')
        if current_step and current_step.isdigit():
            current_step = min(int(current_step), in_progress_step)
        else:
            current_step = in_progress_step

        context['current_step'] = current_step
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

    def update_status(self, only_current_step=False, status=COMPLETED_CHOICE):
        current_section = WizardSection.objects.all()[self.step - 1]
        WizardSection.objects.filter(id=current_section.id).update(status=status)
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
            restricted_deletion=(
                Exists(Issue.objects.filter(administrative_region__administrative_level=OuterRef("pk")))
                | Exists(IssueDepartmentAdministrativeLevel.objects.filter(administrative_level=OuterRef("pk")))
            )
        )
        return self.form_class(queryset=queryset, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = context['form']  # Aliases for clarity in the template
        context['formset_label'] = _('Administrative Level Names')
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

        if not AdministrativeRegion.objects.exists():
            messages.warning(
                self.request,
                ADMINISTRATIVE_LEVEL_UPLOAD_DELETE_MESSAGE,
                extra_tags="warning",
            )
            self.update_status(only_current_step=True, status=IN_PROGRESS_CHOICE)

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


class IssueDepartmentsFormView(WizardFormView):
    form_class = IssueDepartmentFormSet
    template_name = "wizard/formset.html"
    step = 4

    def get_form(self, form_class=None):
        queryset = IssueDepartment.objects.annotate(
            restricted_deletion=Exists(
                IssueCategory.objects.filter(
                    Q(assigned_department__department=OuterRef("pk"))
                    | Q(assigned_appeal_department__department=OuterRef("pk"))
                    | Q(assigned_escalation_department__department=OuterRef("pk"))
                )
            )
        )
        return self.form_class(queryset=queryset, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = context['form']  # Aliases for clarity in the template
        context['formset_label'] = _('Departments')
        context['toast_title'] = NOT_PERMITTED_TEXT
        context['toast_message'] = DEPARTMENT_TOAST_ERROR_MESSAGE
        context['two_fields_by_row'] = True
        return context


class IssueCategoriesFormView(WizardFormView):
    form_class = IssueCategoryFormSet
    template_name = "wizard/formset.html"
    step = 5

    def get_form(self, form_class=None):
        queryset = IssueCategory.objects.annotate(
            restricted_deletion=Exists(Issue.objects.filter(category=OuterRef("pk")))
        )
        return self.form_class(queryset=queryset, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = context['form']  # Aliases for clarity in the template
        context['formset_label'] = _('Categories')
        context['toast_title'] = NOT_PERMITTED_TEXT
        context['toast_message'] = CATEGORY_TOAST_ERROR_MESSAGE
        context['two_fields_by_row'] = True
        return context


class ResolutionProcessFormView(WizardFormView):
    form_class = NewIssueStatusFormSet
    template_name = "wizard/static_formset.html"
    step = 6

    def get_form(self, form_class=None):
        queryset = IssueStatus.objects.all()

        if queryset.exists():
            return ExistingIssueStatusFormSet(queryset=queryset, **self.get_form_kwargs())
        else:
            initial_data = [{'name': item['name']} for item in ISSUE_STATUS_DEFINITIONS.values()]
            kwargs = self.get_form_kwargs()
            kwargs['initial'] = initial_data
            kwargs['queryset'] = IssueStatus.objects.none()

            return self.form_class(**kwargs)

    def form_valid(self, formset):
        instances = formset.save(commit=False)

        for instance, flag in zip(instances, ISSUE_STATUS_DEFINITIONS.keys()):
            if not instance.pk:
                instance.initial_status = flag == "initial_status"
                instance.open_status = flag == "open_status"
                instance.final_status = flag == "final_status"
                instance.rejected_status = flag == "rejected_status"
            instance.save()

        self.update_status()
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = context['form']  # Aliases for clarity in the template
        context['formset_label'] = _('Issue Status')
        return context


class CitizenAgeGroupsFormView(WizardFormView):
    form_class = NewCitizenAgeGroupFormSet
    template_name = "wizard/formset.html"
    step = 7

    def get_form(self, form_class=None):
        queryset = CitizenAgeGroup.objects.annotate(
            restricted_deletion=Exists(Citizen.objects.filter(age_group=OuterRef("pk")))
        )

        if queryset.exists():
            return ExistingCitizenAgeGroupFormSet(queryset=queryset, **self.get_form_kwargs())
        else:
            initial_data = [{'name': name} for name in DEFAULT_CITIZEN_AGE_GROUPS]
            kwargs = self.get_form_kwargs()
            kwargs['initial'] = initial_data
            kwargs['queryset'] = IssueStatus.objects.none()

            return self.form_class(**kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = context['form']  # Aliases for clarity in the template
        context['formset_label'] = _('Citizen Age Groups')
        context['toast_title'] = NOT_PERMITTED_TEXT
        context['toast_message'] = GROUP_TOAST_ERROR_MESSAGE
        return context


class CitizenGroupsFormView(WizardFormView):
    form_class = NewCitizenGroupFormSet
    template_name = "wizard/formset.html"
    step = 8
    queryset = None

    def get_form(self, form_class=None):
        self.queryset = CitizenGroup.objects.annotate(
            restricted_deletion=Exists(Citizen.objects.filter(age_group=OuterRef("pk")))
        )

        if self.queryset.exists():
            self.form_class = ExistingCitizenGroupFormSet

        return self.form_class(queryset=self.queryset, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = context['form']  # Aliases for clarity in the template
        context['formset_label'] = _('Citizen Groups')
        context['toast_title'] = NOT_PERMITTED_TEXT
        context['toast_message'] = GROUP_TOAST_ERROR_MESSAGE
        context['skip'] = False if self.queryset else True
        return context


class ComponentAndSubComponentFormView(WizardFormView):
    form_class = NewComponentFormSet
    template_name = "wizard/nested_formset.html"
    step = 9

    def get_form(self, form_class=None):
        """Get the appropriate formset with subformsets and restricted_deletion annotations."""

        # Annotate Components with restricted_deletion
        queryset = Component.objects.annotate(
            # Check if Component is directly referenced by Issues
            restricted_deletion=Exists(Issue.objects.filter(component=OuterRef("pk")))
        )

        if queryset.exists():
            self.form_class = ExistingComponentFormSet

        formset = self.form_class(queryset=queryset, **self.get_form_kwargs())

        used_subcomponents = SubComponent.objects.filter(issues__isnull=False).distinct().values_list('id', flat=True)

        # Initialize subformsets with POST data if available
        if self.request.method == 'POST':
            # Annotate SubComponents with restricted_deletion
            subcomponents_queryset = SubComponent.objects.annotate(
                restricted_deletion=Exists(Issue.objects.filter(sub_component=OuterRef("pk")))
            )
            formset.subformsets = []
            for i, form in enumerate(formset.forms):
                if form.instance.pk:
                    qs = subcomponents_queryset.filter(parent=form.instance)
                else:
                    qs = subcomponents_queryset.none()

                subformset = SubComponentFormSet(
                    self.request.POST,
                    instance=form.instance if form.instance.pk else None,
                    queryset=qs,
                    prefix=f'subcomponent_form-{i}',
                )
                # Link parent form for validation context
                for subform in subformset.forms:
                    subform.parent_form = form
                    subform.restricted_deletion = subform.instance.id in used_subcomponents
                formset.subformsets.append(subformset)
        else:
            # Link parent forms for GET requests too
            for form, subformset in zip(formset.forms, formset.subformsets):
                for subform in subformset.forms:
                    subform.parent_form = form
                    subform.restricted_deletion = subform.instance.id in used_subcomponents

        return formset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = context['form']
        context["formset_label"] = _("Components and Subcomponents")
        context["toast_title"] = NOT_PERMITTED_TEXT
        context["toast_message"] = COMPONENT_TOAST_ERROR_MESSAGE
        return context

    def form_valid(self, formset):
        """Save components and their subcomponents."""
        instances = formset.save(commit=False)

        # Save each component and its subcomponents
        for instance in instances:
            instance.save()

        # Handle deleted components
        for obj in formset.deleted_objects:
            obj.delete()

        return super().form_valid(formset)


class FeedbackAndAppealFormView(WizardFormView):
    template_name = "wizard/example.html"
    step = 10
