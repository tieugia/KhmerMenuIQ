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
        "budget_amount": None,
        "budget_currency": None,
        "budget_display_amount": None,
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
def test_selected_menu_item_supplies_verified_context_for_pronoun_question(
    mock_intent, mock_search, mock_answer
):
    restaurants = client.get("/api/restaurants").json()
    category_counts = {}
    for candidate_restaurant in restaurants:
        for candidate_item in candidate_restaurant["items"]:
            if candidate_item["min_price_usd"] is None:
                continue
            category = candidate_item["category"]
            category_counts[category] = category_counts.get(category, 0) + 1
    restaurant = next(
        r
        for r in restaurants
        if any(
            item["min_price_usd"] is not None and category_counts[item["category"]] >= 3
            for item in r["items"]
        )
    )
    item = next(
        item
        for item in restaurant["items"]
        if item["min_price_usd"] is not None and category_counts[item["category"]] >= 3
    )
    mock_intent.return_value = {
        # A short pronoun-only question can be misclassified without the UI selection context.
        # The verified selected item must still keep it in menu-question scope.
        "intent_type": "off_topic",
        "budget_usd": None,
        "budget_amount": None,
        "budget_currency": None,
        "budget_display_amount": None,
        "budget_stated": False,
        "party_size": 1,
        "wants": [],
        "wants_defaulted": False,
        "notes": "",
    }
    mock_answer.return_value = "Answer about the selected dish."

    selected_item = {
        "restaurant_id": restaurant["id"],
        "restaurant_name_en": "client-supplied name must not be trusted",
        "item_name_en": item["name_en"],
        "item_name_kh": item["name_kh"],
        "category": item["category"],
        "price_usd": 999999,
    }
    resp = client.post(
        "/api/chat",
        json={"message": "Is this item spicy?", "selected_item": selected_item},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Answer about the selected dish."
    assert len(body["suggested_items"]) == 4
    assert body["suggested_items"][0]["item_en"] == item["name_en"]
    assert body["suggested_items"][0]["price_vs_selected"] == "selected item"
    assert all(card["restaurant_id"] for card in body["suggested_items"])
    mock_search.assert_not_called()
    _, call_hits = mock_answer.call_args.args
    verified = mock_answer.call_args.kwargs["selected_item"]
    assert len(call_hits) >= 3
    assert call_hits[0]["comparison_scope"] == "selected item"
    assert call_hits[0]["item_en"] == verified["item_en"]
    assert all(
        hit["price_vs_selected"] in {"cheaper", "same price", "more expensive"}
        for hit in call_hits[1:]
    )
    assert any(hit["category"] == item["category"] for hit in call_hits[1:])
    assert verified["restaurant"] == restaurant["restaurant_name_en"]
    assert verified["item_en"] == item["name_en"]
    assert verified["price_usd"] == item["min_price_usd"]


@patch("app.routers.chat.answer_general_question")
@patch("app.routers.chat.keyword_search")
@patch("app.routers.chat.extract_intent")
def test_off_topic_classification_skips_keyword_search_entirely(
    mock_intent, mock_search, mock_answer
):
    mock_intent.return_value = {
        "intent_type": "off_topic",
        "budget_usd": None,
        "budget_amount": None,
        "budget_currency": None,
        "budget_display_amount": None,
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
        "budget_amount": 254000.0,
        "budget_currency": "VND",
        "budget_display_amount": 254000.0,
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
    assert body["intent"]["budget_currency"] == "VND"
    assert body["combos"]
    assert body["combos"][0]["budget_currency"] == "VND"
    assert body["combos"][0]["budget_display_amount"] == 254000.0
    assert body["combos"][0]["total_display_amount"] == round(
        body["combos"][0]["total_usd"] * 25400, 2
    )


@patch("app.llm._chat_completion")
def test_vague_non_english_group_recommendation_is_not_refused(mock_completion):
    # Regression test for a real bug report: "tôi đi 4 người, nên ăn món gì?" (Vietnamese for
    # "I'm going with 4 people, what should I eat?") was wrongly answered with OUT_OF_SCOPE_REPLY,
    # because it named no specific dish so keyword_search (English/Khmer only) found nothing.
    # Only the two outbound LLM calls are mocked — extract_intent's classification/defaulting and
    # build_combos run for real against the actual menu dataset.
    mock_completion.side_effect = [
        (
            '{"intent_type": "order", "budget_amount": null, "budget_currency": null, "budget_stated": false, '
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
