from __future__ import annotations

from .schema import ImplementationGenerator


class ImplementationRegistry:
    """A simple explicit registry for implementation generators."""

    def __init__(self) -> None:
        self._generators: dict[str, ImplementationGenerator] = {}

    def register(
        self,
        name: str,
        generator: ImplementationGenerator,
        *,
        replace: bool = False,
    ) -> None:
        normalized_name = self._normalize_name(name)
        if normalized_name in self._generators and not replace:
            raise ValueError(
                f"Implementation {normalized_name!r} is already registered."
            )
        self._generators[normalized_name] = generator

    def get(self, name: str) -> ImplementationGenerator:
        normalized_name = self._normalize_name(name)
        try:
            return self._generators[normalized_name]
        except KeyError as exc:
            supported = ", ".join(self.names()) or "<none>"
            raise ValueError(
                f"Unsupported target implementation {name!r}. "
                f"Registered targets: {supported}."
            ) from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._generators))

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "Implementation name must be a non-empty string."
            )
        return name.strip().lower()
