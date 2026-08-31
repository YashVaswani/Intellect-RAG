# engine/agents/rag_agent.py
"""
Document RAG Analytics Agent — specialized agent for high-precision document search,
cross-encoder reranking, markdown table formatting, and multilingual Q&A grounding.
Uses vector document context budget management (~14k chars / ~3.5k tokens).
"""
import logging
from engine.memory import contextualize_query
from engine.retriever import search_internal_knowledge
from engine.reranker import rerank_documents
from engine import generator
import config

logger = logging.getLogger(__name__)


class DocumentRAGAgent:
    """Specialized Agent for executing vector retrieval, reranking, and document Q&A generation."""

    def run(
        self,
        user_query: str,
        chat_history: list[dict] = None,
        model: str = None,
        session_id: str = None,
        user_name: str = None,
    ) -> dict:
        """
        Executes the high-precision Document RAG pipeline.
        Returns unified dictionary with answer, sources, confidence_score, token_usage, model_used.
        """
        chat_history = chat_history or []
        selected_model = model or config.DEFAULT_LLM_MODEL

        # Step 1: Query expansion
        search_query = contextualize_query(user_query, chat_history)

        # Step 2: Vector retrieval
        retrieved_docs = search_internal_knowledge(
            query=search_query,
            session_id=session_id,
        )

        # Helper method for smart fallback when internal docs do not contain the answer
        def _handle_missing_doc_context(query: str, search_q: str, conf_score: float) -> dict:
            try:
                from engine.agents.web_search_agent import web_search_agent
                web_ans = web_search_agent.run(query)
                if web_ans and "could not retrieve any relevant results" not in web_ans:
                    return {
                        "answer": f"🌐 *Note: The requested information was not found in your uploaded documents. Retrieved via Live Web Intelligence:*\n\n{web_ans}",
                        "search_query": search_q,
                        "sources": [],
                        "source_type": "live_web",
                        "confidence_score": 0.8,
                        "model_used": selected_model,
                        "token_usage": {"input_tokens": 150, "output_tokens": 100, "total_tokens": 250},
                    }
            except Exception as err:
                logger.warning(f"Smart web fallback error: {err}")

            return {
                "answer": (
                    "I am your Intellect RAG Assistant. I searched all of your uploaded documents, "
                    "but could not find information relevant to your specific question. "
                    "If you would like me to search the web for this topic, just ask me to search online!"
                ),
                "search_query": search_q,
                "sources": [],
                "source_type": "internal",
                "confidence_score": conf_score,
                "model_used": selected_model,
                "token_usage": {},
            }

        if not retrieved_docs:
            return _handle_missing_doc_context(user_query, search_query, 0.0)

        # Step 3: Rerank
        reranked_docs, top_score = rerank_documents(
            query=search_query,
            documents=retrieved_docs,
            top_n=config.RERANK_TOP_N,
        )

        final_docs = reranked_docs if reranked_docs else retrieved_docs[:config.RERANK_TOP_N]

        # Step 4: Relevance guardrail check
        from engine.guardrails import check_relevance
        if not check_relevance(top_score, final_docs):
            return _handle_missing_doc_context(user_query, search_query, top_score)

        # Step 5: Format context with budget cap (~14k chars)
        from engine.pipeline import _format_context
        context_str = _format_context(final_docs)

        # Step 6: Build prompt (incorporating user name & multilingual grounding)
        from engine.guardrails import get_system_prompt_guardrail
        guardrail_rules = get_system_prompt_guardrail()
        name_clause = f"The user's name is {user_name}." if user_name else ""

        system_prompt = f"""{guardrail_rules}
{name_clause}

RETRIEVED DOCUMENT CONTEXT:
{context_str}

USER QUESTION: {user_query}

Answer:"""


        # Step 7: Generate response
        answer_text, token_usage, model_used = generator.generate(
            prompt=system_prompt,
            model=selected_model,
        )

        if not answer_text:
            from engine.pipeline import _build_fallback_answer
            answer_text = _build_fallback_answer(final_docs)

        return {
            "answer": answer_text,
            "search_query": search_query,
            "sources": final_docs,
            "source_type": "internal",
            "confidence_score": top_score,
            "model_used": model_used,
            "token_usage": token_usage,
        }


rag_agent = DocumentRAGAgent()
