# engine/agents/web_search_agent.py
"""
Web Search & Real-Time Intelligence Agent — performs live internet search via Tavily API
ONLY when explicitly requested by the user. Zero document vector tokens used.
"""
import logging
from engine.web_search import search_live_internet
from engine.clients import gemini_client, groq_client
from google.genai import types as genai_types

logger = logging.getLogger(__name__)


class WebSearchAgent:
    """Specialized Agent for explicit online web searches via Tavily."""

    def run(self, user_query: str) -> str:
        """Perform live web search and summarize results."""
        search_results = search_live_internet(user_query)
        if not search_results:
            return "🌐 I searched the live web for your request, but could not retrieve any relevant results."

        excerpts = []
        for res in search_results[:4]:
            title = res.get("title", "Result")
            url = res.get("url", "#")
            content = res.get("content", "")
            excerpts.append(f"**[{title}]({url})**\n{content[:300]}")

        web_context = "\n\n".join(excerpts)
        prompt = f"""You are a Web Intelligence Agent summarizing live web search results.
User Request: "{user_query}"
Live Web Search Context:
{web_context}

Provide a clean, well-formatted response with clickable markdown links [Title](URL) for sources."""

        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=600,
                    temperature=0.3,
                ),
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            logger.warning(f"WebSearchAgent Gemini error: {e}")

        try:
            if groq_client:
                res = groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=600,
                    temperature=0.3,
                )
                return res.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"WebSearchAgent Groq fallback error: {e}")

        return f"🌐 **Live Web Search Results:**\n\n{web_context}"


web_search_agent = WebSearchAgent()
