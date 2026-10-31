"""Utilities package exports."""

from .env import get_env_value
from .json import (
    add_value_by_path,
    delete_by_path,
    extract_single_json_from_text,
    find_keys_by_pattern,
    get_value_by_path_with_copy,
    get_value_by_path_without_copy,
    read_json,
    set_value_by_path,
    write_json,
)
from .config import configurate_parameters

try:
    from .llm import (
        LLMclient,
        OpenaiClient,
        PromptSection,
        SearchContextSize,
        WebSearchClient,
        WebSearchResult,
        WebSource,
        create_openai_client,
        create_llm_client,
        create_prompt_section,
        create_web_search_client,
        extract_web_search_result,
        get_model_response,
        get_web_search_response,
    )
    _LLM_EXPORTS = [
        "LLMclient",
        "OpenaiClient",
        "PromptSection",
        "SearchContextSize",
        "WebSearchClient",
        "WebSearchResult",
        "WebSource",
        "create_openai_client",
        "create_llm_client",
        "create_prompt_section",
        "create_web_search_client",
        "extract_web_search_result",
        "get_model_response",
        "get_web_search_response",
    ]
except ModuleNotFoundError:
    _LLM_EXPORTS = []

__all__ = [
    "add_value_by_path",
    "delete_by_path",
    "extract_single_json_from_text",
    "find_keys_by_pattern",
    "get_env_value",
    "get_value_by_path_with_copy",
    "get_value_by_path_without_copy",
    "read_json",
    "set_value_by_path",
    "write_json",
    "configurate_parameters"
] + _LLM_EXPORTS
