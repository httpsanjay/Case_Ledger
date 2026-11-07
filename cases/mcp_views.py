import os
import secrets
from functools import wraps

from django.http import JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import Case, Document


# ============================================================
# MCP INTERNAL TOKEN AUTHENTICATION
# ============================================================

DJANGO_INTERNAL_TOKEN = os.environ.get("DJANGO_INTERNAL_TOKEN")


def mcp_internal_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if not DJANGO_INTERNAL_TOKEN:
            return JsonResponse({
                "success": False,
                "error": "MCP authentication is not configured."
            }, status=503)

        auth_header = request.headers.get("Authorization", "")
        expected_token = f"Token {DJANGO_INTERNAL_TOKEN}"

        if not secrets.compare_digest(auth_header, expected_token):
            return JsonResponse({
                "success": False,
                "error": "Invalid or missing authentication token."
            }, status=401)

        return view_func(request, *args, **kwargs)

    return wrapper


# ============================================================
# CASE ENDPOINTS
# ============================================================

@require_GET
@mcp_internal_required
def mcp_search_cases(request):

    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({
            "success": False,
            "error": "Search query is required."
        }, status=400)

    cases = Case.objects.filter(
        Q(case_number__icontains=query) |
        Q(title__icontains=query)
    ).order_by("-created_at")[:100]

    return JsonResponse({
        "success": True,
        "results": [
            {
                "id": case.id,
                "case_number": case.case_number,
                "title": case.title,
                "case_type": case.case_type,
                "status": case.status,
                "police_station": case.police_station_name,
                "created_at": case.created_at.isoformat(),
            }
            for case in cases
        ]
    })


@require_GET
@mcp_internal_required
def mcp_get_case(request, case_id):

    case = get_object_or_404(
        Case.objects.select_related(
            "created_by",
            "assigned_to",
            "police_station",
        ),
        pk=case_id
    )

    return JsonResponse({
        "success": True,
        "case": {
            "id": case.id,
            "case_number": case.case_number,
            "title": case.title,
            "case_type": case.case_type,
            "status": case.status,
            "description": case.description,
            "police_station": case.police_station_name,
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
            "created_by": (
                case.created_by.username if case.created_by else None
            ),
            "assigned_to": (
                case.assigned_to.username if case.assigned_to else None
            ),
        }
    })


@require_GET
@mcp_internal_required
def mcp_cases_count(request):

    return JsonResponse({
        "success": True,
        "count": Case.objects.count()
    })


# ============================================================
# DOCUMENT ENDPOINTS
# ============================================================

@require_GET
@mcp_internal_required
def mcp_search_documents(request):

    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({
            "success": False,
            "error": "Search query is required."
        }, status=400)

    documents = (
        Document.objects
        .filter(name__icontains=query)
        .select_related("case")
        .order_by("-created_at")[:100]
    )

    return JsonResponse({
        "success": True,
        "results": [
            {
                "id": document.id,
                "name": document.name,
                "document_type": document.document_type,
                "description": document.description,
                "case_id": document.case_id,
                "case_number": document.case.case_number,
            }
            for document in documents
        ]
    })


@require_GET
@mcp_internal_required
def mcp_get_document(request, document_id):

    document = get_object_or_404(
        Document.objects.select_related("case"),
        pk=document_id
    )

    return JsonResponse({
        "success": True,
        "document": {
            "id": document.id,
            "name": document.name,
            "document_type": document.document_type,
            "description": document.description,
            "case_id": document.case_id,
            "case_number": document.case.case_number,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
        }
    })


@require_GET
@mcp_internal_required
def mcp_get_case_documents(request, case_id):

    case = get_object_or_404(Case, pk=case_id)

    documents = case.documents.all().order_by("-created_at")[:100]

    return JsonResponse({
        "success": True,
        "case": {
            "id": case.id,
            "case_number": case.case_number,
            "title": case.title,
        },
        "documents": [
            {
                "id": document.id,
                "name": document.name,
                "document_type": document.document_type,
                "description": document.description,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
            }
            for document in documents
        ]
    })


# ============================================================
# RAG DATA ENDPOINT
# ============================================================

@require_GET
@mcp_internal_required
def mcp_case_rag_data(request, case_id):

    case = get_object_or_404(
        Case.objects.prefetch_related("documents__versions"),
        pk=case_id
    )

    documents = []

    for document in case.documents.all():

        for version in document.versions.all():

            if not version.extracted_text:
                continue

            documents.append({
                "document_id": document.id,
                "document_name": document.name,
                "document_type": document.document_type,
                "version_id": version.id,
                "version_number": version.version_number,
                "text": version.extracted_text,
            })

    return JsonResponse({
        "success": True,
        "case": {
            "id": case.id,
            "case_number": case.case_number,
            "title": case.title,
        },
        "documents": documents
    })