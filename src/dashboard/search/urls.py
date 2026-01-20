from django.urls import path

from dashboard.search.views import SemanticSearchView

app_name = "search"
urlpatterns = [
    path("", SemanticSearchView.as_view(), name="semantic_search"),
]
