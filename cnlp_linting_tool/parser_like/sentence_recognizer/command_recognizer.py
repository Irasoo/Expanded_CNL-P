from altair import value
from stack_data import BlankLines
from streamlit import success

from ...schemas.parser_like import CommandSentence, CNLPSentence
from ...schemas.result import Success, Failure, Result

from typing import Literal, List, Optional, Dict
import re

"""
[ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
"""

# TODO：嵌套问题是一个非常复杂的问题！或许可以从代码静态分析是检查字典定义问题上找到灵感
def recognize_command_sentence(
        belonging: Literal["persona", "constraints", "instruction", "type", "variable"],
        cnlp_sentences: List[dict],
        flow: str,
        flow_condition: str | None = None,
        flow_condition_line: int | None = None,
) -> Dict[str, List[Result]]:
    # 统计一个FLOW内各种 block 计数
    block_counters = {
        "sequential": 0,
        "if": 0,
        "while": 0,
        "for": 0
    }

    current_block = None
    # only main_flow does not have condition
    condition = None
    # only exception_flow has log
    log = None
    log_line = None
    block_begin_match = False

    success_list = []
    error_list = []

    # 这个变量是用来判断BLOCK中有没有COMMAND，理论上来说BLOCK不能没有COMMAND
    block_has_command = False
    # 用来记录每一个BLOCK开始的行数
    block_start_line: int | None = None
    # 用来记录每一个BLOCK_CONDITION的行数, 并不完全等于block_start_line，因为IF_BLOCK中每条分支都有的condition
    block_condition_line: int | None = None

    # 定义匹配 block 开始的模式
    block_patterns = {
        "sequential": re.compile(r"^\s*\[(SEQUENTIAL_BLOCK)\]\s*$"),
        "if": re.compile(r"^\s*\[(IF)\s+(.+?)\]\s*$"),
        "while": re.compile(r"^\s*\[(WHILE)\s+(.+?)\]\s*$"),
        "for": re.compile(r"^\s*\[(FOR)\s+(.+?)\]\s*$")
    }

    command_pattern = re.compile(r"^COMMAND-(\d+)\s+\[(.*)\]$")
    end_pattern = re.compile(r"\[END_([A-Z_]+)]$")
    elif_pattern = re.compile(r"^\s*\[ELSEIF\s+(.+?)\]\s*$")
    else_pattern = re.compile(r"^\s*\[ELSE\]\s*$")

    for sentence in cnlp_sentences:

        line_number = sentence['line_number']
        sentence = sentence['sentence']

        # TODO：检查开头以带来性能提升
        # 检查该语句是否为对某些内容开始定义的语句：例如[IF ...]就是对IF block里面相关内容的定义开始的标识符
        if not sentence.startswith("COMMAND-"):
            for block_type, pattern in block_patterns.items():
                block_match = pattern.match(sentence)
                if block_match:
                    if current_block:
                        error_list.append(
                            Failure(
                                value=sentence,
                                is_fatal=True, # BLOCK之间不允许嵌套
                                start_line=block_start_line,
                                end_line=line_number,
                                error_type="unrecognized_sentence",
                                message=f"The previous BLOCK definition was not properly closed, or the newly defined BLOCK was nested within the previous BLOCK."
                            )
                        )
                    # 每当定义一个新的BLOCK时，需要更新或者重置以下变量
                    block_start_line = line_number
                    block_has_command = False
                    current_block = block_type
                    block_counters[block_type] += 1
                    block_begin_match = True
                    if block_type != "sequential":
                        condition = block_match.group(2)
                        block_condition_line = line_number
                    break  # 一旦匹配成功，就不再尝试其他模式

            if block_begin_match:
                block_begin_match = False
                continue

            # 检查该语句是否为相关的终止语句，如果是，检查终止语句是否匹配
            end_match = end_pattern.match(sentence)
            if end_match:
                end_keyword = end_match.group(1).lower()
                # TODO: 由于其他的BLOCK都是[END_IF]、[END_FOR]、[END_WHILE]结尾，而SEQUENTIAL_BLOCK是以[END_SEQUENTIAL_BLOCK]结尾，这里只能先这样进行处理
                if "sequential" in end_keyword:
                    end_keyword = "sequential"
                if current_block == end_keyword:
                    if not block_has_command:
                        error_list.append(
                            Failure(
                                value=None,
                                is_fatal=True,
                                start_line=block_start_line,
                                end_line=line_number,
                                error_type="",
                                message=f"This is an empty block without command."
                            )
                        )
                    block_start_line = None
                    block_has_command = False
                    current_block = None
                    condition = None
                    continue
                else:
                    error_list.append(
                        Failure(
                            value=None,
                            is_fatal=True,
                            start_line=block_start_line,
                            end_line=line_number,
                            error_type="",
                            message=f"The block definition was not properly closed."
                        )
                    )

            if current_block != "sequential":
                elif_match = elif_pattern.match(sentence)
                if elif_match:
                    condition = elif_match.group(1)
                    block_condition_line = line_number
                    continue
                else_match = else_pattern.match(sentence)
                if else_match:
                    condition = None
                    block_condition_line = None
                    continue

        # 当遇到了一个可能的COMMAND的语句，需要先检查当前是否处于BLOCK的定义中
        if current_block:
            # 如果处于，再初步判断是不是COMMAND类型的语句，注意，仅仅是初步判断，更详细的判断方法再后面
            command_match = command_pattern.match(sentence)
            if command_match:
                # 此时可以判定BLOCK中含有语句
                block_has_command = True
                success_list.append(
                    Success(
                        CNLPSentence(
                            belonging=belonging,
                            line_record={"start_line": line_number, "end_line": line_number},
                            details=CommandSentence(
                                flow=flow if not flow.startswith('main') else 'main_flow',
                                flow_condition=flow_condition,
                                flow_condition_line=flow_condition_line,
                                flow_log=log,
                                flow_log_line=log_line,
                                block=f"{current_block}_block{block_counters[current_block]}",
                                if_condition=condition if current_block == "if" else None,
                                loop_condition=condition if current_block == "while" or current_block == "for" else None,
                                block_condition_line=block_condition_line,
                                order=command_match.group(1),
                                sentence=sentence,
                            )
                        )
                    )
                )
            # 如果初步判断就发现这条语句不符合COMMAND的语法规范
            else:
                error_list.append(
                    Failure(
                        value=sentence,
                        start_line=line_number,
                        end_line=line_number,
                        is_fatal=True, # 任何command的错误可能会影响后续的分析
                        error_type="unrecognized_sentence",
                        message=f"The {sentence} does not match the pattern of COMMAND"
                    )
                )
        # 否则直接报错
        else:
            if sentence.startswith("LOG"):
                if flow.startswith("exception"):
                    # 去掉句子开头的"LOG"字样
                    log = sentence[4:]
                    log_line = line_number
                else:
                    error_list.append(
                        Failure(
                            value=sentence,
                            start_line=line_number,
                            end_line=line_number,
                            is_fatal=False,
                            error_type="unrecognized_sentence",
                            message=f"""'LOG' sentence should be in EXCEPTION_FLOW"""
                        )
                    )
            else:
                error_list.append(
                    Failure(
                        value=sentence,
                        start_line=line_number,
                        end_line=line_number,
                        is_fatal=True,
                        error_type="unrecognized_sentence",
                        message=f"""If the sentence '{sentence}' match the pattern of COMMAND, It should be included in a BLOCK."""
                    )
                )

    if current_block:
        error_list.append(
            Failure(
                value=None,
                is_fatal=False,
                start_line=block_start_line,
                end_line=block_start_line,
                error_type="",
                message=f"The block definition was not properly closed."
            )
        )

    return {"success_list": success_list, "error_list": error_list}
# from ...schemas.parser_like import CommandSentence, CNLPSentence
# from ...schemas.result import Success, Failure, Result
#
# from typing import Literal, List, Optional, Dict
# import re
#
# command_pattern = re.compile(r"^COMMAND-(\d+)\s+\[(.*)\]$")
# end_pattern = re.compile(r"\[END_([A-Z_]+)]$")
#
# def recognize_command_sentence(
#         belonging: Literal["persona", "constraints", "instruction", "type", "variable"],
#         cnlp_sentences: List[dict],
#         flow: str,
#         flow_condition: str | None = None,
# ) -> Dict[str, List[Result]]:
#     # 统计一个FLOW内各种 block 计数
#     block_counters = {
#         "sequential": 0,
#         "if": 0,
#         "while": 0,
#         "for": 0
#     }
#
#     current_block = None
#     condition = None
#     block_begin_match = False
#
#     success_list = []
#     error_list = []
#
#     block_stack = []  # 用于追踪BLOCK的开始以避免嵌套
#
#     # 定义匹配 block 开始的模式
#     block_patterns = {
#         "sequential": re.compile(r"^\s*\[(SEQUENTIAL_BLOCK)\]\s*$"),
#         "if": re.compile(r"^\s*\[(IF)\s+(.+?)\]\s*$"),
#         "while": re.compile(r"^\s*\[(WHILE)\s+(.+?)\]\s*$"),
#         "for": re.compile(r"^\s*\[(FOR)\s+(.+?)\]\s*$")
#     }
#
#     elif_pattern = re.compile(r"^\s*\[ELSEIF\s+(.+?)\]\s*$")
#
#     for sentence in cnlp_sentences:
#         # TODO：检查开头以带来性能提升
#         # 检查该语句是否为对某些内容开始定义的语句：例如[IF ...]就是对IF block里面相关内容的定义开始的标识符
#         if not sentence.startswith("COMMAND-"):
#             for block_type, pattern in block_patterns.items():
#                 block_match = pattern.match(sentence)
#                 if block_match:
#                     if block_stack:
#                         error_list.append(
#                             Failure(
#                                 value=sentence,
#                                 is_fatal=True,
#                                 error_type="nested_block_not_allowed",
#                                 message=f"BLOCK [{sentence}] cannot be nested inside BLOCK [{block_stack[-1]['start']}]"
#                             )
#                         )
#                         continue
#                     current_block = block_type
#                     block_counters[block_type] += 1
#                     block_begin_match = True
#                     if block_type != "sequential":
#                         condition = block_match.group(2)
#                     block_stack.append({
#                         "type": block_type,
#                         "start": sentence,
#                         "counter": block_counters[block_type]
#                     })
#                     break  # 一旦匹配成功，就不再尝试其他模式
#
#             if block_begin_match:
#                 block_begin_match = False
#                 continue
#
#             # 检查该语句是否为相关的终止语句，如果是，检查终止语句是否匹配
#             end_match = end_pattern.match(sentence)
#             if end_match:
#                 end_keyword = end_match.group(1).lower()
#                 if "sequential" in end_keyword:
#                     end_keyword = "sequential"
#                 if block_stack and block_stack[-1]["type"] == end_keyword:
#                     block_stack.pop()
#                     current_block = None
#                     condition = None
#                     continue
#                 else:
#                     error_list.append(
#                         Failure(
#                             value=sentence,
#                             is_fatal=True,
#                             error_type="block_end_mismatch",
#                             message=f"Block ending [{sentence}] does not match any active block"
#                         )
#                     )
#                     continue
#
#             if current_block != "sequential":
#                 elif_match = elif_pattern.match(sentence)
#                 if elif_match:
#                     condition = elif_match.group(1)
#                     continue
#
#         # 如果是一般语句，那么就可能是COMMAND类型的句子，从而用正则表达式进行匹配判断
#         command_match = command_pattern.match(sentence)
#         if command_match:
#             success_list.append(
#                 Success(
#                     CNLPSentence(
#                         belonging=belonging,
#                         details=CommandSentence(
#                             flow=flow if not flow.startswith('main') else 'main_flow',
#                             flow_condition=flow_condition,
#                             block=f"{current_block}_block{block_counters[current_block]}" if current_block else None,
#                             if_condition=condition if current_block == "if" else None,
#                             loop_condition=condition if current_block == "while" or current_block == "for" else None,
#                             order=command_match.group(1),
#                             sentence=sentence,
#                         )
#                     )
#                 )
#             )
#         else:
#             error_list.append(
#                 Failure(
#                     value=sentence,
#                     is_fatal=False,
#                     error_type="unrecognized_sentence",
#                     message=f"The sentence: {sentence} does not match the pattern of COMMAND"
#                 )
#             )
#
#     # 检查是否存在未终止的BLOCK
#     while block_stack:
#         top = block_stack.pop()
#         error_list.append(
#             Failure(
#                 value=top["start"],
#                 is_fatal=True,
#                 error_type="unterminated_block",
#                 message=f"BLOCK [{top['start']}] was not properly closed"
#             )
#         )
#
#     return {"success_list": success_list, "error_list": error_list}
