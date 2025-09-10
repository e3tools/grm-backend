import os

import shortuuid as uuid


def issue_attachment_upload_path(instance, filename):
    filename, file_extension = os.path.splitext(filename)
    filename = f"{uuid.uuid()}{file_extension}"
    return f"attachments/{filename}"
