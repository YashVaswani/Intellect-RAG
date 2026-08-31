# engine/agents/doc_manage_agent.py
"""
Document Management Agent — handles natural language file listing, inspection, deletion, and stats queries.
Interacts directly with doc_manager layer. Zero RAG vector tokens used.
"""
import logging
import doc_manager

logger = logging.getLogger(__name__)


class DocumentManagementAgent:
    """Specialized Agent for natural language document listing and management."""

    def run(self, user_query: str) -> str:
        """Process document management request."""
        query_lower = user_query.lower()

        # 1. Stats query
        if any(w in query_lower for w in ["stats", "statistics", "vector count", "total vectors", "dimension"]):
            stats = doc_manager.get_collection_stats()
            return (
                f"📊 **Knowledge Base Statistics**\n"
                f"- **Collection:** `{stats.get('collection_name')}`\n"
                f"- **Total Documents:** {stats.get('total_documents')}\n"
                f"- **Total Vectors:** {stats.get('total_vectors')}\n"
                f"- **Vector Dimension:** {stats.get('vector_dimension')}\n"
                f"- **Status:** {stats.get('status', 'Active')}"
            )

        # 2. List documents
        docs = doc_manager.list_ingested_documents()
        if not docs:
            return "📁 **Knowledge Base Status:** No documents have been uploaded yet. Use the upload button or watch folder to ingest files!"

        lines = ["📁 **Uploaded Documents in Knowledge Base:**\n"]
        for idx, d in enumerate(docs, 1):
            name = d.get("name", "Unknown")
            chunks = d.get("chunk_count", 0)
            file_type = d.get("file_type", "file")
            lines.append(f"{idx}. **{name}** (`{file_type}`) — *{chunks} vector chunks*")

        lines.append(f"\n*Total Documents:* {len(docs)}")
        return "\n".join(lines)


doc_manage_agent = DocumentManagementAgent()
