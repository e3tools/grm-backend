import logging

from django.db import transaction
from django.utils.timezone import localtime

from common.utils.pinecone_connector import PineconeConnector
from etl.management.commands.base_translated_command import TranslatedBaseCommand
from issues.models import Issue

logger = logging.getLogger(__name__)


class Command(TranslatedBaseCommand):
    help = "Upload confirmed Issue objects to Pinecone using server-side embeddings (SDK 7.3.0)."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100, help="Batch size (default: 100)")
        parser.add_argument("--limit", type=int, help="Optional: limit number of issues")
        parser.add_argument("--dry-run", action="store_true", help="Simulate upload without sending to Pinecone")
        parser.add_argument("--namespace", type=str, default="default", help="Target Pinecone namespace")

    @transaction.atomic
    def handle_translated(self, *args, **options):
        batch_size = options["batch_size"]
        limit = options.get("limit")
        dry_run = options["dry_run"]
        namespace = options["namespace"]

        self.stdout.write(self.style.NOTICE("Initializing Pinecone connector..."))
        connector = PineconeConnector()

        queryset = (
            Issue.objects.filter(confirmed=True, vectorized=False)
            .select_related(
                "administrative_region",
                "issue_type",
                "citizen__age_group",
                "citizen__group",
                "citizen__group_2",
            )
            .order_by("id")
        )

        if limit:
            queryset = queryset[:limit]

        total = queryset.count()
        self.stdout.write(self.style.NOTICE(f"Found {total} confirmed issues."))

        if not total:
            self.stdout.write(self.style.WARNING("No confirmed issues found."))
            return

        batch, processed = [], 0

        for issue in queryset.iterator():
            citizen = getattr(issue, "citizen", None)
            metadata = {
                "administrative_region_id": str(getattr(issue.administrative_region, "id", "")),
                "administrative_region_name": getattr(issue.administrative_region, "name", "") or "",
                "issue_type_id": str(getattr(issue.issue_type, "id", "")),
                "issue_type_name": getattr(issue.issue_type, "name", "") or "",
                "age_group_id": str(citizen.age_group.id) if citizen and citizen.age_group else "",
                "age_group_name": citizen.age_group.name if citizen and citizen.age_group else "",
                "group_id": str(citizen.group.id) if citizen and citizen.group else "",
                "group_name": citizen.group.name if citizen and citizen.group else "",
                "group_2_id": str(citizen.group_2.id) if citizen and citizen.group_2 else "",
                "group_2_name": citizen.group_2.name if citizen and citizen.group_2 else "",
                "issue_date": localtime(issue.issue_date).date().isoformat() if issue.issue_date else "",
                "description": issue.description or "",
            }

            # Text that Pinecone will automatically embed (integrated inference)
            text = " | ".join(
                filter(
                    None,
                    [
                        issue.description,
                        f"Administrative Level: {metadata['administrative_region_name']}",
                        f"Issue Type: {metadata['issue_type_name']}",
                        f"Age Group: {metadata['age_group_name']}",
                        f"Group: {metadata['group_name']}",
                        f"Group 2: {metadata['group_2_name']}",
                        f"Issue Date: {metadata['issue_date']}",
                    ],
                )
            )

            # Correct format for upsert_records in SDK 7.3.0
            record = {"id": str(issue.id), "text": text}
            record.update(metadata)
            batch.append(record)

            if len(batch) >= batch_size:
                self._process_batch(batch, connector, namespace, dry_run)
                processed += len(batch)
                self.stdout.write(self.style.SUCCESS(f"Processed {processed}/{total}"))
                batch = []

        if batch:
            self._process_batch(batch, connector, namespace, dry_run)
            processed += len(batch)

        if not dry_run:
            queryset.update(vectorized=True)

        self.stdout.write(self.style.SUCCESS(f"✅ Upload complete. Total processed: {processed}"))

    def _process_batch(self, batch, connector, namespace, dry_run):
        """Uploads a batch of issues to Pinecone using server-side embeddings."""
        try:
            if dry_run:
                for item in batch:
                    logger.info(f"DRY RUN → Would upload Issue {item['id']}: {item['values']['text'][:100]}...")
                return

            logger.info(f"Uploading batch of {len(batch)} records to Pinecone (namespace='{namespace}')...")
            connector.upsert_texts(namespace=namespace, records=batch)
            logger.info("Batch upload completed successfully.")
        except Exception as e:
            logger.error(f"Error uploading batch to Pinecone: {str(e)}")
            raise
