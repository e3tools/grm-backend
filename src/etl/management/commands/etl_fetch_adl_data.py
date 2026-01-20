from django.conf import settings

from authentication.models import Facilitator, User
from client import get_db
from etl.management.commands.base_translated_command import TranslatedBaseCommand
from etl.utils import fetch_database, process_facilitator_data, process_user_data

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class Command(TranslatedBaseCommand):
    help = 'Get data from CouchDB documents to update User model'

    def handle_translated(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Running: etl_fetch_adl_data'))

        administrative_levels_db = get_db()
        result = administrative_levels_db.get_query_result({"type": "adl"})

        # process data for bulk create and bulk update
        users = process_user_data(result)
        fetch_database(self, result=users, model_class=User)

        # process data for bulk create and bulk update
        facilitators = process_facilitator_data(result)
        fetch_database(self, result=facilitators, model_class=Facilitator)

        self.stdout.write(self.style.SUCCESS('Successfully ran etl_fetch_adl_data'))
