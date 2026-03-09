import openai
import asyncio
from fastapi import HTTPException, status
from typing import Literal, TypedDict, Protocol
from openai import OpenAI, base_url


class PromptSection(TypedDict):
    """
    Represents a section of an LLM prompt with an associated role.
    """
    role: Literal["system", "user", "assistant"]
    content: str


def create_prompt_section(role: Literal["system", "user", "assistant"], content: str):
    return {"role": role, "content": content}


class Chatgpt:
    def __init__(self):
        self.client = None

    @classmethod
    async def create(cls, key, model):
        instance = cls()
        await instance.async_init(key, model)
        return instance

    async def async_init(self, key, model):
        self.client = openai.AsyncOpenAI(api_key=key)
        self.model = model

    async def process_message(self, message: list):
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    messages=message,
                ),
                timeout=120  # Timeout in seconds
            )
            return response
        except asyncio.TimeoutError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request timed out")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"An error occurred: {e}")


class Chatgpt_json:
    def __init__(self):
        self.client = None

    @classmethod
    async def create(cls, settings):
        instance = cls()
        await instance.async_init(settings)
        return instance

    async def async_init(self, settings):
        self.client = openai.AsyncOpenAI(api_key=settings.get('openai_key'))
        self.model = settings.get('llm')

    async def process_message(self, message: list):
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=message,
                    temperature=0,
                    response_format={"type": "json_object"},
                ),
                timeout=120  # Timeout in seconds
            )
            return response
        except asyncio.TimeoutError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request timed out")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"An error occurred: {e}")


class Chatgpt_stream:
    def __init__(self):
        self.client = None

    @classmethod
    async def create(cls, settings):
        instance = cls()
        await instance.async_init(settings)
        return instance

    async def async_init(self, settings):
        self.client = openai.AsyncOpenAI(api_key=settings.get('openai_key'))
        self.model = settings.get('llm')

    async def process_message(self, message: list):
        try:
            stream = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=message,
                    stream=True,
                ),
                timeout=120  # Timeout in seconds
            )
            async for part in stream:
                yield part
        except asyncio.TimeoutError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request timed out")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"An error occurred: {e}")


class LLMclient(Protocol):
    def complete(self, prompt: str | list[PromptSection]) -> str:
        ...


class OpenaiClient(LLMclient):
    api_key: str
    model: str
    org: str

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


def create_llm_client(vals: dict[str, str | None]) -> LLMclient:
    def required_var(name: str) -> str:
        val = vals.get(name, None)
        if val is None:
            raise ValueError(f"Missing environment variable {name}.")
        return val

    if "OPENAI_API_KEY" in vals:
        api_key = required_var("OPENAI_API_KEY")
        model = required_var("OPENAI_MODEL")
        org = vals.get("OPENAI_ORG", None) or ""
        base_url = vals.get("BASE_URL", None) or ""
        return OpenaiClient(api_key, model, org, base_url)

    else:
        raise ValueError("Missing environment variables.")