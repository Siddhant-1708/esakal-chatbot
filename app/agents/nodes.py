import asyncio
from schemas import (
    QueryAnalysis, ContextAssessment, SynthesizedAnswer,
    RetrievedChunk, NewsSource, TraceStep, ChatResponse,
)
from app import quintype, smartflow
from app.retrieval import extract_text, truncate_to_tokens, format_date
from app.claude_client import call_structured, call_answer
from app.config import QUINTYPE_API_BASE
from app.agents.state import GraphState

PLAN_PROMPT = """You are a query planner for Ask Esakal, a news assistant for esakal.com — a Marathi-language newspaper.
All articles on Esakal are written in Marathi. Search queries must match Marathi text.

Analyse the user's question and return a JSON object with:
- intent: one of "answer" | "briefing" | "timeline" | "clarify" | "out_of_scope"
- search_query: the best search string to find relevant Esakal articles (see rules below)
- entities: list of key named entities (people, places, organisations, schemes)
- k: how many articles to retrieve (3 to 15, default 8)
- uses_history: true if the question references the conversation history
- clarification_needed: true if the question is too ambiguous to answer
- clarification_question: the clarifying question to ask (if needed)
- from_date: YYYY-MM-DD derived from any time reference the user gives (see DATE RULES below)
- to_date: YYYY-MM-DD derived from any time reference the user gives (see DATE RULES below)

DATE RULES — today is {today}. Convert all relative/named time references to absolute YYYY-MM-DD:
  Specific month name:
    "एप्रिल" / "April"           → from_date: 2026-04-01, to_date: 2026-04-30
    "मे" / "May"                  → from_date: 2026-05-01, to_date: 2026-05-31
    "जून" / "June"                → from_date: 2026-06-01, to_date: 2026-06-30
    (apply same logic for any month name — use current year unless user says otherwise)
  Relative ranges:
    "आज" / "today"                → from_date: today, to_date: today
    "काल" / "yesterday"           → from_date: yesterday, to_date: yesterday
    "या आठवड्यात" / "this week"   → from_date: Monday of current week, to_date: today
    "गेल्या आठवड्यात" / "last week" → from_date: Monday of last week, to_date: Sunday of last week
    "या महिन्यात" / "this month"  → from_date: 1st of current month, to_date: today
    "गेल्या महिन्यात" / "last month" → from_date: 1st of last month, to_date: last day of last month
    "गेल्या X दिवसांत" / "last X days" → from_date: today minus X days, to_date: today
  Specific dates:
    "१ एप्रिल" / "April 1"        → from_date: 2026-04-01, to_date: 2026-04-01
  No time reference → leave from_date and to_date null
- refusal_reason: explain why if intent is out_of_scope

SEARCH QUERY RULES (critical — Esakal uses simple Marathi keyword search, not natural language):
- search_query must be SHORT keywords only — 1 to 3 words maximum. No full sentences.
- Use only the core entity: person name, place name, or topic word. Drop words like "आज", "काय", "घडले", "बद्दल", "सांगा".
- Always use Marathi/Devanagari spelling. Common transliterations:
    Modi → मोदी, Pune → पुणे, Mumbai → मुंबई, Maharashtra → महाराष्ट्र,
    Delhi → दिल्ली, BJP → भाजप, Congress → काँग्रेस, Fadnavis → फडणवीस,
    Shinde → शिंदे, Pawar → पवार, Nashik → नाशिक, Nagpur → नागपूर
- Examples:
    "आज मुंबईत काय घडले?" → search_query: "मुंबई"
    "news about modi" → search_query: "मोदी"
    "pune traffic today" → search_query: "पुणे वाहतूक"
    "महाराष्ट्रात काय घडले?" → search_query: "महाराष्ट्र"
    "राजकीय बातम्या / politics" → search_query: "महाराष्ट्र फडणवीस" (use politician/party names, not abstract "राजकारण")
    "या आठवड्यातील राजकीय बातम्या" → search_query: "फडणवीस शिंदे पवार"

Intent guide:
- "answer": factual question about a specific topic or event
- "briefing": broad "what's happening / what happened" questions about a place, person, or topic — e.g. "पुण्यात काय घडले?", "मोदींबद्दल सांगा", "recent Pune news". Use this whenever a location or named subject is mentioned.
- "timeline": "what happened with X over time" — ordered chronological summary
- "clarify": ONLY when there is truly NO topic, person, or place mentioned — e.g. bare single words like "politics" or "news" with zero context
- "out_of_scope": not a news question — ONLY for things like coding help, recipes, personal relationship advice, maths homework, etc. When in doubt, use "briefing" instead.

IMPORTANT — these topics are ALWAYS valid news, NEVER mark them out_of_scope:
- Science and space: आर्टिमिस, चंद्र मोहीम, नासा, अंतराळ, Artemis, NASA, moon mission, satellite, rocket
- Health and medicine: कोविड, रोग, औषध, vaccine, disease, hospital
- Finance and economy: personal finance, share market, stock market, budget, tax, GST, inflation, mutual funds, शेअर बाजार, अर्थसंकल्प, कर, महागाई, गुंतवणूक — "personal finance" means finance news, NOT personal advice
- Sports, weather, environment, crime — all are news topics
- Any named event, mission, scheme, or organisation is a news topic
- If you are unsure whether something is news, assume it IS news and use "briefing"

Conversation history:
{history}

Question: {question}"""

CHECK_PROMPT = """You are evaluating whether retrieved news articles contain enough information
to answer a user's question about current events from esakal.com.

Question: {question}

Retrieved articles:
{chunks_formatted}

Return JSON:
- context_enough: true if AT LEAST ONE article contains relevant information (score >= 4). Be generous — if any article partially addresses the question, set true.
- relevance_score: integer 0-10 (0 = completely irrelevant, 10 = perfectly answers the question). Score based on the BEST article, not the average.
- reason: one sentence explaining your score
- suggested_query: a better Marathi search query to try if ALL articles are irrelevant (or null)"""

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
4. Only say "एसकाळकडे या विषयावर सध्या पुरेसे वृत्तांकन उपलब्ध नाही." if NONE of the articles relate to the question at all.
5. WRITE ONLY IN MARATHI. Every word must be in Marathi/Devanagari.

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
    from datetime import date
    history_text = _format_history(state.get("history", []))
    system = "You are a query planner."
    user = PLAN_PROMPT.format(
        history=history_text,
        question=state["question"],
        today=date.today().isoformat(),
    )
    analysis = call_structured(system, user, QueryAnalysis)
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
    query = state.get("current_query") or analysis.search_query or state["question"]
    quintype_articles, print_articles = await asyncio.gather(
        quintype.search(query, limit=analysis.k),
        asyncio.to_thread(smartflow.search, query, limit=max(3, analysis.k // 3)),
    )
    # Apply date-range filter if the planner extracted explicit dates from the query
    from_ms = _ms_from_date_str(analysis.from_date)
    to_ms = _ms_from_date_str(analysis.to_date)
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
        quintype_articles = [a for a in quintype_articles if _in_range(a)]
        print_articles = [a for a in print_articles if _in_range(a)]

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
        chunks.append(RetrievedChunk(
            id=str(article.get("id", "")),
            headline=article.get("headline", "Untitled"),
            published_at=format_date(article.get("published-at")),
            url=_article_url(article),
            chunk_text=truncate_to_tokens(text, 800),
        ))
    state["chunks"] = chunks
    state["steps"] = state.get("steps", []) + [
        TraceStep(title="Retrieving articles", detail=f"Found {len(chunks)} articles for: {query}")
    ]
    return state


def check_context(state: GraphState) -> GraphState:
    chunks = state.get("chunks", [])
    if not chunks:
        state["context_enough"] = False
        state["suggested_query"] = None
        return state
    chunks_formatted = _format_chunks(chunks)
    system = "You are a context evaluator."
    user = CHECK_PROMPT.format(question=state["question"], chunks_formatted=chunks_formatted)
    assessment = call_structured(system, user, ContextAssessment)
    state["context_enough"] = assessment.context_enough
    state["suggested_query"] = assessment.suggested_query
    state["steps"] = state.get("steps", []) + [
        TraceStep(
            title="Checking context quality",
            detail=f"Score: {assessment.relevance_score}/10 — {assessment.reason}",
        )
    ]
    return state


def rewrite_query(state: GraphState) -> GraphState:
    suggested = state.get("suggested_query") or state["analysis"].search_query + " latest"
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
    messages = [{"role": "user", "content": state["question"]}]
    raw_answer = call_answer(system, messages)

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
    _UNABLE = "एसकाळकडे या विषयावर सध्या पुरेसे वृत्तांकन उपलब्ध नाही." if state.get("lang", "mr") == "mr" else "Esakal does not currently have sufficient coverage on this topic."
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
