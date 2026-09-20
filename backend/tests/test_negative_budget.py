import json
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.mark.parametrize('currency', ['USD', 'KHR', 'VND', 'PHP', 'SGD'])
@pytest.mark.parametrize('amount', [-10, -0.01])
def test_negative_budget_asks_again_without_building_order(currency, amount):
    extraction = json.dumps({'intent_type': 'order', 'budget_amount': amount,
                             'budget_currency': currency, 'budget_stated': True,
                             'wants': [{'role': 'chicken', 'quantity': 1}]})
    with patch('app.llm._chat_completion', return_value=extraction) as completion:
        with patch('app.routers.chat.build_combos') as build:
            response = TestClient(app).post('/api/chat', json={'message': f'Chicken, budget {amount} {currency}'})
    assert response.status_code == 200
    body = response.json()
    assert body['intent']['budget_invalid'] is True
    assert body['intent']['budget_usd'] is None
    assert body['intent']['budget_stated'] is False
    assert body['combos'] == []
    assert 'không hợp lệ' in body['reply']
    assert 'nhập lại ngân sách' in body['reply']
    assert completion.call_count == 1
    build.assert_not_called()
