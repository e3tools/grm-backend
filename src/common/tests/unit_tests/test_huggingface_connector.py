import json
from unittest import TestCase
from unittest.mock import patch

import requests
from django.conf import settings
from django.http import JsonResponse
from django.test import RequestFactory, override_settings

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

        self.assertEqual(response.status_code, 200)
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
