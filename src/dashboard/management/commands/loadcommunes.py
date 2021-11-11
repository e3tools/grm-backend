import csv

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from client import get_db


class Command(BaseCommand):
    help = 'Loads communes from csv file to CouchDB'

    def handle(self, *args, **options):
        eadl_db = get_db()

        file_path = f'{settings.BASE_DIR.parent}/data/communes.csv'
        fields = ['region', 'prefecture', 'administrative_id', 'name', 'type_cl', 'population']

        try:
            with open(file_path, newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',', quotechar='"')
                next(reader, None)  # skip header
                count = 0
                for row in reader:
                    row.pop(0)
                    doc = dict(zip(fields, row))
                    doc['population'] = int(doc['population'])
                    doc['administrative_level'] = 'commune'
                    doc['type'] = 'administrative_level'
                    doc['parent_id'] = None
                    eadl_db.create_document(doc)
                    count += 1

            self.stdout.write(self.style.SUCCESS(f'Successfully uploaded {count} communes'))
        except Exception as e:
            raise CommandError(f'Failed to upload communes {e}')
