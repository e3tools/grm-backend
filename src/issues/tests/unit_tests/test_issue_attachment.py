import os

import pytest
from django.test import TestCase

from issues.models import issue_attachment_upload_path


@pytest.mark.django_db
class IssueAttachmentHelpersTest(TestCase):
    def test_issue_attachment_upload_path_keeps_extension_and_uses_attachments_folder(self):
        generated_path = issue_attachment_upload_path(instance=None, filename="evidence-photo.JPG")

        directory, generated_name = os.path.split(generated_path)
        stem, extension = os.path.splitext(generated_name)

        assert directory == "attachments"
        assert extension == ".JPG"
        assert len(stem) == 22
