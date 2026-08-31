# Intellect RAG Assistant 🧠

An enterprise-grade Retrieval-Augmented Generation (RAG) system with a FastAPI backend and a Next.js (Tailwind) frontend, styled like a modern AI chatbot.

## Features ✨

### AI & Models
- **Multi-Provider LLMs**: Supports Google Gemini and Groq (Llama 3.3, Qwen 32B, DeepSeek R1).
- **Auto-Fallback Chain**: If one API fails or hits a rate limit, the system automatically falls back to the next model transparently.
- **Cross-Encoder Reranking**: Uses Cohere for highly accurate document reranking.
- **Live Web Search**: Integrates Tavily for real-time fallback when internal documents lack answers.
- **Semantic Caching**: Saves tokens by caching similar queries using cosine similarity.
- **Smart Conversation Memory**: Seamlessly preserves conversation context, even when switching between different models (Gemini -> Llama) mid-conversation.

### Document Ingestion
- **Formats**: PDF, DOCX, XLSX, PPTX, TXT, CSV, MD.
- **OCR Support**: Extracts text from scanned PDFs and images using EasyOCR.
- **Audio Transcription**: Ingests audio files (`.mp3`, `.wav`) via Whisper.
- **Smart Chunking**: Sentence-aware document splitting instead of arbitrary character chunking.
- **Folder Watcher**: Automatically ingests files dropped into the `watch_folder/`.

### Architecture & Security
- **Decoupled**: FastAPI backend + Next.js React frontend.
- **Auth & Rate Limiting**: JWT-based authentication with per-user daily rate limits.
- **Guardrails**: Built-in prompt injection/jailbreak detection and relevance thresholds.
- **Streaming**: Fully supports token-by-token WebSocket streaming.
- **Export**: Download conversations as Markdown or PDF files.

## Setup 🚀

### 1. Backend (FastAPI)
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Configure Environment
copy .env.example .env
# Edit .env with your API keys (Google, Groq, Qdrant, etc.)

# Run Server
uvicorn main:app --reload --port 8000
```

### 2. Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Navigate to `http://localhost:3000` to access the chat interface!

## Folder Structure 📂
- `/api` - FastAPI route handlers
- `/auth` - JWT, rate limiting, and middleware
- `/engine` - Core RAG pipeline (retriever, reranker, generator, cache, guardrails)
- `/ingestion` - Document loaders, chunker, and folder watcher
- `/frontend` - Next.js React App Router UI