from typing import Literal, TypedDict

from .cnlp_types import CNLPDataType
from .parser import LineRecord


class CNLPValueIR(TypedDict):
    value_kind: Literal["scalar", "array", "structured"]
    value: object


class CNLPStructuredValueElement(TypedDict):
    key: str | None
    value: CNLPValueIR


class CNLPVariableIR(TypedDict):
    variable_name: str
    description: str | None
    data_type: CNLPDataType
    default_value: CNLPValueIR | None
    line_record: LineRecord
