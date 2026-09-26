from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

DJANGO_URL = os.getenv(
    "DJANGO_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "gpt-4o-mini",
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

DEFAULT_TOP_K = int(
    os.getenv("RAG_TOP_K", "5")
)

MAX_TOP_K = 20


# ============================================================
# MODELS
# ============================================================

_embeddings: HuggingFaceEmbeddings | None = None
_llm: ChatOpenAI | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Load the embedding model once and reuse it.
    """

    global _embeddings

    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={
                "device": "cpu",
            },
            encode_kwargs={
                "normalize_embeddings": True,
            },
        )

    return _embeddings


def get_llm() -> ChatOpenAI:
    """
    Load the LLM once and reuse it.
    """

    global _llm

    if _llm is None:

        if not OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured."
            )

        _llm = ChatOpenAI(
            model=LLM_MODEL,
            temperature=0,
            api_key=OPENAI_API_KEY,
        )

    return _llm


# ============================================================
# VALIDATION
# ============================================================

def validate_case_id(case_id: int) -> int:

    if not isinstance(case_id, int):
        raise ValueError(
            "case_id must be an integer."
        )

    if case_id <= 0:
        raise ValueError(
            "case_id must be greater than zero."
        )

    return case_id


def validate_question(question: str) -> str:

    if not isinstance(question, str):
        raise ValueError(
            "question must be a string."
        )

    question = question.strip()

    if not question:
        raise ValueError(
            "question cannot be empty."
        )

    if len(question) > 5000:
        raise ValueError(
            "question is too long."
        )

    return question


def validate_top_k(top_k: int) -> int:

    if not isinstance(top_k, int):
        raise ValueError(
            "top_k must be an integer."
        )

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than zero."
        )

    if top_k > MAX_TOP_K:
        raise ValueError(
            f"top_k cannot exceed {MAX_TOP_K}."
        )

    return top_k


# ============================================================
# DJANGO
# ============================================================

async def get_case_context(
    case_id: int,
) -> dict[str, Any]:
    """
    Get the complete RAG context for a case from Django.

    Django provides:

        case_information
        documents
        timeline
        ocr_documents
    """

    url = (
        f"{DJANGO_URL}"
        f"/internal/mcp/cases/"
        f"{case_id}/rag-data/"
    )

    try:

        async with httpx.AsyncClient(
            timeout=60.0
        ) as client:

            response = await client.get(url)

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            return {
                "success": False,
                "error": (
                    "Django returned "
                    "invalid response data."
                ),
            }

        return data

    except httpx.HTTPStatusError as exc:

        return {
            "success": False,
            "error": (
                f"Django returned HTTP "
                f"{exc.response.status_code}."
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
            "error": (
                "Django returned invalid JSON."
            ),
        }


# ============================================================
# LANGCHAIN DOCUMENTS
# ============================================================

def create_documents(
    case_context: dict[str, Any],
) -> list[Document]:
    """
    Convert Django OCR data into LangChain Documents.
    """

    documents: list[Document] = []

    ocr_documents = case_context.get(
        "ocr_documents",
        [],
    )

    case_information = case_context.get(
        "case_information",
        {},
    )

    case_id = case_information.get(
        "id"
    )

    case_number = case_information.get(
        "case_number"
    )

    if not isinstance(
        ocr_documents,
        list,
    ):
        return documents

    for item in ocr_documents:

        if not isinstance(item, dict):
            continue

        text = item.get(
            "extracted_text"
        )

        if not isinstance(
            text,
            str,
        ):
            continue

        text = text.strip()

        if not text:
            continue

        metadata = {
            "case_id": case_id,
            "case_number": case_number,
            "document_id": item.get(
                "document_id"
            ),
            "document_name": item.get(
                "document_name"
            ),
            "document_type": item.get(
                "document_type"
            ),
            "version_id": item.get(
                "version_id"
            ),
            "version_status": item.get(
                "version_status"
            ),
            "ocr_status": item.get(
                "ocr_status"
            ),
            "created_at": item.get(
                "created_at"
            ),
        }

        documents.append(
            Document(
                page_content=text,
                metadata=metadata,
            )
        )

    return documents


# ============================================================
# TEXT SPLITTER
# ============================================================

def split_documents(
    documents: list[Document],
) -> list[Document]:
    """
    Split OCR documents into retrieval chunks.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ],
    )

    return splitter.split_documents(
        documents
    )


# ============================================================
# VECTOR STORE
# ============================================================

def create_vector_store(
    documents: list[Document],
) -> FAISS:
    """
    Create an in-memory FAISS vector store.
    """

    if not documents:
        raise ValueError(
            "No documents available."
        )

    embeddings = get_embeddings()

    return FAISS.from_documents(
        documents,
        embeddings,
    )


# ============================================================
# RETRIEVAL
# ============================================================

def retrieve_documents(
    vector_store: FAISS,
    question: str,
    top_k: int,
) -> list[Document]:
    """
    Retrieve the most relevant chunks.
    """

    return vector_store.similarity_search(
        question,
        k=top_k,
    )


# ============================================================
# CASE INFORMATION
# ============================================================

def format_case_information(
    case_context: dict[str, Any],
) -> str:
    """
    Format structured case information for the LLM.
    """

    case = case_context.get(
        "case_information",
        {},
    )

    if not isinstance(case, dict):
        return "No case information available."

    police_station = case.get(
        "police_station"
    )

    if isinstance(
        police_station,
        dict,
    ):
        station_name = police_station.get(
            "name",
            "Unknown",
        )
    else:
        station_name = (
            police_station or "Unknown"
        )

    return (
        f"Case Number: "
        f"{case.get('case_number', 'Unknown')}\n"
        f"Title: "
        f"{case.get('title', 'Unknown')}\n"
        f"Case Type: "
        f"{case.get('case_type', 'Unknown')}\n"
        f"Status: "
        f"{case.get('status', 'Unknown')}\n"
        f"Police Station: "
        f"{station_name}\n"
        f"Created At: "
        f"{case.get('created_at', 'Unknown')}"
    )


# ============================================================
# RETRIEVED CONTEXT
# ============================================================

def format_retrieved_context(
    documents: list[Document],
) -> str:
    """
    Format retrieved chunks for the LLM.
    """

    if not documents:
        return (
            "No relevant document content "
            "was found."
        )

    sections = []

    for index, document in enumerate(
        documents,
        start=1,
    ):

        metadata = document.metadata

        document_name = metadata.get(
            "document_name",
            "Unknown",
        )

        document_type = metadata.get(
            "document_type",
            "Unknown",
        )

        sections.append(
            f"""
[Source {index}]
Document: {document_name}
Document Type: {document_type}

Content:
{document.page_content}
"""
        )

    return "\n".join(sections)


# ============================================================
# PROMPT
# ============================================================

RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are the NyayaVault case analysis assistant.

You answer questions about a legal or investigation
case using only the information supplied in the
context.

Rules:

- Do not invent facts.
- Do not assume information that is not present.
- If the information is unavailable, say so clearly.
- Prefer information from the retrieved document
  context over assumptions.
- Mention the source document when useful.
- Do not reveal passwords, credentials, file paths,
  digital signatures, or internal security details.
- OCR text may contain errors. If the text appears
  incomplete or unclear, mention this.
- Keep the answer factual and concise.

CASE INFORMATION:

{case_information}

RETRIEVED DOCUMENT CONTEXT:

{context}
""",
        ),
        (
            "human",
            "{question}",
        ),
    ]
)


# ============================================================
# GENERATION
# ============================================================

async def generate_answer(
    question: str,
    case_information: str,
    retrieved_documents: list[Document],
) -> str:
    """
    Generate the final answer using the LLM.
    """

    llm = get_llm()

    prompt = RAG_PROMPT.invoke(
        {
            "question": question,
            "case_information": case_information,
            "context": format_retrieved_context(
                retrieved_documents
            ),
        }
    )

    response = await llm.ainvoke(
        prompt
    )

    content = response.content

    if isinstance(content, str):
        return content

    return str(content)


# ============================================================
# MAIN RAG PIPELINE
# ============================================================

async def answer_case_question(
    case_id: int,
    question: str,
    top_k: int = DEFAULT_TOP_K,
) -> dict[str, Any]:
    """
    Complete RAG pipeline.

    Flow:

        Django
          ↓
        Case context
          ↓
        OCR documents
          ↓
        LangChain Documents
          ↓
        Text splitting
          ↓
        Embeddings
          ↓
        FAISS
          ↓
        Similarity retrieval
          ↓
        LLM
          ↓
        Answer
    """

    case_id = validate_case_id(
        case_id
    )

    question = validate_question(
        question
    )

    top_k = validate_top_k(
        top_k
    )

    # --------------------------------------------------------
    # 1. Get case data from Django
    # --------------------------------------------------------

    case_context = await get_case_context(
        case_id
    )

    if not case_context.get(
        "success"
    ):
        return case_context

    # --------------------------------------------------------
    # 2. Convert OCR → LangChain Documents
    # --------------------------------------------------------

    documents = create_documents(
        case_context
    )

    if not documents:
        return {
            "success": False,
            "case_id": case_id,
            "error": (
                "No OCR text is available "
                "for this case."
            ),
        }

    # --------------------------------------------------------
    # 3. Split documents
    # --------------------------------------------------------

    chunks = split_documents(
        documents
    )

    if not chunks:
        return {
            "success": False,
            "case_id": case_id,
            "error": (
                "No document chunks "
                "could be created."
            ),
        }

    # --------------------------------------------------------
    # 4. Create vector store
    # --------------------------------------------------------

    vector_store = create_vector_store(
        chunks
    )

    # --------------------------------------------------------
    # 5. Retrieve relevant chunks
    # --------------------------------------------------------

    retrieved_documents = (
        retrieve_documents(
            vector_store,
            question,
            top_k,
        )
    )

    # --------------------------------------------------------
    # 6. Generate answer
    # --------------------------------------------------------

    case_information = (
        format_case_information(
            case_context
        )
    )

    answer = await generate_answer(
        question=question,
        case_information=case_information,
        retrieved_documents=retrieved_documents,
    )

    # --------------------------------------------------------
    # 7. Prepare source information
    # --------------------------------------------------------

    sources = []

    seen = set()

    for document in retrieved_documents:

        metadata = document.metadata

        source_key = (
            metadata.get("document_id"),
            metadata.get("version_id"),
        )

        if source_key in seen:
            continue

        seen.add(source_key)

        sources.append(
            {
                "document_name": metadata.get(
                    "document_name"
                ),
                "document_type": metadata.get(
                    "document_type"
                ),
                "version_id": metadata.get(
                    "version_id"
                ),
            }
        )

    return {
        "success": True,
        "case_id": case_id,
        "answer": answer,
        "sources": sources,
        "retrieved_chunks": len(
            retrieved_documents
        ),
    }