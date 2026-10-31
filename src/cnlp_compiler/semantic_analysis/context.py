from __future__ import annotations

from dataclasses import dataclass, field

from .environment import SemanticEnvironment
from .facts import SemanticFacts
from .flow_analysis import FlowAnalysisResult, VariableFlowAnalyzer
from .type_system import TypeRegistry


@dataclass
class RuleContext:
    facts: SemanticFacts
    environment: SemanticEnvironment
    _types: TypeRegistry | None = field(default=None, init=False, repr=False)
    _flow: FlowAnalysisResult | None = field(default=None, init=False, repr=False)

    @property
    def types(self) -> TypeRegistry:
        if self._types is None:
            self._types = TypeRegistry(
                self.facts.local_types,
                self.environment.schema_source,
            )
        return self._types

    @property
    def flow(self) -> FlowAnalysisResult:
        if self._flow is None:
            self._flow = VariableFlowAnalyzer().analyze(
                self.facts,
                self.environment,
            )
        return self._flow


__all__ = ["RuleContext"]
