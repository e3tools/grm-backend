import io

from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook

from authentication.factories import UserFactory
from grm.tests.base import ViewTestCase
from issues.factories import (
    AdministrativeLevelFactory,
    AdministrativeRegionFactory,
    IssueFactory,
)
from issues.models import AdministrativeLevel, AdministrativeRegion
from wizard.constants import (
    ADMINISTRATIVE_LEVEL_UPLOAD_DELETE_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_DUPLICATES_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_NO_HEADER_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_NOT_FOUND_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_ROOT_ALREADY_EXISTS_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_ROOT_UNIQUE_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_SUCCESS_MESSAGE,
    ADMINISTRATIVE_LEVEL_UPLOAD_UNCHANGEABLE_MESSAGE,
    ADMINISTRATIVE_REGIONS_CHOICE,
    COMPLETED_CHOICE,
    IN_PROGRESS_CHOICE,
    INVALID_EXCEL_FILE_ERROR_MESSAGE,
    ONLY_EXCEL_FILE_EXTENSIONS_ERROR_MESSAGE,
)
from wizard.models import WizardSection
from wizard.registry import get_next_step, get_step_by_name


class AdministrativeRegionFormViewTest(ViewTestCase):
    """Integration tests for the AdministrativeRegionFormView."""

    def setUp(self):
        self.step = get_step_by_name(ADMINISTRATIVE_REGIONS_CHOICE)['step']
        self.url = reverse(f"wizard:setup_step_{self.step}")
        self.user = UserFactory(grm_manager=True)

        # Wizard sections
        self.current_section = WizardSection.objects.get(step=self.step)
        self.current_section.status = IN_PROGRESS_CHOICE
        self.current_section.save()

        next_step_config = get_next_step(ADMINISTRATIVE_REGIONS_CHOICE)
        self.next_section = WizardSection.objects.get(step=next_step_config['step'])

        # Common levels used in most tests
        self.country = AdministrativeLevelFactory(name="Country")
        self.state = AdministrativeLevelFactory(name="State")
        self.city = AdministrativeLevelFactory(name="City")

    def _make_excel(self, headers=None, rows=None):
        wb = Workbook()
        ws = wb.active
        if headers:
            ws.append(headers)
        if rows:
            for row in rows:
                ws.append(row)
        file_stream = io.BytesIO()
        wb.save(file_stream)
        file_stream.seek(0)

        return SimpleUploadedFile(
            "test.xlsx",
            file_stream.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_redirect_if_not_logged_in(self):
        """Test to make the view return 404 to anonymous users."""
        response = self.get(self.url, authorized=False, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_non_ajax_request_returns_404(self):
        """Test that non-AJAX requests return 404 due to AJAXRequestMixin."""
        response = self.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_non_grm_manager_user_cannot_access(self):
        """Test that logged-in non grm manager users cannot access the view."""

        self.user = UserFactory()
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_get_ajax_request_renders(self):
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/regions.html")
        self.assertIn("form", response.context)
        self.assertEqual(response.context["step"], self.step)
        self.assertIn("regions_summary", response.context)
        regions_summary = [
            {'id': level.id, 'name': level.name, 'region_count': 0} for level in AdministrativeLevel.objects.all()
        ]
        self.assertEqual(list(response.context["regions_summary"]), regions_summary)

    def test_post_valid_excel_creates_regions(self):
        """Uploading a valid Excel file should create regions and return JSON with a success message."""

        excel_file = self._make_excel(
            headers=["Country", "State"],
            rows=[["Argentina", "Buenos Aires"], ["Argentina", "Córdoba"]],
        )

        self.assertNotEqual(self.current_section.status, COMPLETED_CHOICE)

        response = self.post(self.url, {"file": excel_file}, ajax=True)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("msg", data)

        # 3 regions must have been created (1 root + 2 children)
        self.assertEqual(AdministrativeRegion.objects.count(), 3)

        messages = list(get_messages(response.wsgi_request))
        success_msgs = [m.message for m in messages if m.level_tag == "success"]
        self.assertEqual(success_msgs[0], ADMINISTRATIVE_LEVEL_UPLOAD_SUCCESS_MESSAGE % {"count": 3})
        self.current_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)

    def test_post_excel_to_delete_regions(self):
        """Uploading an Excel file should delete regions and update current step status to in_progress."""

        excel_file = self._make_excel(
            headers=["Country"],
            rows=[[]],
        )

        self.assertNotEqual(self.current_section.status, COMPLETED_CHOICE)

        response = self.post(self.url, {"file": excel_file}, ajax=True)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("msg", data)

        # All regions have been deleted
        self.assertEqual(AdministrativeRegion.objects.count(), 0)

        messages = list(get_messages(response.wsgi_request))
        success_msgs = [m.message for m in messages if m.level_tag == "warning"]
        self.assertEqual(success_msgs[0], ADMINISTRATIVE_LEVEL_UPLOAD_DELETE_MESSAGE)

        self.current_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)

    def test_post_excel_without_header_returns_error(self):
        """
        If the Excel has no header row, a ValidationError should be raised
        and clean_unused_regions must NOT be executed.
        """
        excel_file = self._make_excel()  # no header at all

        response = self.post(self.url, {"file": excel_file}, ajax=True)

        self.assertEqual(response.status_code, 200)

        messages = list(get_messages(response.wsgi_request))
        error_msgs = [m.message for m in messages if m.level_tag == "error"]
        self.assertIn(str(ADMINISTRATIVE_LEVEL_UPLOAD_NO_HEADER_MESSAGE), error_msgs[0])

    def test_post_excel_with_duplicates(self):
        """
        If the Excel file contains duplicate regions in the same hierarchy,
        they should be skipped and counted as duplicates.
        """
        excel_file = self._make_excel(
            headers=["Country", "State", "City"],
            rows=[
                ["Argentina", "Buenos Aires", "La Plata"],
                ["Argentina", "Buenos Aires", "La Plata"],  # duplicate row
            ],
        )

        response = self.post(self.url, {"file": excel_file}, ajax=True)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("msg", data)

        # One root + one state + one city = 3 unique regions
        self.assertEqual(AdministrativeRegion.objects.count(), 3)

        # Success + duplicate messages must be present
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "success")
        self.assertEqual(messages[0].message, ADMINISTRATIVE_LEVEL_UPLOAD_SUCCESS_MESSAGE % {"count": 3})
        self.assertEqual(messages[1].level_tag, "warning")
        self.assertEqual(messages[1].message, ADMINISTRATIVE_LEVEL_UPLOAD_DUPLICATES_MESSAGE % {"count": 1})

    def test_post_excel_with_regions_in_use_cannot_be_deleted(self):
        """
        If existing regions are linked to Issues, they cannot be deleted.
        A warning message must be returned with the number of undeleted regions.
        """
        # Create an existing region linked to an Issue
        region = AdministrativeRegionFactory(administrative_level=self.country, name="Argentina")
        IssueFactory(administrative_region=region)

        excel_file = self._make_excel(
            headers=["Country"],
            rows=[["Argentina"]],  # Root reused, no deletion should occur
        )

        response = self.post(self.url, {"file": excel_file}, ajax=True)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("msg", data)

        # Region must still exist
        self.assertEqual(AdministrativeRegion.objects.count(), 1)

        # Warning message must mention undeleted regions
        messages = list(get_messages(response.wsgi_request))
        warning_msgs = [m.message for m in messages if m.level_tag == "warning"]
        self.assertEqual(warning_msgs[0], ADMINISTRATIVE_LEVEL_UPLOAD_UNCHANGEABLE_MESSAGE % {"count": 1})

    def test_post_excel_with_incomplete_hierarchy(self):
        """
        If a row in the Excel leaves the last levels empty,
        the system should still create only the regions with values.
        """
        excel_file = self._make_excel(
            headers=["Country", "State", "City"],
            rows=[
                ["Argentina", "Buenos Aires", ""],  # missing City
                ["Argentina", "Córdoba", None],  # also missing City
            ],
        )

        response = self.post(self.url, {"file": excel_file}, ajax=True)

        self.assertEqual(response.status_code, 200)

        # One root + two states (no cities created)
        self.assertEqual(AdministrativeRegion.objects.count(), 3)

        # Success message must be present
        messages = list(get_messages(response.wsgi_request))
        success_msgs = [m.message for m in messages if m.level_tag == "success"]
        self.assertTrue(any("successfully" in msg.lower() for msg in success_msgs))

    def test_post_excel_with_unknown_administrative_level_returns_error(self):
        """
        If the header contains a level name that does not exist in the DB,
        process_excel must return a ValidationError.
        """
        # No AdministrativeLevel created in DB
        excel_file = self._make_excel(headers=["Province"], rows=[["Galicia"]])

        response = self.post(self.url, {"file": excel_file}, ajax=True)

        self.assertEqual(response.status_code, 200)

        messages = list(get_messages(response.wsgi_request))
        error_msgs = [m.message for m in messages if m.level_tag == "error"]
        self.assertIn(ADMINISTRATIVE_LEVEL_UPLOAD_NOT_FOUND_MESSAGE % {'level': "Province"}, error_msgs[0])

    def test_existing_root_conflict_raises_error(self):
        """
        If a root AdministrativeRegion already exists in DB,
        and the uploaded Excel provides a different root name,
        the processor must raise ValidationError.
        """
        no_unchangeable_region = AdministrativeRegionFactory(
            name="Argentina", administrative_level=self.country, parent=None
        )
        IssueFactory(administrative_region=no_unchangeable_region)

        excel_file = self._make_excel(
            headers=["Country"],
            rows=[["USA"]],
        )

        response = self.post(self.url, {"file": excel_file}, ajax=True)

        self.assertEqual(response.status_code, 200)

        messages = list(get_messages(response.wsgi_request))
        error_msgs = [m.message for m in messages if m.level_tag == "error"]
        self.assertIn(
            ADMINISTRATIVE_LEVEL_UPLOAD_ROOT_ALREADY_EXISTS_MESSAGE % {"root": "Argentina", "new": "USA"}, error_msgs[0]
        )

    def test_multiple_different_roots_in_excel_raise_error(self):
        """
        If the Excel contains multiple rows with different root names
        (e.g., 'Argentina' and 'USA'), the processor must raise ValidationError.
        """

        excel_file = self._make_excel(
            headers=["Country", "State"],
            rows=[["Argentina", "Buenos Aires"], ["USA", "California"]],
        )

        response = self.post(self.url, {"file": excel_file}, ajax=True)

        self.assertEqual(response.status_code, 200)

        messages = list(get_messages(response.wsgi_request))
        error_msgs = [m.message for m in messages if m.level_tag == "error"]
        self.assertIn(
            ADMINISTRATIVE_LEVEL_UPLOAD_ROOT_UNIQUE_MESSAGE % {"root": "Argentina", "new": "USA"}, error_msgs[0]
        )

    def test_invalid_extension_raises_validation_error(self):
        """Uploading a file with an invalid extension (.txt) should raise a ValidationError."""
        file_content = b"not an excel file"
        invalid_file = SimpleUploadedFile("regions.txt", file_content, content_type="text/plain")

        response = self.post(self.url, {"file": invalid_file}, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ONLY_EXCEL_FILE_EXTENSIONS_ERROR_MESSAGE)

    def test_invalid_excel_content_raises_validation_error(self):
        """
        Uploading a file with .xlsx extension but invalid content
        should raise a ValidationError when openpyxl fails to parse it.
        """
        # Create a fake file with valid extension but not a real Excel structure
        file_content = b"this is not a real excel file"
        fake_excel = SimpleUploadedFile(
            "regions.xlsx",
            file_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response = self.post(self.url, {"file": fake_excel}, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, INVALID_EXCEL_FILE_ERROR_MESSAGE)
