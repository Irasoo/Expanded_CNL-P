from __future__ import annotations

import json
from typing import Any

from .code_registry.models import RegisteredCode
from .code_registry.registry import (
    _all_registered_code,
    _get_registered_code,
    _registered_code_count,
)
from .match import (
    ReferenceCodeSearchDocument,
    ReferenceCodeSearchQuery,
    build_search_documents,
    llm_based_match,
    rule_based_match,
)


class ReferenceCodeCatalog:
    """The only reader of the package-internal reference-code storage."""

    def get(self, function_name: str) -> RegisteredCode:
        """Return the concrete registered code for one planned function."""
        return _get_registered_code(function_name)

    def search(
        self,
        query: ReferenceCodeSearchQuery,
    ) -> ReferenceCodeSearchDocument | None:
        """Find one source-free reference document for planning."""
        documents = build_search_documents(self.all_entries())
        function_name = rule_based_match(
            query=query,
            documents=documents,
        )
        if function_name is None:
            function_name = llm_based_match(
                query=query,
                documents=documents,
            )
        if function_name is None:
            return None
        return next(
            document
            for document in documents
            if document["function_name"] == function_name
        )

    def all_entries(self) -> tuple[RegisteredCode, ...]:
        return _all_registered_code()

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [
                entry.to_dict() for entry in self.all_entries()
            ]
        }

    def to_string(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2,
        )

    def __len__(self) -> int:
        return _registered_code_count()
