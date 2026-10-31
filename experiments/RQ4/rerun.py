"""Append new attempts to selected runs without regenerating the Agent."""
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from RQ4.shared.batch import load_batch
from RQ4.shared.environment import load_runtime_environment
from RQ4.testing.rerun_failed_tests import rerun_failed_tests
from RQ4.testing.rerun_selected_tests import _resolve_run_directory, rerun_selected_tests


BATCH_ID = ""
MAX_PARALLEL_EXECUTIONS = 3
# mode="failed": rerun process failures/timeouts, NOT business failures.
# mode="selected": rerun the specified execution directories.
RERUN_PLANS = [
    # {"representation": "nl", "testing_id": "20261030_120000", "mode": "selected",
    #  "run_directories": ["ab_test/codex_1in4/inconclusive/run_001"]},
]


def main():
    if not RERUN_PLANS:
        raise ValueError("Fill BATCH_ID and RERUN_PLANS before running rerun.py.")
    root, manifest = load_batch(BATCH_ID)
    load_runtime_environment()
    # Validate all paths and duplicate selections before any execution starts.
    prepared = []
    selected_paths = set()
    for plan in RERUN_PLANS:
        representation = plan["representation"]
        if representation not in manifest["representations"]:
            raise ValueError(f"Representation not in this batch: {representation}")
        state = manifest["representations"][representation]
        if plan["testing_id"] not in state["testing_ids"]:
            raise ValueError(f"Testing batch not registered for {representation}: {plan['testing_id']}")
        if plan["mode"] not in {"selected", "failed"}:
            raise ValueError("Rerun mode must be selected or failed.")
        if plan["mode"] == "selected":
            directories = plan.get("run_directories", [])
            if not directories or len(set(directories)) != len(directories):
                raise ValueError("Select one or more distinct Run directories.")
            testing_directory = root / representation / "results" / state["generation_id"] / plan["testing_id"]
            for relative in directories:
                _resolve_run_directory(testing_directory=testing_directory, raw_directory=relative)
        identity = (representation, plan["testing_id"])
        if identity in selected_paths:
            raise ValueError("Use one rerun plan per representation/testing batch.")
        selected_paths.add(identity)
        prepared.append((plan, state))
    for plan, state in prepared:
        arguments = dict(rq4_directory=root / plan["representation"],
                         generation_id=state["generation_id"], testing_id=plan["testing_id"],
                         max_parallel_executions=MAX_PARALLEL_EXECUTIONS)
        if plan["mode"] == "failed":
            rerun_failed_tests(**arguments)
        else:
            rerun_selected_tests(**arguments, run_directories=plan["run_directories"])


if __name__ == "__main__":
    main()
