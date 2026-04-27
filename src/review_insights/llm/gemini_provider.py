from google import genai
from google.genai import types

from .base import LLMProvider, LLMRequest, LLMResponse


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, temperature: float = 0.0):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._temperature = temperature

    def name(self) -> str:
        return f"gemini/{self._model}"

    def complete(self, request: LLMRequest) -> LLMResponse:
        contents = []
        if request.system:
            contents.append(types.Content(role="user", parts=[types.Part(text=request.system)]))
            contents.append(types.Content(role="model", parts=[types.Part(text="Understood.")]))
        contents.append(types.Content(role="user", parts=[types.Part(text=request.user)]))

        config = types.GenerateContentConfig(
            temperature=request.temperature if request.temperature is not None else self._temperature,
            max_output_tokens=request.max_tokens,
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        if not response.candidates:
            feedback = getattr(response, "prompt_feedback", None)
            raise ValueError(f"Gemini returned no candidates (prompt_feedback: {feedback})")

        candidate = response.candidates[0]

        if not candidate.content or not candidate.content.parts:
            raise ValueError(
                f"Gemini candidate has no content parts (finish_reason: {candidate.finish_reason})"
            )

        # With thinking enabled, parts may include a thinking part before the response.
        # Use the last part which is always the actual text response.
        text = candidate.content.parts[-1].text
        usage = response.usage_metadata

        return LLMResponse(
            text=text,
            model=self._model,
            prompt_tokens=getattr(usage, "prompt_token_count", None),
            completion_tokens=getattr(usage, "candidates_token_count", None),
            finish_reason=str(candidate.finish_reason) if candidate.finish_reason else None,
        )
