from django.urls import path

from . import mcp_views


urlpatterns = [
    path(
        "cases/search/",
        mcp_views.mcp_search_cases,
        name="mcp_cases_search",
    ),

    path(
        "cases/count/",
        mcp_views.mcp_cases_count,
        name="mcp_cases_count",
    ),

    path(
        "cases/<int:case_id>/",
        mcp_views.mcp_get_case,
        name="mcp_get_case",
    ),

    path(
        "cases/<int:case_id>/documents/",
        mcp_views.mcp_get_case_documents,
        name="mcp_case_documents",
    ),

    path(
        "documents/search/",
        mcp_views.mcp_search_documents,
        name="mcp_documents_search",
    ),

    path(
        "documents/<int:document_id>/",
        mcp_views.mcp_get_document,
        name="mcp_get_document",
    ),
    path(
        "cases/<int:case_id>/rag-data/",
        mcp_views.mcp_case_rag_data,
        name="mcp_case_rag_data",
    ),

]