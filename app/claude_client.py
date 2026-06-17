import json
from openai import OpenAI, RateLimitError as OpenAIRateLimitError
from groq import Groq, RateLimitError as GroqRateLimitError
from app.config import OPENAI_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, MODEL

STUB_MODE = not any([OPENAI_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY])

from app import usage_store

# Primary: OpenAI. Fallback: Groq (free tier, 14k RPD)
_openai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
_groq = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Groq uses llama-3.3-70b — highly capable, generous free limits
GROQ_MODEL = "llama-3.3-70b-versatile"

_STUB_STRUCTURED = {
    "QueryAnalysis": {
        "intent": "answer",
        "search_query": "Maharashtra news today",
        "entities": ["Maharashtra"],
        "k": 8,
        "uses_history": False,
        "clarification_needed": False,
        "clarification_question": None,
        "from_date": None,
        "to_date": None,
        "refusal_reason": None,
    },
    "ContextAssessment": {
        "context_enough": True,
        "relevance_score": 8,
        "reason": "[STUB] Articles look relevant.",
        "suggested_query": None,
    },
}


def _chat(client, model: str, messages: list[dict], temperature: float) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    if response.usage:
        provider = "groq" if model == GROQ_MODEL else "openai"
        usage_store.record(
            provider,
            response.usage.prompt_tokens or 0,
            response.usage.completion_tokens or 0,
        )
    return response.choices[0].message.content


class AllProvidersRateLimited(RuntimeError):
    pass


def _call_with_fallback(messages: list[dict], temperature: float) -> str:
    """Try OpenAI first; fall back to Groq on rate-limit."""
    if _openai:
        try:
            return _chat(_openai, MODEL, messages, temperature)
        except OpenAIRateLimitError as e:
            print(f"[llm] OpenAI rate-limit: {e}. Falling back to Groq.")
            if _groq:
                try:
                    return _chat(_groq, GROQ_MODEL, messages, temperature)
                except GroqRateLimitError as e2:
                    raise AllProvidersRateLimited("Both OpenAI and Groq are rate-limited. Try again in a few minutes.") from e2
            raise AllProvidersRateLimited("OpenAI rate-limited and no Groq key set.") from e
    if _groq:
        try:
            return _chat(_groq, GROQ_MODEL, messages, temperature)
        except GroqRateLimitError as e:
            raise AllProvidersRateLimited("Groq rate-limited and no OpenAI key set.") from e
    raise RuntimeError("No LLM client available — set OPENAI_API_KEY or GROQ_API_KEY in .env")


def call_structured(system: str, user: str, schema_class):
    if STUB_MODE:
        name = schema_class.__name__
        data = _STUB_STRUCTURED.get(name, {})
        if not data:
            raise ValueError(f"No stub data for {name}. Set OPENAI_API_KEY in .env.")
        return schema_class(**data)

    messages = [
        {"role": "system", "content": system + "\n\nRespond with valid JSON only. No markdown code fences."},
        {"role": "user", "content": user},
    ]
    raw = _call_with_fallback(messages, temperature=0).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    data = json.loads(raw)
    return schema_class(**data)


def call_answer(system: str, messages: list[dict]) -> str:
    if STUB_MODE:
        question = messages[-1]["content"] if messages else "your question"
        return (
            f"[STUB MODE — no API key set]\n\n"
            f"This is a placeholder answer for: \"{question}\"\n\n"
            f"Set OPENAI_API_KEY or GROQ_API_KEY in your .env to get real answers. [1]"
        )

    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    return _call_with_fallback(full_messages, temperature=0.3)
