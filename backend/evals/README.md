# Diner agent eval

`diner_questions.json` contains 30 distinct scenarios in Vietnamese, English and Khmer:
meal planning, groups, vegetarian preferences, allergy, spice, dessert, prices, availability,
hours, delivery, five currencies, missing/negative/zero/positive/malformed budgets, quantities,
off-topic requests, prompt injection and blank input.

From `backend/` in PowerShell:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m evals.run --live
.venv/Scripts/python.exe -m evals.run --live --ids 12 --output evals/results/negative-budget.json
```

Offline pytest checks the dataset, malformed HTTP requests, the grader, provider-failure detection,
and regression tests. It does **not** measure whether a model understands the 30 messages.
Install `pytest` separately if needed; it is a development dependency.

Live eval uses the real configured `CHAT_MODEL` and `OPENROUTER_API_KEY`, the local FastAPI
`/api/chat` route, and the repository menu dataset. It consumes API credits. There are up to two
model calls per valid message; execution is sequential. It does not call the deployed website.
The completion wrapper observes real calls and flags provider errors even if the app falls back.

Each JSON case supplies partial expected intent fields, expected quantities, forbidden roles,
and optional empty-combo/refusal requirements. The grader also checks real menu names/prices,
line multiplication, combo sums and budget flags. Every failed check is included in the report;
the command exits 1 on any failure, 0 on all passes. Reports are saved after every case so an
interrupted run keeps completed results. `summary.total` is the number actually executed.

`review`/`manual_review` are human review instructions, **not automatically scored**. A passing
case does not certify allergy safety, factual prose, prompt confidentiality, preference handling,
or overall answer quality. Read the recorded `response.reply` for those criteria. Model results
can vary between runs. The suite mixes product expectations (reject negative budgets, preserve
zero, reject malformed numbers, do not turn lookups into orders) with current quantity
limits (invalid/negative quantity defaults to 1; maximum 10). Those quantity policies may warrant
a future clarification flow rather than silent normalization.

`results/latest.json` stores the latest full run; a future run overwrites it.
`results/negative-budget.json` preserves the earlier targeted live check for negative budgets.
Negative or unparseable budgets must produce a clarification without combos. Zero is a valid
budget and must not be increased to $0.25. Price and availability lookups must not become orders;
the known beer/chicken-feet lookups also must not return the canned out-of-scope refusal.

The eval exposed errors in routing lookup intents, preserving zero, accepting broken decimal
separators, and handling punctuation in menu searches. Regression tests cover those fixes.
The extraction prompt also explicitly separates negative dish quantities from negative money
and distinguishes vague money statements from messages that never mention money.
