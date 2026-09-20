# KhmerMenuIQ

Bilingual (Khmer/English) menu explorer + budget ordering assistant, built from 30 photographed
Cambodian restaurant menus in `data 1/`.

Answers questions like: *"I have a budget of $10. I want chicken, some vegetables, and a couple
of beers. What should I order, and from where?"*

## Stack

- **Data pipeline**: `backend/scripts/extract_menus.py` sends each menu photo to a vision LLM
  (via OpenRouter) to transcribe Khmer dish names, English translations, categories, and prices
  (Riel and/or USD) into `backend/data/menus.json`.
- **Backend**: FastAPI (`backend/app`) — serves the menu data and a `/api/chat` endpoint that
  extracts the diner's intent (budget + desired categories) via an LLM, deterministically computes
  the cheapest matching combo per restaurant in Python (so prices/totals are always correct, never
  hallucinated), then asks the LLM to phrase a friendly bilingual reply from those numbers.
- **Frontend**: React + Vite (`frontend/`) — a "Browse Menus" tab (bilingual, grouped by category)
  and an "Ask KhmerMenuIQ" chat tab that renders recommendations as receipt-style combo cards.

## Run locally

**1. Backend** (Python 3.11, from `backend/`):

```
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

**2. Frontend** (from `frontend/`):

```
npm run dev
```

Open **http://localhost:5173** — the Vite dev server proxies `/api` to the backend on port 8000.

## Re-running the data extraction

The menu dataset is already generated at `backend/data/menus.json` (with per-image cache in
`backend/data/raw/`, gitignored). To re-run it (e.g. after adding new menu photos to `data 1/`):

```
backend\.venv\Scripts\python.exe backend\scripts\extract_menus.py
```

Delete the relevant file(s) in `backend/data/raw/` first to force re-extraction of a specific image;
otherwise cached results are reused.

## Configuration

`backend/.env` (gitignored) holds `OPENROUTER_API_KEY`, plus `VISION_MODEL` / `CHAT_MODEL` (default
`google/gemini-2.5-flash`) and `KHR_PER_USD` (fixed conversion rate used to normalize Riel prices
to USD for budget math).
