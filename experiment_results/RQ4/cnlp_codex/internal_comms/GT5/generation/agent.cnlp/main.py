from __future__ import annotations

import logging

from agent import InternalCommsAssistant
from llm_runtime import LLMRuntime, LLMSettings


def main() -> str | None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    settings = LLMSettings.from_environment()
    assistant = InternalCommsAssistant(LLMRuntime(settings))
    return assistant.run()


if __name__ == "__main__":
    main()

