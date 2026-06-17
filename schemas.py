from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class StrictBaseModel(BaseModel):
    model_config = {"extra": "forbid"}


class ChatMessage(StrictBaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(StrictBaseModel):
    question: str = Field(min_length=2, max_length=500)
    source: Literal["esakal"] = "esakal"
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    lang: Literal["mr", "en"] = "mr"


class QueryAnalysis(StrictBaseModel):
    intent: Literal["answer", "briefing", "timeline", "clarify", "out_of_scope"]
    search_query: Optional[str] = Field(default=None, max_length=300)
    entities: list = Field(default_factory=list)
    k: int = Field(default=8)

    @model_validator(mode="before")
    @classmethod
    def coerce_entities(cls, values):
        ents = values.get("entities", [])
        coerced = []
        for e in ents:
            if isinstance(e, dict):
                coerced.append(e.get("name") or e.get("value") or str(e))
            else:
                coerced.append(str(e))
        values["entities"] = coerced
        return values

    @model_validator(mode="after")
    def clamp_k(self):
        self.k = max(3, min(self.k, 15))
        return self
    uses_history: bool = False
    clarification_needed: bool = False
    clarification_question: Optional[str] = Field(default=None, max_length=500)
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    refusal_reason: Optional[str] = Field(default=None, max_length=500)


class RetrievedChunk(StrictBaseModel):
    id: str
    headline: str
    published_at: str
    url: str
    chunk_text: str


class NewsSource(StrictBaseModel):
    number: int
    headline: str
    url: str
    published_at: str


class ContextAssessment(StrictBaseModel):
    context_enough: bool
    relevance_score: int = Field(ge=0, le=10)
    reason: str = Field(min_length=1, max_length=500)
    suggested_query: Optional[str] = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_score(self):
        if self.context_enough and self.relevance_score < 4:
            raise ValueError("context_enough requires relevance_score >= 4")
        return self


class SynthesizedAnswer(StrictBaseModel):
    answer: str = Field(min_length=1, max_length=4000)
    cited_source_numbers: list[int] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"
    unable_to_answer: bool = False

    @model_validator(mode="after")
    def validate_citations(self):
        if not self.unable_to_answer and not self.cited_source_numbers:
            raise ValueError("Answers require at least one cited source.")
        return self


class TraceStep(StrictBaseModel):
    title: str
    detail: str
    source_numbers: list[int] = Field(default_factory=list)


class ChatResponse(StrictBaseModel):
    answer: str
    sources: list[NewsSource]
    confidence: Literal["high", "medium", "low"]
    unable_to_answer: bool = False
    clarification_question: Optional[str] = None
    steps: list[TraceStep] = Field(default_factory=list)
