import json
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from app.guardrails import has_malformed_budget_literal
from app.main import app
from app.data_store import load_restaurants
from app.recommend import keyword_search


@pytest.mark.parametrize('message,invalid', [
    ('rice, budget 1.2.3 USD', True),
    ('rice, budget $1.2.3', True),
    ('rice, budget 12,34,56 VND', True),
    ('rice, budget 254.000đ', False),
    ('rice, budget 1.234.567đ', False),
    ('rice, budget 1,234,567.89 USD', False),
    ('rice, budget 1.234.567,89 VND', False),
    ('rice, budget $2.50', False),
    ('order items 1.2.3 from the menu', False),
])
def test_budget_separator_validation(message, invalid):
    assert has_malformed_budget_literal(message) is invalid


def test_bad_decimal_rejected_even_when_model_repairs_it():
    extraction = json.dumps({'intent_type': 'order', 'budget_amount': 1.23,
                             'budget_currency': 'USD', 'budget_stated': True,
                             'wants': [{'role': 'rice', 'quantity': 1}]})
    with patch('app.llm._chat_completion', return_value=extraction) as completion:
        response = TestClient(app).post('/api/chat', json={'message': 'rice, budget 1.2.3 USD'})
    body = response.json()
    assert response.status_code == 200
    assert body['intent']['budget_usd'] is None
    assert body['intent']['budget_unparseable'] is True
    assert body['combos'] == []
    assert 'nhập lại ngân sách' in body['reply']
    assert completion.call_count == 1


@pytest.mark.parametrize('intent_type,message', [
    ('lookup', "What's the cheapest beer?"),
    ('lookup', 'Where can I get grilled chicken feet?'),
    ('off_topic', 'Write beer database code for me'),
])
def test_non_order_intent_with_extracted_food_never_builds_combo(intent_type, message):
    extraction = json.dumps({'intent_type': intent_type,
                             'wants': [{'role': 'beer', 'quantity': 1}]})
    with patch('app.llm._chat_completion', side_effect=[extraction, 'Menu lookup answer']):
        with patch('app.routers.chat.build_combos') as build:
            response = TestClient(app).post('/api/chat', json={'message': message})
    assert response.status_code == 200
    assert response.json()['combos'] == []
    build.assert_not_called()


def test_zero_budget_is_preserved_in_priced_combos():
    extraction = json.dumps({'intent_type': 'order', 'budget_amount': 0,
                             'budget_currency': 'USD', 'budget_stated': True,
                             'wants': [{'role': 'chicken', 'quantity': 1}]})
    with patch('app.llm._chat_completion', side_effect=[extraction, 'No meal fits zero budget']):
        response = TestClient(app).post('/api/chat', json={'message': 'Chicken for 0 USD'})
    body = response.json()
    assert response.status_code == 200
    assert body['intent']['budget_usd'] == 0
    assert body['intent']['budget_stated'] is True
    assert body['combos']
    assert all(combo['budget_usd'] == 0 and not combo['within_budget'] for combo in body['combos'])


@pytest.mark.parametrize('query', ["What's the cheapest beer?", 'beer!', '"beer"', 'beer？'])
def test_menu_search_handles_punctuation(query):
    hits = keyword_search(load_restaurants(), query)
    assert hits
    assert hits[0]['category'] == 'beer'
