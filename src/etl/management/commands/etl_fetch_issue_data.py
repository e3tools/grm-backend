import logging
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from client import get_db
from etl.management.commands.etl_fetch_adl_data import Command as ADLCommand
from etl.management.commands.etl_fetch_administrative_region_data import (
    Command as RegionCommand,
)
from etl.management.commands.etl_fetch_issue_sub_type_data import (
    Command as SubTypeCommand,
)
from etl.models import ETLExecutionLog
from etl.utils import (
    fetch_database,
    process_category_data,
    process_citizen_group_data,
    process_issue_data,
    process_issue_department_data,
    process_sub_component_data,
)
from issues.models import (
    CitizenAgeGroup,
    CitizenGroup,
    Component,
    Issue,
    IssueCategory,
    IssueDepartment,
    IssueStatus,
    IssueType,
    SubComponent,
    SubProjectGroup,
)

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
        parser.add_argument(
            "--only_confirmed",
            default=False,
            type=bool,
            help="Filter documents by confirmed field",
        )

    def handle(self, *args, **options):
        triggered_by = options["triggered_by"]
        only_confirmed = options["only_confirmed"]

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

            # update User objects
            ADLCommand().handle()

            # update IssueSubType objects
            SubTypeCommand().handle()

            grm_db = get_db(COUCHDB_GRM_DATABASE)

            # update IssueDepartment objects
            # get IssueDepartment documents from CouchDB
            result = grm_db.get_query_result({"type": "issue_department"})

            # process data for bulk create and bulk update
            result = process_issue_department_data(result)
            fetch_database(self, result=result, model_class=IssueDepartment)

            # update CitizenAgeGroup objects
            # get issue_age_group documents from CouchDB
            result = grm_db.get_query_result({"type": "issue_age_group"})
            fetch_database(self, result=result, model_class=CitizenAgeGroup)

            # update CitizenGroup objects
            # get issue_citizen_group documents from CouchDB
            result = grm_db.get_query_result({"type": "issue_citizen_group"})

            # process data for bulk create and bulk update
            result = process_citizen_group_data(result)
            fetch_database(self, result=result, model_class=CitizenGroup)

            # update Component objects
            # get issue_component documents from CouchDB
            result = grm_db.get_query_result({"type": "issue_component"})
            fetch_database(self, result=result, model_class=Component)

            # update SubComponent objects
            # get issue_sub_component documents from CouchDB
            result = grm_db.get_query_result({"type": "issue_sub_component"})

            # process data for bulk create and bulk update
            result = process_sub_component_data(result)
            fetch_database(self, result=result, model_class=SubComponent)

            # update SubProjectGroup objects
            # get issue_subproject_group documents from CouchDB
            result = grm_db.get_query_result({"type": "issue_subproject_group"})
            fetch_database(self, result=result, model_class=SubProjectGroup)

            # update IssueStatus objects
            # get issue_status documents from CouchDB
            result = grm_db.get_query_result({"type": "issue_status"})
            fetch_database(self, result=result, model_class=IssueStatus)

            # update IssueCategory objects
            # get issue_category documents from CouchDB
            result = grm_db.get_query_result({"type": "issue_category"})

            # process data for bulk create and bulk update
            result = process_category_data(result)
            fetch_database(self, result=result, model_class=IssueCategory)

            # update IssueType objects
            # get issue_type documents from CouchDB
            result = grm_db.get_query_result({"type": "issue_type"})
            fetch_database(self, result=result, model_class=IssueType)

            # update Issue objects
            # get issue documents from CouchDB
            selector = {
                "type": "issue",
                "auto_increment_id": {"$ne": ""},
            }
            if only_confirmed:
                selector["confirmed"] = True
            result = grm_db.get_query_result(selector)

            # process data for bulk create and bulk update
            result = process_issue_data(result)
            result = fetch_database(self, result=result, model_class=Issue)

            self.stdout.write(self.style.SUCCESS('Successfully ran etl_fetch_issue_data'))

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
