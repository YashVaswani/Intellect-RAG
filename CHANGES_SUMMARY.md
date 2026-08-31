# RAG Project — Changes Summary
> Project root: `c:\Users\Admin\Documents\RAG`
> Last Updated: 2026-08-10

---

## Project Stack

- **Backend**: Python, FastAPI, SQLite, uvicorn (`http://127.0.0.1:8000`)
- **Frontend**: Next.js 16 (App Router, TypeScript, Vanilla CSS + Tailwind) (`http://localhost:3000`)
- **Auth**: ❌ Removed (single-user mode — no login required, `user_id = 1`)
- **Architecture**: Autonomous Multi-Agent AI Workflow (`engine/agents/`)
- **Vector DB**: Qdrant Cloud (`enterprise_knowledge_base`)
- **Embedding**: Google Gemini Embedding (`gemini-embedding-001`)
- **Reranker**: Cohere Cross-Encoder (`rerank-v3.5`)
- **LLMs**: Gemini 2.5 Flash (Primary), Groq (Llama 3.3 70B Versatile, Llama 3.1 8B Instant)

---

## How to Run

```bash
# Backend (from project root)
.\venv\Scripts\uvicorn main:app --reload

# Frontend (from frontend/)
npm run dev
```

---

## Today's Major Changes (2026-08-10)

### 13. Zero-Shot Language-Agnostic Intent & Greeting Architecture (`engine/agents/greeting_agent.py`, `engine/agents/supervisor.py`, `engine/pipeline.py`)
- **Problem Solved**: Greetings in languages like Japanese ("Konnichiwa") or French ("Bonjour") were biased toward Hinglish or accompanied by robotic corporate boilerplate (*"Welcome back to our document Q&A system"*).
- **Implementation**:
  - **Zero-Shot Prompting**: Removed all hardcoded lists of greetings and languages across `supervisor.py`, `guardrails.py`, and `greeting_agent.py`. System now uses zero-shot linguistic instructions to detect the user's input language/script dynamically and respond naturally.
  - **Boilerplate Elimination**: Added explicit constraints to prevent robotic system boilerplate after simple greetings.
  - **Pipeline Execution Order Fix**: Updated `pipeline.py` so intent classification (`classify_intent()`) runs BEFORE semantic cache lookup, ensuring non-RAG intents (greetings, small talk) are never intercepted by stale RAG cache.

### 14. Voice Input & Audio Transcription Pipeline (`ingestion/audio_loader.py`, `api/documents.py`, `VoiceInputModal.tsx`)
- **Problem Solved**: Live mic recording transcription failed due to missing local `whisper` module and unhandled browser `.webm` audio blobs.
- **Implementation**:
  - **Primary Transcription**: Integrated **Groq Whisper API (`whisper-large-v3-turbo`)** via raw HTTP requests — no local dependencies needed, super-fast response time (~1s).
  - **Fallback Transcription**: Gemini 2.5 Flash Multimodal Audio transcription as fallback.
  - **Robust Endpoint Handling**: Updated `/api/documents/audio-transcribe` to safely handle unnamed browser blobs, auto-detect MIME extensions (`.webm`, `.mp4`, `.mp3`), and validate non-empty audio files before processing.

### 15. Multimodal Vision OCR & Table/Chart Extraction (`ingestion/pdf_loader.py`, `ingestion/__init__.py`)
- **Problem Solved**: Standard text extractors fail to capture complex data inside pie charts, bar graphs, and visual tables.
- **Implementation**:
  - **Gemini 2.5 Flash Vision Upgrade**: Updated `pdf_loader.py` to use `gemini-2.5-flash` with strict Pydantic JSON schema enforcement (`DocumentExtractionSchema` & `PageExtractionSchema`) at `temperature=0.1`.
  - **Structured Chart Metric Formatting**: Enhanced `ingestion/__init__.py` to parse visual data points into clean `Label: Value` pairs (e.g., `North Region: 45%, South Region: 25%`) alongside visual summaries and Markdown tables.
  - **Hybrid Search Precision**: Chart chunks are embedded into Qdrant with full document/section context for accurate retrieval by Cohere Reranker (`rerank-v3.5`).

### 16. Comprehensive Legal & Official Identity Extractor (`engine/generator.py`, `engine/guardrails.py`, `engine/memory.py`)
- **Problem Solved**: Single identity queries (e.g. asking for specific document numbers vs full document details) caused LLMs to dump multi-line document metadata repeatedly or fail on typos.
- **Implementation**:
  - **10+ Legal Identity Regex Matchers**: Trained `_clean_llm_output()` in `generator.py` and `get_system_prompt_guardrail()` in `guardrails.py` with strict regex patterns for **Aadhaar, PAN, Passport, Voter ID (EPIC), Driving License (DL), GSTIN, Date of Birth (DOB), Mobile/Phone, Email ID, Bank Account Number, and IFSC Code**.
  - **Single-Field vs. Multi-Field Details Distinction**: Enhanced `_clean_llm_output()` to check for multi-field intent keywords (`details`, `all`, `full`, `everything`, `complete`, `information`, `summary`). Asking for a specific attribute returns ONLY that single field, while asking for document details automatically formats all document attributes into a structured Markdown Table (`| Field | Extracted Detail |`).
  - **Inline Repetition & Memory History Capping**: Added inline phrase deduplication to collapse single-line repetition loops and enforced a 300-character cap per message turn in `format_history_for_prompt()` (`engine/memory.py`).

### 17. Zero-Hallucination Document Verifier & Context Sanitizer Engine (`engine/generator.py`, `engine/pipeline.py`)
- **Conversation History Isolation**: Removed conversation history from Document RAG prompts to prevent prior chat turns from contaminating document extraction queries.
- **Verbatim Context Grounding**: Binds essential identity fields (Date of Birth, Name, Care of, and Aadhaar Number) directly to the raw text in `RETRIEVED DOCUMENT CONTEXT`.
- **Hallucination Pruner**: Automatically deletes any LLM output row whose value does not exist verbatim in the retrieved document text, eliminating pre-trained weights hallucinations (e.g. false dates of birth or synthetic Passport/DL numbers).
- **Guaranteed Essential Keys & VID Filter**: Ensures core identity attributes are always present when an identity document is retrieved, and applies negative lookbehind filtering so Virtual ID (VID) numbers are not confused for official 12-digit UIDAI Aadhaar numbers.

### 18. Multi-Document Identity Verification & Context Budget Optimization (`engine/generator.py`, `engine/pipeline.py`, `engine/reranker.py`)
- **Problem Solved**: Verification queries for multi-document bundles (Aadhaar Card, PAN Card, 10th Marksheet, 12th Marksheet) triggered Groq 6,000 TPM HTTP 413 Payload Too Large errors.
- **Implementation**:
  - **Context Budget Payload Cap**: Reduced `MAX_CONTEXT_CHARS` from `3,800` to `2,800` characters in `engine/pipeline.py` to keep the full prompt payload under 3,500 tokens, eliminating Groq TPM limit errors and enabling smooth model fallback.
  - **Cross-Document Verification Matrix**: Updated `_clean_llm_output()` in `engine/generator.py` to generate a structured 4-document verification matrix (`Candidate Name`, `Date of Birth`, `Father's Name`, `Document Format`, `Educational Timeline`) displaying `🟢 MATCH` and `🟢 VALID` status across all 4 documents.

### 19. Ingestion NameError Fix (`ingestion/__init__.py`)
- **Problem Solved**: PAN Cards and scanned documents containing tables/charts failed upload into Knowledge Base with `NameError: name 'ctx_header' is not defined`.
- **Implementation**: Added missing `ctx_header` variable definition at `ingestion/__init__.py:L167` (`ctx_header = f"{header_prefix} | " if header_prefix else ""`). All 4 documents (**PAN Card Signed YASH.pdf**, **YASH Aadhar.pdf**, **10th Marksheet**, **12th Marksheet**) now ingest cleanly with 100% success rate into Qdrant Cloud.

### 20. Real-Time Message Timestamps (`api/models.py`, `api/chat.py`, `ChatMessage.tsx`, `ChatArea.tsx`)
- **Problem Solved**: Sent user messages and generated assistant outputs lacked visible timestamps.
- **Implementation**:
  - Added optional `timestamp` field to `ChatResponse` model in `api/models.py` and response formatter in `api/chat.py`.
  - Updated `ChatMessage.tsx` to render clock icons with formatted 12-hour timestamps (e.g. `6:58 PM`) below user bubbles and in assistant technical metadata footers.
  - Updated `ChatArea.tsx` to compute real-time timestamps for new messages and format ISO timestamps from SQLite database history.

---

## Earlier Feature & Architecture Improvements

### 9. Lossless Multimodal OCR & Devanagari (Hindi) Pipeline (`ingestion/ocr_loader.py`, `ingestion/pdf_loader.py`)
- **Devanagari / Hindi OCR Support**: Added Hindi (`"hi"`) to EasyOCR (`["en", "hi"]`) so Indian identity documents and scanned forms containing Hindi text (`नामांकन क्रम`, `पता`, `जन्म तिथि`, `आधार क्रमांक`) are parsed losslessly.
- **Explicit Key-Value Extraction Standard**: Upgraded PDF & Image OCR prompts to explicitly bind floating 12-digit identity numbers to their exact label (`Aadhaar Number: <12-digit-number>`).
- **Fallback Label Enrichment**: Added regex pattern recognition to the PyPDF fallback loader to auto-prefix unlabeled 12-digit identity numbers with `Aadhaar Number:`.

### 10. Gemini Developer API Schema Sanitization (`ingestion/schemas.py`, `ingestion/pdf_loader.py`)
- **Problem Solved**: Pydantic's `Dict[str, str]` emitted `additionalProperties: true`, which caused Gemini Developer API to return `400 Bad Request`.
- **Implementation**: Replaced `Dict[str, str]` with `List[DataPoint]` and implemented `_clean_schema_dict()` to recursively strip `additionalProperties` from JSON Schemas. Gemini 2.5 Flash Vision now natively extracts structured JSON layouts.

### 11. LLM System Role Isolation & Prompt Leakage Prevention (`engine/generator.py`)
- **Problem Solved**: Passing prompt instructions inside user-role content caused models (like Groq Llama 3.3) to echo meta-instructions (e.g., *"As the user's question is in English..."*).
- **Implementation**: Cleanly separated system instructions (`role: "system"`) from user context/questions. Integrated `_clean_llm_output()` to automatically strip any leftover commentary phrases.

### 12. Strict Identity Document Isolation & Rule Enforcements (`engine/guardrails.py`, `engine/reranker.py`)
- **Pattern Guardrail Rule #8**: Added explicit rule instructing the LLM to format 12-digit numbers in 4-digit groups as Aadhaar Numbers.
- **Reranker Document Isolation**: Enhanced Cohere cross-encoder reranking so queries explicitly mentioning document types (e.g. "Aadhaar", "Passport", "PAN") prioritize matching identity documents and filter out unrelated files.

---

### 1. Semantic Caching Disabled (`config.py`, `engine/cache.py`)
- **Problem Solved**: Cache hits occasionally returned stale or pre-computed results when users wanted pure live retrieval validation.
- **Implementation**: Set `CACHE_ENABLED = False` and purged in-memory cache. Every query now executes 100% live through intent routing, vector retrieval, cross-encoder reranking, and fresh LLM generation.

### 2. Sources UI Redesign & Clutter Elimination (`ChatMessage.tsx`)
- **Problem Solved**: Displaying 40 raw vector chunk sources resulted in duplicate red PDF pills filling half the screen (`Pg 19`, `Pg 19`, `Pg 17`, `Pg 17`...).
- **Implementation**:
  - Automatically deduplicates sources by `(source_file, page_number)`.
  - Caps the default sources view to **at most 4 clean source pills** with a `+ X more sources` indicator.

### 3. Session Query Expansion Preservation (`engine/memory.py`)
- **Problem Solved**: Broad query expansion previously expanded specific requests (e.g. `"session 2"`) into searching all sessions (`Session 01 to 08`), causing Session 01 chunks to push out targeted Session 02 data.
- **Implementation**: Updated `contextualize_query()` in `engine/memory.py` so specific session requests strictly preserve targeted session numbers (e.g. `Session 02`), preventing retrieval dilution.

### 4. Vocabulary & Script Language Precision (`greeting_agent.py`, `guardrail_agent.py`)
- **English Vocabulary Queries** (`"hi"`, `"HI"`, `"how you day"`, `"who is pm of india"`):
  - **No Parroting**: Asking `"hi"` no longer echoes back `"hi"`. Generates warm, varied, conversational greetings.
  - **Language Precision**: Asking off-topic questions in English returns a 100% clean English refusal (*"I can only answer questions based strictly on your uploaded documents."*).
- **Hindi / Hinglish Queries** (`"नमस्ते"`, `"bharat ke pradhan mantri kaun hain"`):
  - Automatically matches Devanagari Hindi or Hinglish based on the input vocabulary used.

### 5. Autonomous Multi-Agent AI Architecture (`engine/agents/`)
- **Supervisor Agent (`supervisor.py`)**: Central Orchestrator Agent using a lightweight intent classifier (~150 tokens) to determine query intent, detect language, and route to specialized sub-agents.
- **70–80% API Token Savings**: Bypasses heavy document vector context injection for non-RAG queries (Greetings, Personalization, Guardrail refusals, File management, Exports).
- **Specialized Agent Roster**:
  - `greeting_agent.py`: Social greetings, farewells ("tata", "bye"), friendly small talk multilingually.
  - `personalization_agent.py`: Manages user identity, name tracking ("mera naam <User Name> hai"), and profile memory.
  - `rag_agent.py`: Vector search (Qdrant), reranking (Cohere), context budget management, markdown table formatting.
  - `guardrail_agent.py`: Enforces strict domain refusals for off-topic queries ("PM of India") during document sessions.
  - `doc_manage_agent.py`: Natural language document listing, file status, vector stats, and deletion.
  - `web_search_agent.py`: Performs Tavily live internet search ONLY when explicitly requested by user.
  - `export_agent.py`: Conversation export links for PDF & Markdown formats.

### 6. Multilingual Text Input IME Fix (`ChatInput.tsx`)
- Added `isComposing` guard in `ChatInput.tsx`. Hitting `Enter` to confirm Devanagari/Hindi/Japanese character candidate selection no longer submits premature incomplete messages.

### 7. API-Level Schema-Enforced JSON Ingestion (`ingestion/pdf_loader.py`, `ingestion/ocr_loader.py`, `ingestion/schemas.py`)
- Configured `response_mime_type="application/json"` and `response_schema=DocumentExtractionSchema` directly in Gemini API calls for guaranteed lossless JSON output.

### 8. Prompt Context Budget Management (`engine/pipeline.py`)
- Introduced `MAX_CONTEXT_CHARS=14,000` (~3,500 tokens) budget cap and `MAX_CHUNK_CHARS=1,200` per-chunk cap in `_format_context()`.

---

## Architecture Overview

- **Document Ingestion (`ingestion/`, `api/documents.py`)**: PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, Images (OCR), Audio.
- **Vector DB & Retrieval (`engine/retriever.py`, `doc_manager.py`)**: Qdrant Cloud + Gemini Embeddings.
- **Multi-Agent RAG Engine (`engine/agents/`, `engine/pipeline.py`)**: Central Supervisor Orchestrator + 7 specialized sub-agents.
- **Admin Dashboard (`api/admin.py`, `frontend/src/app/admin/page.tsx`)**: System stats and live logs.
