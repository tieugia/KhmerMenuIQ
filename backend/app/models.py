from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .guardrails import MESSAGE_MAX_LENGTH, MESSAGE_MIN_LENGTH, validate_message

Category = Literal[
    "chicken", "beef", "pork", "fish", "seafood", "egg", "tofu",
    "vegetable", "soup", "rice", "noodle", "salad", "dessert",
    "beer", "soft_drink", "other",
]


class Price(BaseModel):
    label: Optional[str] = None
    amount: float
    currency: str
    usd: float


class MenuItem(BaseModel):
    name_kh: str = ""
    name_en: str = ""
    category: Category
    is_vegetable_forward: bool = False
    is_alcoholic_beverage: bool = False
    prices: list[Price] = []
    min_price_usd: Optional[float] = None

    @field_validator("name_kh", "name_en", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        return v or ""


class Restaurant(BaseModel):
    id: str
    source_image: str
    restaurant_name_kh: Optional[str] = None
    restaurant_name_en: Optional[str] = None
    phone: Optional[str] = None
    items: list[MenuItem] = []


class ChatRequest(BaseModel):
    message: str = Field(min_length=MESSAGE_MIN_LENGTH, max_length=MESSAGE_MAX_LENGTH)
    history: list[dict] = []

    @field_validator("message")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        return validate_message(v)


class ComboLine(BaseModel):
    role: str  # "chicken" | "vegetable" | "beer" | ...
    item_name_en: str
    item_name_kh: str
    quantity: int
    unit_price_usd: float
    line_total_usd: float


class Combo(BaseModel):
    restaurant_id: str
    restaurant_name_en: str
    restaurant_name_kh: Optional[str] = None
    phone: Optional[str] = None
    lines: list[ComboLine]
    total_usd: float
    budget_usd: Optional[float] = None
    within_budget: bool
    missing_roles: list[str] = []
    # Diner's original currency, if their budget wasn't stated in USD (e.g. "VND") — derived from
    # budget_usd/total_usd via a fixed approximate rate, not independently trusted.
    budget_currency: Optional[str] = None
    budget_display_amount: Optional[float] = None
    total_display_amount: Optional[float] = None


class ChatResponse(BaseModel):
    reply: str
    combos: list[Combo] = []
    intent: dict
