import os

import shortuuid as uuid
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from authentication.models import User
from grm.utils import filesizeformat_en
from issues.models import Issue


def issue_attachment_upload_path(instance, filename):
    filename, file_extension = os.path.splitext(filename)
    filename = f"{uuid.uuid()}{file_extension}"
    return f"attachments/{filename}"


class IssueAttachment(models.Model):
    external_id = models.CharField(
        max_length=255, verbose_name="couchDB document _id", default=None, null=True, blank=True
    )
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='attachments', verbose_name=_('Issue'))
    file = models.FileField(
        upload_to=issue_attachment_upload_path, verbose_name='File', help_text=_('File attached to the issue')
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attachments',
        verbose_name=_('Uploaded by'),
    )
    created_date = models.DateTimeField(default=now, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _('Issue Attachment')
        verbose_name_plural = _('Attachments')
        ordering = ['-created_date']
        indexes = [
            models.Index(fields=['issue', 'created_date']),
            models.Index(fields=['uploaded_by']),
        ]

    def __str__(self):
        return f"{self.filename} - Issue #{self.issue.id}"

    def delete(self, *args, **kwargs):
        """
        Deletes the file when the record is deleted
        """
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)

    @property
    def filename(self):
        """
        Returns the original filename
        """
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def file_extension(self):
        """
        Returns the file extension
        """
        return os.path.splitext(self.file.name)[1].lower() if self.file else ''

    @property
    def file_size(self):
        """
        Returns the file size in bytes
        """
        return self.file.size if self.file else 0

    @property
    def formatted_file_size(self):
        """
        Returns the formatted file size in English (MB, GB, etc.)
        """
        return filesizeformat_en(self.file_size)

    @property
    def file_type(self):
        """
        Returns the file MIME type
        """
        if not self.file:
            return ''

        import mimetypes

        mime_type, _ = mimetypes.guess_type(self.file.name)
        return mime_type or 'application/octet-stream'
