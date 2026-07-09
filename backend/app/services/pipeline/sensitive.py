def check_sensitive_words(text: str, words: list[str]) -> list[str]:
    """
    Check text (subject + body combined) against the active sensitive word list.
    Returns list of matched words (empty = no match).
    Priority: highest in pipeline — called BEFORE any LLM classification.
    """
    if not words or not text:
        return []
    text_lower = text.lower()
    matched = [w for w in words if w.lower() in text_lower]
    return matched
