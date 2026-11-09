"""Offline checks for bounded, evidence-linked final interpretation."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audience_core.openrouter import AudienceError, BudgetExceeded, estimate_request_cost
from audience_core.synthesis import (
    enrich_run, source_fingerprint, validated_synthesis, validate_synthesis,
    MAX_OUTPUT_TOKENS, MAX_PROMPT_BYTES, _collect, _messages,
)


def model(rate="0.0000001", name="a/model"):
    return {"id": name, "context_length": 32000,
            "supported_parameters": ["response_format"],
            "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
            "pricing": {"prompt": rate, "completion": rate, "request": "0"}}


def fixture(count=2):
    personas, sessions = [], []
    for index in range(count):
        p = "p" + str(index)
        s = p + "-first"
        event = s + ":e1"
        personas.append({"id": p, "segment": "Mobile" if index % 2 else "Desktop", "goal": "Find the booking result"})
        sessions.append({"id": s, "persona_id": p, "mode": "first_use", "model": "a/model",
                         "status": "abandoned", "events": [{"id": event,
                         "action": {"type": "click", "target": "continue"},
                         "result": {"status": "ok"},
                         "observation": {"url": "https://example.test", "text": "Request is prepared. Confirm to send."}}],
                         "feedback": {"outcome": "failure", "summary": "Could not identify completion", "evidence_ids": [event],
                         "recommendations": [{"change": "Show whether request has been sent", "evidence_ids": [event]}]}})
    return {"plan": {"task": "Проверь понятность сайта", "url": "https://example.test",
                     "budget_usd": 1, "personas": personas, "models": [{"id": "a/model"}]},
            "sessions": sessions, "ledger": []}


def reply(ids=None):
    ids = ids or ["p0-first:e1", "p1-first:e1"]
    return {"summary": "Покажите, когда заявка отправлена, а когда ждёт подтверждения.",
            "summary_evidence_ids": ids,
            "recommendations": [{"issue_key": "unclear_completion", "stage": "result", "scope": "product",
                "change": "Показать статус заявки", "reason": "Непонятно, нужно ли ещё действовать.",
                "observed": "На экране есть подготовленная заявка и кнопка подтверждения.",
                "proposed": "Показать отдельную карточку со статусом и следующим шагом.",
                "expected_metric": "Доля успешно завершённых задач",
                "how_to_verify": "Повторить сценарий отправки заявки после изменения интерфейса.",
                "evidence_ids": ids, "hypothesis": True}],
            "positives": [{"title": "Сохранить предварительный просмотр", "description": "Содержимое заявки доступно до отправки.",
                           "evidence_ids": ids[:1]}], "caveats": ["Проверить изменение на реальных пользователях."]}


class Client:
    def __init__(self, response=None, remaining="1", catalogue=None):
        self.budget_remaining = Decimal(remaining)
        self.catalogue = catalogue or [model()]
        self.response = response if response is not None else reply()
        self.calls = []
        self.catalogue_calls = 0
        self.ledger = []

    def list_models(self):
        self.catalogue_calls += 1
        return self.catalogue

    def complete_json(self, chosen, messages, max_tokens):
        self.calls.append((chosen, copy.deepcopy(messages), max_tokens))
        quote = estimate_request_cost(chosen, messages, max_tokens)
        self.budget_remaining -= quote
        self.ledger.append({"requested_model": chosen["id"], "accounted_usd": float(quote)})
        if isinstance(self.response, Exception):
            raise self.response
        return copy.deepcopy(self.response)


class SynthesisTests(unittest.TestCase):
    def test_single_call_caches_and_revalidates_without_network(self):
        run, client = fixture(), Client()
        result = enrich_run(run, client)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["recommendations"][0]["scope"], "product")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(run["ledger"], client.ledger)
        self.assertLessEqual(result["estimated_cost_usd"], .12)
        self.assertTrue(validated_synthesis(run))
        self.assertIs(enrich_run(run, client), result)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.catalogue_calls, 1)

    def test_cache_fingerprint_changes_with_evidence_not_ledger(self):
        run = fixture()
        first = source_fingerprint(run)
        run["ledger"] = [{"cost_usd": .05}]
        self.assertEqual(first, source_fingerprint(run))
        run["sessions"][0]["events"][0]["observation"]["text"] += " Changed."
        self.assertNotEqual(first, source_fingerprint(run))

    def test_stale_saved_synthesis_never_rendered(self):
        run = fixture()
        enrich_run(run, Client())
        run["sessions"][0]["feedback"]["summary"] = "Different assessment"
        self.assertIsNone(validated_synthesis(run))

    def test_unknown_duplicate_and_failed_refs_are_not_accepted(self):
        for change in ("unknown", "duplicate", "failed", "url_only", "finish"):
            run, client = fixture(), Client()
            if change == "unknown":
                client.response["recommendations"][0]["evidence_ids"] = ["invented"]
            elif change == "duplicate":
                run["sessions"][1]["events"][0]["id"] = "p0-first:e1"
            elif change == "failed":
                run["sessions"][0]["events"][0]["result"] = {"status": "error"}
            elif change == "url_only":
                run["sessions"][0]["events"][0]["observation"].pop("text")
            else:
                run["sessions"][0]["events"][0]["action"] = {"type": "finish"}
            with self.subTest(change=change):
                self.assertNotEqual(enrich_run(run, client)["status"], "completed")
                self.assertIsNone(validated_synthesis(run))

    def test_product_scope_requires_different_personas(self):
        run = fixture(1)
        result = enrich_run(run, Client(reply(["p0-first:e1"])))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["recommendations"][0]["scope"], "flow")

    def test_infrastructure_blocks_and_pending_do_not_become_rejections(self):
        for status in ("blocked", "error", "pending", "running", "budget_limit"):
            run, client = fixture(1), Client()
            run["sessions"][0]["status"] = status
            self.assertEqual(enrich_run(run, client)["status"], "skipped")
            self.assertEqual(client.calls, [])

    def test_no_budget_no_call_and_no_substitution_outside_model_mix(self):
        for client in (Client(remaining="0"), Client(catalogue=[model(name="other/model")]),
                       Client(catalogue=[model(rate="1")])):
            result = enrich_run(fixture(), client)
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(client.calls, [])

    def test_explicit_planning_allowance_and_actual_balance_both_bind(self):
        for allowance, remaining in ((0, "1"), (.000001, "1"), (.12, ".000001")):
            run, client = fixture(), Client(remaining=remaining)
            run["plan"]["report_budget_reserve_usd"] = allowance
            result = enrich_run(run, client)
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(client.calls, [])

    def test_recommendations_remain_proposals_not_claimed_uplift(self):
        _, allowed = _collect(fixture())
        raw = reply()
        raw["recommendations"][0]["hypothesis"] = False
        with self.assertRaises(ValueError):
            validate_synthesis(raw, allowed)

    def test_invalid_or_failed_output_never_retried_for_same_evidence(self):
        for response in ({}, AudienceError("network failed"), BudgetExceeded("cap")):
            run, client = fixture(), Client(response)
            result = enrich_run(run, client)
            self.assertIn(result["status"], ("error", "skipped"))
            enrich_run(run, client)
            self.assertEqual(len(client.calls), 1)

    def test_fabricated_metrics_and_effect_claim_fields_are_rejected(self):
        rows, allowed = _collect(fixture())
        for value in ("Конверсия станет 70%", "CAC $10", "Новый экран <script>alert()</script>", "NPS +30"):
            raw = reply()
            raw["summary"] = value
            with self.assertRaises(ValueError):
                validate_synthesis(raw, allowed)
        raw = reply()
        raw["recommendations"][0]["predicted_uplift"] = .3
        with self.assertRaises(ValueError):
            validate_synthesis(raw, allowed)

    def test_bounded_prompt_sample_and_cross_segment_coverage(self):
        run = fixture(200)
        for s in run["sessions"]:
            s["events"][0]["observation"]["text"] = "Untrusted page " * 10000
            s["events"][0]["action"]["value"] = "я" * 100000
        rows, _ = _collect(run)
        messages, sample = _messages(run, rows)
        self.assertLessEqual(len(json.dumps(messages, ensure_ascii=False).encode()), MAX_PROMPT_BYTES)
        self.assertLess(len(sample), len(rows))
        self.assertIn("UNTRUSTED", messages[0]["content"])
        # Normal-size traces preserve both segments rather than sampling first names only.
        rows, _ = _collect(fixture(40))
        _, sample = _messages(fixture(40), rows)
        self.assertEqual({r["segment"] for r in sample}, {"Desktop", "Mobile"})

    def test_cached_payload_is_revalidated_even_if_fingerprint_unmodified(self):
        run = fixture()
        enrich_run(run, Client())
        run["product_synthesis"]["recommendations"][0]["evidence_ids"] = ["invented"]
        self.assertIsNone(validated_synthesis(run))


if __name__ == "__main__":
    unittest.main()
