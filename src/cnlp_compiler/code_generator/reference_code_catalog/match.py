from __future__ import annotations

import json
import re
from typing import Literal, TypedDict

from ...utils import (
    create_prompt_section,
    extract_single_json_from_text,
    get_model_response,
)
from .code_registry.models import RegisteredCode


class ReferenceCodeSearchArgument(TypedDict):
    """One parameter requirement of the CNL-P Call API Command."""

    # The formal parameter name requested by the CNL-P CALL statement.
    parameter_name: str

    # The CNL-P variable or field supplied to that parameter.
    argument_variable_name: str

    # The business meaning of the supplied CNL-P variable or field.
    argument_description: str | None

    # Simplified matching type: str, number, bool, list, dict, or unknown.
    argument_type: str


class ReferenceCodeExpectedReturn(TypedDict):
    """The return value expected by the CNL-P Call API Command."""

    # The CNL-P variable that will receive the reference function's result.
    variable_name: str

    # The business meaning of the expected result.
    return_description: str | None

    # Simplified matching type: str, number, bool, list, dict, or unknown.
    return_type: str


class ReferenceCodeSearchQuery(TypedDict):
    """Catalog-facing requirements derived from one Call API Plan."""

    # The API name written in the CNL-P CALL statement.
    requested_api_name: str

    # The Planner's full-workflow summary of this particular API invocation.
    task_description: str

    # The input requirements of this API invocation.
    arguments: list[ReferenceCodeSearchArgument]

    # The expected response requirement, or None when the result is ignored.
    expected_return: ReferenceCodeExpectedReturn | None


class ReferenceCodeSearchParameter(TypedDict):
    """Metadata about one registered reference function parameter."""

    # The real Python parameter name of the registered reference function.
    parameter_name: str

    # The registered annotation reduced to one simplified matching type.
    parameter_type: str

    # The parameter explanation supplied during registration or in docstring.
    parameter_description: str

    # Whether callers must provide this parameter.
    parameter_required: bool

    # The Python signature kind needed for basic call compatibility checks.
    parameter_kind: str


class ReferenceCodeSearchReturn(TypedDict):
    """Metadata about the return value of one registered function."""

    # Whether the registered reference function returns a value.
    has_return_value: bool

    # The registered annotation reduced to one simplified matching type.
    return_type: str | None

    # The return-value explanation supplied during registration or docstring.
    return_description: str


class ReferenceCodeSearchDocument(TypedDict):
    """The source-free metadata presented to the matching procedures."""

    # The real Python function name and Catalog key for the candidate.
    function_name: str

    # The registered high-level purpose of the candidate function.
    description: str

    # The candidate function's parameter metadata.
    parameters: list[ReferenceCodeSearchParameter]

    # The candidate function's return metadata.
    return_spec: ReferenceCodeSearchReturn


try:
    from ...prompts.reference_code_catalog import LLM_MATCHING_PROMPT as _LLM_MATCHING_PROMPT
except ImportError:  # Supports legacy top-level package imports.
    from prompts.reference_code_catalog import LLM_MATCHING_PROMPT as _LLM_MATCHING_PROMPT


def build_search_documents(
    entries: tuple[RegisteredCode, ...],
) -> list[ReferenceCodeSearchDocument]:
    """Create source-free documents from the registered reference entries."""
    return [
        ReferenceCodeSearchDocument(
            function_name=entry.function_name,
            description=entry.description,
            parameters=[
                ReferenceCodeSearchParameter(
                    parameter_name=parameter.name,
                    parameter_type=_simplify_search_type(
                        parameter.type_name
                    ),
                    parameter_description=parameter.description,
                    parameter_required=parameter.required,
                    parameter_kind=parameter.kind,
                )
                for parameter in entry.parameters
            ],
            return_spec=ReferenceCodeSearchReturn(
                has_return_value=entry.returns.has_return,
                return_type=(
                    None
                    if entry.returns.type_name is None
                    else _simplify_search_type(entry.returns.type_name)
                ),
                return_description=entry.returns.description,
            ),
        )
        for entry in entries
    ]


def rule_based_match(
    *,
    query: ReferenceCodeSearchQuery,
    documents: list[ReferenceCodeSearchDocument],
) -> str | None:
    """Return one unambiguous exact-name candidate or None.

    This is deliberately narrow. It only accepts candidates whose normalized
    names match exactly and whose call signatures do not contain a clear type
    or required-parameter conflict.
    """
    _validate_search_query(query)
    normalized_name = _normalize_identifier(query["requested_api_name"])
    matching_documents = [
        document
        for document in documents
        if _normalize_identifier(document["function_name"]) == normalized_name
        and _is_signature_compatible(query, document)
    ]
    if len(matching_documents) != 1:
        return None
    return matching_documents[0]["function_name"]


def llm_based_match(
    *,
    query: ReferenceCodeSearchQuery,
    documents: list[ReferenceCodeSearchDocument],
) -> str | None:
    """Select one source-free candidate through the catalog's LLM utility."""
    _validate_search_query(query)
    if not documents:
        return None

    prompt = _build_llm_matching_prompt(query=query, documents=documents)
    response = get_model_response(prompt)
    return _parse_llm_matching_response(
        response=response,
        candidate_names={document["function_name"] for document in documents},
    )


def _is_signature_compatible(
    query: ReferenceCodeSearchQuery,
    document: ReferenceCodeSearchDocument,
) -> bool:
    parameters = {
        parameter["parameter_name"]: parameter
        for parameter in document["parameters"]
    }
    accepts_extra_keywords = any(
        parameter["parameter_kind"] == "var_keyword"
        for parameter in document["parameters"]
    )
    query_arguments = {
        argument["parameter_name"]: argument
        for argument in query["arguments"]
    }

    for parameter in document["parameters"]:
        if (
            parameter["parameter_required"]
            and parameter["parameter_kind"]
            not in {"var_positional", "var_keyword"}
            and parameter["parameter_name"] not in query_arguments
        ):
            return False

    for argument_name, argument in query_arguments.items():
        parameter = parameters.get(argument_name)
        if parameter is None:
            if not accepts_extra_keywords:
                return False
            continue
        if _types_clearly_conflict(
            argument["argument_type"],
            parameter["parameter_type"],
        ):
            return False

    expected_return = query["expected_return"]
    if expected_return is None:
        return True

    return_spec = document["return_spec"]
    if not return_spec["has_return_value"]:
        return False
    return not _types_clearly_conflict(
        expected_return["return_type"],
        return_spec["return_type"],
    )


def _types_clearly_conflict(
    requested_type: str,
    candidate_type: str | None,
) -> bool:
    requested_family = _type_family(requested_type)
    candidate_family = _type_family(candidate_type)
    return (
        requested_family != "unknown"
        and candidate_family != "unknown"
        and requested_family != candidate_family
    )


def _type_family(type_name: str | None) -> Literal[
    "text", "number", "boolean", "list", "dict", "unknown"
]:
    if not isinstance(type_name, str) or not type_name.strip():
        return "unknown"

    normalized = re.sub(r"\s+", "", type_name).strip("'\"").lower()
    if normalized in {"any", "object", "typing.any"}:
        return "unknown"
    if normalized in {"str", "text", "string"}:
        return "text"
    if normalized in {
        "int",
        "float",
        "number",
        "int|float",
        "float|int",
    }:
        return "number"
    if normalized in {"bool", "boolean"}:
        return "boolean"
    if (
        normalized == "list"
        or normalized.startswith("list[")
        or normalized.startswith("typing.list[")
    ):
        return "list"
    if (
        normalized == "dict"
        or normalized.startswith("dict[")
        or normalized.startswith("typing.dict[")
    ):
        return "dict"
    return "unknown"


def _simplify_search_type(type_name: str | None) -> str:
    """Reduce one Python annotation string to the shared matching vocabulary."""
    return {
        "text": "str",
        "number": "number",
        "boolean": "bool",
        "list": "list",
        "dict": "dict",
        "unknown": "unknown",
    }[_type_family(type_name)]


def _normalize_identifier(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _build_llm_matching_prompt(
    *,
    query: ReferenceCodeSearchQuery,
    documents: list[ReferenceCodeSearchDocument],
) -> list[dict[str, str]]:
    content = (
        _LLM_MATCHING_PROMPT
        .replace(
            "{{SEARCH_QUERY_JSON}}",
            json.dumps(query, ensure_ascii=False, indent=2),
        )
        .replace(
            "{{SEARCH_DOCUMENTS_JSON}}",
            json.dumps(documents, ensure_ascii=False, indent=2),
        )
    )
    return [create_prompt_section("user", content)]


def _parse_llm_matching_response(
    *,
    response: str,
    candidate_names: set[str],
) -> str | None:
    if not isinstance(response, str):
        raise ValueError("The LLM matching response must be a JSON string.")
    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        try:
            result = extract_single_json_from_text(response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"The LLM matching response contains invalid JSON: {response!r}"
            ) from exc

    if not isinstance(result, dict) or set(result) != {"function_name"}:
        raise ValueError(
            "The LLM matching response must contain only 'function_name'."
        )

    function_name = result["function_name"]
    if function_name is None:
        return None
    if not isinstance(function_name, str) or function_name not in candidate_names:
        raise ValueError(
            "The LLM matching response selected an unknown function name: "
            f"{function_name!r}."
        )
    return function_name


def _validate_search_query(query: ReferenceCodeSearchQuery) -> None:
    if not isinstance(query, dict) or set(query) != {
        "requested_api_name",
        "task_description",
        "arguments",
        "expected_return",
    }:
        raise ValueError("ReferenceCodeSearchQuery has an invalid structure.")
    if not isinstance(query["requested_api_name"], str) or not query[
        "requested_api_name"
    ].strip():
        raise ValueError("requested_api_name must be a non-empty string.")
    if not isinstance(query["task_description"], str) or not query[
        "task_description"
    ].strip():
        raise ValueError("task_description must be a non-empty string.")
    if not isinstance(query["arguments"], list):
        raise ValueError("arguments must be a list.")

    seen_parameter_names: set[str] = set()
    for argument in query["arguments"]:
        if not isinstance(argument, dict) or set(argument) != {
            "parameter_name",
            "argument_variable_name",
            "argument_description",
            "argument_type",
        }:
            raise ValueError("ReferenceCodeSearchArgument has an invalid structure.")
        for field_name in (
            "parameter_name",
            "argument_variable_name",
            "argument_type",
        ):
            if not isinstance(argument[field_name], str) or not argument[
                field_name
            ].strip():
                raise ValueError(
                    f"ReferenceCodeSearchArgument.{field_name} must be a "
                    "non-empty string."
                )
        if argument["argument_description"] is not None and not isinstance(
            argument["argument_description"], str
        ):
            raise ValueError(
                "ReferenceCodeSearchArgument.argument_description must be "
                "a string or None."
            )
        if argument["parameter_name"] in seen_parameter_names:
            raise ValueError("ReferenceCodeSearchQuery contains duplicate parameters.")
        seen_parameter_names.add(argument["parameter_name"])

    expected_return = query["expected_return"]
    if expected_return is None:
        return
    if not isinstance(expected_return, dict) or set(expected_return) != {
        "variable_name",
        "return_description",
        "return_type",
    }:
        raise ValueError("ReferenceCodeExpectedReturn has an invalid structure.")
    for field_name in ("variable_name", "return_type"):
        if not isinstance(expected_return[field_name], str) or not expected_return[
            field_name
        ].strip():
            raise ValueError(
                f"ReferenceCodeExpectedReturn.{field_name} must be a "
                "non-empty string."
            )
    if expected_return["return_description"] is not None and not isinstance(
        expected_return["return_description"], str
    ):
        raise ValueError(
            "ReferenceCodeExpectedReturn.return_description must be a "
            "string or None."
        )
