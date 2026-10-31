from __future__ import annotations

from dataclasses import dataclass

from .diagnostic import SemanticDiagnostic
from .environment import SemanticEnvironment
from .facts import (
    CommandFact,
    IfFact,
    LoopFact,
    SemanticFacts,
    SequenceFact,
    VariableReference,
    format_path,
)


@dataclass(frozen=True)
class VariableState:
    type_name: str
    is_global: bool = False


@dataclass
class _State:
    definite: dict[str, VariableState]
    partial: set[str]

    def copy(self) -> "_State":
        return _State(dict(self.definite), set(self.partial))


@dataclass(frozen=True)
class FlowAnalysisResult:
    diagnostics: tuple[SemanticDiagnostic, ...]
    command_states: dict[tuple[str, ...], dict[str, VariableState]]
    global_conflict_commands: frozenset[tuple[str, ...]]


class VariableFlowAnalyzer:
    """Reproduce the ICLR temporary-variable and branch-scope semantics."""

    def analyze(
        self,
        facts: SemanticFacts,
        environment: SemanticEnvironment,
    ) -> FlowAnalysisResult:
        diagnostics: list[SemanticDiagnostic] = []
        command_states: dict[tuple[str, ...], dict[str, VariableState]] = {}
        conflicts: set[tuple[str, ...]] = set()
        initial = {
            name: VariableState(variable.type_name, is_global=True)
            for name, variable in environment.global_variables.items()
        }

        for worker_name, flow in facts.worker_flows.items():
            state = _State(dict(initial), set())
            for input_name in facts.worker_inputs.get(worker_name, frozenset()):
                state.definite.setdefault(
                    input_name,
                    VariableState(
                        facts.declared_variables.get(input_name) or "UnKnown"
                    ),
                )
            self._sequence(
                flow,
                state,
                facts=facts,
                diagnostics=diagnostics,
                command_states=command_states,
                conflicts=conflicts,
                worker_name=worker_name,
            )

        return FlowAnalysisResult(
            diagnostics=tuple(diagnostics),
            command_states=command_states,
            global_conflict_commands=frozenset(conflicts),
        )

    def _sequence(
        self,
        sequence: SequenceFact,
        state: _State,
        *,
        facts: SemanticFacts,
        diagnostics: list[SemanticDiagnostic],
        command_states: dict[tuple[str, ...], dict[str, VariableState]],
        conflicts: set[tuple[str, ...]],
        worker_name: str,
    ) -> _State:
        for element in sequence.elements:
            if isinstance(element, CommandFact):
                command_states[element.path] = dict(state.definite)
                for reference in element.reads:
                    self._check_read(reference, state, facts, diagnostics)
                self._write(
                    element,
                    state,
                    facts=facts,
                    diagnostics=diagnostics,
                    conflicts=conflicts,
                )
            elif isinstance(element, IfFact):
                state = self._if(
                    element,
                    state,
                    facts=facts,
                    diagnostics=diagnostics,
                    command_states=command_states,
                    conflicts=conflicts,
                    worker_name=worker_name,
                )
            elif isinstance(element, LoopFact):
                for reference in element.condition_reads:
                    self._check_read(reference, state, facts, diagnostics)
                before = state.copy()
                after = self._sequence(
                    element.body,
                    state.copy(),
                    facts=facts,
                    diagnostics=diagnostics,
                    command_states=command_states,
                    conflicts=conflicts,
                    worker_name=worker_name,
                )
                newly_declared = set(after.definite) - set(before.definite)
                state = before
                state.partial.update(newly_declared)
                state.partial.update(after.partial)
        return state

    def _if(
        self,
        block: IfFact,
        state: _State,
        *,
        facts: SemanticFacts,
        diagnostics: list[SemanticDiagnostic],
        command_states: dict[tuple[str, ...], dict[str, VariableState]],
        conflicts: set[tuple[str, ...]],
        worker_name: str,
    ) -> _State:
        if not block.branches:
            return state
        branch_states: list[_State] = []
        for branch in block.branches:
            branch_state = state.copy()
            for reference in branch.condition_reads:
                self._check_read(reference, branch_state, facts, diagnostics)
            branch_states.append(
                self._sequence(
                    branch.body,
                    branch_state,
                    facts=facts,
                    diagnostics=diagnostics,
                    command_states=command_states,
                    conflicts=conflicts,
                    worker_name=worker_name,
                )
            )

        common_names = set(branch_states[0].definite)
        for branch_state in branch_states[1:]:
            common_names.intersection_update(branch_state.definite)
        definite = {
            name: branch_states[0].definite[name]
            for name in common_names
        }
        seen_anywhere = set(state.partial)
        for branch_state in branch_states:
            seen_anywhere.update(branch_state.partial)
            seen_anywhere.update(branch_state.definite)
        partial = seen_anywhere - common_names
        return _State(definite=definite, partial=partial)

    @staticmethod
    def _check_read(
        reference: VariableReference,
        state: _State,
        facts: SemanticFacts,
        diagnostics: list[SemanticDiagnostic],
    ) -> None:
        if reference.name in state.definite:
            return
        path = format_path(reference.path)
        if reference.name in state.partial:
            diagnostics.append(
                SemanticDiagnostic(
                    code="ICLR-SEM-005",
                    message=(
                        f"Variable '{reference.name}' is not declared in every "
                        "branch before this reference."
                    ),
                    path=path,
                    worker_name=reference.worker_name,
                    command_name=reference.command_name,
                )
            )
        elif reference.name in facts.declared_variables:
            diagnostics.append(
                SemanticDiagnostic(
                    code="ICLR-SEM-003",
                    message=(
                        f"Variable '{reference.name}' is referenced before its "
                        "temporary declaration."
                    ),
                    path=path,
                    worker_name=reference.worker_name,
                    command_name=reference.command_name,
                )
            )
        else:
            diagnostics.append(
                SemanticDiagnostic(
                    code="ICLR-SEM-003",
                    message=f"Variable '{reference.name}' is not declared.",
                    path=path,
                    worker_name=reference.worker_name,
                    command_name=reference.command_name,
                )
            )

    @staticmethod
    def _write(
        command: CommandFact,
        state: _State,
        *,
        facts: SemanticFacts,
        diagnostics: list[SemanticDiagnostic],
        conflicts: set[tuple[str, ...]],
    ) -> None:
        name = command.write_name
        if name is None:
            return
        if not command.write_is_declaration:
            if name in state.definite:
                return
            declared_type = facts.declared_variables.get(name)
            if declared_type is None:
                diagnostics.append(
                    SemanticDiagnostic(
                        code="ICLR-SEM-003",
                        message=f"Variable '{name}' is not declared.",
                        path=format_path(command.path),
                        worker_name=command.worker_name,
                        command_name=command.name,
                    )
                )
                return
            state.definite[name] = VariableState(declared_type)
            state.partial.discard(name)
            return
        existing = state.definite.get(name)
        if existing is not None and existing.is_global:
            conflicts.add(command.path)
            diagnostics.append(
                SemanticDiagnostic(
                    code="ICLR-SEM-014",
                    message=(
                        f"Temporary declaration '{name}' conflicts with the "
                        "instance's global variable of the same name."
                    ),
                    path=format_path(command.path),
                    worker_name=command.worker_name,
                    command_name=command.name,
                )
            )
            return
        if existing is not None or name in state.partial:
            diagnostics.append(
                SemanticDiagnostic(
                    code="ICLR-SEM-004",
                    message=f"Variable '{name}' is declared more than once.",
                    path=format_path(command.path),
                    worker_name=command.worker_name,
                    command_name=command.name,
                )
            )
            return
        state.definite[name] = VariableState(command.write_type_name or "UnKnown")


__all__ = [
    "FlowAnalysisResult",
    "VariableFlowAnalyzer",
    "VariableState",
]
