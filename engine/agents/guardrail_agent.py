# engine/agents/guardrail_agent.py
"""
Guardrail Policy Agent — enforces strict domain scope isolation and policy refusals.
Blocks jailbreak attempts and off-topic general knowledge queries ("PM of India") during document sessions.
Responds cleanly in the user's input language. Zero document context tokens used.
"""
import logging
from engine.clients import gemini_client, groq_client
from google.genai import types as genai_types
import config

logger = logging.getLogger(__name__)


class GuardrailAgent:
    """Specialized Agent for enforcing policy boundaries and domain refusals."""

    def run(self, user_query: str, is_jailbreak: bool = False) -> str:
        """Generates polite, language-matched domain refusal."""
        if is_jailbreak:
            return config.GUARDRAIL_REFUSAL_MESSAGE

        system_instruction = (
            "You are the security and policy guardrail agent for an enterprise document Q&A system.\n\n"
            "STRICT LANGUAGE MATCHING RULES:\n"
            "- If the user question is written in English (e.g. 'who is pm of india', 'tell me about weather'), your response MUST be 100% in clear English.\n"
            "- If the user question is written in Devanagari script (e.g. 'भारत के प्रधानमंत्री कौन हैं'), respond in Devanagari Hindi.\n"
            "- If the user question contains Romanized Hindi words (e.g. 'bharat ke pradhan mantri kaun hain'), respond in Hinglish.\n\n"
            "BEHAVIOR RULES:\n"
            "1. Respond in 1-2 polite sentences explaining that you can only answer questions based strictly on their uploaded documents.\n"
            "2. Invite them to ask a question related to their uploaded files.\n"
            "3. Output ONLY the response text for the user. Do NOT include preambles, reasoning, or system notes."
        )

        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"{system_instruction}\n\nUser Question: {user_query}",
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=120,
                    temperature=0.2,
                ),
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            logger.warning(f"GuardrailAgent Gemini error: {e}")

        try:
            if groq_client:
                res = groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_query},
                    ],
                    max_tokens=120,
                    temperature=0.2,
                )
                return res.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"GuardrailAgent Groq fallback error: {e}")

        return config.GUARDRAIL_REFUSAL_MESSAGE


guardrail_agent = GuardrailAgent()
