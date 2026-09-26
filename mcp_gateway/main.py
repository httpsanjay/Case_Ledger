import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier


# ============================================================
# Configuration
# ============================================================

load_dotenv()

MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN")

if not MCP_AUTH_TOKEN:
    raise RuntimeError("MCP_AUTH_TOKEN is not configured.")




MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))

# Local:
# DJANGO_URL=http://localhost:8000
#
# Docker:
# DJANGO_URL=http://django:8000

DJANGO_URL = os.getenv(
    "DJANGO_URL",
    "http://localhost:8000",
).rstrip("/")


# ============================================================
# MCP Authentication
# ============================================================

auth = StaticTokenVerifier(
    tokens={
        MCP_AUTH_TOKEN: {
            "client_id": "nyayavault-mcp-client",
            "scopes": [
                "cases:read",
                "documents:read",
            ],
        }
    }
)


# ============================================================
# FastMCP Server
# ============================================================

mcp = FastMCP(
    name="NyayaVault MCP",

    instructions="""
NyayaVault MCP provides controlled access to legal and
investigation case information.

Available capabilities:

- Search cases
- Retrieve case metadata
- Search documents
- Retrieve document metadata
- List documents associated with a case
- Ask questions using authorized case information
- Generate structured case-analysis prompts

Security rules:

- Never invent case information.
- Never expose information not returned by Django.
- Treat all case and document information as confidential.
- Do not bypass Django authorization.
- Do not infer missing facts.
- RAG retrieval and authorization are performed by Django.
""",

    auth=auth,
)


# ============================================================
# Django HTTP Helper
# ============================================================

async def django_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:

    url = f"{DJANGO_URL}{path}"

    try:
        async with httpx.AsyncClient(
            timeout=60.0,
        ) as client:

            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json,
            )

        response.raise_for_status()

        return response.json()

    except httpx.HTTPStatusError as exc:

        return {
            "success": False,
            "error": (
                f"Django returned HTTP "
                f"{exc.response.status_code}"
            ),
        }

    except httpx.RequestError as exc:

        return {
            "success": False,
            "error": (
                "Unable to connect to Django: "
                f"{exc}"
            ),
        }

    except ValueError:

        return {
            "success": False,
            "error": "Django returned invalid JSON.",
        }


# ============================================================
# Input Validation
# ============================================================

def clean_query(query: str) -> str:

    if not isinstance(query, str):
        raise ValueError("Query must be a string.")

    query = query.strip()

    if not query:
        raise ValueError(
            "Search query cannot be empty."
        )

    if len(query) > 500:
        raise ValueError(
            "Search query is too long."
        )

    return query


def validate_id(value: int, name: str) -> int:

    if not isinstance(value, int) or value <= 0:
        raise ValueError(
            f"{name} must be a positive integer."
        )

    return value


def validate_top_k(top_k: int) -> int:

    if not isinstance(top_k, int):
        raise ValueError(
            "top_k must be an integer."
        )

    if top_k <= 0:
        raise ValueError(
            "top_k must be positive."
        )

    if top_k > 20:
        raise ValueError(
            "top_k cannot be greater than 20."
        )

    return top_k


# ============================================================
# CASE TOOLS
# ============================================================

@mcp.tool(
    name="search_cases",
    title="Search Cases",
    description=(
        "Search NyayaVault cases using a case number "
        "or partial case-number query."
    ),
)
async def search_cases(
    query: str,
) -> dict[str, Any]:

    query = clean_query(query)

    return await django_request(
        "GET",
        "/internal/mcp/cases/search/",
        params={
            "q": query,
        },
    )


@mcp.tool(
    name="get_case",
    title="Get Case",
    description=(
        "Retrieve case metadata using the internal "
        "case ID."
    ),
)
async def get_case(
    case_id: int,
) -> dict[str, Any]:

    case_id = validate_id(case_id, "case_id")

    return await django_request(
        "GET",
        f"/internal/mcp/cases/{case_id}/",
    )


@mcp.tool(
    name="get_cases_count",
    title="Get Cases Count",
    description=(
        "Return the total number of NyayaVault cases."
    ),
)
async def get_cases_count() -> dict[str, Any]:

    return await django_request(
        "GET",
        "/internal/mcp/cases/count/",
    )


# ============================================================
# DOCUMENT TOOLS
# ============================================================

@mcp.tool(
    name="search_documents",
    title="Search Documents",
    description=(
        "Search NyayaVault documents by document name."
    ),
)
async def search_documents(
    query: str,
) -> dict[str, Any]:

    query = clean_query(query)

    return await django_request(
        "GET",
        "/internal/mcp/documents/search/",
        params={
            "q": query,
        },
    )


@mcp.tool(
    name="get_document",
    title="Get Document",
    description=(
        "Retrieve metadata for a NyayaVault document."
    ),
)
async def get_document(
    document_id: int,
) -> dict[str, Any]:

    document_id = validate_id(
        document_id,
        "document_id",
    )

    return await django_request(
        "GET",
        f"/internal/mcp/documents/{document_id}/",
    )


@mcp.tool(
    name="get_case_documents",
    title="Get Case Documents",
    description=(
        "List documents associated with a specific "
        "NyayaVault case."
    ),
)
async def get_case_documents(
    case_id: int,
) -> dict[str, Any]:

    case_id = validate_id(
        case_id,
        "case_id",
    )

    return await django_request(
        "GET",
        f"/internal/mcp/cases/{case_id}/documents/",
    )


# ============================================================
# RAG TOOL
# ============================================================

@mcp.tool(
    name="ask_case_question",
    title="Ask Case Question",
    description=(
        "Ask a question about an authorized NyayaVault "
        "case. Django performs authorization, semantic "
        "retrieval, and answer generation using RAG."
    ),
)
async def ask_case_question(
    case_id: int,
    question: str,
    top_k: int = 5,
) -> dict[str, Any]:

    case_id = validate_id(
        case_id,
        "case_id",
    )

    question = clean_query(question)

    top_k = validate_top_k(top_k)

    return await django_request(
        "POST",
        f"/internal/mcp/cases/{case_id}/ask/",
        json={
            "question": question,
            "top_k": top_k,
        },
    )


# ============================================================
# PROMPTS
# ============================================================

@mcp.prompt(
    name="summarize_case",
    title="Summarize Case",
    description=(
        "Generate a structured prompt for summarizing "
        "a NyayaVault case."
    ),
)
def summarize_case(
    case_information: str,
) -> str:

    return f"""
You are assisting with a legal/investigation case review.

Analyze ONLY the information provided below.

CASE INFORMATION:
{case_information}

Produce a structured summary containing:

1. Case identification
2. Current status
3. Key known facts
4. Important people or entities mentioned
5. Chronological events
6. Available evidence
7. Missing information
8. Important uncertainties

Rules:

- Do not invent facts.
- Do not infer facts that are not explicitly provided.
- Clearly distinguish known facts from missing information.
- Do not make a legal judgment.
- Do not fabricate evidence.
"""


@mcp.prompt(
    name="analyze_case",
    title="Analyze Case",
    description=(
        "Generate a structured analytical prompt for "
        "reviewing a case."
    ),
)
def analyze_case(
    case_information: str,
) -> str:

    return f"""
You are assisting an authorized investigator reviewing
a legal/investigation case.

CASE INFORMATION:
{case_information}

Perform a structured factual analysis.

Identify:

1. Established facts
2. Claims or allegations
3. Supporting evidence
4. Evidence gaps
5. Contradictions
6. Timeline inconsistencies
7. Missing information
8. Questions requiring further investigation

Important constraints:

- Use only the supplied information.
- Do not invent facts.
- Do not assume that an allegation is true.
- Do not provide a final legal conclusion.
- Clearly identify uncertainty.
- Separate evidence from interpretation.
"""


@mcp.prompt(
    name="review_evidence",
    title="Review Evidence",
    description=(
        "Generate a structured prompt for reviewing "
        "case evidence."
    ),
)
def review_evidence(
    evidence_information: str,
) -> str:

    return f"""
Review the following evidence information:

{evidence_information}

Analyze it using these categories:

1. Evidence identified
2. Source of each item
3. What each item establishes
4. Information that remains unverified
5. Contradictions between items
6. Missing evidence
7. Questions that should be investigated

Rules:

- Do not invent evidence.
- Do not modify the meaning of the supplied information.
- Do not assume authenticity unless explicitly established.
- Clearly identify uncertainty.
- Do not provide a final legal determination.
"""


@mcp.prompt(
    name="find_contradictions",
    title="Find Contradictions",
    description=(
        "Generate a structured prompt for identifying "
        "potential contradictions."
    ),
)
def find_contradictions(
    case_information: str,
) -> str:

    return f"""
Review the following case information for potential
contradictions:

{case_information}

Identify:

1. Direct contradictions
2. Timeline conflicts
3. Conflicting statements
4. Conflicting document information
5. Missing information that prevents resolution
6. Questions requiring clarification

For every potential contradiction:

- Quote or reference the relevant information.
- Explain why the information appears inconsistent.
- Do not decide which statement is true.
- Do not invent missing information.
- Mark uncertain conclusions clearly.
"""


# ============================================================
# Server
# ============================================================

if __name__ == "__main__":

    mcp.run(
        transport="streamable-http",
        host=MCP_HOST,
        port=MCP_PORT,
    )
