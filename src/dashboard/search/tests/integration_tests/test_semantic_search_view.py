from unittest.mock import patch

from django.urls import reverse

from dashboard.search.views import SemanticSearchView
from grm.constants import OPENED_CHOICE
from grm.tests.base import DashboardTestCase
from grm.utils import reset_sequences
from issues.factories import IssueFactory, IssueStatusFactory


class SemanticSearchViewTest(DashboardTestCase):
    """Integration tests for SemanticSearchView using a mocked PineconeConnector."""

    def setUp(self):
        super().setUp()
        reset_sequences()
        self.url = reverse("dashboard:search:semantic_search")
        status = IssueStatusFactory(name=OPENED_CHOICE)
        issues = IssueFactory.create_batch(2, administrative_region=self.root_region, status=status, confirmed=True)
        # Mock results in Pinecone 7.3.0 format: _id + fields
        self.mock_results = [
            {
                "_id": str(issues[0].id),
                "score": 0.98,
                "fields": {
                    "description": "Water supply issue",
                    "issue_date": "2024-03-01",
                    "administrative_region_id": "1",
                    "issue_type_id": "1",
                },
            },
            {
                "_id": str(issues[1].id),
                "score": 0.91,
                "fields": {
                    "description": "Electricity complaint",
                    "issue_date": "2024-03-02",
                    "administrative_region_id": "1",
                    "issue_type_id": "2",
                },
            },
        ]

    @patch.object(SemanticSearchView, "connector")
    def test_initial_load_no_query(self, mock_connector):
        """Should render full template with no search performed."""
        response = self.get(self.url)

        assert response.status_code == 200
        ctx = self.get_context(response)
        assert "search_active" in ctx
        assert not ctx.get("search_active", False)
        mock_connector.query_text.assert_not_called()

        # Ensure the full template (semantic_search.html) was rendered
        template_names = [t.name for t in response.templates if t.name]
        assert any("semantic_search.html" in name for name in template_names)

    @patch.object(SemanticSearchView, "connector")
    def test_semantic_search_with_query(self, mock_connector):
        """Should render results using Pinecone mock."""
        mock_connector.query_text.return_value = self.mock_results

        response = self.get(self.url, data={"q": "water issue"})

        assert response.status_code == 200
        ctx = self.get_context(response)
        assert ctx.get("search_active", False)
        assert ctx.get("total_results", 0) == len(self.mock_results)
        mock_connector.query_text.assert_called_once_with(query_text="water issue", top_k=100)

    @patch.object(SemanticSearchView, "connector")
    def test_htmx_initial_request(self, mock_connector):
        """Should return search container partial on first HTMX search."""
        mock_connector.query_text.return_value = self.mock_results

        response = self.get(
            self.url,
            data={"q": "water issue"},
            ajax=True,
            **{"HTTP_HX-Request": "true", "HTTP_HX-Target": "search-container"},
        )

        assert response.status_code == 200
        template_names = [t.name for t in response.templates if t.name]
        assert any("search/_search_container.html" in name for name in template_names)
        mock_connector.query_text.assert_called_once()

    @patch.object(SemanticSearchView, "connector")
    def test_htmx_results_request(self, mock_connector):
        """Should return only the results partial on subsequent HTMX requests."""
        mock_connector.query_text.return_value = self.mock_results

        response = self.get(
            self.url,
            data={"q": "water issue"},
            ajax=True,
            **{"HTTP_HX-Request": "true", "HTTP_HX-Target": "results"},
        )

        assert response.status_code == 200
        template_names = [t.name for t in response.templates if t.name]
        assert any("search/_results.html" in name for name in template_names)
        mock_connector.query_text.assert_called_once()
