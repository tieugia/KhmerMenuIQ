from .models import Combo, ComboLine, MenuItem, Restaurant

ROLE_ALIASES = {
    "veggie": "vegetable",
    "veggies": "vegetable",
    "vegetables": "vegetable",
    "greens": "vegetable",
    "beers": "beer",
    "beef_dish": "beef",
    "drink": "soft_drink",
    "soda": "soft_drink",
}


def normalize_role(role: str) -> str:
    role = role.lower().strip()
    return ROLE_ALIASES.get(role, role)


def item_matches_role(item: MenuItem, role: str) -> bool:
    role = normalize_role(role)
    if role == "vegetable":
        return item.category == "vegetable" or item.is_vegetable_forward
    if role == "beer":
        return item.category == "beer" or item.is_alcoholic_beverage
    return item.category == role


def build_combos(
    restaurants: list[Restaurant],
    budget_usd: float | None,
    wants: list[dict],
    top_n: int = 5,
) -> list[Combo]:
    """budget_usd=None means the diner never stated one: every complete combo counts as
    "within budget" (there's nothing to violate), and results are simply ranked cheapest-first
    so the top combo is the most affordable way to cover everything requested."""
    candidates: list[Combo] = []

    for r in restaurants:
        lines: list[ComboLine] = []
        missing: list[str] = []
        total = 0.0

        for want in wants:
            role = normalize_role(want.get("role", ""))
            qty = max(1, int(want.get("quantity", 1) or 1))
            matches = [it for it in r.items if item_matches_role(it, role) and it.min_price_usd is not None]
            if not matches:
                missing.append(role)
                continue
            cheapest = min(matches, key=lambda it: it.min_price_usd)
            unit = cheapest.min_price_usd
            line_total = round(unit * qty, 2)
            lines.append(
                ComboLine(
                    role=role,
                    item_name_en=cheapest.name_en,
                    item_name_kh=cheapest.name_kh,
                    quantity=qty,
                    unit_price_usd=unit,
                    line_total_usd=line_total,
                )
            )
            total += line_total

        total = round(total, 2)
        combo = Combo(
            restaurant_id=r.id,
            restaurant_name_en=r.restaurant_name_en or r.id,
            restaurant_name_kh=r.restaurant_name_kh,
            phone=r.phone,
            lines=lines,
            total_usd=total,
            budget_usd=budget_usd,
            within_budget=(len(missing) == 0 and (budget_usd is None or total <= budget_usd)),
            missing_roles=missing,
        )
        candidates.append(combo)

    def sort_key(c: Combo):
        full = len(c.missing_roles) == 0
        tier = 0 if (full and c.within_budget) else (1 if full else 2)
        return (tier, len(c.missing_roles), c.total_usd)

    candidates.sort(key=sort_key)
    return candidates[:top_n]


STOPWORDS = {
    "where", "can", "get", "should", "what", "the", "and", "from", "for",
    "with", "have", "want", "some", "any", "is", "are", "of", "to", "me",
    "you", "do", "does", "there", "which", "how", "much",
}


def keyword_search(restaurants: list[Restaurant], query: str, limit: int = 25) -> list[dict]:
    terms = [t for t in query.lower().split() if len(t) > 1 and t not in STOPWORDS]
    if not terms:
        return []

    scored = []
    for r in restaurants:
        for it in r.items:
            haystack = f"{it.name_en} {it.name_kh} {it.category}".lower()
            score = sum(1 for t in terms if t in haystack)
            if score > 0:
                scored.append(
                    (
                        score,
                        {
                            "restaurant": r.restaurant_name_en or r.id,
                            "restaurant_kh": r.restaurant_name_kh,
                            "item_en": it.name_en,
                            "item_kh": it.name_kh,
                            "category": it.category,
                            "price_usd": it.min_price_usd,
                        },
                    )
                )

    # Highest term-overlap first; among ties, cheapest (and priced) items first.
    scored.sort(key=lambda pair: (-pair[0], pair[1]["price_usd"] if pair[1]["price_usd"] is not None else 1e9))
    return [hit for _, hit in scored[:limit]]
