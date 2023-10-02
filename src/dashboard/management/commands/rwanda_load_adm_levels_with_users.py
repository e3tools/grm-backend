import time
import pandas as pd
import logging
import os
from django.core.management.base import BaseCommand, CommandError
from client import bulk_update, get_db


class Command(BaseCommand):
    help = 'Loads administrative levels from csv file to CouchDB'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Absolute path to csv file')

    def handle(self, *args, **kwargs):
        eadl_db = get_db()
        file_path = kwargs['file_path']

        # Extract the directory path from the file_path
        log_directory = os.path.dirname(file_path)
        log_file_path = os.path.join(log_directory, 'import_log.txt')
        # Configure logging to save the log file in the same directory
        logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

        try:
            country_administrative_id = eadl_db.get_query_result(
                {
                    "type": 'administrative_level',
                    "parent_id": None,
                }
            )[:][0]['administrative_id']
        except Exception as e:
            raise CommandError(f'Failed to get country administrative level {e}')


        try:
            df = pd.read_csv(file_path)

            # Administrative level columns
            administrative_columns = ['District', 'Sector', 'Cell']

            # Create administrative levels
            created = 0
            docs_to_update = []
            # updated_value = 1
            for index, row in df.iterrows():
                # if updated_value > 2:
                #     break
                current_parent_id = country_administrative_id
                doc_data = row.to_dict()
                doc_data = {key.title(): value for key, value in doc_data.items()}  # Convert keys to lowercase
                try:
                    latitude = float(str(doc_data.get('Latitude', '0')).replace(',', '.'))
                    longitude = float(str(doc_data.get('Longitude', '0')).replace(',', '.'))
                except ValueError as e:
                    error_msg = f'Invalid value in line {index + 2} for latitude/longitude. {e}'
                    self.stdout.write(self.style.ERROR(error_msg))
                    logging.error(error_msg)
                    continue
                for administrative_level, name in doc_data.items():
                    if administrative_level.title() in administrative_columns and administrative_level.title() != "":
                        administrative_level_doc = eadl_db.get_query_result(
                            {
                                "type": 'administrative_level',
                                "name": ''.join(name.split()).title(),
                                "administrative_level": ''.join(administrative_level.split()).title(),
                                "parent_id": current_parent_id,
                            }
                        )[:]

                        if administrative_level_doc:
                            doc = administrative_level_doc[0]
                            to_update = not doc.get('latitude') or not doc.get('longitude')
                            if not doc.get('latitude'):
                                doc['latitude'] = latitude
                            if not doc.get('longitude'):
                                doc['longitude'] = longitude
                            if to_update:
                                docs_to_update.append(doc)
                        else:
                            doc = {
                                "type": 'administrative_level',
                                "administrative_id": str(time.time()).replace('.', ''),
                                "administrative_level": ''.join(administrative_level.split()).title(),
                                "name": ''.join(name.split()).title(),
                                "latitude": latitude,
                                "longitude": longitude,
                                "parent_id": current_parent_id,
                            }

                            eadl_db.create_document(doc)
                            created += 1

                        current_parent_id = doc['administrative_id']

                        if administrative_level.title() == 'Cell':
                            # check if user phone number doesn't exist
                            email_vice = f"0{doc_data.get('Telephone', '000')}@rbc.gov.rw"
                            if not eadl_db.get_query_result(
                                {
                                    "representative.email": email_vice
                                }
                            )[:]:
                                doc_app_user = {
                                    "type": "adl",
                                    "administrative_region": current_parent_id,
                                    "name": ''.join(doc_data.get('Cell', '').split()).title(),
                                    "photo": "",
                                    "location": {
                                        "lat": latitude,
                                        "long": longitude
                                    },
                                    "representative": {
                                        "email": email_vice,
                                        "password": "",
                                        "is_active": True,
                                        "name": doc_data.get('Name', '').title(),
                                        "telephone": f"0{doc_data.get('Telephone', '000')}",
                                        "national_id": f"{doc_data.get('Id No', '000')}",
                                        "chw_title": f"{doc_data.get('Chw Title', '000')}",
                                        "photo": "",
                                        "last_active": "null"
                                    },
                                    "phases": [],
                                    "department": 1,
                                    "administrative_level": "CELL",
                                    "unique_region": 1,
                                    "village_secretary": 1
                                }
                                eadl_db.create_document(doc_app_user)
                                log_msg = f"Created ADL for {doc_data.get('Name', '').title()}, email: {email_vice}, " \
                                          f"Cell: {doc_data.get('Cell', '').title()}, Sector: {doc_data.get('Sector', '').title()}, " \
                                          f"District: {doc_data.get('District', '').title()}" \
                                          f"Title: {doc_data.get('Chw Title', '').title()}" 
                                logging.info(log_msg)
                                self.stdout.write(self.style.SUCCESS(log_msg))


                # updated_value += 1

                updated = len(bulk_update(eadl_db, docs_to_update))

            self.stdout.write(self.style.SUCCESS(f'Successfully created {created} administrative levels'))
            self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated} administrative levels'))

            # Add logging for success messages
            logging.info(f'Successfully created {created} administrative levels')
            logging.info(f'Successfully updated {updated} administrative levels')

        except Exception as e:
            error_msg = f'Error: {e}'
            logging.error(error_msg)
            raise CommandError(error_msg)
