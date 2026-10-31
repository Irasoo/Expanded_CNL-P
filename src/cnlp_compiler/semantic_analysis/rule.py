from __future__ import annotations

from typing import Protocol

from .context import RuleContext
from .diagnostic import SemanticDiagnostic


class SemanticRule(Protocol):
    rule_id: str

    def check(self, context: RuleContext) -> list[SemanticDiagnostic]: ...


__all__ = ["SemanticRule"]
