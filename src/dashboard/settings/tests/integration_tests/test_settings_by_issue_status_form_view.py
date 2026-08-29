from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import IssueStatusFactory
from issues.models import IssueStatus


class SettingsByIssueStatusFormViewTest(DashboardTestCase):
    """Integration tests for SettingsByIssueStatusFormView"""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.url = reverse("dashboard:settings:by_status")

    def _create_all_flag_statuses(self):
        # Create one status for each flag so the formset labels/fields match expectations
        s_initial = IssueStatusFactory(
            initial_status=True, open_status=False, final_status=False, rejected_status=False
        )
        s_open = IssueStatusFactory(initial_status=False, open_status=True, final_status=False, rejected_status=False)
        s_rejected = IssueStatusFactory(
            initial_status=False, open_status=False, final_status=False, rejected_status=True
        )
        s_final = IssueStatusFactory(initial_status=False, open_status=False, final_status=True, rejected_status=False)
        return [s_initial, s_open, s_rejected, s_final]

    def test_access_denied_without_ajax(self):
        """View should return 404 without AJAX header even for manager"""
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 404

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager cannot access the AJAX view"""
        resp = self.get(self.url, user=self.normal_user, ajax=True)
        assert resp.status_code == 403

    def test_get_ajax_request_renders(self):
        self._create_all_flag_statuses()
        resp = self.get(self.url, user=self.manager, ajax=True)
        assert resp.status_code == 200
        # Template and context
        assert "settings/static_formset.html" in [t.name for t in resp.templates]
        ctx = self.get_context(resp)
        assert "form" in ctx
        assert "formset" in ctx
        assert ctx.get("card_title") == "Settings by Issue Status"

        # Ensure threshold_days field present for some (initial/open) rows
        formset = ctx["form"]
        assert any("threshold_days" in f.fields for f in formset.forms)
        # And ensure for rejected/final forms it is absent
        assert any("threshold_days" not in f.fields for f in formset.forms)

    def test_post_updates_existing_statuses_and_returns_json(self):
        statuses = self._create_all_flag_statuses()
        updated_names = [f"{s.name} Updated" for s in statuses]
        updated_thresholds = [5, 7]  # for initial and open only

        data = {
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "4",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }

        for i, s in enumerate(statuses):
            data[f"form-{i}-id"] = s.id
            data[f"form-{i}-name"] = updated_names[i]
            # Include thresholds only for initial and open statuses
            if s.initial_status or s.open_status:
                # use different values for the two forms that include this field
                data[f"form-{i}-threshold_days"] = updated_thresholds[0] if s.initial_status else updated_thresholds[1]

        resp = self.post(self.url, data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        json_data = resp.json()
        assert "msg" in json_data
        assert "successfully updated" in json_data["msg"].lower()

        # Verify DB updated
        refreshed = list(IssueStatus.objects.order_by("id"))
        # Map by id for name check
        id_to_new_name = {s.id: new for s, new in zip(statuses, updated_names)}
        for s in refreshed:
            assert s.name == id_to_new_name[s.id]
            if s.initial_status:
                assert s.threshold_days == updated_thresholds[0]
            if s.open_status:
                assert s.threshold_days == updated_thresholds[1]

    def test_required_fields_validation(self):
        statuses = self._create_all_flag_statuses()
        data = {
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "4",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }
        for i, s in enumerate(statuses):
            data[f"form-{i}-id"] = s.id
            # Intentionally leave name empty for one of the forms
            data[f"form-{i}-name"] = "" if i == 0 else s.name
            if s.initial_status or s.open_status:
                data[f"form-{i}-threshold_days"] = s.threshold_days

        resp = self.post(self.url, data, user=self.manager, ajax=True)
        # FormView returns 200 with the invalid form rendered
        assert resp.status_code == 200
        html = resp.content.decode("utf-8").lower()
        assert "this field is required" in html

    def test_threshold_validation_rejects_zero(self):
        statuses = self._create_all_flag_statuses()
        data = {
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "4",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }
        for i, s in enumerate(statuses):
            data[f"form-{i}-id"] = s.id
            data[f"form-{i}-name"] = s.name
            if s.initial_status or s.open_status:
                data[f"form-{i}-threshold_days"] = 0  # invalid

        resp = self.post(self.url, data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        html = resp.content.decode("utf-8").lower()
        assert "greater than zero" in html
