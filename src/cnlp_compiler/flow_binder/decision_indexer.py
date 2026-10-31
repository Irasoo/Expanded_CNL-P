from __future__ import annotations

import copy
import re
from typing import Any


_DECISION_PATTERNS = (
    re.compile(r"^if_block\d+$"),
    re.compile(r"^while_block\d+$"),
    re.compile(r"^for_block\d+$"),
)


def build_decision_indexed_worker_ast(
    worker_ast: dict[str, Any],
) -> dict[str, Any]:
    """Return a normalized Worker copy with stable Decision indices.

    This is AST normalization owned by flow binding, not an AST query.  The
    caller's object is never mutated.  Existing positive indices are kept and
    missing indices are allocated in structural traversal order.
    """
    if not isinstance(worker_ast, dict):
        raise TypeError("worker_ast must be a dictionary.")

    indexed_worker = copy.deepcopy(worker_ast)
    used_indices: set[int] = set()

    def is_decision(key: str, value: Any) -> bool:
        return isinstance(value, dict) and any(
            pattern.fullmatch(key) is not None
            for pattern in _DECISION_PATTERNS
        )

    def collect_existing(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if is_decision(key, child):
                    raw_index = child.get("decision_index")
                    if raw_index is not None:
                        decision_index = _coerce_decision_index(raw_index)
                        if decision_index in used_indices:
                            raise ValueError(
                                f"Duplicate decision_index: {decision_index}."
                            )
                        used_indices.add(decision_index)
                        child["decision_index"] = decision_index
                collect_existing(child)
        elif isinstance(value, list):
            for child in value:
                collect_existing(child)

    next_index = 1

    def assign_missing(value: Any) -> None:
        nonlocal next_index
        if isinstance(value, dict):
            for key, child in value.items():
                if is_decision(key, child) and "decision_index" not in child:
                    while next_index in used_indices:
                        next_index += 1
                    child["decision_index"] = next_index
                    used_indices.add(next_index)
                    next_index += 1
                assign_missing(child)
        elif isinstance(value, list):
            for child in value:
                assign_missing(child)

    collect_existing(indexed_worker)
    assign_missing(indexed_worker)
    return indexed_worker


def _coerce_decision_index(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Boolean values cannot be used as decision_index.")
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str):
        match = re.search(r"(\d+)$", value.strip())
        if match and int(match.group(1)) > 0:
            return int(match.group(1))
    raise ValueError(f"Invalid decision_index value: {value!r}.")


__all__ = ["build_decision_indexed_worker_ast"]
