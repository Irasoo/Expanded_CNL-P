from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator, Mapping
from pathlib import Path, PurePosixPath
from typing import Literal


WriteType = Literal["rewrite", "append"]


class VirtualFileSystem:
    """Collect generated files before choosing their physical output form."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def reset(self) -> None:
        self.files.clear()

    def write(
        self,
        path: str,
        content: str | bytes,
        type: WriteType = "rewrite",
    ) -> None:
        normalized_path = self._normalize_path(path)
        encoded_content = (
            content.encode("utf-8")
            if isinstance(content, str)
            else content
        )

        if type == "rewrite":
            self.files[normalized_path] = encoded_content
            return

        if type == "append":
            self.files[normalized_path] = (
                self.files.get(normalized_path, b"") + encoded_content
            )
            return

        raise ValueError(f"Unsupported write type: {type}")

    def write_generated_file(
        self,
        generated_file: Mapping[str, object],
    ) -> None:
        """Apply one file item yielded by a target implementation."""
        content = generated_file["content"]
        write_type = generated_file["write_type"]
        if not isinstance(content, (str, bytes)):
            raise TypeError(
                "Generated file content must be str or bytes."
            )
        if write_type not in {"rewrite", "append"}:
            raise ValueError(
                f"Unsupported write type: {write_type!r}."
            )

        self.write(
            path=str(generated_file["relative_path"]),
            content=content,
            type=write_type,
        )

    def iter_files(self) -> Iterator[tuple[str, bytes]]:
        for path in sorted(self.files):
            yield path, self.files[path]

    def write_to_directory(self, output_directory: str | Path) -> Path:
        """
        Materialize the current file tree.

        Existing files with the same paths are replaced. Unrelated files in
        the output directory are left untouched.
        """
        root = Path(output_directory).resolve()
        root.mkdir(parents=True, exist_ok=True)

        for relative_path, content in self.iter_files():
            target_path = root.joinpath(
                *PurePosixPath(relative_path).parts
            ).resolve()
            if root != target_path and root not in target_path.parents:
                raise ValueError(
                    f"Generated path escapes output directory: "
                    f"{relative_path!r}."
                )
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(content)

        return root

    def to_zip(self) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(
            buffer,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for path, content in self.iter_files():
                archive.writestr(path, content)
        return buffer.getvalue()

    def write_zip(self, output_file: str | Path) -> Path:
        output_path = Path(output_file).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self.to_zip())
        return output_path

    @staticmethod
    def _normalize_path(path: str) -> str:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("Generated file path must be a non-empty string.")

        normalized = PurePosixPath(path.replace("\\", "/"))
        if (
            normalized.is_absolute()
            or ".." in normalized.parts
            or str(normalized) in {"", "."}
        ):
            raise ValueError(
                f"Generated file path must be relative: {path!r}."
            )
        return str(normalized)
