# import re
#
# multi_line_text = """{
# Processing Logic Error,
# inputs: {
# order_id: 98765,
# user_id: 12345,
# order_details: { items: ["Laptop", "Mouse"], total_price: 1200 }
# },
# defect-outputs: {
# confirmation_message: "Order has been placed successfully.",
# shipping_status: "Pending"
# },
# execution-path: COMMAND-1, COMMAND-3, COMMAND-7,
# defect-explanation: "Order confirmation message was sent, but the order was not actually recorded in the database."
# }"""
#
# # 改进匹配方式，确保 `{}` 结构完整
# inputs_match = re.search(r"inputs:\s*(\{(?:[^{}]*|\{[^{}]*\})*\})", multi_line_text, re.DOTALL)
# inputs_content = inputs_match.group(1).strip() if inputs_match else None
#
# # 提取 defect-outputs
# outputs_match = re.search(r"defect-outputs:\s*(\{(?:[^{}]*|\{[^{}]*\})*\})", multi_line_text, re.DOTALL)
# outputs_content = outputs_match.group(1).strip() if outputs_match else None
#
# # 提取 execution-path
# execution_match = re.search(r"execution-path:\s*([^,\n]+(?:,\s*[^,\n]+)*)", multi_line_text)
# execution_content = execution_match.group(1).strip() if execution_match else None
#
# # 提取 defect-explanation
# explanation_match = re.search('defect-explanation:\s*"([^"]+)"', multi_line_text)
# explanation_content = explanation_match.group(1) if explanation_match else None
#
# # 输出结果
# print("🟢 Inputs:", inputs_content)
# print("🟢 Defect Outputs:", outputs_content)
# print("🟢 Execution Path:", execution_content)
# print("🟢 Defect Explanation:", explanation_content)
import re
from typing import Literal, List, Dict

from ...schemas.result import Result, Success, Failure
from ...schemas.parser_like import CNLPSentence, ExampleSentence


example_start_patterns = {
    "expect": re.compile(r"^\s*<EXPECTED-WORKER-BEHAVIOR>"),
    "defect": re.compile(r"^\s*<DEFECT-WORKER-BEHAVIOR>")
}

example_end_patterns = {
    "expect": re.compile(r".*</EXPECTED-WORKER-BEHAVIOR>\s*$"),
    "defect": re.compile(r".*</DEFECT-WORKER-BEHAVIOR>\s*$")
}


def recognize_example_sentence(
        belonging: Literal["persona", "constraints", "instruction", "type", "variable"],
        cnlp_sentences: List[dict],
        *args,
        **kwargs
) -> Dict[str, List[Result]]:

    example_begin_match = False
    example_end_match = False

    current_example_type = None
    current_example_content = []
    example_counters = {
        "expect": 0,
        "defect": 0,
    }

    success_list = []
    error_list = []

    # TODO: 思考...example_end_line是否必要...
    # 由于EXAMPLES中的每一个例子在实际书写时非常可能跨越多行，所以需要记录下原文中起始行和终止行
    example_start_line = 0
    example_end_line = 0

    for sentence in cnlp_sentences:

        line_number = sentence["line_number"]
        sentence = sentence["sentence"]

        # TODO：检测是否以"<"开头，如果不是以<开头，则跳过...下同
        for start_example_type, pattern in example_start_patterns.items():
            if pattern.match(sentence):
                # 原理其实和worker那一部分的差不多
                if current_example_type:
                    error_list.append(
                        Failure(
                            value=None,
                            is_fatal=False,
                            error_type="identifier_error",
                            message=f"""The definition of the previous "{current_example_type} example behavior" has not been completed yet, and a new "{start_example_type} example behavior" is currently being defined.""",
                            start_line=example_start_line,
                            end_line=line_number-1, # TODO: ...
                        )
                    )
                    # 由于新换了一个example，缓冲区的内容需要清空
                    current_example_content = []
                example_start_line = line_number
                current_example_type = start_example_type
                example_counters[current_example_type] += 1
                current_example_content.append(sentence)
                example_begin_match = True
                break

        if example_begin_match:
            example_begin_match = False
            continue

        for end_example_type, pattern in example_end_patterns.items():
            if pattern.match(sentence):
                # 如果当前正在识别某一个example
                if current_example_type:
                    # 检查example类型是否一致
                    # 一致则终止该Example的定义
                    if current_example_type == end_example_type:
                        current_example_content.append(sentence)
                        success_list.append(
                            Success(
                                CNLPSentence(
                                    belonging=belonging,
                                    line_record={'start_line': example_start_line, 'end_line': line_number},
                                    details=ExampleSentence(
                                        example_type=current_example_type,
                                        order=example_counters[current_example_type], # TODO: 为什么会警告？
                                        sentence="".join(current_example_content)
                                    )
                                )
                            )
                        )
                        # 正常关闭进行重置
                        # TODO: 思考此时example_start_line的计数应该归零嘛？
                        example_start_line = None
                        current_example_type = None
                        current_example_content = []
                        example_end_match = True
                        break
                    # 如果是终止模式但是类型不匹配
                    else:
                        error_list.append(
                            Failure(
                                value=sentence,
                                is_fatal=False,
                                error_type="identifier_error",
                                message=f"The current type of 'example behavior' is '{current_example_type}', but it now ends with '{sentence}'",
                                start_line = example_start_line,
                                end_line = line_number,  # TODO: ...
                            )
                        )
                        break

        if example_end_match:
            example_end_match = False
            continue

        if current_example_type:
            current_example_content.append(sentence)
        else:
            error_list.append(
                Failure(
                    value=sentence,
                    is_fatal=False,
                    error_type="unrecognized_sentence",
                    message="The current sentence is neither enclosed between '<EXPECTED-WORKER-BEHAVIOR>' and '</EXPECTED-WORKER-BEHAVIOR>', nor enclosed between '<DEFECT-WORKER-BEHAVIOR>' and '</DEFECT-WORKER-BEHAVIOR>'",
                    start_line=line_number,
                    end_line=line_number,  # TODO: ...
                )
            )

    return {"success_list": success_list, "error_list": error_list}













