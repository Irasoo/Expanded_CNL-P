"""Legacy answer extraction and deterministic scoring helpers."""

from __future__ import annotations

import re


def _kor_category(task_id: str) -> str | None:
    if len(task_id) == 4 and task_id.isdigit():
        if task_id.startswith("17"):
            return "cipher"
        if task_id.startswith("18"):
            return "logic"
    return None


def _extract_kor_bracket_content(text: str) -> str | None:
    for pattern in (
        r"\[\[\s*(.*?)\s*\]\]",
        r"\$\\boxed\{(.*?)\}\$",
        r"\[\s*(.*?)\s*\]",
    ):
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return None


def _normalize_kor_answer(text: str, category: str) -> str | None:
    content = _extract_kor_bracket_content(text)
    if content is None:
        return None
    if category == "cipher":
        content = re.sub(r'["\s\[\]]+', "", content)
    else:
        content = re.sub(r'["\s.]', "", content)
    return f"[[{content}]]"


def _kor_logic_rule_id(task_id: str) -> str:
    return str(int(task_id[2:]))


def _score_kor_answer(task_id: str, expected: str, model_output: str) -> tuple[str | None, int | None]:
    category = _kor_category(task_id)
    assert category is not None
    extracted = _normalize_kor_answer(model_output, category)
    expected_normalized = _normalize_kor_answer(expected, category)
    if extracted is None or expected_normalized is None:
        return extracted, None
    if category == "logic" and _kor_logic_rule_id(task_id) == "5":
        response_parts = [part.strip("[]") for part in extracted[2:-2].split(";")]
        expected_parts = [part.strip("[]") for part in expected_normalized[2:-2].split(";")]
        return extracted, int(sorted(response_parts) == sorted(expected_parts))
    return extracted, int(extracted == expected_normalized)


def extract_answer(model_output: str, task_id: str) -> str | None:
    if not model_output or not model_output.strip():
        return None
    text = model_output.strip()
    category = _kor_category(task_id)
    if category is not None:
        return _normalize_kor_answer(text, category)
    if task_id == "1162":
        match = re.search(r"\b(True|False)\b", text, re.IGNORECASE)
        return match.group(1).title() if match else None
    if task_id == "385":
        match = re.search(r"\b([A-Ca-c]\s*,\s*[A-Ca-c])\b", text)
        if match:
            return match.group(1).upper().replace(" ", "")
    for pattern in (
        r"(?:answer|option|choice|output|result|label)\s*(?:is|:|=|->)\s*\(?([A-Ea-e])\)?\b",
        r"(?:choose|select|pick|output:?)\s*\(?([A-Ea-e])\)?\b",
        r"(?:^|\n)\s*\(?([A-Ea-e])\)?[.]?\s*$",
        r"^\s*([A-Ea-e])\s*$",
    ):
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if matches:
            return matches[-1].upper()
    return None


def score_row(task_id: str, expected: str, model_output: str) -> int | None:
    if _kor_category(task_id) is not None:
        _, score = _score_kor_answer(task_id, expected, model_output)
        return score
    extracted = extract_answer(model_output, task_id)
    if extracted is None:
        return None
    if task_id == "385":
        return int(extracted in {item.strip().upper() for item in expected.split(",")})
    if task_id == "1162":
        return int(extracted.casefold() == expected.strip().casefold())
    return int(extracted == expected.strip().split(",")[0].strip().upper())


def format_accuracy(correct: int, total: int) -> tuple[str, str]:
    if total == 0:
        return "", ""
    accuracy = correct / total
    decimal = f"{accuracy:.3f}".rstrip("0").rstrip(".")
    percent = f"{accuracy * 100:.3f}".rstrip("0").rstrip(".")
    return decimal, f"{percent}%"
