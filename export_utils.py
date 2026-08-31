# export_utils.py
"""
Export utilities — convert conversations to Markdown and PDF formats.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def export_to_markdown(messages: list[dict], session_id: str) -> str:
    """Convert conversation messages to a clean Markdown file."""
    lines = [
        f"# Conversation Export",
        f"**Session ID:** {session_id}",
        f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Messages:** {len(messages)}",
        "",
        "---",
        "",
    ]

    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        timestamp = msg.get("timestamp", "")

        if role == "user":
            lines.append(f"## 👤 User")
        else:
            model = msg.get("model_used", "")
            model_info = f" (via {model})" if model else ""
            lines.append(f"## 🤖 Assistant{model_info}")

        if timestamp:
            lines.append(f"*{timestamp}*")
        lines.append("")
        lines.append(content)
        lines.append("")

        # Add source citations if present
        sources = msg.get("sources", [])
        if sources and role == "assistant":
            lines.append("### 📚 Sources")
            for i, src in enumerate(sources, 1):
                source_file = src.get("source_file", "Unknown")
                page = src.get("page_number", "N/A")
                src_type = src.get("type", "unknown")
                if src_type == "live_web":
                    lines.append(f"{i}. 🌐 [{source_file}]({source_file})")
                else:
                    lines.append(f"{i}. 📄 {source_file} (Page {page})")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def export_to_pdf(messages: list[dict], session_id: str) -> bytes:
    """Convert conversation messages to a PDF file."""
    try:
        from fpdf import FPDF
    except ImportError:
        logger.warning("fpdf2 not installed, falling back to text-based PDF")
        # Fallback: return markdown as plain text PDF-like
        content = export_to_markdown(messages, session_id)
        return content.encode("utf-8")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Conversation Export", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Session: {session_id[:16]}...", ln=True, align="C")
    pdf.cell(
        0, 6,
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ln=True, align="C",
    )
    pdf.ln(10)

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        # Role header
        pdf.set_font("Helvetica", "B", 12)
        if role == "user":
            pdf.set_text_color(59, 130, 246)  # Blue
            pdf.cell(0, 8, "User:", ln=True)
        else:
            pdf.set_text_color(34, 197, 94)  # Green
            model_info = f" (via {msg.get('model_used', 'AI')})"
            pdf.cell(0, 8, f"Assistant{model_info}:", ln=True)

        # Message content
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)
        # Handle encoding — replace characters that can't be encoded in latin-1
        safe_content = content.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 5, safe_content)
        pdf.ln(5)

        # Sources
        sources = msg.get("sources", [])
        if sources and role == "assistant":
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(100, 100, 100)
            for i, src in enumerate(sources, 1):
                source_text = f"Source {i}: {src.get('source_file', 'Unknown')}"
                safe_source = source_text.encode("latin-1", errors="replace").decode("latin-1")
                pdf.cell(0, 5, safe_source, ln=True)
            pdf.ln(3)

        # Separator
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

    out = pdf.output()
    return bytes(out) if isinstance(out, (bytearray, list)) else out.encode("latin-1") if isinstance(out, str) else bytes(out)
