import logging
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from client import get_db
from etl.management.commands.etl_fetch_administrative_region_data import (
    Command as RegionCommand,
)
from etl.management.commands.etl_fetch_issue_department_data import (
    Command as DepartmentCommand,
)
from etl.models import ETLExecutionLog
from etl.utils import bulk_create_or_update, process_category_data, process_issue_data
from issues.models import Issue, IssueCategory, IssueStatus, IssueType

logger = logging.getLogger(__name__)
COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class Command(BaseCommand):
    help = 'Get data from CouchDB documents to update information related to the Issue model'

    def add_arguments(self, parser):
        parser.add_argument(
            "--triggered_by",
            default='Manual Execution',
            type=str,
            help="Indicates the type of ETL trigger to record a log of the execution.",
        )

    def fetch_database(self, documents, model_class):
        documents = [doc for doc in documents]

        # create or update database
        model_name = model_class.__name__
        result = bulk_create_or_update(model_class, documents)
        self.stdout.write(self.style.NOTICE(f"Created {result['total_created']} {model_name} objects"))
        self.stdout.write(self.style.NOTICE(f"Updated {result['total_updated']} {model_name}  objects"))
        self.stdout.write(self.style.NOTICE(f"Processed {result['total_processed']} {model_name}  objects"))
        return result

    def handle(self, *args, **options):
        triggered_by = options["triggered_by"]

        etl_name = 'etl_fetch_issue_data'
        log_entry = None

        try:
            log_entry = ETLExecutionLog.objects.create(
                etl_name=etl_name, started_at=timezone.now(), status='RUNNING', triggered_by=triggered_by
            )
            logger.info(f"Started ETL {etl_name} - Log ID: {log_entry.id}")

            self.stdout.write(self.style.NOTICE('Running: etl_fetch_issue_data'))

            # update AdministrativeRegion objects
            RegionCommand().handle()

            # update IssueDepartment objects
            DepartmentCommand().handle()

            grm_db = get_db(COUCHDB_GRM_DATABASE)

            # update IssueStatus objects
            # get issue_status documents from CouchDB
            documents = grm_db.get_query_result({"type": "issue_status"})
            self.fetch_database(documents=documents, model_class=IssueStatus)

            # update IssueCategory objects
            # get issue_category documents from CouchDB
            documents = grm_db.get_query_result({"type": "issue_category"})

            # process data for bulk create and bulk update
            documents = process_category_data(documents)
            self.fetch_database(documents=documents, model_class=IssueCategory)

            # update IssueType objects
            # get issue_type documents from CouchDB
            documents = grm_db.get_query_result({"type": "issue_type"})
            self.fetch_database(documents=documents, model_class=IssueType)

            # update Issue objects
            # get issue documents from CouchDB
            selector = {
                "type": "issue",
                "confirmed": True,
                "auto_increment_id": {"$ne": ""},
            }
            documents = grm_db.get_query_result(selector)

            # process data for bulk create and bulk update
            documents = process_issue_data(documents)
            result = self.fetch_database(documents=documents, model_class=Issue)

            self.stdout.write(self.style.SUCCESS('Successfully ran ETL process'))

            log_entry.status = 'SUCCESS'
            log_entry.finished_at = timezone.now()
            log_entry.records_processed = result['total_processed']
            log_entry.save()

            logger.info(f"ETL {etl_name} completed successfully. Processed {result['total_processed']} records")
        except Exception as e:
            error_message = f"ETL failed: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_message)

            if log_entry:
                log_entry.status = 'FAILED'
                log_entry.finished_at = timezone.now()
                log_entry.error_message = error_message[:1000]  # Truncate if too long
                log_entry.save()
