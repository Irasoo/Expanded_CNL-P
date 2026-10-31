from __future__ import annotations

import re
from dataclasses import dataclass

from ....schema.cnlp_variables import (
    CNLPStructuredValueElement,
    CNLPValueIR,
    CNLPVariableIR,
)
from ....schema.result import Failure, Result, Success
from ..cnlp_types_reconstructor.data_type_parser import (
    DataTypeSyntaxError,
    parse_data_type_prefix,
)


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class VariableSyntaxError(ValueError):
    def __init__(self, message: str, position: int):
        super().__init__(message)
        self.position = position


@dataclass
class _LineCursor:
    text: str
    position: int = 0

    def skip_whitespace(self) -> None:
        while self.position < len(self.text) and self.text[self.position].isspace():
            self.position += 1

    def at_end(self) -> bool:
        self.skip_whitespace()
        return self.position >= len(self.text)

    def peek(self) -> str | None:
        self.skip_whitespace()
        if self.position >= len(self.text):
            return None
        return self.text[self.position]

    def consume(self, expected: str) -> None:
        self.skip_whitespace()
        if not self.text.startswith(expected, self.position):
            actual = self.text[self.position:self.position + 1] or "end of line"
            raise VariableSyntaxError(
                f"Expected '{expected}', but found '{actual}'.",
                self.position,
            )
        self.position += len(expected)

    def parse_word(self, role: str) -> str:
        self.skip_whitespace()
        start = self.position
        delimiters = set("{}[],:=\"")
        while (
            self.position < len(self.text)
            and not self.text[self.position].isspace()
            and self.text[self.position] not in delimiters
        ):
            self.position += 1

        if self.position == start:
            raise VariableSyntaxError(f"Expected {role}.", self.position)

        return self.text[start:self.position]

    def parse_quoted_text(self, role: str) -> str:
        self.skip_whitespace()
        if self.position >= len(self.text) or self.text[self.position] != '"':
            raise VariableSyntaxError(f"Expected {role}.", self.position)

        self.position += 1
        characters: list[str] = []
        escaped = False

        while self.position < len(self.text):
            character = self.text[self.position]
            self.position += 1

            if escaped:
                characters.append(character)
                escaped = False
                continue

            if character == "\\":
                escaped = True
                continue

            if character == '"':
                return "".join(characters)

            characters.append(character)

        raise VariableSyntaxError(f"Missing closing quote for {role}.", self.position)


class _ValueParser:
    def __init__(self, text: str):
        self.cursor = _LineCursor(text=text)

    def parse(self) -> CNLPValueIR:
        next_character = self.cursor.peek()
        if next_character is None:
            raise VariableSyntaxError("Expected default value after '='.", 0)
        if next_character == "[":
            return self._parse_array()
        if next_character == "{":
            return self._parse_structured_value()
        return self._parse_scalar(stop_characters=set())

    def ensure_finished(self) -> None:
        if not self.cursor.at_end():
            raise VariableSyntaxError(
                f"Unexpected content after default value: "
                f"'{self.cursor.text[self.cursor.position:].strip()}'.",
                self.cursor.position,
            )

    def _parse_array(self) -> CNLPValueIR:
        self.cursor.consume("[")
        if self.cursor.peek() == "]":
            self.cursor.consume("]")
            return CNLPValueIR(value_kind="array", value=[])

        elements: list[CNLPValueIR] = []
        while True:
            elements.append(self._parse_nested_value(stop_characters={",", "]"}))
            next_character = self.cursor.peek()
            if next_character == "]":
                self.cursor.consume("]")
                return CNLPValueIR(value_kind="array", value=elements)
            if next_character != ",":
                raise VariableSyntaxError(
                    "Expected ',' or ']' after array element.",
                    self.cursor.position,
                )
            self.cursor.consume(",")
            if self.cursor.peek() == "]":
                raise VariableSyntaxError(
                    "Expected array element after ','.",
                    self.cursor.position,
                )

    def _parse_structured_value(self) -> CNLPValueIR:
        self.cursor.consume("{")
        if self.cursor.peek() == "}":
            self.cursor.consume("}")
            return CNLPValueIR(value_kind="structured", value=[])

        elements: list[CNLPStructuredValueElement] = []
        seen_keys: set[str] = set()
        while True:
            key = self._try_parse_key()
            if key is not None:
                if not _IDENTIFIER_PATTERN.fullmatch(key):
                    raise VariableSyntaxError(
                        f"Invalid structured value key '{key}'.",
                        self.cursor.position,
                    )
                if key in seen_keys:
                    raise VariableSyntaxError(
                        f"Duplicate structured value key '{key}'.",
                        self.cursor.position,
                    )
                seen_keys.add(key)
            value = self._parse_nested_value(stop_characters={",", "}"})
            elements.append(CNLPStructuredValueElement(key=key, value=value))

            next_character = self.cursor.peek()
            if next_character == "}":
                self.cursor.consume("}")
                return CNLPValueIR(value_kind="structured", value=elements)
            if next_character != ",":
                raise VariableSyntaxError(
                    "Expected ',' or '}' after structured value element.",
                    self.cursor.position,
                )
            self.cursor.consume(",")
            if self.cursor.peek() == "}":
                raise VariableSyntaxError(
                    "Expected structured value element after ','.",
                    self.cursor.position,
                )

    def _try_parse_key(self) -> str | None:
        original_position = self.cursor.position
        try:
            candidate = self.cursor.parse_word("structured value key")
        except VariableSyntaxError:
            self.cursor.position = original_position
            return None

        if self.cursor.peek() != ":":
            self.cursor.position = original_position
            return None

        self.cursor.consume(":")
        return candidate

    def _parse_nested_value(self, stop_characters: set[str]) -> CNLPValueIR:
        next_character = self.cursor.peek()
        if next_character is None or next_character in stop_characters:
            raise VariableSyntaxError("Expected value.", self.cursor.position)
        if next_character == "[":
            return self._parse_array()
        if next_character == "{":
            return self._parse_structured_value()
        return self._parse_scalar(stop_characters=stop_characters)

    def _parse_scalar(self, stop_characters: set[str]) -> CNLPValueIR:
        self.cursor.skip_whitespace()
        start = self.cursor.position
        in_quote = False
        escaped = False

        while self.cursor.position < len(self.cursor.text):
            if not in_quote and self.cursor.text.startswith(
                "<REF>", self.cursor.position
            ):
                reference_end = self.cursor.text.find(
                    "</REF>", self.cursor.position + len("<REF>")
                )
                if reference_end == -1:
                    raise VariableSyntaxError(
                        "Missing '</REF>' in default value.",
                        self.cursor.position,
                    )
                self.cursor.position = reference_end + len("</REF>")
                continue

            character = self.cursor.text[self.cursor.position]
            if escaped:
                escaped = False
                self.cursor.position += 1
                continue
            if character == "\\" and in_quote:
                escaped = True
                self.cursor.position += 1
                continue
            if character == '"':
                in_quote = not in_quote
                self.cursor.position += 1
                continue
            if not in_quote and character in stop_characters:
                break
            self.cursor.position += 1

        if in_quote:
            raise VariableSyntaxError(
                "Missing closing quote in default value.",
                self.cursor.position,
            )

        raw_value = self.cursor.text[start:self.cursor.position].strip()
        if not raw_value:
            raise VariableSyntaxError("Expected value.", start)
        _validate_reference_markers(raw_value, start)

        return CNLPValueIR(
            value_kind="scalar",
            value=_normalize_scalar(raw_value),
        )


def _normalize_scalar(raw_value: str) -> str | int | float | bool:
    if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] == '"':
        cursor = _LineCursor(text=raw_value)
        value = cursor.parse_quoted_text("quoted default value")
        if cursor.at_end():
            return value

    if raw_value.lower() == "true":
        return True
    if raw_value.lower() == "false":
        return False
    if re.fullmatch(r"[+-]?\d+", raw_value):
        return int(raw_value)
    if re.fullmatch(
        r"[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?",
        raw_value,
    ):
        return float(raw_value)
    return raw_value


def _validate_reference_markers(text: str, offset: int = 0) -> None:
    position = 0
    reference_open = False
    reference_content_start = 0

    while position < len(text):
        if text.startswith("<REF>", position):
            if reference_open:
                raise VariableSyntaxError(
                    "Nested '<REF>' is not allowed.",
                    offset + position,
                )
            reference_open = True
            position += len("<REF>")
            reference_content_start = position
            continue
        if text.startswith("</REF>", position):
            if not reference_open:
                raise VariableSyntaxError(
                    "Unexpected '</REF>'.",
                    offset + position,
                )
            reference_name = text[reference_content_start:position].strip()
            if not reference_name:
                raise VariableSyntaxError(
                    "Reference name cannot be empty.",
                    offset + reference_content_start,
                )
            if any(character.isspace() for character in reference_name):
                raise VariableSyntaxError(
                    "Reference name cannot contain whitespace.",
                    offset + reference_content_start,
                )
            reference_open = False
            position += len("</REF>")
            continue
        position += 1

    if reference_open:
        raise VariableSyntaxError(
            "Missing '</REF>'.",
            offset + len(text),
        )


class CNLPVariableParser:
    @staticmethod
    def parse_line(sentence: str, line_number: int) -> Result[CNLPVariableIR]:
        line = sentence.strip()
        if not line:
            return Failure(
                value=sentence,
                is_fatal=False,
                error_type="variable_definition_error",
                message="Variable declaration cannot be empty.",
                start_line=line_number,
                end_line=line_number,
            )

        try:
            cursor = _LineCursor(text=line)
            description = None
            if cursor.peek() == '"':
                description = cursor.parse_quoted_text("variable description")
                _validate_reference_markers(description)

            variable_name = cursor.parse_word("variable name")
            if not _IDENTIFIER_PATTERN.fullmatch(variable_name):
                raise VariableSyntaxError(
                    f"Invalid variable name '{variable_name}'.",
                    cursor.position - len(variable_name),
                )
            cursor.consume(":")

            type_and_default = cursor.text[cursor.position:]
            data_type, consumed = parse_data_type_prefix(type_and_default)
            remainder = type_and_default[consumed:].strip()

            default_value = None
            if remainder:
                if not remainder.startswith("="):
                    raise VariableSyntaxError(
                        f"Expected '=' before default value, but found "
                        f"'{remainder}'.",
                        cursor.position + consumed,
                    )
                default_text = remainder[1:].strip()
                value_parser = _ValueParser(default_text)
                default_value = value_parser.parse()
                value_parser.ensure_finished()

            return Success(
                CNLPVariableIR(
                    variable_name=variable_name,
                    description=description,
                    data_type=data_type,
                    default_value=default_value,
                    line_record={
                        "start_line": line_number,
                        "end_line": line_number,
                    },
                )
            )
        except (VariableSyntaxError, DataTypeSyntaxError) as error:
            return Failure(
                value=sentence,
                is_fatal=False,
                error_type="variable_definition_error",
                message=str(error),
                start_line=line_number,
                end_line=line_number,
            )
