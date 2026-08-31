# ingestion/text_loader.py
"""
Plain text file extraction — TXT, Markdown, CSV.
"""
import os
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> list[dict]:
    """
    Extract text from plain text files.
    
    For CSV: formats rows as structured text.
    For TXT/MD: splits by double newlines into logical sections.
    
    Returns:
        List of {"text": str, "page_number": str, "metadata": dict}
    """
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".csv":
            return _load_csv(file_path)
        else:
            return _load_text(file_path)
    except Exception as e:
        logger.error(f"Failed to load text file {file_path}: {e}")
        return []


def _load_text(file_path: str) -> list[dict]:
    """Load a plain text or Markdown file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    if not content.strip():
        return []

    # Split by double newlines (sections/paragraphs)
    sections = content.split("\n\n")
    segments = []
    section_num = 1

    for section in sections:
        text = section.strip()
        if text and len(text) > 20:  # Skip very short fragments
            segments.append({
                "text": text,
                "page_number": f"Section {section_num}",
                "metadata": {"extraction_method": "text"},
            })
            section_num += 1

    # If no sections detected, treat as single segment
    if not segments and content.strip():
        segments.append({
            "text": content.strip(),
            "page_number": "Full Document",
            "metadata": {"extraction_method": "text"},
        })

    logger.info(f"Text file loaded: {file_path} → {len(segments)} segments")
    return segments


def _load_csv(file_path: str) -> list[dict]:
    """Load a CSV file and format rows as structured text."""
    import csv

    segments = []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        headers = None
        rows_text = []

        for row_idx, row in enumerate(reader):
            if row_idx == 0:
                headers = [h.strip() for h in row]
                continue

            if headers:
                pairs = []
                for i, cell in enumerate(row):
                    cell = cell.strip()
                    if cell and i < len(headers):
                        pairs.append(f"{headers[i]}: {cell}")
                if pairs:
                    rows_text.append(", ".join(pairs))
            else:
                row_str = ", ".join(c.strip() for c in row if c.strip())
                if row_str:
                    rows_text.append(row_str)

        # Split into segments of 20 rows
        for i in range(0, len(rows_text), 20):
            batch = rows_text[i:i + 20]
            segments.append({
                "text": "\n".join(batch),
                "page_number": f"Rows {i + 1}-{i + len(batch)}",
                "metadata": {"extraction_method": "csv"},
            })

    logger.info(f"CSV loaded: {file_path} → {len(segments)} segments")
    return segments
