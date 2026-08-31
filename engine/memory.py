# engine/memory.py
"""
Conversation memory & Query Expansion engine — builds context from chat history
and uses Groq (Llama 3.3 70B) for ultra-fast query optimization before vector retrieval.
"""
import logging
import config
from engine.clients import groq_client

logger = logging.getLogger(__name__)


def build_conversation_context(chat_history: list[dict]) -> str:
    """Formats recent conversation turns into a context block for the LLM prompt."""
    if not chat_history:
        return ""

    max_messages = config.MAX_HISTORY_TURNS * 2
    recent = chat_history[-max_messages:]

    lines = []
    for msg in recent:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role_label}: {msg['content']}")

    context = "\n".join(lines)
    logger.debug(f"Built conversation context from {len(recent)} messages")
    return context


def contextualize_query(user_query: str, chat_history: list[dict] = None) -> str:
    """
    Rewrites and expands a user query into an optimized vector search query.
    Uses Groq (Llama 3.3 70B via OpenAI-compatible SDK) for ultra-fast query expansion if available.
    """
    if chat_history is None:
        chat_history = []

    # Determine if current query is a follow-up query requiring conversation context
    follow_up_indicators = [
        "them", "they", "it", "its", "those", "these", "that", "this",
        "more", "other", "another", "else", "also", "above", "previous",
        "same", "similar", "related", "again", "continue", "elaborate",
        "explain", "his", "her", "their", "what about", "how about",
    ]
    query_lower = user_query.lower()
    is_follow_up = any(indicator in query_lower.split() or indicator in query_lower for indicator in follow_up_indicators)

    # Try Groq ultra-fast query expansion first
    if groq_client:
        try:
            history_hint = ""
            if chat_history and is_follow_up:
                last_user = next((m["content"] for m in reversed(chat_history) if m["role"] == "user"), "")
                last_assistant = next((m["content"] for m in reversed(chat_history) if m["role"] == "assistant"), "")
                if last_user:
                    history_hint = f"Previous Question Context: {last_user}\n"
                    if last_assistant:
                        history_hint += f"Previous Answer Context: {last_assistant[:200]}\n"
                    
            prompt = (
                f"{history_hint}Current User Query: {user_query}\n\n"
                "Rephrase and expand this user query into 1 clear, detailed search query optimized for vector database retrieval of document text, tables, and visual charts.\n"
                "CRITICAL: Preserve key names, session numbers (e.g. Session 01), dates (e.g. 07/02/2025), paper IDs, author lists, and exact user terms verbatim.\n"
                "Do NOT invent or alter the semantic meaning of the user query (e.g., do NOT turn 'list of authors for session 1' into 'authors serving as session chairs').\n"
                "Output ONLY the search query text, without introduction or explanations."
            )
            
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1,
            )
            
            expanded = completion.choices[0].message.content.strip()
            if expanded:
                logger.info(f"Groq query expansion: '{user_query}' → '{expanded}'")
                return expanded
        except Exception as e:
            logger.warning(f"Groq query expansion failed: {e}. Using fallback contextualizer...")

    # Fallback heuristic contextualizer
    if not chat_history:
        return user_query

    follow_up_indicators = [
        "them", "they", "it", "its", "those", "these", "that", "this",
        "more", "other", "another", "else", "also", "above", "previous",
        "same", "similar", "related", "again", "continue", "elaborate",
        "explain", "details", "tell me", "what about", "how about",
    ]
    
    query_lower = user_query.lower()
    is_follow_up = any(indicator in query_lower for indicator in follow_up_indicators)

    if not is_follow_up:
        return user_query

    last_user_msg = ""
    last_assistant_msg = ""
    
    for msg in reversed(chat_history):
        if msg["role"] == "assistant" and not last_assistant_msg:
            last_assistant_msg = msg["content"][:200]
        elif msg["role"] == "user" and not last_user_msg:
            last_user_msg = msg["content"]
        if last_user_msg and last_assistant_msg:
            break

    contextualized = f"Based on the previous question about '{last_user_msg}': {user_query}"
    logger.info(f"Contextualized follow-up query: '{user_query}' → '{contextualized[:100]}...'")
    return contextualized


def format_history_for_prompt(chat_history: list[dict]) -> str:
    """Formats full conversation history for inclusion in LLM prompt."""
    if not chat_history:
        return ""

    max_messages = config.MAX_HISTORY_TURNS * 2
    recent = chat_history[-max_messages:]

    formatted = "=== CONVERSATION HISTORY ===\n"
    for msg in recent:
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg.get("content", "")
        if role == "Assistant":
            # Sanitize old assistant responses — strip stale card formatting, emojis, and tables so LLM doesn't copy legacy styles
            content_clean = re.sub(r'[🪪👥📝🗺️]', '', content)
            if "| --- |" in content_clean or "Extracted Document Details" in content_clean:
                content_clean = "[Provided structured table response]"
            elif len(content_clean) > 150:
                content_clean = content_clean[:150] + "..."
            formatted += f"Assistant: {content_clean}\n"
        else:
            formatted += f"User: {content}\n"
    formatted += "=== END HISTORY ===\n"

    return formatted
