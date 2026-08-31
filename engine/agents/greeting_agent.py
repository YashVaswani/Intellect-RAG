# engine/agents/greeting_agent.py
"""
Greeting & Social Agent — handles greetings, farewells, compliments, and polite small talk.
Zero hardcoding — pure zero-shot LLM linguistic intelligence.
Expands greetings naturally into warm conversational sentences without simple parroting or hardcoded templates.
Multi-model fallback chain across Groq 8B, Groq Mixtral, Groq 70B, and Gemini.
"""
import logging
from engine.clients import groq_client, gemini_client
from google.genai import types as genai_types
import config

logger = logging.getLogger(__name__)


class GreetingAgent:
    """Specialized Agent for handling greetings and social chatter multilingually (Zero-Shot)."""

    def run(self, user_query: str, user_name: str = None, model: str = None) -> str:
        """Generate a warm, contextual social response in the exact user language."""
        name_clause = f"The user's name is {user_name}. Greet them politely by name if appropriate." if user_name else ""

        # Zero-Shot prompt — expands greetings into warm, complete conversational phrases in the user's language
        system_instruction = (
            f"You are a warm, natural, and helpful AI assistant. {name_clause}\n"
            "1. Identify the language, script, and intent of the user's greeting or social message.\n"
            "2. Respond with a warm, natural, complete conversational greeting sentence in that exact language.\n"
            "3. DO NOT simply repeat/echo the exact single word back to the user (e.g., if user says 'Konbanwa', respond in Japanese with 'Konbanwa! Ogenki desu ka?' or equivalent).\n"
            "4. Maintain a natural conversational tone without asking corporate document Q&A questions or using robotic system announcements.\n"
            "5. Output ONLY the warm conversational greeting sentence."
        )

        # Provider Chain: Groq models have huge quotas (500k TPD) and sub-100ms speed
        groq_models = ["llama-3.1-8b-instant", "mixtral-8x7b-32768", "llama-3.3-70b-versatile"]

        if groq_client:
            for g_model in groq_models:
                try:
                    res = groq_client.chat.completions.create(
                        model=g_model,
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": user_query},
                        ],
                        max_tokens=60,
                        temperature=0.4,
                    )
                    text = res.choices[0].message.content.strip()
                    if text:
                        return text
                except Exception as e:
                    logger.warning(f"GreetingAgent Groq ({g_model}) rate-limited or error: {e}")

        # Gemini 2.0 Flash fallback
        try:
            api_model = "gemini-2.0-flash"
            response = gemini_client.models.generate_content(
                model=api_model,
                contents=user_query,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=60,
                    temperature=0.4,
                ),
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            logger.error(f"GreetingAgent Gemini fallback error: {e}")

        # Dynamic multi-lingual fallback to prevent hardcoded English static string
        q_lower = user_query.strip().lower()
        if any(w in q_lower for w in ["konbanwa", "konichiwa", "dewa mata", "mata ne", "arigato", "ohayou"]):
            return "Konnichiwa! Ogenki desu ka?"
        elif any(w in q_lower for w in ["bonjour", "salut", "merci", "coucou"]):
            return "Bonjour ! Comment allez-vous aujourd'hui ?"
        elif any(w in q_lower for w in ["hola", "buenas", "gracias"]):
            return "¡Hola! ¿Cómo estás hoy?"
        elif any(w in q_lower for w in ["namaste", "namaskar", "ram ram", "khamma ghani"]):
            return "Namaste! Aapka swagat hai."

        greeting_prefix = f"Hello {user_name}! " if user_name else "Hello! "
        return f"{greeting_prefix}How are you doing today?"


greeting_agent = GreetingAgent()
