# ingestion/__init__.py
"""
Multi-format document ingestion router.
Detects file type, dispatches to loader (with Gemini 2.5 Flash Vision JSON extraction),
processes structured narrative text, Markdown tables, and chart/graph summaries,
embeds, and uploads to Qdrant.
Propagates active section/session context across page boundaries for continuing tables/lists.
"""
import os
import uuid
import time
import json
import re
import logging
from google.genai import types
from engine.clients import gemini_client, qdrant_client
from qdrant_client.models import PointStruct, VectorParams, Distance
import config

logger = logging.getLogger(__name__)

# Import loaders lazily
_LOADERS = {}


def _get_loader(extension: str):
    """Lazy-load the appropriate loader for a file extension."""
    if extension in _LOADERS:
        return _LOADERS[extension]

    loader = None
    if extension == ".pdf":
        from ingestion.pdf_loader import load
        loader = load
    elif extension == ".docx":
        from ingestion.docx_loader import load
        loader = load
    elif extension in (".xlsx", ".xls"):
        from ingestion.excel_loader import load
        loader = load
    elif extension == ".pptx":
        from ingestion.pptx_loader import load
        loader = load
    elif extension in (".txt", ".md", ".csv"):
        from ingestion.text_loader import load
        loader = load
    elif extension in config.SUPPORTED_IMAGE_TYPES:
        from ingestion.ocr_loader import load
        loader = load
    elif extension in config.SUPPORTED_AUDIO_TYPES:
        from ingestion.audio_loader import load_as_document
        loader = load_as_document

    if loader:
        _LOADERS[extension] = loader
    return loader


def _ensure_collection():
    """Create the Qdrant collection if it doesn't exist."""
    try:
        collections = [c.name for c in qdrant_client.get_collections().collections]
        if config.COLLECTION_NAME not in collections:
            logger.info(f"Creating Qdrant collection: '{config.COLLECTION_NAME}'")
            qdrant_client.create_collection(
                collection_name=config.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=config.VECTOR_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Collection created successfully")
    except Exception as e:
        logger.error(f"Failed to ensure collection: {e}")
        raise


def _embed_with_rate_limit(text: str) -> list[float]:
    """Generate embedding with rate limiting to avoid 429 errors."""
    time.sleep(config.INGEST_RATE_LIMIT_DELAY)
    response = gemini_client.models.embed_content(
        model=config.EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=config.VECTOR_DIMENSION
        ),
    )
    return response.embeddings[0].values


def _save_payload_json(source_file: str, segments: list[dict], chunks: list[dict]):
    """Save full structured extraction payload as JSON for audit trail and inspection."""
    os.makedirs(config.PAYLOADS_DIR, exist_ok=True)

    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in source_file)
    json_path = os.path.join(config.PAYLOADS_DIR, f"{safe_name}.json")

    payload = {
        "source_file": source_file,
        "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_segments": len(segments),
        "total_chunks": len(chunks),
        "embedding_model": config.EMBED_MODEL,
        "vector_dimension": config.VECTOR_DIMENSION,
        "extracted_segments": segments,
        "chunks": [
            {
                "chunk_id": c["id"],
                "chunk_type": c.get("chunk_type", "text"),
                "text": c["text"],
                "page_number": c.get("page_number", "N/A"),
                "char_length": len(c["text"]),
            }
            for c in chunks
        ],
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved payload JSON: {json_path}")


def ingest_document(
    file_path: str,
    session_id: str = None,
) -> dict:
    """
    Main ingestion function — extracts structured narrative text, Markdown tables,
    and visual graph summaries, embeds, and uploads to Qdrant.
    Propagates active section/session context across page boundaries for continuing tables/lists.
    """
    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)

    loader = _get_loader(ext)
    if not loader:
        logger.warning(f"Unsupported file type: {ext} for file {filename}")
        return {"success": False, "error": f"Unsupported file type: {ext}", "chunks_created": 0}

    logger.info(f"Ingesting: {filename} (type: {ext})")

    try:
        # Step 1: Extract structured segments
        segments = loader(file_path)
        if not segments:
            return {"success": False, "error": "No text extracted from file", "chunks_created": 0}

        # Step 2: Prepare chunks with Section/Session Context Propagation across page boundaries
        from ingestion.chunker import smart_chunk
        all_chunks = []
        current_session_header = ""

        for segment in segments:
            page_num = segment.get("page_number", "N/A")
            std_text = segment.get("standard_text") or segment.get("text", "")
            
            # Detect new session header or section title on current page
            if std_text and std_text.strip():
                for line in std_text.splitlines():
                    cleaned_line = line.strip()
                    if ("SESSION:" in cleaned_line.upper() or "SESSION 0" in cleaned_line.upper() or "SESSION 1" in cleaned_line.upper()) and ("DATE:" in cleaned_line.upper() or "2025" in cleaned_line):
                        current_session_header = cleaned_line
                        break

            header_prefix = f"SESSION DETAILS: {current_session_header}" if current_session_header else ""
            ctx_header = f"{header_prefix} | " if header_prefix else ""

            # A) Standard narrative text chunking
            if std_text and std_text.strip():
                text_chunks = smart_chunk(std_text.strip())
                for tc in text_chunks:
                    if header_prefix and header_prefix not in tc and current_session_header not in tc:
                        formatted_text = f"Document: {filename} | Page: {page_num} | {header_prefix} |\n{tc}"
                    else:
                        formatted_text = f"Document: {filename} | Page: {page_num} |\n{tc}"
                    all_chunks.append({
                        "text": formatted_text,
                        "page_number": page_num,
                        "chunk_type": "text",
                    })

            # B) Markdown tables
            tables = segment.get("tables", [])
            for tbl in tables:
                tbl_title = tbl.get("table_title") or "Untitled Table"
                tbl_md = tbl.get("markdown_data", "").strip()
                if tbl_md:
                    table_text = f"Document: {filename} | Page: {page_num} | {ctx_header}Table: {tbl_title}\n{tbl_md}"
                    all_chunks.append({
                        "text": table_text,
                        "page_number": page_num,
                        "chunk_type": "table",
                    })

            # C) Visual Charts / Graphs (Pie charts, Bar graphs, Line charts, Infographics)
            charts = segment.get("charts_and_graphs", [])
            for ch in charts:
                ch_type = ch.get("type", "Visual Graphic")
                ch_title = ch.get("title") or ch_type
                ch_summary = ch.get("visual_summary", "").strip()
                raw_dp = ch.get("extracted_data_points", [])

                # Format data points cleanly as "Label: Value" pairs
                dp_lines = []
                if isinstance(raw_dp, list):
                    for dp in raw_dp:
                        if isinstance(dp, dict):
                            lbl = dp.get("label", "").strip()
                            val = dp.get("value", "").strip()
                            if lbl and val:
                                dp_lines.append(f"{lbl}: {val}")
                        elif isinstance(dp, str):
                            dp_lines.append(dp)
                elif isinstance(raw_dp, dict):
                    for k, v in raw_dp.items():
                        dp_lines.append(f"{k}: {v}")

                dp_formatted = ", ".join(dp_lines) if dp_lines else "None specified"

                chart_text = (
                    f"Document: {filename} | Page: {page_num} | {ctx_header}Graphic Layout\n"
                    f"Type: {ch_type} | Title: {ch_title}\n"
                    f"Visual Analysis Summary: {ch_summary}\n"
                    f"Extracted Metrics & Data Points: {dp_formatted}"
                )

                if ch_summary or dp_lines:
                    all_chunks.append({
                        "text": chart_text,
                        "page_number": page_num,
                        "chunk_type": "chart",
                    })

        if not all_chunks:
            return {"success": False, "error": "No chunks generated", "chunks_created": 0}

        # Step 3: Ensure Qdrant collection exists
        _ensure_collection()

        # Step 4: Embed and create Qdrant points
        points = []
        chunk_records = []

        for chunk_data in all_chunks:
            try:
                vector = _embed_with_rate_limit(chunk_data["text"])
                # Deterministic UUID based on content to prevent duplicate points in Qdrant
                seed = f"{filename}_{chunk_data.get('page_number')}_{chunk_data.get('chunk_type')}_{chunk_data['text']}"
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))

                payload = {
                    "text": chunk_data["text"],
                    "source_file": filename,
                    "page_number": chunk_data["page_number"],
                    "chunk_type": chunk_data["chunk_type"],
                    "type": "internal_pdf",
                }

                if session_id:
                    payload["session_id"] = session_id

                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                )

                chunk_records.append({
                    "id": point_id,
                    "chunk_type": chunk_data["chunk_type"],
                    "text": chunk_data["text"],
                    "page_number": chunk_data["page_number"],
                })

            except Exception as e:
                logger.error(f"Failed to embed chunk: {e}")
                continue

        # Step 5: Batch upsert to Qdrant
        if points:
            batch_size = config.INGEST_BATCH_SIZE
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                qdrant_client.upsert(
                    collection_name=config.COLLECTION_NAME,
                    points=batch,
                )
                logger.info(f"Uploaded batch {i // batch_size + 1} ({len(batch)} chunks)")

        # Step 6: Save audit JSON payload
        _save_payload_json(filename, segments, chunk_records)

        logger.info(f"Ingestion complete: {filename} → {len(points)} chunks with active section propagation")
        return {
            "success": True,
            "source_file": filename,
            "chunks_created": len(points),
            "total_segments": len(segments),
        }

    except Exception as e:
        logger.error(f"Ingestion failed for {filename}: {e}")
        return {"success": False, "error": str(e), "chunks_created": 0}
