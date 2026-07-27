import asyncio
import calendar
import re
from datetime import date, timedelta
from schemas import (
    QueryAnalysis, ContextAssessment, SynthesizedAnswer,
    RetrievedChunk, NewsSource, TraceStep, ChatResponse,
)
from app import quintype, smartflow
from app.retrieval import extract_text, truncate_to_tokens, format_date
from app.claude_client import call_answer
from app.config import QUINTYPE_API_BASE
from app.agents.state import GraphState

# ---------------------------------------------------------------------------
# Rule-based query planning (no LLM call). Esakal's search is a simple
# keyword match, so intent/date/search-query extraction doesn't need a
# model call — this replaces what used to be a dedicated LLM planning step.
# ---------------------------------------------------------------------------

OOS_KEYWORDS = [
    "recipe", "biryani", "बिर्याणी", "रेसिपी", "कसे बनवावे", "कसा बनवावा", "स्वयंपाक कसा",
    "write code", "python code", "program in", "function in python", "कोड लिही", "प्रोग्राम लिही",
    "2+2", "3+3", "what is 2", "गणिताचे कोडे", "गणित सोडव",
    "कुंडली", "राशीफळ", "horoscope", "zodiac", "जन्मपत्रिका",
    "girlfriend", "boyfriend", "relationship advice", "breakup", "प्रियकर", "प्रेयसी",
    "माझी गर्लफ्रेंड", "माझा बॉयफ्रेंड",
]

BARE_WORDS = {"news", "politics", "राजकारण", "बातम्या", "update", "updates"}

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "what", "happened", "in", "on", "of",
    "about", "today", "recent", "latest", "news", "tell", "me", "please", "current",
    "situation", "regarding", "and", "top", "stories", "story", "headlines",
    "आज", "काय", "घडले", "घडल्या", "बद्दल", "सांगा", "आहे", "मध्ये", "ची", "चा", "ला",
    "बातम्या", "विषयी", "सध्याची", "सद्यस्थिती", "चे", "सांगणे", "मधील",
    "आजच्या", "ताज्या", "ताजी", "ताजा", "ताजे", "स्टोरीज", "हेडलाईन्स",
    # filler adjectives/verbs that add no search value
    "महत्त्वाच्या", "महत्वाच्या", "महत्त्वाचे", "महत्वाचे", "महत्त्वाची", "महत्वाची",
    "महत्त्वाचा", "महत्वाचा", "ठळक", "मुख्य", "प्रमुख", "सर्वात", "खूप", "काही",
    "आहेत", "होते", "होती", "होता", "होत्या", "झाले", "झाली", "झाला", "झाल्या",
    "सांगतो", "सांगते", "द्या", "करा", "घ्या", "जाणून", "घेऊया", "पाहूया",
    # "देश-विदेश घडामोडी" (national/international developments) is a roundup
    # phrase, not a searchable topic — literal keyword search on these words
    # matches disparate unrelated articles. Route it to the generic
    # top-stories fallback instead (same treatment as "आजच्या ताज्या बातम्या").
    "देश", "विदेश", "घडामोडी",
}

MULTI_WORD_TRANSLITERATE = {
    "share market": "शेअर बाजार",
    "stock market": "शेअर बाजार",
    "moon mission": "चंद्र मोहीम",
}

SINGLE_WORD_TRANSLITERATE = {
    "modi": "मोदी", "pune": "पुणे", "mumbai": "मुंबई", "maharashtra": "महाराष्ट्र",
    "delhi": "दिल्ली", "bjp": "भाजप", "congress": "काँग्रेस", "fadnavis": "फडणवीस",
    "shinde": "शिंदे", "pawar": "पवार", "nashik": "नाशिक", "nagpur": "नागपूर",
    "crime": "गुन्हा", "politics": "राजकारण", "health": "आरोग्य", "covid": "कोविड",
    "sports": "क्रीडा", "cricket": "क्रिकेट", "election": "निवडणूक", "budget": "अर्थसंकल्प",
    "weather": "हवामान", "monsoon": "पाऊस", "education": "शिक्षण", "farmer": "शेतकरी",
    "water": "पाणी", "finance": "अर्थ", "gst": "जीएसटी", "tax": "कर", "inflation": "महागाई",
    "nasa": "नासा", "environment": "पर्यावरण",
}

# Generic category words rarely appear literally in headlines/body text
# (search is literal keyword matching, not semantic) — real articles use
# specific terms instead. Expanding to a multi-word query also triggers
# quintype.search's existing per-word fallback/merge logic for better recall.
CATEGORY_EXPANSION = {
    "क्रीडा": "क्रीडा क्रिकेट cricket football IPL",
    "राजकारण": "राजकारण निवडणूक सरकार election",
    "आरोग्य": "आरोग्य रुग्णालय उपचार hospital",
    "शिक्षण": "शिक्षण शाळा विद्यार्थी",
    "हवामान": "हवामान पाऊस तापमान monsoon",
}

# Maps Marathi category words to Quintype section slugs for direct section fetch.
CATEGORY_TO_SECTION: dict[str, str] = {
    "क्रीडा": "krida",
    "राजकारण": "politics",
    "महाराष्ट्र": "maharashtra",
    "आरोग्य": "health",
    "गुन्हे": "crime",
    "शिक्षण": "education",
    "व्यवसाय": "business",
}

# Some topics are covered under an English name even in Marathi headlines
# (e.g. "FIFA World Cup 2026" rather than "फिफा विश्वचषक"). Matched by
# substring so inflected forms like "विश्वचषकात" still trigger the append.
# Marathi terms whose English equivalent often appears in Marathi headlines.
# Matched by substring so inflected forms ("विश्वचषकात") still trigger.
WORD_SYNONYMS = {
    "फिफा": "FIFA World Cup",
    "विश्वचषक": "World Cup",
    "ऑलिंपिक": "Olympics",
    "क्रिकेट": "cricket IPL",
    "फुटबॉल": "football",
    "टेनिस": "tennis",
    "बॅडमिंटन": "badminton",
    "कुस्ती": "wrestling",
    "बॉक्सिंग": "boxing",
    "नासा": "NASA",
    "इस्रो": "ISRO",
    "बजेट": "budget",
    "जीएसटी": "GST",
    "सेन्सेक्स": "Sensex",
    "शेअर": "stock market Sensex Nifty",
}

# English terms whose Marathi equivalent appears in Marathi headlines.
# Used to build a parallel English search query when the user types in Marathi.
_EN_FALLBACK: dict[str, str] = {
    "cricket": "क्रिकेट IPL",
    "football": "फुटबॉल",
    "election": "निवडणूक",
    "budget": "अर्थसंकल्प बजेट",
    "modi": "मोदी",
    "bjp": "भाजप",
    "congress": "काँग्रेस",
    "pune": "पुणे",
    "mumbai": "मुंबई",
    "maharashtra": "महाराष्ट्र",
    "rain": "पाऊस",
    "flood": "पूर",
    "farmer": "शेतकरी",
}

MONTHS_MR = {
    "जानेवारी": 1, "फेब्रुवारी": 2, "मार्च": 3, "एप्रिल": 4, "मे": 5, "जून": 6,
    "जुलै": 7, "ऑगस्ट": 8, "सप्टेंबर": 9, "ऑक्टोबर": 10, "नोव्हेंबर": 11, "डिसेंबर": 12,
}
MONTHS_EN = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "december": 12, "dec": 12,
}


_ENTERTAINMENT_KEYWORDS = {
    "अभिनेत्री", "अभिनेता", "बॉलिवूड", "घटस्फोट", "actress", "actor",
    "bollywood", "divorce", "celebrity", "सेलिब्रिटी", "लव्ह स्टोरी",
    "फिल्म स्टार", "tv star", "reality show",
}


def _is_out_of_scope(lower: str) -> bool:
    return any(kw in lower for kw in OOS_KEYWORDS)


def _build_en_fallback_query(marathi_query: str) -> str:
    """Return an English-keyword search string for a Marathi query, or '' if none apply."""
    lower = marathi_query.lower()
    parts: list[str] = []
    for mr_word, en_terms in _EN_FALLBACK.items():
        if mr_word in lower:
            parts.append(en_terms)
    # Also add any English words already present in the query (e.g. "IPL")
    for tok in re.findall(r"[a-zA-Z]+", marathi_query):
        if len(tok) > 2 and tok.lower() not in parts:
            parts.append(tok)
    return " ".join(parts[:4])


_CASE_SUFFIXES = ["ातील", "ाबद्दल", "ाबाबत", "ात", "ाला", "ाचा", "ाची", "ाचे", "ाने"]


def _stem_variant(tok: str) -> str | None:
    """Strip a trailing Marathi case suffix (locative/dative/genitive) so an
    inflected form like "बाजारात" (in the market) also matches headlines that
    use the bare form "बाजार" — search is literal substring matching, not
    morphology-aware, so these otherwise never cross-match."""
    for suf in _CASE_SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            return tok[: -len(suf)]
    return None


def _build_search_query(question: str) -> str:
    lower = question.strip().lower()
    for phrase, marathi in MULTI_WORD_TRANSLITERATE.items():
        if phrase in lower:
            lower = lower.replace(phrase, marathi)
    lower = _strip_date_tokens(lower)
    tokens = re.findall(r"[\wऀ-ॿ]+", lower)
    kept: list[str] = []
    for tok in tokens:
        if tok in STOPWORDS:
            continue
        mapped = SINGLE_WORD_TRANSLITERATE.get(tok, tok)
        if mapped not in kept:
            kept.append(mapped)
        stem = _stem_variant(mapped)
        if stem and stem not in kept:
            kept.append(stem)
    if not kept:
        # Nothing substantive left after stripping dates/months/stopwords (e.g.
        # "एप्रिलमधील बातम्या" or "आजच्या ताज्या बातम्या") — signal the caller to
        # use the generic top-stories fallback instead of a doomed keyword search.
        return ""
    if len(kept) == 1 and kept[0] in CATEGORY_EXPANSION:
        return CATEGORY_EXPANSION[kept[0]]
    for word, synonym in WORD_SYNONYMS.items():
        if any(word in tok for tok in kept) and synonym not in kept:
            kept.append(synonym)
    return " ".join(kept[:4])


_DATE_PHRASES_MR = [
    "गेल्या आठवड्यातील", "या आठवड्यातील", "गेल्या महिन्यातील", "या महिन्यातील",
    "गेल्या आठवड्यात", "या आठवड्यात", "गेल्या महिन्यात", "या महिन्यात",
    # Longer inflected forms must precede the bare "आज"/"काल" so they get
    # removed whole instead of leaving a fragment like "आजच्या" -> "च्या".
    "आजच्या", "आजची", "आजचे", "आजचा", "काल्च्या", "काल्ची",
    "आज", "काल",
]
_DATE_PHRASES_EN = ["last week", "this week", "last month", "this month", "today", "yesterday"]


def _strip_date_tokens(text: str) -> str:
    """Remove date-related phrases/month names so they don't pollute the search query
    (the date range is applied separately as a post-fetch filter)."""
    cleaned = text
    for phrase in _DATE_PHRASES_MR + _DATE_PHRASES_EN:
        cleaned = cleaned.replace(phrase, " ")
    cleaned = re.sub(r"(?:गेल्या|last)\s*\d+\s*(?:दिवस|days?)", " ", cleaned)
    for name in MONTHS_MR:
        cleaned = cleaned.replace(name, " ")
    for name in MONTHS_EN:
        cleaned = re.sub(r"\b" + re.escape(name) + r"\b", " ", cleaned)
    return cleaned


def _extract_date_range(lower: str) -> tuple[str | None, str | None]:
    today = date.today()

    if "आज" in lower or "today" in lower:
        return today.isoformat(), today.isoformat()
    if "काल" in lower or "yesterday" in lower:
        y = today - timedelta(days=1)
        return y.isoformat(), y.isoformat()

    m = re.search(r"(?:गेल्या|last)\s*(\d+)\s*(?:दिवस|days?)", lower)
    if m:
        n = int(m.group(1))
        start = today - timedelta(days=n)
        return start.isoformat(), today.isoformat()

    if "गेल्या आठवड्यात" in lower or "last week" in lower:
        monday_this = today - timedelta(days=today.weekday())
        monday_last = monday_this - timedelta(days=7)
        sunday_last = monday_this - timedelta(days=1)
        return monday_last.isoformat(), sunday_last.isoformat()
    if "या आठवड्यात" in lower or "this week" in lower:
        monday_this = today - timedelta(days=today.weekday())
        return monday_this.isoformat(), today.isoformat()

    if "गेल्या महिन्यात" in lower or "last month" in lower:
        first_this = today.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start.isoformat(), last_month_end.isoformat()
    if "या महिन्यात" in lower or "this month" in lower:
        first_this = today.replace(day=1)
        return first_this.isoformat(), today.isoformat()

    for name, mon in MONTHS_MR.items():
        if name in lower:
            last_day = calendar.monthrange(today.year, mon)[1]
            return date(today.year, mon, 1).isoformat(), date(today.year, mon, last_day).isoformat()
    for name, mon in MONTHS_EN.items():
        if re.search(r"\b" + re.escape(name) + r"\b", lower):
            last_day = calendar.monthrange(today.year, mon)[1]
            return date(today.year, mon, 1).isoformat(), date(today.year, mon, last_day).isoformat()

    return None, None


def _rule_based_analysis(question: str) -> QueryAnalysis:
    lower = question.strip().lower()

    if _is_out_of_scope(lower):
        return QueryAnalysis(
            intent="out_of_scope",
            search_query=None,
            entities=[],
            k=8,
            refusal_reason="not a news question",
        )

    search_query = _build_search_query(question)
    kept_tokens = search_query.split() if search_query else []
    from_date, to_date = _extract_date_range(lower)

    if lower in BARE_WORDS or not kept_tokens:
        # No substantive topic word (e.g. "आजच्या ताज्या बातम्या", bare "news") —
        # rather than asking the user to clarify, fetch top/recent stories directly.
        # search_query="" is a sentinel the retrieve step checks for.
        return QueryAnalysis(
            intent="briefing",
            search_query="",
            entities=[],
            k=8,
            from_date=from_date,
            to_date=to_date,
        )

    return QueryAnalysis(
        intent="briefing",
        search_query=search_query,
        entities=[],
        k=8,
        from_date=from_date,
        to_date=to_date,
    )

SYSTEM_PROMPT_EN = """You are Ask Esakal, a news assistant for esakal.com — Sakal Media Group's digital news platform.

Your ONLY job is to answer questions using the article excerpts provided below.
Do not use any knowledge from your training data.

Rules:
1. Answer only from the provided articles. Never use outside knowledge.
2. Keep answers concise — 3 to 5 sentences for simple questions, up to 8 for briefings/timelines.
3. Include inline citations [1], [2], etc. corresponding to the source numbers.
4. Only say "Esakal does not currently have sufficient coverage on this topic." if NO article is relevant at all — never use this when relevant articles are present.
5. Always respond in English, even if the articles are in Marathi.

ARTICLES:
{articles}"""

SYSTEM_PROMPT_MR = """You are Ask Esakal, a news assistant for esakal.com (Sakal Media Group).

CRITICAL: You MUST write your entire response in Marathi (Devanagari script). Do not write any English.

Your job is to answer the user's question using ONLY the article excerpts below.

Rules:
1. Use the provided articles. If even one article is relevant, write a summary answer from it.
2. Keep answers concise — 3-5 sentences for simple questions, up to 8 for briefings.
3. Add inline citations [1], [2], etc. after each fact.
4. Only say "ई सकाळकडे या विषयावर सध्या पुरेसे वृत्तांकन उपलब्ध नाही." if NONE of the articles relate to the question at all.
5. WRITE ONLY IN MARATHI. Every word must be in Marathi/Devanagari.
6. IMPORTANT: The source articles often use flowery, literary, or headline-style Marathi (e.g. "वावड्यांच्या वावरात", "सावटाखाली", "कूटनीतिक कसोटी"). Do NOT copy that phrasing. Always REWRITE the facts in simple, everyday spoken Marathi — the way you'd casually explain the news to a friend, using common words a school-going reader would understand. Prefer short, direct sentences over long, clause-heavy ones. Never carry over a headline's dramatic wording into your answer.

ARTICLES:
{articles}"""


def _article_url(article: dict) -> str:
    """Build a full article URL from whatever Quintype provides."""
    url = article.get("url", "")
    if url and url.startswith("http"):
        return url
    slug = article.get("slug", "")
    if slug:
        return QUINTYPE_API_BASE.rstrip("/") + "/" + slug.lstrip("/")
    if url:
        return QUINTYPE_API_BASE.rstrip("/") + "/" + url.lstrip("/")
    return QUINTYPE_API_BASE


def _format_history(history) -> str:
    if not history:
        return "No prior conversation."
    lines = []
    for msg in history:
        role = msg.role if hasattr(msg, "role") else msg.get("role", "")
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")
        lines.append(f"{role.capitalize()}: {content}")
    return "\n".join(lines)


def _renumber_citations(text: str, cited: list[int]) -> tuple[str, dict[int, int]]:
    """Remap sparse citation numbers ([1],[4],[8]) to sequential ([1],[2],[3])."""
    remap = {old: new for new, old in enumerate(cited, 1)}
    # Replace highest numbers first to avoid partial matches (e.g. [1] inside [10])
    for old in sorted(remap, reverse=True):
        text = text.replace(f"[{old}]", f"[__R{remap[old]}__]")
    for new in remap.values():
        text = text.replace(f"[__R{new}__]", f"[{new}]")
    return text, remap


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[{i}] {chunk.headline} ({chunk.published_at})\n{chunk.chunk_text}"
        )
    return "\n\n".join(parts)


def plan_query(state: GraphState) -> GraphState:
    analysis = _rule_based_analysis(state["question"])
    state["analysis"] = analysis
    state["steps"] = state.get("steps", []) + [
        TraceStep(title="Planning query", detail=f"Intent: {analysis.intent}, search: {analysis.search_query}")
    ]
    return state


def _ms_from_date_str(date_str: str | None) -> int | None:
    if not date_str:
        return None
    from datetime import datetime, timezone
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            dt = datetime.strptime(date_str.strip()[:10], fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    return None


async def retrieve(state: GraphState) -> GraphState:
    analysis = state["analysis"]
    generic = state.get("current_query") is None and analysis.search_query == ""
    state["generic_query"] = generic
    query = state.get("current_query") or analysis.search_query or state["question"]
    if generic:
        quintype_articles, print_articles = await asyncio.gather(
            quintype.top_stories(limit=analysis.k),
            asyncio.to_thread(smartflow.recent, limit=max(3, analysis.k // 3)),
        )
        # Filter celebrity/entertainment from generic top-stories — they dominate
        # the feed but aren't what users mean by "today's news".
        def _is_entertainment(a: dict) -> bool:
            text = (a.get("headline", "") + " " + a.get("subheadline", "")).lower()
            return any(kw in text for kw in _ENTERTAINMENT_KEYWORDS)
        filtered = [a for a in quintype_articles if not _is_entertainment(a)]
        if filtered:
            quintype_articles = filtered
    else:
        # Check if the query maps to a known site section for a direct section fetch.
        query_token = query.split()[0] if query else ""
        section_slug = CATEGORY_TO_SECTION.get(query_token)

        if section_slug:
            quintype_articles, print_articles = await asyncio.gather(
                quintype.section_stories(section_slug, limit=analysis.k),
                asyncio.to_thread(smartflow.search, query, limit=max(3, analysis.k // 3)),
            )
            # Supplement with keyword search in case section API misses specific queries
            if len(quintype_articles) < 3:
                extra = await quintype.search(query, limit=analysis.k)
                seen = {str(a.get("id", "")) for a in quintype_articles}
                for a in extra:
                    aid = str(a.get("id", ""))
                    if aid not in seen:
                        quintype_articles.append(a)
                        seen.add(aid)
        else:
            quintype_articles, print_articles = await asyncio.gather(
                quintype.search(query, limit=analysis.k),
                asyncio.to_thread(smartflow.search, query, limit=max(3, analysis.k // 3)),
            )
            # Bilingual fallback: if Marathi search returned few results, also search
            # with English equivalents (many Marathi headlines use English sports/brand names).
            if len(quintype_articles) < 3:
                en_query = _build_en_fallback_query(query)
                if en_query:
                    extra = await quintype.search(en_query, limit=analysis.k)
                    seen = {str(a.get("id", "")) for a in quintype_articles}
                    for a in extra:
                        aid = str(a.get("id", ""))
                        if aid not in seen:
                            quintype_articles.append(a)
                            seen.add(aid)
    # Apply date-range filter if the planner extracted explicit dates from the query.
    # Skip for generic "top stories" queries — there's no specific topic to widen the
    # search on if the strict date filter empties the result, so best-effort recency
    # (already provided by top_stories/recent) is used instead of a hard cutoff.
    from_ms = None if generic else _ms_from_date_str(analysis.from_date)
    to_ms = None if generic else _ms_from_date_str(analysis.to_date)
    if to_ms:
        # Include full to_date day (add 24h)
        to_ms += 86_400_000

    def _in_range(article: dict) -> bool:
        pub = article.get("published-at") or 0
        if from_ms and pub < from_ms:
            return False
        if to_ms and pub > to_ms:
            return False
        return True

    if from_ms or to_ms:
        all_quintype, all_print = quintype_articles, print_articles
        combined = [a for a in all_quintype if _in_range(a)] + [a for a in all_print if _in_range(a)]

        if not combined:
            # Nothing on the exact date(s) asked for — widen by 3 days each way
            # before giving up entirely, so "काल X बद्दल काय झाले?" doesn't dead-end
            # just because the closest coverage is a day or two off.
            widened_from = (from_ms - 3 * 86_400_000) if from_ms else None
            widened_to = (to_ms + 3 * 86_400_000) if to_ms else None

            def _in_widened(article: dict) -> bool:
                pub = article.get("published-at") or 0
                if widened_from and pub < widened_from:
                    return False
                if widened_to and pub > widened_to:
                    return False
                return True

            combined = [a for a in (all_quintype + all_print) if _in_widened(a)]
            # else (still empty): fall through and pad below with unfiltered
            # topic-search results as a last resort.

        if len(combined) < 3:
            # A date window can trap just one weak/tangential match (e.g. a crime
            # story that only mentions "शेअर बाजार" in passing) while the actually
            # relevant coverage sits a day or two outside it. Pad with the topic
            # search's other results regardless of date rather than letting one
            # thin match crowd out better answers.
            seen_ids = {str(a.get("id", "")) for a in combined}
            for a in all_quintype + all_print:
                if str(a.get("id", "")) not in seen_ids:
                    combined.append(a)
                    seen_ids.add(str(a.get("id", "")))

        quintype_articles, print_articles = combined, []

    # Merge: quintype first (digital, more recent), then print; deduplicate by id
    seen_ids: set[str] = set()
    articles: list[dict] = []
    for a in quintype_articles + print_articles:
        aid = str(a.get("id", ""))
        if aid and aid in seen_ids:
            continue
        if aid:
            seen_ids.add(aid)
        articles.append(a)
    chunks = []
    for article in articles:
        text = extract_text(article)
        if len(text.strip()) < 50:
            continue
        headline = article.get("headline", "")
        # Skip boilerplate daily-roundup teaser pages ("Read today's updates in
        # one click") — Quintype only exposes a ~200-char generic blurb for
        # these, never real content, so they crowd out substantive articles.
        if "क्लिकवर" in headline:
            continue
        chunks.append(RetrievedChunk(
            id=str(article.get("id", "")),
            headline=article.get("headline", "Untitled"),
            published_at=format_date(article.get("published-at")),
            url=_article_url(article),
            chunk_text=truncate_to_tokens(text, 400),
        ))
    state["chunks"] = chunks
    state["steps"] = state.get("steps", []) + [
        TraceStep(title="Retrieving articles", detail=f"Found {len(chunks)} articles for: {query}")
    ]
    return state


def check_context(state: GraphState) -> GraphState:
    chunks = state.get("chunks", [])
    count = len(chunks)
    state["context_enough"] = count >= 1
    state["suggested_query"] = None
    state["steps"] = state.get("steps", []) + [
        TraceStep(
            title="Checking context quality",
            detail=(f"{count} article(s) retrieved" if count else "No relevant articles found"),
        )
    ]
    return state


def rewrite_query(state: GraphState) -> GraphState:
    current = state.get("current_query") or state["analysis"].search_query or state["question"]
    tokens = current.split()
    suggested = tokens[0] if len(tokens) > 1 else state["question"]
    state["current_query"] = suggested
    state["attempts"] = state.get("attempts", 0) + 1
    state["steps"] = state.get("steps", []) + [
        TraceStep(title="Rewriting query", detail=f"Trying: {suggested}")
    ]
    return state


def answer(state: GraphState) -> GraphState:
    chunks = state.get("chunks", [])
    articles_text = _format_chunks(chunks)
    prompt_tmpl = SYSTEM_PROMPT_MR if state.get("lang", "mr") == "mr" else SYSTEM_PROMPT_EN
    system = prompt_tmpl.format(articles=articles_text)
    if state.get("generic_query"):
        # A roundup phrase like "देश-विदेश घडामोडी" has no specific topic to
        # match — asking the LLM to judge relevance against that literal
        # phrasing makes it (correctly, but unhelpfully) refuse when the top
        # stories are just disparate news items. Ask it to summarize the
        # supplied top stories directly instead.
        user_content = (
            "आजच्या ठळक बातम्यांचा थोडक्यात सारांश द्या."
            if state.get("lang", "mr") == "mr"
            else "Summarize today's top news headlines briefly."
        )
    else:
        user_content = state["question"]
    messages = [{"role": "user", "content": user_content}]
    raw_answer = call_answer(system, messages)

    # If the LLM itself admits the retrieved articles aren't relevant, don't
    # auto-cite them as sources just because it left no [n] markers.
    unable = (
        "does not currently have sufficient coverage" in raw_answer
        or "पुरेसे वृत्तांकन उपलब्ध नाही" in raw_answer
    )

    if unable:
        cited_numbers = []
    else:
        cited_numbers = []
        for i in range(1, len(chunks) + 1):
            if f"[{i}]" in raw_answer:
                cited_numbers.append(i)
        if not cited_numbers:
            cited_numbers = list(range(1, min(len(chunks) + 1, 4)))

    raw_answer, remap = _renumber_citations(raw_answer, cited_numbers)

    sources = [
        NewsSource(
            number=remap[i],
            headline=chunks[i - 1].headline,
            url=chunks[i - 1].url,
            published_at=chunks[i - 1].published_at,
        )
        for i in cited_numbers
        if i <= len(chunks)
    ]

    state["sources"] = sources
    state["response"] = ChatResponse(
        answer=raw_answer,
        sources=sources,
        confidence="high" if len(cited_numbers) >= 2 else "medium",
        steps=state.get("steps", []),
    )
    return state


def limited_answer(state: GraphState) -> GraphState:
    chunks = state.get("chunks", [])
    _UNABLE = "ई सकाळकडे या विषयावर सध्या पुरेसे वृत्तांकन उपलब्ध नाही." if state.get("lang", "mr") == "mr" else "Esakal does not currently have sufficient coverage on this topic."
    if chunks:
        articles_text = _format_chunks(chunks)
        prompt_tmpl = SYSTEM_PROMPT_MR if state.get("lang", "mr") == "mr" else SYSTEM_PROMPT_EN
        system = prompt_tmpl.format(articles=articles_text)
        messages = [{"role": "user", "content": state["question"]}]
        raw_answer = call_answer(system, messages)
        # If the LLM itself admitted it can't answer, don't show irrelevant sources
        unable = (
            "does not currently have sufficient coverage" in raw_answer
            or "पुरेसे वृत्तांकन उपलब्ध नाही" in raw_answer
        )
        if unable:
            sources = []
        else:
            cited = [i for i in range(1, len(chunks) + 1) if f"[{i}]" in raw_answer]
            if not cited:
                cited = list(range(1, min(len(chunks) + 1, 4)))
            raw_answer, remap = _renumber_citations(raw_answer, cited)
            sources = [
                NewsSource(number=remap[i], headline=chunks[i-1].headline, url=chunks[i-1].url, published_at=chunks[i-1].published_at)
                for i in cited if i <= len(chunks)
            ]
        state["response"] = ChatResponse(
            answer=raw_answer,
            sources=sources,
            confidence="low",
            unable_to_answer=unable,
            steps=state.get("steps", []),
        )
    else:
        state["response"] = ChatResponse(
            answer=_UNABLE,
            sources=[],
            confidence="low",
            unable_to_answer=True,
            steps=state.get("steps", []),
        )
    return state


def out_of_scope(state: GraphState) -> GraphState:
    if state.get("lang", "mr") == "mr":
        answer_text = "मी फक्त esakal.com वर प्रकाशित बातम्यांबद्दलच उत्तर देऊ शकतो. हा प्रश्न बातम्यांच्या व्याप्तीबाहेर आहे."
    else:
        answer_text = "I can only answer questions about news covered on esakal.com. This question is outside the scope of news coverage."
    state["response"] = ChatResponse(
        answer=answer_text,
        sources=[],
        confidence="high",
        steps=state.get("steps", []),
    )
    return state


def ask_clarification(state: GraphState) -> GraphState:
    if state.get("lang", "mr") == "mr":
        question = state["analysis"].clarification_question or "कृपया तुमचा प्रश्न अधिक स्पष्ट करा."
        answer_text = "तुम्हाला मदत करण्यासाठी थोडी अधिक माहिती हवी आहे."
    else:
        question = state["analysis"].clarification_question or "Could you please clarify your question?"
        answer_text = "I need a bit more information to help you."
    state["response"] = ChatResponse(
        answer=answer_text,
        sources=[],
        confidence="high",
        clarification_question=question,
        steps=state.get("steps", []),
    )
    return state


def route_after_plan(state: GraphState) -> str:
    intent = state["analysis"].intent
    if intent == "out_of_scope":
        return "out_of_scope"
    if intent == "clarify" or state["analysis"].clarification_needed:
        return "ask_clarification"
    return "retrieve"


def route_after_check(state: GraphState) -> str:
    if state["context_enough"]:
        return "answer"
    if state.get("attempts", 0) < 1:
        return "rewrite_query"
    # After one rewrite attempt, try to answer with what we have
    return "answer" if state.get("chunks") else "limited_answer"
