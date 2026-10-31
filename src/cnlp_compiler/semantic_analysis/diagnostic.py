from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticDiagnostic:
    """One deterministic compiler-style semantic diagnostic."""

    code: str
    message: str
    path: str
    worker_name: str | None = None
    command_name: str | None = None


@dataclass(frozen=True)
class SemanticReport:
    diagnostics: tuple[SemanticDiagnostic, ...]

    @property
    def has_errors(self) -> bool:
        return bool(self.diagnostics)

    def by_code(self, code: str) -> tuple[SemanticDiagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.code == code)


__all__ = ["SemanticDiagnostic", "SemanticReport"]
