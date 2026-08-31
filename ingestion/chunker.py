# ingestion/chunker.py
"""
Sentence-aware smart chunking — splits text at sentence boundaries
instead of arbitrary character positions.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Sentence-ending patterns
SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+(?=[A-Z\u0900-\u097F\u0980-\u09FF])')
# Fallback: split on newlines, semicolons, or long phrases
FALLBACK_SPLIT = re.compile(r'[\n;]+')


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex patterns."""
    # Try sentence-ending split first
    sentences = SENTENCE_ENDINGS.split(text)

    # If that produced only 1 chunk, try newline/semicolon split
    if len(sentences) <= 1:
        sentences = FALLBACK_SPLIT.split(text)

    # If still 1 chunk, split by any period followed by space
    if len(sentences) <= 1:
        sentences = re.split(r'\.\s+', text)

    # Filter out empty sentences
    return [s.strip() for s in sentences if s.strip()]


def smart_chunk(
    text: str,
    max_chars: int = 1500,
    overlap_sentences: int = 2,
) -> list[str]:
    """
    Split text into chunks at sentence boundaries with overlap.
    
    Args:
        text: Raw text to chunk
        max_chars: Maximum characters per chunk (roughly ~375 tokens)
        overlap_sentences: Number of sentences to repeat at chunk boundaries
    
    Returns:
        List of chunk strings
    """
    if not text or not text.strip():
        return []

    sentences = _split_sentences(text)

    if not sentences:
        # If no sentences detected, fall back to character chunking
        return _character_chunk(text, max_chars)

    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        # If a single sentence exceeds max_chars, split it by characters
        if sentence_len > max_chars:
            # Flush current chunk first
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0
            # Split the long sentence
            for sub in _character_chunk(sentence, max_chars):
                chunks.append(sub)
            continue

        # If adding this sentence exceeds the limit, start a new chunk
        if current_length + sentence_len + 1 > max_chars and current_chunk:
            chunks.append(" ".join(current_chunk))

            # Overlap: carry the last N sentences to the next chunk
            if overlap_sentences > 0 and len(current_chunk) >= overlap_sentences:
                current_chunk = current_chunk[-overlap_sentences:]
                current_length = sum(len(s) for s in current_chunk) + len(current_chunk) - 1
            else:
                current_chunk = []
                current_length = 0

        current_chunk.append(sentence)
        current_length += sentence_len + 1  # +1 for space

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    logger.debug(f"Smart chunking: {len(sentences)} sentences → {len(chunks)} chunks")
    return chunks


def _character_chunk(text: str, max_chars: int = 1500) -> list[str]:
    """Fallback character-based chunking for texts that don't split well."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks
