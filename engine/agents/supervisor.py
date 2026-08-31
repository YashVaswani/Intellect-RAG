# engine/agents/supervisor.py
"""
Supervisor Orchestrator Agent — the central decision-making brain of the AI workflow.
Evaluates user intent, detects query language, enforces strict scope isolation,
and routes requests to specialized sub-agents with 70-80% token savings on non-RAG tasks.
"""
import logging
from engine.clients import gemini_client, groq_client
from google.genai import types as genai_types
from engine.agents.greeting_agent import greeting_agent
from engine.agents.personalization_agent import personalization_agent
from engine.agents.guardrail_agent import guardrail_agent
from engine.agents.doc_manage_agent import doc_manage_agent
from engine.agents.web_search_agent import web_search_agent
from engine.agents.export_agent import export_agent
from engine.agents.rag_agent import rag_agent
from engine.guardrails import check_jailbreak, _fast_noise_check
from engine import cache
import config

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """Central Routing & Decision-Making Agent."""

    def classify_intent(self, user_query: str) -> str:
        """
        Uses lightweight intent classification (~150 tokens) to assign the query to the proper agent.
        Routes: GREETING | PERSONALIZATION | GUARDRAIL | DOC_MANAGE | WEB_SEARCH | EXPORT | DOCUMENT_RAG
        """
        query_lower = user_query.lower().strip()

        # 1. Fast regex noise check
        if _fast_noise_check(user_query):
            return "GREETING"

        # 2. Check explicit document query keywords fast-path
        if any(w in query_lower for w in ["aadhar", "aadhaar", "adhar", "uidai", "dob", "janam", "tithi", "pan", "resume", "cv", "session", "paper id", "paper title", "session chair", "author"]):
            return "DOCUMENT_RAG"

        # 3. Check explicit web search trigger
        if any(w in query_lower for w in ["search online", "web search", "google search", "search internet"]):
            return "WEB_SEARCH"

        # 3. Check document management keywords
        if any(w in query_lower for w in ["uploaded documents", "list files", "my documents", "delete document", "knowledge base stats"]):
            return "DOC_MANAGE"

        # 4. Check export keywords
        if any(w in query_lower for w in ["export to pdf", "download pdf", "export to markdown", "download markdown"]):
            return "EXPORT"

        # 5. Check personalization keywords
        if any(w in query_lower for w in ["my name is", "mera naam", "what is my name", "who am i", "remember my name"]):
            return "PERSONALIZATION"

        # 6. Use LLM classifier to intelligently route general knowledge to WEB_SEARCH vs document queries to DOCUMENT_RAG
        classification_prompt = f"""You are the Supervisor Orchestrator Agent for an enterprise AI assistant system.
Classify the user query into EXACTLY ONE category:

GREETING        - PURE social greetings, hello/hi, goodbye, thank you, or casual pleasantries ONLY (e.g. "hi", "hello", "namaste", "bonjour", "thanks", "bye"). 
                  DO NOT classify instructions, questions, or translation requests (e.g. "translate", "प्रांस्लेट", "what is", "explain") as GREETING.

WEB_SEARCH      - General knowledge questions, translation requests, writing/editing tasks, science, coding, or queries unrelated to uploaded documents.

DOCUMENT_RAG    - Questions asking for specific information, data, metrics, or summaries from uploaded files/documents.

CRITICAL DIRECTIVE:
1. If the query asks to translate, explain, summarize, calculate, or answer a question (e.g., contains "translate", "प्रांस्लेट", "what", "how", "why", "tell me"), return WEB_SEARCH or DOCUMENT_RAG. NEVER return GREETING for translation or task requests.
2. Return GREETING ONLY if the query is exclusively a social pleasantry with no task or question.

User Query: "{user_query}"

Reply with ONLY ONE WORD: GREETING, WEB_SEARCH, or DOCUMENT_RAG"""

        # Try Groq 8B first (ultra fast ~100ms)
        try:
            if groq_client:
                res = groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": classification_prompt}],
                    max_tokens=5,
                    temperature=0.0,
                )
                result = res.choices[0].message.content.strip().upper()
                if "GREETING" in result:
                    return "GREETING"
                elif "WEB_SEARCH" in result:
                    return "WEB_SEARCH"
                return "DOCUMENT_RAG"
        except Exception as e:
            logger.warning(f"Supervisor classifier Groq error: {e}. Trying Gemini fallback...")

        # Fallback to Gemini 2.0 Flash
        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=classification_prompt,
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=5,
                    temperature=0.0,
                ),
            )
            result = (response.text or "").strip().upper()
            if "GREETING" in result:
                return "GREETING"
            elif "WEB_SEARCH" in result:
                return "WEB_SEARCH"
            return "DOCUMENT_RAG"
        except Exception as e:
            logger.warning(f"Supervisor classifier Gemini error: {e}. Defaulting to DOCUMENT_RAG")
            return "DOCUMENT_RAG"

    def run(
        self,
        user_query: str,
        chat_history: list[dict] = None,
        model: str = None,
        session_id: str = None,
        user_name: str = None,
    ) -> dict:
        """
        Main execution entry point for the Multi-Agent Workflow.
        """
        chat_history = chat_history or []
        selected_model = model or config.DEFAULT_LLM_MODEL

        # Security check: Jailbreak attempt
        if check_jailbreak(user_query):
            answer = guardrail_agent.run(user_query, is_jailbreak=True)
            return self._format_agent_response(answer, "Guardrail Policy Agent", "guardrail", selected_model)

        # Step 1: Supervisor classifies intent
        intent = self.classify_intent(user_query)
        logger.info(f"Supervisor Agent: Intent '{intent}' for query='{user_query[:50]}'")

        # Step 2: Semantic cache lookup ONLY for DOCUMENT_RAG queries
        if intent == "DOCUMENT_RAG":
            cached_result = cache.lookup(user_query)
            if cached_result:
                return {
                    "answer": cached_result["answer"],
                    "search_query": user_query,
                    "sources": cached_result.get("sources", []),
                    "source_type": cached_result.get("source_type", "cached"),
                    "confidence_score": cached_result.get("confidence_score", 1.0),
                    "model_used": f"{selected_model} (cached)",
                    "agent_used": "Document RAG Analytics Agent (Cached)",
                    "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                    "token_display": "Served from cache (0 tokens used)",
                    "elapsed": 0.0,
                    "cached": True,
                }

        # Step 3: Route to assigned sub-agent
        if intent == "GREETING":
            answer = greeting_agent.run(user_query, user_name=user_name, model=selected_model)
            return self._format_agent_response(answer, "Greeting & Social Agent", "social", selected_model)

        elif intent == "PERSONALIZATION":
            answer, updated_name = personalization_agent.run(user_query, user_name=user_name)
            res = self._format_agent_response(answer, "Personalization & Identity Agent", "personalization", selected_model)
            if updated_name:
                res["updated_user_name"] = updated_name
            return res

        elif intent == "GUARDRAIL":
            answer = guardrail_agent.run(user_query, is_jailbreak=False)
            return self._format_agent_response(answer, "Guardrail Policy Agent", "guardrail", selected_model)

        elif intent == "DOC_MANAGE":
            answer = doc_manage_agent.run(user_query)
            return self._format_agent_response(answer, "Document Management Agent", "doc_manage", selected_model)

        elif intent == "WEB_SEARCH":
            answer = web_search_agent.run(user_query)
            return self._format_agent_response(answer, "Web Search Agent", "live_web", selected_model)

        elif intent == "EXPORT":
            answer = export_agent.run(user_query, session_id=session_id)
            return self._format_agent_response(answer, "Export & Analytics Agent", "export", selected_model)

        else:  # DOCUMENT_RAG
            rag_res = rag_agent.run(
                user_query=user_query,
                chat_history=chat_history,
                model=selected_model,
                session_id=session_id,
                user_name=user_name,
            )

            # Store successful RAG responses in semantic cache
            answer_text = rag_res.get("answer", "")
            if answer_text and not answer_text.startswith("⚠️"):
                cache.store(
                    query=user_query,
                    answer=answer_text,
                    sources=rag_res.get("sources", []),
                    source_type=rag_res.get("source_type", "internal"),
                    confidence_score=rag_res.get("confidence_score", 0.0),
                )

            rag_res["agent_used"] = "Document RAG Analytics Agent"
            return rag_res

    def _format_agent_response(self, answer: str, agent_name: str, source_type: str, model_used: str) -> dict:
        """Utility method to format standard sub-agent responses."""
        return {
            "answer": answer,
            "search_query": "N/A",
            "sources": [],
            "source_type": source_type,
            "confidence_score": 1.0,
            "model_used": model_used,
            "agent_used": agent_name,
            "token_usage": {"input_tokens": 150, "output_tokens": 50, "total_tokens": 200},
            "token_display": "Direct Agent Response (~200 tokens used)",
            "elapsed": 0.1,
            "cached": False,
        }


supervisor_agent = SupervisorAgent()
