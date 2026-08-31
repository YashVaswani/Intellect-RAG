# main.py
"""
FastAPI application entry point.
Run with: uvicorn main:app --reload --port 8000
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import database
from engine import cache

logger = logging.getLogger(__name__)

# Initialize database & clear cache on startup
database.init_db()
cache.clear()

# Create FastAPI app
app = FastAPI(
    title="Intellect RAG Assistant API",
    description="Enterprise-grade RAG pipeline with multi-provider LLM support",
    version="2.0.0",
)

# CORS middleware — allows Next.js frontend to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",    # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
from api.chat import router as chat_router
from api.documents import router as documents_router
from api.admin import router as admin_router
from api.export import router as export_router

app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(admin_router)
app.include_router(export_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "app": "Intellect RAG Assistant",
        "version": "2.0.0",
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    health = {"api": "healthy"}

    # Check Qdrant
    try:
        from engine.clients import qdrant_client
        import config
        info = qdrant_client.get_collection(config.COLLECTION_NAME)
        health["qdrant"] = "connected"
        health["vectors"] = info.points_count
    except Exception as e:
        health["qdrant"] = f"error: {str(e)[:50]}"

    # Check Gemini
    try:
        from engine.clients import gemini_client
        health["gemini"] = "connected"
    except Exception:
        health["gemini"] = "error"

    # Check Groq
    try:
        from engine.clients import groq_client
        health["groq"] = "connected" if groq_client else "not configured"
    except Exception:
        health["groq"] = "error"

    return health


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
