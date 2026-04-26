from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone

from etl.models import ETLExecutionLog
from grm.tests.base import DashboardTestCase


class UpdateIssuesDataViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("dashboard:diagnostics:update_issues_data")

    def test_auth_permission(self):
        response = self.post(self.url, data={}, authorized=False, ajax=True)

        assert response.status_code != 200

    @patch("dashboard.diagnostics.views.call_command")
    def test_returns_success_message_when_new_success_log_created(self, call_command_mock):
        now = timezone.now()
        ETLExecutionLog.objects.create(
            etl_name="etl_fetch_issue_data",
            started_at=now - timedelta(minutes=2),
            finished_at=now - timedelta(minutes=1),
            status="SUCCESS",
            records_processed=10,
            triggered_by="MANUAL",
        )
        ETLExecutionLog.objects.create(
            etl_name="etl_fetch_issue_data",
            started_at=now,
            finished_at=now + timedelta(minutes=1),
            status="SUCCESS",
            records_processed=42,
            triggered_by="MANUAL",
        )

        response = self.post(self.url, data={}, ajax=True)

        assert response.status_code == 200
        call_command_mock.assert_called_once_with("etl_fetch_issue_data", only_confirmed=True)
        payload = response.json()
        assert "success" in payload["msg"]
        assert "Records processed: 42" in payload["msg"]
        assert payload["finished_at"]

    @patch("dashboard.diagnostics.views.call_command")
    def test_returns_error_message_when_no_new_success_log(self, call_command_mock):
        now = timezone.now()
        ETLExecutionLog.objects.create(
            etl_name="etl_fetch_issue_data",
            started_at=now - timedelta(minutes=2),
            finished_at=now - timedelta(minutes=1),
            status="SUCCESS",
            records_processed=10,
            triggered_by="MANUAL",
        )

        response = self.post(self.url, data={}, ajax=True)

        assert response.status_code == 200
        call_command_mock.assert_called_once_with("etl_fetch_issue_data", only_confirmed=True)
        payload = response.json()
        assert "danger" in payload["msg"]
        assert "Data update failed" in payload["msg"]
