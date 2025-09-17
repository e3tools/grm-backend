from unittest.mock import Mock

import pytest

from grm.tasks import setup_periodic_tasks


@pytest.mark.django_db
def test_setup_periodic_tasks_registers_all_periodic_tasks():
    """Test that setup_periodic_tasks registers the expected periodic tasks."""

    sender = Mock()
    setup_periodic_tasks(sender=sender)

    expected_calls = [
        (300, "grm.tasks.check_issues()", "check issues every 5 minutes"),
        (300, "grm.tasks.escalate_issues()", "escalate issues every 5 minutes"),
        (300, "grm.tasks.send_sms_message()", "send sms every 5 minutes"),
        (300, "grm.tasks.send_mail_message()", "send mail every 5 minutes"),
        (86400, "grm.tasks.escalate_old_issues()", "escalate old issues every day"),
        (3600, "grm.tasks.reassign_issues_to_appeal()", "reassign issues to appeal every hour"),
    ]

    actual_calls = [
        (call.args[0], str(call.args[1]), call.kwargs["name"]) for call in sender.add_periodic_task.call_args_list
    ]

    assert actual_calls == expected_calls
    assert sender.add_periodic_task.call_count == len(expected_calls)
