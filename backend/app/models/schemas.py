from typing import Literal
from pydantic import BaseModel, Field


class Source(BaseModel):
    title: str
    url: str
    website: str
    relevance: float = 0.0
    excerpt: str = ""


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=20)
    stream: bool = False


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    model: str | None = None
    fallback: bool = False


class HealthResponse(BaseModel):
    status: Literal["ok"]
    knowledge_ready: bool


class StatusResponse(BaseModel):
    backend: Literal["ok"]
    knowledge_base: Literal["ready", "empty"]
    ai_model_configured: bool
    document_count: int
    source_websites: list[str] = Field(default_factory=list)


class SourceInfo(BaseModel):
    name: str
    url: str
    document_count: int
