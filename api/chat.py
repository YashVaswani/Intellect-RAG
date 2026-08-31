# api/chat.py
"""
Chat API endpoints — query processing, streaming, session management.
"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.models import ChatRequest, ChatResponse, SessionRenameRequest
from engine.pipeline import generate_rag_response, generate_rag_response_stream
import database
import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Default user ID — auth removed, single-user mode
DEFAULT_USER_ID = 1


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a query and get a full RAG response."""
    user_id = DEFAULT_USER_ID

    # Load conversation history for this session
    messages = database.get_session_messages(req.session_id, user_id)
    chat_history = [{"role": m["role"], "content": m["content"]} for m in messages]

    # Run RAG pipeline
    response = generate_rag_response(
        user_query=req.query,
        chat_history=chat_history,
        model=req.model or config.DEFAULT_LLM_MODEL,
        session_id=req.session_id,
    )

    # Save user message
    database.save_message(
        session_id=req.session_id,
        user_id=user_id,
        role="user",
        content=req.query,
    )

    # Save assistant response
    database.save_message(
        session_id=req.session_id,
        user_id=user_id,
        role="assistant",
        content=response["answer"],
        sources=response.get("sources"),
        source_type=response.get("source_type"),
        score=response.get("confidence_score"),
        model_used=response.get("model_used"),
        token_usage=response.get("token_usage"),
    )

    from datetime import datetime
    response["timestamp"] = datetime.now().strftime("%I:%M %p").lstrip("0")

    return ChatResponse(**response)


@router.websocket("/stream")
async def chat_stream(websocket: WebSocket):
    """
    WebSocket endpoint for streaming RAG responses.
    
    Client sends: {"query": "...", "session_id": "...", "model": "..."}
    Server sends: {"type": "sources|token|done|error", "data": ...}
    """
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            user_id = DEFAULT_USER_ID
            query = data.get("query", "")
            session_id = data.get("session_id", "")
            model = data.get("model", config.DEFAULT_LLM_MODEL)

            if not query:
                await websocket.send_json({"type": "error", "data": "Query is required"})
                continue

            # Load history
            messages = database.get_session_messages(session_id, user_id)
            chat_history = [{"role": m["role"], "content": m["content"]} for m in messages]

            # Save user message first
            database.save_message(session_id=session_id, user_id=user_id, role="user", content=query)

            # Stream response
            full_response = []
            final_meta = {}

            for event in generate_rag_response_stream(
                user_query=query,
                chat_history=chat_history,
                model=model,
                session_id=session_id,
            ):
                await websocket.send_json(event)
                if event["type"] == "token":
                    full_response.append(event["data"])
                elif event["type"] == "done":
                    final_meta = event.get("data", {})

            # Save assistant response
            answer_text = "".join(full_response)
            database.save_message(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=answer_text,
                model_used=final_meta.get("model_used"),
                token_usage=final_meta.get("token_usage"),
            )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "data": "An unexpected error occurred"})
        except Exception:
            pass


# ─── Session Management ─────────────────────────────────────

@router.get("/sessions")
async def list_sessions():
    """Get all sessions for the default user."""
    sessions = database.get_user_sessions(DEFAULT_USER_ID)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get all messages for a specific session."""
    messages = database.get_session_messages(session_id, DEFAULT_USER_ID)
    return {"session_id": session_id, "messages": messages}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its messages."""
    database.delete_session(session_id, DEFAULT_USER_ID)
    return {"success": True, "message": "Session deleted"}


@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, req: SessionRenameRequest):
    """Rename a session."""
    database.rename_session(session_id, DEFAULT_USER_ID, req.title)
    return {"success": True, "message": "Session renamed"}


@router.post("/sessions/{session_id}/pin")
async def pin_session(session_id: str):
    """Toggle pin status of a session."""
    database.toggle_pin_session(session_id, DEFAULT_USER_ID)
    return {"success": True, "message": "Pin toggled"}


@router.delete("/sessions")
async def clear_all_sessions():
    """Delete all sessions."""
    database.clear_user_sessions(DEFAULT_USER_ID)
    return {"success": True, "message": "All sessions cleared"}


@router.get("/sessions/search/{query}")
async def search_sessions(query: str):
    """Search across all sessions by message content."""
    results = database.search_sessions(DEFAULT_USER_ID, query)
    return {"results": results}


@router.get("/models")
async def list_available_models():
    """Get all available LLM models with their info."""
    models = []
    for model_id, model_info in config.LLM_MODELS.items():
        models.append({
            "id": model_id,
            "display_name": model_info["display_name"],
            "description": model_info["description"],
            "provider": model_info["provider"],
            "speed": model_info["speed"],
        })
    return {"models": models, "default": config.DEFAULT_LLM_MODEL}
