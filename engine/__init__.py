# engine/__init__.py
"""
Modular RAG Engine — replaces the old monolithic rag_engine.py.
Each component handles one responsibility:
  - clients.py:       Shared API client instances
  - retriever.py:     Embedding + Qdrant vector search
  - reranker.py:      Cohere cross-encoder reranking
  - generator.py:     Multi-provider LLM generation with retry + streaming
  - memory.py:        Conversation context builder
  - guardrails.py:    Topic enforcement + safety filters
  - cache.py:         Semantic similarity caching
  - web_search.py:    Tavily web search fallback
  - token_counter.py: Input/output token tracking
  - pipeline.py:      Orchestrates the full RAG flow
"""
