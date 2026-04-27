import os

from dotenv import load_dotenv

from .base import LLMProvider, LLMRequest, LLMResponse

load_dotenv()


def get_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "gemini-2.0-flash")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    if not api_key:
        raise ValueError("LLM_API_KEY is not set in .env")

    if provider == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider(api_key=api_key, model=model, temperature=temperature)

    raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'. Supported: gemini")


__all__ = ["get_provider", "LLMProvider", "LLMRequest", "LLMResponse"]
