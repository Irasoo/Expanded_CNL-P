from __future__ import annotations

from internal_comms_agent import InternalCommsAgent


def main() -> str | None:
    """Initialize the agent, run its entry worker, and return the result."""
    agent = InternalCommsAgent.from_environment()
    return agent.run_dispatcher()


if __name__ == "__main__":
    main()
