from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from .llm_client import create_llm_client, create_prompt_section


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
CLEAN_VALIDATION_SENTENCE = (
    "If no syntax error described by this prompt is found, return an empty "
    "JSON list: []."
)


SYNTAX_SYSTEM_PROMPT = r"""
You perform syntax-only static analysis for CNL-P v0.0.1. Check the concrete
grammar and structural placement of sentences. Do not analyze natural-language
meaning, business logic, variable scope, symbol existence, types of referenced
variables, API existence, API signatures, Worker call contracts, control-flow
reachability, or Example execution-path semantics.

1. Top-level structure

- An Agent starts with `[DEFINE_AGENT: AgentName]` and ends with `[END_AGENT]`.
  An optional quoted description may follow AgentName, for example
  `[DEFINE_AGENT: DietAdvisor "Diet advice Agent."]`.
- PERSONA and at least one WORKER are required. AUDIENCE, CONCEPTS,
  CONSTRAINTS, TYPES, and VARIABLES are optional.
- Each section must be inside the Agent and use its matching start/end pair.
- PERSONA must contain a non-empty `ROLE: description` sentence. Every Agent
  aspect name must start with an uppercase letter; its remaining characters
  may be letters, digits, or underscores. Both `Communication_Style` and
  `COMMUNICATION_STYLE` are therefore syntactically valid names. Every aspect
  must have a non-empty description after `:`.
- Multiple Workers are allowed and each uses
  `[DEFINE_WORKER: "optional description" WorkerName] ... [END_WORKER]`.

2. Worker structure

- INPUTS, OUTPUTS, and EXAMPLES are optional singleton Worker sections; each
  may occur at most once. MAIN_FLOW is a required singleton section.
- An optional Worker section must be omitted completely when it has no items.
  In particular, `[INPUTS][END_INPUTS]` and `[OUTPUTS][END_OUTPUTS]` with no
  content between the identifiers are invalid empty sections.
- ALTERNATIVE_FLOW and EXCEPTION_FLOW may occur more than once.
- Worker sections are not required to appear in a particular order. In
  particular, EXAMPLES may legally appear before MAIN_FLOW.
- INPUTS and OUTPUTS contain references, optionally prefixed by REQUIRED or
  OPTIONAL, for example `REQUIRED <REF>user</REF>`.
- Every MAIN_FLOW, ALTERNATIVE_FLOW, and EXCEPTION_FLOW must contain at least
  one Block.
- EXCEPTION_FLOW contains exactly one LOG sentence before its first Block.

3. Blocks and branches

- Sequential Block:
  `[SEQUENTIAL_BLOCK]` commands `[END_SEQUENTIAL_BLOCK]`.
- Conditional Block:
  `[IF condition]` commands, zero or more `[ELSEIF condition]` branches, an
  optional `[ELSE]`, and `[END_IF]`.
- Loop Blocks use `[WHILE condition] ... [END_WHILE]` or
  `[FOR condition] ... [END_FOR]`.
- Blocks cannot be empty or nested inside another Block.
- ELSE and ELSEIF are legal only inside IF. ELSE occurs at most once, and no
  ELSEIF may occur after ELSE.

4. Commands

Every command starts with `COMMAND-` followed by an integer and then exactly
one bracketed body. The integer pattern is syntactic; do not check numbering
uniqueness or execution order.

- General command:
  `COMMAND-n [COMMAND non-empty description [RESULT target SET|APPEND]]`
- Input command:
  `COMMAND-n [INPUT [DISPLAY] non-empty description VALUE target SET|APPEND]`
- Call command:
  `COMMAND-n [CALL Target [WITH {name: value, ...}]
  [RESPONSE target SET|APPEND]]`
- Display command:
  `COMMAND-n [DISPLAY non-empty description]`

A target is either a declaration such as `name: Type` or a reference such as
`<REF>name</REF>`. For CALL arguments, each formal argument name must be a valid
identifier, must have a non-empty value after `:`, and must not occur twice in
the same WITH object. An empty argument object `WITH {}` is invalid; omit WITH
when there are no arguments.

The following are explicitly valid general commands:

- `COMMAND-1 [COMMAND Analyze the input]`
- `COMMAND-2 [COMMAND Analyze the input RESULT report: text SET]`
- `COMMAND-3 [COMMAND Improve the report RESULT <REF>report</REF> SET]`

All text before the final RESULT clause is natural-language description and may
contain punctuation, colons, words that resemble types, and ordinary uses of
the word SET. Do not infer a malformed result merely from descriptive text.

5. Types and references

- Common simple types include `text`, `str`, `string`, `int`, `float`,
  `number`, `bool`, and `boolean`.
- Enumeration syntax is `[value1, value2]`.
- A quoted description line may immediately precede a type declaration, for
  example `"User profile"` followed by `UserInfo = {...}`.
- Record syntax is `{field: Type, other_field: Type}`. A record field may have
  an optional quoted description immediately before its name, for example
  `{"REQUIRED" user_name: text, "OPTIONAL" note: text}`. The quoted text is a
  syntactic description, not an INPUTS/OUTPUTS qualifier, and is legal.
- List syntax is `List[Type]`. Whitespace around brackets is insignificant, so
  both `List[text]` and `List [text]` are syntactically acceptable.
- References use a matched `<REF>name</REF>` pair. Whitespace immediately
  inside the pair is syntactically acceptable.
- This is syntax analysis: do not report an error merely because a referenced
  name, declared type, API, or Worker cannot be resolved.

6. Examples

- EXAMPLES contains EXPECTED-WORKER-BEHAVIOR and/or DEFECT-WORKER-BEHAVIOR
  records.
- Expected records use a matched
  `<EXPECTED-WORKER-BEHAVIOR> { ... } </EXPECTED-WORKER-BEHAVIOR>` pair and
  contain inputs, expected-outputs, and execution-path.
- Defect records use a matched
  `<DEFECT-WORKER-BEHAVIOR> { ... } </DEFECT-WORKER-BEHAVIOR>` pair and contain
  a defect type, inputs, defect-outputs, execution-path, and
  defect-explanation.
- The defect type is intentionally the first bare item and has no key or colon.
  For example, `Processing Logic Error,` followed by `inputs: {...}` is legal.
- Check delimiters, required record fields, key/value punctuation, and the
  `COMMAND-n` token pattern only. Do not judge whether values, outputs, or paths
  make semantic sense.

7. Error categories

- Structural Anomalies: content outside its legal section; mismatched,
  missing, duplicated, or improperly nested identifier sections; duplicate
  singleton Worker sections; empty/nested Blocks; Flow without Block; illegal
  branch placement/order; invalid EXCEPTION_FLOW LOG placement.
- Sentence Pattern Issues: malformed or empty Agent aspects; malformed type or
  variable declarations; malformed command number/body/result; malformed CALL
  arguments; malformed DISPLAY; malformed Example records.
- Reference Issues: malformed or unmatched REF tags. Do not perform name
  resolution.
- Missing Required Fields: PERSONA lacks ROLE, or a Worker lacks MAIN_FLOW.

8. Output

Return only a valid JSON list with no Markdown or prose. Each error object has
exactly these fields:

[
  {
    "start_line": 1,
    "end_line": 1,
    "error_content": "the offending source text",
    "error_message": "the syntax error explanation"
  }
]

Line numbers are one-based. For a missing field without a precise source line,
use 0 for both line fields and an empty error_content. Report only errors found
in the supplied CNL-P instance; never copy source text from this prompt.
"""


def build_syntax_system_prompt(*, clean_validation: bool = False) -> str:
    if clean_validation:
        return f"{SYNTAX_SYSTEM_PROMPT}\n{CLEAN_VALIDATION_SENTENCE}"
    return SYNTAX_SYSTEM_PROMPT


def syntax_issue_linting_agent(
    cnl_p: str,
    *,
    clean_validation: bool = False,
    max_retries: int = 10,
    retry_delay_seconds: int = 15,
    attempt_log_path: Path | None = None,
    attempt_context: dict[str, Any] | None = None,
) -> str:
    messages = [
        create_prompt_section(
            role="system",
            content=build_syntax_system_prompt(
                clean_validation=clean_validation,
            ),
        ),
        create_prompt_section(
            role="user",
            content=(
                "Analyze the following CNL-P instance at the syntax level:\n\n"
                f"{cnl_p}"
            ),
        ),
    ]
    llm_client = create_llm_client(dotenv_values(WORKSPACE_ROOT / ".env"))
    return llm_client.complete(
        messages,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay_seconds,
        attempt_log_path=attempt_log_path,
        attempt_context=attempt_context,
    )


__all__ = [
    "CLEAN_VALIDATION_SENTENCE",
    "SYNTAX_SYSTEM_PROMPT",
    "build_syntax_system_prompt",
    "syntax_issue_linting_agent",
]
