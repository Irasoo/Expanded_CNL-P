"""Run this file directly in PyCharm; normal settings are below."""
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from RQ4.shared.batch import compilation_plan, create_batch, load_batch, write_json
from RQ4.compilation.main import compile_agents
from RQ4.shared.environment import load_runtime_environment
from RQ4.testing.main import test_agents


# "compile_only", "run_only", or "both". No command-line arguments required.
EXECUTION_MODE = "both"
REPRESENTATIONS = ["cnlp", "nl", "risen"]
CASE_NAMES = ["ab_test", "creative_concept_refinement", "github_project_navigator", "internal_comms"]

# Independent generations in this batch. Set NL and RISEN to 5 for five trials per group.
GENERATION_COUNTS = {
    "cnlp": {"native": 5, "langgraph": 5, "codex": 5},
    "nl": {"codex": 4},
    "risen": {"codex": 3},
}
GENERATION_TIMEOUT_SECONDS = 3600
COMPILATION_RETRY_POLICY = {"max_attempts": 20, "retry_delay_seconds": 180}
REPEAT_COUNT = 3
# Generation is always serial. Runtime slots are filled as executions finish.
MAX_PARALLEL_EXECUTIONS = {"cnlp": 1, "nl": 3, "risen": 4}
TESTING_RETRY_POLICY = {"timeout_max_retries": 5, "timeout_retry_delay_seconds": 30}

# Required only for run_only: select an existing batch.
BATCH_ID = ""


def main():
    if EXECUTION_MODE not in {"compile_only", "run_only", "both"}:
        raise ValueError("EXECUTION_MODE must be compile_only, run_only, or both.")
    load_runtime_environment()
    if EXECUTION_MODE == "run_only":
        root, manifest = load_batch(BATCH_ID)
        if not REPRESENTATIONS or len(set(REPRESENTATIONS)) != len(REPRESENTATIONS):
            raise ValueError("Select distinct representations.")
        for representation in REPRESENTATIONS:
            if representation not in manifest["representations"]:
                raise ValueError(f"Representation was not prepared in this batch: {representation}")
            if not manifest["representations"][representation]["generation_id"]:
                raise ValueError(f"No generation exists for {representation} in {BATCH_ID}.")
        if set(CASE_NAMES) - set(manifest["case_names"]):
            raise ValueError("Selected cases were not prepared in this batch.")
    else:
        root, manifest = create_batch(
            representations=REPRESENTATIONS, cases=CASE_NAMES,
            generation_counts=GENERATION_COUNTS, parallel_executions=MAX_PARALLEL_EXECUTIONS,
            repeat_count=REPEAT_COUNT,
        )
        manifest["generation_timeout_seconds"] = GENERATION_TIMEOUT_SECONDS
        manifest["compilation_retry_policy"] = dict(COMPILATION_RETRY_POLICY)
        manifest["testing_retry_policy"] = dict(TESTING_RETRY_POLICY)
        write_json(root / "batch_manifest.json", manifest)
    print(f"[RQ4] Batch: {root.name}", flush=True)

    for representation in REPRESENTATIONS:
        experiment_directory = root / representation
        state = manifest["representations"][representation]
        print(f"[RQ4] Representation: {representation}", flush=True)
        if EXECUTION_MODE != "run_only":
            state["generation_id"] = compile_agents(
                rq4_directory=experiment_directory,
                compilation_plan=compilation_plan(root, representation, CASE_NAMES,
                                                   state["generation_counts"], GENERATION_TIMEOUT_SECONDS),
                retry_policy=COMPILATION_RETRY_POLICY,
            )
            write_json(root / "batch_manifest.json", manifest)
        if EXECUTION_MODE != "compile_only":
            results = test_agents(
                rq4_directory=experiment_directory, generation_id=state["generation_id"],
                case_names=CASE_NAMES, methods=list(state["generation_counts"]),
                repeat_count=REPEAT_COUNT,
                max_parallel_executions=MAX_PARALLEL_EXECUTIONS[representation],
                **TESTING_RETRY_POLICY,
            )
            if results:
                state["testing_ids"].append(results[0]["testing_id"])
                write_json(root / "batch_manifest.json", manifest)
            completed = sum(result["status"] == "completed" for result in results)
            print(f"[{representation}] {completed}/{len(results)} processes completed; "
                  "business success requires review.", flush=True)


if __name__ == "__main__":
    main()
