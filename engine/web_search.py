# engine/web_search.py
"""
Tavily web search fallback — used when internal documents don't have relevant answers.
"""
import logging
from engine.clients import tavily_client

logger = logging.getLogger(__name__)


def search_live_internet(query: str, max_results: int = 3) -> list[dict]:
    """
    Searches the live internet using Tavily for real-time web results.
    
    Returns documents in the same format as internal retrieval for seamless integration.
    """
    try:
        search_results = tavily_client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
        )

        results = []
        for item in search_results.get("results", []):
            results.append({
                "text": f"Title: {item.get('title', 'N/A')}\nContent: {item.get('content', '')}",
                "source_file": item.get("url", "Unknown URL"),
                "page_number": "Web",
                "type": "live_web",
                "score": item.get("score", 0.99),
            })

        logger.info(f"Tavily web search returned {len(results)} results for: '{query[:60]}...'")
        return results

    except Exception as e:
        logger.error(f"Tavily web search failed: {e}")
        return []
