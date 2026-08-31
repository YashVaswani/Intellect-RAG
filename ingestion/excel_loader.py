# ingestion/excel_loader.py
"""
Excel spreadsheet (.xlsx/.xls) text extraction.
Converts each sheet into structured text segments.
"""
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> list[dict]:
    """
    Extract text from an Excel spreadsheet.
    Each sheet becomes one or more segments.
    
    Returns:
        List of {"text": str, "page_number": str, "metadata": dict}
    """
    try:
        from openpyxl import load_workbook

        wb = load_workbook(file_path, read_only=True, data_only=True)
        segments = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows_text = []
            headers = []

            for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                # Convert all cell values to strings
                cells = [str(cell).strip() if cell is not None else "" for cell in row]

                # Skip completely empty rows
                if not any(cells):
                    continue

                if row_idx == 0:
                    # First row as headers
                    headers = cells
                    rows_text.append(" | ".join(cells))
                else:
                    # Format as "Header: Value" pairs for better semantic search
                    if headers:
                        pairs = []
                        for i, cell in enumerate(cells):
                            if cell and i < len(headers) and headers[i]:
                                pairs.append(f"{headers[i]}: {cell}")
                            elif cell:
                                pairs.append(cell)
                        if pairs:
                            rows_text.append(", ".join(pairs))
                    else:
                        row_str = " | ".join(c for c in cells if c)
                        if row_str:
                            rows_text.append(row_str)

            if rows_text:
                # Split into manageable segments (every 20 rows)
                for i in range(0, len(rows_text), 20):
                    batch = rows_text[i:i + 20]
                    segments.append({
                        "text": "\n".join(batch),
                        "page_number": f"Sheet: {sheet_name}",
                        "metadata": {
                            "extraction_method": "excel",
                            "sheet_name": sheet_name,
                        },
                    })

        wb.close()
        logger.info(f"Excel loaded: {file_path} → {len(segments)} segments")
        return segments

    except ImportError:
        logger.error("openpyxl not installed. Run: pip install openpyxl")
        return []
    except Exception as e:
        logger.error(f"Failed to load Excel {file_path}: {e}")
        return []
