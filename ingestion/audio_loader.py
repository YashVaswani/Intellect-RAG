# ingestion/audio_loader.py
"""
Audio transcription using Groq Whisper API (primary) and Gemini multimodal (fallback).
Converts audio files (.mp3, .wav, .m4a, .ogg, .flac, .webm) into structured text.
Uses HTTP calls only — no local packages required.
"""
import os
import logging
import mimetypes
import config

logger = logging.getLogger(__name__)

# Supported audio MIME types
AUDIO_MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
    ".mp4": "audio/mp4",
}


def transcribe_audio(file_path: str) -> str:
    """
    Transcribe an audio file to text.
    Primary: Groq Whisper API (fast, free, no local install needed).
    Fallback: Gemini 2.5 Flash multimodal audio.
    """
    filename = os.path.basename(file_path)

    # ── Primary: Groq Whisper API ─────────────────────────────
    groq_key = config.GROQ_API_KEY
    if groq_key:
        try:
            import requests

            ext = os.path.splitext(filename)[1].lower()
            mime = AUDIO_MIME_TYPES.get(ext, "audio/webm")

            with open(file_path, "rb") as f:
                audio_bytes = f.read()

            # Groq uses the OpenAI-compatible /audio/transcriptions endpoint
            response = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {groq_key}"},
                files={"file": (filename, audio_bytes, mime)},
                data={"model": "whisper-large-v3-turbo", "response_format": "text"},
                timeout=60,
            )

            if response.status_code == 200:
                transcript = response.text.strip()
                if transcript:
                    logger.info(f"Groq Whisper transcription complete: {filename} ({len(transcript)} chars)")
                    return transcript
                else:
                    logger.warning(f"Groq returned empty transcript for {filename}")
            else:
                logger.warning(
                    f"Groq Whisper failed for {filename}: HTTP {response.status_code} — {response.text[:200]}"
                )

        except Exception as e:
            logger.warning(f"Groq Whisper transcription error for {filename}: {e}")

    # ── Fallback: Gemini multimodal audio ────────────────────
    google_key = config.GOOGLE_API_KEY
    if google_key:
        try:
            from google import genai

            client = genai.Client(api_key=google_key)
            uploaded_file = client.files.upload(file=file_path)

            prompt = (
                "Transcribe this audio file completely and accurately. "
                "Output ONLY the transcribed text, nothing else."
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[uploaded_file, prompt],
            )

            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass

            if response.text and response.text.strip():
                logger.info(f"Gemini multimodal transcription complete: {filename}")
                return response.text.strip()

        except Exception as e:
            logger.warning(f"Gemini multimodal transcription failed for {filename}: {e}")

    logger.error(f"All transcription methods failed for {filename}")
    return ""


def load_as_document(file_path: str) -> list[dict]:
    """
    Transcribe audio file and return structured document segment for ingestion.
    """
    filename = os.path.basename(file_path)
    transcript = transcribe_audio(file_path)
    if not transcript:
        return []

    return [
        {
            "page_number": "Audio Transcript",
            "standard_text": transcript,
            "tables": [],
            "charts_and_graphs": [],
            "has_visual_data": False,
            "metadata": {
                "extraction_method": "audio_transcription",
                "source_file": filename,
            },
        }
    ]
