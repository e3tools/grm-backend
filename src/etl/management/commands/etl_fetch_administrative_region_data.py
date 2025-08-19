import copy

from django.conf import settings
from django.core.management.base import BaseCommand

from client import get_db
from etl.utils import bulk_create_or_update, process_administrative_region_data
from issues.models import AdministrativeRegion

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE


class Command(BaseCommand):
    help = 'Get data from CouchDB documents to update AdministrativeRegion model'

    def fetch_administrative_region(self, administrative_levels_db):
        # get administrative_level documents from CouchDB
        result = administrative_levels_db.get_query_result({"type": "administrative_level"})
        regions = [doc for doc in result]

        # process data for bulk create and bulk update
        regions = process_administrative_region_data(regions)
        regions_without_parent_id = copy.deepcopy(regions)

        # delete parent_id in the copy
        for obj in regions_without_parent_id:
            obj.pop("parent_id", None)

        # create administrative regions without parent_id
        result = bulk_create_or_update(AdministrativeRegion, regions_without_parent_id)
        self.stdout.write(self.style.NOTICE(f"Created {result['total_created']} AdministrativeRegion objects"))

        if AdministrativeRegion.objects.filter(parent=None).count() > 1:
            # update parent_id to administrative regions
            self.stdout.write(
                self.style.NOTICE(
                    "Updating AdministrativeRegion objects if there are new values for the parent_id field"
                )
            )
            result = bulk_create_or_update(AdministrativeRegion, regions)
            self.stdout.write(self.style.NOTICE(f"Created {result['total_created']} AdministrativeRegion objects"))
            self.stdout.write(self.style.NOTICE(f"Updated {result['total_updated']} AdministrativeRegion objects"))
            self.stdout.write(self.style.NOTICE(f"Processed {result['total_processed']} AdministrativeRegion objects"))

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Running: etl_fetch_administrative_region_data'))

        administrative_levels_db = get_db()
        self.fetch_administrative_region(administrative_levels_db)

        self.stdout.write(self.style.SUCCESS('Successfully ran etl_fetch_administrative_region_data'))
