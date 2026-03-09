from ....schemas.result import Failure, Success, Result
from ....schemas.parser_like import CNLPSentence

import re
import json
from dataclasses import dataclass
from typing_extensions import Generic, TypeAlias, TypeVar, Literal, Optional
from typing import TypedDict, NotRequired, Any, Dict, List


def reconstruct_reference(cnlp_sentence: CNLPSentence) -> Result:
    sentence = cnlp_sentence['details']['sentence'].strip()

    if not sentence.startswith("<REF>") or not sentence.endswith("</REF>"):
        return Failure(
            value=cnlp_sentence['details']['sentence'],
            is_fatal=True if cnlp_sentence['belonging'] == "instruction" else False,
            error_type="unrecognized_sentence",
            message="Missing <REF> or </REF> markers"
        )

    inner = sentence[len("<REF>") : -len("</REF>")].strip()

    if not inner:
        return Failure(
            value=cnlp_sentence['details']['sentence'],
            is_fatal=True if cnlp_sentence['belonging'] == "instruction" else False,
            error_type="unrecognized_sentence",
            message="Empty content inside <REF>...</REF>"
        )

    parts = inner.split()

    if not parts:
        return Failure(
            value=cnlp_sentence['details']['sentence'],
            is_fatal=True if cnlp_sentence['belonging'] == "instruction" else False,
            error_type="unrecognized_sentence",
            message="No variable name found inside <REF>...</REF>"
        )

    if len(parts) > 2:
        return Failure(
            value=cnlp_sentence['details']['sentence'],
            is_fatal=True if cnlp_sentence['belonging'] == "instruction" else False,
            error_type="unrecognized_sentence",
            message="Too many parts inside <REF>... only asterisk and one variable allowed"
        )

    asterisk = False
    var_name = ""

    if len(parts) == 1:
        if parts[0].startswith("*"):
            asterisk = True
            var_name = parts[0][1:]
            if not var_name:
                return Failure(
                    value=cnlp_sentence['details']['sentence'],
                    is_fatal=True if cnlp_sentence['belonging'] == "instruction" else False,
                    error_type="unrecognized_sentence",
                    message="No variable name after '*'"
                )
        else:
            var_name = parts[0]
    else:  # len(parts) == 2
        if parts[0] != "*":
            return Failure(
                value=cnlp_sentence['details']['sentence'],
                is_fatal=True if cnlp_sentence['belonging'] == "instruction" else False,
                error_type="unrecognized_sentence",
                message="Invalid format, unexpected first token"
            )
        asterisk = True
        var_name = parts[1]

    name_pattern = re.compile(
        r'^[a-zA-Z_][a-zA-Z0-9_]*'  # simple name
        r'(?:'
        r'(?:\[\d+\])'  # array access
        r'|(?:\["[a-zA-Z_][a-zA-Z0-9_]*"\])'  # dict access
        r'|(?:\.[a-zA-Z_][a-zA-Z0-9_]*)'  # dot access
        r'|(?:\.\[\d+\])'  # dot + array
        r'|(?:\.\["[a-zA-Z_][a-zA-Z0-9_]*"\])'  # dot + dict
        r')*$',  # repeat
    )

    if not name_pattern.fullmatch(var_name):
        return Failure(
            value=cnlp_sentence['details']['sentence'],
            is_fatal=True if cnlp_sentence['belonging'] == "instruction" else False,
            error_type="unrecognized_sentence",
            message=f"Invalid variable name: '{var_name}'"
        )

    return Success({"asterisk": asterisk, "var_name": var_name})


def reconstruct_description_with_reference(cnlp_sentence: CNLPSentence) -> Result:
    description_with_reference = re.sub(r'^[A-Z]+:', '', cnlp_sentence['details']['sentence'])

    token_specification = [
        ('RefStart', r'<REF>'),
        ('RefEnd', r'</REF>'),
        ('Asterisk', r'\*'),
        ('Str', r'[^\s<>*,?!;]+'),
        ('Punctuation', r'[,.?!;]'),
        ('Space', r' +'),
        ('Newline', r'\n'),
    ]
    token_regex = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in token_specification)
    get_token = re.compile(token_regex).match

    pos = 0
    tokens = []
    while pos < len(description_with_reference):
        match = get_token(description_with_reference, pos)
        if not match:
            pos += 1
            continue
        token_type = match.lastgroup
        token_value = match.group(token_type)
        tokens.append({'token_type': token_type, 'token_value': token_value})
        pos = match.end()

    error_list = []
    ref_close = True
    description_dict = {}
    ref_descriptions = {}
    ref_index = 1
    text_accum = ""
    ref_content = ""
    collecting_ref = False
    ref_messy = False

    for token in tokens:
        if token['token_type'] == 'RefStart':
            if not ref_close:
                ref_messy = True
                break
            ref_close = False
            collecting_ref = True
            ref_content = "<REF>"
            description_dict['description'] = description_dict.get('description', '')
            if text_accum:
                description_dict['description'] += text_accum.strip()
                text_accum = ""
            description_dict['description'] += f"<reference{ref_index}> "


        elif token['token_type'] == 'RefEnd':
            if ref_close or not collecting_ref:
                ref_messy = True
                break
            ref_content += "</REF>"
            collecting_ref = False
            ref_close = True

            intermediate_sentence = CNLPSentence(
                belonging=cnlp_sentence['belonging'],
                details={"sentence": ref_content},
            )
            reconstruct_reference_result = reconstruct_reference(intermediate_sentence)
            if isinstance(reconstruct_reference_result, Failure):
                error_list.append(reconstruct_reference_result)
            else:
                ref_descriptions[f'reference{ref_index}'] = reconstruct_reference_result.value
                ref_index += 1
            ref_content = ""

        elif collecting_ref:
            ref_content += token['token_value']
        else:
            text_accum += token['token_value']

    # 如果仍有文本剩余在缓冲区，那么就将这一部分部分在最后进行追加
    if text_accum:
        description_dict['description'] = description_dict.get('description', '') + text_accum.strip()

    description_dict.update(ref_descriptions)

    if not ref_close or ref_messy:
        return Failure(
            value=cnlp_sentence['details']['sentence'],
            is_fatal=True if cnlp_sentence['belonging'] == "instruction" else False,
            error_type="identifier_error",
            message="The '<REF>' and '</REF>' identifiers have pairing errors."
        )

    if error_list:
        message = []
        for error in error_list:
            message.append(f"The content '{error.value}' has an error: {error.message}")
        message = "\n".join(message)
        return Failure(
            value=cnlp_sentence['details']['sentence'],
            is_fatal=True if cnlp_sentence['belonging'] == "instruction" else False,
            error_type="identifier_error",
            message=message
        )

    return Success(description_dict)

def parse_general_command(command_content: str) -> Result:
    command_content = command_content.strip()
    error_list = []

    # 分离出 RESULT 和操作部分（非贪婪匹配）
    # 匹配三个部分：描述、RESULT 部分（可选）、SET/APPEND（可选）
    match = re.match(
        r'(?P<desc>.+?)(?:\s+RESULT\s+(?P<result>.+?)(?:\s+(?P<op>SET|APPEND))?)?$',
        command_content,
        re.DOTALL
    )

    if not match:
        return Failure(
            value=command_content,
            is_fatal=True,
            error_type="unrecognized_sentence",
            message="'COMMAND' command must follow the format: description_with_reference [RESULT var':'type|reference [SET|APPEND]]"
        )

    desc_text = match.group("desc").strip()
    result_part = match.group("result")
    operation = match.group("op") or "SET"  # 默认操作为 SET

    # 处理描述部分
    desc_result = reconstruct_description_with_reference(
        CNLPSentence(
            belonging="instruction",
            details={"sentence": desc_text}
        )
    )
    if isinstance(desc_result, Failure):
        error_list.append(
            Failure(
                value=desc_text,
                is_fatal=True,
                error_type="description_error",
                message=desc_result.message
            )
        )

    result_info = None
    if result_part:
        result_part = result_part.strip()
        if result_part.startswith("<REF>") and result_part.endswith("</REF>"):
            ref_result = reconstruct_reference(
                CNLPSentence(
                    belonging="instruction",
                    details={"sentence": result_part}
                )
            )
            if isinstance(ref_result, Failure):
                error_list.append(
                    Failure(
                        value=result_part,
                        is_fatal=True,
                        error_type="reference_error",
                        message=ref_result.message
                    )
                )
            else:
                result_info = ref_result.value
        else:
            if ':' not in result_part:
                error_list.append(
                    Failure(
                        value=result_part,
                        is_fatal=True,
                        error_type="unrecognized_sentence",
                        message="Missing ':' in variable declaration or malformed <REF>"
                    )
                )
            else:
                var_name, var_type = result_part.split(':', 1)
                var_name = var_name.strip()
                var_type = var_type.strip()

                # ✅ 校验 var_name：合法 Python 风格变量名
                if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', var_name):
                    error_list.append(
                        Failure(
                            value=var_name,
                            is_fatal=True,
                            error_type="invalid_variable_name",
                            message=f"Variable name '{var_name}' is invalid. It must not contain spaces or special characters and must start with a letter or underscore."
                        )
                    )

                # ✅ 校验 var_type：不能含空格
                elif not re.match(r'^[^\s]+$', var_type):
                    error_list.append(
                        Failure(
                            value=var_type,
                            is_fatal=True,
                            error_type="invalid_variable_type",
                            message=f"Variable type '{var_type}' is invalid. Type name must not contain spaces."
                        )
                    )

                else:
                    result_info = {
                        "var_name": var_name,
                        "var_type": var_type
                    }

        if result_info is not None:
                result_info["operation"] = operation

    # 错误处理
    if error_list:
        messages = []
        is_fatal = False
        for err in error_list:
            messages.append(f"The content '{err.value}' has an error: {err.message}")
            if err.is_fatal:
                is_fatal = True
        return Failure(
            value=command_content,
            is_fatal=is_fatal,
            error_type="general_command_error",
            message="\n".join(messages)
        )

    # 返回结构
    result_data = {
        "type": "general_command",
        "description_with_reference": desc_result.value
    }
    if result_info:
        result_data["result"] = result_info

    return Success(result_data)

# 解析类型为“CALL”的command
def parse_call_command(command_content: str) -> Result:
    original = command_content.strip()
    response_info = {}
    paras = {}

    error_list = []

    # 处理 RESPONSE 段（SET 或 APPEND）
    response_match = re.search(r'\bRESPONSE\s+(.+)\s+(SET|APPEND)\s*$', original)
    if response_match:
        response_part, operation = response_match.groups()
        original = original[:response_match.start()].strip()  # 去掉 RESPONSE 段

        # 当是引用了一个变量重新赋值时，需要调用
        if response_part.startswith("<REF>"):
            # 这里实际上构建了一个IntermediateSentence类型的值
            ref_result = reconstruct_reference({
                "belonging": "instruction",
                "details": {"sentence": response_part}
            })
            if isinstance(ref_result, Failure):
                error_list.append(
                    Failure(
                        value=original,
                        is_fatal=True,
                        error_type="reference_error",
                        message=ref_result.message
                    )
                )
            else:
                response_info['reference'] = ref_result.value
                response_info['operation'] = operation
        else:
            if ':' not in response_part:
                error_list.append(
                    Failure(
                        value=response_part,
                        is_fatal=True,
                        error_type="unrecognized_sentence",
                        message="Missing ':' in variable declaration or '<REF>', '</REF>' in variable reference"
                    )
                )
            else:
                var_name, var_type = response_part.split(':', 1)
                var_name = var_name.strip()
                var_type = var_type.strip()
                error_list = []

                if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', var_name):
                    error_list.append(
                        Failure(
                            value=var_name,
                            is_fatal=True,
                            error_type="invalid_variable_name",
                            message=f"Variable name '{var_name}' is invalid. It must not contain spaces or special characters and must start with a letter or underscore."
                        )
                    )

                elif not re.match(r'^[^\s]+$', var_type):
                    error_list.append(
                        Failure(
                            value=var_type,
                            is_fatal=True,
                            error_type="invalid_variable_type",
                            message=f"Variable type '{var_type}' is invalid. Type name must not contain spaces."
                        )
                    )

                if error_list:
                    return Failure(
                        value=response_part,
                        is_fatal=True,
                        error_type="response_variable_format_error",
                        message="\n".join(
                            f"The content '{err.value}' has an error: {err.message}" for err in error_list)
                    )

                response_info = {
                    "var_name": var_name,
                    "var_type": var_type,
                    "operation": operation
                }

    #TODO:
    #   response match匹配为空的分为没有RESPONSE的情况、没有SET|APPEND的情况，以及两者同时都不存在的情况
    #   只有当RESPONSE、SET|APPEND同时不存在，才不会报错，否则都算报错
    else:
        if 'RESPONSE' in original or "SET" in original or "APPEND" in original:
            error_list.append(
                Failure(
                    value=original,
                    is_fatal=True,
                    error_type="unrecognized_sentence",
                    message="""If the function returns a value, add a declaration after "RESPONSE" and indicate the variable handling type "SET" or "APPEND".""",
                )
            )
            # TODO：检测到RESPONSE部分存在错误，那么在添加完相应的错误以后，应该删除这一部分的内容
            if 'RESPONSE' in original:
                # 删除从 'RESPONSE' 开始到结尾，删除内容包括 'RESPONSE'本身
                response_idx = original.find('RESPONSE')
                original = original[:response_idx].strip()
            else:
                # 存在 SET 或 APPEND，但没有 RESPONSE
                last_brace_idx = original.rfind('}')
                if last_brace_idx != -1:
                    # 保留 } 之前的所有内容，包括 }
                    original = original[:last_brace_idx + 1].strip()
                else:
                    # 如果连 } 都没有，就保留整个原句（不做截断），可能后面还有 WITH 等错误需要处理
                    pass

    # 处理 WITH 参数段
    with_idx = original.rfind("WITH")
    if with_idx != -1:
        before_with = original[:with_idx].strip()
        after_with = original[with_idx + len("WITH"):].strip()

        if after_with:
            # 参数必须是 {...}
            # 首先检查最外层是不是被"{}"包括，按照语法，参数列表最外层应该由"{}"包裹
            match = re.match(r'^{.*}$', after_with, re.DOTALL)
            # 如果不被"{}"包裹，应该直接报错
            if not match:
                error_list.append(
                    Failure(
                        value=after_with,
                        is_fatal=True,
                        error_type="unrecognized_sentence",
                        message="The parameter object following “WITH” must be valid argument list: {...}"
                    )
                )
            # 如果被正确的符号包裹
            else:
                # 去除最外层"{", "}"
                param_block = after_with[1:-1].strip()
                # 还要检查参数列表是否为空
                if param_block:
                    param_pairs = re.split(r',\s*(?![^<]*</REF>)', param_block)
                    for pair in param_pairs:
                        if ':' not in pair:
                            error_list.append(
                                Failure(
                                    value=pair,
                                    is_fatal=True,
                                    error_type="param_syntax_error",
                                    message="Each parameter must have a ':' separating formal parameter name and actual formal value."
                                )
                            )
                            continue

                        param_name, param_val = pair.split(':', 1)
                        param_name = param_name.strip()
                        param_val = param_val.strip()

                        if param_val.startswith("<REF>") and param_val.endswith("</REF>"):
                            ref_result = reconstruct_reference({
                                "belonging": "instruction",
                                "details": {"sentence": param_val}
                            })
                            if isinstance(ref_result, Failure):
                                error_list.append(
                                    Failure(
                                        value=param_val,
                                        is_fatal=True,
                                        error_type="reference_error",
                                        message=ref_result.message
                                    )
                                )
                            else:
                                paras[param_name] = {"reference": ref_result.value['var_name'], "type": 'reference'}
                        else:
                            # 普通值直接赋值为字符串
                            paras[param_name] = {"value": param_val, "type": 'actual value'}
                # 如果是一个空的参数列表，那么也应该报错
                else:
                    error_list.append(
                        Failure(
                            value=before_with,
                            is_fatal=True,
                            error_type="param_syntax_error",
                            message="The argument list is empty. if the function. If a function does not require parameters, there is no need to declare an empty argument list through 'WITH'"
                        )
                    )
        api_name = before_with
    else:
        api_name = original

    api_name = api_name.strip()
    if not re.fullmatch(r'[a-zA-Z_]\w*', api_name):
        error_list.append(
            Failure(
                value=api_name,
                is_fatal=True,
                error_type="unrecognized_sentence",
                message=f"Invalid function name: {api_name}"
            )
        )

    if error_list:
        message = []
        is_fatal = False
        for error in error_list:
            message.append(f"The content '{error.value}' has an error: {error.message}")
            if error.is_fatal:
                is_fatal = True
        message = "\n".join(message)
        return Failure(
            value=command_content,
            is_fatal=is_fatal,
            error_type="identifier_error",
            message=message
        )

    result = {
        "type": "call_api",
        "api_name": api_name
    }
    if paras:
        result["paras"] = paras
    if response_info:
        result["response"] = response_info

    return Success(result)

def parse_input_command(command_content: str) -> Result:
    original = command_content.strip()
    error_list = []

    # 尝试匹配语法：描述 VALUE 变量 SET|APPEND
    match = re.match(r'(.+)\s+VALUE\s+(.+)\s+(SET|APPEND)$', original, re.DOTALL)
    if not match:
        return Failure(
            value=original,
            is_fatal=True,
            error_type="unrecognized_sentence",
            message="Expected format: <description_with_reference> VALUE <var> SET|APPEND"
        )

    desc_part, var_part, operation = match.groups()

    # 解析描述部分
    desc_result = reconstruct_description_with_reference({
        "belonging": "instruction",
        "details": {"sentence": desc_part.strip()}
    })
    if isinstance(desc_result, Failure):
        error_list.append(
            Failure(
                value=desc_part,
                is_fatal=True,
                error_type="description_error",
                message=desc_result.message
            )
        )

    # 解析变量部分
    var_part = var_part.strip()
    target_info = None

    if var_part.startswith("<REF>") and var_part.endswith("</REF>"):
        ref_result = reconstruct_reference({
            "belonging": "instruction",
            "details": {"sentence": var_part}
        })
        if isinstance(ref_result, Failure):
            error_list.append(
                Failure(
                    value=var_part,
                    is_fatal=True,
                    error_type="reference_error",
                    message=ref_result.message
                )
            )
        else:
            target_info = ref_result.value
    else:
        if ':' not in var_part:
            error_list.append(
                Failure(
                    value=var_part,
                    is_fatal=True,
                    error_type="unrecognized_sentence",
                    message="Missing ':' in variable declaration or malformed <REF>"
                )
            )
        else:
            var_name, var_type = var_part.split(':', 1)
            var_name = var_name.strip()
            var_type = var_type.strip()

            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', var_name):
                error_list.append(
                    Failure(
                        value=var_name,
                        is_fatal=True,
                        error_type="invalid_variable_name",
                        message=f"Variable name '{var_name}' is invalid. It must not contain spaces or special characters and must start with a letter or underscore."
                    )
                )

            elif not re.match(r'^[^\s]+$', var_type):
                error_list.append(
                    Failure(
                        value=var_type,
                        is_fatal=True,
                        error_type="invalid_variable_type",
                        message=f"Variable type '{var_type}' is invalid. Type name must not contain spaces."
                    )
                )

            else:
                target_info = {
                    "var_name": var_name,
                    "var_type": var_type
                }

    # 汇总错误或构建成功结果
    if error_list:
        messages = []
        is_fatal = False
        for err in error_list:
            messages.append(f"The content '{err.value}' has an error: {err.message}")
            if err.is_fatal:
                is_fatal = True
        return Failure(
            value=command_content,
            is_fatal=is_fatal,
            error_type="input_command_error",
            message="\n".join(messages)
        )

    target_info["operation"] = operation

    return Success({
        "type": "request_input",
        "description_with_reference": desc_result.value,
        "value": target_info
    })

def parse_display_command(command_content: str) -> Result:
    desc_result = reconstruct_description_with_reference({
        "belonging": "instruction",
        "details": {"sentence": command_content.strip()}
    })

    if isinstance(desc_result, Failure):
        return desc_result
    else:
        return Success({
            "type": "display_message",
            "description_with_reference": desc_result.value,

        })


def reconstruct_command(cnlp_sentence: CNLPSentence) -> Result:

    parse_command_content_function_map = {
        "COMMAND": parse_general_command,
        "INPUT": parse_input_command,
        "DISPLAY": parse_display_command,
        "CALL": parse_call_command,
    }

    command_sentence = cnlp_sentence['details']['sentence']

    # match = re.match(r'COMMAND-(\d+)\s*\[([A-Z]+)(.*?)\]', command_sentence, re.DOTALL)
    match = re.match(r'COMMAND-(\d+)\s*\[([A-Z]+)\s*(.*)\]$', command_sentence, re.DOTALL)

    if match:
        command_order, command_type, command_content = match.groups()
        #TODO: 对command order的检查可能是非必要的，因为在“sentence_recognizer”对其的检查应该是完善的。
        if command_order != cnlp_sentence['details']['order']:
            return Failure()
        # TODO：这里应该要改用function_map的形式
        if command_type not in parse_command_content_function_map.keys():
            return Failure(
                value=command_sentence,
                is_fatal=True,
                error_type="unrecognized_sentence",
                message=f"Invalid command type: '{command_type}'."
            )
        reconstruct_result = parse_command_content_function_map[command_type](command_content)
        if isinstance(reconstruct_result, Failure):
            reconstruct_result.value = command_sentence
            return reconstruct_result
        else:
            return reconstruct_result
    else:
        return Failure(
            value=cnlp_sentence['details']['sentence'],
            is_fatal=True,
            error_type="unrecognized_sentence",
            message="the sentence does not conform to the syntax pattern of command"
        )


# def parse_structured_text(text: str) -> Any:
#     """
#     将“类 JSON”结构的字符串转换为合法 JSON 并解析为 Python 对象。
#     自动容错处理非程序员风格的 JSON 写法：
#     - key 可无引号
#     - 字符串值可无引号（改进为更安全）
#     - 布尔值大小写容忍
#     - 允许尾逗号
#     - 单引号替换为双引号
#     """
#     try:
#         json_compatible = text.strip()
#
#         # 替换 key 的单引号（在 { 或 , 后面，冒号前）
#         json_compatible = re.sub(
#             r"([{,]\s*)'([^']+?)'\s*:",
#             r'\1"\2":',
#             json_compatible
#         )
#
#         # 替换 Python 风格的布尔值和 null
#         json_compatible = re.sub(r'\bTrue\b', 'true', json_compatible)
#         json_compatible = re.sub(r'\bFalse\b', 'false', json_compatible)
#         json_compatible = re.sub(r'\bNone\b', 'null', json_compatible)
#
#         # 修复 key 缺引号（允许包含空格）
#         json_compatible = re.sub(
#             r'([{,]\s*)([a-zA-Z_][\w\s-]*)\s*:',
#             r'\1"\2":',
#             json_compatible
#         )
#
#         print(json_compatible)
#
#         # 更安全的裸字符串修复函数
#         def fix_naked_values(s):
#             # 仅修复裸字符串值（避免误处理合法 JSON 值或复杂句子）
#             def quote_if_needed(match):
#                 key_sep, val = match.group(1), match.group(2).strip()
#
#                 # 合法 JSON 值不处理
#                 if re.match(r'^(true|false|null|[-+]?\d+(\.\d+)?([eE][-+]?\d+)?|"[^"]*"|\{.*\}|\[.*\])$', val):
#                     return f"{key_sep}{val}"
#
#                 # 如果包含冒号，通常为句子，包一层引号但不修改内容
#                 if ':' in val:
#                     return f'{key_sep}"{val}"'
#
#                 return f'{key_sep}"{val}"'
#
#             # 对 key: value 的 value 部分进行修复
#             s = re.sub(
#                 r'(:)\s*([^,\}\]\n]+)',
#                 quote_if_needed,
#                 s
#             )
#
#             # 修复数组项
#             def fix_array_items(match):
#                 array_body = match.group(1)
#                 items = [item.strip() for item in array_body.split(",")]
#                 fixed_items = []
#                 for item in items:
#                     if not item:
#                         continue
#                     if re.match(r'^(true|false|null|[-+]?\d+|"[^"]*"|\{.*\}|\[.*\])$', item):
#                         fixed_items.append(item)
#                     elif ':' in item:
#                         fixed_items.append(f'"{item}"')
#                     else:
#                         fixed_items.append(f'"{item}"')
#                 return "[" + ", ".join(fixed_items) + "]"
#
#             s = re.sub(r'\[\s*([^\[\]]+?)\s*\]', fix_array_items, s)
#
#             return s
#
#         for _ in range(3):  # 最多递归3层
#             new_json = fix_naked_values(json_compatible)
#             if new_json == json_compatible:
#                 break
#             json_compatible = new_json
#
#         # 去除尾逗号
#         json_compatible = re.sub(r',\s*([}\]])', r'\1', json_compatible)
#
#         print(json_compatible)
#
#         return Success(json.loads(json_compatible))
#
#     except Exception as e:
#         return Failure(
#             value=text,
#             is_fatal=False,
#             error_type="unrecognized_structured_text",
#             message=f"failed to be parsed for the reason: {e}"
#         )


def parse_structured_text(text: str) -> Any:
    """
    将“类 JSON”结构的字符串转换为合法 JSON 并解析为 Python 对象。
    自动容错处理非程序员风格的 JSON 写法：
    - key 可无引号
    - 字符串值可无引号
    - 布尔值大小写容忍
    - 允许尾逗号
    - 单引号替换为双引号
    """
    try:
        json_compatible = text.strip()

        # 替换 key 的单引号（在 { 或 , 后面，冒号前）
        json_compatible = re.sub(
            r"([{,]\s*)'([^']+?)'\s*:",
            r'\1"\2":',
            json_compatible
        )

        # json_compatible = json_compatible.replace("'", '"')

        # 替换 Python 风格的布尔值和 null
        json_compatible = re.sub(r'\bTrue\b', 'true', json_compatible)
        json_compatible = re.sub(r'\bFalse\b', 'false', json_compatible)
        json_compatible = re.sub(r'\bNone\b', 'null', json_compatible)

        # 修复 key 缺引号（允许包含空格）
        json_compatible = re.sub(
            r'([{,]\s*)([a-zA-Z_][\w\s-]*)\s*:',
            r'\1"\2":',
            json_compatible
        )

        # TODO: EXAMPLE的修复问题
        # # 递归修复裸字符串值（包括嵌套结构）
        # def fix_naked_values(s):
        #     # 修复对象中的裸值
        #     s = re.sub(
        #         r'(:)\s*(?!true|false|null|["{\[\d-])([^,\}\]\s][^,\}\]\n]*)',
        #         lambda m: f'{m.group(1)}"{m.group(2)}"',
        #         s
        #     )
        #
        #     # 修复数组中的裸值
        #     def fix_array_items(match):
        #         array_content = match.group(1)
        #         items = re.split(r',\s*(?![^{}]*\})', array_content)
        #         fixed_items = []
        #         for item in items:
        #             if not item.strip():
        #                 continue
        #             if re.match(r'^\s*(true|false|null|\d+|".*"|{.*}|\[.*\])\s*$', item, re.DOTALL):
        #                 fixed_items.append(item)
        #             else:
        #                 fixed_items.append(f'"{item.strip()}"')
        #         return "[" + ", ".join(fixed_items) + "]"
        #
        #     s = re.sub(r'\[\s*([^\[\]]+?)\s*\]', fix_array_items, s)
        #     return s
        #
        # for _ in range(3):  # 最多递归3层
        #     new_json = fix_naked_values(json_compatible)
        #     if new_json == json_compatible:
        #         break
        #     json_compatible = new_json

        # 去除非法尾逗号（逗号后紧接 } 或 ]）
        json_compatible = re.sub(r',\s*([}\]])', r'\1', json_compatible)

        # TODO:这样的修复方法
        # 修复 Windows 路径中反斜杠（如 C:\Users\Admin）
        # json_compatible = re.sub(
        #     r':\s*"([A-Za-z]:\\[^"]*)"',
        #     lambda m: ': "' + m.group(1).replace("\\", "\\\\") + '"',
        #     json_compatible
        # )

        return Success(json.loads(json_compatible))

    except Exception as e:
        return Failure(
            value=text,
            is_fatal=False,
            error_type="unrecognized_structured_text",
            message=f"failed to be parsed for the reason: {e}"
        )

def extract_nested_block(text: str, key: str) -> Optional[str]:
    """
    提取给定 key 后第一个完整的 {...} 区块字符串
    """
    key_index = text.find(key)
    if key_index == -1:
        return None

    brace_start = text.find('{', key_index)
    if brace_start == -1:
        return None

    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[brace_start:i + 1]  # 包含闭合大括号
    return None

def parse_expected_worker_behavior(sentence: CNLPSentence) -> Result:
    content = sentence['details']['sentence']
    pattern = r'<EXPECTED-WORKER-BEHAVIOR>\s*{(.*)}\s*</EXPECTED-WORKER-BEHAVIOR>'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return Failure(
            value=content,
            is_fatal=False,
            error_type="unrecognized_sentence",
            message="The content of EXAMPLE sentence should be included within “{}”."
        )

    body = match.group(1)
    error_list = []
    expected_worker_behavior = {}

    # Inputs
    input_pattern = r"inputs\s*:\s*{"
    input_match = re.search(input_pattern, body, re.DOTALL)
    if not input_match:
        error_list.append(
            Failure(
                value=body,
                is_fatal=False,
                error_type="unrecognized_sentence",
                message="The example-inputs should be included by '{' and '}'."
            )
        )
    input_block = extract_nested_block(body, "inputs")
    if not input_block:
        error_list.append(Failure(
            value=body,
            is_fatal=False,
            error_type="unrecognized_sentence",
            message="missing or malformed 'inputs'"
        ))
        expected_worker_behavior['inputs'] = "missing or malformed 'inputs'"
    else:
        input_result = parse_structured_text(input_block)
        if isinstance(input_result, Failure):
            error_list.append(Failure(
                value=input_block,
                is_fatal=False,
                error_type="unrecognized_structured_text",
                message=f"Invalid inputs structure: '{input_result.value}' {input_result.message}"
            ))
            expected_worker_behavior['inputs'] = f"The EXAMPLE input {input_result.value}"
        else:
            expected_worker_behavior['inputs'] = input_result.value

    # Outputs
    output_pattern = r"outputs\s*:\s*{"
    output_match = re.search(output_pattern, body, re.DOTALL)
    if not output_match:
        error_list.append(
            Failure(
                value=body,
                is_fatal=False,
                error_type="unrecognized_sentence",
                message="The example-outputs should be included by '{' and '}'."
            )
        )
    output_block = extract_nested_block(body, "expected-outputs")
    if not output_block:
        error_list.append(Failure(
            value=body,
            is_fatal=False,
            error_type="unrecognized_sentence",
            message="missing or malformed 'expected-outputs'"
        ))
        expected_worker_behavior['expected-output'] = "missing or malformed 'expected-outputs'"
    else:
        output_result = parse_structured_text(output_block)
        if isinstance(output_result, Failure):
            error_list.append(Failure(
                value=output_block,
                is_fatal=False,
                error_type="unrecognized_structured_text",
                message=f"Invalid output structure: '{output_result.value}' {output_result.message}"
            ))
            expected_worker_behavior['expected-output'] = f"The EXAMPLE output {output_result.value}"
        else:
            expected_worker_behavior['expected-output'] = output_result.value

    # Execution Path
    path_match = re.search(r'execution-path\s*:\s*(COMMAND-\d+(?:\s*,\s*COMMAND-\d+)*)', body)
    if not path_match:
        error_list.append(Failure(
            value=body,
            is_fatal=False,
            error_type="unrecognized_sentence",
            message="Missing or malformed 'execution-path'"
        ))
        expected_worker_behavior['execution-path'] = "missing or malformed"
    else:
        expected_worker_behavior['execution-path'] = [s.strip() for s in path_match.group(1).split(',')]

    if error_list:
        summary = f"There are several errors in {content}:\n"
        summary += "\n".join([f"{i+1}.{e.message}" for i, e in enumerate(error_list)])
        return Failure(
            value=expected_worker_behavior,
            is_fatal=False,
            error_type=None,
            message=summary
        )

    return Success(expected_worker_behavior)

def parse_defect_worker_behavior(sentence: CNLPSentence) -> Result:
    content = sentence['details']['sentence']
    example_number = sentence['details']['order']
    pattern = r'<DEFECT-WORKER-BEHAVIOR>\s*{(.*)}\s*</DEFECT-WORKER-BEHAVIOR>'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        return Failure(
            value=content,
            is_fatal=False,
            error_type="unrecognized_sentence",
            message="The content of DEFECT sentence should be included within “{}”."
        )

    body = match.group(1)
    error_list = []
    defect_behavior = {}

    # Defect type
    defect_type_match = re.match(r'\s*([^,]+)\s*,', body)
    if not defect_type_match:
        error_list.append(Failure(
            value=body,
            is_fatal=False,
            error_type="unrecognized_sentence",
            message="Missing or malformed defect type at the beginning."
        ))
        defect_behavior["defect_type"] = "missing or malformed"
    else:
        defect_behavior["defect_type"] = defect_type_match.group(1).strip()

    # Inputs
    input_block = extract_nested_block(body, "inputs")
    if not input_block:
        error_list.append(Failure(
            value=body,
            is_fatal=False,
            error_type="unrecognized_sentence",
            message="Missing or malformed 'inputs'"
        ))
        defect_behavior["inputs"] = "missing"
    else:
        input_result = parse_structured_text(input_block)
        if isinstance(input_result, Failure):
            error_list.append(Failure(
                value=input_block,
                is_fatal=False,
                error_type="unrecognized_structured_text",
                message=f"Invalid inputs structure: '{input_result.value}' {input_result.message}"
            ))
            defect_behavior["inputs"] = "malformed"
        else:
            defect_behavior["inputs"] = input_result.value

    # Defect outputs
    output_block = extract_nested_block(body, "defect-outputs")
    if not output_block:
        error_list.append(Failure(
            value=body,
            is_fatal=False,
            error_type="unrecognized_sentence",
            message="Missing or malformed 'defect-outputs'"
        ))
        defect_behavior["defect-outputs"] = "missing"
    else:
        output_result = parse_structured_text(output_block)
        if isinstance(output_result, Failure):
            error_list.append(Failure(
                value=output_block,
                is_fatal=False,
                error_type="unrecognized_structured_text",
                message=f"Invalid output structure: '{output_result.value}' {output_result.message}"
            ))
            defect_behavior["defect-outputs"] = "malformed"
        else:
            defect_behavior["defect-outputs"] = output_result.value

    # Execution path
    path_match = re.search(r'execution-path\s*:\s*(COMMAND-\d+(?:\s*,\s*COMMAND-\d+)*)', body)
    if not path_match:
        error_list.append(Failure(
            value=body,
            is_fatal=False,
            error_type="unrecognized_sentence",
            message="Missing or malformed 'execution-path'. Should be [COMMAND-<number>, ...]"
        ))
        defect_behavior["execution-path"] = "missing or malformed"
    else:
        defect_behavior["execution-path"] = [s.strip() for s in path_match.group(1).split(",")]

    # Defect explanation
    explanation_match = re.search(r'defect-explanation\s*:\s*([^"]+)', body)
    if not explanation_match:
        error_list.append(Failure(
            value=body,
            is_fatal=False,
            error_type="unrecognized_sentence",
            message="Missing 'defect-explanation'."
        ))
        defect_behavior["defect-explanation"] = "missing"
    else:
        defect_behavior["defect-explanation"] = explanation_match.group(1).strip()

    if error_list:
        summary = f"There are several errors in DEFECT-WORKER-BEHAVIOR:\n{content}\n"
        summary += "\n".join([f"{i+1}. [{e.error_type}] {e.message}" for i, e in enumerate(error_list)])
        return Failure(
            value=defect_behavior,
            is_fatal=False,
            error_type="defect_worker_behavior_parsing_failure",
            message=summary
        )

    return Success(defect_behavior)

# def parse_defect_worker_behavior(sentence: CNLPSentence) -> Result:
#     content = sentence['details']['sentence']
#     example_number = sentence['details']['order']
#     pattern = r'<DEFECT-WORKER-BEHAVIOR>\s*{(.*)}\s*</DEFECT-WORKER-BEHAVIOR>'
#     match = re.search(pattern, content, re.DOTALL)
#
#     if not match:
#         return Failure(
#             value=content,
#             is_fatal=False,
#             error_type="unrecognized_sentence",
#             message="The content of DEFECT sentence should be included within “{}”."
#         )
#
#     body = match.group(1)
#     error_list = []
#     defect_behavior = {}
#
#     # Defect type
#     defect_type_match = re.match(r'\s*([^,]+)\s*,', body)
#     if not defect_type_match:
#         error_list.append(Failure(
#             value=body,
#             is_fatal=False,
#             error_type="unrecognized_sentence",
#             message="Missing or malformed defect type at the beginning."
#         ))
#         defect_behavior["defect_type"] = "missing or malformed"
#     else:
#         defect_behavior["defect_type"] = defect_type_match.group(1).strip()
#
#     # Inputs
#     input_block = extract_nested_block(body, "inputs")
#     if not input_block:
#         error_list.append(Failure(
#             value=body,
#             is_fatal=False,
#             error_type="unrecognized_sentence",
#             message="Missing or malformed 'inputs'"
#         ))
#         defect_behavior["input"] = "missing"
#     else:
#         input_result = parse_structured_text(input_block)
#         if isinstance(input_result, Failure):
#             error_list.append(Failure(
#                 value=input_block,
#                 is_fatal=False,
#                 error_type="unrecognized_structured_text",
#                 message=f"Invalid input structure: {input_result.value}"
#             ))
#             defect_behavior["input"] = "malformed"
#         else:
#             defect_behavior["input"] = input_result.value
#
#     # Defect outputs
#     output_block = extract_nested_block(body, "defect-outputs")
#     if not output_block:
#         error_list.append(Failure(
#             value=body,
#             is_fatal=False,
#             error_type="unrecognized_sentence",
#             message="Missing or malformed 'defect-outputs'"
#         ))
#         defect_behavior["defect-output"] = "missing"
#     else:
#         output_result = parse_structured_text(output_block)
#         if isinstance(output_result, Failure):
#             error_list.append(Failure(
#                 value=output_block,
#                 is_fatal=False,
#                 error_type="unrecognized_structured_text",
#                 message=f"Invalid output structure: {output_result.value}"
#             ))
#             defect_behavior["defect-output"] = "malformed"
#         else:
#             defect_behavior["defect-output"] = output_result.value
#
#     # Execution path
#     path_match = re.search(r'execution-path\s*:\s*(COMMAND-\d+(?:\s*,\s*COMMAND-\d+)*)', body)
#     if not path_match:
#         error_list.append(Failure(
#             value=body,
#             is_fatal=False,
#             error_type="unrecognized_sentence",
#             message="Missing or malformed 'execution-path'. Should be [COMMAND-<number>, ...]"
#         ))
#         defect_behavior["execution-path"] = "missing or malformed"
#     else:
#         defect_behavior["execution-path"] = [s.strip() for s in path_match.group(1).split(",")]
#
#     # Defect explanation
#     explanation_match = re.search(r'defect-explanation\s*:\s*"([^"]+)"', body)
#     if not explanation_match:
#         error_list.append(Failure(
#             value=body,
#             is_fatal=False,
#             error_type="unrecognized_sentence",
#             message="Missing 'defect-explanation'."
#         ))
#         defect_behavior["defect_explanation"] = "missing"
#     else:
#         defect_behavior["defect_explanation"] = explanation_match.group(1).strip()
#
#     if error_list:
#         summary = f"There are several errors in DEFECT-WORKER-BEHAVIOR:\n{content}\n"
#         summary += "\n".join([f"{i+1}. [{e.error_type}] {e.message}" for i, e in enumerate(error_list)])
#         return Failure(
#             value=defect_behavior,
#             is_fatal=False,
#             error_type="defect_worker_behavior_parsing_failure",
#             message=summary
#         )
#
#     return Success(defect_behavior)


def reconstruct_example(cnlp_sentence: CNLPSentence) -> Result:
    # result = {"examples": {}}
    # for sentence in sentences:
    #     example_type = sentence['details'].get("example_type")
    #     if example_type == "expect":
    #         parsed = parse_expected_worker_behavior(sentence)
    #         result["examples"].update(parsed)
    #     elif example_type == "defect":
    #         parsed = parse_defect_worker_behavior(sentence)
    #         result["examples"].update(parsed)
    # return result
    example_type = cnlp_sentence['details'].get("example_type")
    if example_type == 'expect':
        reconstruct_result = parse_expected_worker_behavior(cnlp_sentence)
    elif example_type == 'defect':
        reconstruct_result = parse_defect_worker_behavior(cnlp_sentence)

    return reconstruct_result

