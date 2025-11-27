from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("issues", "0030_issuestatuschange_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_isc_issue_id
                    ON issues_issuestatuschange (issue_id);
                """,
            reverse_sql="""
                        DROP INDEX CONCURRENTLY IF EXISTS idx_isc_issue_id;
                        """,
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_isc_status_entered
                    ON issues_issuestatuschange (status_id, entered_at);
                """,
            reverse_sql="""
                        DROP INDEX CONCURRENTLY IF EXISTS idx_isc_status_entered;
                        """,
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_isc_exited_nonnull
                    ON issues_issuestatuschange (status_id, entered_at, exited_at)
                    WHERE exited_at IS NOT NULL;
                """,
            reverse_sql="""
                        DROP INDEX CONCURRENTLY IF EXISTS idx_isc_exited_nonnull;
                        """,
        ),
        migrations.RunSQL(
            sql="""
                CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ux_isc_one_open_per_issue
                    ON issues_issuestatuschange (issue_id)
                    WHERE exited_at IS NULL;
                """,
            reverse_sql="""
                        DROP INDEX CONCURRENTLY IF EXISTS ux_isc_one_open_per_issue;
                        """,
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_administrative_region
                    ON issues_issue (administrative_region_id);
                """,
            reverse_sql="""
                        DROP INDEX CONCURRENTLY IF EXISTS idx_issue_administrative_region;
                        """,
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issue_category
                    ON issues_issue (category_id);
                """,
            reverse_sql="""
                        DROP INDEX CONCURRENTLY IF EXISTS idx_issue_category;
                        """,
        ),
    ]
