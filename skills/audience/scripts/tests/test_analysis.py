"""Metric provenance, persona denominators, priorities and conditional forecasts."""
import copy
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audience_core.report import _aggregate, _forecast
from audience_core.analysis import analyze
from audience_core.forecast import extend_forecast


def visit(identifier, pid, mode="first_use", status="completed", rating=9, satisfaction=5, returned=True):
    eid = identifier + ":e1"
    return {"id": identifier, "persona_id": pid, "model": "test/model", "mode": mode, "status": status,
        "events": [{"id": eid, "action": {"type": "click"}, "result": {"status": "ok"}, "observation": {"url": "https://example.test", "text": "Saved"}}],
        "feedback": {"outcome": "success" if status == "completed" else "failure", "rating": rating, "return_intent": returned, "evidence_ids": [eid], "likes": ["Результат можно сохранить"],
        "assessment": {"purpose_clear": True, "next_step_clear": True, "result_clear": False, "satisfaction": satisfaction, "effort": 2, "evidence_ids": [eid]},
        "recommendations": [], "journey": [{"stage": "start", "reached": True, "evidence_ids": [eid]}]}}


def run_for(sessions, agents=2):
    return {"plan": {"url": "https://example.test", "task": "Проверь сайт", "scenario_modes": ["first_use", "regular"], "personas": [{"id": "p" + str(i), "name": "Агент " + str(i), "segment": "Выбрать товар" if i == 1 else "Вернуться к выбору", "group_id": "g" + str(i), "model": "test/model", "device": "mobile" if i == 1 else "desktop", "scenario_modes": ["first_use", "regular"]} for i in range(1, agents + 1)]}, "sessions": sessions}


def analysis(run):
    return analyze(run, run["sessions"], _aggregate(run["sessions"]))


class AnalysisTests(unittest.TestCase):
    def test_sampled_synthesis_discloses_coverage_without_reducing_metrics(self):
        run = run_for([visit('a','p1'), visit('b','p2')])
        run['product_synthesis'] = {'status':'completed', 'coverage':{'sampled':True,'sampled_sessions':1,'eligible_sessions':2}}
        with patch('audience_core.synthesis.validated_synthesis', return_value={'summary':'Проверить понятность результата','summary_evidence_ids':['a:e1'],'recommendations':[]}):
            result = analysis(run)
        self.assertEqual(result['experiment']['evaluable_sessions'],2)
        self.assertEqual(result['synthesis']['coverage']['sampled_sessions'],1)
        self.assertTrue(any('1 из 2' in warning for warning in result['experiment']['warnings']))

    def test_one_person_one_latest_valid_answer(self):
        a = visit("a", "p1", rating=10, satisfaction=5, returned=True)
        b = visit("b", "p1", "regular", rating=0, satisfaction=2, returned=False)
        c = visit("c", "p2", rating=9, satisfaction=4)
        d = visit("d", "p2", "regular", status="error", rating=0, satisfaction=1)
        result = analysis(run_for([a, b, c, d]))
        self.assertEqual(result["satisfaction"]["nps"], {"value": 0, "n": 2, "promoters": 1, "passives": 0, "detractors": 1, "unknown": 0})
        self.assertEqual(result["satisfaction"]["csat"]["satisfied"], 1)
        self.assertEqual(result["satisfaction"]["csat"]["mean"], 3)
        self.assertEqual(result["satisfaction"]["return_intent"]["yes"], 1)
        self.assertEqual(_aggregate([a, b, c, d])["synthetic_nps"], 0)
        self.assertEqual(_aggregate([a, b, c, d])["nps_n"], 2)

    def test_missing_answers_are_unknown_not_zero(self):
        a = visit("a", "p1")
        a["feedback"]["assessment"]["evidence_ids"] = ["invented"]
        a["feedback"]["evidence_ids"] = []
        result = analysis(run_for([a], agents=3))
        self.assertIsNone(result["satisfaction"]["csat"]["mean"])
        self.assertEqual(result["satisfaction"]["csat"]["unknown"], 3)
        self.assertEqual(result["satisfaction"]["nps"]["n"], 0)
        self.assertEqual(result["audience"][1]["first_use"]["unknown"], 1)

    def test_experiment_separates_plan_observation_and_evaluation(self):
        a = visit("a", "p1")
        b = visit("b", "p2", status="blocked")
        c = visit("c", "p1", "regular", status="pending")
        c["events"] = []
        result = analysis(run_for([a, b, c], agents=3))
        experiment = result["experiment"]
        self.assertEqual(experiment["planned_agents"], 3)
        self.assertEqual(experiment["executed_agents"], 2)
        self.assertEqual(experiment["evaluable_agents"], 1)
        self.assertEqual(experiment["planned_sessions"], 6)
        self.assertEqual(experiment["executed_sessions"], 2)
        self.assertEqual(experiment["evaluable_sessions"], 1)
        self.assertEqual(experiment["not_executed_sessions"], 4)
        self.assertEqual(experiment["blocked_sessions"], 1)

    def test_plan_only_does_not_turn_into_bad_product(self):
        a = visit("a", "p1", status="pending"); a["events"] = []
        result = analysis(run_for([a]))
        self.assertEqual(result["priorities"], [])
        self.assertEqual(result["experiment"]["executed_sessions"], 0)
        self.assertIn("Нет завершённых сессий", result["insight"])
        self.assertIsNone(result["satisfaction"]["csat"]["rate"])

    def test_product_issue_above_detail_and_counts_unique_people(self):
        a = visit("a", "p1", status="abandoned")
        b = visit("b", "p1", "regular", status="abandoned")
        c = visit("c", "p2", status="abandoned")
        for session in (a, b, c):
            session["feedback"]["recommendations"] = [{"change": "Показать, что можно сделать", "issue_key": "offer", "scope": "product", "stage": "entry", "reason": "Не нашли нужный сценарий", "evidence_ids": [session["events"][0]["id"]]}, {"change": "Исправить маленькую подпись", "issue_key": "detail", "scope": "detail", "stage": "action", "reason": "Подпись нечитаема", "evidence_ids": [session["events"][0]["id"]]}]
        result = analysis(run_for([a, b, c]))
        top = result["priorities"][0]
        self.assertEqual(top["scope"], "product")
        self.assertEqual(top["affected_count"], 2)
        self.assertEqual(len(top["session_ids"]), 3)
        self.assertEqual(top["evidence_count"], 3)
        self.assertTrue(top["expected_metric"])
        self.assertTrue(top["how_to_verify"])

    def test_bad_citations_cannot_make_priority_or_positive(self):
        a = visit("a", "p1")
        a["feedback"]["recommendations"] = [{"change": "Change", "scope": "product", "evidence_ids": ["missing"]}]
        a["feedback"]["evidence_ids"] = ["missing"]
        result = analysis(run_for([a]))
        self.assertEqual(result["priorities"], [])
        self.assertEqual(result["recommendations"][0]["affected_count"], 0)
        self.assertEqual(result["positives"], [])

    def test_journey_uses_explicit_supported_stage_answers(self):
        a = visit("a", "p1")
        a["feedback"]["journey"].append({"stage": "result", "reached": True, "evidence_ids": ["invented"]})
        result = analysis(run_for([a]))
        stages = {s["id"]: s for s in result["journey"]["stages"]}
        self.assertEqual(stages["start"]["n"], 1)
        self.assertEqual(stages["entry"]["n"], 0)
        self.assertEqual(stages["result"]["n"], 0)


class ForecastTests(unittest.TestCase):
    def forecast(self, values):
        return extend_forecast(values, _forecast({}))

    def test_explicit_baseline_and_scenario_math(self):
        inputs = {"source": "Допущения пользователя", "monthly_visitors": 10000, "marketing_spend": 300000, "currency": "RUB", "baseline": {"registration_rate": .35, "activation_rate": .6, "d7_retention": .25, "d30_retention": .12, "paid_conversion": .03, "mau": 5000, "active_days": 8}, "scenarios": [{"name": "base", "label": "Базовый", "assumptions": {"registration_rate": .4, "activation_rate": .65, "d7_retention": .28, "d30_retention": .15, "paid_conversion": .036, "mau": 5800, "active_days": 9}}]}
        original = copy.deepcopy(inputs)
        forecast = self.forecast(inputs)
        base = forecast["baseline"]["metrics"]
        after = forecast["named_scenarios"][0]["metrics"]
        self.assertEqual(base["activated_users"]["value"], 2100)
        self.assertEqual(base["d7_returners"]["value"], 525)
        self.assertEqual(after["activated_users"]["value"], 2600)
        self.assertAlmostEqual(after["d7_returners"]["value"], 728)
        self.assertEqual(after["d30_returners"]["value"], 390)
        self.assertAlmostEqual(after["cac"]["value"], 833.3333333333)
        self.assertEqual(after["dau"]["value"], 1740)
        self.assertEqual(forecast["comparison"][0]["metrics"]["activated_users"]["delta"], 500)
        self.assertEqual(forecast["named_scenarios"][0]["provenance"]["monthly_visitors"], "monthly_visitors")
        self.assertEqual(inputs, original)

    def test_zero_denominators_are_undefined(self):
        forecast = self.forecast({"monthly_visitors": 0, "marketing_spend": 200, "baseline": {"paid_conversion": 0, "mau": 0, "active_days": 5}, "scenarios": [{"name": "x", "paid_conversion": 0, "mau": 0, "active_days": 5}]})
        metrics = forecast["baseline"]["metrics"]
        self.assertIsNone(metrics["cac"]["value"])
        self.assertIsNone(metrics["stickiness"]["value"])
        self.assertIsNone(forecast["comparison"][0]["metrics"]["cac"]["delta"])
        self.assertIsNone(forecast["comparison"][0]["metrics"]["mau"]["relative_change"])

    def test_missing_data_never_creates_scenario(self):
        forecast = self.forecast({})
        self.assertFalse(forecast["available"])
        self.assertEqual(forecast["named_scenarios"], [])
        self.assertIsNone(forecast["baseline"])
        self.assertFalse(forecast["source_info"]["supplied"])

    def test_retention_can_use_explicit_cohort_but_never_mau(self):
        forecast = self.forecast({"baseline": {"mau": 1000, "d7_retention": .2, "d30_retention": .1}})
        self.assertNotIn("d7_returners", forecast["baseline"]["metrics"])
        forecast = self.forecast({"baseline": {"retention_cohort_size": 200, "d7_retention": .2}})
        self.assertEqual(forecast["baseline"]["metrics"]["d7_returners"]["value"], 40)

    def test_invalid_explicit_cohort_does_not_fallback(self):
        f = self.forecast({"monthly_visitors": 1000, "baseline": {"registration_rate": .5, "activation_rate": .5, "retention_cohort_size": -1, "d7_retention": .2}})
        self.assertIn("activated_users", f["baseline"]["metrics"])
        self.assertNotIn("d7_returners", f["baseline"]["metrics"])
        self.assertIn("retention_cohort_size", f["baseline"]["invalid"])

    def test_huge_finite_arithmetic_never_emits_infinity(self):
        f = self.forecast({"monthly_visitors": 1, "marketing_spend": 1e308, "baseline": {"paid_conversion": 1e-308, "mau": 1e308, "active_days": 30}})
        self.assertIsNone(f["baseline"]["metrics"]["cac"]["value"])
        self.assertIn("calculated.cac", f["baseline"]["invalid"])
        self.assertEqual(f["baseline"]["metrics"]["dau"]["value"], 1e308)

    def test_currency_change_does_not_create_cac_delta(self):
        f = self.forecast({"monthly_visitors": 1000, "paid_conversion": .1, "baseline": {"currency": "USD", "marketing_spend": 100}, "scenarios": [{"name": "after", "currency": "RUB", "marketing_spend": 1000}]})
        self.assertNotIn("cac", f["comparison"][0]["metrics"])
        self.assertEqual(f["baseline"]["metrics"]["cac"]["unit"], "USD / клиент")
        self.assertEqual(f["named_scenarios"][0]["metrics"]["cac"]["unit"], "RUB / клиент")
        self.assertTrue(any("валюты" in x for x in f["assumptions"]))

    def test_provenance_preserves_nested_assumption_paths(self):
        f = self.forecast({"monthly_visitors": 1000, "baseline": {"assumptions": {"paid_conversion": .1, "marketing_spend": 100}}, "scenarios": [{"name": "after", "assumptions": {"paid_conversion": .2}}]})
        self.assertEqual(f["baseline"]["provenance"]["marketing_spend"], "baseline.assumptions.marketing_spend")
        self.assertEqual(f["named_scenarios"][0]["provenance"]["paid_conversion"], "scenarios[0].assumptions.paid_conversion")

    def test_invalid_rates_and_nonfinite_inputs_do_not_propagate(self):
        forecast = self.forecast({"monthly_visitors": 100, "baseline": {"registration_rate": True, "activation_rate": 1.1, "d7_retention": -.2, "mau": float("inf"), "active_days": 31}})
        self.assertEqual(forecast["baseline"]["metrics"], {})
        self.assertEqual(set(forecast["baseline"]["invalid"]), {"registration_rate", "activation_rate", "d7_retention", "mau", "active_days"})


if __name__ == "__main__":
    unittest.main()
