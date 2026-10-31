from __future__ import annotations

from creative_agent import run_agent


def main():
    """Initialize and execute the CreativeConceptDeveloper worker."""
    try:
        return run_agent()
    except Exception as exc:
        print(f"\nAgent execution failed: {exc}")
        return {"error": str(exc)}


if __name__ == "__main__":
    main()
