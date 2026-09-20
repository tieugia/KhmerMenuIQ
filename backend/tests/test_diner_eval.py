"""Offline dataset/HTTP checks and regression checks for the eval grader itself."""
from copy import deepcopy
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.guardrails import OUT_OF_SCOPE_REPLY
from evals.run import grade, load_cases, run_case


def test_dataset_has_thirty_distinct_scenarios():
    cases = load_cases()
    assert len(cases) == 30
    assert len({case['id'] for case in cases}) == 30
    assert len({case['message'] for case in cases}) == 30
    assert len({case['topic'] for case in cases}) == 30
    assert all(case['expected'] and case['review'] for case in cases)


@pytest.mark.parametrize('payload', [{}, {'message': None}, {'message': 123},
                                     {'message': []}, {'message': {}}, {'message': ''},
                                     {'message': '   '}, {'message': 'a' * 501}])
def test_bad_request_does_not_call_model(payload):
    with patch('app.llm._chat_completion') as completion:
        response = TestClient(app).post('/api/chat', json=payload)
    assert response.status_code == 422
    completion.assert_not_called()


def test_grader_rejects_fabricated_budget_and_lookup_combo():
    case = {'expected': {'intent_type': 'lookup', 'budget_usd': None, 'combos': 'empty'}}
    body = {'intent': {'intent_type': 'lookup', 'budget_usd': None}, 'reply': 'Menu answer', 'combos': []}
    assert grade(case, 200, body) == []
    altered = deepcopy(body)
    altered['intent']['budget_usd'] = 10
    assert any('budget_usd' in error for error in grade(case, 200, altered))
    altered['combos'] = [{'restaurant_id': 'nonexistent'}]
    errors = grade(case, 200, altered)
    assert any('incorrectly returned' in error for error in errors)
    assert 'Invented restaurant' in errors


def test_provider_failure_cannot_pass_as_safe_fallback():
    case = {'id': 'failure', 'topic': 'transport', 'message': 'xyz',
            'expected': {'intent_type': 'lookup', 'combos': 'empty'}, 'review': 'n/a'}
    with patch('app.llm._chat_completion', side_effect=RuntimeError('secret must not be logged')):
        result = run_case(TestClient(app), case)
    assert not result['passed']
    assert 'LLM call failed: RuntimeError' in result['errors']
    assert 'secret' not in str(result)


def test_known_menu_lookup_cannot_pass_with_refusal():
    case = {'expected': {'intent_type': 'lookup', 'combos': 'empty', 'refusal': False}}
    body = {'intent': {'intent_type': 'lookup'}, 'reply': OUT_OF_SCOPE_REPLY, 'combos': []}
    assert 'Known menu lookup was refused' in grade(case, 200, body)
