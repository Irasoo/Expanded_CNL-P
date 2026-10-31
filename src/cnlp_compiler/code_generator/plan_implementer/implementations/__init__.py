from __future__ import annotations

from ...reference_code_catalog import ReferenceCodeCatalog
from ..registry import ImplementationRegistry
from .langgraph import LangGraphImplementer
from .native import NativeImplementer


def create_default_implementation_registry(
    *,
    reference_code_catalog: ReferenceCodeCatalog,
) -> ImplementationRegistry:
    """
    Register implementations shipped with the compiler.

    Additional implementations can be registered explicitly by the
    application without changing PlanImplementer.
    """
    registry = ImplementationRegistry()
    # TODO(Native main switch): CompilerConfig.target_implementation is the
    # explicit switch. Use "native" for deterministic PC/while/match Main
    # generation, or "native_llm_main" to compare against the preserved
    # compiler-time LLM Main generator.
    registry.register(
        "native",
        NativeImplementer(
            reference_code_catalog=reference_code_catalog,
        ),
    )
    registry.register(
        "native_llm_main",
        NativeImplementer(
            reference_code_catalog=reference_code_catalog,
            use_llm_main_implementer=True,
        ),
    )
    # TODO(Native config switch): Keep the former compiler-time LLM config.py
    # generator available for controlled comparison. Normal compilation uses
    # target_implementation="native" and therefore deterministic config.py.
    registry.register(
        "native_llm_config",
        NativeImplementer(
            reference_code_catalog=reference_code_catalog,
            use_llm_config_implementer=True,
        ),
    )
    registry.register(
        "langgraph",
        LangGraphImplementer(
            reference_code_catalog=reference_code_catalog,
        ),
    )
    return registry


__all__ = ["create_default_implementation_registry"]
