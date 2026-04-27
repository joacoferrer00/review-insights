"""Quick connectivity test for the configured LLM provider."""

from review_insights.llm import LLMRequest, get_provider


def main() -> None:
    provider = get_provider()
    print(f"Provider : {provider.name()}")

    request = LLMRequest(
        system="You are a helpful assistant.",
        user="Reply with exactly one sentence confirming you are working correctly.",
    )

    response = provider.complete(request)

    print(f"Response : {response.text.strip()}")
    print(f"Tokens   : {response.prompt_tokens} in / {response.completion_tokens} out")
    print(f"Finish   : {response.finish_reason}")
    print("\nOK - LLM provider is operational.")


if __name__ == "__main__":
    main()
