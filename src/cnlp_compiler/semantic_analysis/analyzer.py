from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..parser import ParserLike
from .context import RuleContext
from .diagnostic import SemanticDiagnostic, SemanticReport
from .environment import SemanticEnvironment
from .facts import SemanticFactCollector
from .rule import SemanticRule
from .rules import DEFAULT_RULES


class SemanticAnalyzer:
    """Standalone rule runner over the TOSEM Parser AST."""

    def __init__(self, rules: Iterable[SemanticRule] | None = None) -> None:
        self.rules = tuple(DEFAULT_RULES if rules is None else rules)
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Semantic rule IDs must be unique.")
        self.collector = SemanticFactCollector()

    def analyze(
        self,
        cnlp_ast: dict[str, Any],
        *,
        global_variables: str | dict[str, Any] | None = None,
        apis: str | dict[str, Any] | None = None,
        schema: str | None = None,
    ) -> SemanticReport:
        environment = SemanticEnvironment.from_raw(
            global_variables=global_variables,
            apis=apis,
            schema=schema,
        )
        context = RuleContext(
            facts=self.collector.collect(cnlp_ast),
            environment=environment,
        )
        diagnostics: list[SemanticDiagnostic] = []
        for rule in self.rules:
            diagnostics.extend(rule.check(context))
        return SemanticReport(
            tuple(
                sorted(
                    diagnostics,
                    key=lambda item: (item.path, item.code, item.message),
                )
            )
        )

    def analyze_source(
        self,
        cnlp: str,
        *,
        global_variables: str | dict[str, Any] | None = None,
        apis: str | dict[str, Any] | None = None,
        schema: str | None = None,
    ) -> SemanticReport:
        """Convenience entry point; it is not connected to CNLPCompiler."""

        parse_result = ParserLike().syntax_analysis(cnl_p=cnlp)
        if parse_result.errors:
            messages = "; ".join(error.message for error in parse_result.errors)
            raise ValueError(
                "CNL-P must pass TOSEM Parser before semantic analysis: " + messages
            )
        if not isinstance(parse_result.value, dict):
            raise ValueError("TOSEM Parser did not produce a CNL-P AST.")
        return self.analyze(
            parse_result.value,
            global_variables=global_variables,
            apis=apis,
            schema=schema,
        )


__all__ = ["SemanticAnalyzer"]
