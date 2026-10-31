from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


from ..shared.environment import load_runtime_environment


METHOD_NAME = "codex"
CODEX_REFERENCE_FILE_NAME = "reference_code_for_codex.py"
CODEX_DOCKER_IMAGE = "rq4-codex-runtime:0.147.0"
CODEX_CONTAINER_WORKDIR = "/workspace"
CODEX_PROVIDER_ID = "rq4_relay"
CODEX_PROVIDER_API_KEY_ENV = "RQ4_CODEX_PROVIDER_API_KEY"
CODEX_INPUT_DIRECTORY_NAME = "_codex_inputs"
CODEX_EVENTS_FILE_NAME = "codex_events.jsonl"
CODEX_COMPATIBILITY_LOG_NAME = "codex_compatibility_log.json"
CODEX_COMPATIBILITY_EVENTS_NAME = "codex_compatibility_events.jsonl"


CODEX_COMPILATION_PROMPT = """
【任务】

请根据当前目录中提供的 CNL-P Script 和 Reference Code，生成一个可以
实际运行的 Python Agent 项目。

必须立即使用本地工具读取以下两个输入文件并开始生成代码，不要只回复工作计划：

- `_codex_inputs/agent.cnlp`：完整的 CNL-P Script，是 Agent 业务语义的唯一权威来源。
- `_codex_inputs/reference_code.py`：为 CNL-P 中 CALL API 提供的 Python 参考实现。

不得修改这两个输入文件。生成后的 Agent 不得在运行时读取或依赖
`_codex_inputs`。

【生成结果】

当前工作目录就是最终 Agent 的根目录，不要创建额外的外层项目目录。

项目可以只有一个 Python 文件，也可以包含多个文件，但根目录必须包含 `main.py`，
并提供以下无参数入口：

def main():
    ...

`main()` 应初始化 Agent、执行入口 Worker，并返回最终执行结果。

`main.py` 被 import 时不得自动运行，同时必须支持直接运行：

if __name__ == "__main__":
    main()

项目内部如何划分文件、保存变量和组织流程，由你自行决定。

【终端交互】

生成的 Agent 与用户之间的所有交互必须在终端中完成：

- 使用标准输出向用户展示提示、说明和结果。
- 使用标准输入读取用户回答。
- 不得生成 GUI、Web 页面或后台服务。
- 每次执行一个 CNL-P INPUT Command，只读取一次用户输入。
- 如果一个 INPUT Command 需要获得多个字段，应从这一次用户输入中理解并提取，
  不得擅自拆成多轮提问。
- 只有当 CNL-P Flow 再次执行某个 INPUT Command 时，才可以再次读取输入。

【CNL-P 语义】

必须完整实现 CNL-P Script 表达的 Types、Variables、Commands、Conditions、Workers、
INPUTS、OUTPUTS 和控制流程。

不得使用固定示例值、占位返回值或与当前 Script 绑定的测试答案替代真实功能。

【CNL-P 基本执行语义】

类型和值：
- `[a, b, c]` 表示只能取这些值之一的有限值域，不表示列表。
- `List [T]` 表示由若干 T 类型元素组成的列表。
- `{field: T}` 表示包含具名字段的结构化值。
- `OPTIONAL field: T` 表示该字段可以不存在。
- 写入变量的值必须满足变量声明的类型，不得擅自改变变量类型。

引用和写入：
- `<REF>x</REF>` 表示读取当前状态中变量 x 的值；带字段路径的引用表示读取对应
  嵌套字段。
- `SET` 表示用新值替换变量当前值。
- `VALUE <REF>x</REF> SET` 表示将 INPUT Command 处理后的用户输入写入 x。
- `RESULT <REF>x</REF> SET` 表示将 COMMAND 的处理结果写入 x。
- `RESPONSE <REF>x</REF> SET` 表示将 CALL API 或 CALL Worker 的返回结果写入 x。

Command：
- INPUT：展示请求，读取恰好一次用户输入，按照 Command 描述处理后写入 VALUE
  指定的变量。
- COMMAND：根据 Command 描述及其引用的数据完成计算或语义处理，并将结果写入
  RESULT 指定的变量。
- CALL：调用指定的 API 或 Worker，并将返回值写入 RESPONSE 指定的变量。
- DISPLAY：向用户展示指定内容；除非 Script 明确要求，否则不得修改变量。
- LOG：记录诊断信息，不等同于面向用户的 DISPLAY。

控制结构和 Worker：
- SEQUENTIAL_BLOCK 中的内容按照书写顺序执行。
- 同一组 IF、ELSEIF 和 ELSE 是互斥分支，只执行第一个满足条件的分支。
- 调用 Worker 时，只通过其声明的 INPUTS 传入数据，并通过其声明的 OUTPUTS
  返回结果。
- REQUIRED OUTPUT 在 Worker 正常结束时必须存在；OPTIONAL OUTPUT 可以不存在。
- DISPLAY 某个值不等于已经设置或返回该 OUTPUT。

【Reference Code】

Reference Code 为 CNL-P 中对应的 CALL API 提供参考实现。

对于 Reference Code 中与语言模型调用有关的代码，可以根据本实验统一的
OpenAI Client、模型、Base URL 和 reasoning effort 配置进行替换，不要求复制其
LLM 客户端初始化和模型调用样板代码。

除上述 LLM 调用基础设施外，应尽可能妥善利用 Reference Code 已提供的内容，
包括 Prompt 内容和指令约束、输入数据的组织与序列化方式、调用前的数据处理、
输出提取与解析、清洗和类型转换、返回值构造、结果校验、空结果处理、错误处理，
以及不依赖 LLM 的确定性业务逻辑。

可以直接复用、封装、内联或进行必要适配，不限制生成项目的代码组织形式，但
不得无故丢弃 Reference Code 中已有的重要 Prompt、处理逻辑和行为约束。

如果 Reference Code 与 CNL-P Script 的类型、接口或业务语义存在冲突，以
CNL-P Script 为最终依据，并进行必要适配。

【运行时语言模型】

当 CNL-P Command 或 Condition 涉及自然语言理解、自然语言生成、语义转换或语义
判断时，应使用运行时语言模型完成，不得擅自替换成关键词匹配、简单正则表达式、
固定模板或硬编码结论。

明确且不需要语义理解的计算、赋值、比较、流程控制和数据处理，可以直接使用
Python 实现。

具体哪些 Commands 和 Conditions 需要语言模型，以及如何组织相关代码，由你根据
CNL-P 的真实语义决定。

运行时语言模型必须：

- 使用官方 OpenAI Python Client：`from openai import OpenAI`。
- 从 `.env` 或当前进程环境变量读取 `OPENAI_API_KEY`。
- 从 `.env` 或当前进程环境变量读取 `BASE_URL`。
- 优先从 `.env` 或当前进程环境变量读取 `CNLP_REFERENCE_LLM_MODEL` 作为模型
  名称；若未设置，则读取 `OPENAI_MODEL`。若两者均未设置，应报告明确错误。
- 所有运行时语言模型调用都必须显式使用 `high` reasoning effort，例如
  `reasoning={"effort": "high"}`。
- 不得在代码中写入真实 API Key 或其他凭据。

这些是生成后 Agent 的运行时模型配置，不是当前 Codex 生成代码时使用的配置。

【Static Attributes】

CNL-P 中的 Static Attributes 用于约束 Agent 的整体行为：

- Persona：Agent 的身份、职责和行为立场。
- Audience：目标用户及其知识背景，影响术语选择、解释深度和表达方式。
- Concepts：Agent 应遵循的领域概念及其含义。
- Constraints：Agent 必须遵守的业务边界和行为限制。

这些属性应实际影响需要自然语言理解、判断或生成的交互过程，但具体如何在项目中
体现，由你自行决定。

【三类 Flow】

- Main Flow 是 Worker 的正常执行流程和执行入口。
- Alternative Flow 是可恢复的旁路流程；满足条件时从 Main Flow 进入，执行完成后
  返回 Main Flow 中合理的位置继续执行。
- Exception Flow 是不可恢复的旁路流程；满足条件时从 Main Flow 进入，执行完成后
  结束当前 Worker，不再返回 Main Flow。
- Alternative Flow 和 Exception Flow 只能由 Main Flow 触发，旁路 Flow 之间不得相互
  触发或调用。
- CNL-P 不直接标出旁路 Flow 的触发位置和 Alternative Flow 的返回位置。应根据
  条件所依赖的数据、更新这些数据的 Command 以及整体业务语义确定，不得只根据
  Command 编号猜测。

当一个 CALL 调用另一个 Worker 时，将被调用 Worker 视为子程序：按照其 INPUTS 接收
数据，执行自身 Flow，再按照其 OUTPUTS 和 CALL RESPONSE 将结果返回给调用者。

【执行边界】

所有生成文件只能写入当前工作目录。

不得读取或修改父目录、同级目录、其他案例、已有编译产物或编译器源码。不得联网
搜索实现方案，不得写入密钥或机器相关的绝对路径。

生成完成后，仅对生成的 Python 文件执行语法检查，例如使用 `python -m py_compile`。
不得导入或启动 Agent，不得调用真实外部 API。

只有在根目录已经生成 `main.py` 及其所需文件，并完成上述语法检查后，任务才算
完成。只给出计划、建议或代码说明不算完成。
""".strip()


CODEX_DIRECTORY_ACCESS_INSTRUCTIONS = """
You may access only the current working directory. Do not list, read, search,
or modify its parent directory, sibling directories, or any other project.
Write every generated artifact below the current working directory. Do not use
the network and do not request expanded permissions. The two files under the
current directory's _codex_inputs folder are the only task inputs. Read them
with local tools, do the work, and write the generated project into the current
working directory. A plan-only response is not a completed task.
""".strip()


CODEX_COMPATIBILITY_PROMPT = """
Use the local file tools now. Create a file named main.py directly in the
current working directory with exactly one public entry function:

def main():
    return "codex_tool_calling_ok"

After writing the file, run a local Python syntax check for main.py. Do not
only describe a plan and do not merely print the source code in your answer.
The task is complete only after main.py physically exists in the current
working directory.
""".strip()


REASONING_EFFORT_VALUES = {
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
}


def _validated_case_input_paths(
    case_directory: Path,
    specification_file: str = "agent.cnlp",
) -> tuple[Path, Path]:
    cnlp_path = case_directory / specification_file
    reference_path = case_directory / CODEX_REFERENCE_FILE_NAME
    if not cnlp_path.is_file():
        raise FileNotFoundError(f"Specification input file not found: {cnlp_path}")
    if not reference_path.is_file():
        raise FileNotFoundError(
            f"Codex reference-code file not found: {reference_path}"
        )
    reference_code = reference_path.read_text(encoding="utf-8")
    reference_tree = ast.parse(
        reference_code,
        filename=str(reference_path),
    )
    decorated_functions = [
        node.name
        for node in ast.walk(reference_tree)
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
        and node.decorator_list
    ]
    if decorated_functions:
        raise ValueError(
            f"{CODEX_REFERENCE_FILE_NAME} must not contain decorated "
            "functions: "
            + ", ".join(sorted(decorated_functions))
        )
    return cnlp_path, reference_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _create_isolated_work_directory(
    *,
    work_root: Path,
    prefix: str,
) -> Path:
    """Create a unique workspace without tempfile's Windows ACL behavior."""
    for _ in range(10):
        candidate = (
            work_root
            / f"{prefix}{uuid.uuid4().hex}"
        )
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate.resolve()
    raise RuntimeError(
        "Cannot create a unique isolated Codex workspace."
    )


def _stage_codex_inputs(
    *,
    case_directory: Path,
    work_directory: Path,
    specification_file: str = "agent.cnlp",
) -> dict[str, Any]:
    """Copy only the two approved inputs into the isolated workspace."""
    cnlp_path, reference_path = _validated_case_input_paths(case_directory, specification_file)
    input_directory = work_directory / CODEX_INPUT_DIRECTORY_NAME
    input_directory.mkdir()
    staged_name = "agent.cnlp" if specification_file == "agent.cnlp" else "specification.txt"
    staged_cnlp = input_directory / staged_name
    staged_reference = input_directory / "reference_code.py"
    shutil.copy2(cnlp_path, staged_cnlp)
    shutil.copy2(reference_path, staged_reference)
    return {
        "directory": input_directory,
        "hashes": {
            staged_name: _sha256(staged_cnlp),
            "reference_code.py": _sha256(staged_reference),
        },
    }


def _verify_staged_inputs(input_record: dict[str, Any]) -> None:
    input_directory = Path(input_record["directory"])
    for file_name, expected_hash in input_record["hashes"].items():
        input_path = input_directory / file_name
        if not input_path.is_file() or _sha256(input_path) != expected_hash:
            raise RuntimeError(
                "Codex modified or removed its task input: "
                f"{file_name}."
            )


def _validate_generated_python(
    agent_directory: Path,
) -> None:
    """Perform only structural validation, never an Agent execution."""
    main_path = agent_directory / "main.py"
    if not main_path.is_file():
        raise RuntimeError(
            "Codex must generate main.py directly in the Agent root."
        )

    python_files = sorted(
        agent_directory.rglob("*.py")
    )
    if not python_files:
        raise RuntimeError(
            "Codex did not generate any Python source files."
        )

    syntax_trees: dict[Path, ast.Module] = {}

    for python_file in python_files:
        source = python_file.read_text(encoding="utf-8")
        if CODEX_INPUT_DIRECTORY_NAME in source:
            raise RuntimeError(
                "Generated Python code must not depend on the temporary "
                f"{CODEX_INPUT_DIRECTORY_NAME} input directory: "
                f"{python_file}"
            )
        syntax_trees[python_file] = ast.parse(
            source,
            filename=str(python_file),
        )

    main_functions = [
        node
        for node in syntax_trees[main_path].body
        if isinstance(node, ast.FunctionDef)
        and node.name == "main"
    ]

    if len(main_functions) != 1:
        raise RuntimeError(
            "Root main.py must define exactly one top-level "
            "synchronous main function."
        )

    main_arguments = main_functions[0].args

    positional_arguments = [
        *main_arguments.posonlyargs,
        *main_arguments.args,
    ]

    required_positional_count = (
        len(positional_arguments)
        - len(main_arguments.defaults)
    )

    required_keyword_only_count = sum(
        default is None
        for default in main_arguments.kw_defaults
    )

    if (
        required_positional_count
        or required_keyword_only_count
    ):
        raise RuntimeError(
            "Generated main() must be callable without arguments."
        )


def _required_environment_value(
    *names: str,
) -> str:
    """
    Return the first non-empty configured environment value.
    """
    for name in names:
        value = os.getenv(
            name,
            "",
        ).strip()

        if value:
            return value

    raise RuntimeError(
        "Missing required environment value. Tried: "
        + ", ".join(names)
    )


def _load_codex_environment(
    case_directory: Path,
) -> tuple[str, str, str]:
    return _load_codex_environment_from_rq4(case_directory.parents[1])


def _load_codex_environment_from_rq4(
    rq4_directory: Path,
) -> tuple[str, str, str]:
    """
    Load relay credentials and default model.

    CODEX_RELAY_* variables are optional Codex-only overrides.

    If they do not exist, Codex deliberately uses the same
    OPENAI_API_KEY / BASE_URL / OPENAI_MODEL configuration used
    by Native and LangGraph.
    """
    load_runtime_environment()

    api_key = _required_environment_value(
        "CODEX_RELAY_API_KEY",
        "OPENAI_API_KEY",
    )

    base_url = _required_environment_value(
        "CODEX_RELAY_BASE_URL",
        "BASE_URL",
    )

    default_model = _required_environment_value(
        "CODEX_MODEL",
        "OPENAI_MODEL",
    )

    return (
        api_key,
        base_url,
        default_model,
    )


def _toml_string(
    value: str,
) -> str:
    """
    Encode a Python string as a TOML-compatible basic string.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
    )


def _docker_available() -> None:
    """
    Fail early if Docker Desktop / Docker Engine is unavailable.
    """
    try:
        completed = subprocess.run(
            [
                "docker",
                "version",
                "--format",
                "{{.Server.Version}}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    except OSError as exc:
        raise RuntimeError(
            "Docker CLI is not available. "
            "Install/start Docker Desktop first."
        ) from exc

    if completed.returncode != 0:
        raise RuntimeError(
            "Docker is installed but the Docker daemon "
            "is not available.\n"
            f"stderr:\n{completed.stderr}"
        )


def _build_docker_command(
    *,
    work_directory: Path,
    base_url: str,
    model: str,
    reasoning_effort: str | None,
) -> list[str]:
    """
    Construct one isolated Dockerized Codex invocation.
    """
    command = [
        "docker",
        "run",

        # Remove the container after Codex exits.
        "--rm",

        # Keep stdin open because the complete prompt is sent via stdin.
        "-i",

        # ---------------------------------------------------------
        # Physical host filesystem boundary.
        #
        # THIS is the only RQ4 business directory exposed to Docker.
        # ---------------------------------------------------------
        "--mount",
        (
            "type=bind,"
            f"source={work_directory},"
            f"target={CODEX_CONTAINER_WORKDIR}"
        ),

        "--workdir",
        CODEX_CONTAINER_WORKDIR,

        # ---------------------------------------------------------
        # Only this secret is copied into the Codex process.
        #
        # The host .env file itself is NOT mounted.
        # ---------------------------------------------------------
        "--env",
        CODEX_PROVIDER_API_KEY_ENV,

        CODEX_DOCKER_IMAGE,

        # =========================================================
        # Codex top-level CLI arguments.
        # =========================================================

        "--ask-for-approval",
        "never",

        # Docker is the filesystem isolation boundary for RQ4. Running the
        # inner Linux sandbox here would start Bubblewrap inside Docker, which
        # fails on standard Docker Desktop because unprivileged user
        # namespaces are unavailable. danger-full-access only applies inside
        # this disposable container; the host exposes one temporary Trial
        # workspace and no other RQ4 directory.
        "--sandbox",
        "danger-full-access",

        "--cd",
        CODEX_CONTAINER_WORKDIR,

        "--model",
        model,

        # ---------------------------------------------------------
        # Custom relay provider.
        # ---------------------------------------------------------

        "--config",
        (
            "model_provider="
            f"{_toml_string(CODEX_PROVIDER_ID)}"
        ),

        "--config",
        (
            f"model_providers."
            f"{CODEX_PROVIDER_ID}.name="
            f"{_toml_string('RQ4 relay')}"
        ),

        "--config",
        (
            f"model_providers."
            f"{CODEX_PROVIDER_ID}.base_url="
            f"{_toml_string(base_url)}"
        ),

        "--config",
        (
            f"model_providers."
            f"{CODEX_PROVIDER_ID}.env_key="
            f"{_toml_string(CODEX_PROVIDER_API_KEY_ENV)}"
        ),

        "--config",
        (
            f"model_providers."
            f'{CODEX_PROVIDER_ID}.wire_api="responses"'
        ),

        "--config",
        (
            f"model_providers."
            f"{CODEX_PROVIDER_ID}."
            "requires_openai_auth=false"
        ),

        # ---------------------------------------------------------
        # Model-level access instructions.
        # ---------------------------------------------------------

        "--config",
        (
            "developer_instructions="
            f"{_toml_string(CODEX_DIRECTORY_ACCESS_INSTRUCTIONS)}"
        ),

        # ---------------------------------------------------------
        # Disable Codex web search.
        # ---------------------------------------------------------

        "--config",
        'web_search="disabled"',

        # ---------------------------------------------------------
        # Do not forward KEY / SECRET / TOKEN environment variables
        # into the shell processes started by the model.
        # ---------------------------------------------------------

        "--config",
        (
            "shell_environment_policy."
            "ignore_default_excludes=false"
        ),

        "--config",
        'shell_environment_policy.inherit="core"',

        # ---------------------------------------------------------
        # Do not walk upward looking for another project root.
        # ---------------------------------------------------------

        "--config",
        "project_root_markers=[]",

        # ---------------------------------------------------------
        # Keep each compilation as one primary Codex agent.cnlp.
        # ---------------------------------------------------------

        "--config",
        "agents.enabled=false",

        "--config",
        "features.multi_agent=false",

        # ---------------------------------------------------------
        # Avoid login-shell side effects.
        # ---------------------------------------------------------

        "--config",
        "allow_login_shell=false",

        # The Docker image pins the Codex version.
        "--config",
        "check_for_update_on_startup=false",
    ]

    if reasoning_effort is not None:
        command.extend(
            [
                "--config",
                (
                    "model_reasoning_effort="
                    f"{_toml_string(reasoning_effort)}"
                ),
            ]
        )

    command.extend(
        [
            # =====================================================
            # Non-interactive Codex execution.
            # =====================================================

            "exec",

            # Do not persist session rollout files.
            "--ephemeral",

            # Machine-readable JSONL output.
            "--json",

            # Do not read ~/.codex/config.toml.
            "--ignore-user-config",

            # Do not load ambient execpolicy rules.
            "--ignore-rules",

            # The temporary workspace intentionally is not a Git repo.
            "--skip-git-repo-check",

            # Read the complete task from stdin.
            "-",
        ]
    )

    return command


def _parse_codex_jsonl(
    stdout: str,
) -> dict[str, Any]:
    """
    Extract experiment facts from codex exec --json output.
    """
    thread_id: str | None = None
    final_response: str | None = None
    token_usage: Any = None
    reported_error: Any = None
    turn_completed = False
    event_counts: dict[str, int] = {}
    completed_item_counts: dict[str, int] = {}
    tool_item_ids: set[str] = set()
    successful_tool_item_ids: set[str] = set()
    failed_tool_item_ids: set[str] = set()
    non_json_line_count = 0

    for line_index, raw_line in enumerate(stdout.splitlines(), start=1):
        line = raw_line.strip()

        if not line:
            continue

        try:
            event = json.loads(line)

        except json.JSONDecodeError:
            non_json_line_count += 1
            continue

        if not isinstance(event, dict):
            continue

        event_type = event.get("type")
        if isinstance(event_type, str):
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        if isinstance(event_type, str) and event_type.startswith("item."):
            item = event.get("item")
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type in {"command_execution", "file_change"}:
                    item_id = item.get("id")
                    tool_item_ids.add(
                        item_id
                        if isinstance(item_id, str)
                        else f"line-{line_index}-{item_type}"
                    )
                if event_type == "item.completed" and isinstance(
                    item_type,
                    str,
                ):
                    completed_item_counts[item_type] = (
                        completed_item_counts.get(item_type, 0) + 1
                    )
                    if item_type in {"command_execution", "file_change"}:
                        item_id = item.get("id")
                        normalized_item_id = (
                            item_id
                            if isinstance(item_id, str)
                            else f"line-{line_index}-{item_type}"
                        )
                        if item.get("status") == "failed":
                            failed_tool_item_ids.add(normalized_item_id)
                        else:
                            successful_tool_item_ids.add(normalized_item_id)

        if event_type == "thread.started":
            raw_thread_id = event.get(
                "thread_id"
            )

            if isinstance(
                raw_thread_id,
                str,
            ):
                thread_id = raw_thread_id

        elif event_type == "item.completed":
            item = event.get("item")

            if (
                isinstance(item, dict)
                and item.get("type")
                == "agent_message"
                and isinstance(
                    item.get("text"),
                    str,
                )
            ):
                final_response = item["text"]

        elif event_type == "turn.completed":
            turn_completed = True
            token_usage = event.get(
                "usage"
            )

        elif event_type in {
            "turn.failed",
            "error",
        }:
            reported_error = event

    return {
        "thread_id": thread_id,
        "final_response": final_response,
        "token_usage": token_usage,
        "reported_error": reported_error,
        "turn_completed": turn_completed,
        "event_counts": event_counts,
        "completed_item_counts": completed_item_counts,
        "tool_activity_count": len(tool_item_ids),
        "successful_tool_activity_count": len(
            successful_tool_item_ids
        ),
        "failed_tool_activity_count": len(failed_tool_item_ids),
        "non_json_line_count": non_json_line_count,
    }


def _normalize_codex_token_usage(
    raw_usage: Any,
) -> dict[str, Any] | None:
    """Expose Codex aggregate usage through the common RQ4 total schema."""
    if not isinstance(raw_usage, dict):
        return None

    def token_count(*names: str) -> int:
        for name in names:
            value = raw_usage.get(name)
            if (
                isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
            ):
                return value
        return 0

    input_tokens = token_count("input_tokens")
    cached_input_tokens = token_count("cached_input_tokens")
    output_tokens = token_count("output_tokens")
    reasoning_tokens = token_count(
        "reasoning_output_tokens",
        "reasoning_tokens",
    )
    reported_total_tokens = raw_usage.get("total_tokens")
    total_tokens = (
        reported_total_tokens
        if (
            isinstance(reported_total_tokens, int)
            and not isinstance(reported_total_tokens, bool)
            and reported_total_tokens >= 0
        )
        else input_tokens + output_tokens
    )

    return {
        "source": "codex_cli_turn_completed",
        # codex exec reports one aggregate for the complete tool-using turn.
        # It does not expose a reliable count or usage record for each model
        # request made internally during that turn.
        "request_count": None,
        "successful_request_count": None,
        "failed_request_count": None,
        "requests_without_usage_count": None,
        "total": {
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "total_tokens": total_tokens,
        },
        "calls": None,
        # Preserve provider-specific fields such as
        # cache_write_input_tokens and reasoning_output_tokens.
        "raw_usage": raw_usage,
    }


class _CodexProgressDisplay:
    """把已有 Codex JSONL 事件压缩为一行活动状态。

    Codex 在开始前不知道最终会执行多少次工具调用，因此这里不显示虚假的完成
    百分比。计数完全来自本来就要读取和保存的事件流，不增加模型请求、文件扫描
    或轮询线程，也不会改变 Codex 的生成过程。
    """

    def __init__(self) -> None:
        self._started_at = time.monotonic()
        self._completed_tools = 0
        self._failed_tools = 0
        self._changed_files = 0
        self._reported_errors = 0
        self._last_width = 0
        self._finished = False

    @staticmethod
    def _elapsed_text(elapsed_seconds: float) -> str:
        elapsed = max(0, round(elapsed_seconds))
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _render(self, status: str, *, final: bool = False) -> None:
        elapsed = self._elapsed_text(time.monotonic() - self._started_at)
        message = (
            f"[Codex] {status} | tools {self._completed_tools} done"
            f" ({self._failed_tools} failed) | file changes {self._changed_files}"
            f" | errors {self._reported_errors} | elapsed {elapsed}"
        )
        padded_message = message.ljust(self._last_width)
        self._last_width = max(self._last_width, len(message))
        print(
            "\r" + padded_message,
            end="\n" if final else "",
            flush=True,
        )
        if final:
            self._finished = True

    def consume(self, line: str) -> None:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict):
            return

        event_type = event.get("type")
        if event_type in {"thread.started", "turn.started"}:
            self._render("working")
            return

        if event_type == "item.completed":
            item = event.get("item")
            if not isinstance(item, dict):
                return
            item_type = item.get("type")
            if item_type not in {"command_execution", "file_change"}:
                return
            self._completed_tools += 1
            if item.get("status") == "failed":
                self._failed_tools += 1
            if item_type == "file_change":
                self._changed_files += 1
            self._render("working")
            return

        if event_type == "error":
            # Codex 可能在断线重连后继续并最终成功，所以 error 事件只计数，
            # 不在这里提前把整个 Trial 标记为失败。
            self._reported_errors += 1
            self._render("working")
            return

        if event_type in {"turn.completed", "turn.failed"}:
            self._render(
                "completed" if event_type == "turn.completed" else "failed",
                final=True,
            )

    def finish_if_needed(self, *, succeeded: bool) -> None:
        if not self._finished:
            self._render("completed" if succeeded else "failed", final=True)


def _forward_codex_stream(
    *,
    stream: TextIO | None,
    captured_parts: list[str],
    jsonl: bool,
    progress_display: _CodexProgressDisplay | None = None,
) -> None:
    if stream is None:
        return
    try:
        for line in iter(stream.readline, ""):
            captured_parts.append(line)
            if jsonl:
                if progress_display is not None:
                    progress_display.consume(line.strip())
            # stderr 仍会被完整保存，并在失败异常中展示。正常执行时不逐行
            # 转发，避免警告或重连信息破坏单行进度显示。
    finally:
        stream.close()


def _run_codex_in_container(
    *,
    prompt: str,
    work_directory: Path,
    method_record: dict[str, Any],
    api_key: str,
    base_url: str,
    model: str,
    reasoning_effort: str | None,
    events_path: Path,
) -> None:
    """
    Execute exactly one Codex compilation inside Docker.
    """
    _docker_available()

    process_environment = os.environ.copy()

    # -------------------------------------------------------------
    # Internally rename whichever host-side key was selected.
    #
    # This means the Docker command never needs to know whether the
    # original key came from OPENAI_API_KEY or CODEX_RELAY_API_KEY.
    # -------------------------------------------------------------

    process_environment[
        CODEX_PROVIDER_API_KEY_ENV
    ] = api_key

    command = _build_docker_command(
        work_directory=work_directory,
        base_url=base_url,
        model=model,
        reasoning_effort=reasoning_effort,
    )

    started_at = time.monotonic()
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    progress_display = _CodexProgressDisplay()
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        env=process_environment,
        bufsize=1,
    )
    stdout_thread = threading.Thread(
        target=_forward_codex_stream,
        kwargs={
            "stream": process.stdout,
            "captured_parts": stdout_parts,
            "jsonl": True,
            "progress_display": progress_display,
        },
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_forward_codex_stream,
        kwargs={
            "stream": process.stderr,
            "captured_parts": stderr_parts,
            "jsonl": False,
            "progress_display": None,
        },
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    if process.stdin is None:
        raise RuntimeError("Cannot open stdin for the Codex container.")
    try:
        process.stdin.write(prompt)
        process.stdin.close()
        return_code = process.wait()
    finally:
        stdout_thread.join()
        stderr_thread.join()

    progress_display.finish_if_needed(
        succeeded=return_code == 0,
    )

    stdout = "".join(stdout_parts)
    stderr = "".join(stderr_parts)
    # Preserve the complete machine-readable stream separately from the
    # summary in compilation_log.json. This is essential when a relay reports
    # turn.completed even though Codex never receives or invokes file tools.
    events_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    events_path.write_text(stdout, encoding="utf-8")

    duration_ms = round(
        (
            time.monotonic()
            - started_at
        )
        * 1000
    )

    facts = _parse_codex_jsonl(stdout)

    # -------------------------------------------------------------
    # Keep the same type of factual experiment record as before.
    #
    # codex exec JSONL currently does not expose a stable separate
    # turn ID, so codex_turn_id is explicitly None.
    # -------------------------------------------------------------

    method_record[
        "codex_thread_id"
    ] = facts["thread_id"]

    method_record[
        "codex_turn_id"
    ] = None

    method_record[
        "codex_turn_status"
    ] = (
        "completed"
        if (
            return_code == 0
            and facts["turn_completed"]
        )
        else "failed"
    )

    method_record[
        "codex_turn_error"
    ] = facts["reported_error"]

    method_record[
        "codex_duration_ms"
    ] = duration_ms

    method_record[
        "codex_final_response"
    ] = facts["final_response"]

    method_record["codex_events_file"] = events_path.name
    method_record["codex_event_counts"] = facts["event_counts"]
    method_record["codex_completed_item_counts"] = facts[
        "completed_item_counts"
    ]
    method_record["codex_tool_activity_count"] = facts[
        "tool_activity_count"
    ]
    method_record["codex_successful_tool_activity_count"] = facts[
        "successful_tool_activity_count"
    ]
    method_record["codex_failed_tool_activity_count"] = facts[
        "failed_tool_activity_count"
    ]
    method_record["codex_non_json_line_count"] = facts[
        "non_json_line_count"
    ]

    method_record[
        "codex_container_image"
    ] = CODEX_DOCKER_IMAGE

    method_record[
        "codex_inner_sandbox"
    ] = "danger-full-access"

    method_record[
        "codex_isolation_boundary"
    ] = "docker_single_temporary_workspace_mount"

    method_record[
        "codex_model"
    ] = model

    # Keep the exact model-reasoning setting in every Trial log. This makes
    # Codex High experiments distinguishable from runs using the provider's
    # default reasoning effort.
    method_record[
        "codex_reasoning_effort"
    ] = reasoning_effort

    method_record[
        "codex_provider"
    ] = CODEX_PROVIDER_ID

    method_record[
        "codex_stderr"
    ] = stderr

    # trial_runner.py moves this field to the stable top-level
    # compilation_log.json["token_usage"] location.
    method_record[
        "token_usage"
    ] = _normalize_codex_token_usage(
        facts["token_usage"]
    )

    if (
        return_code != 0
        or not facts["turn_completed"]
    ):
        reported_error_text = (
            json.dumps(
                facts["reported_error"],
                ensure_ascii=False,
            )
            if facts["reported_error"] is not None
            else "No structured Codex error was reported."
        )
        raise RuntimeError(
            "Containerized Codex compilation failed.\n"
            f"exit code: "
            f"{return_code}\n"
            f"reported error:\n"
            f"{reported_error_text}\n"
            f"stderr:\n"
            f"{stderr}"
        )

    if facts["tool_activity_count"] == 0:
        raise RuntimeError(
            "Codex reported turn.completed but performed no "
            "command_execution or file_change. The model returned only text, "
            "so the configured relay must be checked for complete Responses "
            "API tool-calling support. See codex_events.jsonl for the raw "
            "event stream."
        )

    if facts["successful_tool_activity_count"] == 0:
        raise RuntimeError(
            "Codex invoked local tools, but every completed "
            "command_execution and file_change failed. See "
            "codex_events.jsonl and codex_stderr for the concrete local "
            "tool error."
        )


def _copy_generated_agent(
    *,
    work_directory: Path,
    agent_directory: Path,
) -> None:
    """
    Export the validated staging workspace into the Trial's
    normal generated/.../agent/ directory.
    """
    agent_directory = (
        agent_directory.resolve()
    )

    agent_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    if any(
        agent_directory.iterdir()
    ):
        raise RuntimeError(
            "Final Codex agent_directory "
            "must be empty before export: "
            f"{agent_directory}"
        )

    shutil.copytree(
        work_directory,
        agent_directory,
        dirs_exist_ok=True,
    )


def _utc_timestamp() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _write_json(
    path: Path,
    value: dict[str, Any],
) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def verify_codex_environment(
    *,
    rq4_directory: str | Path,
    model: str | None = None,
    reasoning_effort: str = "high",
) -> dict[str, Any]:
    """Verify Codex file-tool compatibility outside every formal Trial.

    This diagnostic deliberately generates only a tiny main.py in a temporary
    workspace. Its token usage and result are written to standalone files and
    are never counted as an RQ4 compilation Trial.
    """
    resolved_rq4_directory = Path(
        rq4_directory
    ).resolve()
    if reasoning_effort not in REASONING_EFFORT_VALUES:
        raise ValueError(
            "reasoning_effort must be one of: "
            + ", ".join(sorted(REASONING_EFFORT_VALUES))
        )

    api_key, base_url, default_model = (
        _load_codex_environment_from_rq4(
            resolved_rq4_directory
        )
    )
    selected_model = (
        model.strip()
        if isinstance(model, str) and model.strip()
        else default_model
    )
    log_path = (
        resolved_rq4_directory
        / CODEX_COMPATIBILITY_LOG_NAME
    )
    events_path = (
        resolved_rq4_directory
        / CODEX_COMPATIBILITY_EVENTS_NAME
    )
    work_root = (
        resolved_rq4_directory
        / "compilation"
        / ".codex_work"
    )
    work_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    method_record: dict[str, Any] = {}
    report: dict[str, Any] = {
        "diagnostic": "codex_file_tool_compatibility",
        "status": "running",
        "started_at": _utc_timestamp(),
        "finished_at": None,
        "formal_trial": False,
        "method_details": method_record,
        "error": None,
        "events_path": str(events_path),
    }

    try:
        work_directory = _create_isolated_work_directory(
            work_root=work_root,
            prefix="codex_compatibility_",
        )
        try:
            _run_codex_in_container(
                prompt=CODEX_COMPATIBILITY_PROMPT,
                work_directory=work_directory,
                method_record=method_record,
                api_key=api_key,
                base_url=base_url,
                model=selected_model,
                reasoning_effort=reasoning_effort,
                events_path=events_path,
            )
            _validate_generated_python(
                work_directory
            )
        finally:
            if work_directory.is_dir():
                shutil.rmtree(work_directory)
        report["status"] = "compatible"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        report["finished_at"] = _utc_timestamp()
        _write_json(
            log_path,
            report,
        )

    return report


def compile_agent(
    *,
    case_directory: Path,
    agent_directory: Path,
    method_record: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """
    Generate one Agent in a fresh Docker-isolated Codex workspace.
    """
    allowed_options = {
        "model",
        "reasoning_effort",
        "specification_file",
        "prompt_file",
    }

    unknown_options = sorted(
        set(options)
        - allowed_options
    )

    if unknown_options:
        raise ValueError(
            "Unsupported Codex compilation options: "
            + ", ".join(
                unknown_options
            )
        )

    configured_model = options.get(
        "model"
    )

    reasoning_effort = options.get(
        "reasoning_effort"
    )

    if (
        configured_model is not None
        and (
            not isinstance(
                configured_model,
                str,
            )
            or not configured_model.strip()
        )
    ):
        raise ValueError(
            "Codex option 'model' "
            "must be a non-empty string."
        )

    if (
        reasoning_effort is not None
        and (
            not isinstance(
                reasoning_effort,
                str,
            )
            or reasoning_effort.strip()
            not in REASONING_EFFORT_VALUES
        )
    ):
        raise ValueError(
            "Codex option 'reasoning_effort' "
            "must be one of: "
            + ", ".join(
                sorted(
                    REASONING_EFFORT_VALUES
                )
            )
        )

    # The task Prompt is fixed across Trials. The two case-specific inputs are
    # copied into the isolated workspace below instead of being embedded in a
    # very long user message. Codex therefore has to demonstrate that its file
    # tools work before it can compile the Agent.
    specification_file = options.get("specification_file", "agent.cnlp")
    prompt_file = options.get("prompt_file")
    for name in (specification_file, prompt_file):
        if name is not None and (
            not isinstance(name, str) or not name
            or Path(name).name != name or name in {".", ".."}
            or "/" in name or "\\" in name
        ):
            raise ValueError("Codex input options must be direct case filenames.")
    if specification_file != "agent.cnlp" and prompt_file is None:
        raise ValueError("Alternate specifications require their corresponding prompt_file.")
    prompt = (
        (case_directory / prompt_file).read_text(encoding="utf-8")
        if prompt_file is not None else CODEX_COMPILATION_PROMPT
    )
    if not prompt.strip():
        raise ValueError("Codex prompt must not be empty.")
    if prompt_file is not None:
        method_record["representation_inputs"] = {
            "specification_file": specification_file,
            "specification_sha256": _sha256(case_directory / specification_file),
            "prompt_file": prompt_file,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "reference_sha256": _sha256(case_directory / CODEX_REFERENCE_FILE_NAME),
        }

    (
        api_key,
        base_url,
        default_model,
    ) = _load_codex_environment(
        case_directory
    )

    model = (
        configured_model.strip()
        if isinstance(
            configured_model,
            str,
        )
        else default_model
    )

    normalized_reasoning_effort = (
        reasoning_effort.strip()
        if isinstance(
            reasoning_effort,
            str,
        )
        else "high"
    )

    compilation_directory = (
        Path(__file__)
        .resolve()
        .parent
    )

    work_root = (
        compilation_directory
        / ".codex_work"
    )

    work_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    # =============================================================
    # ISOLATED CODEX PHASE
    #
    # Example host path:
    #
    # RQ4/
    #   compilation/
    #     .codex_work/
    #       github_project_navigator_abcd1234/
    #
    # Docker sees only:
    #
    # /workspace
    #
    # The following are NOT mounted:
    #
    # - RQ4/cases/
    # - RQ4/generated/
    # - RQ4/testing/
    # - RQ4/compilation/codex.py
    # - Native outputs
    # - LangGraph outputs
    # - other Codex Trials
    # =============================================================

    work_directory = _create_isolated_work_directory(
        work_root=work_root,
        prefix=f"{case_directory.name}_",
    )
    try:
        input_record = _stage_codex_inputs(
            case_directory=case_directory,
            work_directory=work_directory,
            specification_file=specification_file,
        )
        events_path = (
            agent_directory.parent
            / CODEX_EVENTS_FILE_NAME
        )

        try:
            _run_codex_in_container(
                prompt=prompt,
                work_directory=work_directory,
                method_record=method_record,
                api_key=api_key,
                base_url=base_url,
                model=model,
                reasoning_effort=(
                    normalized_reasoning_effort
                ),
                events_path=events_path,
            )
            _verify_staged_inputs(
                input_record
            )
        finally:
            # _codex_inputs only carries trusted source material into the
            # container. It is never part of the generated Agent artifact.
            staged_input_directory = Path(
                input_record["directory"]
            )
            if staged_input_directory.is_dir():
                shutil.rmtree(
                    staged_input_directory
                )

        # =========================================================
        # Docker has already exited.
        #
        # Everything below is trusted host Python again.
        # =========================================================

        _validate_generated_python(
            work_directory
        )

        _copy_generated_agent(
            work_directory=work_directory,
            agent_directory=agent_directory,
        )
    finally:
        if work_directory.is_dir():
            shutil.rmtree(work_directory)
