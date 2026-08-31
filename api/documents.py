# api/documents.py
"""
Document management API endpoints — upload, ingest, list, delete, stats.
"""
import os
import logging
from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional
import database
import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["Documents"])

# Default user ID — auth removed, single-user mode
DEFAULT_USER_ID = 1


@router.post("/upload")
async def upload_and_ingest(
    files: list[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
):
    """
    Upload one or more files and ingest them into the vector database.
    Supports PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, and audio files.
    """
    os.makedirs(config.TEMP_UPLOADS_DIR, exist_ok=True)
    results = []

    for file in files:
        try:
            # Save to temp
            file_path = os.path.join(config.TEMP_UPLOADS_DIR, file.filename)
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            # Ingest using the ingestion module
            from ingestion import ingest_document
            ingest_result = ingest_document(
                file_path=file_path,
                session_id=session_id,
            )

            # Track document in session if session_id provided
            if session_id:
                ext = os.path.splitext(file.filename)[1].lower()
                database.add_session_document(session_id, file.filename, ext)

            results.append({
                "filename": file.filename,
                "success": True,
                "chunks": ingest_result.get("chunks_created", 0),
            })
            logger.info(f"Ingested: {file.filename} ({ingest_result.get('chunks_created', 0)} chunks)")

        except Exception as e:
            logger.error(f"Failed to ingest {file.filename}: {e}")
            results.append({
                "filename": file.filename,
                "success": False,
                "error": "Failed to process this file. Please try again.",
            })

    return {
        "success": True,
        "results": results,
        "total_processed": len(results),
    }


@router.get("")
async def list_documents():
    """List all ingested documents in the vector database."""
    try:
        from doc_manager import list_ingested_documents
        docs = list_ingested_documents()
        return {"documents": docs}
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        return {"documents": [], "error": "Could not retrieve document list"}


@router.get("/stats")
async def collection_stats():
    """Get vector collection statistics."""
    try:
        from doc_manager import get_collection_stats
        stats = get_collection_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {"error": "Could not retrieve collection statistics"}


@router.get("/{document_name}/chunks")
async def get_document_chunks(document_name: str):
    """Preview chunks for a specific document."""
    try:
        from doc_manager import get_document_chunks
        chunks = get_document_chunks(document_name)
        return {"document": document_name, "chunks": chunks, "total": len(chunks)}
    except Exception as e:
        logger.error(f"Failed to get chunks for {document_name}: {e}")
        return {"chunks": [], "error": "Could not retrieve document chunks"}


@router.delete("/{document_name}")
async def delete_document(document_name: str):
    """Delete a document and all its chunks from the vector database."""
    try:
        from doc_manager import delete_document
        result = delete_document(document_name)
        return {"success": result, "message": f"Deleted '{document_name}' from knowledge base"}
    except Exception as e:
        logger.error(f"Failed to delete {document_name}: {e}")
        return {"success": False, "error": "Could not delete document"}


@router.post("/audio-transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe an audio file and return the text."""
    try:
        os.makedirs(config.TEMP_UPLOADS_DIR, exist_ok=True)

        # Use a safe filename — browser recordings may send 'blob' or None
        raw_name = file.filename or "recording"
        # Ensure a proper extension based on content-type if missing
        if "." not in raw_name:
            content_type = file.content_type or "audio/webm"
            ext_map = {
                "audio/webm": ".webm",
                "audio/mp4": ".mp4",
                "audio/mpeg": ".mp3",
                "audio/wav": ".wav",
                "audio/ogg": ".ogg",
                "audio/flac": ".flac",
            }
            ext = ext_map.get(content_type, ".webm")
            raw_name = raw_name + ext

        file_path = os.path.join(config.TEMP_UPLOADS_DIR, raw_name)
        content = await file.read()

        if not content:
            return {"success": False, "error": "Received empty audio file. Please try recording again."}

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"Audio transcription request: {raw_name} ({len(content)} bytes)")

        from ingestion.audio_loader import transcribe_audio as do_transcribe
        transcript = do_transcribe(file_path)

        # Clean up temp file
        try:
            os.remove(file_path)
        except Exception:
            pass

        if transcript:
            return {"success": True, "transcript": transcript}
        else:
            return {"success": False, "error": "Could not transcribe audio — the recording may be too short or silent."}

    except Exception as e:
        logger.error(f"Transcription endpoint error: {e}", exc_info=True)
        return {"success": False, "error": "Transcription service error. Please try again."}
