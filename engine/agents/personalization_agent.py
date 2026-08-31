# engine/agents/personalization_agent.py
"""
Personalization & User Identity Agent — manages user identity, name tracking, and profile memory.
Responds natively in the user's input language. Zero document context tokens used.
"""
import logging
import re
from engine.clients import gemini_client, groq_client
from google.genai import types as genai_types

logger = logging.getLogger(__name__)


class PersonalizationAgent:
    """Specialized Agent for managing user identity and profile preferences."""

    def extract_name(self, query: str) -> str | None:
        """Extract name from phrases like 'my name is Yash', 'mera naam Yash hai', 'I am Yash'."""
        patterns = [
            r"(?:my name is|i am|call me|this is|mera naam|naam hai)\s+([A-Z][a-z]+|[A-Za-z0-9_]+)",
            r"(?:name's)\s+([A-Za-z0-9_]+)",
        ]
        for p in patterns:
            match = re.search(p, query, re.IGNORECASE)
            if match:
                return match.group(1).capitalize()
        return None

    def run(self, user_query: str, user_name: str = None) -> tuple[str, str | None]:
        """
        Processes identity query.
        Returns (response_text, updated_user_name_if_any).
        """
        extracted_name = self.extract_name(user_query)
        active_name = extracted_name or user_name

        prompt = f"""You are a personalized AI assistant.
Current stored user name: {active_name or 'Unknown'}
User asked: "{user_query}"

If the user is telling you their name, acknowledge it warmly and confirm you will remember it.
If the user is asking what their name is or who they are, state their name cleanly.
Respond natively in the exact language/script of the user query (e.g. English, Hindi, Hinglish).
Keep response friendly and under 3 sentences."""

        # Try Gemini Flash
        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=150,
                    temperature=0.3,
                ),
            )
            if response and response.text:
                return response.text.strip(), extracted_name
        except Exception as e:
            logger.warning(f"PersonalizationAgent error: {e}")

        # Fallback to Groq
        try:
            if groq_client:
                res = groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150,
                    temperature=0.3,
                )
                return res.choices[0].message.content.strip(), extracted_name
        except Exception as e:
            logger.error(f"PersonalizationAgent Groq fallback error: {e}")

        if extracted_name:
            return f"Nice to meet you, {extracted_name}! I have noted your name.", extracted_name
        elif user_name:
            return f"Your name is {user_name}.", None
        else:
            return "I don't know your name yet! What should I call you?", None


personalization_agent = PersonalizationAgent()
