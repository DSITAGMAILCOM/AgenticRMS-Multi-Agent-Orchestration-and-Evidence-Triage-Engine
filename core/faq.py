# core/faq.py
"""
FAQ Deflection Engine
Provides high-performance, zero-cost responses for recurring student inquiries.
Bypasses LLM token inference, SQL execution, and vector RAG operations.
"""
import re
from typing import Optional, List, Dict, Any

def match_faq(query: str, faq_catalog: List[Dict[str, Any]]) -> Optional[str]:
    """
    Matches a sanitized query against an agent's FAQ pattern catalog.
    
    Supports:
    - Substring phrases: e.g., "payment mode"
    - Keyword conjunction tuples: e.g., ("pay", "fee") -> all terms must appear in query
    - Regular expressions: e.g., r"\\bpay\\b.*\\bfees?\\b"
    
    Args:
        query: Preprocessed, lowercase query string with punctuation removed.
        faq_catalog: List of dictionaries with 'patterns' and 'answer'.
        
    Returns:
        The authoritative Markdown answer if a match is found, else None.
    """
    q = query.lower()
    for faq in faq_catalog:
        for pat in faq["patterns"]:
            matched = False
            if isinstance(pat, (tuple, list)):
                if all(term in q for term in pat):
                    matched = True
            elif isinstance(pat, str):
                if pat in q:
                    matched = True
                else:
                    try:
                        if re.search(pat, q):
                            matched = True
                    except re.error:
                        pass
            if matched:
                return f"⚡ **[Instant FAQ Deflection — Zero Model Cost]**\n\n{faq['answer']}"
    return None
