from typing import TypedDict, NotRequired, Literal


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
    flow_condition: NotRequired[str] # condition in alternative flow
    flow_condition_line: NotRequired[int]
    flow_log: NotRequired[str]
    flow_log_line: NotRequired[int]
    block: str
    if_condition: NotRequired[str] # branch condition in if block
    loop_condition: NotRequired[str] # condition in loop block
    block_condition_line: int
    order: str # 重复的部分需要编号
    sentence: str


# 一种在句子重构期间传递中间值的临时CNL-P句子结构
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
    belonging: Literal["persona", "constraints", "instruction", "type", "variable", "concepts", "audience"]
    line_record: LineRecord
    details: AspectSentence | ExampleSentence | CommandSentence | IOSentence | IntermediateSentence


"""
{
    "belonging": "instruction",
    "line_record": {...},
    flow: "alternative_flow",
    flow_condition: ...,
    block: "if_block",
    block_condition: ...,
    sentence: "COMMAND-15 [COMMAND ...]"
}
"""


"""
{
    "belonging": "instruction",
    "line_record": {...},
    flow: "alternative_flow",
    flow_condition: ...,
    block: "if_block",
    block_condition: ...,
    json_representation: {"command15": {"type": "general_command", "description_with_reference": ..., "result": ...}}
}
"""

"""
{
    ...,
    "worker": {
        ...,
        "alternative_flow2": {
            ...
            "if_block1": {
                ...,
                "else_branch": {
                    ...,
                    "command15": {
                        "type": "general_command", 
                        "description_with_reference": ..., 
                        "result": ...
                    },
                    ...,
                },
                ...,
            },
            ...,
        },
        ...,
    },
    ...,
}
"""