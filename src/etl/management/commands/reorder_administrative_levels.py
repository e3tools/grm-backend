from django.conf import settings

from etl.management.commands.base_translated_command import TranslatedBaseCommand
from etl.utils import reorder_level_names_by_depth

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class Command(TranslatedBaseCommand):
    help = 'Reorders AdministrativeLevel names by depth while preserving FK relationships'

    def handle_translated(self, *args, **options):
        self.stdout.write('Starting administrative level reordering...')

        try:
            reorder_level_names_by_depth()
            self.stdout.write(self.style.SUCCESS('Successfully reordered administrative levels!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            raise
