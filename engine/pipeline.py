# engine/pipeline.py
"""
Main RAG pipeline orchestrator.
Coordinates: guardrail pre-checks → cache → Groq query expansion → retrieval → reranking → relevance guardrails → multi-LLM generation.
"""
import time
import logging
import re
from engine import retriever, reranker, generator, memory, guardrails, cache, web_search
from engine.token_counter import count_tokens_estimate, format_usage_display
import config

logger = logging.getLogger(__name__)


def generate_rag_response(
    user_query: str,
    chat_history: list[dict] = None,
    model: str = None,
    session_id: str = None,
    user_name: str = None,
) -> dict:
    """
    Executes the Multi-Agent Workflow via SupervisorAgent.
    """
    from engine.agents.supervisor import supervisor_agent
    start_time = time.time()
    
    res = supervisor_agent.run(
        user_query=user_query,
        chat_history=chat_history,
        model=model,
        session_id=session_id,
        user_name=user_name,
    )
    
    res["elapsed"] = round(time.time() - start_time, 2)
    if "token_display" not in res:
        res["token_display"] = format_usage_display(res.get("token_usage", {}))
        
    return res

    # ─── Step 3: Semantic cache lookup ──────────────────────
    cached_response = cache.lookup(user_query)
    if cached_response:
        cached_response["model_used"] = "cache"
        cached_response["elapsed"] = time.time() - start_time
        cached_response["search_query"] = user_query
        cached_response["token_usage"] = {
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
        }
        cached_response["token_display"] = "📊 Served from cache (0 tokens used)"
        return cached_response

    # ─── Step 4: Groq Query Expansion ───────────────────────
    search_query = memory.contextualize_query(user_query, chat_history)

    # ─── Step 5: Internal knowledge retrieval ───────────────
    internal_docs = retriever.search_internal_knowledge(
        search_query, session_id=session_id
    )

    # ─── Step 6: Cross-encoder reranking ────────────────────
    reranked_docs, top_score = reranker.rerank_documents(
        search_query, internal_docs, top_n=config.RERANK_TOP_N
    )

    # ─── Step 7: Relevance & Context Grounding Check ────────
    if not guardrails.check_relevance(top_score, reranked_docs):
        # Strict guardrail refusal — non-grounded / out of scope query
        return _build_response(
            answer=guardrails.get_refusal_response(),
            search_query=search_query,
            sources=[],
            source_type="guardrail",
            confidence_score=top_score,
            model_used=selected_model,
            token_usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            elapsed=time.time() - start_time,
            cached=False,
        )

    final_docs = reranked_docs
    source_type = "internal"

    # ─── Step 8: Build generation prompt ────────────────────
    context_str = _format_context(final_docs)
    history_str = memory.format_history_for_prompt(chat_history)
    guardrail_prompt = guardrails.get_system_prompt_guardrail()

    system_prompt = f"""{guardrail_prompt}

{history_str}

Context:
{context_str}

Question: {user_query}

Answer:"""

    # ─── Step 9: Generate with selected model (auto-fallback) 
    answer_text, token_usage, model_used = generator.generate(
        prompt=system_prompt,
        model=selected_model,
    )

    if not answer_text or "rate-limited" in answer_text.lower():
        from engine.generator import _clean_llm_output
        answer_text = _clean_llm_output(answer_text or _build_fallback_answer(final_docs), system_prompt)

    # ─── Step 10: Store in semantic cache ───────────────────
    cache.store(
        query=user_query,
        answer=answer_text,
        sources=final_docs,
        source_type=source_type,
        confidence_score=top_score,
    )

    elapsed = time.time() - start_time

    return _build_response(
        answer=answer_text,
        search_query=search_query,
        sources=final_docs,
        source_type=source_type,
        confidence_score=top_score,
        model_used=model_used,
        token_usage=token_usage,
        elapsed=elapsed,
        cached=False,
    )


def generate_rag_response_stream(
    user_query: str,
    chat_history: list[dict] = None,
    model: str = None,
    session_id: str = None,
    user_name: str = None,
):
    """
    Streaming version of the multi-agent RAG workflow.
    Integrates SupervisorAgent intent routing, vector retrieval, cross-encoder reranking,
    smart web fallback, and token streaming.
    """
    if chat_history is None:
        chat_history = []

    start_time = time.time()
    selected_model = model or config.DEFAULT_LLM_MODEL
    from engine.agents.supervisor import supervisor_agent

    # Security check: Jailbreak
    if guardrails.check_jailbreak(user_query):
        yield {"type": "token", "data": guardrails.get_jailbreak_response()}
        yield {"type": "done", "data": {"model_used": selected_model, "elapsed": round(time.time() - start_time, 2)}}
        return

    # Classify intent via SupervisorAgent FIRST
    intent = supervisor_agent.classify_intent(user_query)
    logger.info(f"Supervisor Agent (Stream): Intent '{intent}' for query='{user_query[:50]}'")

    # Non-RAG sub-agent routes (Greeting, Personalization, Guardrail, Doc Manage, Web Search, Export)
    if intent in ("GREETING", "PERSONALIZATION", "GUARDRAIL", "DOC_MANAGE", "WEB_SEARCH", "EXPORT"):
        agent_res = supervisor_agent.run(
            user_query=user_query,
            chat_history=chat_history,
            model=selected_model,
            session_id=session_id,
            user_name=user_name,
        )
        yield {"type": "sources", "data": {"sources": agent_res.get("sources", []), "source_type": agent_res.get("source_type", "agent")}}
        yield {"type": "token", "data": agent_res.get("answer", "")}
        yield {
            "type": "done",
            "data": {
                "model_used": agent_res.get("model_used", selected_model),
                "elapsed": round(time.time() - start_time, 2),
                "cached": False,
                "token_usage": agent_res.get("token_usage", {}),
            },
        }
        return

    # Check semantic cache ONLY for DOCUMENT_RAG queries
    cached_response = cache.lookup(user_query)
    if cached_response:
        yield {"type": "sources", "data": {"sources": cached_response.get("sources", []), "source_type": "cached"}}
        yield {"type": "token", "data": cached_response["answer"]}
        yield {"type": "done", "data": {"model_used": "cache", "elapsed": round(time.time() - start_time, 2), "cached": True}}
        return

    # DOCUMENT_RAG Pipeline
    search_query = memory.contextualize_query(user_query, chat_history)
    internal_docs = retriever.search_internal_knowledge(search_query, session_id=session_id)
    reranked_docs, top_score = reranker.rerank_documents(search_query, internal_docs)
    final_docs = reranked_docs if reranked_docs else internal_docs[:config.RERANK_TOP_N]

    # Check relevance
    if not internal_docs or not guardrails.check_relevance(top_score, final_docs):
        # Attempt smart live web search fallback if internal documents lack information
        try:
            from engine.agents.web_search_agent import web_search_agent
            web_ans = web_search_agent.run(user_query)
            if web_ans and "could not retrieve any relevant results" not in web_ans:
                yield {"type": "sources", "data": {"sources": [], "source_type": "live_web", "confidence_score": 0.8}}
                yield {"type": "token", "data": f"🌐 *Note: The requested detail was not found in your uploaded documents. Retrieved via Live Web Intelligence:*\n\n{web_ans}"}
                yield {"type": "done", "data": {"model_used": selected_model, "elapsed": round(time.time() - start_time, 2)}}
                return
        except Exception as web_err:
            logger.warning(f"Stream web fallback error: {web_err}")

        fallback_msg = (
            "I am your Intellect RAG Assistant. I searched all of your uploaded documents, "
            "but could not find information relevant to your specific question. "
            "If you would like me to search the web for this topic, just ask me to search online!"
        )
        yield {"type": "token", "data": fallback_msg}
        yield {"type": "done", "data": {"model_used": selected_model, "elapsed": round(time.time() - start_time, 2)}}
        return

    # Send retrieved sources to frontend
    yield {
        "type": "sources",
        "data": {
            "sources": final_docs,
            "source_type": "internal",
            "confidence_score": top_score,
        },
    }

    # Format context & build prompt (Strictly grounding on retrieved context without stale conversation history)
    context_str = _format_context(final_docs)
    guardrail_prompt = guardrails.get_system_prompt_guardrail()
    name_clause = f"The user's name is {user_name}." if user_name else ""

    system_prompt = f"""{guardrail_prompt}
{name_clause}

RETRIEVED DOCUMENT CONTEXT:
{context_str}

USER QUESTION: {user_query}

Answer:"""

    # Generate complete answer using generator.generate to enforce _clean_llm_output rules (single field isolation, structured markdown tables, deduplication)
    answer_text, token_usage, model_used = generator.generate(
        prompt=system_prompt,
        model=selected_model,
    )

    if not answer_text:
        answer_text = _build_fallback_answer(final_docs)

    # Stream the cleaned response text to the frontend
    yield {"type": "token", "data": answer_text}

    # Store in semantic cache if clean answer
    if answer_text and not answer_text.startswith("⚠️"):
        cache.store(
            query=user_query,
            answer=answer_text,
            sources=final_docs,
            source_type="internal",
            confidence_score=top_score,
        )

    elapsed = time.time() - start_time

    yield {
        "type": "done",
        "data": {
            "model_used": selected_model,
            "elapsed": round(elapsed, 2),
            "cached": False,
            "token_usage": {
                "input_tokens": count_tokens_estimate(system_prompt),
                "output_tokens": count_tokens_estimate(answer_text),
                "total_tokens": count_tokens_estimate(system_prompt) + count_tokens_estimate(answer_text),
            },
        },
    }


# Maximum context characters allowed in LLM prompt
MAX_CONTEXT_CHARS = 2_800
MAX_CHUNK_CHARS = 3_000  # Per-chunk cap so one large chunk can't consume the whole budget


def _format_context(documents: list[dict]) -> str:
    """Format retrieved documents into context block for LLM.
    
    Applies two-level size management:
    1. Per-chunk cap (MAX_CHUNK_CHARS) — trims oversized individual chunks.
    2. Total budget cap (MAX_CONTEXT_CHARS) — stops adding chunks once budget is reached,
       ensuring the prompt fits within model token limits (especially Groq 8B's 6k TPM).
    """
    if not documents:
        return "No relevant documents found."

    # Keep exact relevance rank order produced by Cohere reranker (do not sort alphabetically by filename)
    pass

    boilerplate_patterns = [
        r"IEEE International Conference on\s*",
        r"Computational, Communication and Information Technology\s*",
        r"\[ICCCIT2025\]\s*",
        r"IPS ACADEMY\s*",
        r"Institute of Engineering & Science, Indore\s*",
        r"\(A UGC Autonomous Institute, Affiliated to RGPV\)\s*",
        r"Computer Science & Engineering Department\s*",
        r"\(NBA Accredited UG Programme\)\s*",
        r"SESSION DETAILS\s*",
    ]

    parts = []
    total_chars = 0

    for i, d in enumerate(documents, 1):
        source_name = d.get("source_file", "Document")
        page_num = d.get("page_number", "N/A")
        chunk_type = d.get("chunk_type", "text")
        text = d.get("text", "")

        # Strip repetitive header boilerplate to conserve tokens
        for pattern in boilerplate_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        text = text.strip()

        # Per-chunk cap: trim if a single chunk is too long
        if len(text) > MAX_CHUNK_CHARS:
            text = text[:MAX_CHUNK_CHARS] + "..."

        chunk_str = f"[Source {i}]: File: {source_name} (Page {page_num}, Type: {chunk_type})\n{text}"

        # Total budget cap: stop adding chunks once budget is reached
        if total_chars + len(chunk_str) > MAX_CONTEXT_CHARS:
            logger.info(
                f"Context budget reached at chunk {i}/{len(documents)} "
                f"({total_chars} chars). Truncating context."
            )
            break

        parts.append(chunk_str)
        total_chars += len(chunk_str)

    return "\n\n".join(parts)


def _build_fallback_answer(documents: list[dict]) -> str:
    """Return a clean error message if all LLM models fail — never expose raw document chunks."""
    return (
        "⚠️ All AI models are currently rate-limited. This is temporary — Groq resets in ~1 hour, "
        "Gemini resets in ~1 minute. Please try your query again shortly."
    )


def _build_response(
    answer: str,
    search_query: str,
    sources: list[dict],
    source_type: str,
    confidence_score: float,
    model_used: str,
    token_usage: dict,
    elapsed: float,
    cached: bool,
) -> dict:
    """Build standard response dictionary."""
    return {
        "answer": answer,
        "search_query": search_query,
        "sources": sources,
        "source_type": source_type,
        "confidence_score": confidence_score,
        "model_used": model_used,
        "token_usage": token_usage,
        "token_display": format_usage_display(token_usage),
        "elapsed": round(elapsed, 2),
        "cached": cached,
    }
