from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ....schema import GeneratedFile


class StaticCodeGenerator:
    """Yield the Native implementation's fixed source tree unchanged."""

    def __init__(
        self,
        static_code_directory: str | Path | None = None,
    ) -> None:
        self.static_code_directory = (
            Path(static_code_directory)
            if static_code_directory is not None
            else Path(__file__).resolve().parent / "static_code"
        )

    def generate_static_code(self) -> Iterator[GeneratedFile]:
        if not self.static_code_directory.is_dir():
            return

        source_files = sorted(
            path
            for path in self.static_code_directory.rglob("*")
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
            )
        )
        for source_path in source_files:
            yield GeneratedFile(
                relative_path=source_path.relative_to(
                    self.static_code_directory
                ).as_posix(),
                content=source_path.read_bytes(),
                write_type="rewrite",
            )
