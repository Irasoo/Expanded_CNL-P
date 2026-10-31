from dataclasses import dataclass
from typing import TypedDict


class ParserSettings(TypedDict):
    agent_sections: list[str]
    worker_sections: list[str]
    ignored_agent_sections: list[str]
    required_fields: list[list[str]]


parser_like_settings: ParserSettings = {
    "agent_sections": [
        "DEFINE_PERSONA",
        "DEFINE_CONSTRAINTS",
        "DEFINE_CONCEPTS",
        "DEFINE_TYPES",
        "DEFINE_VARIABLES",
        "DEFINE_WORKER",
        "DEFINE_AUDIENCE",
    ],
    "ignored_agent_sections": [],
    "worker_sections": [
        "INPUTS",
        "OUTPUTS",
        "EXAMPLES",
        "MAIN_FLOW",
        "ALTERNATIVE_FLOW",
        "EXCEPTION_FLOW",
    ],
    "required_fields": [
        ["persona", "ROLE"],
        ["worker", "main_flow"],
    ],
}


@dataclass(frozen=True)
class Settings:
    parser_like_settings: ParserSettings


settings = Settings(parser_like_settings=parser_like_settings)
