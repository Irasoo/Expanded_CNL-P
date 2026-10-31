"""Prepare human reviews, then recompute final-attempt correctness and tokens."""
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from RQ4.shared.batch import load_batch
from RQ4.shared.metrics import process_testing_batch

BATCH_ID = ""
# Blank testing_id selects the latest testing invocation registered for that
# representation. Supply an explicit ID to process a different invocation.
RESULT_PLANS = [
    {"representation": "cnlp", "testing_id": ""},
    {"representation": "nl", "testing_id": ""},
    {"representation": "risen", "testing_id": ""},
]


def main():
    root, manifest = load_batch(BATCH_ID)
    for plan in RESULT_PLANS:
        representation = plan["representation"]
        state = manifest["representations"][representation]
        if not state["testing_ids"]:
            raise ValueError(f"No tests recorded for {representation}.")
        testing_id = plan["testing_id"] or state["testing_ids"][-1]
        if testing_id not in state["testing_ids"]:
            raise ValueError(f"Unregistered testing batch: {representation}/{testing_id}")
        output, summary = process_testing_batch(root / representation, state["generation_id"], testing_id)
        pending = sum(group["pending_review_count"] for group in summary["testing"].values())
        print(f"[{representation}] Results: {output}; awaiting human review: {pending}")


if __name__ == "__main__":
    main()
