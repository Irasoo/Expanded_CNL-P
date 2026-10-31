from __future__ import annotations

from dataclasses import dataclass
import re

from ....schema.cnlp_types import (
    CNLPArrayType,
    CNLPDataType,
    CNLPDeclaredType,
    CNLPEnumType,
    CNLPSimpleType,
    FieldOfCNLPStructType,
)


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DataTypeSyntaxError(ValueError):
    def __init__(self, message: str, position: int):
        super().__init__(message)
        self.position = position


@dataclass
class _Cursor:
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
            raise DataTypeSyntaxError(
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
            raise DataTypeSyntaxError(f"Expected {role}.", self.position)

        return self.text[start:self.position]

    def parse_quoted_text(self, role: str) -> str:
        self.skip_whitespace()
        if self.position >= len(self.text) or self.text[self.position] != '"':
            raise DataTypeSyntaxError(f"Expected {role}.", self.position)

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

        raise DataTypeSyntaxError(f"Missing closing quote for {role}.", self.position)


class _DataTypeParser:
    def __init__(self, text: str):
        self.cursor = _Cursor(text=text)

    def parse(self) -> CNLPDataType:
        next_character = self.cursor.peek()
        if next_character is None:
            raise DataTypeSyntaxError("Expected data type.", self.cursor.position)
        if next_character == "{":
            return self._parse_structured_type()
        if next_character == "[":
            return self._parse_enum_type()

        type_name = self.cursor.parse_word("data type")
        if not _IDENTIFIER_PATTERN.fullmatch(type_name):
            raise DataTypeSyntaxError(
                f"Invalid data type name '{type_name}'.",
                self.cursor.position - len(type_name),
            )
        if type_name.lower() == "list":
            self.cursor.consume("[")
            element_type = self.parse()
            self.cursor.consume("]")

            if (
                isinstance(element_type, dict)
                and "type_of_list_element" in element_type
                and "nesting_level" in element_type
            ):
                return CNLPArrayType(
                    type_of_list_element=element_type["type_of_list_element"],
                    nesting_level=element_type["nesting_level"] + 1,
                )

            return CNLPArrayType(
                type_of_list_element=element_type,
                nesting_level=1,
            )

        if type_name.lower() in {"text", "number", "boolean"}:
            return CNLPSimpleType(simple_type=type_name.lower())

        return CNLPDeclaredType(declared_type_name=type_name)

    def _parse_enum_type(self) -> CNLPEnumType:
        self.cursor.consume("[")
        if self.cursor.peek() == "]":
            raise DataTypeSyntaxError(
                "Enum type must contain at least one element.",
                self.cursor.position,
            )

        elements: list[str] = []
        seen_elements: set[str] = set()
        while True:
            element = self.cursor.parse_word("enum element")
            if not _IDENTIFIER_PATTERN.fullmatch(element):
                raise DataTypeSyntaxError(
                    f"Invalid enum element '{element}'.",
                    self.cursor.position - len(element),
                )
            if element in seen_elements:
                raise DataTypeSyntaxError(
                    f"Duplicate enum element '{element}'.",
                    self.cursor.position - len(element),
                )
            seen_elements.add(element)
            elements.append(element)
            next_character = self.cursor.peek()
            if next_character == "]":
                self.cursor.consume("]")
                return CNLPEnumType(enum_elements=elements)
            if next_character != ",":
                raise DataTypeSyntaxError(
                    "Expected ',' or ']' after enum element.",
                    self.cursor.position,
                )
            self.cursor.consume(",")
            if self.cursor.peek() == "]":
                raise DataTypeSyntaxError(
                    "Expected enum element after ','.",
                    self.cursor.position,
                )

    def _parse_structured_type(self) -> list[FieldOfCNLPStructType]:
        self.cursor.consume("{")
        if self.cursor.peek() == "}":
            self.cursor.consume("}")
            return []

        fields: list[FieldOfCNLPStructType] = []
        seen_field_names: set[str] = set()
        while True:
            field_comment = None
            if self.cursor.peek() == '"':
                field_comment = self.cursor.parse_quoted_text("field description")

            first_word = self.cursor.parse_word("field name")
            is_optional = first_word.upper() == "OPTIONAL"
            if is_optional:
                if field_comment is None and self.cursor.peek() == '"':
                    field_comment = self.cursor.parse_quoted_text(
                        "field description"
                    )
                field_name = self.cursor.parse_word("field name")
            else:
                field_name = first_word

            if not _IDENTIFIER_PATTERN.fullmatch(field_name):
                raise DataTypeSyntaxError(
                    f"Invalid structured type field name '{field_name}'.",
                    self.cursor.position - len(field_name),
                )
            if field_name in seen_field_names:
                raise DataTypeSyntaxError(
                    f"Duplicate structured type field '{field_name}'.",
                    self.cursor.position - len(field_name),
                )
            seen_field_names.add(field_name)

            self.cursor.consume(":")
            field_content = self.parse()
            fields.append(
                FieldOfCNLPStructType(
                    field_name=field_name,
                    field_comment=field_comment,
                    is_optional=is_optional,
                    field_content=field_content,
                )
            )

            next_character = self.cursor.peek()
            if next_character == "}":
                self.cursor.consume("}")
                return fields
            if next_character != ",":
                raise DataTypeSyntaxError(
                    "Expected ',' or '}' after structured type field.",
                    self.cursor.position,
                )
            self.cursor.consume(",")
            if self.cursor.peek() == "}":
                raise DataTypeSyntaxError(
                    "Expected structured type field after ','.",
                    self.cursor.position,
                )


def parse_data_type_prefix(text: str) -> tuple[CNLPDataType, int]:
    parser = _DataTypeParser(text)
    data_type = parser.parse()
    parser.cursor.skip_whitespace()
    return data_type, parser.cursor.position


def parse_data_type(text: str) -> CNLPDataType:
    data_type, consumed = parse_data_type_prefix(text)
    if text[consumed:].strip():
        raise DataTypeSyntaxError(
            f"Unexpected content after data type: '{text[consumed:].strip()}'.",
            consumed,
        )
    return data_type
