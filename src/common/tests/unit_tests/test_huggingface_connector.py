import json
from unittest import TestCase
from unittest.mock import patch

import requests
from django.conf import settings
from django.http import JsonResponse
from django.test import RequestFactory, override_settings
from rest_framework import status

from common.utils.huggingface_connector import (
    HuggingFaceConnectionError,
    HuggingFaceConnector,
    HuggingFaceConnectorManager,
    get_embedding,
)


class HuggingFaceConnectorTest(TestCase):

    def setUp(self):
        self.connector = HuggingFaceConnector(api_key="fake", model="test-model", timeout=1, max_retries=1)
        HuggingFaceConnectorManager.set_instance(self.connector)
        self.factory = RequestFactory()

    def tearDown(self):
        HuggingFaceConnectorManager.reset()

    @override_settings(HUGGINGFACE_API_KEY="settings_key", HUGGINGFACE_EMBEDDING_MODEL="settings_model")
    def test_settings_loading(self):
        connector = HuggingFaceConnector()
        self.assertEqual(connector.api_key, "settings_key")
        self.assertEqual(connector.model, "settings_model")

    @override_settings(HUGGINGFACE_API_KEY="")
    def test_missing_api_key_setting(self):
        with self.assertRaises(ValueError) as e:
            HuggingFaceConnector()
        self.assertIn("Hugging Face API key not found", str(e.exception))

    @override_settings(HUGGINGFACE_API_KEY="test_key", HUGGINGFACE_API_TIMEOUT=60, HUGGINGFACE_MAX_RETRIES=5)
    def test_optional_settings(self):
        self.assertEqual(settings.HUGGINGFACE_API_TIMEOUT, 60)
        self.assertEqual(settings.HUGGINGFACE_MAX_RETRIES, 5)

    @patch("common.utils.huggingface_connector.HuggingFaceConnector._make_request")
    def test_embedding_view_success(self, mock_make_request):
        sample_embedding = [0.1, 0.2, 0.3]
        mock_make_request.return_value = sample_embedding

        def embedding_view(request):
            text = request.GET.get("text", "")
            emb = get_embedding(text)
            return JsonResponse({"embedding": emb})

        request = self.factory.get("/embed", {"text": "hello world"})
        response = embedding_view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content.decode())
        self.assertEqual(data["embedding"], sample_embedding)
        mock_make_request.assert_called_once_with("hello world", "test-model")

    @patch("requests.Session.post")
    def test_make_request_timeout_raises_connection_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        with self.assertRaises(HuggingFaceConnectionError) as e:
            self.connector._make_request("hello")
        self.assertIn("timeout", str(e.exception).lower())

    @patch("requests.Session.post")
    def test_make_request_connection_error_raises_connection_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Network unreachable")
        with self.assertRaises(HuggingFaceConnectionError) as e:
            self.connector._make_request("hello")
        self.assertIn("connection error", str(e.exception).lower())

    @patch.object(HuggingFaceConnector, "_make_request")
    def test_get_embedding_fallback_also_fails(self, mock_make_request):
        mock_make_request.side_effect = HuggingFaceConnectionError("Primary model failed")
        with self.assertRaises(HuggingFaceConnectionError) as e:
            get_embedding("hello world", model="other-model")
        self.assertIn("Primary model failed", str(e.exception))
        self.assertGreaterEqual(mock_make_request.call_count, 1)

    @patch("requests.Session.post")
    def test_make_request_http_error_with_json(self, mock_post):
        response = requests.Response()
        response.status_code = status.HTTP_400_BAD_REQUEST
        response._content = b'{"error": "Invalid request"}'

        http_error = requests.exceptions.HTTPError(response=response)
        mock_post.return_value = response
        response.raise_for_status = lambda: (_ for _ in ()).throw(http_error)

        with self.assertRaises(Exception) as e:
            self.connector._make_request("hello")

        self.assertIn("HTTP error 400: Invalid request", str(e.exception))

    @patch("requests.Session.post")
    def test_make_request_http_error_with_text(self, mock_post):
        response = requests.Response()
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        response._content = b"Internal server error"

        http_error = requests.exceptions.HTTPError(response=response)
        mock_post.return_value = response
        response.raise_for_status = lambda: (_ for _ in ()).throw(http_error)

        with self.assertRaises(Exception) as e:
            self.connector._make_request("hello")

        self.assertIn("HTTP error 500", str(e.exception))
        self.assertIn("Internal server error", str(e.exception))

    @patch("requests.Session.post")
    def test_make_request_handles_rate_limit_retry(self, mock_post):
        first_response = requests.Response()
        first_response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        first_response.headers["Retry-After"] = "0"  # no wait
        first_response._content = b'{"error": "Rate limit"}'

        second_response = requests.Response()
        second_response.status_code = status.HTTP_200_OK
        second_response._content = b"[0.1, 0.2, 0.3]"

        mock_post.side_effect = [first_response, second_response]

        embedding = self.connector._make_request("hello")
        self.assertEqual(embedding, [0.1, 0.2, 0.3])

    @patch("requests.Session.post")
    def test_make_request_handles_model_loading_retry(self, mock_post):
        first_response = requests.Response()
        first_response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        first_response._content = b'{"error": "Model is loading", "estimated_time": 0}'

        second_response = requests.Response()
        second_response.status_code = status.HTTP_200_OK
        second_response._content = b"[0.5, 0.6, 0.7]"

        mock_post.side_effect = [first_response, second_response]

        embedding = self.connector._make_request("hello")
        self.assertEqual(embedding, [0.5, 0.6, 0.7])
