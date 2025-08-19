import copy

from django.conf import settings
from django.core.management.base import BaseCommand

from client import get_db
from etl.utils import bulk_create_or_update
from issues.models import IssueSubType

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class Command(BaseCommand):
    help = 'Get data from CouchDB documents to update IssueSubType model'

    def fetch_issue_sub_type(self, grm_db):
        # get issue_sub_type documents from CouchDB
        result = grm_db.get_query_result({"type": "issue_sub_type"})
        sub_types = [doc for doc in result]

        # process data for bulk create and bulk update
        sub_types_without_parent_id = copy.deepcopy(sub_types)

        # delete parent_id in the copy
        for obj in sub_types_without_parent_id:
            obj.pop("parent_id", None)

        # create issue subtypes without parent_id
        result = bulk_create_or_update(IssueSubType, sub_types_without_parent_id)
        self.stdout.write(self.style.NOTICE(f"Created {result['total_created']} IssueSubType objects"))

        # if IssueSubType.objects.filter(parent=None).count() > 1:
        #     # update parent_id to issue subtypes
        #     self.stdout.write(
        #         self.style.NOTICE(
        #             "Updating IssueSubType objects if there are new values for the parent_id field"
        #         )
        #     )
        #     result = bulk_create_or_update(IssueSubType, sub_types)
        #     self.stdout.write(self.style.NOTICE(f"Created {result['total_created']} IssueSubType objects"))
        #     self.stdout.write(self.style.NOTICE(f"Updated {result['total_updated']} IssueSubType objects"))
        #     self.stdout.write(self.style.NOTICE(f"Processed {result['total_processed']} IssueSubType objects"))

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Running: etl_fetch_issue_sub_type_data'))

        grm_db = get_db(COUCHDB_GRM_DATABASE)
        self.fetch_issue_sub_type(grm_db)

        self.stdout.write(self.style.SUCCESS('Successfully ran etl_fetch_issue_sub_type_data'))
