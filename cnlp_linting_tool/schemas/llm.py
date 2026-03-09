from typing import Literal, TypedDict, Protocol

class PromptSection(TypedDict):
    """
    Represents a section of an LLM prompt with an associated role.
    """
    role: Literal["system", "user", "assistant"]
    content: str