"""Step 2: extract answers, score them, and collect manual reviews."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from itertools import product
from pathlib import Path
import re

from utils import (
    MANUAL_FIELDS,
    PipelineConfig,
    _read_csv,
    resolve_run_root,
    result_files,
    write_csv,
)

@dataclass(frozen=True)
class SemanticAssessment:
    extracted_answer: str
    score: int | None
    status: str
    normalized_expected: str
    normalized_answer: str
    reason: str


def _balanced_boxed_contents(text: str) -> list[str]:
    """Return ``\\boxed{...}`` contents while preserving nested braces."""
    contents: list[str] = []
    marker = r"\boxed{"
    start = 0
    while (index := text.find(marker, start)) >= 0:
        depth = 1
        cursor = index + len(marker)
        while cursor < len(text) and depth:
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
            cursor += 1
        if depth == 0:
            content = text[index + len(marker):cursor - 1].strip()
            if content:
                contents.append(content)
        start = cursor
    return contents


def _single_bracket_contents(text: str) -> list[str]:
    """Find non-LaTeX single-bracket answers.

    ``\\[...\\]`` is a LaTeX display environment, not an answer delimiter.
    Nested ``[[...]]`` markers are handled separately.
    """
    pattern = re.compile(r"(?<![\\\[])\[(?!\[)\s*(.*?)\s*(?<!\\)\]", re.DOTALL)
    return [match.group(1).strip() for match in pattern.finditer(text) if match.group(1).strip()]


def extract_semantic_answer(text: str) -> str | None:
    """Extract the last non-empty, explicitly formatted final answer.

    Choosing the last marker avoids treating examples, code-block matrices, and
    intermediate formula displays as the answer.  This policy is intentionally
    distinct from the frozen KOR-Bench-compatible legacy extraction policy.
    """
    if not text or not text.strip():
        return None
    double = [match.group(1).strip() for match in re.finditer(r"\[\[\s*(.*?)\s*\]\]", text, re.DOTALL)]
    double = [content for content in double if content]
    if double:
        return double[-1]
    boxed = _balanced_boxed_contents(text)
    if boxed:
        return boxed[-1]
    single = _single_bracket_contents(text)
    if single:
        return single[-1]
    for pattern in (
        r"(?:answer|option|choice|output|result|label)\s*(?:is|:|=|->)\s*\(?([A-Ea-e])\)?\b",
        r"(?:choose|select|pick|output:?)\s*\(?([A-Ea-e])\)?\b",
        r"(?:^|\n)\s*\(?([A-Ea-e])\)?[.]?\s*$",
    ):
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if matches:
            return matches[-1].upper()
    return None


MULTIPLE_CHOICE_TASKS = frozenset({"385", "729", "1424", "1678"})


def extract_multiple_choice_answer(text: str) -> str | None:
    """Extract an explicit A-E option (or ``NONE``) from old MCQ tasks.

    These tasks usually return ``a)`` (task 1424) or ``a.`` (task 1678),
    frequently wrapped in Markdown or backticks.  The generic semantic
    extractor intentionally does not scan for arbitrary option-like text, but
    that policy leaves these otherwise unambiguous answers unresolved.

    Prefer labelled conclusions such as ``Correct option: **b) ...**``.  A
    labelled line is used only as a fallback so calculations containing words
    such as "choice" do not become answers accidentally.
    """
    if not text or not text.strip():
        return None

    angle_wrapped = re.fullmatch(r"\s*<\s*([a-e])\s*>\s*", text, re.IGNORECASE)
    if angle_wrapped:
        return angle_wrapped.group(1).upper()

    # JSON-mode and prompt-constrained models often return a quoted bare
    # label (for example, ``"D"``).  Accept it only when the entire response
    # is the wrapped label, so option letters in prose remain conservative.
    quoted_or_bare = re.fullmatch(
        r"\s*[*_`]*[\"']?\s*\(?([a-e])\)?\s*[.]?\s*[\"']?[*_`]*\s*",
        text,
        re.IGNORECASE,
    )
    if quoted_or_bare:
        return quoted_or_bare.group(1).upper()

    tagged_patterns = (
        # Structured output used by GPT-5.x in this run.
        r"<(?:correct[_ -]*option|final[_ -]*answer|answer)[^>]*>\s*([a-e])",
        r"<REF[^>]*>\s*(?:correct[_ -]*option|final[_ -]*answer|answer)\s*</REF>"
        r"\s*:\s*([a-e])",
        # Explicit option labels inside a final ``\boxed{\text{...}}`` value.
        r"\\text\{\s*([a-e])\s*[.)]",
        # ``\text{Correct choice: } \mathbf{c}`` and close variants.
        r"\\text\{[^}]*\b(?:answer|option|choice)\s*:?\s*\}\s*"
        r"\\(?:mathbf|mathrm|text)\{\s*([a-e])\s*\}",
    )
    tagged_matches: list[re.Match[str]] = []
    for pattern in tagged_patterns:
        tagged_matches.extend(re.finditer(pattern, text, re.IGNORECASE))
    if tagged_matches:
        return max(tagged_matches, key=lambda match: match.start()).group(1).upper()

    # Treat snake_case labels (``correct_option``/``final_answer``) like their
    # natural-language equivalents.  Underscores used for Markdown emphasis
    # are harmless when converted to spaces here.
    cue_text = text.replace("_", " ")
    cue_pattern = re.compile(
        r"\b(?:(?:final|correct|incorrect|selected|exact|valid)\s+)*"
        r"(?:answer|option|choice|output)\b"
        r"[\s*`]*(?:for\s+the\s+(?:problem|question)\s*)?"
        r"(?:(?:is|would\s+be|corresponds\s+to)\b[\s*`]*)?"
        r"(?:(?::|=|->|-)[\s*`]*)?(?:the\s+)?(?:option[\s*`]+)?"
        r"\(?([a-e])(?=\s*(?:[.)\]:;,*`]|$))",
        re.IGNORECASE | re.MULTILINE,
    )
    matches = list(cue_pattern.finditer(cue_text))
    if matches:
        return matches[-1].group(1).upper()

    labelled_lines: list[str] = []
    for line in text.splitlines():
        # Remove only common list/heading/Markdown prefixes.  The option
        # punctuation itself remains mandatory when a value follows it.
        candidate = re.sub(r"^[\s#>*_`]+", "", line).strip()
        labelled = re.match(
            r"^(?:option\s*)?(?:\(([a-e])\)|([a-e])[.)])\s*(?:[*_`]+\s*)?\S",
            candidate,
            re.IGNORECASE,
        )
        if labelled:
            labelled_lines.append((labelled.group(1) or labelled.group(2)).upper())
            continue
        standalone = re.fullmatch(
            r"(?:option\s*)?\(?([a-e])\)?\s*[.]?\s*[*_`]*",
            candidate,
            re.IGNORECASE,
        )
        if standalone:
            labelled_lines.append(standalone.group(1).upper())
    if labelled_lines:
        # Repeated copies of the same label are harmless, but a list containing
        # different A-E labels is likely an echoed option list, not a choice.
        unique_labels = set(labelled_lines)
        if len(unique_labels) == 1:
            return labelled_lines[-1]

    # Rejecting every listed option is also an explicit multiple-choice
    # response.  Retain a visible sentinel so the scoring layer can route it
    # to manual review instead of losing the reason extraction was unresolved.
    no_option_patterns = (
        r"\bnone\s+of\s+(?:the\s+)?(?:given\s+|provided\s+|listed\s+)?(?:answer\s+)?options\b",
        r"\bnone\s+of\s+(?:the\s+)?(?:answer\s+)?choices\b",
        r"\bnone\s+of\s+(?:the\s+)?(?:given\s+|provided\s+|listed\s+)?"
        r"(?:answer\s+)?choices\b",
        r"\bnone\s+of\s+the\s+above\b",
        r"\bno\s+(?:listed\s+)?option\s+is\s+correct\b",
        r"\bnot\s+(?:listed|included)\s+(?:in|among)\s+(?:the\s+)?"
        r"(?:given\s+|provided\s+|listed\s+)?(?:answer\s+)?(?:options|choices)\b",
        r"\bnot\s+among\s+(?:the\s+)?(?:given\s+|provided\s+|listed\s+)?options\b",
        r"\bdoes\s+not\s+match\s+any\s+of\s+(?:the\s+)?(?:given\s+|provided\s+|listed\s+)?(?:answer\s+)?(?:options|choices)\b",
        r"\bnot\s+match\s+any\s+of\s+(?:the\s+)?(?:given\s+|provided\s+|listed\s+)?(?:answer\s+)?(?:options|choices)\b",
    )
    no_option_text = re.sub(r"[*_`]+", " ", text)
    if any(re.search(pattern, no_option_text, re.IGNORECASE) for pattern in no_option_patterns):
        return "NONE"
    return None


def extract_task1424_1678_answer(text: str) -> str | None:
    """Extend the shared MCQ extractor only for task1424/task1678 formats.

    Their historical outputs frequently contain ``e ) value`` (a space before
    the option punctuation) or a final LaTeX conclusion such as
    ``\text{Answer: } a``.  Other multiple-choice tasks retain the common
    extractor's original, deliberately conservative behavior.
    """
    extracted = extract_multiple_choice_answer(text)
    if extracted is not None:
        return extracted

    spaced_labels: list[str] = []
    for line in text.splitlines():
        candidate = re.sub(r"^[\s#>*_`]+", "", line).strip()
        match = re.match(
            r"^(?:option\s*)?(?:\(([a-e])\)|([a-e])\s+[.)])\s*"
            r"(?:[*_`]+\s*)?\S",
            candidate,
            re.IGNORECASE,
        )
        if match:
            spaced_labels.append((match.group(1) or match.group(2)).upper())
    if spaced_labels and len(set(spaced_labels)) == 1:
        return spaced_labels[-1]

    # Duplicate-valued options are present in task1424.  Models sometimes
    # explicitly conclude with ``option b or c`` instead of choosing one of
    # the equivalent labels; either label is sufficient for set-based scoring.
    tail = text[-600:]
    paired = re.findall(
        r"\b(?:answer|result|correct\s+answer)[^\n]{0,120}?"
        r"(?:either\s+)?option\s+[*_`]*\(?([a-e])\)?[*_`]*\s+or\s+"
        r"(?:option\s+)?[*_`]*\(?([a-e])\)?",
        tail,
        re.IGNORECASE,
    )
    if paired:
        return paired[-1][0].upper()

    corresponds = re.findall(
        r"\bcorresponds\s+to\s+[*_`]*\(?([a-e])(?=\s*(?:[.)\]:;,*`]|$))",
        tail,
        re.IGNORECASE,
    )
    if corresponds:
        return corresponds[-1].upper()

    conclusions = _balanced_boxed_contents(text) + _latex_math_candidates(text)
    for conclusion in reversed(tuple(dict.fromkeys(conclusions))):
        normalized = re.sub(r"[*_`]", "", _normalize_common(conclusion)).strip()
        compact = re.sub(r"[\s(){}\[\].:;]+", "", normalized).casefold()
        if compact in {"a", "b", "c", "d", "e"}:
            return compact.upper()
        labelled = re.search(
            r"\b(?:final\s+)?(?:answer|option|choice)\b\s*(?:is\s*)?"
            r"(?::|=)?\s*([a-e])\b",
            normalized,
            re.IGNORECASE,
        )
        if labelled:
            return labelled.group(1).upper()
        if re.search(
            r"\b(?:(?:final|correct)\s+)?(?:answer|option|choice)\b[^\n]{0,40}"
            r"\bnone\b",
            normalized,
            re.IGNORECASE,
        ):
            return "NONE"
    # Some task1424 answers state ``The correct option is none`` in prose
    # rather than inside the final math region.  Limit this fallback to the
    # tail and to an explicit answer/option cue so rationale mentions of
    # ``none`` cannot become a prediction.
    if re.search(
        r"\b(?:(?:final|correct)\s+)?(?:answer|option|choice)\b[^\n]{0,50}"
        r"\bnone\b",
        text[-400:],
        re.IGNORECASE,
    ):
        return "NONE"
    return None


def _multiple_choice_options(instance_content: str) -> dict[str, str]:
    """Parse the A-E option text used by task1424/task1678 prompts."""
    match = re.search(
        r"\bOptions\s*:\s*(.*)$", instance_content, re.IGNORECASE | re.DOTALL
    )
    if not match:
        return {}
    option_text = match.group(1).strip()
    matches = list(
        re.finditer(
            r"(?<![A-Za-z])([a-e])\s*(?:\)|\.)\s*",
            option_text,
            re.IGNORECASE,
        )
    )
    options: dict[str, str] = {}
    for index, option in enumerate(matches):
        start = option.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(option_text)
        value = option_text[start:end].strip().rstrip(",").strip()
        if value:
            options[option.group(1).upper()] = value
    return options


def _normalized_option_value(value: str) -> str:
    value = _normalize_common(value)
    value = re.sub(r"\\frac\s*\{\s*(-?\d+)\s*\}\s*\{\s*(\d+)\s*\}", r"\1/\2", value)
    value = re.sub(r"[*_`$]", "", value)
    value = re.sub(r"\b(?:rs|s)\s*\.\s*", "", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", "", value).strip(".,;:()[]{}").casefold()


def _single_numeric_value(value: str) -> Fraction | None:
    values = _numeric_values_in_text(value)
    return next(iter(values)) if len(values) == 1 else None


def _final_numeric_value(text: str) -> Fraction | None:
    """Return a numeric value from a final equation-style conclusion.

    This deliberately ignores arbitrary numbers in the rationale.  It only
    considers the last meaningful line, and when that line is an equation it
    reads the final right-hand side.  The fallback is used only for task1424,
    whose historical answers frequently end with a displayed value rather
    than an option label.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    while lines and lines[-1] in {r"\[", r"\]", "$$"}:
        lines.pop()
    if not lines:
        return None

    candidate = lines[-1]
    if "=" in candidate:
        candidate = candidate.rsplit("=", 1)[-1].strip()
    elif len(candidate) > 120:
        return None

    candidate = re.sub(r"(?:\\\]|\$\$)\s*$", "", candidate).strip()
    return _single_numeric_value(candidate)


def _labels_for_numeric_option_value(
    value: Fraction, instance_content: str
) -> tuple[str, ...]:
    return tuple(
        label
        for label, option in _multiple_choice_options(instance_content).items()
        if _single_numeric_value(option) == value
    )


def _multiple_choice_value_labels(
    text: str, instance_content: str
) -> tuple[str, ...]:
    """Map a bare/boxed answer value back to every matching option label.

    Duplicate options are deliberately preserved.  For example, task1424
    instance 7 has both B and C equal to 1/2, so a value-only response should
    be accepted when either label is in the corrected gold answer.
    """
    options = _multiple_choice_options(instance_content)
    if not options:
        return ()

    candidates: list[str] = []
    stripped = text.strip()
    if stripped and len(stripped) <= 120:
        candidates.append(stripped)
    semantic = extract_semantic_answer(text)
    if semantic:
        candidates.append(semantic)
    nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if nonempty_lines and len(nonempty_lines[-1]) <= 120:
        candidates.append(nonempty_lines[-1])

    for candidate in reversed(tuple(dict.fromkeys(candidates))):
        normalized_candidate = _normalized_option_value(candidate)
        numeric_candidate = _single_numeric_value(candidate)
        matched: list[str] = []
        for label, option in options.items():
            normalized_option = _normalized_option_value(option)
            numeric_option = _single_numeric_value(option)
            if normalized_candidate and normalized_candidate == normalized_option:
                matched.append(label)
            elif numeric_candidate is not None and numeric_candidate == numeric_option:
                matched.append(label)
        if matched:
            return tuple(matched)
    return ()


def _none_option_labels(instance_content: str) -> tuple[str, ...]:
    labels: list[str] = []
    for label, option in _multiple_choice_options(instance_content).items():
        normalized = _normalized_option_value(option)
        if normalized in {"none", "noneoftheabove", "noneofthese"}:
            labels.append(label)
    return tuple(labels)


def _latex_math_candidates(text: str) -> list[str]:
    """Return explicit LaTeX math regions, with the final region first."""
    matches: list[tuple[int, str]] = []
    for pattern in (r"\\\[(.*?)\\\]", r"\\\((.*?)\\\)"):
        matches.extend(
            (match.start(), match.group(1).strip())
            for match in re.finditer(pattern, text, re.DOTALL)
            if match.group(1).strip()
        )
    return [value for _, value in sorted(matches, reverse=True)]


def _structured_answer_candidates(text: str) -> list[str]:
    """Candidates for structured tasks whose answer wrapper was omitted."""
    candidates: list[str] = []
    explicit = extract_semantic_answer(text)
    if explicit:
        candidates.append(explicit)
    candidates.extend(_latex_math_candidates(text))
    stripped = text.strip()
    if stripped and len(stripped) <= 500:
        candidates.append(stripped)
    return list(dict.fromkeys(candidates))


def extract_boolean_answer(text: str) -> str | None:
    """Extract an unambiguous True/False classification."""
    if not text or not text.strip():
        return None

    compact = re.sub(r"[\s\[\](){}<>*_`.:;!]+", "", text).lower()
    if compact in {"true", "false"}:
        return compact.capitalize()

    patterns = (
        r"\b(?:final\s+)?(?:answer|result|output|label|classification|judgment|verdict)\b\s*"
        r"(?:is\s*)?(?::|=|->)?\s*(?:[*_`\[\]()<>]\s*)*(true|false)\b",
        r"(?:^|\n)\s*(?:#+\s*)?(?:[*_`]*)?(true|false)(?:[*_`]*)?\s*[.!]?\s*$",
    )
    matches: list[re.Match[str]] = []
    for pattern in patterns:
        matches.extend(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE))
    if matches:
        return max(matches, key=lambda match: match.start()).group(1).capitalize()

    # A response that uses only one of the two Boolean words is unambiguous,
    # even when it follows that classification with a prose explanation.
    values = {match.group(1).capitalize() for match in re.finditer(r"\b(true|false)\b", text, re.IGNORECASE)}
    if len(values) == 1:
        return values.pop()
    return None


def _task385_options(instance_content: str) -> dict[str, str]:
    """Parse task385's ``Options: (A) ... (B) ... (C) ...`` field."""
    match = re.search(r"\bOptions\s*:\s*(.*)$", instance_content, re.IGNORECASE | re.DOTALL)
    if not match:
        return {}
    option_text = match.group(1).strip()
    options: dict[str, str] = {}
    for option in re.finditer(
        r"\(([A-C])\)\s*(.*?)(?=\s+\([A-C]\)\s|$)",
        option_text,
        re.IGNORECASE | re.DOTALL,
    ):
        options[option.group(1).upper()] = option.group(2).strip()
    return options


def _normalize_task385_option_text(text: str) -> str:
    text = re.sub(r"[*_`]+", "", text).strip()
    text = text.strip('"\'“”‘’')
    return re.sub(r"\s+", " ", text).rstrip(".。 ").casefold()


def extract_task385_answer(text: str, instance_content: str = "") -> str | None:
    """Extract task385 labels, including bare option text responses."""
    extracted = extract_multiple_choice_answer(text)
    if extracted is not None:
        return extracted

    # Task385 frequently spells out both the correct and incorrect choices in
    # its rationale.  Only labels tied to the final/incorrect-answer cue are
    # authoritative; taking an arbitrary last A-C mention would be unsafe.
    labelled_patterns = (
        r"\b(?:one\s+)?incorrect\s+answer(?:\s+option)?(?:\s+selected)?"
        r"(?:\s+from[^\n]{0,80})?\s*(?:is|:|=)\s*(?:[*_`\"']*)\(?([a-c])\)",
        r"\bselected\s+incorrect\s+answer(?:\s+option)?\s*(?:is|:|=)\s*"
        r"(?:[*_`\"']*)\(?([a-c])\)",
    )
    labelled_matches: list[re.Match[str]] = []
    for pattern in labelled_patterns:
        labelled_matches.extend(re.finditer(pattern, text, re.IGNORECASE))
    if labelled_matches:
        return max(labelled_matches, key=lambda match: match.start()).group(1).upper()

    wrapped = re.fullmatch(
        r"\s*[\"']?\s*\(([a-c])\)\s+.+?\s*[\"']?\s*",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if wrapped:
        return wrapped.group(1).upper()

    options = _task385_options(instance_content)
    if not options:
        return None

    candidates = [text]
    value_patterns = (
        r'"incorrect_answer"\s*:\s*"([^"]+)"',
        r"\bincorrect[_ ]answer(?:\s+selected)?\s*(?:is|:|=)\s*[\"']?([^\n\"']+)",
    )
    for pattern in value_patterns:
        candidates.extend(match.group(1) for match in re.finditer(pattern, text, re.IGNORECASE))

    matched_labels: list[str] = []
    for candidate in candidates:
        normalized_candidate = _normalize_task385_option_text(candidate)
        if not normalized_candidate:
            continue
        labels = [
            label
            for label, option in options.items()
            if normalized_candidate == _normalize_task385_option_text(option)
        ]
        if len(labels) == 1:
            matched_labels.append(labels[0])
    return matched_labels[-1] if matched_labels else None


def _multiple_choice_labels(value: str) -> tuple[str, ...]:
    """Return unique standalone A-E labels, preserving source order."""
    labels = re.findall(r"(?<![A-Za-z])([A-Ea-e])(?![A-Za-z])", value)
    return tuple(dict.fromkeys(label.upper() for label in labels))


def _numeric_value(value: str) -> Fraction | None:
    """Parse a corrected numeric gold answer, including percentages."""
    text = value.strip().replace(",", "")
    percent = text.endswith("%")
    if percent:
        text = text[:-1].strip()
    fraction = re.fullmatch(r"(-?\d+)\s*/\s*(\d+)", text)
    try:
        result = (
            Fraction(int(fraction.group(1)), int(fraction.group(2)))
            if fraction
            else Fraction(Decimal(text))
        )
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None
    return result / 100 if percent else result


def _numeric_values_in_text(text: str) -> set[Fraction]:
    """Collect exact numeric values stated in a model response."""
    values: set[Fraction] = set()
    spans: list[tuple[int, int]] = []

    for match in re.finditer(r"\\frac\s*\{\s*(-?\d+)\s*\}\s*\{\s*(\d+)\s*\}", text):
        denominator = int(match.group(2))
        if denominator:
            values.add(Fraction(int(match.group(1)), denominator))
        spans.append(match.span())
    for match in re.finditer(r"(?<![\d.])(-?\d+)\s*/\s*(\d+)(?!\d)", text):
        denominator = int(match.group(2))
        if denominator:
            values.add(Fraction(int(match.group(1)), denominator))
        spans.append(match.span())
    for match in re.finditer(r"(?<![\d.])(-?\d+(?:\.\d+)?)\s*%", text):
        values.add(Fraction(Decimal(match.group(1))) / 100)
        spans.append(match.span())

    def covered(start: int, end: int) -> bool:
        return any(left <= start and end <= right for left, right in spans)

    for match in re.finditer(r"(?<![\d./])(-?\d+(?:\.\d+)?)(?![\d./])", text.replace(",", "")):
        if not covered(*match.span()):
            values.add(Fraction(Decimal(match.group(1))))
    return values


def extract_task190_answer(text: str) -> str | None:
    """Extract the E/C/N sentence-relation label used by task 190.

    Task 190 prompts ask for a relation rather than a multiple-choice answer.
    Models consequently return either the compact labels (``E``, ``C``, ``N``)
    or the relation names in a labelled conclusion.  Keep the latter task-local:
    relation words elsewhere in a rationale (for example, ``doesn't
    contradict``) must not be treated as the answer.
    """
    if not text or not text.strip():
        return None

    labels = {
        "e": "E",
        "entailment": "E",
        "entails": "E",
        "c": "C",
        "contradiction": "C",
        "contradict": "C",
        "contradicts": "C",
        "n": "N",
        "neutral": "N",
    }
    label_pattern = r"(?P<label>entailment|entails|contradiction|contradicts|neutral|[ecn])"

    # A substantial part of the corpus is a compact label, optionally wrapped
    # in Markdown/HTML/bracket delimiters (for example, ``**C**`` or ``[N]``).
    compact = re.sub(r"[\s\[\](){}<>*_`.:;!]+", "", text).lower()
    if compact in labels:
        return labels[compact]
    relation_with_code = {
        "entailmente": "E",
        "contradictionc": "C",
        "neutraln": "N",
    }
    if compact in relation_with_code:
        return relation_with_code[compact]

    # Prefer an explicit answer on the final non-empty line over relation words
    # in the preceding rationale.  For example, a rationale may mention both
    # entailment and contradiction before ending with ``Final judgment: N``.
    for line in reversed(text.splitlines()):
        if not line.strip():
            continue
        compact_line = re.sub(r"[\s\[\](){}<>*_`.:;!]+", "", line).lower()
        if compact_line in labels:
            return labels[compact_line]
        formatted_line = re.sub(r"[\[*_`<>]", "", line).strip()
        anchored_line = re.search(
            rf"\b(?:final\s+)?(?:answer|result|output|label|classification|conclusion|judgment|verdict|decision)\b\s*"
            rf"(?:is\s*)?(?::|=|->)?\s*(?:[\[\]()*_`<>\s]{{0,12}}){label_pattern}\b"
            rf"(?:\s*\((?:entailment|contradiction|neutral)\))?\s*[.!]?\s*$",
            formatted_line,
            re.IGNORECASE,
        )
        if anchored_line:
            return labels[anchored_line.group("label").lower()]
        line_match = re.fullmatch(
            r"(?:entailment|contradiction|neutral)\s*(?:\([ecn]\))?",
            formatted_line,
            re.IGNORECASE,
        )
        if line_match:
            return labels[line_match.group(0).split()[0].lower()]
        code_then_relation = re.fullmatch(
            r"(?P<label>[ecn])\s*(?:[-—:,]\s*)?(?:\((?:entailment|contradiction|neutral)\)|(?:entailment|contradiction|neutral))?\s*[.!]?",
            formatted_line,
            re.IGNORECASE,
        )
        if code_then_relation:
            return labels[code_then_relation.group("label").lower()]
        # GPT-5 sometimes ends an otherwise unlabelled conclusion with the
        # compact relation code on its final sentence (``... supported. E``).
        # Because this is the last non-empty output line, it remains a
        # task-local, explicit final answer rather than a rationale mention.
        trailing_code = re.search(r"(?:^|[.!?:=])\s*(?P<label>[ecn])\s*[.!?]?\s*$", formatted_line, re.IGNORECASE)
        if trailing_code:
            return labels[trailing_code.group("label").lower()]
        break

    patterns = (
        # ``Judgment: N``, ``Final answer is contradiction``, etc.  Task 190
        # prompts frequently ask for a judgment, so that label is as explicit
        # an answer anchor as ``answer`` or ``result``.
        rf"\b(?:final\s+)?(?:answer|result|output|label|classification|conclusion|judgment|verdict|decision)\b\s*"
        rf"(?:is\s*)?(?::|=|->)?\s*(?:[\[\]()*_`<>\s]{{0,12}}){label_pattern}\b",
        # Some Claude responses put a short natural-language conclusion after
        # ``Judgment:`` (for example, ``Judgment: ... this is a
        # contradiction``), rather than placing the label immediately after
        # the delimiter.  Keep the match to the same line and conclusion
        # anchor so an earlier rationale is not mistaken for the answer.
        rf"\b(?:final\s+)?(?:judgment|verdict|decision)\b\s*:\s*[^\n]{{0,180}}?\b{label_pattern}\b",
        # ``The relationship between the sentences is Neutral``.  The limited
        # span supports the common phrasing without searching an entire
        # rationale for an unrelated relation word.
        rf"\b(?:relationship|relation)\b[^\n.]{{0,80}}?(?:\bis\b|:|=|->)\s*"
        rf"(?:an?\s+)?(?:[\[\]()*_`<>\s]{{0,12}}){label_pattern}\b",
        # ``The sentences have a Neutral relationship`` is another frequent
        # sentence-relation formulation.
        rf"\b{label_pattern}\b\s+(?:relationship|relation|judgment|verdict|decision)\b",
        rf"\b(?:these\s+)?sentences\s+(?:are|have)\s+(?:in\s+)?(?:an?\s+)?"
        rf"(?:[\[\]()*_`<>\s]{{0,12}}){label_pattern}\b",
        # These are affirmative relation statements, unlike negative rationale
        # clauses such as ``do not contradict each other``.
        r"\b(?:sentence\s*1|the\s+first\s+sentence)\s+(?P<label>entails)\s+"
        r"(?:sentence\s*2|the\s+second\s+sentence)\b",
        r"\b(?:these\s+)?sentences\s+(?:directly\s+)?(?P<label>contradict)\s+"
        r"(?:each\s+other|one\s+another)\b",
        # Some verbose models end with a prose conclusion instead of a label.
        rf"\b(?:therefore|thus|hence|in\s+summary|overall|to\s+summarize)\b[^\n.]{{0,160}}?"
        rf"\b{label_pattern}\b",
        # Compact natural-language endings such as ``C for contradiction``.
        r"\b(?P<label>[ecn])\s*,?\s+for\s+"
        r"(?:entailment|contradiction|neutral)\b",
    )
    matches: list[re.Match[str]] = []
    for pattern in patterns:
        matches.extend(re.finditer(pattern, text, re.IGNORECASE))
    if matches:
        return labels[matches[-1].group("label").lower()]

    return None


def _replace_text_commands(value: str) -> str:
    previous = None
    while value != previous:
        previous = value
        value = re.sub(r"\\text\{([^{}]*)\}", r"\1", value)
    return value


def _normalize_common(value: str) -> str:
    value = _replace_text_commands(value)
    replacements = (
        (r"\Longrightarrow", "→"),
        (r"\Rightarrow", "→"),
        (r"\rightarrow", "→"),
        (r"\implies", "→"),
        (r"\to", "→"),
        (r"\leftrightarrow", "↔"),
        (r"\forall", "∀"),
        (r"\exists", "∃"),
        (r"\emptyset", "∅"),
        (r"\varnothing", "∅"),
        (r"\neg", "¬"),
        (r"\lnot", "¬"),
        (r"\wedge", "∧"),
        (r"\land", "∧"),
        (r"\vee", "∨"),
        (r"\lor", "∨"),
        (r"\mid", "|"),
        (r"\vert", "|"),
        (r"\cdot", "*"),
        (r"\times", "*"),
        (r"\dfrac", r"\frac"),
        (r"\left", ""),
        (r"\right", ""),
        (r"\{", "{"),
        (r"\}", "}"),
        (r"\&", "&"),
    )
    for old, new in replacements:
        value = value.replace(old, new)
    return value.replace("∣", "|").replace("∧", "&").replace("∨", "|").replace("¬", "!")


def _strip_square_wrapper(value: str) -> str:
    value = value.strip()
    while value.startswith("[") and value.endswith("]"):
        value = value[1:-1].strip()
    return value


def _split_top_level(value: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    opening = "([{"
    closing = ")]}"
    for index, char in enumerate(value):
        if char in opening:
            depth += 1
        elif char in closing:
            depth = max(depth - 1, 0)
        elif char == delimiter and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return parts


def _answer_parts(value: str) -> list[str]:
    # A ``[[a];[b]]`` capture is necessarily non-greedy, therefore its
    # contents are ``a];[b``.  Strip those separator-adjacent wrappers before
    # comparing individual answers.
    return [part.strip().strip("[]").strip() for part in _split_top_level(value, ";")]


class _BooleanParser:
    def __init__(self, text: str) -> None:
        compact = re.sub(r"\s+", "", _normalize_common(text))
        self.tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]*|[01]|[!&|>()]", compact)
        if "".join(self.tokens) != compact:
            raise ValueError("unsupported boolean syntax")
        self.index = 0

    def parse(self) -> tuple[object, ...]:
        expression = self._implication()
        if self.index != len(self.tokens):
            raise ValueError("trailing boolean tokens")
        return expression

    def _take(self, token: str) -> bool:
        if self.index < len(self.tokens) and self.tokens[self.index] == token:
            self.index += 1
            return True
        return False

    def _implication(self) -> tuple[object, ...]:
        left = self._or()
        if self._take(">"):
            return ("imp", left, self._implication())
        return left

    def _or(self) -> tuple[object, ...]:
        value = self._and()
        while self._take("|"):
            value = ("or", value, self._and())
        return value

    def _and(self) -> tuple[object, ...]:
        value = self._unary()
        while self._take("&"):
            value = ("and", value, self._unary())
        return value

    def _unary(self) -> tuple[object, ...]:
        if self._take("!"):
            return ("not", self._unary())
        if self._take("("):
            value = self._implication()
            if not self._take(")"):
                raise ValueError("unclosed boolean parenthesis")
            return value
        if self.index >= len(self.tokens):
            raise ValueError("missing boolean operand")
        token = self.tokens[self.index]
        self.index += 1
        if token == "0":
            return ("const", False)
        if token == "1":
            return ("const", True)
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", token):
            return ("var", token)
        raise ValueError("invalid boolean operand")


def _variables(expression: tuple[object, ...]) -> set[str]:
    if expression[0] == "var":
        return {str(expression[1])}
    result: set[str] = set()
    for item in expression[1:]:
        if isinstance(item, tuple):
            result.update(_variables(item))
    return result


def _evaluate(expression: tuple[object, ...], values: dict[str, bool]) -> bool:
    operator = expression[0]
    if operator == "const":
        return bool(expression[1])
    if operator == "var":
        return values[str(expression[1])]
    if operator == "not":
        return not _evaluate(expression[1], values)  # type: ignore[arg-type]
    left = _evaluate(expression[1], values)  # type: ignore[arg-type]
    right = _evaluate(expression[2], values)  # type: ignore[arg-type]
    if operator == "and":
        return left and right
    if operator == "or":
        return left or right
    if operator == "imp":
        return (not left) or right
    raise ValueError(f"Unsupported boolean operator {operator!r}")


def _boolean_equivalent(expected: str, actual: str) -> bool | None:
    try:
        expected_expression = _BooleanParser(expected).parse()
        actual_expression = _BooleanParser(actual).parse()
    except ValueError:
        return None
    names = sorted(_variables(expected_expression) | _variables(actual_expression))
    if len(names) > 8:
        return None
    for truth_values in product((False, True), repeat=len(names)):
        assignment = dict(zip(names, truth_values))
        if _evaluate(expected_expression, assignment) != _evaluate(actual_expression, assignment):
            return False
    return True


def _normalize_clause_text(value: str) -> str:
    value = _normalize_common(value)
    return re.sub(r"\s+", "", value)


def _strip_outer_braces(value: str) -> str | None:
    value = value.strip()
    if not value.startswith("{") or not value.endswith("}"):
        return None
    depth = 0
    for index, char in enumerate(value):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        if depth == 0 and index != len(value) - 1:
            return None
    return value[1:-1]


def _parse_clause_group(value: str) -> frozenset[frozenset[str]] | None:
    value = _normalize_clause_text(_strip_square_wrapper(value))
    value = re.sub(r"^S_?\d*=", "", value, flags=re.IGNORECASE)
    if value == "∅":
        return frozenset()
    inner = _strip_outer_braces(value)
    if inner is None:
        # A single resolvent is often rendered as ``[¬p, ¬q, s]`` rather
        # than ``[{¬p∨¬q∨s}]``.  Both describe one clause.
        delimiter = "," if "," in value else "|"
        literals = [literal.strip() for literal in _split_top_level(value, delimiter) if literal.strip()]
        return frozenset({frozenset(literals)}) if literals else None
    items = _split_top_level(inner, ",")
    if not items or any(not item for item in items):
        return None
    nested = all(_strip_outer_braces(item) is not None for item in items)
    clauses: set[frozenset[str]] = set()
    for item in items:
        clause_text = _strip_outer_braces(item) if nested else item
        assert clause_text is not None
        literals = _split_top_level(clause_text, "|")
        if nested:
            literals = _split_top_level(clause_text, ",")
        literals = [literal.strip() for literal in literals if literal.strip()]
        if not literals:
            return None
        clauses.add(frozenset(literals))
    return frozenset(clauses)


def _canonical_generic(value: str) -> str:
    value = _normalize_common(value)
    value = re.sub(r"\s+", "", value)
    return value.replace('"', "").replace("'", "").strip(".")


def _normalize_fol(value: str, *, legacy_expected: bool = False) -> str:
    """Normalize only notational variants used by task1807.

    Task1807 asks the model to execute an interpretation, not to simplify the
    resulting arithmetic.  Consequently this normalizer deliberately keeps
    ``x+0``, ``x*0``, operand order, variable names, and grouping intact.

    ``legacy_expected`` is restricted to the standard-answer side.  The
    original task1807 instance 69 gold wrote ``2x`` even though directly
    applying ``gJ(x, y) = x * y`` yields ``x*2``.  Supporting that legacy gold
    here lets historical result CSVs be rescored without accepting ``2x`` as a
    model answer.
    """
    value = _replace_text_commands(value)

    # A model may redundantly annotate quantified variables with the already
    # fixed natural-number domain.  This is an explicitly accepted task-local
    # presentation variant.
    quantifier_domain = re.compile(
        r"((?:\\forall|\\exists|∀|∃)\s*[A-Za-z][A-Za-z0-9_]*)\s*"
        r"(?:\\in|∈)\s*"
        r"(?:\\mathbb\s*\{\s*N\s*\}|\\mathbb\s+N|ℕ|N(?![A-Za-z0-9_]))"
    )
    previous = None
    while value != previous:
        previous = value
        value = quantifier_domain.sub(r"\1", value)

    # Remove math-environment and size/spacing commands without changing the
    # represented formula.
    for delimiter in (r"\(", r"\)", r"\[", r"\]"):
        value = value.replace(delimiter, "")
    value = value.replace("$", "")
    value = re.sub(r"\\[,;!:]", "", value)
    value = re.sub(
        r"\\(?:qquad|quad|enspace|thinspace|medspace|thickspace|"
        r"Biggl|Biggr|biggl|biggr|Bigl|Bigr|bigl|bigr|Bigg|bigg|Big|big)\b",
        "",
        value,
    )

    value = _normalize_common(value)
    value = (
        value.replace("·", "*")
        .replace("×", "*")
        .replace("∗", "*")
        .replace("⇒", "→")
        .replace("⟹", "→")
        .replace("->", "→")
        .replace("=>", "→")
        .replace(r"\ast", "*")
    )
    # Braces are accepted as grouping delimiters, but are not discarded: they
    # become parentheses so formula structure remains visible to the parser.
    value = value.replace("{", "(").replace("}", ")")
    value = re.sub(r"\s+", "", value)
    if legacy_expected:
        value = re.sub(
            r"(?<![A-Za-z0-9_])(\d+)([A-Za-z][A-Za-z0-9_]*)",
            r"\2*\1",
            value,
        )
    return value


class _Task1807FormulaParser:
    """Parse the small first-order/arithmetic language used by task1807."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = re.findall(
            r"∀|∃|→|\(|\)|\+|\*|=|[A-Za-z][A-Za-z0-9_]*|\d+",
            text,
        )
        if "".join(self.tokens) != text:
            raise ValueError("unsupported task1807 syntax")
        self.index = 0

    def parse(self) -> tuple:
        expression = self._parse_implication()
        if self.index != len(self.tokens):
            raise ValueError("trailing task1807 tokens")
        return expression

    def _peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _take(self, expected: str | None = None) -> str:
        token = self._peek()
        if token is None or (expected is not None and token != expected):
            raise ValueError(f"expected {expected or 'token'}")
        self.index += 1
        return token

    def _parse_implication(self) -> tuple:
        left = self._parse_unary_formula()
        if self._peek() == "→":
            self._take("→")
            return ("imp", left, self._parse_implication())
        return left

    def _parse_unary_formula(self) -> tuple:
        token = self._peek()
        if token in {"∀", "∃"}:
            quantifier = self._take()
            variable = self._take()
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", variable):
                raise ValueError("invalid quantified variable")
            # A quantifier binds the following unary formula.  Parentheses can
            # explicitly widen its scope to an implication.
            return ("quant", quantifier, variable, self._parse_unary_formula())

        if token == "(":
            start = self.index
            self._take("(")
            try:
                nested = self._parse_implication()
                self._take(")")
                return nested
            except ValueError:
                self.index = start

        return self._parse_atom()

    def _parse_atom(self) -> tuple:
        left = self._parse_term()
        self._take("=")
        return ("eq", left, self._parse_term())

    def _parse_term(self) -> tuple:
        expression = self._parse_product()
        while self._peek() == "+":
            self._take("+")
            expression = ("add", expression, self._parse_product())
        return expression

    def _parse_product(self) -> tuple:
        expression = self._parse_primary()
        while self._peek() == "*":
            self._take("*")
            expression = ("mul", expression, self._parse_primary())
        return expression

    def _parse_primary(self) -> tuple:
        token = self._peek()
        if token == "(":
            self._take("(")
            expression = self._parse_term()
            self._take(")")
            return expression
        if token is None or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_]*|\d+", token
        ):
            raise ValueError("invalid arithmetic term")
        self._take()
        return ("number", token) if token.isdigit() else ("name", token)


def _parse_task1807_formula(
    value: str, *, legacy_expected: bool = False
) -> tuple[tuple | None, str]:
    normalized = _normalize_fol(value, legacy_expected=legacy_expected)
    try:
        return _Task1807FormulaParser(normalized).parse(), normalized
    except ValueError:
        return None, normalized


def _task1807_answer_parts(value: str) -> list[str]:
    # A LaTeX spacing command must not be mistaken for the separator between
    # two task answers.
    value = re.sub(r"\\[;,!]", "", value).strip()
    # Accept ``[[A];[B]]``, ``[ [A];[B] ]``, and the explicitly permitted
    # one-layer-short ``[A];[B]`` without discarding brackets that affect only
    # one item.
    while value.startswith("[") and value.endswith("]"):
        depth = 0
        encloses_entire_value = True
        for index, char in enumerate(value):
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0 and index != len(value) - 1:
                    encloses_entire_value = False
                    break
        if not encloses_entire_value or depth != 0:
            break
        value = value[1:-1].strip()
    return _answer_parts(value)


def _task1807_answer_candidates(text: str) -> list[str]:
    """Return task1807 candidates, including permitted missing wrappers."""
    candidates: list[str] = []
    explicit = extract_semantic_answer(text)
    if explicit:
        candidates.append(explicit)

    stripped = text.strip()
    # The raw candidate recovers ``[A];[B]`` (one missing outer layer) and a
    # bare formula.  Prose does not become a false positive because the task
    # parser rejects non-formula tokens.
    if stripped and len(stripped) <= 500:
        candidates.append(stripped)

    nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if nonempty_lines and len(nonempty_lines[-1]) <= 500:
        candidates.append(nonempty_lines[-1])

    # Do not allow a rationale display to override an explicitly formatted
    # final answer.  With no explicit answer, a display formula is an accepted
    # wrapper-free response for this task.
    if not explicit:
        candidates.extend(_latex_math_candidates(text))
    return list(dict.fromkeys(candidates))


def _normalize_rule_symbolization(value: str) -> str:
    value = re.sub(r"\s+", "", _normalize_common(value))
    return re.sub(r"\bIf([A-Za-z]+)\(([^()]*)\),then", r"\1(\2)→", value)


def _remove_fol_domain_annotations(value: str) -> str:
    return re.sub(r";\s*(?:\\text\{[^{}]*\}\s*)?\\mathbb\{N\}", "", value)


def _assessment(
    extracted: str | None,
    expected: str,
    score: int | None,
    normalized_expected: str,
    normalized_answer: str,
    reason: str,
) -> SemanticAssessment:
    return SemanticAssessment(
        extracted_answer=extracted or "",
        score=score,
        status="manual_review" if score is None else ("correct" if score else "incorrect"),
        normalized_expected=normalized_expected,
        normalized_answer=normalized_answer,
        reason=reason,
    )


def _is_invalid_standard_answer(task_id: str, expected: str) -> bool:
    """Return whether an upstream dataset marks the row as unscorable.

    Public instance files use ``INVALID`` when a reference item must be
    excluded rather than routed to manual scoring.
    """
    del task_id  # Retained in the signature for compatibility with callers.
    normalized = expected.strip()
    return normalized.upper() == "INVALID"


def score_semantic_row(
    task_id: str,
    expected: str,
    model_output: str,
    instance_content: str = "",
) -> SemanticAssessment:
    """Score one row, keeping failed or ambiguous extraction for manual review."""
    if model_output.strip().lower().startswith("error: chat completion failed"):
        return _assessment(
            None,
            expected,
            0 if task_id == "1807" else None,
            expected.strip(),
            "",
            "model_api_error",
        )

    if task_id in MULTIPLE_CHOICE_TASKS:
        expected_labels = _multiple_choice_labels(expected)
        extracted = (
            extract_task385_answer(model_output, instance_content)
            if task_id == "385"
            else (
                extract_task1424_1678_answer(model_output)
                if task_id in {"1424", "1678"}
                else extract_multiple_choice_answer(model_output)
            )
        )
        normalized_expected = ",".join(expected_labels)
        if not expected_labels:
            expected_value = _numeric_value(expected)
            if expected_value is not None:
                contains_expected = expected_value in _numeric_values_in_text(model_output)
                if contains_expected and extracted in {None, "NONE"}:
                    return _assessment(
                        expected,
                        expected,
                        1,
                        str(expected_value),
                        str(expected_value),
                        "corrected_numeric_answer_match",
                    )
                if contains_expected:
                    return _assessment(
                        extracted,
                        expected,
                        None,
                        str(expected_value),
                        extracted or "",
                        "numeric_answer_with_conflicting_option_label",
                    )
                if extracted is not None:
                    return _assessment(
                        extracted,
                        expected,
                        0,
                        str(expected_value),
                        extracted,
                        "corrected_numeric_answer_mismatch",
                    )
                return _assessment(
                    None,
                    expected,
                    None,
                    str(expected_value),
                    "",
                    "missing_or_ambiguous_corrected_numeric_answer",
                )
            return _assessment(
                extracted,
                expected,
                None,
                "",
                extracted or "",
                "invalid_multiple_choice_standard_answer",
            )
        value_labels = (
            _multiple_choice_value_labels(model_output, instance_content)
            if task_id in {"1424", "1678"}
            else ()
        )
        if extracted is None and value_labels:
            normalized_answer = ",".join(value_labels)
            correct = bool(set(value_labels) & set(expected_labels))
            return _assessment(
                normalized_answer,
                expected,
                int(correct),
                normalized_expected,
                normalized_answer,
                (
                    "multiple_choice_value_match"
                    if correct
                    else "multiple_choice_value_mismatch"
                ),
            )
        if extracted is None and task_id == "1424":
            final_value = _final_numeric_value(model_output)
            if final_value is not None:
                final_labels = _labels_for_numeric_option_value(
                    final_value, instance_content
                )
                normalized_answer = (
                    ",".join(final_labels) if final_labels else str(final_value)
                )
                correct = bool(set(final_labels) & set(expected_labels))
                return _assessment(
                    normalized_answer,
                    expected,
                    int(correct),
                    normalized_expected,
                    normalized_answer,
                    (
                        "multiple_choice_final_numeric_match"
                        if correct
                        else "multiple_choice_final_numeric_mismatch"
                    ),
                )
        if extracted is None:
            return _assessment(
                None,
                expected,
                None,
                normalized_expected,
                "",
                "missing_or_ambiguous_multiple_choice_answer",
            )
        if extracted == "NONE":
            if task_id in {"1424", "1678"}:
                none_labels = _none_option_labels(instance_content)
                if none_labels:
                    normalized_answer = ",".join(none_labels)
                    correct = bool(set(none_labels) & set(expected_labels))
                    return _assessment(
                        normalized_answer,
                        expected,
                        int(correct),
                        normalized_expected,
                        normalized_answer,
                        (
                            "none_option_label_match"
                            if correct
                            else "none_option_label_mismatch"
                        ),
                    )
                return _assessment(
                    extracted,
                    expected,
                    0,
                    normalized_expected,
                    extracted,
                    "none_of_listed_options_mismatch",
                )
            return _assessment(
                extracted,
                expected,
                None,
                normalized_expected,
                extracted,
                "none_of_listed_options_requires_manual_review",
            )
        correct = extracted in expected_labels
        return _assessment(
            extracted,
            expected,
            int(correct),
            normalized_expected,
            extracted,
            "multiple_choice_label_match" if correct else "multiple_choice_label_mismatch",
        )

    if task_id == "190":
        expected_answer = extract_task190_answer(expected)
        extracted = extract_task190_answer(model_output)
        if expected_answer is None:
            return _assessment(None, expected, None, "", "", "invalid_standard_answer")
        if extracted is None:
            return _assessment(None, expected, None, expected_answer, "", "missing_or_ambiguous_task190_answer")
        return _assessment(
            extracted,
            expected,
            int(expected_answer == extracted),
            expected_answer,
            extracted,
            "task190_relation_label_comparison",
        )

    if task_id == "1162":
        expected_answer = extract_boolean_answer(expected)
        extracted = extract_boolean_answer(model_output)
        if expected_answer is None:
            return _assessment(extracted, expected, None, "", extracted or "", "invalid_boolean_standard_answer")
        if extracted is None:
            return _assessment(None, expected, None, expected_answer, "", "missing_or_ambiguous_boolean_answer")
        return _assessment(
            extracted,
            expected,
            int(expected_answer == extracted),
            expected_answer,
            extracted,
            "boolean_label_comparison",
        )

    expected_answer = extract_semantic_answer(expected) or expected.strip().split(",")[0].strip()
    extracted = extract_semantic_answer(model_output)
    if not expected_answer:
        return _assessment(extracted, expected, None, "", "", "invalid_standard_answer")
    if extracted is None and task_id not in {"1804", "1807"}:
        return _assessment(None, expected, None, expected_answer, "", "missing_or_ambiguous_final_answer")

    expected_parts = _answer_parts(expected_answer)
    answer_parts = _answer_parts(extracted) if extracted is not None else []
    if task_id == "1802":
        if len(expected_parts) == len(answer_parts):
            equivalents = [_boolean_equivalent(left, right) for left, right in zip(expected_parts, answer_parts)]
            if all(value is not None for value in equivalents):
                equivalent = all(bool(value) for value in equivalents)
                return _assessment(
                    extracted,
                    expected,
                    int(equivalent),
                    ";".join(_canonical_generic(part) for part in expected_parts),
                    ";".join(_canonical_generic(part) for part in answer_parts),
                    "boolean_truth_table_equivalent" if equivalent else "boolean_truth_table_mismatch",
                )
        normalized_expected = _canonical_generic(expected_answer)
        normalized_answer = _canonical_generic(extracted)
        return _assessment(extracted, expected, int(normalized_expected == normalized_answer), normalized_expected, normalized_answer, "strict_nonformula_comparison")

    if task_id == "1804":
        expected_groups = [_parse_clause_group(part) for part in expected_parts]
        candidates = (
            [extracted]
            if extracted is not None
            else _structured_answer_candidates(model_output)
        )
        for candidate in candidates:
            candidate_parts = _answer_parts(candidate)
            answer_groups = [_parse_clause_group(part) for part in candidate_parts]
            if (
                len(expected_groups) == len(answer_groups)
                and all(
                    group is not None
                    for group in expected_groups + answer_groups
                )
            ):
                equivalent = expected_groups == answer_groups
                return _assessment(
                    candidate,
                    expected,
                    int(equivalent),
                    repr(expected_groups),
                    repr(answer_groups),
                    (
                        "clause_set_equivalent"
                        if equivalent
                        else "clause_set_mismatch"
                    ),
                )
        if extracted is None:
            return _assessment(
                None,
                expected,
                None,
                repr(expected_groups),
                "",
                "missing_or_ambiguous_clause_answer",
            )
        normalized_expected = _canonical_generic(expected_answer)
        normalized_answer = _canonical_generic(extracted)
        return _assessment(extracted, expected, int(normalized_expected == normalized_answer), normalized_expected, normalized_answer, "strict_non_clause_comparison")

    if task_id == "1807":
        expected_parts = _task1807_answer_parts(expected_answer)
        expected_parsed = [
            _parse_task1807_formula(part, legacy_expected=True)
            for part in expected_parts
        ]
        expected_asts = [parsed for parsed, _ in expected_parsed]
        normalized_expected_parts = [normalized for _, normalized in expected_parsed]
        if any(parsed is None for parsed in expected_asts):
            return _assessment(
                extracted,
                expected,
                None,
                ";".join(normalized_expected_parts),
                "",
                "invalid_task1807_standard_answer",
            )

        candidates = _task1807_answer_candidates(model_output)
        first_normalized_answer = ""
        for candidate in candidates:
            candidate_parts = _task1807_answer_parts(candidate)
            answer_parsed = [
                _parse_task1807_formula(part) for part in candidate_parts
            ]
            answer_asts = [parsed for parsed, _ in answer_parsed]
            normalized_answer_parts = [normalized for _, normalized in answer_parsed]
            if not first_normalized_answer:
                first_normalized_answer = ";".join(normalized_answer_parts)
            if (
                len(expected_asts) == len(answer_asts)
                and all(parsed is not None for parsed in answer_asts)
                and expected_asts == answer_asts
            ):
                return _assessment(
                    candidate,
                    expected,
                    1,
                    ";".join(normalized_expected_parts),
                    ";".join(normalized_answer_parts),
                    "interpretation_normal_form_equivalent",
                )
        return _assessment(
            extracted or (candidates[0] if candidates else None),
            expected,
            0,
            ";".join(normalized_expected_parts),
            first_normalized_answer,
            (
                "interpretation_normal_form_mismatch"
                if candidates
                else "missing_interpretation_answer"
            ),
        )

    if task_id == "1819":
        normalized_expected = _normalize_rule_symbolization(expected_answer)
        normalized_answer = _normalize_rule_symbolization(extracted)
        return _assessment(
            extracted,
            expected,
            int(normalized_expected == normalized_answer),
            normalized_expected,
            normalized_answer,
            "rule_symbolization_equivalent" if normalized_expected == normalized_answer else "rule_symbolization_mismatch",
        )

    normalized_expected = _canonical_generic(expected_answer)
    normalized_answer = _canonical_generic(extracted)
    return _assessment(
        extracted,
        expected,
        int(normalized_expected == normalized_answer),
        normalized_expected,
        normalized_answer,
        "strict_semantic_v2_comparison",
    )

def _load_manual_review(path: Path) -> tuple[dict[tuple[str, str], str], list[dict[str, str]]]:
    if not path.is_file():
        return {}, []
    _, rows = _read_csv(path)
    overrides = {
        (row.get("source_csv", "").strip(), row.get("instance_id", "").strip()): row.get("manual_score", "").strip()
        for row in rows
    }
    return overrides, rows


def _review_row(row: dict[str, str], relative: str, csv_row: int) -> dict[str, str]:
    return {
        "task_id": row["task_id"],
        "model": row["model"],
        "language": row["language"],
        "source_csv": relative,
        "csv_row": str(csv_row),
        "instance_id": row["instance_id"],
        "standard_output": row["standard_output"],
        "instance_content": row["instance_content"],
        "model_output": row.get("model_output", ""),
        "extracted_answer": row.get("extracted_answer", ""),
        "manual_score": "2",
    }


def run(config: PipelineConfig, *, run_root: Path | None = None) -> tuple[int, int]:
    run_root = run_root or resolve_run_root(config)
    review_path = run_root / "manual_review.csv"
    overrides, review_rows = _load_manual_review(review_path)
    existing_keys = set(overrides)
    additions: list[dict[str, str]] = []
    unresolved_keys: set[tuple[str, str]] = set()
    invalid_keys: set[tuple[str, str]] = set()
    scored = total = 0

    for path in result_files(run_root):
        fields, rows = _read_csv(path)
        relative = path.relative_to(run_root).as_posix()
        modified = False
        for csv_row, row in enumerate(rows, start=2):
            total += 1
            key = (relative, row["instance_id"].strip())
            if _is_invalid_standard_answer(row["task_id"], row.get("standard_output", "")):
                row["extracted_answer"] = "INVALID"
                row["score"] = "X"
                invalid_keys.add(key)
                modified = True
                continue
            manual_score = overrides.get(key, "")
            if manual_score in {"0", "1"}:
                if row.get("score", "") != manual_score:
                    row["score"] = manual_score
                    modified = True
                scored += 1
                continue
            output = row.get("model_output", "").strip()
            assessment = score_semantic_row(
                row["task_id"],
                row["standard_output"],
                output,
                row.get("instance_content", ""),
            )
            row["extracted_answer"] = assessment.extracted_answer
            score = assessment.score
            if score is None:
                row["score"] = "2"
                unresolved_keys.add(key)
                if key not in existing_keys:
                    additions.append(_review_row(row, relative, csv_row))
                    existing_keys.add(key)
            else:
                row["score"] = str(score)
                scored += 1
            modified = True
        if modified:
            write_csv(path, fields, rows)

    # Retain explicit human decisions, plus only those previous review rows
    # that are still unresolved.  This lets improved task-specific extraction
    # clear stale ``manual_score=2`` rows on a later Step 2 run.
    merged = {
        (row.get("source_csv", "").strip(), row.get("instance_id", "").strip()): row
        for row in review_rows
        if (row.get("source_csv", "").strip(), row.get("instance_id", "").strip()) not in invalid_keys
        and (
            row.get("manual_score", "").strip() in {"0", "1"}
            or (row.get("source_csv", "").strip(), row.get("instance_id", "").strip()) in unresolved_keys
        )
    }
    for row in additions:
        merged.setdefault((row["source_csv"], row["instance_id"]), row)
    all_reviews = [merged[key] for key in sorted(merged)]
    write_csv(review_path, MANUAL_FIELDS, all_reviews)
    unresolved = sum(row.get("manual_score", "").strip() not in {"0", "1"} for row in all_reviews)
    print(f"Step 2 complete: total={total}, scored={scored}, manual_review={unresolved}")
    return scored, unresolved


if __name__ == "__main__":
    from main import build_config

    run(build_config())
