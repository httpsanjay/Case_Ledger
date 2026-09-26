import re

from langchain_core.documents import Document as LCDocument
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from .models import Case, Document, DocumentVersion
from .permissions import (
    can_access_case,
    can_access_document_version,
)


_CHUNK_SIZE = 1200
_CHUNK_OVERLAP = 200

_STOPWORDS = {
    "a", "about", "after", "again", "against", "all", "also", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can", "cannot", "could", "did", "do", "does",
    "doing", "down", "during", "each", "few", "for", "from", "further", "had",
    "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its",
    "itself", "just", "me", "more", "most", "my", "myself", "no", "nor", "not",
    "of", "off", "on", "once", "only", "or", "other", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some",
    "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "will", "with", "you",
    "your", "yours", "yourself", "yourselves",
}


def _significant_query_terms(query):
    return [
        term
        for term in re.findall(r"\w+", (query or "").lower())
        if len(term) > 1 and term not in _STOPWORDS
    ]


# ---------------------------------------------------------
# LangChain embedding model
# ---------------------------------------------------------

_embeddings = None


def _get_embeddings():
    global _embeddings

    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={
                "device": "cpu",
            },
            encode_kwargs={
                "normalize_embeddings": True,
            },
        )

    return _embeddings


# ---------------------------------------------------------
# Chunking
# ---------------------------------------------------------

def _chunks(text):
    text = (text or "").strip()

    if not text:
        return []

    if len(text) <= _CHUNK_SIZE:
        return [text]

    chunks = []

    step = _CHUNK_SIZE - _CHUNK_OVERLAP

    for start in range(0, len(text), step):
        chunk = text[start:start + _CHUNK_SIZE]

        if chunk.strip():
            chunks.append(chunk)

    return chunks



def _keyword_matches(query, version): 
    terms = _significant_query_terms(query) 
    text = (version.extracted_text or "").strip() 
    lowered = text.lower() 

    if not text or not terms or not any(term in lowered for term in terms): 
        return [] 
    
    first_position = min( (lowered.find(term) for term in terms if lowered.find(term) >= 0), default=0, )
    
    start = max(first_position - 90, 0) 
    end = min(start + 240, len(text)) 
    score = sum(lowered.count(term) for term in terms) / len(terms) 
    return [{ 
        "text": text[start:end], 
        "score": round(min(score / 5, 1), 4), 
        "version_id": version.pk, 
        "version_number": version.version_number, 
        "chunk_index": 0, 
        }]

# ---------------------------------------------------------
# Semantic search using LangChain + FAISS
# ---------------------------------------------------------

def _semantic_matches(query, version):
    terms = _significant_query_terms(query)

    if len(terms) < 2:
        return []

    text = (version.extracted_text or "").strip()

    if not text:
        return []

    chunks = _chunks(text)

    if not chunks:
        return []

    documents = [
        LCDocument(
            page_content=chunk,
            metadata={
                "version_id": version.pk,
                "version_number": version.version_number,
                "chunk_index": index,
            },
        )
        for index, chunk in enumerate(chunks)
    ]

    try:
        vector_store = FAISS.from_documents(
            documents,
            _get_embeddings(),
        )

        results = vector_store.similarity_search_with_score(
            query,
            k=min(3, len(documents)),
        )

    except Exception:
        return []

    matches = []

    for document, distance in results:

        # FAISS returns distance.
        # Smaller distance = better match.
        score = 1 / (1 + float(distance))

        matches.append({
            "text": document.page_content,
            "score": round(score, 4),
            "version_id": document.metadata["version_id"],
            "version_number": document.metadata["version_number"],
            "chunk_index": document.metadata["chunk_index"],
        })

    return matches

