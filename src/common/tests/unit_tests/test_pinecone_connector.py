"""
Unit tests for PineconeConnector using unittest.TestCase and mocks.
Fully isolated — no real API key or network required.
"""

import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch

from common.utils import pinecone_connector


class PineconeConnectorTest(TestCase):

    def setUp(self):
        """Prepare mocks for Pinecone, EmbeddingService, and Django settings."""
        # Reset singleton
        pinecone_connector.PineconeConnector._instance = None
        pinecone_connector.PineconeConnector._client = None
        pinecone_connector.PineconeConnector._index = None

        # Mock Django settings
        patcher_settings = patch.object(pinecone_connector, "settings")
        self.mock_settings = patcher_settings.start()
        self.addCleanup(patcher_settings.stop)
        self.mock_settings.PINECONE_API_KEY = "fake-api-key"
        self.mock_settings.PINECONE_ENVIRONMENT = "fake-region"
        self.mock_settings.PINECONE_INDEX_NAME = "grm-grievances"

        # Mock Pinecone client and index
        self.mock_index = MagicMock()
        self.mock_client = MagicMock()
        self.mock_client.Index.return_value = self.mock_index
        self.mock_client.list_indexes.return_value = [{"name": "grm-grievances"}]

        # Patch Pinecone class
        patcher_pinecone = patch.object(pinecone_connector, "Pinecone", return_value=self.mock_client)
        patcher_pinecone.start()
        self.addCleanup(patcher_pinecone.stop)

        # Mock EmbeddingService
        self.mock_embedding_service = MagicMock()
        self.mock_embedding_service.encode.return_value = [0.1] * 384
        self.mock_embedding_service.get_dimension.return_value = 384
        patcher_embedding = patch.object(
            pinecone_connector, "EmbeddingService", return_value=self.mock_embedding_service
        )
        patcher_embedding.start()
        self.addCleanup(patcher_embedding.stop)

        # Initialize connector AFTER mocks
        self.connector = pinecone_connector.PineconeConnector()

    def test_initialize_pinecone_connector(self):
        """Test initialization and index setup."""
        self.assertIsNotNone(self.connector._client)
        self.assertIsNotNone(self.connector._index)
        self.mock_client.Index.assert_called_with("grm-grievances")

    def test_upsert_vectors(self):
        """Test vector upsert using mocked embedding service."""
        items = [
            {"id": "1", "text": "Test grievance", "metadata": {"category": "water"}},
            {"id": "2", "text": "Another grievance"},
        ]

        self.connector.upsert_vectors(items)

        self.mock_embedding_service.encode.assert_any_call("Test grievance")
        self.mock_index.upsert.assert_called_once()
        args, kwargs = self.mock_index.upsert.call_args
        self.assertEqual(len(kwargs["vectors"]), 2)

    def test_delete_vectors(self):
        """Test deletion of vectors by ID."""
        self.connector.delete_vectors(["1", "2"])
        self.mock_index.delete.assert_called_once_with(ids=["1", "2"])

    def test_semantic_search(self):
        """Test semantic search flow."""
        self.mock_index.query.return_value = {"matches": [{"id": "1", "score": 0.95}]}

        results = self.connector.semantic_search("water issue", top_k=3)

        self.assertIsInstance(results, list)
        self.assertEqual(results[0]["id"], "1")
        self.mock_index.query.assert_called_once()

    def test_get_index_stats(self):
        """Test retrieval of index statistics."""
        self.mock_index.describe_index_stats.return_value = {
            "dimension": 384,
            "total_vector_count": 10,
        }

        stats = self.connector.get_index_stats()

        self.assertIn("dimension", stats)
        self.assertEqual(stats["total_vector_count"], 10)
        self.mock_index.describe_index_stats.assert_called_once()


if __name__ == "__main__":
    unittest.main()
