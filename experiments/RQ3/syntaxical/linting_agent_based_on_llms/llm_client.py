from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

from openai import OpenAI

from experiments.RQ3.experiment_runtime import call_with_retry


LLM_MODEL = "gpt-5.6-sol"
LLM_REASONING_EFFORT = "high"


class PromptSection(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


def create_prompt_section(
    role: Literal["system", "user", "assistant"],
    content: str,
) -> PromptSection:
    return {"role": role, "content": content}


class LLMClient(Protocol):
    def complete(
        self,
        prompt: list[PromptSection],
        *,
        max_retries: int = 10,
        retry_delay_seconds: int = 15,
        attempt_log_path: Path | None = None,
        attempt_context: dict[str, Any] | None = None,
    ) -> str:
        ...


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        organization: str = "",
        base_url: str = "",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.organization = organization
        self.base_url = base_url

    def complete(
        self,
        prompt: list[PromptSection],
        *,
        max_retries: int = 10,
        retry_delay_seconds: int = 15,
        attempt_log_path: Path | None = None,
        attempt_context: dict[str, Any] | None = None,
    ) -> str:
        client_arguments: dict[str, object] = {"api_key": self.api_key}
        if self.organization:
            client_arguments["organization"] = self.organization
        if self.base_url:
            client_arguments["base_url"] = self.base_url
        client = OpenAI(**client_arguments)
        def request() -> str:
            completion = client.chat.completions.create(
                model=self.model,
                n=1,
                messages=prompt,
                reasoning_effort=LLM_REASONING_EFFORT,
            )
            if not completion.choices:
                raise RuntimeError(
                    "The LLM endpoint returned no completion choices."
                )
            content = completion.choices[0].message.content
            if not content or not content.strip():
                raise RuntimeError("The LLM endpoint returned an empty response.")
            return content

        return call_with_retry(
            request,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            attempt_log_path=attempt_log_path,
            context=attempt_context,
        )


def create_llm_client(values: dict[str, str | None]) -> LLMClient:
    api_key = values.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing environment variable OPENAI_API_KEY.")
    base_url = (
        values.get("OPENAI_BASE_URL")
        or values.get("BASE_URL")
        or ""
    )
    return OpenAICompatibleClient(
        api_key=api_key,
        model=LLM_MODEL,
        organization=values.get("OPENAI_ORG") or "",
        base_url=base_url,
    )


__all__ = [
    "LLM_MODEL",
    "LLM_REASONING_EFFORT",
    "PromptSection",
    "create_llm_client",
    "create_prompt_section",
]
