from __future__ import annotations

import builtins
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from typing_extensions import is_typeddict

from .schema import BooleanResponse, HistorySection, ModelConfig

if TYPE_CHECKING:
    from .model import AgentState


def display(content: str) -> None:
    """Send content to the user."""
    print(content)


def input() -> str:
    """Receive the user's raw input without sending any content."""
    return builtins.input()


def python_schema_to_json_schema(
    python_schema: Any,
) -> dict[str, Any]:
    """Convert a Python type into a strict structured-output schema."""
    source_schema = _create_json_schema(python_schema)
    return _make_strict_json_schema(
        deepcopy(source_schema),
    )


def _create_json_schema(
    python_schema: Any,
) -> dict[str, Any]:
    """Return Pydantic's source schema before strict normalization."""
    try:
        from pydantic import TypeAdapter
    except ImportError as exc:
        raise RuntimeError(
            "Schema conversion requires the 'pydantic' package."
        ) from exc

    json_schema = TypeAdapter(python_schema).json_schema()
    if not isinstance(json_schema, dict):
        raise TypeError("Pydantic returned an invalid JSON Schema.")
    return json_schema


def _make_strict_json_schema(
    json_schema: dict[str, Any],
) -> dict[str, Any]:
    """Close every object and make optional properties nullable."""
    for definitions_key in ("$defs", "definitions"):
        definitions = json_schema.get(definitions_key)
        if isinstance(definitions, dict):
            for definition_name, definition_schema in definitions.items():
                if not isinstance(definition_schema, dict):
                    raise TypeError(
                        "JSON Schema definition must be an object: "
                        f"{definition_name!r}."
                    )
                definitions[definition_name] = _make_strict_json_schema(
                    definition_schema
                )

    properties = json_schema.get("properties")
    if isinstance(properties, dict):
        original_required = json_schema.get("required", [])
        if not isinstance(original_required, list):
            raise TypeError("JSON Schema required must be an array.")
        required_names = {
            name for name in original_required if isinstance(name, str)
        }

        strict_properties: dict[str, Any] = {}
        for property_name, property_schema in properties.items():
            if not isinstance(property_schema, dict):
                raise TypeError(
                    "JSON Schema property must be an object: "
                    f"{property_name!r}."
                )
            strict_property_schema = _make_strict_json_schema(
                property_schema
            )
            if property_name not in required_names:
                strict_property_schema = _allow_json_null(
                    strict_property_schema
                )
            strict_properties[property_name] = strict_property_schema

        json_schema["properties"] = strict_properties
        json_schema["required"] = list(strict_properties)
        json_schema["additionalProperties"] = False
    elif json_schema.get("type") == "object":
        json_schema.setdefault("additionalProperties", False)

    items = json_schema.get("items")
    if isinstance(items, dict):
        json_schema["items"] = _make_strict_json_schema(items)

    for union_key in ("anyOf", "oneOf", "allOf"):
        variants = json_schema.get(union_key)
        if isinstance(variants, list):
            json_schema[union_key] = [
                _make_strict_json_schema(variant)
                if isinstance(variant, dict)
                else variant
                for variant in variants
            ]

    return json_schema


def _allow_json_null(
    json_schema: dict[str, Any],
) -> dict[str, Any]:
    if _json_schema_allows_null(json_schema):
        return json_schema
    return {
        "anyOf": [
            json_schema,
            {"type": "null"},
        ]
    }


def _json_schema_allows_null(
    json_schema: dict[str, Any],
) -> bool:
    schema_type = json_schema.get("type")
    if schema_type == "null":
        return True
    if isinstance(schema_type, list) and "null" in schema_type:
        return True
    enum_values = json_schema.get("enum")
    if isinstance(enum_values, list) and None in enum_values:
        return True
    return any(
        isinstance(variant, dict)
        and _json_schema_allows_null(variant)
        for union_key in ("anyOf", "oneOf")
        for variant in (
            json_schema.get(union_key)
            if isinstance(json_schema.get(union_key), list)
            else []
        )
    )


def _remove_optional_null_values(
    value: Any,
    source_schema: dict[str, Any],
) -> Any:
    """Turn strict-output nulls back into omitted TypedDict fields."""
    return _normalize_schema_value(
        value=value,
        schema=source_schema,
        root_schema=source_schema,
    )


def _normalize_schema_value(
    *,
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
) -> Any:
    resolved_schema = _resolve_local_schema_reference(
        schema=schema,
        root_schema=root_schema,
    )

    if value is None:
        return None

    union_variants = resolved_schema.get("anyOf")
    if isinstance(union_variants, list):
        selected_variant = next(
            (
                variant
                for variant in union_variants
                if isinstance(variant, dict)
                and variant.get("type") != "null"
            ),
            None,
        )
        if selected_variant is not None:
            return _normalize_schema_value(
                value=value,
                schema=selected_variant,
                root_schema=root_schema,
            )

    properties = resolved_schema.get("properties")
    if isinstance(value, dict) and isinstance(properties, dict):
        required = resolved_schema.get("required", [])
        required_names = {
            name for name in required if isinstance(name, str)
        }
        normalized: dict[str, Any] = {}
        for property_name, property_value in value.items():
            property_schema = properties.get(property_name)
            if not isinstance(property_schema, dict):
                normalized[property_name] = property_value
                continue
            if (
                property_name not in required_names
                and property_value is None
            ):
                continue
            normalized[property_name] = _normalize_schema_value(
                value=property_value,
                schema=property_schema,
                root_schema=root_schema,
            )
        return normalized

    items = resolved_schema.get("items")
    if isinstance(value, list) and isinstance(items, dict):
        return [
            _normalize_schema_value(
                value=item,
                schema=items,
                root_schema=root_schema,
            )
            for item in value
        ]

    return value


def _resolve_local_schema_reference(
    *,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
) -> dict[str, Any]:
    reference = schema.get("$ref")
    if not isinstance(reference, str) or not reference.startswith("#/"):
        return schema

    resolved: Any = root_schema
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(resolved, dict) or part not in resolved:
            raise ValueError(
                f"JSON Schema reference cannot be resolved: {reference!r}."
            )
        resolved = resolved[part]
    if not isinstance(resolved, dict):
        raise TypeError(
            f"JSON Schema reference is not an object: {reference!r}."
        )
    return resolved


def validate_python_value(
    value: Any,
    python_schema: Any,
) -> Any:
    """Validate without silently coercing a value to another basic type."""
    try:
        from pydantic import TypeAdapter, ValidationError
    except ImportError as exc:
        raise RuntimeError(
            "Value validation requires the 'pydantic' package."
        ) from exc

    try:
        return TypeAdapter(python_schema).validate_python(
            value,
            strict=True,
        )
    except ValidationError as exc:
        raise TypeError(
            f"Value does not match {python_schema!r}: {exc}"
        ) from exc


def json_text(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        default=str,
        indent=2,
    )


def _build_model_input(
    history: Sequence[HistorySection],
    *,
    current_instruction: str,
) -> list[dict[str, str]]:
    """Combine prior Command History with the current internal request."""
    messages = [
        {
            "role": section["role"],
            "content": section["content"],
        }
        for section in history
    ]

    normalized_instruction = current_instruction.strip()
    if normalized_instruction:
        messages.append(
            {
                "role": "user",
                "content": normalized_instruction,
            }
        )
    return messages


class OpenAIClient:
    """
    OpenAI client used by generated Agent code.

    Dispatch rules:
    - complete_call_api(prompt): execute a reference function's stateless LLM call.
    - return_bool=True: return bool.
    - written_variable names a TypedDict variable: return validated dict.
    - otherwise: return the model's original string.
    """

    def __init__(self, config: ModelConfig) -> None:
        self.config = dict(config)
        self._client: Any | None = None

    def complete(
        self,
        *,
        state: AgentState,
        current_instruction: str,
        written_variable: str | None = None,
        return_bool: bool = False,
    ) -> str | dict[str, Any] | bool:
        if return_bool and written_variable is not None:
            raise ValueError(
                "written_variable and return_bool cannot be used together."
            )

        messages = _build_model_input(
            state.history,
            current_instruction=current_instruction,
        )

        if return_bool:
            return self._complete_bool(messages)

        if written_variable is not None:
            variable_type = state.get_variable_type(written_variable)
            if is_typeddict(variable_type):
                return self._complete_typed_dict(
                    messages=messages,
                    variable_type=variable_type,
                    schema_name=written_variable,
                )

        return self._complete_string(messages)

    def complete_call_api(self, prompt: str) -> str:
        """Execute an LLM call originating from Call API reference logic.

        Unlike ``complete()``, this interface does not read Agent State or
        History. The supplied prompt is sent as the complete current request.
        """

        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Call API prompt cannot be empty.")
        response = self._get_client().responses.create(
            model=self.config["model_name"],
            input=normalized_prompt,
        )
        output_text = str(response.output_text).strip()
        if not output_text:
            raise RuntimeError("The model returned an empty response.")
        return output_text

    def _complete_string(
        self,
        messages: Sequence[Mapping[str, str]],
    ) -> str:
        response = self._create_response(messages=messages)
        output_text = str(response.output_text).strip()
        if not output_text:
            raise RuntimeError("The model returned an empty response.")
        return output_text

    def _complete_typed_dict(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        variable_type: Any,
        schema_name: str,
    ) -> dict[str, Any]:
        source_schema = _create_json_schema(variable_type)
        json_schema = _make_strict_json_schema(
            deepcopy(source_schema),
        )
        response = self._create_response(
            messages=messages,
            schema_name=schema_name,
            json_schema=json_schema,
        )
        parsed_value = _remove_optional_null_values(
            self._parse_json_response(response),
            source_schema,
        )
        validated_value = validate_python_value(
            parsed_value,
            variable_type,
        )
        if not isinstance(validated_value, dict):
            raise TypeError(
                "The validated TypedDict response is not an object."
            )
        return validated_value

    def _complete_bool(
        self,
        messages: Sequence[Mapping[str, str]],
    ) -> bool:
        response = self._create_response(
            messages=messages,
            schema_name="boolean_response",
            json_schema=python_schema_to_json_schema(BooleanResponse),
        )
        parsed_value = self._parse_json_response(response)
        validated_value = validate_python_value(
            parsed_value,
            BooleanResponse,
        )
        return validated_value["result"]

    @staticmethod
    def _parse_json_response(response: Any) -> dict[str, Any]:
        output_text = str(response.output_text).strip()
        if not output_text:
            raise RuntimeError(
                "The model returned an empty structured response."
            )

        try:
            parsed_value = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "The model returned invalid JSON."
            ) from exc
        if not isinstance(parsed_value, dict):
            raise TypeError(
                "The structured response is not a JSON object."
            )
        return parsed_value

    def _create_response(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        schema_name: str | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> Any:
        request: dict[str, Any] = {
            "model": self.config["model_name"],
            "input": [
                {
                    "role": message["role"],
                    "content": message["content"],
                }
                for message in messages
            ],
        }

        if json_schema is not None:
            if not schema_name or not schema_name.strip():
                raise ValueError(
                    "schema_name is required for a structured response."
                )
            request["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": json_schema,
                    "strict": True,
                }
            }

        return self._get_client().responses.create(**request)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Model calls require the 'openai' package."
            ) from exc

        options: dict[str, Any] = {
            "api_key": self.config["api_key"],
            "timeout": 60.0,
            "max_retries": 2,
        }
        base_url = self.config.get("base_url")
        if base_url:
            options["base_url"] = base_url

        self._client = OpenAI(**options)
        return self._client
