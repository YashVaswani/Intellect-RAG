# config.py
import os
import logging
from dotenv import load_dotenv

# Fix Windows httpx NO_PROXY IPv6 parsing bug (removes ::1 that crashes httpx/google-genai)
if os.environ.get("NO_PROXY"):
    os.environ["NO_PROXY"] = ",".join(
        p for p in os.environ["NO_PROXY"].split(",") if p.strip() not in ("::1", "::1/128")
    )
elif os.environ.get("no_proxy"):
    os.environ["no_proxy"] = ",".join(
        p for p in os.environ["no_proxy"].split(",") if p.strip() not in ("::1", "::1/128")
    )

load_dotenv()

# ─── API Keys ───────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# ─── Embedding & Reranking ──────────────────────────────────
EMBED_MODEL = "gemini-embedding-001"
RERANK_MODEL = "rerank-v3.5"
VECTOR_DIMENSION = 768

# ─── Multi-Provider LLM Configuration ───────────────────────
LLM_MODELS = {
    "gemini-2.0-flash": {
        "provider": "gemini",
        "display_name": "Gemini 2.0 Flash",
        "description": "Google's latest balanced multimodal model — fast, accurate, vision-native (1M context window)",
        "speed": "⚡ Fast",
        "context_window": 1_048_576,
    },
    "llama-3.3-70b-versatile": {
        "provider": "groq",
        "display_name": "Llama 3.3 70B",
        "description": "Meta's powerful open model via Groq",
        "speed": "⚡ Fast",
        "context_window": 131_072,
    },
    "llama-3.1-8b-instant": {
        "provider": "groq",
        "display_name": "Llama 3.1 8B Instant",
        "description": "Meta's ultra-fast lightweight model via Groq",
        "speed": "⚡ Ultra Fast",
        "context_window": 131_072,
    },
}

DEFAULT_LLM_MODEL = "gemini-2.0-flash"

# Fallback chain: if the selected model fails, try these in order
MODEL_FALLBACK_CHAIN = [
    "gemini-2.0-flash",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# ─── Vector Database ────────────────────────────────────────
COLLECTION_NAME = "enterprise_knowledge_base"
QDRANT_TIMEOUT = 60.0

# ─── Chunking Configuration ─────────────────────────────────
CHUNK_MAX_TOKENS = 500
CHUNK_OVERLAP_SENTENCES = 2

# ─── Retrieval & Reranking ───────────────────────────────────
RETRIEVAL_TOP_K = 30
RERANK_TOP_N = 8
WEB_FALLBACK_THRESHOLD = 0.20

# ─── Conversation Memory ────────────────────────────────────
MAX_HISTORY_TURNS = 5

# ─── Guardrails ─────────────────────────────────────────────
GUARDRAIL_ENABLED = True
GUARDRAIL_MIN_RELEVANCE = 0.05  # Permissive relevance threshold so all uploaded document chunks are processed by LLM
GUARDRAIL_REFUSAL_MESSAGE = (
    "I searched your uploaded documents, but could not find information relevant to your request."
)

# ─── Semantic Cache ─────────────────────────────────────────
CACHE_ENABLED = False
CACHE_SIMILARITY_THRESHOLD = 0.95
CACHE_TTL_HOURS = 24

# ─── Error Handling ─────────────────────────────────────────
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
RETRY_BACKOFF_MULTIPLIER = 2.0

# ─── Ingestion ──────────────────────────────────────────────
INGEST_RATE_LIMIT_DELAY = 1.0
INGEST_BATCH_SIZE = 20

# ─── Whisper (Audio Transcription) ──────────────────────────
WHISPER_MODEL_SIZE = "base"

# ─── Groq API ───────────────────────────────────────────────
GROQ_API_BASE = "https://api.groq.com/openai/v1"

# ─── Paths ──────────────────────────────────────────────────
DATA_DIR = "data"
TEMP_UPLOADS_DIR = "temp_uploads"
WATCH_FOLDER = "watch_folder"
PAYLOADS_DIR = "payloads"
LOG_FILE = "app.log"
DB_FILE = "chat_history.db"

# ─── Logging Setup ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# ─── Supported File Types ───────────────────────────────────
SUPPORTED_DOCUMENT_TYPES = [".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv"]
SUPPORTED_AUDIO_TYPES = [".mp3", ".wav", ".m4a", ".ogg", ".flac"]
SUPPORTED_IMAGE_TYPES = [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]