"""Project paths and runtime constants shared by the RQ2 pipeline."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PROJECT_ROOT.parents[1]
DATA_ROOT = PROJECT_ROOT.parents[1] / "experiment_results" / "RQ2"
INSTANCE_ROOT = DATA_ROOT / "instances"
PROMPT_ROOT = DATA_ROOT / "prompts"
RESULTS_ROOT = DATA_ROOT / "results"
RUN_RESULTS_BASE_DEFAULT = RESULTS_ROOT / "run_results"
ANALYSIS_RESULTS_BASE_DEFAULT = RESULTS_ROOT / "analysis_results" / "cnlp"
RESULT_BASE_DEFAULT = RUN_RESULTS_BASE_DEFAULT
OUTPUT_ENCODING = "utf-8-sig"

MAX_ASYNC_CONCURRENCY = 80
CONCURRENT_REQUESTS_PER_KEY = 16
MAX_CONSECUTIVE_MODEL_FAILURES = 5
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 15.0
RATE_LIMITED_PROVIDERS: tuple[str, ...] = ()
RATE_LIMITED_PROVIDER_MAX_CONCURRENCY = 2
RATE_LIMITED_PROVIDER_REQUESTS_PER_MINUTE = 12

LANGUAGE_ORDER = (
    "original",
    "risen-direct",
    "risen-gold",
    "risen-variant-1",
    "risen-variant-2",
    "rodes-direct",
    "rodes-gold",
    "rodes-variant-1",
    "rodes-variant-2",
    "cnlp-direct",
    "cnlp-gold",
    "cnlp-variant-1",
    "cnlp-variant-2",
)
README_LANGUAGE_ORDER = (
    "original",
    "risen-direct",
    "risen-gold",
    "risen-variant-1",
    "risen-variant-2",
    "rodes-direct",
    "rodes-gold",
    "rodes-variant-1",
    "rodes-variant-2",
    "cnlp-direct",
    "cnlp-variant-1",
    "cnlp-variant-2",
    "cnlp-gold",
)
