from __future__ import annotations

import builtins
import importlib
import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any


try:
    from .runtime_token_tracker import (
        RuntimeTokenUsageTracker,
        track_openai_sdk_usage,
    )
except ImportError:
    # execution_runner starts this file directly, so package-relative imports
    # are unavailable in the child process.
    from runtime_token_tracker import (
        RuntimeTokenUsageTracker,
        track_openai_sdk_usage,
    )


GENERATED_PACKAGE_NAME = "rq4_generated_agent_package"


class InputTracker:
    """Provide one predefined value for each actual builtins.input() call."""

    encoding = "utf-8"

    def __init__(self, inputs: list[str]) -> None:
        self._inputs = inputs
        self.consumed_input_count = 0
        self.input_exhausted = False

    def _echo_predefined_input(self, value: str) -> None:
        """Write one visually separated user-input block to the transcript.

        The generated Agent still receives ``value`` unchanged. These labels
        affect only captured stdout, making the prompt before the input and
        the Agent output after it easy to distinguish during manual review.
        """
        input_index = self.consumed_input_count
        input_count = len(self._inputs)
        print("\n")
        print(
            "==================== "
            f"USER INPUT {input_index}/{input_count} "
            "===================="
        )
        print(value)
        print(
            "================== "
            f"END USER INPUT {input_index}/{input_count} "
            "=================="
        )
        print(
            "\n==================== "
            "AGENT OUTPUT "
            "===================="
        )

    def input(self, prompt: object = "") -> str:
        # Reproduce builtins.input(prompt) output so stdout contains the exact
        # prompt displayed by the generated Agent.
        if prompt:
            print(str(prompt), end="", flush=True)
        if self.consumed_input_count >= len(self._inputs):
            self.input_exhausted = True
            raise EOFError("The predefined testing inputs have been exhausted.")

        value = self._inputs[self.consumed_input_count]
        self.consumed_input_count += 1
        self._echo_predefined_input(value)
        sys.stdout.flush()
        return value

    def readline(self, size: int = -1) -> str:
        """Also track Agents that read directly from sys.stdin."""
        if self.consumed_input_count >= len(self._inputs):
            self.input_exhausted = True
            return ""

        value = self._inputs[self.consumed_input_count]
        self.consumed_input_count += 1
        self._echo_predefined_input(value)
        sys.stdout.flush()
        line = value + "\n"
        return line if size < 0 else line[:size]

    @staticmethod
    def isatty() -> bool:
        return False

    def report(self) -> dict[str, Any]:
        unused_count = len(self._inputs) - self.consumed_input_count
        return {
            "consumed_input_count": self.consumed_input_count,
            "unused_input_count": unused_count,
            "ended_before_all_inputs_consumed": unused_count > 0,
            "input_exhausted": self.input_exhausted,
        }


def _write_report(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _load_package_main(
    *,
    agent_directory: Path,
    main_path: Path,
) -> Any:
    """Load a generated package without using its directory name as Python.

    Compilation artifacts may live in directories such as ``agent.cnlp``.
    That is a valid filesystem name but not a valid Python identifier. The
    test subprocess therefore assigns one internal package name and points
    that package at the real artifact directory. Relative imports such as
    ``from .config import ...`` continue to work, while the experiment's
    external directory layout remains method-independent.
    """
    init_path = agent_directory / "__init__.py"
    package_specification = importlib.util.spec_from_file_location(
        GENERATED_PACKAGE_NAME,
        init_path,
        submodule_search_locations=[str(agent_directory)],
    )
    if (
        package_specification is None
        or package_specification.loader is None
    ):
        raise RuntimeError(
            f"Cannot load generated Agent package: {agent_directory}"
        )

    package_module = importlib.util.module_from_spec(package_specification)
    sys.modules[GENERATED_PACKAGE_NAME] = package_module
    package_specification.loader.exec_module(package_module)

    module = importlib.import_module(f"{GENERATED_PACKAGE_NAME}.main")
    if Path(module.__file__).resolve() != main_path.resolve():
        raise RuntimeError(
            "Generated Agent main module resolved outside its artifact "
            f"directory: {module.__file__}"
        )
    return module


def _run_agent(agent_directory: Path) -> None:
    main_path = agent_directory / "main.py"
    if not main_path.is_file():
        raise FileNotFoundError(
            f"Generated Agent has no root main.py: {agent_directory}"
        )

    if (agent_directory / "__init__.py").is_file():
        # Use an internal legal package name rather than deriving one from the
        # artifact directory. This supports both ``agent/`` and names such as
        # ``agent.cnlp/`` without changing generated relative imports.
        trial_directory = agent_directory.parent
        os.chdir(trial_directory)
        sys.path.insert(0, str(trial_directory))
        module = _load_package_main(
            agent_directory=agent_directory,
            main_path=main_path,
        )
    else:
        # A standalone artifact is loaded directly from its root main.py. It
        # may still import sibling modules because the Agent root is on
        # sys.path; a one-file model-generated Agent follows the same path.
        os.chdir(agent_directory)
        sys.path.insert(0, str(agent_directory))
        specification = importlib.util.spec_from_file_location(
            "rq4_generated_agent_main",
            main_path,
        )
        if specification is None or specification.loader is None:
            raise RuntimeError(f"Cannot import generated main.py: {main_path}")
        module = importlib.util.module_from_spec(specification)
        # Some valid standalone Agents use dataclasses, decorators, or other
        # import-time features that resolve their defining module through
        # sys.modules. Register the module before execution, matching Python's
        # normal import behavior instead of treating Codex-style one-file
        # artifacts as a special case.
        sys.modules[specification.name] = module
        try:
            specification.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(specification.name, None)
            raise

    main_function = getattr(module, "main", None)
    if not callable(main_function):
        raise RuntimeError(
            f"Generated Agent does not expose a callable main(): {main_path}"
        )
    main_function()


def _main() -> int:
    if len(sys.argv) != 2:
        print(
            "agent_process is an internal helper and expects one request file.",
            file=sys.stderr,
        )
        return 64

    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    agent_directory = Path(request["agent_directory"]).resolve()
    report_path = Path(request["report_path"]).resolve()
    runtime_token_usage_path = Path(
        request["runtime_token_usage_path"]
    ).resolve()
    inputs = request["inputs"]
    if not isinstance(inputs, list) or not all(
        isinstance(value, str) for value in inputs
    ):
        raise ValueError("Agent-process inputs must be a list of strings.")

    tracker = InputTracker(inputs)
    original_input = builtins.input
    original_stdin = sys.stdin
    runtime_exception: dict[str, str] | None = None
    exit_code = 0
    token_usage_tracker = RuntimeTokenUsageTracker(
        runtime_token_usage_path
    )

    try:
        builtins.input = tracker.input
        sys.stdin = tracker  # type: ignore[assignment]
        # Install before importing the generated Agent. Native, LangGraph,
        # Codex, and reference-code clients that use the OpenAI SDK therefore
        # pass through the same process-local measurement boundary.
        with track_openai_sdk_usage(token_usage_tracker):
            # Begin the human-review transcript with an explicit role marker.
            # InputTracker prints the same marker again after each injected
            # user-input block, so every interaction boundary remains clear.
            print(
                "==================== "
                "AGENT OUTPUT "
                "===================="
            )
            _run_agent(agent_directory)
    except SystemExit as exc:
        if exc.code not in (None, 0):
            exit_code = exc.code if isinstance(exc.code, int) else 1
            runtime_exception = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
    except BaseException as exc:
        exit_code = 1
        runtime_exception = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        traceback.print_exc()
    finally:
        builtins.input = original_input
        sys.stdin = original_stdin
        report = tracker.report()
        report["runtime_exception"] = runtime_exception
        report["runtime_token_usage"] = token_usage_tracker.snapshot()
        _write_report(report_path, report)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(_main())
