"""Regression tests for report evidence, denominators, scenarios and escaping."""

import copy
import json
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audience_core.report import build_report


def session(identifier, status="completed", outcome="success", rating=9, evidence=True):
    return {
        "id": identifier,
        "persona_id": identifier,
        "model": "test-model",
        "mode": "first_use",
        "status": status,
        "duration_s": 2,
        "events": [{"id": identifier + "-e1", "action": {"type": "click"}, "observation": {"url": "https://example.com/done", "title": "Complete", "text": "Saved", "elements": []}, "result": {"ok": True}, "elapsed_ms": 100}],
        "feedback": {"outcome": outcome, "rating": rating, "likes": [], "dislikes": [], "recommendations": [], "return_intent": True, "summary": "Done", "evidence_ids": [identifier + "-e1"] if evidence else []},
    }


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)


class ReportTests(unittest.TestCase):
    def report(self, sessions=None, **extra):
        run = {"id": "test", "plan": {"url": "https://example.com", "task": "Save", "audience": "Test audience", "report_focus": ["usability", "conversion", "retention", "pricing"], "personas": []}, "sessions": sessions or [], "ledger": []}
        run.update(extra)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        paths = build_report(run, Path(folder.name))
        def reject_nonstandard_constant(value):
            raise ValueError("Nonstandard JSON token: " + value)
        report = json.loads(Path(paths["json"]).read_text(), parse_constant=reject_nonstandard_constant)
        page = Path(paths["html"]).read_text()
        return report, page, paths

    def test_task_denominator_excludes_infrastructure_and_blocked(self):
        sessions = [session("ok"), session("failure", outcome="failure"), session("error", status="error"), session("blocked", status="blocked"), session("abandon", status="abandoned", outcome="failure"), session("limited", status="step_limit", outcome="partial")]
        report, _, _ = self.report(sessions)
        metric = report["metrics"]
        self.assertEqual(metric["total"], 6)
        self.assertEqual(metric["eligible"], 4)
        self.assertEqual(metric["task_success"], 1)
        self.assertEqual(metric["completion_rate"], .25)
        self.assertEqual(metric["infrastructure_error_rate"], 1 / 6)
        self.assertEqual(metric["blocked_rate"], 1 / 6)

    def test_success_requires_usable_same_session_evidence(self):
        cases = [session("missing", evidence=False), session("wrong"), session("explicit-error"), session("finish-only"), session("duplicate"), session("valid")]
        cases[1]["feedback"]["evidence_ids"] = ["valid-e1"]
        cases[2]["events"][0]["result"] = {"ok": False, "error": "network"}
        cases[3]["events"][0]["action"] = {"type": "finish"}
        cases[4]["events"].append(copy.deepcopy(cases[4]["events"][0]))
        report, _, _ = self.report(cases)
        self.assertEqual(report["metrics"]["task_success"], 1)
        self.assertEqual(report["metrics"]["sessions"][-1]["evidence"][0]["id"], "valid-e1")

    def test_pending_running_and_budget_limit_are_not_assessed(self):
        sessions = [session("done", rating=10), session("pending", status="pending", rating=0), session("running", status="running", rating=0), session("budget", status="budget_limit", rating=0), session("steps", status="step_limit", outcome="partial", rating=8)]
        report, page, paths = self.report(sessions)
        metric = report["metrics"]
        self.assertEqual(metric["total"], 5)
        self.assertEqual(metric["eligible"], 2)
        self.assertEqual(metric["task_success"], 1)
        self.assertEqual(metric["task_non_success"], 1)
        self.assertEqual(metric["completion_rate"], .5)
        self.assertEqual(metric["nps_n"], 2)
        self.assertEqual(metric["synthetic_nps"], 50)
        self.assertEqual(metric["pending"], 1)
        self.assertEqual(metric["running"], 1)
        self.assertEqual(metric["budget_limited"], 1)
        self.assertEqual(metric["excluded"], 3)
        self.assertIn("Не запускалась", page)
        self.assertIn("В работе", page)
        self.assertIn("Лимит бюджета", page)
        self.assertNotIn("Как закончились сессии", page)
        self.assertIn("Ожидают запуска", Path(paths["md"]).read_text())

    def test_infrastructure_feedback_cannot_inflate_synthetic_nps(self):
        sessions = [session("good", rating=0), session("error", status="error", rating=10), session("blocked", status="blocked", rating=10)]
        report, _, _ = self.report(sessions)
        self.assertEqual(report["metrics"]["nps_n"], 1)
        self.assertEqual(report["metrics"]["synthetic_nps"], -100)

    def test_only_pending_sessions_do_not_claim_an_executed_or_failed_run(self):
        report, page, _ = self.report([session("pending", status="pending")])
        self.assertEqual(report["metrics"]["eligible"], 0)
        self.assertIsNone(report["metrics"]["completion_rate"])
        self.assertIsNone(report["metrics"]["synthetic_nps"])
        self.assertEqual(report["metrics"]["task_non_success"], 0)
        self.assertIn("Нет завершённых сессий", report["insight"])
        self.assertNotIn("Все сессии заблокированы", page)

    def test_ratings_exclude_invalid_values_and_show_sample_size(self):
        ratings = [10, 9, 8, 7, 6, 0, -1, 11, "10", None, True, 9.5, float("nan"), float("inf")]
        report, page, _ = self.report([session(str(index), rating=rating) for index, rating in enumerate(ratings)])
        self.assertEqual(report["metrics"]["nps_n"], 6)
        self.assertEqual(report["metrics"]["synthetic_nps"], 0)
        self.assertEqual(report["metrics"]["nps_promoters"], 2)
        self.assertEqual(report["metrics"]["nps_detractors"], 2)
        self.assertIn("По 6 ответам AI-агентов", page)

    def test_no_eligible_sessions_or_ratings_produces_no_percentage(self):
        report, _, _ = self.report([session("blocked", "blocked", rating=None)])
        self.assertIsNone(report["metrics"]["completion_rate"])
        self.assertIsNone(report["metrics"]["synthetic_nps"])

    def test_model_and_mode_breakdowns_use_their_own_denominators(self):
        sessions = [session("a"), session("b", status="blocked"), session("c", outcome="partial")]
        sessions[2]["model"] = "other-model"
        sessions[2]["mode"] = "regular"
        report, _, _ = self.report(sessions)
        self.assertEqual(report["metrics"]["by_model"]["test-model"]["completion_rate"], 1)
        self.assertEqual(report["metrics"]["by_model"]["other-model"]["completion_rate"], 0)
        self.assertEqual(report["metrics"]["by_mode"]["regular"]["eligible"], 1)

    def test_all_untrusted_html_is_escaped_and_unsafe_urls_are_not_links(self):
        injection = '<script>alert("bad")</script><img src=x onerror=alert(1)>'
        dangerous = session(injection)
        dangerous["model"] = injection
        dangerous["persona_id"] = injection
        dangerous["events"][0]["observation"]["url"] = 'javascript:alert("bad")'
        dangerous["events"][0]["observation"]["text"] = injection
        dangerous["events"][0]["action"] = injection
        dangerous["feedback"]["summary"] = injection
        dangerous["feedback"]["recommendations"] = [{"change": injection, "reason": injection, "evidence_ids": [dangerous["events"][0]["id"]]}]
        report, page, paths = self.report([dangerous], id=injection, plan={"url": "data:text/html,<script>alert(1)</script>", "task": injection, "audience": injection})
        parser = PageParser()
        parser.feed(page)
        # Exactly two bundled scripts: inert JSON data and the trusted UI runtime.
        # Untrusted closing tags cannot add a third executable script.
        self.assertEqual(parser.tags.count("script"), 2)
        self.assertNotIn(injection, page)
        self.assertIn("application/json", page)
        self.assertNotIn("img", parser.tags)
        self.assertFalse(any(key.lower().startswith("on") for key, _ in parser.attributes))
        self.assertFalse(any(key == "href" and (value or "").startswith(("javascript:", "data:")) for key, value in parser.attributes))
        self.assertIn("&lt;script&gt;", page)
        self.assertEqual(report["run"]["sessions"][0]["feedback"]["summary"], injection)
        self.assertNotIn("<script>", Path(paths["md"]).read_text())

    def test_safe_links_escape_attribute_injection(self):
        report, page, _ = self.report(plan={"url": 'https://example.com/\" onmouseover=\"alert(1)', "task": "test"})
        parser = PageParser()
        parser.feed(page)
        self.assertFalse(any(key.startswith("on") for key, _ in parser.attributes))
        self.assertTrue(any(key == "href" and value.startswith("https://example.com/") for key, value in parser.attributes))

    def test_forecast_uses_external_scenario_bounds_and_named_assumptions(self):
        report, _, _ = self.report(forecast_inputs={"monthly_visitors": 1000, "marketing_spend": 1000, "paid_conversion": [.01, .04], "return_rate": [.1, .2], "active_days": [3, 6], "mau": [100, 200]})
        forecast = report["forecast"]
        self.assertEqual(forecast["scenarios"]["cac"]["low"], 25)
        self.assertEqual(forecast["scenarios"]["cac"]["high"], 100)
        self.assertEqual(forecast["scenarios"]["paying_customers"]["low"], 10)
        self.assertEqual(forecast["scenarios"]["dau"]["low"], 10)
        self.assertEqual(forecast["scenarios"]["dau"]["high"], 40)
        self.assertEqual(forecast["scenarios"]["mau"]["low"], 100)
        self.assertGreaterEqual(len(forecast["assumptions"]), 4)

    def test_cac_is_undefined_at_zero_conversion(self):
        for conversion, low in [([0, .04], 25), ([0, 0], None)]:
            with self.subTest(conversion=conversion):
                report, _, _ = self.report(forecast_inputs={"monthly_visitors": 1000, "marketing_spend": 1000, "paid_conversion": conversion})
                cac = report["forecast"]["scenarios"]["cac"]
                self.assertEqual(cac["low"], low)
                self.assertIsNone(cac["high"])
                self.assertTrue(cac["undefined_at_zero_conversion"])

    def test_return_intent_and_unapproved_forecasts_never_generate_numbers(self):
        report, page, _ = self.report([session("good")], forecasts={"dau": 5000, "retention": .9})
        self.assertEqual(report["forecast"]["scenarios"], {})
        self.assertIn("Прогноз продуктовых метрик", page)
        self.assertIn("Для расчёта нужны исходные данные", page)
        self.assertNotIn("5000", page)

    def test_invalid_forecast_ranges_are_not_calculated(self):
        report, _, _ = self.report(forecast_inputs={"monthly_visitors": -1, "marketing_spend": True, "paid_conversion": [1.1, 1.2], "active_days": [6, 3], "mau": [100, 200], "return_rate": "high"})
        self.assertNotIn("cac", report["forecast"]["scenarios"])
        self.assertNotIn("dau", report["forecast"]["scenarios"])
        self.assertEqual(set(report["forecast"]["invalid"]), {"monthly_visitors", "marketing_spend", "paid_conversion", "active_days", "return_rate"})

    def test_priority_recommendations_link_to_recorded_events(self):
        failing = session("fail", outcome="failure")
        failing["feedback"]["recommendations"] = [{"change": "Show save confirmation", "reason": "Result unclear", "evidence_ids": ["fail-e1"]}, {"change": "Try green", "reason": "Preference", "evidence_ids": ["not-an-event"]}]
        report, page, _ = self.report([failing])
        top = report["recommendations"][0]
        self.assertEqual(top["change"], "Show save confirmation")
        self.assertEqual(top["priority"], "Высокий")
        self.assertIn('href="#session-1-event-1"', page)
        self.assertIn('id="session-1-event-1"', page)
        self.assertEqual(report["recommendations"][1]["priority"], "Нужна проверка")

    def test_report_focus_is_adaptive_and_raw_trace_is_preserved(self):
        original = session("kept")
        report, page, paths = self.report([original], plan={"report_focus": ["pricing"]}, ledger=[{"amount": 1.5, "model": "test-model"}])
        self.assertEqual([item["focus"] for item in report["focus"]], ["pricing"])
        self.assertEqual(report["run"]["sessions"][0], original)
        self.assertEqual(report["run"]["ledger"], [{"amount": 1.5, "model": "test-model"}])
        self.assertEqual(set(paths), {"json", "md", "html"})
        self.assertTrue(all(Path(path).is_absolute() and Path(path).is_file() for path in paths.values()))
        self.assertIn("<details", page)

    def test_costs_separate_actual_estimated_unknown_and_reserved(self):
        ledger = [
            {"requested_model": "m1", "returned_model": "served-m1", "cost_status": "actual", "cost_usd": .1, "accounted_usd": .1, "reserved_usd": .5},
            {"requested_model": "m1", "cost_status": "estimated", "cost_usd": .2, "accounted_usd": .2, "reserved_usd": .2},
            {"requested_model": "m1", "cost_status": "unknown", "cost_usd": None, "accounted_usd": .3, "reserved_usd": .3},
            {"model": "m2", "cost_status": "reserved", "cost_usd": None, "accounted_usd": .4, "reserved_usd": .4},
            {"model": "m2", "cost_status": "not_charged", "cost_usd": 0, "accounted_usd": 0, "reserved_usd": .5},
        ]
        report, page, paths = self.report(ledger=ledger, plan={"budget_usd": 2})
        cost = report["costs"]
        self.assertAlmostEqual(cost["confirmed_usd"], .1)
        self.assertAlmostEqual(cost["estimated_usd"], .2)
        self.assertAlmostEqual(cost["unknown_usd"], .3)
        self.assertAlmostEqual(cost["reserved_usd"], .4)
        self.assertAlmostEqual(cost["accounted_usd"], 1)
        self.assertAlmostEqual(cost["budget_remaining_usd"], 1)
        self.assertEqual(cost["budget_usd"], 2)
        self.assertAlmostEqual(cost["by_model"]["served-m1"]["confirmed_usd"], .1)
        self.assertIn("Подтверждено провайдером", page)
        self.assertIn("Это не счёт провайдера", page)
        self.assertIn("Расходы на исследование", Path(paths["md"]).read_text())

    def test_costs_without_amounts_do_not_claim_known_remaining_budget(self):
        report, _, _ = self.report(ledger=[{"model": "test", "cost_status": "unknown"}], plan={"budget_usd": 1})
        self.assertEqual(report["costs"]["unquantified_entries"], 1)
        self.assertIsNone(report["costs"]["budget_remaining_usd"])
        self.assertEqual(report["costs"]["confirmed_usd"], 0)

    def test_imported_secrets_are_redacted_without_mutating_run(self):
        credential = "sk-or-v1-" + "a" * 36
        original = session("private")
        original["feedback"]["summary"] = credential
        forecast = {"source": credential, "api_key": credential}
        before = copy.deepcopy(original)
        report, page, paths = self.report([original], forecast_inputs=forecast)
        self.assertEqual(original, before)
        self.assertEqual(forecast["api_key"], credential)
        for path in paths.values():
            self.assertNotIn(credential, Path(path).read_text())
        self.assertEqual(report["run"]["sessions"][0]["feedback"]["summary"], "[REDACTED]")

    def test_nonfinite_invalid_forecast_can_still_render(self):
        report, page, paths = self.report(forecast_inputs={"baseline": {"mau": float("inf"), "active_days": 4}})
        self.assertIn("baseline.mau", report["forecast"]["invalid"])
        self.assertEqual(report["forecast"]["baseline"]["metrics"], {})
        self.assertTrue(Path(paths["html"]).is_file())

    def test_cac_currency_is_external_and_research_costs_remain_usd(self):
        report, _, _ = self.report(forecast_inputs={"monthly_visitors": 1000, "marketing_spend": 1000, "paid_conversion": [.01, .04], "currency": "rub"})
        self.assertEqual(report["forecast"]["scenarios"]["cac"]["unit"], "RUB / клиент")
        self.assertEqual(report["costs"]["currency"], "USD")


if __name__ == "__main__":
    unittest.main()
