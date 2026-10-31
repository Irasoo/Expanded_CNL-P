from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from typing_extensions import NotRequired, TypedDict

from .code_generator import CodeGenerator
from .code_generator.reference_code_catalog import ReferenceCodeCatalog
from .flow_binder import FlowBinder
from .parser import ParserLike
from .progress import CompactCompilerProgress
from .schema import Failure, ImplementationPlan, ModelConfig, StopProcess
from .utils.llm import (
    CompilationTokenUsageReport,
    track_compilation_token_usage,
)


class CompilerConfig(TypedDict):
    """Configuration consumed by the top-level CNL-P compiler."""

    model_config: ModelConfig
    target_implementation: NotRequired[str]


class CNLPParseError(ValueError):
    """Raised when parser diagnostics prevent subsequent compilation."""

    def __init__(self, diagnostics: tuple[Failure[Any], ...]) -> None:
        self.diagnostics = diagnostics
        details = "\n".join(
            self._format_diagnostic(diagnostic)
            for diagnostic in diagnostics
        )
        super().__init__(
            "CNL-P parsing failed."
            + (f"\n{details}" if details else "")
        )

    @staticmethod
    def _format_diagnostic(diagnostic: Failure[Any]) -> str:
        location = (
            f"line {diagnostic.start_line}: "
            if diagnostic.start_line is not None
            else ""
        )
        return f"- {location}{diagnostic.message}"


class CNLPCompiler:
    """Coordinate parsing, Worker flow binding, and code generation."""

    def __init__(
        self,
        *,
        parser: ParserLike | None = None,
        flow_binder: FlowBinder | None = None,
        code_generator: CodeGenerator | None = None,
        reference_code_catalog: ReferenceCodeCatalog | None = None,
        code_generator_config: dict[str, Any] | None = None,
    ) -> None:
        self.parser = parser or ParserLike()
        self.flow_binder = flow_binder or FlowBinder()
        self.code_generator = code_generator or CodeGenerator(
            config=dict(code_generator_config or {}),
            reference_code_catalog=reference_code_catalog,
        )
        self.last_diagnostics: tuple[Failure[Any], ...] = ()
        # Convenience view of the most recently finished compile or plan call.
        # Each invocation replaces this snapshot; it is not a process-wide
        # accumulator and should not be shared by concurrent experiments.
        self.last_token_usage: CompilationTokenUsageReport | None = None
        # Full internal messages from the latest compile. The terminal receives
        # only the compact progress view, while experiment runners can persist
        # this trace for later debugging without losing information.
        self.last_compilation_trace: tuple[str, ...] = ()

    def compile(
        self,
        cnlp_text: str,
        config: CompilerConfig,
        *,
        output_directory: str | Path | None = None,
    ) -> str | bytes:
        """Compile to a directory, or return ZIP bytes when no path is given."""
        # A new ContextVar-backed session is created for every invocation. All
        # OpenaiClient instances created by FlowBinder, Planner, and
        # Implementer discover this same session through utils.llm.
        compilation_started_at = time.monotonic()
        compilation_status = "failed"
        progress = CompactCompilerProgress()
        try:
            with progress.capture():
                with track_compilation_token_usage() as token_usage_session:
                    try:
                        result = self._compile_once(
                            cnlp_text=cnlp_text,
                            config=config,
                            output_directory=output_directory,
                        )
                        compilation_status = "succeeded"
                        return result
                    finally:
                        # Preserve usage even when parsing, planning,
                        # implementation, validation, or output writing raises.
                        self.last_token_usage = token_usage_session.snapshot()
                        duration = time.monotonic() - compilation_started_at
                        print(
                            "[Compiler][Summary] Compilation "
                            f"{compilation_status} in {duration:.2f}s; "
                            "LLM requests="
                            f"{self.last_token_usage['request_count']}; "
                            "total tokens="
                            f"{self.last_token_usage['total']['total_tokens']}.",
                            flush=True,
                        )
        finally:
            self.last_compilation_trace = progress.trace

    def plan(self, cnlp_text: str) -> ImplementationPlan:
        """Run through Planning and return its result without implementation."""
        planning_started_at = time.monotonic()
        planning_status = "failed"
        progress = CompactCompilerProgress()
        try:
            with progress.capture():
                with track_compilation_token_usage() as token_usage_session:
                    try:
                        cnlp_ast, _ = self._prepare(cnlp_text=cnlp_text)
                        result = self.code_generator.plan(
                            cnlp_script=cnlp_text,
                            cnlp_ast=cnlp_ast,
                        )
                        planning_status = "succeeded"
                        return result
                    finally:
                        self.last_token_usage = token_usage_session.snapshot()
                        duration = time.monotonic() - planning_started_at
                        print(
                            "[Compiler][Summary] Planning "
                            f"{planning_status} in {duration:.2f}s; "
                            "LLM requests="
                            f"{self.last_token_usage['request_count']}; "
                            "total tokens="
                            f"{self.last_token_usage['total']['total_tokens']}.",
                            flush=True,
                        )
        finally:
            self.last_compilation_trace = progress.trace

    def _compile_once(
        self,
        *,
        cnlp_text: str,
        config: CompilerConfig,
        output_directory: str | Path | None,
    ) -> str | bytes:
        """Run the existing compilation pipeline inside an active tracker."""
        model_config, target_implementation = self._resolve_config(config)
        print(
            "[Compiler] Compilation started; "
            f"target implementation={target_implementation}.",
            flush=True,
        )
        cnlp_ast, binding_table = self._prepare(
            cnlp_text=cnlp_text,
        )
        virtual_files = self.code_generator.generate(
            cnlp_script=cnlp_text,
            cnlp_ast=cnlp_ast,
            binding_table=binding_table,
            model_config=model_config,
            target_implementation=target_implementation,
        )
        if output_directory is None:
            print(
                "[Compiler][Output] Packaging generated Agent as ZIP bytes...",
                flush=True,
            )
            return virtual_files.to_zip()

        print(
            f"[Compiler][Output] Writing generated Agent to "
            f"{output_directory}...",
            flush=True,
        )
        output_path = virtual_files.write_to_directory(output_directory)
        print(
            "[Compiler][Output] Generated Agent was written successfully.",
            flush=True,
        )
        return f"编译后的 Agent 已输出到：{output_path}"

    def _prepare(
        self,
        *,
        cnlp_text: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        parsing_started_at = time.monotonic()
        print("[Compiler][Stage 1/4][Parsing] Started.", flush=True)
        cnlp_ast = self._parse(cnlp_text)
        workers = cnlp_ast.get("workers", {})
        worker_count = len(workers) if isinstance(workers, dict) else 0
        print(
            "[Compiler][Stage 1/4][Parsing] Completed in "
            f"{time.monotonic() - parsing_started_at:.2f}s; "
            f"AST contains {worker_count} Worker(s).",
            flush=True,
        )

        binding_started_at = time.monotonic()
        print(
            "[Compiler][Stage 2/4][Flow Binding] Started for "
            f"{worker_count} Worker(s).",
            flush=True,
        )
        binding_table = self._bind_worker_flows(
            cnlp_ast=cnlp_ast,
        )
        print(
            "[Compiler][Stage 2/4][Flow Binding] Completed in "
            f"{time.monotonic() - binding_started_at:.2f}s.",
            flush=True,
        )

        return cnlp_ast, binding_table

    def _parse(self, cnlp_text: str) -> dict[str, Any]:
        if not isinstance(cnlp_text, str):
            raise TypeError("cnlp_text must be a string.")
        if not cnlp_text.strip():
            raise ValueError("cnlp_text must not be empty.")

        parse_result = self.parser.syntax_analysis(cnl_p=cnlp_text)
        self.last_diagnostics = tuple(parse_result.errors)
        fatal_diagnostics = tuple(
            diagnostic
            for diagnostic in parse_result.errors
            if diagnostic.is_fatal
        )
        if isinstance(parse_result, StopProcess) or fatal_diagnostics:
            raise CNLPParseError(
                fatal_diagnostics or self.last_diagnostics
            )
        if not isinstance(parse_result.value, dict):
            raise TypeError("The parser did not return a CNL-P AST object.")
        return parse_result.value

    def _bind_worker_flows(
        self,
        *,
        cnlp_ast: dict[str, Any],
    ) -> dict[str, Any]:
        workers = cnlp_ast.get("workers")
        if not isinstance(workers, dict) or not workers:
            raise ValueError("The CNL-P AST does not contain any Workers.")
        binding_table: dict[str, Any] = {}
        worker_count = len(workers)
        for worker_index, (worker_name, worker_ast) in enumerate(
            workers.items(),
            start=1,
        ):
            print(
                "[Compiler][Stage 2/4][Flow Binding] Worker "
                f"{worker_index}/{worker_count} {worker_name}: started.",
                flush=True,
            )
            binding_table[worker_name] = self.flow_binder.bind(
                worker_ast,
            )
            print(
                "[Compiler][Stage 2/4][Flow Binding] Worker "
                f"{worker_index}/{worker_count} {worker_name}: completed.",
                flush=True,
            )
        return binding_table

    @staticmethod
    def _resolve_config(
        config: CompilerConfig,
    ) -> tuple[ModelConfig, str]:
        if not isinstance(config, dict):
            raise TypeError("config must be a CompilerConfig object.")

        model_config = config.get("model_config")
        if not isinstance(model_config, dict):
            raise ValueError("config.model_config is required.")

        normalized_model_config: ModelConfig = {
            "api_key": CNLPCompiler._required_string(
                model_config,
                "api_key",
            ),
            "model_name": CNLPCompiler._required_string(
                model_config,
                "model_name",
            ),
            "base_url": CNLPCompiler._required_string(
                model_config,
                "base_url",
            ),
        }
        # TODO(Native main switch): Set target_implementation to "native" for
        # deterministic PC/while/match generation. Set it to
        # "native_llm_main" only when explicitly comparing with the preserved
        # compiler-time LLM Main generator.
        # TODO(Native config switch): Use "native_llm_config" only to compare
        # against the preserved LLM-generated config.py. The default "native"
        # target generates both config.py and main.py deterministically.
        target_implementation = config.get(
            "target_implementation",
            "native",
        )
        if (
            not isinstance(target_implementation, str)
            or not target_implementation.strip()
        ):
            raise ValueError(
                "config.target_implementation must be a non-empty string."
            )
        return normalized_model_config, target_implementation

    @staticmethod
    def _required_string(values: dict[str, Any], field_name: str) -> str:
        value = values.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"config.model_config.{field_name} must be a non-empty string."
            )
        return value


__all__ = [
    "CNLPCompiler",
    "CNLPParseError",
    "CompilerConfig",
]
