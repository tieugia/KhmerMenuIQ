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
                    "restaurant": restaurant.restaurant_name_en or restaurant.id,
                    "restaurant_kh": restaurant.restaurant_name_kh,
                    "item_en": item.name_en,
                    "item_kh": item.name_kh,
                    "category": item.category,
                    "price_usd": item.min_price_usd,
                }
    return None


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    restaurants = load_restaurants()
    intent = extract_intent(req.message)
    selected_hit = _resolve_selected_item(restaurants, req.selected_item)

    # "order" intent always has a non-empty wants list by this point (extract_intent fills in a
    # balanced default when the diner didn't name specific dishes), so this also covers vague,
    # non-English recommendation requests like "tôi đi 4 người, nên ăn món gì?".
    if intent["wants"]:
        combos = build_combos(restaurants, intent["budget_usd"], intent["wants"], top_n=3)
        _add_currency_display(combos, intent)
        reply = compose_reply(req.message, intent, combos)
        return ChatResponse(reply=reply, combos=combos, intent=intent)

    if intent["intent_type"] == "off_topic" and not selected_hit:
        # Classified as unrelated to Cambodian food/menus regardless of language — skip the LLM
        # entirely rather than relying on (English/Khmer-only) keyword matching to detect scope.
        return ChatResponse(reply=OUT_OF_SCOPE_REPLY, combos=[], intent=intent)

    hits = [selected_hit] if selected_hit else keyword_search(restaurants, req.message)
    if not hits:
        # A "lookup" question, but nothing in the menu data matches it.
        return ChatResponse(reply=OUT_OF_SCOPE_REPLY, combos=[], intent=intent)

    reply = answer_general_question(req.message, hits, selected_item=selected_hit)
    return ChatResponse(reply=reply, combos=[], intent=intent)
