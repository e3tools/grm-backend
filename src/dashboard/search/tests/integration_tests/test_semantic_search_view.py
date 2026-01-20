from datetime import date
from unittest.mock import patch

from django.urls import reverse

from dashboard.search.views import SemanticSearchView
from grm.tests.base import DashboardTestCase
from grm.utils import reset_sequences
from issues.factories import (
    CitizenAgeGroupFactory,
    CitizenFactory,
    CitizenGroupFactory,
    IssueFactory,
    IssueStatusFactory,
    IssueTypeFactory,
)
from issues.models import IssueStatus


class SemanticSearchViewTest(DashboardTestCase):
    """Integration tests for SemanticSearchView using a mocked PineconeConnector."""

    def setUp(self):
        super().setUp()
        reset_sequences()
        self.url = reverse("dashboard:search:semantic_search")

        IssueStatus.objects.all().delete()
        self.status = IssueStatusFactory(id=1)
        self.type1 = IssueTypeFactory(name="Water")
        self.type2 = IssueTypeFactory(name="Electricity")

        self.age_group = CitizenAgeGroupFactory(name="Adults")
        self.group = CitizenGroupFactory(name="Group A")
        self.group_2 = CitizenGroupFactory(name="Group B")

        # Citizens with age groups and groups
        self.citizen = CitizenFactory(age_group=self.age_group, group=self.group, group_2=self.group_2)

        self.issue_match = IssueFactory(
            administrative_region=self.root_region,
            issue_type=self.type1,
            status=self.status,
            citizen=self.citizen,
            confirmed=True,
            issue_date=date(2024, 3, 1),
        )

        self.issue_nonmatch = IssueFactory(
            administrative_region=self.root_region,
            issue_type=self.type2,
            status=self.status,
            confirmed=True,
            issue_date=date(2023, 1, 1),
        )

        self.mock_results = [
            {
                "_id": str(self.issue_match.id),
                "score": 0.98,
                "fields": {
                    "description": "Water supply issue",
                    "issue_date": "2024-03-01",
                    "administrative_region_id": str(self.root_region.id),
                    "issue_type_id": str(self.type1.id),
                    "age_group_id": str(self.age_group.id),
                    "group_id": str(self.group.id),
                    "group_2_id": str(self.group_2.id),
                },
            },
            {
                "_id": str(self.issue_nonmatch.id),
                "score": 0.90,
                "fields": {
                    "description": "Electricity complaint",
                    "issue_date": "2023-01-01",
                    "administrative_region_id": str(self.root_region.id),
                    "issue_type_id": str(self.type2.id),
                },
            },
        ]

    @patch.object(SemanticSearchView, "connector")
    def test_semantic_search_with_filters_applied(self, mock_connector):
        """Should correctly apply query and filters, returning only matching items."""
        mock_connector.query_text.return_value = self.mock_results

        filters = {
            "q": "water",
            "administrative_region": str(self.root_region.id),
            "issue_type": str(self.type1.id),
            "age_group": str(self.age_group.id),
            "group": str(self.group.id),
            "group_2": str(self.group_2.id),
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "page": 1,
            "per_page": 10,
        }

        response = self.get(self.url, data=filters)
        assert response.status_code == 200

        ctx = self.get_context(response)

        # ✅ 1. Verify context variables
        assert ctx["query"] == filters["q"]
        assert ctx["search_active"] is True
        assert ctx["filters"]["administrative_region"] == filters["administrative_region"]
        assert ctx["filters"]["issue_type"] == filters["issue_type"]
        assert ctx["filters"]["age_group"] == filters["age_group"]
        assert ctx["filters"]["group"] == filters["group"]
        assert ctx["filters"]["group_2"] == filters["group_2"]
        assert ctx["filters"]["start_date"] == filters["start_date"]
        assert ctx["filters"]["end_date"] == filters["end_date"]

        # ✅ 2. Verify filtering worked — only 1 result should match
        assert ctx["total_results"] == 1
        page_obj = ctx["page_obj"]
        assert len(page_obj.object_list) == 1

        result = page_obj.object_list[0]
        assert result["_id"] == str(self.issue_match.id)
        assert "Water supply issue" in result["fields"]["description"]

        # ✅ 3. Ensure Pinecone was called once
        mock_connector.query_text.assert_called_once_with(query_text="water", top_k=100)
