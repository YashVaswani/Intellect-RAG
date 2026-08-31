# engine/reranker.py
"""
Cross-encoder reranking using Cohere to filter the most relevant chunks.
"""
import logging
from engine.clients import cohere_client
import config

logger = logging.getLogger(__name__)


def rerank_documents(
    query: str,
    documents: list[dict],
    top_n: int = None,
) -> tuple[list[dict], float]:
    """
    Reranks candidate document chunks using Cohere's cross-encoder.
    
    Returns:
        tuple of (reranked_docs, max_relevance_score)
        Falls back gracefully if Cohere is unavailable.
    """
    top_n = top_n or config.RERANK_TOP_N

    if not documents:
        return [], 0.0

    try:
        rerank_response = cohere_client.rerank(
            model=config.RERANK_MODEL,
            query=query,
            documents=[d["text"] for d in documents],
            top_n=top_n,
        )

        reranked_docs = []
        max_score = 0.0

        for result in rerank_response.results:
            doc = documents[result.index].copy()  # Don't mutate original
            doc["score"] = result.relevance_score
            reranked_docs.append(doc)
            max_score = max(max_score, result.relevance_score)

        # Smart Cutoff & File Type Isolation Filter:
        # Accumulate all target keywords present in multi-document queries
        query_lower = query.lower()
        target_kws = []
        if any(kw in query_lower for kw in ["aadhar", "aadhaar", "adhar", "uidai"]):
            target_kws.extend(["aadhar", "aadhaar", "adhar", "uidai"])
        if "resume" in query_lower or "cv" in query_lower:
            target_kws.extend(["resume", "cv"])
        if "pan" in query_lower and "japan" not in query_lower and "company" not in query_lower:
            target_kws.extend(["pan"])
        if "passport" in query_lower:
            target_kws.extend(["passport"])
        if any(kw in query_lower for kw in ["10th", "12th", "marksheet", "scorecard", "board", "grade"]):
            target_kws.extend(["10th", "12th", "marksheet", "scorecard", "roll", "0808cs"])

        # Deduplicate reranked documents by text content
        seen_texts = set()
        unique_reranked = []
        for d in reranked_docs:
            t_norm = d.get("text", "").strip()
            if t_norm and t_norm not in seen_texts:
                seen_texts.add(t_norm)
                unique_reranked.append(d)
        reranked_docs = unique_reranked

        cutoff = max(0.12, max_score * 0.75) if max_score > 0 else 0.0
        top_source_file = reranked_docs[0]["source_file"] if reranked_docs else "N/A"
        
        filename_matches = []
        content_matches = []
        other_matches = []

        for d in reranked_docs:
            source_lower = (d.get("source_file") or d.get("filename") or d.get("source") or d.get("file_name") or "").lower()
            text_lower = d.get("text", "").lower()

            if target_kws:
                if any(kw in source_lower for kw in target_kws):
                    filename_matches.append(d)
                elif any(kw in text_lower for kw in target_kws):
                    content_matches.append(d)
                elif d["score"] >= cutoff:
                    other_matches.append(d)
            elif d["score"] >= cutoff:
                other_matches.append(d)

        # For multi-document requests, round-robin filename_matches by distinct source file
        if len(set(d.get("source_file") for d in filename_matches)) > 1:
            file_groups = {}
            for d in filename_matches:
                sf = d.get("source_file")
                file_groups.setdefault(sf, []).append(d)
            interleaved = []
            max_len = max(len(v) for v in file_groups.values())
            for i in range(max_len):
                for sf in file_groups:
                    if i < len(file_groups[sf]):
                        interleaved.append(file_groups[sf][i])
            filename_matches = interleaved

        # File name matches take highest priority, followed by content matches and general cutoff matches
        filtered_docs = filename_matches + content_matches + other_matches

        # Cap max context chunks to 8 unique chunks
        filtered_docs = filtered_docs[:8]

        # Multi-Page Session Continuation Aggregator:
        # If a retrieved chunk belongs to a multi-page session, pull along the continuing page chunk (e.g. Page 2) from candidate docs.
        import re
        extended_filtered = []
        seen_pages = set()

        for d in filtered_docs:
            extended_filtered.append(d)
            src_file = d.get("source_file")
            page_num = d.get("page_number")
            text_content = d.get("text", "")

            if src_file and isinstance(page_num, int):
                seen_pages.add((src_file, page_num))
                session_match = re.search(r'Session\s*[:\-]\s*(0?\d+)', text_content, re.IGNORECASE)
                if session_match:
                    sess_num = session_match.group(1).lstrip('0') or '0'
                    next_page_num = page_num + 1
                    for cand in documents:
                        if (
                            cand.get("source_file") == src_file
                            and cand.get("page_number") == next_page_num
                            and (src_file, next_page_num) not in seen_pages
                        ):
                            cand_text = cand.get("text", "")
                            if (
                                f"Session: 0{sess_num}" in cand_text
                                or f"Session: {sess_num}" in cand_text
                                or "SESSION DETAILS" in cand_text
                            ):
                                extended_filtered.append(cand.copy())
                                seen_pages.add((src_file, next_page_num))
                                break

        filtered_docs = extended_filtered[:8]

        if not filtered_docs and reranked_docs:
            filtered_docs = [reranked_docs[0]]

        logger.info(
            f"Reranked {len(documents)} docs → filtered {len(filtered_docs)}/{len(reranked_docs)} relevant docs, "
            f"max_score={max_score:.3f}, cutoff={cutoff:.3f}, top_file='{top_source_file}'"
        )
        return filtered_docs, max_score

    except Exception as e:
        logger.error(f"Cohere reranking failed: {e}")
        # Graceful fallback: filter by top source file and return top 3 vector docs max
        if not documents:
            return [], 0.0
        top_file = documents[0].get("source_file")
        fallback_docs = [d.copy() for d in documents if d.get("source_file") == top_file][:3]
        if not fallback_docs:
            fallback_docs = [d.copy() for d in documents[:3]]
        for d in fallback_docs:
            d["score"] = 0.5
        return fallback_docs, 0.5
