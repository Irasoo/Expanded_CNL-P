from ..schemas.llm import PromptSection

from typing import Protocol, Literal
from openai import OpenAI

def create_prompt_section(role: Literal["system", "user", "assistant"], content: str):
    return {"role": role, "content": content}


class LLMclient(Protocol):
    def complete(self, prompt: str | list[PromptSection]) -> str:
        ...


class OpenaiClient(LLMclient):
    api_key: str
    model: str
    org: str
    base_url: str  # 可选：添加类型注解以保持一致性

    def __init__(self, api_key: str, model: str, org: str, base_url: str):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.org = org
        self.base_url = base_url

    def complete(self, prompt: list[PromptSection]):
        client = OpenAI(
            api_key=self.api_key,
            organization=self.org,
            base_url=self.base_url,
        )

        completion = client.chat.completions.create(
            model=self.model,
            n=1,
            temperature=0,
            messages=prompt
        )

        return completion.choices[0].message.content


def create_llm_client(settings) -> LLMclient:

    if settings.OPENAI_API_KEY:
        api_key = settings.OPENAI_API_KEY
        model = settings.OPENAI_MODEL
        org = ""
        base_url = settings.BASE_URL or ""
        return OpenaiClient(api_key, model, org, base_url)

    else:
        raise ValueError("Missing environment variables.")