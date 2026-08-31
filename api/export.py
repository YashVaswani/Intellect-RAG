# api/export.py
"""
Export API endpoints — download conversations as Markdown or PDF.
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from export_utils import export_to_markdown, export_to_pdf
import database
import io

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["Export"])

# Default user ID — auth removed, single-user mode
DEFAULT_USER_ID = 1


@router.get("/{session_id}/markdown")
async def export_markdown(session_id: str):
    """Export a conversation as a Markdown file."""
    messages = database.get_session_messages(session_id, DEFAULT_USER_ID)
    if not messages:
        raise HTTPException(status_code=404, detail="No messages found for this session")

    markdown_content = export_to_markdown(messages, session_id)

    return StreamingResponse(
        io.BytesIO(markdown_content.encode("utf-8")),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=conversation_{session_id[:8]}.md"},
    )


@router.get("/{session_id}/pdf")
async def export_pdf(session_id: str):
    """Export a conversation as a PDF file."""
    messages = database.get_session_messages(session_id, DEFAULT_USER_ID)
    if not messages:
        raise HTTPException(status_code=404, detail="No messages found for this session")

    pdf_bytes = export_to_pdf(messages, session_id)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=conversation_{session_id[:8]}.pdf"},
    )
