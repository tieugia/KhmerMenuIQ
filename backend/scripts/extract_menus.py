"""
One-time data pipeline: reads photographed Khmer restaurant menus from `data 1/`,
sends each to a vision-capable LLM via OpenRouter, and writes structured bilingual
menu JSON to backend/data/menus.json (with per-image cache under backend/data/raw/).

Run:
    backend/.venv/Scripts/python.exe backend/scripts/extract_menus.py
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
DATA_DIR = ROOT / "data 1"
RAW_CACHE_DIR = BACKEND_DIR / "data" / "raw"
OUTPUT_FILE = BACKEND_DIR / "data" / "menus.json"

load_dotenv(BACKEND_DIR / ".env")

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
VISION_MODEL = os.environ.get("VISION_MODEL", "google/gemini-2.5-flash")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MAX_DIM = 1900  # downscale long edge to keep payload size + cost reasonable
JPEG_QUALITY = 85

SYSTEM_PROMPT = """You are an expert Khmer-English menu transcriber for Cambodian restaurants.
You will be shown a photo of a physical restaurant menu board or sheet, written mostly in Khmer
script, sometimes with English translations and phone numbers already printed on it.

Transcribe it into STRICT JSON (no markdown fences, no commentary) matching exactly this shape:

{
  "restaurant_name_kh": string or null,   // Khmer name of the restaurant/shop as printed, null if none visible
  "restaurant_name_en": string or null,   // English name as printed, OR your best transliteration/translation if only Khmer is shown
  "phone": string or null,                // phone number(s) as printed, joined with " / " if multiple
  "items": [
    {
      "name_kh": string,                  // dish/drink name in Khmer exactly as printed
      "name_en": string,                  // English translation (use printed English if present, else translate yourself)
      "category": one of ["chicken","beef","pork","fish","seafood","egg","tofu","vegetable","soup","rice","noodle","salad","dessert","beer","soft_drink","other"],
      "is_vegetable_forward": boolean,    // true if the dish is principally a vegetable dish (not just a garnish)
      "is_alcoholic_beverage": boolean,   // true for beer or other alcohol
      "prices": [
        {"label": string or null, "amount": number, "currency": "USD" or "KHR"}
        // one entry per size/variant shown (e.g. small/large, S/M/L/XL). label null if only one price.
        // Riel prices are usually printed like "10000ន" or "ន.10000" (ន = Riel symbol); USD prices use "$".
      ]
    }
  ]
}

Rules:
- Include EVERY distinct menu item/dish/drink visible in the photo, even if partially cut off, as long as a name and at least one price are legible.
- If a price is genuinely illegible, omit that price entry but still include the item with an empty prices array.
- category "chicken" = the primary protein is chicken (មុន ាំង). Use "beef"/គ្រូ, "pork"/ចោក, "fish"/ត្រtrី, "seafood" (shrimp/crab/squid), "egg", "tofu" as appropriate. If mixed or unclear meat, use "other".
- category "beer" for any beer brand (Angkor, Cambodia, Anchor, Tiger, Heineken, ABC, etc). category "soft_drink" for sodas/juices/water.
- Respond with ONLY the JSON object, nothing else.
"""


def downscale_image(path: Path) -> bytes:
    with Image.open(path) as img:
        img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, MAX_DIM / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        return buf.getvalue()


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def call_vision_model(image_bytes: bytes, client: httpx.Client) -> dict:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:image/jpeg;base64,{b64}"
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe this Cambodian restaurant menu photo into the JSON schema."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0,
    }
    resp = client.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return extract_json(content)


def slugify(name: str, fallback: str) -> str:
    base = name or fallback
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()
    return base or fallback


def khr_to_usd(amount: float, khr_per_usd: float) -> float:
    return round(amount / khr_per_usd, 2)


def normalize_item(item: dict, khr_per_usd: float) -> dict:
    prices = item.get("prices") or []
    normalized_prices = []
    usd_candidates = []
    for p in prices:
        amount = p.get("amount")
        currency = (p.get("currency") or "USD").upper()
        if amount is None:
            continue
        if currency == "KHR":
            usd = khr_to_usd(float(amount), khr_per_usd)
        else:
            usd = round(float(amount), 2)
        normalized_prices.append(
            {
                "label": p.get("label"),
                "amount": amount,
                "currency": currency,
                "usd": usd,
            }
        )
        usd_candidates.append(usd)
    item["prices"] = normalized_prices
    item["min_price_usd"] = min(usd_candidates) if usd_candidates else None
    item.setdefault("category", "other")
    item.setdefault("is_vegetable_forward", False)
    item.setdefault("is_alcoholic_beverage", item.get("category") == "beer")
    return item


def process_image(path: Path, index: int, client: httpx.Client, khr_per_usd: float) -> dict | None:
    cache_file = RAW_CACHE_DIR / f"{path.stem}.json"
    if cache_file.exists():
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
    else:
        print(f"[{index:02d}] extracting {path.name} ...", flush=True)
        image_bytes = downscale_image(path)
        for attempt in range(3):
            try:
                raw = call_vision_model(image_bytes, client)
                break
            except Exception as exc:  # noqa: BLE001
                print(f"    attempt {attempt + 1} failed: {exc}", flush=True)
                if attempt == 2:
                    return None
                time.sleep(2 * (attempt + 1))
        RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    items = [normalize_item(it, khr_per_usd) for it in raw.get("items", [])]
    name_en = raw.get("restaurant_name_en") or f"Restaurant {index}"
    restaurant = {
        "id": slugify(name_en, f"restaurant-{index}"),
        "source_image": path.name,
        "restaurant_name_kh": raw.get("restaurant_name_kh"),
        "restaurant_name_en": name_en,
        "phone": raw.get("phone"),
        "items": items,
    }
    return restaurant


def main() -> None:
    khr_per_usd = float(os.environ.get("KHR_PER_USD", "4100"))
    images = sorted(DATA_DIR.glob("*.png")) + sorted(DATA_DIR.glob("*.jpg")) + sorted(DATA_DIR.glob("*.jpeg"))
    if not images:
        print(f"No images found in {DATA_DIR}", file=sys.stderr)
        sys.exit(1)

    RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    restaurants = []
    with httpx.Client() as client:
        for i, path in enumerate(images, start=1):
            result = process_image(path, i, client, khr_per_usd)
            if result:
                restaurants.append(result)

    # de-duplicate ids
    seen: dict[str, int] = {}
    for r in restaurants:
        base_id = r["id"]
        seen[base_id] = seen.get(base_id, 0) + 1
        if seen[base_id] > 1:
            r["id"] = f"{base_id}-{seen[base_id]}"

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps({"restaurants": restaurants}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    total_items = sum(len(r["items"]) for r in restaurants)
    print(f"Wrote {len(restaurants)} restaurants, {total_items} items -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
