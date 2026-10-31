from __future__ import annotations

from typing import Any, Literal
from typing_extensions import NotRequired, TypedDict


WriteOperation = Literal["SET", "APPEND"]
HistoryRole = Literal["system", "user", "assistant"]


class CNLPVariableInfo(TypedDict):
    """Configuration required to initialize one CNL-P variable."""

    variable_name: str
    # config.py imports generated types from schema.py and stores the actual
    # Python type object here.
    value_type: Any
    default_value: Any


class HistorySection(TypedDict):
    role: HistoryRole
    content: str


class ModelConfig(TypedDict):
    api_key: str
    model_name: str
    base_url: NotRequired[str | None]


class AgentConfig(TypedDict):
    variable_config: list[CNLPVariableInfo]
    agent_attributes: str
    model_config: ModelConfig


class BooleanResponse(TypedDict):
    result: bool


# CNL-P declared types are appended below this static section by the
# Native schema generator.
