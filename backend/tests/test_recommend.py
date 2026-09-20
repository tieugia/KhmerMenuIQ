from app.models import MenuItem, Price, Restaurant
from app.recommend import build_combos, item_matches_role, keyword_search


def _item(name_en, category, price_usd, *, is_veg=False, is_beer=False, name_kh=""):
    return MenuItem(
        name_en=name_en,
        name_kh=name_kh or name_en,
        category=category,
        is_vegetable_forward=is_veg,
        is_alcoholic_beverage=is_beer,
        prices=[Price(label=None, amount=price_usd, currency="USD", usd=price_usd)],
        min_price_usd=price_usd,
    )


def _restaurant(id_, name_en, items, name_kh=None):
    return Restaurant(
        id=id_,
        source_image=f"{id_}.png",
        restaurant_name_en=name_en,
        restaurant_name_kh=name_kh,
        phone=None,
        items=items,
    )


CHEAP = _restaurant(
    "cheap-spot",
    "Cheap Spot",
    [
        _item("Grilled Chicken", "chicken", 1.0),
        _item("Fried Morning Glory", "vegetable", 1.0, is_veg=True),
        _item("Angkor Beer", "beer", 1.0, is_beer=True),
    ],
)

PRICEY = _restaurant(
    "pricey-spot",
    "Pricey Spot",
    [
        _item("Roast Chicken", "chicken", 5.0),
        _item("Stir-fried Kale", "vegetable", 4.0, is_veg=True),
        _item("Imported Beer", "beer", 6.0, is_beer=True),
    ],
)

NO_BEER = _restaurant(
    "no-beer-spot",
    "No Beer Spot",
    [
        _item("Chicken Wings", "chicken", 1.5),
        _item("Papaya Salad", "salad", 1.5, is_veg=True),
    ],
)

WANTS = [
    {"role": "chicken", "quantity": 1},
    {"role": "vegetable", "quantity": 1},
    {"role": "beer", "quantity": 2},
]


def test_item_matches_role_handles_vegetable_flag_and_aliases():
    veg = _item("Stir-fried Cabbage", "other", 2.0, is_veg=True)
    assert item_matches_role(veg, "vegetable")
    assert item_matches_role(veg, "veggies")  # alias


def test_item_matches_role_handles_beer_flag():
    beer = _item("Craft Lager", "other", 3.0, is_beer=True)
    assert item_matches_role(beer, "beer")
    assert item_matches_role(beer, "beers")  # alias


def test_build_combos_with_explicit_budget_flags_within_and_over():
    combos = build_combos([CHEAP, PRICEY], budget_usd=5.0, wants=WANTS)
    by_id = {c.restaurant_id: c for c in combos}
    assert by_id["cheap-spot"].within_budget is True
    assert by_id["pricey-spot"].within_budget is False


def test_build_combos_marks_missing_role_and_never_within_budget_via_that_field():
    combos = build_combos([NO_BEER], budget_usd=100.0, wants=WANTS)
    combo = combos[0]
    assert combo.missing_roles == ["beer"]
    assert combo.within_budget is False  # incomplete combo never counts as satisfying the request


def test_build_combos_ranks_cheapest_full_match_first():
    combos = build_combos([PRICEY, CHEAP], budget_usd=100.0, wants=WANTS)
    assert combos[0].restaurant_id == "cheap-spot"


def test_build_combos_with_no_budget_stated_treats_every_full_match_as_within_budget():
    combos = build_combos([CHEAP, PRICEY], budget_usd=None, wants=WANTS)
    for c in combos:
        if not c.missing_roles:
            assert c.budget_usd is None
            assert c.within_budget is True
    # still ranked cheapest-first so the top suggestion is the most affordable option
    assert combos[0].restaurant_id == "cheap-spot"


def test_keyword_search_ranks_more_specific_matches_first():
    hits = keyword_search([CHEAP, PRICEY], "grilled chicken")
    assert hits[0]["item_en"] == "Grilled Chicken"


def test_keyword_search_returns_empty_for_unrelated_query():
    assert keyword_search([CHEAP, PRICEY], "pizza and sushi") == []
