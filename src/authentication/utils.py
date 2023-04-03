import os
import zlib
from django.utils.text import slugify
import shortuuid as uuid
from client import bulk_update, get_db
from authentication.models import GovernmentWorker, User


def photo_path(instance, filename):
    filename, file_extension = os.path.splitext(filename)
    filename = '{}{}'.format(uuid.uuid(), file_extension)
    return 'photos/{}'.format(filename)


def get_validation_code(seed):
    return str(zlib.adler32(str(seed).encode('utf-8')))[:6]

def create_government_workers():
    eadl_db = get_db()
    # working with district
    districts = eadl_db.get_query_result(
        {
            "type": 'administrative_level',
            "administrative_level": "DISRICT",
        }
    )

    for district in districts:
        try:
            user_1 = User.objects.create(
                email='doh_rusizi.' + slugify(district["name"]) + '@rbc.gov.rw',
                phone_number='0788888888',
                password='123Qwerty',
            )
            user_1.set_password('123Qwerty')
            user_2 = User.objects.create(
                email='hpro.' + slugify(district["name"]) + '@rbc.gov.rw',
                phone_number='0788888888',
                password='123Qwerty',
            )
            user_2.set_password('123Qwerty')
            GovernmentWorker.objects.create(
                user=user_1,
                department=1,
                administrative_id=district["administrative_id"]
            )
            GovernmentWorker.objects.create(
                user=user_2,
                department=1,
                administrative_id=district["administrative_id"]
            )
        except Exception as e:
            print(e)
            pass
        sectors = eadl_db.get_query_result(
            {
                "type": 'administrative_level',
                "administrative_level": "SECTOR",
                "parent_id": district["administrative_id"]
            }
        )

        for sector in sectors:
            try:
                print(sector["name"], district['name'])
                user_sector_1 = User.objects.create(
                    email='hohc.' + slugify(sector["name"]) + '.' + slugify(district['name']) + '@rbc.gov.rw',
                    phone_number='0788888888'
                )
                user_sector_1.set_password('123Qwerty')
                user_sector_2 = User.objects.create(
                    email='ceho.' + slugify(sector["name"]) + '.' + slugify(district['name']) + '@rbc.gov.rw',
                    phone_number='0788888888',
                )
                user_sector_2.set_password('123Qwerty')
                GovernmentWorker.objects.create(
                    user=user_sector_1,
                    department=1,
                    administrative_id=sector["administrative_id"]
                )
                GovernmentWorker.objects.create(
                    user=user_sector_2,
                    department=1,
                    administrative_id=sector["administrative_id"]
                )
            except Exception as e:
                print(e)
                pass