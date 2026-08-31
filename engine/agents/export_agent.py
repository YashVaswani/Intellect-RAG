# engine/agents/export_agent.py
"""
Export & Analytics Agent — handles conversation export requests and token/usage analytics.
Zero document RAG tokens used.
"""
import logging

logger = logging.getLogger(__name__)


class ExportAgent:
    """Specialized Agent for handling export and usage metrics requests."""

    def run(self, user_query: str, session_id: str = None) -> str:
        """Process export or analytics request."""
        query_lower = user_query.lower()

        if "pdf" in query_lower:
            link = f"/api/export/{session_id}/pdf" if session_id else "#"
            return f"📄 You can download your conversation export in PDF format here: [Download PDF Export]({link})"
        elif "markdown" in query_lower or "md" in query_lower:
            link = f"/api/export/{session_id}/markdown" if session_id else "#"
            return f"📝 You can download your conversation export in Markdown format here: [Download Markdown Export]({link})"
        else:
            pdf_link = f"/api/export/{session_id}/pdf" if session_id else "#"
            md_link = f"/api/export/{session_id}/markdown" if session_id else "#"
            return (
                f"📊 **Export Conversation Options:**\n"
                f"- [Download PDF Format]({pdf_link})\n"
                f"- [Download Markdown Format]({md_link})"
            )


export_agent = ExportAgent()
