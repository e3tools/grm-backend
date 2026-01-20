"""
Pinecone Connector Service for GRM Platform
Compatible with pinecone==7.3.0

- Checks and creates the index with built-in inference if it doesn't exist
- Allows text upsertation (server-side embeddings)
- Vector deletion
- Semantic search
- Index statistics
"""

import logging
from typing import Any

from django.conf import settings
from pinecone import Pinecone

logger = logging.getLogger(__name__)


class PineconeConnector:
    _instance = None
    _client = None
    _index = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            try:
                api_key = settings.PINECONE_API_KEY
                index_name = settings.PINECONE_INDEX_NAME

                if not api_key:
                    raise ValueError("PINECONE_API_KEY is not configured")

                logger.info("Initializing Pinecone client (v7.3.0)...")
                self._client = Pinecone(api_key=api_key)

                # Ensure index exists (with integrated inference)
                self._ensure_index(index_name)

                # Connect to index
                self._index = self._client.Index(index_name)
                logger.info(f"Pinecone index '{index_name}' initialized successfully.")

            except Exception as e:
                logger.error(f"Error initializing Pinecone client: {str(e)}")
                raise

    def _ensure_index(self, index_name: str):
        """Ensure the index exists. If not, create it with integrated inference."""
        existing_indexes = [idx["name"] for idx in self._client.list_indexes()]
        if index_name in existing_indexes:
            logger.info(f"Index '{index_name}' already exists.")
            return

        logger.warning(f"Index '{index_name}' not found. Creating new index with integrated inference...")

        self._client.create_index_for_model(
            name=index_name,
            cloud="aws",
            region="us-east-1",
            embed={
                "model": "multilingual-e5-large",
                "field_map": {"text": "text"},
            },
        )
        logger.info(f"Index '{index_name}' created successfully with integrated inference.")

    def upsert_texts(self, namespace: str, records: list[dict[str, Any]]):
        """Upsert text documents into Pinecone (server-side embeddings)."""
        try:
            logger.info(f"Upserting {len(records)} records into namespace '{namespace}'...")
            result = self._index.upsert_records(namespace=namespace, records=records)
            logger.info("Upsert completed successfully.")
            return result
        except Exception as e:
            logger.error(f"Error during Pinecone upsert: {str(e)}")
            raise

    def delete_vectors(self, ids: list[str], namespace: str = None):
        """Delete vectors from Pinecone by their IDs."""
        try:
            ns = namespace or "default"
            logger.info(f"Deleting {len(ids)} vectors from namespace '{ns}'...")
            self._index.delete(ids=ids, namespace=ns)
            logger.info("Deletion completed successfully.")
        except Exception as e:
            logger.error(f"Error deleting vectors from Pinecone: {str(e)}")
            raise

    def query_text(self, query_text: str, top_k: int = 5, namespace: str = "default"):
        """Perform semantic search using Pinecone’s built-in embeddings."""
        try:
            logger.info(f"Performing semantic search for query: '{query_text[:50]}...'")
            response = self._index.search(
                namespace=namespace,
                query={"inputs": {"text": query_text}, "top_k": top_k},
            )
            result = response.get("result", {}) or {}
            hits = result.get("hits", [])
            logger.info(f"Semantic search returned {len(hits)} results.")
            return hits
        except Exception as e:
            logger.error(f"Error performing semantic search: {str(e)}")
            raise

    def get_index_stats(self) -> dict[str, Any]:
        """Retrieve Pinecone index statistics."""
        try:
            logger.info("Retrieving Pinecone index statistics...")
            stats = self._index.describe_index_stats()
            logger.info("Index statistics retrieved successfully.")
            return stats
        except Exception as e:
            logger.error(f"Error retrieving index stats: {str(e)}")
            raise
