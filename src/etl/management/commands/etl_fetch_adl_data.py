from django.conf import settings
from django.core.management.base import BaseCommand

from authentication.models import User
from client import get_db
from etl.utils import bulk_create_or_update, process_adl_data

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class Command(BaseCommand):
    help = 'Get data from CouchDB documents to update User model'

    def fetch_user(self, administrative_levels_db):
        # get issue_component documents from CouchDB
        result = administrative_levels_db.get_query_result({"type": "adl"})
        users = [doc for doc in result]

        # process data for bulk create and bulk update
        users = process_adl_data(users)

        # create departments
        result = bulk_create_or_update(User, users, validate=False)

        self.stdout.write(self.style.NOTICE(f"Created {result['total_created']} User objects"))
        self.stdout.write(self.style.NOTICE(f"Updated {result['total_updated']} User objects"))
        self.stdout.write(self.style.NOTICE(f"Processed {result['total_processed']} User objects"))

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Running: etl_fetch_adl_data'))

        administrative_levels_db = get_db()
        self.fetch_user(administrative_levels_db)

        self.stdout.write(self.style.SUCCESS('Successfully ran etl_fetch_adl_data'))
