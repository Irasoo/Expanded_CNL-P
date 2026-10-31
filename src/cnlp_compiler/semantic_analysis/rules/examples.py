from __future__ import annotations

from collections.abc import Iterator

from ..context import RuleContext
from ..diagnostic import SemanticDiagnostic
from ..facts import CommandFact, IfFact, LoopFact, SequenceFact, format_path


def _display_command(name: str) -> str:
    if name.startswith("command") and name[7:].isdigit():
        return f"COMMAND-{int(name[7:])}"
    return name


def _commands_in_sequence(sequence: SequenceFact) -> frozenset[str]:
    commands: set[str] = set()
    for element in sequence.elements:
        if isinstance(element, CommandFact):
            commands.add(element.name)
        elif isinstance(element, IfFact):
            for branch in element.branches:
                commands.update(_commands_in_sequence(branch.body))
        elif isinstance(element, LoopFact):
            commands.update(_commands_in_sequence(element.body))
    return frozenset(commands)


def _if_blocks(sequence: SequenceFact) -> Iterator[IfFact]:
    for element in sequence.elements:
        if isinstance(element, IfFact):
            yield element
            for branch in element.branches:
                yield from _if_blocks(branch.body)
        elif isinstance(element, LoopFact):
            yield from _if_blocks(element.body)


class ExampleMutuallyExclusiveBranchesRule:
    """Task 015: one Example path cannot enter two branches of one IF."""

    rule_id = "TOSEM-SEM-EXAMPLE-MUTUALLY-EXCLUSIVE-BRANCHES"

    def check(self, context: RuleContext) -> list[SemanticDiagnostic]:
        diagnostics: list[SemanticDiagnostic] = []
        for example in context.facts.examples:
            flow = context.facts.worker_flows.get(example.worker_name)
            if flow is None:
                continue
            path_commands = set(example.execution_path)
            for if_block in _if_blocks(flow):
                selected_branches: list[frozenset[str]] = []
                for branch in if_block.branches:
                    selected = _commands_in_sequence(branch.body) & path_commands
                    if selected:
                        selected_branches.append(selected)
                if len(selected_branches) < 2:
                    continue
                selected_names = sorted(
                    _display_command(command)
                    for branch in selected_branches
                    for command in branch
                )
                diagnostics.append(
                    SemanticDiagnostic(
                        code="TOSEM-SEM-015",
                        message=(
                            "Example execution path combines commands from "
                            "mutually exclusive branches: "
                            + ", ".join(selected_names)
                            + "."
                        ),
                        path=format_path((*example.path, "execution-path")),
                        worker_name=example.worker_name,
                    )
                )
        return diagnostics


class ExampleCommandExistsRule:
    """Task 016: every Example path command exists in its owning Worker."""

    rule_id = "TOSEM-SEM-EXAMPLE-COMMAND-EXISTS"

    def check(self, context: RuleContext) -> list[SemanticDiagnostic]:
        diagnostics: list[SemanticDiagnostic] = []
        commands_by_worker: dict[str, set[str]] = {}
        for command in context.facts.commands:
            commands_by_worker.setdefault(command.worker_name, set()).add(command.name)
        for example in context.facts.examples:
            known = commands_by_worker.get(example.worker_name, set())
            missing = sorted(set(example.execution_path) - known)
            if not missing:
                continue
            diagnostics.append(
                SemanticDiagnostic(
                    code="TOSEM-SEM-016",
                    message=(
                        "Example execution path references command(s) that do "
                        f"not exist in Worker '{example.worker_name}': "
                        + ", ".join(_display_command(name) for name in missing)
                        + "."
                    ),
                    path=format_path((*example.path, "execution-path")),
                    worker_name=example.worker_name,
                )
            )
        return diagnostics


class ExampleOutputPathConsistencyRule:
    """Task 017: an Expected output must be produced on its stated path."""

    rule_id = "TOSEM-SEM-EXAMPLE-OUTPUT-PATH-CONSISTENCY"

    def check(self, context: RuleContext) -> list[SemanticDiagnostic]:
        diagnostics: list[SemanticDiagnostic] = []
        producers: dict[tuple[str, str], set[str]] = {}
        for command in context.facts.commands:
            if command.write_name is None:
                continue
            producers.setdefault(
                (command.worker_name, command.write_name), set()
            ).add(command.name)

        for example in context.facts.examples:
            if example.kind != "expected":
                continue
            path_commands = set(example.execution_path)
            worker_inputs = context.facts.worker_inputs.get(
                example.worker_name, frozenset()
            )
            for output_name in sorted(example.outputs):
                if output_name in worker_inputs:
                    continue
                possible_producers = producers.get(
                    (example.worker_name, output_name), set()
                )
                if possible_producers & path_commands:
                    continue
                producer_names = ", ".join(
                    _display_command(name) for name in sorted(possible_producers)
                )
                if producer_names:
                    detail = f"; its producer is {producer_names}"
                else:
                    detail = "; no command in the Worker produces it"
                diagnostics.append(
                    SemanticDiagnostic(
                        code="TOSEM-SEM-017",
                        message=(
                            f"Expected output '{output_name}' is not produced "
                            f"by the Example execution path{detail}."
                        ),
                        path=format_path((*example.path, "expected-output")),
                        worker_name=example.worker_name,
                    )
                )
        return diagnostics


__all__ = [
    "ExampleCommandExistsRule",
    "ExampleMutuallyExclusiveBranchesRule",
    "ExampleOutputPathConsistencyRule",
]
