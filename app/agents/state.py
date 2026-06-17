from typing import TypedDict, Optional
from schemas import ChatMessage, QueryAnalysis, RetrievedChunk, NewsSource, ChatResponse, TraceStep


class GraphState(TypedDict):
    question: str
    source: str
    lang: str
    history: list[ChatMessage]
    analysis: Optional[QueryAnalysis]
    current_query: Optional[str]
    chunks: list[RetrievedChunk]
    sources: list[NewsSource]
    attempts: int
    context_enough: bool
    suggested_query: Optional[str]
    steps: list[TraceStep]
    response: Optional[ChatResponse]
