import logging
import time
from typing import Any

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up module-level logger
logger = logging.getLogger(__name__)


# Custom exception raised when connection to Hugging Face fails
class HuggingFaceConnectionError(Exception):
    pass


# Custom exception raised when Hugging Face returns an unexpected or error response
class HuggingFaceAPIError(Exception):
    pass


class HuggingFaceConnector:
    """
    A connector class to interact with Hugging Face's inference API for embedding generation.
    Handles retries, timeouts, and error parsing.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = 30,
        max_retries: int = 3,
        session: requests.Session | None = None,
    ):
        """
        Initializes the connector with API credentials, model, and session configuration.
        """
        self.api_key = api_key or self._get_api_key()
        self.model = model or self._get_default_model()
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = settings.HUGGINGFACE_API_BASE_URL
        self.session = session or self._setup_session()
        logger.info(f"HuggingFace connector initialized with model: {self.model}")

    def _get_api_key(self) -> str:
        """
        Retrieves the API key from Django settings.
        Raises an error if not found.
        """
        api_key = settings.HUGGINGFACE_API_KEY
        if not api_key:
            raise ValueError("Hugging Face API key not found. Please set HUGGINGFACE_API_KEY.")
        return api_key

    def _get_default_model(self) -> str:
        """
        Retrieves the default embedding model from Django settings.
        """
        return settings.HUGGINGFACE_EMBEDDING_MODEL

    def _setup_session(self) -> requests.Session:
        """
        Configures a requests session with retry logic and headers.
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
            backoff_factor=1,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update(
            {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
        )
        return session

    def _make_request(self, text: str, model: str | None = None) -> list[float]:
        """
        Sends a POST request to Hugging Face's API to retrieve embeddings for the given text.
        Handles retry-after and model loading delays.
        """
        model_to_use = model or self.model
        url = f"{self.base_url}/{model_to_use}"
        payload = {"inputs": text}

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                time.sleep(retry_after)
                return self._make_request(text, model)

            # Handle model loading delay
            if response.status_code == 503:
                error_data = response.json()
                if 'loading' in error_data.get('error', '').lower():
                    estimated_time = error_data.get('estimated_time', 30)
                    time.sleep(estimated_time)
                    return self._make_request(text, model)

            response.raise_for_status()
            embeddings = response.json()

            # Validate response format
            if not isinstance(embeddings, list) or not embeddings:
                raise HuggingFaceAPIError(f"Unexpected response format: {embeddings}")

            return embeddings[0] if isinstance(embeddings[0], list) else embeddings

        except requests.exceptions.Timeout:
            raise HuggingFaceConnectionError(f"Request timeout after {self.timeout} seconds")
        except requests.exceptions.ConnectionError as e:
            raise HuggingFaceConnectionError(f"Connection error: {str(e)}")
        except requests.exceptions.HTTPError as e:
            resp = e.response
            status_code = resp.status_code if resp else "unknown"
            error_msg = f"HTTP error {status_code}"
            if resp:
                try:
                    error_details = resp.json()
                    error_msg += f": {error_details.get('error', resp.text)}"
                except Exception:
                    error_msg += f": {resp.text}"
            raise HuggingFaceAPIError(error_msg) from e

    def get_embedding(self, text: str, model: str | None = None, fallback_to_default: bool = True) -> list[float]:
        """
        Retrieves a single embedding for the given text.
        Optionally falls back to the default model if the specified one fails.
        """
        if not text or not isinstance(text, str):
            raise ValueError("Text must be a non-empty string")
        text = text.strip()
        if not text:
            raise ValueError("Text cannot be empty after stripping")

        max_length = 512
        if len(text) > max_length * 4:
            text = text[: max_length * 4]

        model_to_try = model or self.model
        try:
            return self._make_request(text, model_to_try)
        except (HuggingFaceConnectionError, HuggingFaceAPIError) as e:
            if fallback_to_default and model and model != self.model:
                try:
                    return self._make_request(text, self.model)
                except Exception as fallback_error:
                    raise fallback_error
            else:
                raise e

    def get_embeddings_batch(
        self, texts: list[str], model: str | None = None, batch_size: int = 10
    ) -> list[list[float]]:
        """
        Retrieves embeddings for a batch of texts.
        Handles batching and error fallback per item.
        """
        if not texts:
            return []

        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            for text in batch:
                try:
                    embedding = self.get_embedding(text, model)
                    embeddings.append(embedding)
                except Exception:
                    embeddings.append([])
            if i + batch_size < len(texts):
                time.sleep(0.1)  # Prevent rate limiting
        return embeddings

    def health_check(self) -> dict[str, Any]:
        """
        Performs a basic health check by requesting an embedding for a test string.
        Returns diagnostic info.
        """
        try:
            test_embedding = self.get_embedding("Health check test")
            return {
                'status': 'healthy',
                'model': self.model,
                'embedding_dimension': len(test_embedding),
                'test_successful': True,
            }
        except Exception as e:
            return {'status': 'unhealthy', 'model': self.model, 'error': str(e), 'test_successful': False}


class HuggingFaceConnectorManager:
    """
    Singleton manager for HuggingFaceConnector.
    Ensures a single shared instance across the application.
    """

    _instance: HuggingFaceConnector | None = None

    @classmethod
    def get_instance(cls) -> HuggingFaceConnector:
        if cls._instance is None:
            cls._instance = HuggingFaceConnector()
        return cls._instance

    @classmethod
    def set_instance(cls, connector: HuggingFaceConnector):
        cls._instance = connector

    @classmethod
    def reset(cls):
        cls._instance = None


def get_embedding(text: str, model: str | None = None) -> list[float]:
    """
    Convenience function to get an embedding using the singleton connector.
    """
    return HuggingFaceConnectorManager.get_instance().get_embedding(text, model)


def get_connector() -> HuggingFaceConnector:
    """
    Returns the singleton connector instance.
    """
    return HuggingFaceConnectorManager.get_instance()
