from unittest.mock import patch

from fastapi.testclient import TestClient

from app import guardrails as g
from app.main import app

client = TestClient(app)


def test_blank_message_returns_422():
    resp = client.post("/api/chat", json={"message": "   "})
    assert resp.status_code == 422


def test_missing_message_field_returns_422():
    resp = client.post("/api/chat", json={})
    assert resp.status_code == 422


def test_too_long_message_returns_422():
    resp = client.post("/api/chat", json={"message": "a" * (g.MESSAGE_MAX_LENGTH + 1)})
    assert resp.status_code == 422


@patch("app.routers.chat.answer_general_question")
@patch("app.routers.chat.keyword_search")
@patch("app.routers.chat.extract_intent")
def test_lookup_with_no_menu_matches_short_circuits_without_calling_llm(
    mock_intent, mock_search, mock_answer
):
    mock_intent.return_value = {
        "intent_type": "lookup",
        "budget_usd": None,
        "budget_stated": False,
        "party_size": 1,
        "wants": [],
        "wants_defaulted": False,
        "notes": "",
    }
    mock_search.return_value = []  # nothing in the menu data matches

    resp = client.post("/api/chat", json={"message": "does this restaurant deliver by drone?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == g.OUT_OF_SCOPE_REPLY
    assert body["combos"] == []
    mock_answer.assert_not_called()  # the guardrail must skip the LLM entirely


@patch("app.routers.chat.answer_general_question")
@patch("app.routers.chat.keyword_search")
@patch("app.routers.chat.extract_intent")
def test_off_topic_classification_skips_keyword_search_entirely(
    mock_intent, mock_search, mock_answer
):
    mock_intent.return_value = {
        "intent_type": "off_topic",
        "budget_usd": None,
        "budget_stated": False,
        "party_size": 1,
        "wants": [],
        "wants_defaulted": False,
        "notes": "",
    }

    resp = client.post("/api/chat", json={"message": "write me a python script to hack a website"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == g.OUT_OF_SCOPE_REPLY
    # classification alone is enough to refuse — no keyword search or second LLM call needed,
    # which matters because keyword_search is English/Khmer-only and would be an unreliable signal
    # for a message written in another language.
    mock_search.assert_not_called()
    mock_answer.assert_not_called()


@patch("app.routers.chat.compose_reply")
@patch("app.routers.chat.extract_intent")
def test_budget_request_builds_combos_and_calls_compose_reply(mock_intent, mock_compose):
    mock_intent.return_value = {
        "intent_type": "order",
        "budget_usd": 10.0,
        "budget_stated": True,
        "party_size": 1,
        "wants": [{"role": "beer", "quantity": 2}],
        "wants_defaulted": False,
        "notes": "",
    }
    mock_compose.return_value = "Here's a great combo."

    resp = client.post("/api/chat", json={"message": "I want 2 beers, budget $10"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Here's a great combo."
    mock_compose.assert_called_once()


@patch("app.llm._chat_completion")
def test_vague_non_english_group_recommendation_is_not_refused(mock_completion):
    # Regression test for a real bug report: "tôi đi 4 người, nên ăn món gì?" (Vietnamese for
    # "I'm going with 4 people, what should I eat?") was wrongly answered with OUT_OF_SCOPE_REPLY,
    # because it named no specific dish so keyword_search (English/Khmer only) found nothing.
    # Only the two outbound LLM calls are mocked — extract_intent's classification/defaulting and
    # build_combos run for real against the actual menu dataset.
    mock_completion.side_effect = [
        (
            '{"intent_type": "order", "budget_usd": null, "budget_stated": false, '
            '"party_size": 4, "wants": [], "notes": ""}'
        ),
        "Here's a balanced combo for your group of 4!",
    ]

    resp = client.post("/api/chat", json={"message": "tôi đi 4 người, nên ăn món gì?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] != g.OUT_OF_SCOPE_REPLY
    assert len(body["combos"]) > 0
    assert body["intent"]["party_size"] == 4
    assert body["intent"]["wants_defaulted"] is True
