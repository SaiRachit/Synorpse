"""Helpers for routing questions about the assistant instead of executing them."""
import re


_AGENT_META_PATTERNS = [
    r'^(?:if|when)\s+i\s+(?:ask|tell|want)\s+you\s+to\b',
    r'\bhow\s+(?:would|do)\s+you\s+(?:decide|choose|use|plan|order|work|think)\b',
    r'\bwhat\s+(?:tools|capabilities|functions)\s+(?:do|can)\s+you\b',
    r'\bwhat\s+can\s+you\s+do\b',
    r'\bexplain\s+(?:how|your)\b.*\b(?:tools|capabilities|workflow|process|order|planning|reasoning)\b',
    r'\bi\s+want\s+to\s+understand\s+what\s+capabilities\s+you\s+have\b',
    r'\b(?:tool|capability|workflow|planning|reasoning)\s+(?:selection|order|process|logic)\b',
    r'\bwhat\s+(?:is|was)\s+your\s+(?:plan|workflow|process|reasoning)\b',
]


def is_agent_meta_query(query: str) -> bool:
    """Return True when the user is asking how the assistant would act."""
    query_lower = (query or "").lower().strip()
    return any(re.search(pattern, query_lower) for pattern in _AGENT_META_PATTERNS)
