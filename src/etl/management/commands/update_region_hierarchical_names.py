from django.db import connection

from etl.management.commands.base_translated_command import TranslatedBaseCommand
from issues.models import AdministrativeRegion


class Command(TranslatedBaseCommand):
    help = 'Update hierarchical_name for all AdministrativeRegions'

    def handle_translated(self, *args, **options):
        self.stdout.write('Updating hierarchical_name...')

        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH RECURSIVE hierarchy_builder AS (
                    -- Base case: start from all regions
                    SELECT id,
                           name,
                           parent_id,
                           name::TEXT AS hierarchy_path
                    FROM issues_administrativeregion

                    UNION ALL

                    -- Recursive case: append parent names
                    SELECT hb.id,
                           hb.name,
                           ar.parent_id,
                           hb.hierarchy_path || ', ' || ar.name AS hierarchy_path
                    FROM hierarchy_builder hb
                             INNER JOIN issues_administrativeregion ar ON hb.parent_id = ar.id)
                UPDATE issues_administrativeregion
                SET hierarchical_name = (SELECT hierarchy_path
                                         FROM hierarchy_builder
                                         WHERE hierarchy_builder.id = issues_administrativeregion.id
                                           AND hierarchy_builder.parent_id IS NULL)
                WHERE EXISTS (SELECT 1
                              FROM hierarchy_builder
                              WHERE hierarchy_builder.id = issues_administrativeregion.id
                                AND hierarchy_builder.parent_id IS NULL)
                """
            )

        count = AdministrativeRegion.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Successfully update for {count} regions'))
