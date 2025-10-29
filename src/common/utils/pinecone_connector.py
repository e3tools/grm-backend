"""
Pinecone Connector Service for GRM Platform

This service abstracts all vector operations:
- Index creation and validation
- Upsert (insert/update) of grievance vectors
- Delete vectors by ID
- Semantic search using embeddings
- Retrieve index statistics

Dependencies:
- pinecone==7.3.0
- sentence-transformers==5.1.1
"""

import logging
from typing import Any

from django.conf import settings
from pinecone import Pinecone, ServerlessSpec

from .embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class PineconeConnector:
    """
    Service for managing vector operations using Pinecone.

    This class provides a high-level abstraction for all vector index operations
    used by the GRM platform, integrating seamlessly with the EmbeddingService.
    """

    _instance = None
    _client = None
    _index = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the Pinecone client and ensure the index exists."""
        if self._client is None:
            try:
                api_key = settings.PINECONE_API_KEY
                index_name = settings.PINECONE_INDEX_NAME
                environment = settings.PINECONE_ENVIRONMENT or "us-east-1"

                if not api_key:
                    raise ValueError("PINECONE_API_KEY is not configured")

                logger.info("Initializing Pinecone client...")
                self._client = Pinecone(api_key=api_key)

                self._ensure_index(index_name, environment)
                self._index = self._client.Index(index_name)
                logger.info(f"Pinecone index '{index_name}' initialized successfully.")

            except Exception as e:
                logger.error(f"Error initializing Pinecone client: {str(e)}")
                raise

    # def _ensure_index(self, index_name: str, environment: str):
    #     """
    #     Ensure that the target Pinecone index exists; create it if not.
    #     """
    #     try:
    #         existing_indexes = [idx["name"] for idx in self._client.list_indexes()]
    #         if index_name not in existing_indexes:
    #             embedding_service = EmbeddingService()
    #             dimension = embedding_service.get_dimension()
    #             logger.info(f"Creating new Pinecone index '{index_name}' with dimension {dimension}...")
    #             self._client.create_index(
    #                 name=index_name,
    #                 dimension=dimension,
    #                 metric="cosine",
    #                 spec=ServerlessSpec(cloud="aws", region=environment),
    #             )
    #     except Exception as e:
    #         logger.error(f"Error ensuring Pinecone index: {str(e)}")
    #         raise

    # def upsert_vectors(self, items: list[dict[str, Any]]):
    #     """
    #     Upsert (insert/update) vectors into Pinecone.

    #     Args:
    #         items: List of dictionaries, each with keys:
    #             - 'id': Unique identifier for the grievance
    #             - 'text': Text content to embed
    #             - 'metadata': Optional dictionary of metadata fields
    #     """
    #     try:
    #         embedding_service = EmbeddingService()
    #         vectors = []

    #         for item in items:
    #             vector = embedding_service.encode(item["text"])
    #             vectors.append({"id": str(item["id"]), "values": vector, "metadata": item.get("metadata", {})})

    #         self._index.upsert(vectors=vectors)
    #         logger.info(f"Upserted {len(vectors)} vectors into Pinecone index.")
    #     except Exception as e:
    #         logger.error(f"Error during Pinecone upsert: {str(e)}")
    #         raise

    # def delete_vectors(self, ids: list[str]):
    #     """
    #     Delete vectors from Pinecone by their IDs.
    #     """
    #     try:
    #         self._index.delete(ids=ids)
    #         logger.info(f"Deleted {len(ids)} vectors from Pinecone index.")
    #     except Exception as e:
    #         logger.error(f"Error deleting vectors from Pinecone: {str(e)}")
    #         raise

    # def semantic_search(self, query: str, top_k: int = 5, include_metadata: bool = True) -> list[dict[str, Any]]:
    #     """
    #     Perform semantic search against the Pinecone index.

    #     Args:
    #         query: Text query to search for
    #         top_k: Number of results to retrieve
    #         include_metadata: Whether to include stored metadata in the response

    #     Returns:
    #         List of matched results with similarity scores and metadata
    #     """
    #     try:
    #         embedding_service = EmbeddingService()
    #         query_vector = embedding_service.encode(query)

    #         results = self._index.query(vector=query_vector, top_k=top_k, include_metadata=include_metadata)

    #         matches = results.get("matches", [])
    #         logger.info(f"Semantic search completed with {len(matches)} results.")
    #         return matches
    #     except Exception as e:
    #         logger.error(f"Error performing semantic search: {str(e)}")
    #         raise

    # def get_index_stats(self) -> dict[str, Any]:
    #     """
    #     Retrieve Pinecone index statistics and status.
    #     """
    #     try:
    #         stats = self._index.describe_index_stats()
    #         logger.info("Retrieved Pinecone index statistics.")
    #         return stats
    #     except Exception as e:
    #         logger.error(f"Error retrieving index stats: {str(e)}")
    #         raise
