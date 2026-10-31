from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any


from ..shared.environment import load_runtime_environment

from cnlp_compiler import CNLPCompiler
from cnlp_compiler.schema import (
    ModelConfig,
)

METHOD_NAME = "langgraph"


def _required_environment_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment value: {name}")
    return value


def _load_model_config(workspace_root: Path) -> ModelConfig:
    # Keep model configuration identical to Native so the selected Plan
    # Implementer is the only intended compiler-side difference. The complete
    # configuration is preserved in the generated Agent without post-processing.
    load_runtime_environment()
    return {
        "api_key": _required_environment_value("OPENAI_API_KEY"),
        "model_name": _required_environment_value("OPENAI_MODEL"),
        "base_url": _required_environment_value("BASE_URL"),
    }


def _load_reference_code(reference_path: Path) -> None:
    """Execute this case's reference registrations in the trial process."""
    module_name = f"rq4_reference_{reference_path.parent.name}"
    specification = importlib.util.spec_from_file_location(
        module_name,
        reference_path,
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(
            f"Cannot load reference-code module: {reference_path}"
        )

    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)


def compile_agent(
    *,
    case_directory: Path,
    agent_directory: Path,
    method_record: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Compile one case with the LangGraph Plan Implementer."""
    if options:
        raise ValueError("LangGraph compilation currently accepts no options.")

    # Persist the exact compiler package used by this Trial so RQ4 logs can
    # distinguish V0.1.1 results from artifacts produced by older compilers.
    method_record["compiler_package"] = "cnlp_compiler"

    workspace_root = case_directory.parents[1]
    reference_path = case_directory / "reference_code.py"
    cnlp_path = case_directory / "agent.cnlp"
    compiler = CNLPCompiler()

    try:
        _load_reference_code(reference_path)
        model_config = _load_model_config(workspace_root)
        compiler_return = compiler.compile(
            cnlp_text=cnlp_path.read_text(encoding="utf-8"),
            config={
                "model_config": model_config,
                # LangGraph is selected here rather than inferred from the
                # output directory name or a compiler default.
                "target_implementation": METHOD_NAME,
            },
            output_directory=agent_directory,
        )
        method_record["compiler_return"] = compiler_return
    except Exception as exc:
        print(
            f"[Compilation][{case_directory.name}][langgraph] Failed: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        raise
    finally:
        method_record["token_usage"] = compiler.last_token_usage
        method_record["compiler_trace"] = list(
            compiler.last_compilation_trace
        )
