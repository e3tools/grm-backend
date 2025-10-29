import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch

from common.utils import pinecone_connector


class PineconeConnectorTest(TestCase):
    def setUp(self):
        # Reset singleton state
        pinecone_connector.PineconeConnector._instance = None
        pinecone_connector.PineconeConnector._client = None
        pinecone_connector.PineconeConnector._index = None

        # Mock Django settings
        patcher_settings = patch.object(pinecone_connector, "settings")
        self.mock_settings = patcher_settings.start()
        self.addCleanup(patcher_settings.stop)
        self.mock_settings.PINECONE_API_KEY = "fake-api-key"
        self.mock_settings.PINECONE_INDEX_NAME = "grm-grievances"

        # Mock Pinecone client + index
        self.mock_index = MagicMock()
        self.mock_client = MagicMock()
        self.mock_client.Index.return_value = self.mock_index

        patcher_pinecone = patch.object(pinecone_connector, "Pinecone", return_value=self.mock_client)
        patcher_pinecone.start()
        self.addCleanup(patcher_pinecone.stop)

    def test_initialize_connector_with_existing_index(self):
        self.mock_client.list_indexes.return_value = [{"name": "grm-grievances"}]
        connector = pinecone_connector.PineconeConnector()
        self.assertIsNotNone(connector._index)
        self.mock_client.Index.assert_called_with("grm-grievances")
        self.mock_client.create_index_for_model.assert_not_called()

    def test_initialize_connector_creates_index(self):
        self.mock_client.list_indexes.return_value = []
        pinecone_connector.PineconeConnector()
        self.mock_client.create_index_for_model.assert_called_once_with(
            name="grm-grievances",
            cloud="aws",
            region="us-east-1",
            embed={"model": "multilingual-e5-large", "field_map": {"text": "text"}},
        )

    def test_upsert_texts(self):
        self.mock_client.list_indexes.return_value = [{"name": "grm-grievances"}]
        connector = pinecone_connector.PineconeConnector()
        records = [{"id": "1", "text": "Test grievance"}]
        connector.upsert_texts("default", records)
        self.mock_index.upsert_records.assert_called_once_with(namespace="default", records=records)

    def test_delete_vectors(self):
        self.mock_client.list_indexes.return_value = [{"name": "grm-grievances"}]
        connector = pinecone_connector.PineconeConnector()
        connector.delete_vectors(["1", "2"], namespace="default")
        self.mock_index.delete.assert_called_once_with(ids=["1", "2"], namespace="default")

    def test_query_text(self):
        self.mock_client.list_indexes.return_value = [{"name": "grm-grievances"}]
        connector = pinecone_connector.PineconeConnector()
        # Mock response in SDK 7.3.0 format
        self.mock_index.search.return_value = {
            "result": {"hits": [{"_id": "1", "score": 0.95, "fields": {"description": "Test grievance"}}]}
        }
        results = connector.query_text("water issue", top_k=3, namespace="default")
        self.assertEqual(results[0]["_id"], "1")
        self.assertIn("fields", results[0])

    def test_get_index_stats(self):
        self.mock_client.list_indexes.return_value = [{"name": "grm-grievances"}]
        connector = pinecone_connector.PineconeConnector()
        self.mock_index.describe_index_stats.return_value = {
            "dimension": 1024,
            "total_vector_count": 10,
        }
        stats = connector.get_index_stats()
        self.assertEqual(stats["total_vector_count"], 10)


if __name__ == "__main__":
    unittest.main()
