"""Run the experiment pipeline (execute, judge, and score)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.config import load_app_config
from utils import PipelineConfig


def build_config() -> PipelineConfig:
    return load_app_config().pipeline


def main() -> None:
    from pipeline.step1_run import run as step1
    from pipeline.step2_judge import run as step2
    from pipeline.step3_score import run as step3

    config = build_config()
    run_root = step1(config)
    step2(config, run_root=run_root)
    step3(config, run_root=run_root)
    print(f"\nPipeline complete: {run_root}")


if __name__ == "__main__":
    main()
