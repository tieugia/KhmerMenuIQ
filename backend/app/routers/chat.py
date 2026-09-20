from fastapi import APIRouter

from ..currency import from_usd
from ..data_store import load_restaurants
from ..guardrails import OUT_OF_SCOPE_REPLY
from ..llm import answer_general_question, compose_reply, extract_intent
from ..models import ChatRequest, ChatResponse, Combo
from ..recommend import build_combos, keyword_search

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _add_currency_display(combos: list[Combo], intent: dict) -> None:
    """Attach the diner's original-currency figures to each combo, derived from the already
    USD-clamped budget_usd/total_usd (never independently re-parsed) — a no-op when the diner
    stated (or defaulted to) USD."""
    currency = intent.get("budget_currency")
    if not currency or currency == "USD":
        return
    for combo in combos:
        combo.budget_currency = currency
        combo.total_display_amount = round(from_usd(combo.total_usd, currency), 2)
        if combo.budget_usd is not None:
            combo.budget_display_amount = round(from_usd(combo.budget_usd, currency), 2)


def _resolve_selected_item(restaurants, selected_item) -> dict | None:
    """Resolve client selection against menu data so names and prices cannot be fabricated."""
    if selected_item is None:
        return None
    for restaurant in restaurants:
        if restaurant.id != selected_item.restaurant_id:
            continue
        for item in restaurant.items:
            same_en = selected_item.item_name_en and item.name_en == selected_item.item_name_en
            same_kh = selected_item.item_name_kh and item.name_kh == selected_item.item_name_kh
            if same_en or same_kh:
                return {
                    "restaurant_id": restaurant.id,
                    "restaurant": restaurant.restaurant_name_en or restaurant.id,
                    "restaurant_kh": restaurant.restaurant_name_kh,
                    "item_en": item.name_en,
                    "item_kh": item.name_kh,
                    "category": item.category,
                    "price_usd": item.min_price_usd,
                }
    return None


def _selected_item_context(restaurants, selected_hit: dict, limit: int = 12) -> list[dict]:
    """Build deterministic comparison context around an exact selected menu item.

    Same-category items are the strongest comparison. Items from the same restaurant are
    preferred, and a few other dishes there are included when the category has too few peers.
    Python computes every price relationship so the LLM only has to explain it.
    """
    selected_price = selected_hit.get("price_usd")
    candidates: list[tuple] = []

    for restaurant in restaurants:
        for item in restaurant.items:
            is_selected = (
                restaurant.id == selected_hit["restaurant_id"]
                and item.name_en == selected_hit["item_en"]
                and item.name_kh == selected_hit["item_kh"]
            )
            if is_selected or item.min_price_usd is None:
                continue

            same_restaurant = restaurant.id == selected_hit["restaurant_id"]
            same_category = item.category == selected_hit["category"]
            if not same_restaurant and not same_category:
                continue

            if same_restaurant and same_category:
                priority = 0
                comparison_scope = "same category at the same restaurant"
            elif same_category:
                priority = 1
                comparison_scope = "same category at another restaurant"
            else:
                priority = 2
                comparison_scope = "another item at the same restaurant"

            if selected_price is None:
                price_relation = "unknown"
                difference = None
                distance = float("inf")
            else:
                signed_difference = round(item.min_price_usd - selected_price, 2)
                distance = abs(signed_difference)
                difference = distance
                price_relation = (
                    "same price"
                    if signed_difference == 0
                    else "more expensive"
                    if signed_difference > 0
                    else "cheaper"
                )

            candidates.append(
                (
                    priority,
                    distance,
                    item.min_price_usd,
                    {
                        "restaurant_id": restaurant.id,
                        "restaurant": restaurant.restaurant_name_en or restaurant.id,
                        "restaurant_kh": restaurant.restaurant_name_kh,
                        "item_en": item.name_en,
                        "item_kh": item.name_kh,
                        "category": item.category,
                        "price_usd": item.min_price_usd,
                        "comparison_scope": comparison_scope,
                        "price_vs_selected": price_relation,
                        "price_difference_usd": difference,
                    },
                )
            )

    candidates.sort(key=lambda candidate: candidate[:3])
    selected = {
        **selected_hit,
        "comparison_scope": "selected item",
        "price_vs_selected": "selected item",
        "price_difference_usd": 0.0 if selected_price is not None else None,
    }
    return [selected, *(candidate[3] for candidate in candidates[: limit - 1])]


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    restaurants = load_restaurants()
    intent = extract_intent(req.message)
    if intent.get("budget_invalid"):
        return ChatResponse(
            reply=(
                "Ngân sách không hợp lệ: budget không được là số âm. "
                "Vui lòng nhập lại ngân sách, ví dụ 10 USD hoặc 40.000 KHR. "
                "Invalid budget: a budget cannot be negative. Please enter your budget again."
            ),
            combos=[],
            intent=intent,
        )
    if intent.get("budget_unparseable"):
        return ChatResponse(
            reply=(
                "Ngân sách không hợp lệ: mình chưa hiểu số tiền bạn nhập. "
                "Vui lòng nhập lại ngân sách bằng số, ví dụ 10 USD hoặc 40.000 KHR. "
                "Invalid budget amount. Please enter your budget again as a number."
            ),
            combos=[],
            intent=intent,
        )
    selected_hit = _resolve_selected_item(restaurants, req.selected_item)

    # "order" intent always has a non-empty wants list by this point (extract_intent fills in a
    # balanced default when the diner didn't name specific dishes), so this also covers vague,
    # non-English recommendation requests like "tôi đi 4 người, nên ăn món gì?".
    if intent["intent_type"] == "order" and intent["wants"] and not selected_hit:
        combos = build_combos(restaurants, intent["budget_usd"], intent["wants"], top_n=3)
        _add_currency_display(combos, intent)
        reply = compose_reply(req.message, intent, combos)
        return ChatResponse(reply=reply, combos=combos, intent=intent)

    if intent["intent_type"] == "off_topic" and not selected_hit:
        # Classified as unrelated to Cambodian food/menus regardless of language — skip the LLM
        # entirely rather than relying on (English/Khmer-only) keyword matching to detect scope.
        return ChatResponse(reply=OUT_OF_SCOPE_REPLY, combos=[], intent=intent)

    hits = (
        _selected_item_context(restaurants, selected_hit)
        if selected_hit
        else keyword_search(restaurants, req.message)
    )
    if not hits:
        # A "lookup" question, but nothing in the menu data matches it.
        return ChatResponse(reply=OUT_OF_SCOPE_REPLY, combos=[], intent=intent)

    reply = answer_general_question(req.message, hits, selected_item=selected_hit)
    return ChatResponse(reply=reply, combos=[], suggested_items=hits[:4] if selected_hit else [], intent=intent)
