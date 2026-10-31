from __future__ import annotations

import io
import re
import sys
import threading
import time
from contextlib import contextmanager, redirect_stdout
from collections.abc import Iterator
from typing import TextIO


class _CompilerTraceStream(io.TextIOBase):
    """Collect detailed compiler output and forward complete lines as events."""

    def __init__(self, display: "CompactCompilerProgress") -> None:
        self._display = display
        self._buffer = ""

    def writable(self) -> bool:
        return True

    def write(self, value: str) -> int:
        self._buffer += value
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._display.consume(line.rstrip("\r"))
        return len(value)

    def flush(self) -> None:
        if self._buffer:
            self._display.consume(self._buffer.rstrip("\r"))
            self._buffer = ""


class CompactCompilerProgress:
    """Render two compact progress lines while retaining the detailed trace."""

    _BAR_WIDTH = 24
    _REQUEST_NUMBER = re.compile(r"Request\s+(\d+)")
    _COMMAND_PROGRESS = re.compile(r"Commands\]\s+(\d+)/(\d+)")
    _PREDICATE_PROGRESS = re.compile(r"Predicates\]\s+(\d+)/(\d+)")

    def __init__(
        self,
        *,
        terminal: TextIO | None = None,
    ) -> None:
        self._terminal = terminal or sys.stdout
        self._trace: list[str] = []
        self._phase = "analysis"
        self._percent = 0
        self._status = "starting"
        self._phase_started_at = time.monotonic()
        self._last_width = 0
        self._finished = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._ticker: threading.Thread | None = None

    @staticmethod
    def _elapsed_text(elapsed_seconds: float) -> str:
        elapsed = max(0, round(elapsed_seconds))
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _phase_label(self) -> str:
        if self._phase == "implementation":
            return "Implementation"
        return "Analysis + Planning"

    def _bar(self) -> str:
        completed = round(self._BAR_WIDTH * self._percent / 100)
        return "#" * completed + "-" * (self._BAR_WIDTH - completed)

    def _render(self, *, final: bool = False) -> None:
        if self._phase is None:
            return
        elapsed = self._elapsed_text(time.monotonic() - self._phase_started_at)
        status = self._status
        if len(status) > 48:
            status = status[:45] + "..."
        message = (
            f"[Compiler][{self._phase_label()}] [{self._bar()}] "
            f"{self._percent:3d}% | {status} | elapsed {elapsed}"
        )
        padded = message.ljust(self._last_width)
        self._last_width = max(self._last_width, len(message))
        self._terminal.write("\r" + padded)
        if final:
            self._terminal.write("\n")
            self._last_width = 0
        self._terminal.flush()

    def _set_progress(
        self,
        percent: int,
        status: str,
        *,
        final: bool = False,
    ) -> None:
        with self._lock:
            self._percent = max(self._percent, min(100, percent))
            self._status = status
            self._render(final=final)

    def _begin_implementation(self) -> None:
        with self._lock:
            if self._phase == "analysis":
                self._percent = 100
                self._status = "completed"
                self._render(final=True)
            self._phase = "implementation"
            self._percent = 0
            self._status = "starting"
            self._phase_started_at = time.monotonic()
            self._render()

    def _ticker_loop(self) -> None:
        while not self._stop_event.wait(1.0):
            with self._lock:
                if not self._finished and self._phase is not None:
                    self._render()

    def start(self) -> None:
        with self._lock:
            self._render()
        self._ticker = threading.Thread(
            target=self._ticker_loop,
            daemon=True,
        )
        self._ticker.start()

    def consume(self, line: str) -> None:
        if not line:
            return
        self._trace.append(line)

        if "[Stage 1/4][Parsing] Started" in line:
            self._set_progress(5, "parsing CNL-P")
        elif "[Stage 1/4][Parsing] Completed" in line:
            self._set_progress(15, "CNL-P parsed")
        elif "[Stage 2/4][Flow Binding] Started" in line:
            self._set_progress(20, "binding Worker flows")
        elif "[Stage 2/4][Flow Binding] Completed" in line:
            self._set_progress(30, "Worker flows bound")
        elif "[Stage 3/4][Planning] Started" in line:
            self._set_progress(35, "planning implementations")
        elif "Summarizing descriptions" in line:
            self._set_progress(45, "summarizing Call API semantics")
        elif "Description summary completed" in line:
            self._set_progress(55, "Call API semantics summarized")
        elif "searching Reference Code Catalog" in line:
            self._set_progress(65, "searching Reference Code Catalog")
        elif "adaptation analysis started" in line:
            self._set_progress(75, "planning reference adaptation")
        elif "[Compiler][LLM] Request" in line:
            match = self._REQUEST_NUMBER.search(line)
            request_name = (
                f"LLM request {match.group(1)}"
                if match is not None
                else "LLM request"
            )
            request_state = (
                "running" if " started:" in line else "completed"
            )
            self._set_progress(
                self._percent,
                f"{request_name} {request_state}",
            )
        elif "[Stage 3/4][Planning] Completed" in line:
            self._set_progress(100, "completed", final=True)
            with self._lock:
                self._phase = None
        elif "[Stage 4/4][Implementation] Started" in line:
            self._begin_implementation()
        elif "[Implementation][Native] Static files" in line or (
            "[Implementation][LangGraph] Static files" in line
        ):
            self._set_progress(10, "collecting static files")
        elif "schema.py" in line and "[Implementation]" in line:
            self._set_progress(20, "generating schema.py")
        elif "config.py" in line and "[Implementation]" in line:
            self._set_progress(30, "generating config.py")
        elif "[Implementation][Commands]" in line:
            match = self._COMMAND_PROGRESS.search(line)
            percent = 55
            if match is not None:
                current, total = map(int, match.groups())
                percent = 35 + round(30 * current / max(total, 1))
            self._set_progress(percent, "generating commands.py")
        elif "[Implementation][Predicates]" in line:
            match = self._PREDICATE_PROGRESS.search(line)
            percent = 75
            if match is not None:
                current, total = map(int, match.groups())
                percent = 68 + round(12 * current / max(total, 1))
            self._set_progress(percent, "generating predicates.py")
        elif "Worker control" in line or "workflow.py and main.py" in line:
            self._set_progress(88, "generating workflow control")
        elif "[Implementation][Native] main.py" in line:
            self._set_progress(92, "generating main.py")
        elif "[Stage 4/4][Implementation] Completed" in line:
            self._set_progress(95, "writing generated Agent")
        elif "Generated Agent was written successfully" in line:
            self._set_progress(100, "completed", final=True)
            with self._lock:
                self._phase = None
        elif "[Compiler][Summary] Compilation succeeded" in line:
            if self._phase is not None:
                self._set_progress(100, "completed", final=True)
                with self._lock:
                    self._phase = None

    def finish(self, *, succeeded: bool) -> None:
        self._stop_event.set()
        if self._ticker is not None:
            self._ticker.join(timeout=2)
        with self._lock:
            if self._phase is not None:
                self._percent = 100 if succeeded else self._percent
                self._status = "completed" if succeeded else "failed"
                self._render(final=True)
                self._phase = None
            self._finished = True
    @property
    def trace(self) -> tuple[str, ...]:
        return tuple(self._trace)

    @contextmanager
    def capture(self) -> Iterator[None]:
        """Replace verbose compiler stdout with the compact two-phase view."""
        stream = _CompilerTraceStream(self)
        self.start()
        try:
            with redirect_stdout(stream):
                yield
        except BaseException:
            stream.flush()
            self.finish(succeeded=False)
            raise
        else:
            stream.flush()
            self.finish(succeeded=True)

