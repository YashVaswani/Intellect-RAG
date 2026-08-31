# engine/retriever.py
"""
Handles embedding user queries and searching Qdrant for relevant document chunks.
Search covers all documents in the enterprise knowledge base.
"""
import logging
from google.genai import types
from engine.clients import gemini_client, qdrant_client
import config

logger = logging.getLogger(__name__)


def embed_query(query: str) -> list[float] | None:
    """Generates a vector embedding for the given query text using Gemini."""
    try:
        response = gemini_client.models.embed_content(
            model=config.EMBED_MODEL,
            contents=query,
            config=types.EmbedContentConfig(
                output_dimensionality=config.VECTOR_DIMENSION
            ),
        )
        return response.embeddings[0].values
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return None


from qdrant_client.models import Filter, FieldCondition, MatchValue


def search_vectors(
    query_vector: list[float],
    top_k: int = None,
    session_id: str = None,
) -> list[dict]:
    """
    Searches Qdrant for the most similar document chunks across the enterprise knowledge base.
    Restricts search to session-attached documents when session_id is provided.
    """
    top_k = top_k or config.RETRIEVAL_TOP_K
    qdrant_filter = None

    if session_id:
        try:
            import database
            session_docs = database.get_session_documents(session_id)
            if session_docs:
                doc_names = [d["document_name"] for d in session_docs]
                should_conditions = [FieldCondition(key="session_id", match=MatchValue(value=session_id))]
                for name in doc_names:
                    should_conditions.append(FieldCondition(key="source_file", match=MatchValue(value=name)))
                qdrant_filter = Filter(should=should_conditions)
                logger.info(f"Applying session document filter for session={session_id}: {doc_names}")
        except Exception as filter_err:
            logger.warning(f"Failed to build session filter: {filter_err}")

    try:
        kwargs = {
            "collection_name": config.COLLECTION_NAME,
            "query": query_vector,
            "limit": top_k,
        }
        if qdrant_filter:
            kwargs["query_filter"] = qdrant_filter

        search_results = qdrant_client.query_points(**kwargs).points

        return [
            {
                "id": str(point.id),
                "text": point.payload.get("text", ""),
                "source_file": (
                    point.payload.get("source_file")
                    or point.payload.get("filename")
                    or point.payload.get("source")
                    or point.payload.get("file_name")
                    or "Unknown"
                ),
                "page_number": point.payload.get("page_number", "N/A"),
                "type": point.payload.get("type", "internal_pdf"),
                "score": getattr(point, "score", 0.0),
            }
            for point in search_results
        ]

    except Exception as e:
        logger.error(f"Qdrant search failed: {e}")
        return []


def search_internal_knowledge(
    query: str,
    top_k: int = None,
    session_id: str = None,
) -> list[dict]:
    """
    Full retrieval pipeline: embed query → search Qdrant → return ranked chunks.
    """
    query_vector = embed_query(query)
    if not query_vector:
        return []
    return search_vectors(query_vector, top_k=top_k, session_id=session_id)
