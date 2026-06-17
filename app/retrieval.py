from datetime import datetime


def extract_text(article: dict) -> str:
    parts = []
    for card in article.get("cards", []):
        for element in card.get("story-elements", []):
            if element.get("type") == "text":
                text = element.get("text", "").strip()
                if text:
                    parts.append(text)

    # Print articles (smartflow) carry full text in _body
    if not parts:
        body = (article.get("_body") or "").strip()
        if body:
            parts.append(body)

    # Search API returns summary-only stories without cards — fall back to subheadline
    if not parts:
        sub = (article.get("subheadline") or "").strip()
        if sub:
            parts.append(sub)

    return "\n\n".join(parts)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def format_date(timestamp_ms: int | None) -> str:
    if not timestamp_ms:
        return "Unknown date"
    try:
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        return dt.strftime("%B %d, %Y")
    except (OSError, OverflowError, ValueError):
        return "Unknown date"
