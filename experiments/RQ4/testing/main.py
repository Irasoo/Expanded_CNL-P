from __future__ import annotations

from pathlib import Path

from .execution_runner import TestingResult, run_agent_tests as _run_agent_tests


__all__ = ["test_agents"]


def test_agents(
    *,
    rq4_directory: str | Path,
    generation_id: str,
    case_names: list[str] | None = None,
    methods: list[str] | None = None,
    repeat_count: int | None = None,
    timeout_max_retries: int = 0,
    timeout_retry_delay_seconds: float = 0,
    max_parallel_executions: int = 1,
) -> list[TestingResult]:
    """Test selected Agents from one generated compilation batch.

    Passing only generation_id runs every successful Case, method, and Trial
    in that batch. case_names and methods narrow the selection; repeat_count
    overrides each input group's local YAML repeat when it is not None.
    """
    return _run_agent_tests(
        rq4_directory=Path(rq4_directory).resolve(),
        generation_id=generation_id,
        case_names=case_names,
        methods=methods,
        repeat_count=repeat_count,
        timeout_max_retries=timeout_max_retries,
        timeout_retry_delay_seconds=timeout_retry_delay_seconds,
        max_parallel_executions=max_parallel_executions,
    )
