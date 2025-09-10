from django.core.files.base import ContentFile
from django.core.files.storage import Storage


class InMemoryStorage(Storage):
    def _open(self, name, mode='rb'):
        return ContentFile(b"")

    def _save(self, name, content):
        return name

    def exists(self, name):
        return False

    def url(self, name):
        return f"/media/{name}"
