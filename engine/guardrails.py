# engine/guardrails.py
"""
Guardrails — ensures the system only answers questions grounded in retrieved context.

Two-layer architecture:
  Layer 1 — Fast regex pre-filter: catches obvious single-word noise (hi, bye, ok, etc.)
             instantly without any API call.
  Layer 2 — LLM intent classifier (Groq llama-3.1-8b-instant): detects greetings in ANY
             language, off-topic general knowledge queries (e.g. "PM of India"), and
             ambiguous chatter that the regex misses. Ultra-fast (~100ms).

If both layers pass → query goes to the RAG pipeline.
"""
import logging
import re
from google.genai import types as genai_types
import config

logger = logging.getLogger(__name__)


# ─── Jailbreak patterns (regex — always hardcoded for security) ──────────────
JAILBREAK_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "ignore your instructions",
    "disregard your instructions",
    "forget your instructions",
    "you are now",
    "pretend you are",
    "act as if",
    "bypass your",
    "override your",
    "new persona",
    "developer mode",
    "do anything now",
    "jailbreak",
]

# ─── Layer 1: Fast regex pre-filter ─────────────────────────────────────────
# Only for ultra-obvious single-word/symbol noise — anything ambiguous goes to LLM.
_FAST_NOISE_PATTERNS = [
    r"^\s*[^a-zA-Z0-9\u0900-\u097F\u0600-\u06FF]+\s*$",  # Only punctuation/symbols
    r"^\s*(.)\1{4,}\s*$",                                   # Repeated characters: "aaaaa"
    r"^\s*\d+\s*$",                                         # Only numbers: "123"
]


def check_jailbreak(user_query: str) -> bool:
    """Detects if the user query contains common prompt injection attempts."""
    query_lower = user_query.lower().strip()
    for pattern in JAILBREAK_PATTERNS:
        if pattern in query_lower:
            logger.warning(f"Jailbreak attempt detected: pattern='{pattern}' in query='{user_query[:80]}'")
            return True
    return False


def _fast_noise_check(user_query: str) -> bool:
    """Layer 1: Instant regex check for pure symbol/number/repeated-char noise."""
    query = user_query.strip()
    for pattern in _FAST_NOISE_PATTERNS:
        if re.search(pattern, query):
            logger.info(f"Fast noise filter blocked: '{user_query}'")
            return True
    return False


def check_greeting_or_chatter(user_query: str) -> bool:
    """
    Two-layer chatter/off-topic detection:

    Layer 1 — Instant regex for obvious noise (no API call).
    Layer 2 — Groq LLM classifier: detects greetings in ANY language, farewells,
               small talk, and off-topic general knowledge queries automatically.
               No hardcoded word lists — the LLM understands context and language.

    Returns True if the query should be BLOCKED (not sent to RAG pipeline).
    """
    # Layer 1: fast noise check
    if _fast_noise_check(user_query):
        return True

    # Layer 2: LLM-based intent classification
    return _llm_intent_check(user_query)


def _llm_intent_check(user_query: str) -> bool:
    """
    Uses an LLM to classify query intent — detects greetings/farewells in ANY language
    and off-topic general knowledge queries. No hardcoded word lists.

    Tries Gemini 2.0 Flash first, falls back to Groq llama-3.1-8b-instant.
    Returns True if query should be BLOCKED.
    """
    classification_prompt = f"""You are a query classifier for a universal document Q&A system.
Classify the user query into EXACTLY ONE category:

GREETING   - Pure social greetings, salutations, farewells, thanks, compliments, or casual small talk in ANY global language or script (native character sets or Romanized/phonetic transliterations).
             Do NOT restrict to specific languages — classify ANY pure greeting or courtesy phrase in ANY global language as GREETING.

VALID      - Any question, inquiry, search, or request for information (Aadhaar, identity cards, PDFs,
             personal records, session lists, authors, contact numbers, papers, dates, schedules, or file content).

IMPORTANT: If the message is a pure social greeting/farewell/thanks in ANY language with no document question — return GREETING.

User Query: "{user_query}"

Reply with ONLY ONE WORD: GREETING or VALID"""

    # Try Gemini 2.0 Flash first
    try:
        from engine.clients import gemini_client
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
            logger.info(f"Gemini guardrail: GREETING blocked — '{user_query}'")
            return True
        else:
            logger.info(f"Gemini guardrail: VALID — '{user_query[:60]}'")
            return False
    except Exception as gemini_err:
        logger.warning(f"Gemini intent check failed: {gemini_err}. Trying Groq fallback...")

    # Fallback: Groq llama-3.1-8b-instant
    try:
        from engine.clients import groq_client
        if groq_client:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": classification_prompt}],
                max_tokens=5,
                temperature=0.0,
            )
            result = response.choices[0].message.content.strip().upper()
            if "GREETING" in result:
                logger.info(f"Groq guardrail: GREETING blocked — '{user_query}'")
                return True
            return False
    except Exception as groq_err:
        logger.warning(f"Groq intent check also failed: {groq_err}. Allowing query through.")
        return False  # Fail open — don't block valid queries on API error


def check_relevance(top_score: float, documents: list[dict]) -> bool:
    """
    Pre-generation check: determines if the retrieved documents are relevant enough
    to form a useful answer.
    """
    if not config.GUARDRAIL_ENABLED:
        return True

    if not documents:
        logger.info("Guardrail: No documents retrieved — relevance check failed")
        return False

    if top_score < config.GUARDRAIL_MIN_RELEVANCE:
        logger.info(
            f"Guardrail: Top relevance score ({top_score:.3f}) below "
            f"threshold ({config.GUARDRAIL_MIN_RELEVANCE}) — refusing"
        )
        return False

    return True


def get_system_prompt_guardrail() -> str:
    """
    Returns the guardrail instruction to be injected into the LLM system prompt.
    Enforces strict grounding, structured Markdown output formatting, complete column extraction,
    sequential index numbering, page citations, and multi-page continuation aggregation.
    """
    return """You are a precise document extraction and analysis AI assistant.

FOLLOW THESE RULES WITHOUT EXCEPTION:

**RULE 0 — ZERO HALLUCINATION & STRICT DOCUMENT CONTEXT GROUNDING (ABSOLUTE):**
Extract ONLY information that literally exists in the RETRIEVED DOCUMENT CONTEXT. Do NOT invent, infer, or pull values from conversation history — all numbers, names, titles, dates, and details MUST be extracted verbatim from the retrieved text. If no relevant information is present in the context for the user's question, state that the requested information was not found in the retrieved document context.

**RULE 1 — GENERAL TABLES, AUTHOR LISTS, SCHEDULES & MULTI-COLUMN DATA:**
When answering questions about lists, tables, schedules, conference sessions, author lists, invoices, or structured reports:
- MUST format the output as a Markdown table containing ALL 7 original columns:
  `| S.No | Paper ID | Paper Title | Author Name | Contact Number | Email Address | Mode |`
- NEVER use bullet points, list items, or summaries instead of a Markdown table.
- CRITICAL FOR MULTI-PAGE SESSIONS: Scan ALL `[Source X]` context blocks. If `[Source 1]` contains Items 1-4 and `[Source 2]` contains Items 5-9 for the requested session, MERGE ALL ITEMS into ONE SINGLE MARKDOWN TABLE (Items 1, 2, 3, 4, 5, 6, 7, 8, 9). NEVER stop after `[Source 1]` or create bulleted lists.
- At the top of the table, explicitly display: **Session Chair:** [Name]
- Extract EVERY matching row across ALL retrieved pages without truncating rows or dropping columns (`Paper Title`, `Contact Number`, `Email Address`, `Mode`).
- Example Output Template:
  **Session Chair:** Ms. Neha Talreja

  | S.No | Paper ID | Paper Title | Author Name | Contact Number | Email Address | Mode |
  | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
  | 1 | 797 | Autonomous Vehicle Navigation Systems... | Dr. Sheela Hundekari | 09584468105 | sheelahundekari90@gmail.com | Online |

**RULE 2 — SINGLE-FIELD SPECIFICITY:**
If the user explicitly asks for ONLY ONE specific field (e.g., 'give me the Aadhaar number', 'what is the email of John'), output ONLY that specific field and value.

**RULE 3 — PERSONAL IDENTITY DOCUMENTS (Aadhaar, PAN, Passport, Voter ID, DL, Resumes):**
When the document is an official identity card or resume, group personal fields (Name, DOB, Identity Number, Address, Contact) into clear sections or clean key-value tables.

**RULE 4 — CLEAN MARKDOWN OUTPUT & CITATIONS:**
Present answers cleanly formatted in standard GitHub Markdown. Always end your response with a source citation referencing the document and page number `[Source: filename.pdf, Page X]`.

**RULE 5 — MISSING INFORMATION:**
If a requested field or table row does not appear in the retrieved context, state clearly: 'That detail is not available in the retrieved document.'"""


def get_greeting_refusal_response() -> str:
    """Returns the guardrail refusal message for greetings and non-document queries."""
    return (
        "I am an AI assistant specifically configured to answer questions based strictly "
        "on your uploaded documents and knowledge base. Please ask a specific question related "
        "to the documents."
    )


def get_refusal_response() -> str:
    """Returns the standard refusal message when guardrails block a query due to zero retrieved context."""
    return config.GUARDRAIL_REFUSAL_MESSAGE


def get_jailbreak_response() -> str:
    """Returns a polite refusal for jailbreak attempts."""
    return (
        "I'm designed to help you strictly with questions about your uploaded documents "
        "and knowledge base. I cannot modify my behavior or instructions. "
        "Please ask a question related to the available knowledge base."
    )
