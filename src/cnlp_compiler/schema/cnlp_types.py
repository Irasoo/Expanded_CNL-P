from enum import Enum
from typing import TypeAlias, TypedDict


class TokenTypeOfCNLPTypes(str, Enum):
    EQUAL = "equal"
    LBRACE = "left_brace"
    RBRACE = "right_brace"
    LBRACKET = "left_bracket"
    RBRACKET = "right_bracket"
    COMMA = "comma"
    COLON = "colon"
    OPTIONAL = "optional"
    LIST = "list"
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    WORD = "word"
    COMMENT = "comment"


class CNLPTypeToken(TypedDict):
    token_value: str
    token_type: TokenTypeOfCNLPTypes
    start_line: int
    end_line: int


class CNLPSimpleType(TypedDict):
    simple_type: str


class CNLPDeclaredType(TypedDict):
    declared_type_name: str


class CNLPArrayType(TypedDict):
    type_of_list_element: "CNLPDataType"
    nesting_level: int


class CNLPEnumType(TypedDict):
    enum_elements: list[str]


class FieldOfCNLPStructType(TypedDict):
    field_name: str
    field_comment: str | None
    is_optional: bool
    field_content: "CNLPDataType"


CNLPDataType: TypeAlias = (
    CNLPSimpleType
    | CNLPDeclaredType
    | CNLPArrayType
    | CNLPEnumType
    | list[FieldOfCNLPStructType]
)


class CNLPTypeIR(TypedDict):
    type_name: str
    type_comment: str | None
    type_content: CNLPDataType
