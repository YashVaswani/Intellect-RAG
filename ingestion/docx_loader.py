# ingestion/docx_loader.py
"""
Word document (.docx) text extraction.
"""
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> list[dict]:
    """
    Extract text from a Word document.
    Each paragraph becomes a segment; adjacent paragraphs are grouped.
    
    Returns:
        List of {"text": str, "page_number": str, "metadata": dict}
    """
    try:
        from docx import Document

        doc = Document(file_path)
        segments = []
        current_text = []
        page_estimate = 1
        char_count = 0

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                # Empty paragraph — flush current text as a segment
                if current_text:
                    segments.append({
                        "text": "\n".join(current_text),
                        "page_number": page_estimate,
                        "metadata": {"extraction_method": "docx"},
                    })
                    current_text = []
                continue

            current_text.append(text)
            char_count += len(text)

            # Rough page estimation (~3000 chars per page)
            if char_count > 3000:
                page_estimate += 1
                char_count = 0

        # Flush remaining text
        if current_text:
            segments.append({
                "text": "\n".join(current_text),
                "page_number": page_estimate,
                "metadata": {"extraction_method": "docx"},
            })

        # Also extract text from tables
        for table_idx, table in enumerate(doc.tables):
            table_text = []
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_data:
                    table_text.append(" | ".join(row_data))

            if table_text:
                segments.append({
                    "text": "\n".join(table_text),
                    "page_number": f"Table {table_idx + 1}",
                    "metadata": {"extraction_method": "docx_table"},
                })

        logger.info(f"DOCX loaded: {file_path} → {len(segments)} segments")
        return segments

    except ImportError:
        logger.error("python-docx not installed. Run: pip install python-docx")
        return []
    except Exception as e:
        logger.error(f"Failed to load DOCX {file_path}: {e}")
        return []
