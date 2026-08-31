# ingestion/ocr_loader.py
"""
OCR & Multimodal Vision text/table/chart extraction for scanned images and document images.
Uses Gemini 2.5 Flash Vision JSON schema parsing with EasyOCR fallback.
"""
import os
import logging
import json
import config

logger = logging.getLogger(__name__)


def load(file_path: str) -> list[dict]:
    """
    Extract structured text, tables, and visual charts from an image using Gemini 2.5 Flash Vision.
    Falls back to EasyOCR if Gemini fails or is unavailable.
    """
    filename = os.path.basename(file_path)
    
    # Try Gemini 2.5 Flash Multimodal OCR first
    try:
        api_key = config.GOOGLE_API_KEY
        if api_key:
            from google import genai
            from google.genai import types
            from ingestion.schemas import PageExtractionSchema
            
            client = genai.Client(api_key=api_key)
            uploaded_file = client.files.upload(file=file_path)
            
            # Extraction-only prompt — JSON structure is auto-enforced by response_schema below.
            # No JSON instructions in the prompt; the Pydantic schema + application/json MIME type
            # guarantee the output format automatically at the API level.
            prompt = (
                "Analyze this image document. "
                "1. IDENTITY & OFFICIAL DOCUMENTS (Aadhaar, PAN, Voter ID, Passport, Resumes, Invoices, Receipts): "
                "Extract EVERY key-value field explicitly with clear, unambiguous labels as written in the document. "
                "CRITICAL IDENTITY RULE: For identification numbers (e.g. Aadhaar 12-digit numbers), explicitly label them with their exact document label (e.g., 'Aadhaar Number: XXXX XXXX XXXX'). "
                "Preserve all names, enrolment numbers, DOBs, VIDs, mobile numbers, dates, and full addresses verbatim from the document text. "
                "Preserve original language and English side-by-side if present in the document. "
                "2. TABLES & CHARTS: Extract all visual tables into Markdown format with headings. Extract all charts, diagrams, or graphs into detailed visual summaries and key metrics."
            )
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[uploaded_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=PageExtractionSchema,
                    temperature=0.1,
                ),
            )
            
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
                
            if response.text:
                p_data = json.loads(response.text)
                return [{
                    "page_number": p_data.get("page_number", 1),
                    "standard_text": p_data.get("standard_text", ""),
                    "tables": p_data.get("tables", []),
                    "charts_and_graphs": p_data.get("charts_and_graphs", []),
                    "has_visual_data": p_data.get("has_visual_data", False),
                    "metadata": {"extraction_method": "gemini_vision_ocr", "source": filename},
                }]

    except Exception as e:
        logger.warning(f"Gemini Vision OCR failed for {filename}: {e}. Trying EasyOCR fallback...")

    # EasyOCR Fallback (Supports English + Hindi / Devanagari)
    try:
        import easyocr
        reader = easyocr.Reader(["en", "hi"], gpu=False)
        results = reader.readtext(file_path)

        full_text = " ".join([r[1] for r in results])

        if not full_text.strip():
            return []

        return [{
            "page_number": 1,
            "standard_text": full_text,
            "tables": [],
            "charts_and_graphs": [],
            "has_visual_data": False,
            "metadata": {"extraction_method": "easyocr_fallback", "source": filename},
        }]

    except Exception as e:
        logger.error(f"OCR failed for {file_path}: {e}")
        return []
