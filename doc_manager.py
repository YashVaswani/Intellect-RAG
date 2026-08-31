# doc_manager.py
"""
Document management — list, preview, delete documents from Qdrant.
"""
import logging
from engine.clients import qdrant_client
from qdrant_client.models import Filter, FieldCondition, MatchValue
import config

logger = logging.getLogger(__name__)


def list_ingested_documents() -> list[dict]:
    """
    Get a list of all unique documents in the vector database.
    Returns document name, chunk count, and sample text.
    """
    try:
        # Scroll through all points to collect unique source files
        documents = {}
        offset = None
        batch_size = 100

        while True:
            results = qdrant_client.scroll(
                collection_name=config.COLLECTION_NAME,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            points, next_offset = results

            for point in points:
                source = point.payload.get("source_file", "Unknown")
                if source not in documents:
                    documents[source] = {
                        "name": source,
                        "chunk_count": 0,
                        "file_type": point.payload.get("type", "unknown"),
                        "sample_text": point.payload.get("text", "")[:200],
                    }
                documents[source]["chunk_count"] += 1

            if next_offset is None:
                break
            offset = next_offset

        return list(documents.values())

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        return []


def get_document_chunks(source_file: str) -> list[dict]:
    """Get all chunks for a specific document."""
    try:
        results = qdrant_client.scroll(
            collection_name=config.COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="source_file", match=MatchValue(value=source_file))]
            ),
            limit=1000,
            with_payload=True,
            with_vectors=False,
        )

        chunks = []
        for point in results[0]:
            chunks.append({
                "id": str(point.id),
                "text": point.payload.get("text", ""),
                "page_number": point.payload.get("page_number", "N/A"),
                "type": point.payload.get("type", "unknown"),
            })

        def _parse_page(val) -> int:
            try:
                return int(val)
            except (ValueError, TypeError):
                return 0

        return sorted(chunks, key=lambda x: _parse_page(x.get("page_number", 0)))

    except Exception as e:
        logger.error(f"Failed to get chunks for {source_file}: {e}")
        return []


def delete_document(source_file: str) -> bool:
    """Delete all chunks for a specific document from Qdrant."""
    try:
        qdrant_client.delete(
            collection_name=config.COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="source_file", match=MatchValue(value=source_file))]
            ),
        )
        logger.info(f"Deleted all chunks for document: {source_file}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete document {source_file}: {e}")
        return False


def get_collection_stats() -> dict:
    """Get vector collection statistics."""
    try:
        info = qdrant_client.get_collection(config.COLLECTION_NAME)
        docs = list_ingested_documents()
        return {
            "collection_name": config.COLLECTION_NAME,
            "total_vectors": info.points_count,
            "total_documents": len(docs),
            "vector_dimension": config.VECTOR_DIMENSION,
            "status": str(info.status),
        }
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        return {
            "collection_name": config.COLLECTION_NAME,
            "total_vectors": 0,
            "total_documents": 0,
            "error": str(e),
        }
