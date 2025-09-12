import factory

from authentication.constants import ADL, MAJOR
from client import get_db


class CouchdbUser:
    def __init__(
        self,
        email,
        password,
        name,
        doc_type,
        is_active,
        photo,
        phone,
        birthday,
        data,
        doc,
    ):
        self.email = email
        self.password = password
        self.name = name
        self.doc_type = doc_type
        self.is_active = is_active
        self.photo = photo
        self.phone = phone
        self.birthday = birthday
        self.data = data
        self.doc = doc

    def __str__(self):
        return f"{self.email} {self.doc_type}"


class CouchdbUserFactory(factory.Factory):
    class Meta:
        model = CouchdbUser

    email = factory.Faker("email")
    password = ""
    name = factory.Faker("name")
    doc_type = factory.Iterator([ADL, MAJOR])
    is_active = True
    photo = factory.Faker("image_url")
    phone = factory.Faker("phone_number")
    birthday = factory.Faker("date_of_birth")

    @factory.lazy_attribute
    def data(self):
        return {
            "type": self.doc_type,
            "representative": {
                "email": self.email,
                "password": self.password,
                "name": self.name,
                "is_active": self.is_active,
                "photo": self.photo,
                "phone": self.phone,
                "birthday": str(self.birthday),
            },
        }

    @factory.lazy_attribute
    def doc(self):
        eadl_db = get_db()
        return eadl_db.create_document(self.data)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "authentication.User"

    email = factory.Faker("email")
    phone_number = factory.Faker("phone_number")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    grm_manager = False
