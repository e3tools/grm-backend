from django.conf import settings
from django.core.management import call_command

from authentication.models import Cdata, Pdata
from client import get_db
from etl.management.commands.base_translated_command import TranslatedBaseCommand
from etl.utils import create_attachments, fetch_database, process_comments_data
from issues.models import Comment, Issue

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class Command(TranslatedBaseCommand):
    help = 'Get data from CouchDB documents to update all related models'

    def update_cripto_models(self, external_issues):
        def update_keys(model_class):
            model_name = model_class.__name__
            items_to_update = []
            external_issues_keys = [str(key) for key in external_issues.keys()]
            objs = model_class.objects.filter(key__in=external_issues_keys)
            for obj in objs:
                obj.key = str(external_issues[obj.key])
                items_to_update.append(obj)

            if items_to_update:
                # New ones are created and old ones are deleted because bulk_update cannot be applied to pk field (key)
                model_class.objects.bulk_create(items_to_update)
                model_class.objects.filter(key__in=external_issues_keys).delete()
                self.stdout.write(self.style.NOTICE(f"Updated {len(items_to_update)} {model_name} objects"))

        update_keys(Cdata)
        update_keys(Pdata)

    def handle_translated(self, *args, **options):

        self.stdout.write(self.style.NOTICE('Running: etl_fetch_all_data'))

        # update Issue objects and their FK objects
        call_command("etl_fetch_issue_data")

        # Load issues into a dictionary {external_id: id}
        external_issues = dict(Issue.objects.filter(external_id__isnull=False).values_list('external_id', 'id'))

        # update Cdata and Pdata objects
        self.update_cripto_models(external_issues)

        # update Comment objects
        # get issue documents from CouchDB
        grm_db = get_db(COUCHDB_GRM_DATABASE)
        selector = {
            "type": "issue",
            "auto_increment_id": {"$ne": ""},
        }
        data = grm_db.get_query_result(selector)

        # process data for bulk create
        result = process_comments_data(data, external_issues)
        fetch_database(self, result=result, model_class=Comment)

        # create IssueAttachment objects
        attachments_created = create_attachments(data, external_issues)

        self.stdout.write(self.style.NOTICE(f"Created {attachments_created} IssueAttachment objects"))

        self.stdout.write(self.style.SUCCESS('Successfully ran etl_fetch_all_data'))
