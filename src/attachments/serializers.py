from django.conf import settings
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from dashboard.grm.constants import FILE_SIZE_ERROR_MESSAGE, MAX_UPLOAD_SIZE


class AuthMixinSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        if username != settings.COUCHDB_USERNAME or password != settings.COUCHDB_PASSWORD:
            raise serializers.ValidationError(self.default_error_messages.get("credentials"), code="authorization")

        return super().validate(attrs)

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.default_error_messages["credentials"] = _("Unauthorized access with the credentials provided.")


class FileSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if value.size > MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(self.default_error_messages["file_size"] % filesizeformat(value.size))
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.default_error_messages["file_size"] = FILE_SIZE_ERROR_MESSAGE


class TaskFileSerializer(AuthMixinSerializer, FileSerializer):
    doc_id = serializers.CharField()
    phase = serializers.IntegerField(min_value=1)
    task = serializers.IntegerField(min_value=1)
    attachment_id = serializers.CharField()


class AttachmentUpdateStatusSerializer(serializers.Serializer):
    ok = serializers.BooleanField(read_only=True)
    id = serializers.CharField(read_only=True)
    rev = serializers.CharField(read_only=True)


class GetAttachmentSerializer(serializers.Serializer):
    db = serializers.CharField(read_only=True, required=False)


class IssueFileSerializer(AuthMixinSerializer, FileSerializer):
    doc_id = serializers.CharField()
    attachment_id = serializers.CharField()
