# engine/clients.py
"""
Centralized API client initialization.
Every module imports clients from here — single source of truth.
"""
import logging
from google import genai
from qdrant_client import QdrantClient
import cohere
from tavily import TavilyClient
import config

logger = logging.getLogger(__name__)

# ─── Google Gemini Client (embeddings + generation) ─────────
gemini_client = genai.Client(api_key=config.GOOGLE_API_KEY)
logger.info("Google Gemini client initialized")

# ─── Groq Client (OpenAI-compatible for Llama/Qwen/DeepSeek) 
groq_client = None
if config.GROQ_API_KEY:
    try:
        from openai import OpenAI
        groq_client = OpenAI(
            api_key=config.GROQ_API_KEY,
            base_url=config.GROQ_API_BASE,
            max_retries=0,
        )
        logger.info("Groq client initialized (Llama/Qwen/DeepSeek available)")
    except ImportError:
        logger.warning("openai package not installed — Groq models unavailable. Run: pip install openai")
else:
    logger.warning("GROQ_API_KEY not set — Groq models (Llama/Qwen/DeepSeek) unavailable")

# ─── Qdrant Vector Database Client ──────────────────────────
qdrant_client = QdrantClient(
    url=config.QDRANT_URL,
    api_key=config.QDRANT_API_KEY,
    timeout=config.QDRANT_TIMEOUT,
    check_compatibility=False,
)
logger.info("Qdrant Cloud client initialized")

# ─── Cohere Reranker Client ─────────────────────────────────
cohere_client = cohere.Client(api_key=config.COHERE_API_KEY)
logger.info("Cohere reranker client initialized")

# ─── Tavily Web Search Client ───────────────────────────────
tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)
logger.info("Tavily web search client initialized")
