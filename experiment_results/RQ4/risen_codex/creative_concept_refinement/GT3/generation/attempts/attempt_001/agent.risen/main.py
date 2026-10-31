from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI


QUALITY_THRESHOLD = 8.0
MAX_REFINEMENTS = 2
BRIEF_FIELDS = [
    'brand', 'product', 'target_audience', 'objective',
    'key_product_benefit', 'channels', 'budget', 'constraints',
]


def load_dotenv() -> None:
    path = Path.cwd() / '.env'
    if not path.is_file():
        return
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in chr(39) + chr(34):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def get_client() -> tuple[OpenAI, str]:
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    base_url = os.getenv('BASE_URL', '').strip()
    model = os.getenv('CNLP_REFERENCE_LLM_MODEL', '').strip() or os.getenv('OPENAI_MODEL', '').strip()
    missing = [name for name, value in (
        ('OPENAI_API_KEY', api_key),
        ('BASE_URL', base_url),
        ('CNLP_REFERENCE_LLM_MODEL or OPENAI_MODEL', model),
    ) if not value]
    if missing:
        raise RuntimeError('Missing runtime model configuration: ' + ', '.join(missing) + '. Set it in .env or the process environment.')
    return OpenAI(api_key=api_key, base_url=base_url), model


def extract_json_object(text: str) -> str:
    start = text.find('{')
    if start < 0:
        return text
    depth, in_string, escaped = 0, False, False
    slash, quote = chr(92), chr(34)
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == slash:
                escaped = True
            elif char == quote:
                in_string = False
            continue
        if char == quote:
            in_string = True
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return text[start:]


def remove_trailing_commas(text: str) -> str:
    output, in_string, escaped, index = [], False, False, 0
    slash, quote = chr(92), chr(34)
    while index < len(text):
        char = text[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == slash:
                escaped = True
            elif char == quote:
                in_string = False
            index += 1
            continue
        if char == quote:
            in_string = True
        elif char == ',':
            next_index = index + 1
            while next_index < len(text) and text[next_index].isspace():
                next_index += 1
            if next_index < len(text) and text[next_index] in '}]':
                index += 1
                continue
        output.append(char)
        index += 1
    return ''.join(output)


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith(chr(96) * 3):
        lines = cleaned.splitlines()[1:]
        if lines and lines[-1].strip() == chr(96) * 3:
            lines = lines[:-1]
        cleaned = chr(10).join(lines).strip()
    try:
        value = json.loads(remove_trailing_commas(extract_json_object(cleaned)))
    except json.JSONDecodeError as exc:
        raise ValueError('Model returned invalid JSON: ' + cleaned) from exc
    if not isinstance(value, dict):
        raise ValueError('Model JSON response must be an object.')
    return value


def required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Field ' + field + ' must be non-empty text.')
    return value.strip()


def extract_brief(answer: str) -> dict[str, str]:
    client, model = get_client()
    prompt = '''Extract a complete CreativeBrief from this single free-form answer.
Return one strict JSON object with exactly these text fields: %s.
Map only information supplied by the user; do not guess or invent. Use an empty string when absent.

USER ANSWER:
%s
''' % (json.dumps(BRIEF_FIELDS), answer)
    response = client.responses.create(model=model, input=prompt, reasoning={'effort': 'high'})
    data = parse_json_response(response.output_text)
    return {field: required_text(data.get(field), field) for field in BRIEF_FIELDS}


def generate_concept(brief: dict[str, str]) -> str:
    client, model = get_client()
    prompt = '''You are CreativeConceptDeveloper, a creative director assistant.
Generate one complete and specific marketing creative concept from the brief.
Clearly describe the core idea, principal execution, brand or product role, and how it serves the target audience and objective.
Ground every claim and detail in the brief. Do not invent capabilities, resources, partnerships, research, or facts.
Return only the concept in clear prose, with no JSON, alternatives, scores, or process commentary.

CREATIVE BRIEF:
%s
''' % json.dumps(brief, ensure_ascii=False, indent=2)
    response = client.responses.create(model=model, input=prompt, reasoning={'effort': 'high'})
    concept = response.output_text.strip()
    if not concept:
        raise ValueError('Concept generation returned an empty concept.')
    return concept


def evaluate_creative_concept(creative_brief: dict[str, str], creative_concept: str) -> dict[str, Any]:
    if not isinstance(creative_brief, dict):
        raise ValueError('creative_brief must be a dictionary.')
    if not isinstance(creative_concept, str) or not creative_concept.strip():
        raise ValueError('creative_concept must be a non-empty string.')
    client, model = get_client()
    rubric = '''Evaluate an advertising or marketing creative concept using these weighted criteria.
Score each from 1 to 10, using the full scale and grounding judgments in the brief and concept.
ORIGINALITY weight 0.30: generic 1-3, modest twist 4-5, differentiated 6-7, strong memorable product-specific 8, exceptional 9-10.
STRATEGIC FIT weight 0.30: misses brief 1-3, partly relevant 4-5, addresses audience/objective/benefit 6-7, strongly solves brief with central product role 8, unusually precise 9-10.
AUDIENCE IMPACT weight 0.20: confusing/flat 1-3, mildly interesting 4-5, clear/engaging 6-7, immediately memorable hook 8, exceptionally compelling 9-10.
EXECUTABILITY weight 0.20: conflicts with constraints 1-3, complex/risky 4-5, practical/adaptable 6-7, simple/reusable 8, unusually efficient 9-10.
Do not invent facts, capabilities, partnerships, research, or resources. Explain important strengths and weaknesses and give concrete refinement directions.
Return only strict JSON with exactly: originality_score, strategic_fit_score, audience_impact_score, executability_score, evaluation_reasons, refinement_suggestions. Scores are integers 1-10. Do not calculate overall_score.'''
    prompt = rubric + chr(10) + chr(10) + 'CREATIVE BRIEF:' + chr(10) + json.dumps(creative_brief, ensure_ascii=False, indent=2) + chr(10) + chr(10) + 'CURRENT CREATIVE CONCEPT:' + chr(10) + creative_concept
    response = client.responses.create(model=model, input=prompt, reasoning={'effort': 'high'})
    raw = parse_json_response(response.output_text)
    fields = ['originality_score', 'strategic_fit_score', 'audience_impact_score', 'executability_score']
    scores: dict[str, float] = {}
    for field in fields:
        if field not in raw:
            raise ValueError('Missing score in evaluation result: ' + field)
        try:
            score = float(raw[field])
        except (TypeError, ValueError) as exc:
            raise ValueError(field + ' must be numeric.') from exc
        if not score.is_integer() or not 1 <= score <= 10:
            raise ValueError(field + ' must be an integer between 1 and 10.')
        scores[field] = score
    criteria = {
        'originality': scores['originality_score'],
        'strategic_fit': scores['strategic_fit_score'],
        'audience_impact': scores['audience_impact_score'],
        'executability': scores['executability_score'],
    }
    overall = (scores['originality_score'] * .30 + scores['strategic_fit_score'] * .30 + scores['audience_impact_score'] * .20 + scores['executability_score'] * .20)
    return {
        **{field: int(score) for field, score in scores.items()},
        'overall_score': round(overall, 2),
        'weak_criteria': [name for name, score in criteria.items() if score == min(criteria.values())],
        'evaluation_reasons': required_text(raw.get('evaluation_reasons'), 'evaluation_reasons'),
        'refinement_suggestions': required_text(raw.get('refinement_suggestions'), 'refinement_suggestions'),
    }


def refine_creative_concept(creative_brief: dict[str, str], current_concept: str, evaluation: dict[str, Any]) -> str:
    if not isinstance(creative_brief, dict):
        raise ValueError('creative_brief must be a dictionary.')
    if not isinstance(current_concept, str) or not current_concept.strip():
        raise ValueError('current_concept must be a non-empty string.')
    weak = evaluation.get('weak_criteria') if isinstance(evaluation, dict) else None
    if not isinstance(weak, list):
        raise ValueError('evaluation.weak_criteria must be a list.')
    client, model = get_client()
    methodology = '''Revise the existing marketing concept. Improve the weakest criteria while preserving useful strengths and faithfulness to the original brief. Originality should use a distinctive product, brand, audience, or context mechanism. Strategic fit should connect audience, objective, benefit, channels, and constraints. Audience impact should sharpen the hook, payoff, clarity, and memorability. Executability should simplify unnecessary elements and fit the stated budget and channels. Never invent capabilities, budgets, partners, celebrities, technologies, research, or market facts. Do not solve a weakness by merely adding messages or mechanics. Return one complete revised concept only, not alternatives, scores, or commentary. It must describe the core idea, main execution, product or brand role, and audience/objective connection.'''
    prompt = methodology + chr(10) + chr(10) + 'ORIGINAL CREATIVE BRIEF:' + chr(10) + json.dumps(creative_brief, ensure_ascii=False, indent=2) + chr(10) + chr(10) + 'CURRENT CREATIVE CONCEPT:' + chr(10) + current_concept + chr(10) + chr(10) + 'CURRENT EVALUATION:' + chr(10) + json.dumps(evaluation, ensure_ascii=False, indent=2) + chr(10) + chr(10) + 'PRIMARY WEAK CRITERIA:' + chr(10) + json.dumps(weak, ensure_ascii=False)
    response = client.responses.create(model=model, input=prompt, reasoning={'effort': 'high'})
    revised = response.output_text.strip()
    if not revised:
        raise ValueError('Refinement returned an empty concept.')
    return revised


def present_result(result: dict[str, Any]) -> None:
    print(chr(10) + '=== Final Creative Concept ===')
    print(result['creative_concept'])
    print(chr(10) + '=== Standardized Evaluation ===')
    print(json.dumps(result['evaluation'], ensure_ascii=False, indent=2))
    print(chr(10) + '=== Refinements Performed ===')
    print(result['refinement_count'])
    status = 'true' if result['quality_threshold_met'] else 'false (two-refinement limit reached without satisfying threshold)'
    print(chr(10) + '=== Quality Threshold (overall score >= 8.0) ===' + chr(10) + status)


def main() -> dict[str, Any]:
    print('CreativeDirectorAssistant')
    print('Provide one complete creative brief containing brand, product, target audience, objective, key product benefit, channels, budget, and constraints.')
    answer = input(chr(10) + 'Creative brief: ')
    brief = extract_brief(answer)
    concept = generate_concept(brief)
    evaluation = evaluate_creative_concept(brief, concept)
    refinement_count = 0
    while evaluation['overall_score'] < QUALITY_THRESHOLD and refinement_count < MAX_REFINEMENTS:
        concept = refine_creative_concept(brief, concept, evaluation)
        refinement_count += 1
        evaluation = evaluate_creative_concept(brief, concept)
    result = {
        'creative_concept': concept,
        'evaluation': evaluation,
        'refinement_count': refinement_count,
        'quality_threshold_met': evaluation['overall_score'] >= QUALITY_THRESHOLD,
    }
    present_result(result)
    return result


if __name__ == '__main__':
    main()
