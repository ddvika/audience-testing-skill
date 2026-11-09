"""Deterministic product-owner analysis from recorded synthetic sessions.

This module adds no participants, observations, survey answers or forecast inputs.
An LLM may summarize recorded issues separately; counts and attribution stay here.
"""
from __future__ import annotations

from collections import Counter
import re

STAGES = {"entry": "Понять, что предлагает продукт", "start": "Начать задачу", "action": "Выполнить нужные действия", "result": "Получить и понять результат", "return": "Продолжить при повторном визите"}
SCOPE = {"product": 0, "flow": 1, "detail": 2}
METRIC_CHECK = {
    "entry": ("Поняли назначение продукта", "Повторить первое знакомство и проверить, могут ли агенты своими словами объяснить, для чего нужен продукт."),
    "start": ("Поняли следующий шаг", "Повторить ту же задачу и проверить, получается ли начать без подсказок."),
    "action": ("Успешно завершили задачу", "Повторить те же сценарии с прежним составом групп и сравнить успешные завершения и причины остановки."),
    "result": ("Поняли результат действия", "После действия проверить, могут ли агенты объяснить, что уже выполнено и что требуется от них."),
    "return": ("Завершили задачу при повторном визите", "Повторить сценарий с сохранённым состоянием; затем проверить возвращения реальных пользователей по аналитике."),
}


def _d(value):
    return value if isinstance(value, dict) else {}


def _l(value):
    return value if isinstance(value, list) else []


def _t(value):
    return value.strip() if isinstance(value, str) else ""


def _refs(ids, refs, supports=True):
    answer = []
    for value in _l(ids):
        ref = refs.get(str(value))
        if ref and (not supports or ref["supports_result"]) and ref not in answer:
            answer.append(ref)
    return answer


def _scale(value, maximum=5):
    return value if type(value) is int and 1 <= value <= maximum else None


def _ratio(yes, total, population):
    return {"yes": yes, "n": total, "unknown": max(0, population - total), "rate": yes / total if total else None}


def _survey(rows, population):
    """One latest valid answer per participant per question, never per visit."""
    latest = {key: {} for key in ("rating", "satisfaction", "effort", "return_intent", "purpose_clear", "next_step_clear", "result_clear")}
    for row in rows:
        if not row["eligible"] or not row["observed"]:
            continue
        feedback, assessment = row["feedback"], _d(row["feedback"].get("assessment"))
        if feedback.get("outcome") not in ("success", "partial", "failure"):
            continue
        pid = row["persona_id"]
        if row["feedback_refs"]:
            value = row["rating"]
            if value is not None:
                latest["rating"][pid] = value
            value = feedback.get("return_intent")
            if type(value) is bool:
                latest["return_intent"][pid] = value
        if row["assessment_refs"]:
            for key in ("purpose_clear", "next_step_clear", "result_clear"):
                if type(assessment.get(key)) is bool:
                    latest[key][pid] = assessment[key]
            for key in ("satisfaction", "effort"):
                value = _scale(assessment.get(key))
                if value is not None:
                    latest[key][pid] = value
    ratings = list(latest["rating"].values())
    n = len(ratings)
    promoters, detractors = sum(x >= 9 for x in ratings), sum(x <= 6 for x in ratings)
    satisfied = list(latest["satisfaction"].values())
    csat_n = len(satisfied)
    effort = list(latest["effort"].values())
    return {
        "scope": "latest_valid_answer_per_persona",
        "note": "Каждый агент учитывается один раз по последнему допустимому ответу на вопрос. Это оценки AI-агентов после записанных действий, а не удовлетворённость реальных людей.",
        "nps": {"value": 100 * (promoters - detractors) / n if n else None, "n": n, "promoters": promoters, "passives": n - promoters - detractors, "detractors": detractors, "unknown": max(0, population - n)},
        "csat": {"satisfied": sum(x >= 4 for x in satisfied), "n": csat_n, "rate": sum(x >= 4 for x in satisfied) / csat_n if csat_n else None, "mean": sum(satisfied) / csat_n if csat_n else None, "unknown": max(0, population - csat_n), "distribution": [satisfied.count(x) for x in range(1, 6)]},
        "return_intent": _ratio(sum(latest["return_intent"].values()), len(latest["return_intent"]), population),
        "assessment": {key: _ratio(sum(latest[key].values()), len(latest[key]), population) for key in ("purpose_clear", "next_step_clear", "result_clear")},
        "effort": {"mean": sum(effort) / len(effort) if effort else None, "n": len(effort), "unknown": max(0, population - len(effort))},
    }


def _session_measure(rows, modes, planned):
    selected = [r for r in rows if r["mode"] in modes]
    # Count visit goals separately. A resume observation is not a new task.
    n = sum(r["eligible"] and r["observed"] for r in selected)
    success = sum(r["task_success"] and r["observed"] for r in selected)
    return {"success": success, "n": n, "unknown": max(0, planned - n), "rate": success / n if n else None}


def _issue_key(rec):
    key = _t(rec.get("issue_key"))
    if key:
        return key.casefold()[:120]
    return re.sub(r"\W+", " ", _t(rec.get("change")).casefold()).strip()


def _recommendations(rows, synthesis):
    """Only cited observed participants contribute to affected counts."""
    all_refs = {}
    global_counts = Counter(ref["id"] for row in rows for ref in row["refs"].values())
    for row in rows:
        if row["eligible"] and row["observed"]:
            for key, ref in row["refs"].items():
                if global_counts[key] == 1 and ref["supports_result"]:
                    all_refs[key] = {**ref, "persona_id": row["persona_id"], "session_id": row["id"], "session_anchor": row["anchor"], "failed": not row["task_success"]}
    candidates = []
    if synthesis:
        for rec in _l(synthesis.get("recommendations")):
            if isinstance(rec, dict):
                candidates.append((rec, _refs(rec.get("evidence_ids"), all_refs)))
    else:
        for row in rows:
            for rec in _l(row["feedback"].get("recommendations")):
                if not isinstance(rec, dict):
                    continue
                local = {key: {**ref, "persona_id": row["persona_id"], "session_id": row["id"], "session_anchor": row["anchor"], "failed": not row["task_success"]} for key, ref in row["refs"].items() if global_counts[key] == 1}
                refs = _refs(rec.get("evidence_ids"), local) if row["eligible"] and row["observed"] else []
                candidates.append((rec, refs))
    groups = {}
    for rec, refs in candidates:
        change = _t(rec.get("change")) or _t(rec.get("proposed"))
        if not change:
            continue
        stage = rec.get("stage") if rec.get("stage") in STAGES else "action"
        scope = rec.get("scope") if rec.get("scope") in SCOPE else "detail"
        key = (scope, stage, _issue_key({**rec, "change": change}))
        item = groups.setdefault(key, {"change": change, "issue_key": key[2], "stage": stage, "scope": scope, "reasons": [], "observed": _t(rec.get("observed")), "proposed": _t(rec.get("proposed")) or change, "expected_metric": _t(rec.get("expected_metric")) or METRIC_CHECK[stage][0], "how_to_verify": _t(rec.get("how_to_verify")) or METRIC_CHECK[stage][1], "evidence": [], "affected_personas": [], "session_ids": [], "session_anchors": [], "failure_sessions": 0, "hypothesis": True})
        reason = _t(rec.get("reason"))
        if reason and reason not in item["reasons"]:
            item["reasons"].append(reason)
        for ref in refs:
            if ref["id"] not in [r["id"] for r in item["evidence"]]:
                item["evidence"].append({"id": ref["id"], "anchor": ref["anchor"], "supports_result": True})
            if ref["persona_id"] not in item["affected_personas"]:
                item["affected_personas"].append(ref["persona_id"])
            if ref["session_id"] not in item["session_ids"]:
                item["session_ids"].append(ref["session_id"])
                item["session_anchors"].append(ref["session_anchor"])
                item["failure_sessions"] += int(ref["failed"])
    for rec in groups.values():
        if rec["scope"] == "product" and len(rec["affected_personas"]) < 2:
            rec["scope"] = "flow"
    ordered = sorted(groups.values(), key=lambda r: (not bool(r["evidence"]), SCOPE[r["scope"]], -len(r["affected_personas"]), -r["failure_sessions"], r["change"]))
    for rank, rec in enumerate(ordered, 1):
        rec.update(rank=rank, affected_count=len(rec["affected_personas"]), evidence_count=len(rec["evidence"]))
        rec["priority"] = "Высокий" if rec["evidence"] and rec["failure_sessions"] else "Средний" if rec["evidence"] else "Нужна проверка"
        if not rec["observed"]:
            rec["observed"] = " ".join(rec["reasons"]) or "Агент отметил трудность в записанном пути; подробности — в событиях."
    return ordered


def _positive_findings(rows, synthesis):
    groups = {}
    global_counts = Counter(ref["id"] for row in rows for ref in row["refs"].values())
    if synthesis:
        all_refs = {}
        counts = Counter(ref["id"] for row in rows for ref in row["refs"].values())
        for row in rows:
            if row["eligible"] and row["observed"]:
                for key, ref in row["refs"].items():
                    if counts[key] == 1 and ref["supports_result"]:
                        all_refs[key] = {**ref, "persona_id": row["persona_id"]}
        values = [(p, _refs(_d(p).get("evidence_ids"), all_refs)) for p in _l(synthesis.get("positives"))]
    else:
        values = [({"title": text}, [{**ref, "persona_id": row["persona_id"]} for ref in row["feedback_refs"] if global_counts[ref["id"]] == 1]) for row in rows if row["eligible"] and row["observed"] for text in _l(row["feedback"].get("likes")) if isinstance(text, str)]
    for positive, refs in values:
        text = _t(_d(positive).get("title")) or _t(_d(positive).get("description"))
        if not text or not refs:
            continue
        value = groups.setdefault(text.casefold(), {"text": text, "count": 0, "persona_ids": [], "evidence": []})
        for ref in refs:
            if ref["persona_id"] not in value["persona_ids"]:
                value["persona_ids"].append(ref["persona_id"])
            if ref["id"] not in [r["id"] for r in value["evidence"]]:
                value["evidence"].append({"id": ref["id"], "anchor": ref["anchor"]})
        value["count"] = len(value["persona_ids"])
    return sorted(groups.values(), key=lambda item: (-item["count"], item["text"]))


def analyze(run, sessions, metrics):
    from .report import _evidence
    plan = _d(run.get("plan"))
    design = _d(plan.get("experiment_design"))
    roster = {str(p["id"]): p for p in _l(plan.get("personas")) if isinstance(p, dict) and p.get("id") is not None}
    rows = []
    for index, session in enumerate(sessions):
        metric = metrics["sessions"][index]
        refs = _evidence(session, index)
        pid = str(session.get("persona_id") or "unknown-persona-" + str(index + 1))
        if pid not in roster:
            roster[pid] = {"id": pid, "name": pid, "segment": "Группа не указана", "model": metric["model"]}
        feedback = _d(session.get("feedback"))
        observed = any(_d(e.get("observation")).get("text") or _d(e.get("observation")).get("elements") for e in _l(session.get("events")) if isinstance(e, dict))
        rows.append({**metric, "persona_id": pid, "feedback": feedback, "observed": observed, "refs": refs, "feedback_refs": _refs(feedback.get("evidence_ids"), refs), "assessment_refs": _refs(_d(feedback.get("assessment")).get("evidence_ids"), refs)})
    synthesis = None
    try:
        from .synthesis import validated_synthesis
        synthesis = validated_synthesis(run)
    except (ImportError, AttributeError):
        pass
    recommendations = _recommendations(rows, synthesis)
    priorities = [r for r in recommendations if r["evidence"]][:3]
    satisfaction = _survey(rows, len(roster))
    satisfaction["first_use_assessment"] = _survey([r for r in rows if r["mode"] == "first_use"], len(roster))["assessment"]
    by_persona = {pid: [r for r in rows if r["persona_id"] == pid] for pid in roster}
    groups = {}
    design_groups = {str(g.get("id")): g for g in _l(design.get("groups")) if isinstance(g, dict)}
    for pid, persona in roster.items():
        group_key = _t(persona.get("group_id")) or _t(persona.get("segment")) or "unassigned"
        group = groups.setdefault(group_key, {"id": group_key, "label": _t(persona.get("segment")) or "Группа не указана", "why": _t(persona.get("selection_reason")) or _t(_d(design_groups.get(group_key)).get("selection_reason")) or "Гипотеза аудитории для проверки выбранных задач; репрезентативность не установлена.", "personas": []})
        group["personas"].append({"id": pid, "name": _t(persona.get("name")) or pid, "goal": _t(persona.get("goal")), "device": _t(persona.get("device")) or "не указан", "experience": _t(persona.get("experience")) or "не указан", "model": _t(persona.get("model")) or "не указана", "session_ids": [r["id"] for r in by_persona[pid]], "success_criteria": _l(persona.get("success_criteria")), "scenario_goals": _d(persona.get("scenario_goals"))})
    audience = []
    for group in groups.values():
        pids = {p["id"] for p in group["personas"]}
        group_rows = [r for r in rows if r["persona_id"] in pids]
        survey = _survey(group_rows, len(pids))
        person_modes = [_l(roster[pid].get("scenario_modes")) or _l(plan.get("scenario_modes")) or ["first_use"] for pid in pids]
        first_planned = max(sum("first_use" in modes for modes in person_modes), sum(r["mode"] == "first_use" for r in group_rows))
        repeat_planned = max(sum("regular" in modes for modes in person_modes), sum(r["mode"] == "regular" for r in group_rows))
        resume_planned = max(sum("resume" in modes for modes in person_modes), sum(r["mode"] == "resume" for r in group_rows))
        group.update(planned=len(pids), executed=sum(any(r["observed"] and r["status"] != "pending" for r in by_persona[pid]) for pid in pids), evaluable=sum(any(r["eligible"] and r["observed"] for r in by_persona[pid]) for pid in pids), first_use=_session_measure(group_rows, {"first_use"}, first_planned), repeat=_session_measure(group_rows, {"regular"}, repeat_planned), resume=_session_measure(group_rows, {"resume"}, resume_planned), choose_again=survey["return_intent"], satisfaction={"mean": survey["csat"]["mean"], "n": survey["csat"]["n"]})
        audience.append(group)
    planned_sessions = sum(len(_l(p.get("scenario_modes")) or _l(plan.get("scenario_modes")) or ["first_use"]) for p in roster.values())
    planned_sessions = max(planned_sessions, len(sessions))
    executed = [r for r in rows if r["observed"] and r["status"] != "pending"]
    models = []
    for mid in dict.fromkeys([_t(p.get("model")) or "Не указана" for p in roster.values()]):
        models.append({"id": mid, "planned": sum((_t(p.get("model")) or "Не указана") == mid for p in roster.values()), "executed": len({r["persona_id"] for r in executed if r["model"] == mid})})
    observed_viewports = {}
    for index, session in enumerate(sessions):
        pid = str(session.get("persona_id") or "unknown-persona-" + str(index + 1))
        for event in _l(session.get("events")):
            viewport = _d(_d(_d(event).get("observation")).get("viewport"))
            width, height = viewport.get("width"), viewport.get("height")
            if type(width) is int and type(height) is int and width > 0 and height > 0:
                observed_viewports[pid] = {"width": width, "height": height, "device": "mobile" if width <= 700 else "desktop"}
    measured_devices = dict(Counter(v["device"] for v in observed_viewports.values()))
    measured_devices["unknown"] = max(0, len(roster) - len(observed_viewports))
    experiment = {
        "product": _t(plan.get("product_summary")), "task": _t(plan.get("task")), "url": _t(plan.get("url")),
        "audience": _t(design.get("audience_summary")) or _t(plan.get("audience")) or "; ".join(g["label"] for g in audience),
        "why": _t(design.get("selection_reason")) or "Проверяем разные задачи, опыт и устройства, чтобы увидеть, где путь к результату отличается. Это гипотезы аудитории по доступному интерфейсу, а не данные о реальных клиентах.",
        "planned_agents": len(roster), "executed_agents": len({r["persona_id"] for r in executed}), "evaluable_agents": len({r["persona_id"] for r in rows if r["eligible"] and r["observed"]}),
        "planned_sessions": planned_sessions, "executed_sessions": len(executed), "evaluable_sessions": sum(r["eligible"] and r["observed"] for r in rows), "blocked_sessions": sum(r["status"] == "blocked" for r in rows), "failed_sessions": sum(r["status"] == "error" for r in rows), "not_executed_sessions": max(0, planned_sessions - len(executed)),
        "measured_devices": measured_devices, "observed_viewports": observed_viewports,
        "models": models, "devices": dict(Counter(_t(p.get("device")) or "не указано" for p in roster.values())), "scenario_modes": _l(plan.get("scenario_modes")) or list(dict.fromkeys(r["mode"] for r in rows)),
        "assumptions": _l(plan.get("assumptions")) + _l(design.get("limitations")), "warnings": _l(plan.get("warnings")) + _l(run.get("warnings")),
        "groups": [{k: g[k] for k in ("id", "label", "planned", "executed", "why")} for g in audience],
        "selection_basis": _t(design.get("selection_basis")) or "not_recorded",
    }
    session_mode = _t(plan.get("session_mode")) or _t(run.get("session_mode")) or "not_recorded"
    experiment["session_mode"] = session_mode
    experiment["session_mode_note"] = {
        "shared_account": "Общий тестовый аккаунт: у каждого AI-агента своя история решений и отдельный чат в продукте. Память и настройки аккаунта на сервере могут влиять на всех агентов; это не независимые новые пользователи.",
        "isolated": "Режим отдельных браузерных контекстов. Изоляция аккаунтов и серверной памяти требует отдельных учётных записей; её нельзя подтвердить только по браузерному контексту.",
    }.get(session_mode, "Режим изоляции не записан. Независимость аккаунтов и серверной памяти не подтверждена.")
    # A view/visit (including resume) must never inflate the number of new tasks.
    # Only engine/host-confirmed trigger evidence counts; do not guess from labels.
    new_task_sessions = [s for s in sessions if s.get("mode", "first_use") in ("first_use", "regular")]
    observed_new_tasks = [s for s in new_task_sessions if any(_d(_d(e).get("observation")).get("text") or _d(_d(e).get("observation")).get("elements") for e in _l(s.get("events")))]
    experiment["tasks_started"] = sum(s.get("task_started") is True for s in observed_new_tasks)
    experiment["tasks_completed"] = sum(s.get("task_started") is True and s.get("task_completed") is True for s in observed_new_tasks)
    experiment["tasks_unknown"] = sum(
        type(s.get("task_started")) is not bool or
        (s.get("task_started") is False and not any(
            _d(_d(event).get("observation")).get("task_state") in {"idle", "running", "completed", "failed"}
            for event in _l(s.get("events"))))
        for s in observed_new_tasks)
    experiment["task_count_note"] = "Новая задача учитывается только после подтверждённого запуска. Просмотр прежнего ответа и открытие пустого чата не создают новую задачу."
    experiment["resume_sessions"] = sum(r["mode"] == "resume" for r in executed)
    experiment["regular_sessions"] = sum(r["mode"] == "regular" for r in executed)
    synthesis_coverage = _d(_d(run.get("product_synthesis")).get("coverage")) if synthesis else {}
    if synthesis_coverage.get("sampled"):
        experiment["warnings"].append(
            "Итоговый анализ рассмотрел записи {} из {} пригодных сессий. Метрики рассчитаны по всему прогону; подтверждения рекомендаций относятся к приведённым событиям.".format(
                synthesis_coverage.get("sampled_sessions", 0), synthesis_coverage.get("eligible_sessions", 0)))
    stages = []
    for stage, label in STAGES.items():
        observations = {}
        evidence = []
        for row in rows:
            if not row["eligible"] or not row["observed"]:
                continue
            for item in _l(row["feedback"].get("journey")):
                item = _d(item)
                refs = _refs(item.get("evidence_ids"), row["refs"])
                if stage == "return" and row["mode"] == "first_use":
                    continue
                if item.get("stage") == stage and type(item.get("reached")) is bool and refs:
                    observations[row["persona_id"]] = item["reached"]
                    evidence.extend(refs)
        stages.append({"id": stage, "label": label, "reached": sum(observations.values()), "n": len(observations), "unknown": max(0, len(roster) - len(observations)), "evidence": evidence})
    journey = {"available": any(s["n"] for s in stages), "stages": stages, "note": "Показаны только этапы, которые агент явно оценил со ссылкой на действие. Для каждого этапа указан собственный знаменатель; это не единая воронка конверсии."}
    if priorities:
        insight = _t(synthesis.get("summary")) if synthesis else ""
        if not insight:
            insight = "Сначала: " + priorities[0]["change"].rstrip(".") + "."
    elif not experiment["evaluable_sessions"]:
        insight = "Нет завершённых сессий, пригодных для оценки продукта. Сначала устраните причины остановки теста и повторите проверку."
    else:
        insight = "Цель визита достигнута в {} из {} оцениваемых сессий. Подтверждённых рекомендаций для изменения продукта пока нет.".format(metrics["task_success"], metrics["eligible"])
    return {"experiment": experiment, "audience": audience, "satisfaction": satisfaction, "journey": journey, "recommendations": recommendations, "priorities": priorities, "positives": _positive_findings(rows, synthesis), "insight": insight, "improvement_plan": {"now": priorities, "next": [r for r in recommendations if r["evidence"]][3:]}, "synthesis": {"used": bool(synthesis), "status": _d(run.get("product_synthesis")).get("status", "not_requested"), "coverage": synthesis_coverage}}
