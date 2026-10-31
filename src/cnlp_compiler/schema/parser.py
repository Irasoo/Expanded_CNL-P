from typing import Literal, NotRequired, TypedDict


class IOSentence(TypedDict):
    IO: Literal["input", "output"]
    is_required: bool
    sentence: str


class ExampleSentence(TypedDict):
    example_type: Literal["expect", "defect"]
    order: int
    sentence: str


class CommandSentence(TypedDict):
    flow: str
    flow_condition: NotRequired[str]
    flow_condition_line: NotRequired[int]
    flow_log: NotRequired[str]
    flow_log_line: NotRequired[int]
    block: str
    if_condition: NotRequired[str]
    loop_condition: NotRequired[str]
    block_condition_line: int
    order: str
    sentence: str


class IntermediateSentence(TypedDict):
    sentence: str


class AspectSentence(TypedDict):
    aspect_name: str
    sentence: str


class TypeSentence(TypedDict):
    description: str
    sentence: str


class LineRecord(TypedDict):
    start_line: int
    end_line: int


class CNLPSentence(TypedDict):
    belonging: Literal[
        "persona",
        "constraints",
        "instruction",
        "type",
        "variable",
        "concepts",
        "audience",
    ]
    line_record: LineRecord
    details: (
        AspectSentence
        | ExampleSentence
        | CommandSentence
        | IOSentence
        | IntermediateSentence
        | TypeSentence
    )
