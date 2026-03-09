from ..schemas.result import Failure, Success, Result
from ..schemas.process_decision import ProcessDecision, ContinueProcess, StopProcess

from typing import List
import json


def explain_syntax_analysis_result(process_result: ProcessDecision):
    pass


def format_failures(errors: List[Failure]) -> str:
    lines = []
    for error in errors:
        about = f" about '{error.value}'" if error.value is not None else ""

        if error.start_line is not None and error.end_line is not None:
            if error.start_line == error.end_line:
                lines.append(f"In line {error.start_line}{about}: {error.message}")
            else:
                lines.append(f"In lines {error.start_line}-{error.end_line}{about}: {error.message}")
        elif error.error_path is not None:
            lines.append(f"In path {error.error_path}{about}: {error.message}")
        else:
            lines.append(f"Unknown location{about}: {error.message}")
    return "\n".join(lines)


def extract_single_json(text):
    """
    假设文本中有且仅有一个完整的 JSON ({} 或 [])。
    返回该 JSON 解析后的 Python 对象（dict 或 list）。
    """
    stack = []
    start_index = None

    for i, c in enumerate(text):
        if c in '{[':
            if not stack:
                start_index = i
            stack.append(c)
        elif c in '}]':
            if stack:
                last = stack.pop()
                if (last == '{' and c != '}') or (last == '[' and c != ']'):
                    raise ValueError(f"JSON 括号不匹配：{last} - {c}")
                if not stack and start_index is not None:
                    json_str = text[start_index:i+1]
                    return json.loads(json_str)

    raise ValueError("未能在文本中找到完整的 JSON 结构")