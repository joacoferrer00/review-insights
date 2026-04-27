from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMRequest(BaseModel):
    system: str | None = None
    user: str
    temperature: float = 0.0
    max_tokens: int | None = None


class LLMResponse(BaseModel):
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    def name(self) -> str: ...
