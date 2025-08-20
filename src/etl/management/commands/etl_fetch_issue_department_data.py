from django.conf import settings
from django.core.management.base import BaseCommand

from client import get_db
from etl.utils import bulk_create_or_update, process_issue_department_data
from issues.models import IssueDepartment

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class Command(BaseCommand):
    help = 'Get data from CouchDB documents to update IssueDepartment model'

    def fetch_issue_department(self, grm_db):
        # get issue_department documents from CouchDB
        result = grm_db.get_query_result({"type": "issue_department"})
        departments = [doc for doc in result]

        # process data for bulk create and bulk update
        departments = process_issue_department_data(departments)

        # create departments
        result = bulk_create_or_update(IssueDepartment, departments)

        self.stdout.write(self.style.NOTICE(f"Created {result['total_created']} IssueDepartment objects"))
        self.stdout.write(self.style.NOTICE(f"Updated {result['total_updated']} IssueDepartment objects"))
        self.stdout.write(self.style.NOTICE(f"Processed {result['total_processed']} IssueDepartment objects"))

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Running: etl_fetch_issue_department_data'))

        grm_db = get_db(COUCHDB_GRM_DATABASE)
        self.fetch_issue_department(grm_db)

        self.stdout.write(self.style.SUCCESS('Successfully ran etl_fetch_issue_department_data'))
