"""Export selected Run directories, including retained attempts, to one ZIP."""
from datetime import datetime
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from RQ4.shared.batch import load_batch
from RQ4.testing.rerun_selected_tests import _resolve_run_directory

BATCH_ID = ""
EXPORT_PLANS = [
    # {"representation": "nl", "testing_id": "20261030_120000",
    #  "run_directories": ["ab_test/codex_1in4/inconclusive/run_001"]},
]


def main():
    if not EXPORT_PLANS:
        raise ValueError("Fill BATCH_ID and EXPORT_PLANS before exporting results.")
    root, manifest = load_batch(BATCH_ID)
    selected, used_paths = [], set()
    for plan in EXPORT_PLANS:
        state = manifest["representations"][plan["representation"]]
        if plan["testing_id"] not in state["testing_ids"]:
            raise ValueError(f"Testing ID not registered: {plan['testing_id']}")
        if not plan["run_directories"]:
            raise ValueError("Select at least one Run per export plan.")
        testing = root / plan["representation"] / "results" / state["generation_id"] / plan["testing_id"]
        for relative in plan["run_directories"]:
            directory = _resolve_run_directory(testing_directory=testing, raw_directory=relative)
            if directory in used_paths:
                raise ValueError(f"Duplicate selected Run: {directory}")
            used_paths.add(directory)
            selected.append(directory)
    output = root / "archives"
    output.mkdir(exist_ok=True)
    path = output / f"selected_results_{datetime.now():%Y%m%d_%H%M%S_%f}.zip"
    with ZipFile(path, mode="x", compression=ZIP_DEFLATED) as archive:
        for directory in selected:
            for source in sorted(directory.rglob("*")):
                if source.is_file():
                    archive.write(source, arcname=(Path(root.name) / source.relative_to(root)).as_posix())
    print(f"Exported {len(selected)} Runs to {path}")


if __name__ == "__main__":
    main()
