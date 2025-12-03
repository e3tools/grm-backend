from unittest.mock import Mock

import pytest

from grm.tasks import setup_periodic_tasks


@pytest.mark.django_db
def test_setup_periodic_tasks_registers_all_periodic_tasks():
    """Test that setup_periodic_tasks registers the expected periodic tasks."""

    sender = Mock()
    setup_periodic_tasks(sender=sender)

    # Check presence of core tasks by name
    core_expected_names = {
        "check issues every 5 minutes",
        "escalate issues every 5 minutes",
        "send sms every 5 minutes",
        "send mail every 5 minutes",
        "escalate old issues every day",
        "reassign issues to appeal every hour",
    }

    registered_names = {call.kwargs.get("name") for call in sender.add_periodic_task.call_args_list}
    # Ensure all core tasks are present
    assert core_expected_names.issubset(registered_names)

    # Metrics-related tasks counts and presence
    shards_7d = 20
    shards_30d = 8
    expected_metrics_names = {f"update metrics 7d shard {i}" for i in range(shards_7d)}
    expected_metrics_names.update({f"update metrics 30d shard {i}" for i in range(shards_30d)})
    expected_metrics_names.add("update metrics 90d daily")

    assert expected_metrics_names.issubset(registered_names)

    # Status-bottlenecks related periodic tasks (mirrors metrics sharding)
    shards_7d_sb = 20
    shards_30d_sb = 8
    expected_sb_names = {f"update status bottlenecks 7d shard {i}" for i in range(shards_7d_sb)}
    expected_sb_names.update({f"update status bottlenecks 30d shard {i}" for i in range(shards_30d_sb)})
    expected_sb_names.add("update status bottlenecks 90d daily")

    assert expected_sb_names.issubset(registered_names)

    # Region performance periodic tasks (three scheduled entries)
    expected_region_perf_names = {
        "update region performance 7d every 30min",
        "update region performance 30d every 2h",
        "update region performance 90d daily",
    }
    assert expected_region_perf_names.issubset(registered_names)

    # Final sanity: expected total number of add_periodic_task calls
    expected_total = (
        len(core_expected_names)
        + shards_7d
        + shards_30d
        + 1  # metrics daily 90d
        + shards_7d_sb
        + shards_30d_sb
        + 1  # status-bottlenecks daily 90d
        + len(expected_region_perf_names)  # region performance periodic tasks
    )
    assert sender.add_periodic_task.call_count == expected_total
