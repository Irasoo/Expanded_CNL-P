from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


AGENT_INSTRUCTIONS = """
You are an assistant responsible for drafting company-internal communications.
Your users are company members who need clear, concise drafts for team updates,
company newsletters, FAQs, or other internal communications.

Apply these rules to every task:
- Never invent company facts, project status, personnel decisions, dates,
  metrics, owners, commitments, policies, or organizational information.
- Ground all factual claims in information supplied by the user.
- A 3P update clearly separates Progress, Plans, and Problems.
- A newsletter prioritizes broadly relevant information and removes narrow,
  repetitive, or overly detailed material.
- FAQ answers use only supplied information and explicitly identify missing
  information when a question cannot be answered.
- General communications follow the requested audience, purpose, tone, and
  format.
""".strip()


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    model: str
    base_url: str | None

    @classmethod
    def from_environment(cls) -> "LLMSettings":
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = (
            os.getenv("CNLP_REFERENCE_LLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
        )
        base_url = os.getenv("BASE_URL", "").strip() or None

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured in .env or the environment.")
        if not model:
            raise RuntimeError(
                "Neither CNLP_REFERENCE_LLM_MODEL nor OPENAI_MODEL is configured "
                "in .env or the environment."
            )
        return cls(api_key=api_key, model=model, base_url=base_url)


class LLMRuntime:
    def __init__(self, settings: LLMSettings) -> None:
        client_options: dict[str, str] = {"api_key": settings.api_key}
        if settings.base_url:
            client_options["base_url"] = settings.base_url.rstrip("/")
        self._client = OpenAI(**client_options)
        self._model = settings.model

    def complete(self, prompt: str, *, empty_result_error: str) -> str:
        response = self._client.responses.create(
            model=self._model,
            reasoning={"effort": "high"},
            instructions=AGENT_INSTRUCTIONS,
            input=prompt,
        )
        result = str(response.output_text or "").strip()
        if not result:
            raise RuntimeError(empty_result_error)
        return result

    def complete_json(self, prompt: str, *, empty_result_error: str) -> dict[str, Any]:
        raw = self.complete(prompt, empty_result_error=empty_result_error)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start < 0 or end <= start:
                raise RuntimeError("The LLM did not return a valid JSON object.") from None
            try:
                value = json.loads(raw[start : end + 1])
            except json.JSONDecodeError as exc:
                raise RuntimeError("The LLM did not return a valid JSON object.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("The LLM returned JSON, but it was not an object.")
        return value

