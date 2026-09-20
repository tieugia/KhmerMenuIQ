"""Run real /api/chat calls in-process; never substitute expected model outputs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import llm
from app.config import CHAT_MODEL, OPENROUTER_API_KEY
from app.data_store import load_restaurants
from app.guardrails import OUT_OF_SCOPE_REPLY
from app.main import app

CASES_PATH = Path(__file__).with_name("diner_questions.json")


def load_cases():
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def grade(case, status, body):
    """Return all deterministic failures, leaving subjective prose to human review."""
    errors = []

    def check(ok, detail):
        if not ok:
            errors.append(detail)

    expected = case["expected"]
    check(status == expected.get("status_code", 200), f"HTTP {status}")
    if status != 200 or expected.get("status_code", 200) != 200:
        return errors
    intent = body.get("intent", {})
    for key, value in expected.items():
        if key in {"status_code", "wants", "forbidden_roles", "combos", "refusal"}:
            continue
        check(key in intent and intent[key] == value,
              f"{key}: expected {value!r}, got {intent.get(key)!r}")
    wants = {w["role"]: w["quantity"] for w in intent.get("wants", [])}
    for role, quantity in expected.get("wants", {}).items():
        check(wants.get(role) == quantity,
              f"wants.{role}: expected {quantity}, got {wants.get(role)!r}")
    for role in expected.get("forbidden_roles", []):
        check(role not in wants, f"Unwanted role: {role}")
    combos = body.get("combos", [])
    if expected.get("combos") == "empty":
        check(not combos, "Lookup/off-topic request incorrectly returned order combos")
    if expected.get("intent_type") == "order" and expected.get("combos") != "empty":
        check(bool(combos), "Order produced no combos")
    check(bool(body.get("reply", "").strip()), "Empty reply")
    if expected.get("refusal"):
        check(body.get("reply") == OUT_OF_SCOPE_REPLY, "Expected out-of-scope reply")
    elif expected.get("refusal") is False:
        check(body.get("reply") != OUT_OF_SCOPE_REPLY, "Known menu lookup was refused")
    restaurants = {r.id: r for r in load_restaurants()}
    for combo in combos:
        restaurant = restaurants.get(combo["restaurant_id"])
        check(restaurant is not None, "Invented restaurant")
        if restaurant is None:
            continue
        total = round(sum(line["line_total_usd"] for line in combo["lines"]), 2)
        check(total == combo["total_usd"], "Incorrect combo sum")
        check(combo["budget_usd"] == intent.get("budget_usd"), "Combo budget differs from intent")
        budget = combo["budget_usd"]
        check(combo["within_budget"] == (not combo["missing_roles"] and (budget is None or total <= budget)),
              "Incorrect within_budget flag")
        for line in combo["lines"]:
            check(line["line_total_usd"] == round(line["unit_price_usd"] * line["quantity"], 2),
                  "Incorrect line multiplication")
            check(any(item.name_en == line["item_name_en"] and item.name_kh == line["item_name_kh"]
                      and item.min_price_usd == line["unit_price_usd"] for item in restaurant.items),
                  f"Item/price not in restaurant menu: {line['item_name_en']}")
    return errors


def run_case(client, case):
    started = time.monotonic()
    transport_errors = []
    completion = llm._chat_completion
    calls = 0

    def observed_completion(*args, **kwargs):
        nonlocal calls
        calls += 1
        try:
            return completion(*args, **kwargs)
        except Exception as exc:
            # The app swallows provider failures; do not let fallback responses count as passes.
            # Store class only: provider exceptions can contain sensitive request information.
            transport_errors.append(f"LLM call failed: {type(exc).__name__}")
            raise

    body = {}
    status = None
    try:
        with patch.object(llm, "_chat_completion", side_effect=observed_completion):
            response = client.post("/api/chat", json={"message": case["message"]})
        status, body = response.status_code, response.json()
        errors = grade(case, status, body)
    except Exception as exc:
        errors = [f"Evaluation exception: {type(exc).__name__}"]
    errors.extend(transport_errors)
    return {"id": case["id"], "topic": case["topic"], "message": case["message"],
            "expected": case["expected"], "passed": not errors, "errors": errors,
            "status_code": status, "llm_calls": calls, "seconds": round(time.monotonic() - started, 2),
            "response": body, "manual_review": case["review"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call configured OpenRouter model (uses API credits)")
    parser.add_argument("--ids", nargs="+", help="Run only these case IDs")
    parser.add_argument("--output", type=Path, default=Path("evals/results/latest.json"))
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to run real model evaluation; use pytest for offline checks")
    if not OPENROUTER_API_KEY:
        parser.error("OPENROUTER_API_KEY is not configured")
    cases = load_cases()
    if args.ids:
        unknown = set(args.ids) - {case["id"] for case in cases}
        if unknown:
            parser.error(f"Unknown case IDs: {sorted(unknown)}")
        cases = [case for case in cases if case["id"] in args.ids]
    report = {"model": CHAT_MODEL, "started_at": datetime.now(timezone.utc).isoformat(),
              "mode": "live", "grading": "Deterministic structured checks; prose requires manual review",
              "results": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with TestClient(app) as client:
        for case in cases:
            result = run_case(client, case)
            report["results"].append(result)
            counts = Counter("passed" if row["passed"] else "failed" for row in report["results"])
            report["summary"] = {"total": len(report["results"]), "passed": counts["passed"], "failed": counts["failed"]}
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"{'PASS' if result['passed'] else 'FAIL'} {case['id']} {case['topic']}: {result['errors']}", flush=True)
    print(json.dumps(report["summary"]), flush=True)
    return int(report["summary"]["failed"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
