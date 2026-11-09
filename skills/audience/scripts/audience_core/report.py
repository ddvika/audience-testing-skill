"""Deterministic, evidence-linked reports for synthetic Audience sessions.

No language model or network is used here. Numeric forecasts are conditional
scenarios from explicitly supplied external inputs, never agent opinions.
"""

from __future__ import annotations

import html
import json
import math
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


FOCUS = {
    "usability": "Удобство",
    "conversion": "Конверсия",
    "retention": "Возвращение",
    "pricing": "Цена и ценность",
}
STATUS = {
    "completed": "Завершены",
    "abandoned": "Прерваны агентом",
    "blocked": "Заблокированы",
    "error": "Ошибка инфраструктуры",
    "step_limit": "Лимит шагов",
    "budget_limit": "Лимит бюджета",
    "time_limit": "Лимит времени",
    "pending": "Ожидают запуска",
    "running": "Выполняются",
}
MODE = {"first_use": "Первое знакомство", "resume": "Продолжение", "regular": "Повторный визит"}
SUCCESS_LABEL = "Успех задачи · оценка агента по сессии"


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return str(value)


def _json_safe(value):
    """Keep JSON standards-compliant if a Python caller supplies NaN/Infinity.

    These values have no JSON representation; preserve their literal spelling
    as strings in the audit copy instead of emitting invalid JSON tokens.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _escape(value):
    return html.escape(_text(value), quote=True)


def _md(value):
    # Markdown renderers may accept inline HTML, so escape both syntaxes.
    return re.sub(r"([\\`*_{}\[\]()#+!|])", r"\\\1", html.escape(_text(value), quote=True))


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _safe_url(value):
    if not isinstance(value, str) or any(ord(char) < 32 for char in value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        return value
    except ValueError:
        return None


def _link(url, label=None):
    label = url if label is None else label
    safe = _safe_url(url)
    if safe:
        return '<a href="{}" rel="noopener noreferrer">{}</a>'.format(_escape(safe), _escape(label))
    return _escape(label)


def _rating(value):
    number = _number(value)
    return int(number) if number is not None and 0 <= number <= 10 and number.is_integer() else None


def _event_supports_result(event):
    """A cited event must contain evidence and cannot explicitly be an error.

    This validates evidence provenance, not the agent's semantic judgement.
    Reports label the metric accordingly; callers retain the full trace.
    """
    action = event.get("action")
    action_type = action.get("type", action.get("action")) if isinstance(action, dict) else action
    if action_type in ("finish", "feedback"):
        return False  # A concluding assertion alone is not browser evidence.
    result = event.get("result")
    if result is False or (isinstance(result, str) and result.strip().lower() in ("error", "failed", "failure", "blocked")):
        return False
    if isinstance(result, dict):
        if result.get("success") is False or result.get("ok") is False:
            return False
        if result.get("error") or result.get("status") in ("error", "failed", "failure", "blocked"):
            return False
    observation = _dict(event.get("observation"))
    has_observation = any(observation.get(key) for key in ("url", "title", "text", "elements"))
    return bool(has_observation or result)


def _evidence(session, session_index):
    events = [event for event in _list(session.get("events")) if isinstance(event, dict)]
    counts = Counter(_text(event.get("id")) for event in events if event.get("id") is not None)
    return {
        _text(event["id"]): {
            "id": _text(event["id"]),
            "anchor": "session-{}-event-{}".format(session_index + 1, event_index + 1),
            "supports_result": _event_supports_result(event),
        }
        for event_index, event in enumerate(events)
        if event.get("id") is not None and counts[_text(event["id"])] == 1
    }


def _aggregate(sessions):
    rows = []
    for index, session in enumerate(sessions):
        feedback = _dict(session.get("feedback"))
        refs = _evidence(session, index)
        cited = []
        for reference in _list(feedback.get("evidence_ids")):
            evidence = refs.get(_text(reference))
            if evidence and evidence["supports_result"] and evidence not in cited:
                cited.append(evidence)
        status = _text(session.get("status")) or "error"
        observed = any(isinstance(event, dict) and any(_dict(event.get("observation")).get(key) for key in ("text", "elements")) for event in _list(session.get("events")))
        eligible = status in ("completed", "abandoned", "step_limit") and observed
        completed = eligible and status == "completed" and feedback.get("outcome") == "success" and bool(cited)
        rows.append({
            "id": _text(session.get("id")) or str(index + 1),
            "anchor": "session-{}".format(index + 1),
            "persona_id": _text(session.get("persona_id")) or "unknown-persona-" + str(index + 1),
            "model": _text(session.get("model")) or "Не указан",
            "mode": _text(session.get("mode")) or "first_use",
            "status": status,
            "eligible": eligible,
            "task_success": completed,
            "evidence": cited,
            "rating": _rating(feedback.get("rating")) if eligible and cited and feedback.get("outcome") in ("success", "partial", "failure") else None,
            "reported_outcome": feedback.get("outcome"),
        })

    def summary(group):
        total = len(group)
        eligible = sum(row["eligible"] for row in group)
        success = sum(row["task_success"] for row in group)
        latest_ratings = {row["persona_id"]: row["rating"] for row in group if row["rating"] is not None}
        ratings = list(latest_ratings.values())
        n = len(ratings)
        promoters = sum(rating >= 9 for rating in ratings)
        detractors = sum(rating <= 6 for rating in ratings)
        statuses = Counter(row["status"] for row in group)
        return {
            "total": total,
            "eligible": eligible,
            "task_success": success,
            "task_non_success": eligible - success,
            "completion_rate": success / eligible if eligible else None,
            "infrastructure_errors": statuses.get("error", 0),
            "blocked": statuses.get("blocked", 0),
            "budget_limited": statuses.get("budget_limit", 0),
            "time_limited": statuses.get("time_limit", 0),
            "pending": statuses.get("pending", 0),
            "running": statuses.get("running", 0),
            "excluded": total - eligible,
            "infrastructure_error_rate": statuses.get("error", 0) / total if total else None,
            "blocked_rate": statuses.get("blocked", 0) / total if total else None,
            "statuses": dict(statuses),
            "nps_scope": "latest_valid_answer_per_persona",
            "synthetic_nps": 100 * (promoters - detractors) / n if n else None,
            "nps_n": n,
            "nps_promoters": promoters,
            "nps_passives": n - promoters - detractors,
            "nps_detractors": detractors,
        }

    result = summary(rows)
    result["sessions"] = rows
    result["by_model"] = {model: summary([row for row in rows if row["model"] == model]) for model in sorted({row["model"] for row in rows})}
    result["by_mode"] = {mode: summary([row for row in rows if row["mode"] == mode]) for mode in sorted({row["mode"] for row in rows})}
    return result


def _forecast(inputs):
    inputs = _dict(inputs)
    result = {"source": "external_inputs", "scenarios": {}, "assumptions": [], "needed": [], "invalid": []}

    def scalar(key):
        value = _number(inputs.get(key))
        if key in inputs and (value is None or value < 0):
            result["invalid"].append(key)
            return None
        return value

    def bounds(key, maximum=None):
        value = inputs.get(key)
        if key not in inputs:
            return None
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            result["invalid"].append(key)
            return None
        low, high = (_number(item) for item in value)
        if low is None or high is None or low < 0 or low > high or (maximum is not None and high > maximum):
            result["invalid"].append(key)
            return None
        return [low, high]

    visitors = scalar("monthly_visitors")
    spend = scalar("marketing_spend")
    conversion = bounds("paid_conversion", 1)
    return_rate = bounds("return_rate", 1)
    active_days = bounds("active_days", 30)
    mau = bounds("mau")
    scenarios = result["scenarios"]
    currency = inputs.get("currency")
    currency = currency.upper() if isinstance(currency, str) and re.fullmatch(r"[A-Za-z]{3}", currency) else None
    if visitors is not None and conversion is not None:
        paid = [visitors * conversion[0], visitors * conversion[1]]
        scenarios["paying_customers"] = {"low": paid[0], "high": paid[1], "unit": "клиентов / месяц"}
        result["assumptions"].append("Платная конверсия — доля месячных посетителей, ставших новыми платящими клиентами в том же периоде.")
        if spend is not None:
            scenarios["cac"] = {
                "low": spend / paid[1] if paid[1] > 0 else None,
                "high": spend / paid[0] if paid[0] > 0 else None,
                "unit": "{} / клиент".format(currency or "ед. валюты расходов"),
                "undefined_at_zero_conversion": paid[0] == 0,
            }
            result["assumptions"].append("CAC = расходы на маркетинг / новые платящие клиенты; весь указанный бюджет отнесён к их привлечению. При нулевом числе клиентов CAC не определён.")
    if "cac" not in scenarios:
        result["needed"].append("Для CAC: monthly_visitors, marketing_spend и paid_conversion [low, high] из внешних данных.")
    if mau is not None:
        scenarios["mau"] = {"low": mau[0], "high": mau[1], "unit": "активных пользователей / месяц"}
        result["assumptions"].append("MAU — заданный внешний диапазон, а не оценка по синтетическим сессиям.")
    else:
        result["needed"].append("Для MAU: внешний диапазон mau [low, high] с определением активного пользователя.")
    if mau is not None and active_days is not None:
        scenarios["dau"] = {"low": mau[0] * (active_days[0] / 30), "high": mau[1] * (active_days[1] / 30), "unit": "средних активных пользователей / день"}
        result["assumptions"].append("Средний DAU = MAU × среднее число активных дней на пользователя / 30; принят месяц из 30 дней, границы перемножены как независимые допустимые сценарии.")
    else:
        result["needed"].append("Для среднего DAU: mau и active_days [low, high] на пользователя за 30 дней.")
    if return_rate is not None:
        scenarios["return_rate"] = {"low": return_rate[0], "high": return_rate[1], "unit": "доля", "external_assumption": True}
        result["assumptions"].append("Доля возвращений — только заданное внешнее допущение; окно и когорта должны совпадать с вашим измерением. Оно не выведено из намерений агентов.")
    else:
        result["needed"].append("Для возвращений: return_rate [low, high] из аналитики с окном наблюдения и когортой.")
    for key, metric in scenarios.items():
        for bound in ("low", "high"):
            value = metric.get(bound)
            if value is not None and not math.isfinite(value):
                metric[bound] = None
                result["invalid"].append("calculated." + key + "." + bound)
    result["available"] = bool(scenarios)
    return result


def _costs(ledger, plan):
    """Separate provider-confirmed charges from conservative budget accounting."""
    entries = [entry for entry in _list(ledger) if isinstance(entry, dict)]

    def amount(entry, key):
        value = _number(entry.get(key))
        return value if value is not None and value >= 0 else None

    def summarize(rows):
        result = {"confirmed_usd": 0.0, "estimated_usd": 0.0, "unknown_usd": 0.0, "reserved_usd": 0.0, "accounted_usd": 0.0, "entries": len(rows), "unquantified_entries": 0}
        for entry in rows:
            status = entry.get("cost_status")
            cost = amount(entry, "cost_usd")
            accounted = amount(entry, "accounted_usd")
            if status == "not_charged":
                continue
            if accounted is None:
                accounted = cost if status in ("actual", "estimated") else amount(entry, "reserved_usd")
            if accounted is None:
                result["unquantified_entries"] += 1
            else:
                result["accounted_usd"] += accounted
            if status == "actual" and cost is not None:
                result["confirmed_usd"] += cost
            elif status == "estimated":
                result["estimated_usd"] += accounted or 0
            elif status == "reserved":
                result["reserved_usd"] += accounted or 0
            else:
                result["unknown_usd"] += accounted or 0
        return result

    def model_name(entry):
        return _text(entry.get("returned_model") or entry.get("actual_model") or entry.get("requested_model") or entry.get("model")) or "Не указана"

    result = summarize(entries)
    result["available"] = bool(entries)
    result["currency"] = "USD"
    cap = _number(_dict(plan).get("budget_usd"))
    result["budget_usd"] = cap if cap is not None and cap >= 0 else None
    result["budget_remaining_usd"] = max(0, cap - result["accounted_usd"]) if result["budget_usd"] is not None and not result["unquantified_entries"] else None
    result["by_model"] = {model: summarize([entry for entry in entries if model_name(entry) == model]) for model in sorted({model_name(entry) for entry in entries})}
    return result


def _usd(value):
    return "—" if value is None else "${:,.4f}".format(value).replace(",", " ")


def _cost_markdown(cost):
    lines = ["", "## Расходы на исследование", "", "| Статья | USD |", "| --- | --- |"]
    for label, key in [("Подтверждено провайдером", "confirmed_usd"), ("Оценка по резерву", "estimated_usd"), ("Неопределённая стоимость · учтённая сумма", "unknown_usd"), ("Резерв активных запросов", "reserved_usd"), ("Всего учтено в ограничении бюджета", "accounted_usd"), ("Лимит бюджета", "budget_usd"), ("Остаток по учёту бюджета", "budget_remaining_usd")]:
        lines.append("| {} | {} |".format(label, _usd(cost[key])))
    lines.extend(["", "Учтённая сумма включает подтверждённые расходы, оценки и удерживаемые резервы; она не является фактическим счётом провайдера."])
    if not cost["available"]:
        lines.extend(["", "Записей расходов пока нет."])
    if cost["unquantified_entries"]:
        lines.extend(["", "Записей без допустимой суммы: {}. Итог учёта неполон.".format(cost["unquantified_entries"])])
    if cost["by_model"]:
        lines.extend(["", "| Модель | Подтверждено | Оценка | Неопределённо | Резерв | Учтено |", "| --- | --- | --- | --- | --- | --- |"])
        for model, group in cost["by_model"].items():
            lines.append("| {} | {} | {} | {} | {} | {} |".format(_md(model), *(_usd(group[key]) for key in ("confirmed_usd", "estimated_usd", "unknown_usd", "reserved_usd", "accounted_usd"))))
    return lines


def _focus_sections(plan, sessions, metrics):
    requested = plan.get("report_focus", ["usability"])
    requested = [requested] if isinstance(requested, str) else _list(requested)
    sections = []
    for focus in dict.fromkeys(_text(item) for item in requested):
        if focus not in FOCUS:
            continue
        if focus == "usability":
            text = "{} из {} доступных для оценки сессий завершили задачу с ссылкой на след действий. Ошибки, блокировки, лимит бюджета и незавершённые запуски исключены из знаменателя.".format(metrics["task_success"], metrics["eligible"])
        elif focus == "conversion":
            text = "Достижение цели оценивается только по заданной задаче и записям сессии. Это не измерение конверсии реальных посетителей в оплату."
        elif focus == "retention":
            mode_counts = []
            for mode in ("first_use", "resume", "regular"):
                group = metrics["by_mode"].get(mode, {})
                mode_counts.append("{}/{}".format(group.get("eligible", 0), group.get("total", 0)))
            text = "Сессии по режимам (оценено / всего): первое знакомство — {}; продолжение — {}; повторный визит — {}. Намерение агента вернуться — качественная гипотеза, не прогноз удержания.".format(*mode_counts)
        else:
            text = "Оценки цены и ценности берутся из записанных отзывов. Готовность агента платить не измеряет спрос; CAC считается только при наличии внешних допущений."
        sections.append({"focus": focus, "title": FOCUS[focus], "text": text})
    return sections


def _percent(value):
    return "—" if value is None else "{:.0f}%".format(value * 100)


def _fmt(value):
    if value is None:
        return "не определено"
    return "{:,.1f}".format(value).rstrip("0").rstrip(".").replace(",", " ")


def _scenario_label(key):
    return {"paying_customers": "Новые платящие клиенты", "cac": "CAC", "mau": "MAU", "dau": "Средний DAU", "return_rate": "Доля возвращений"}.get(key, key)


def _scenario_range(key, value):
    formatter = _percent if key == "return_rate" else _fmt
    return "{} — {}".format(formatter(value["low"]), formatter(value["high"]))


def _markdown(run, sessions, report):
    exp, satisfaction = report["experiment"], report["satisfaction"]
    metrics, forecast = report["metrics"], report["forecast"]
    lines = ["# Audience · отчёт для команды продукта", "", "Синтетическое тестирование: ниже показаны план и фактически записанные прохождения AI-агентов. Их ответы не заменяют исследование реальных людей.", "", "## Дизайн эксперимента", "", "**Продукт:** " + _md(exp["product"] or exp["url"]), "", "**Задача:** " + _md(exp["task"]), "", "**Аудитория:** " + _md(exp["audience"]), "", "**Почему выбрали её:** " + _md(exp["why"]), "", "| Что считаем | Количество |", "| --- | --- |"]
    for label, key in [("Запланировано агентов", "planned_agents"), ("Агенты с записанными наблюдениями", "executed_agents"), ("Агенты с доступными для оценки результатами", "evaluable_agents"), ("Запланировано визитов", "planned_sessions"), ("Визиты с записанными наблюдениями", "executed_sessions"), ("Визиты с результатом для оценки", "evaluable_sessions"), ("Блокировки", "blocked_sessions"), ("Ошибки инфраструктуры", "failed_sessions"), ("Визиты без записанных наблюдений", "not_executed_sessions")]:
        lines.append("| {} | {} |".format(label, exp[key]))
    lines += ["", _md(exp.get("session_mode_note", "")), "", "Подтверждённо запущено новых задач: {}. Продолжений прежней задачи: {}. Визитов без разметки запуска: {}.".format(exp.get("tasks_started", 0), exp.get("resume_sessions", 0), exp.get("tasks_unknown", 0)), "", _md(exp.get("task_count_note", ""))]
    lines += ["", "Сценарии: " + ", ".join(_md(MODE.get(mode, mode)) for mode in exp["scenario_modes"]) + ".", "", ("Повторный визит моделируется с сохранённым контекстом. Между визитами не проходили реальные семь или тридцать дней." if any(m in exp["scenario_modes"] for m in ("resume", "regular")) else "Повторные визиты в этот прогон не входили; удержание не измерялось."), "", "| Группа | Запланировано / есть наблюдения | Зачем её выбрали |", "| --- | --- | --- |"]
    for group in report["audience"]:
        lines.append("| {} | {} / {} | {} |".format(_md(group["label"]), group["planned"], group["executed"], _md(group["why"])))
    lines += ["", "## Главный вывод", "", _md(report["insight"]), "", ("## Что изменить в следующем релизе" if report["priorities"] else "## Есть ли основания менять продукт"), ""]
    def recommendation(rec):
        return ["### {}. {}".format(rec["rank"], _md(rec["change"])), "", "**Что увидели:** " + _md(rec["observed"]), "", "**Кого затронуло:** {} агентов; {} сессий со ссылками на действия.".format(rec["affected_count"], len(rec["session_ids"])), "", "**Что сделать:** " + _md(rec["proposed"]), "", "**Что проверить:** " + _md(rec["expected_metric"]), "", _md(rec["how_to_verify"]), "", "Основание: " + (", ".join("[{}](#{})".format(_md(ref["id"]), ref["anchor"]) for ref in rec["evidence"]) or "нет допустимых ссылок на события; это гипотеза"), ""]
    for rec in report["priorities"]:
        lines.extend(recommendation(rec))
    if not report["priorities"]:
        lines += ["Подтверждённых изменений для плана релиза пока нет. Доступные наблюдения и ограничения приведены ниже.", ""]
    lines += ["## Кому удалось решить задачу", "", "| Группа | Первая задача: успех / оценено | Новая задача при повторном визите: успех / оценено | Продолжение прежней задачи: успех / оценено | Выбрали бы снова: да / ответили |", "| --- | --- | --- | --- | --- |"]
    for group in report["audience"]:
        first, repeat, resumed, choice = group["first_use"], group["repeat"], group["resume"], group["choose_again"]
        lines.append("| {} | {} / {} | {} / {} | {} / {} | {} / {} |".format(_md(group["label"]), first["success"], first["n"], repeat["success"], repeat["n"], resumed["success"], resumed["n"], choice["yes"], choice["n"]))
    lines += ["", (("Успех показан после проверки результата по событиям; исходные оценки и поправки проверяющего сохранены в аудите. " if run.get("quality_review") else "Успех — оценка агента с допустимой ссылкой на наблюдение. ") + "Из знаменателя исключены блокировки, технические ошибки, лимиты бюджета и незаконченные запуски. Лимит шагов считается незавершённой задачей. Ноль ответов не означает нулевую удовлетворённость."), "", "## Понятность интерфейса и путь к результату", ""]
    for key, label in [("purpose_clear", "Поняли назначение продукта"), ("next_step_clear", "Поняли следующий шаг"), ("result_clear", "Поняли результат действия")]:
        item = satisfaction["assessment"][key]
        lines.append("- {}: {} из {} ответивших; нет оценки у {} агентов.".format(label, item["yes"], item["n"], item["unknown"]))
    if report["journey"]["available"]:
        lines += ["", "| Этап | Достигли / оценили | Без оценки |", "| --- | --- | --- |"]
        for stage in report["journey"]["stages"]:
            lines.append("| {} | {} / {} | {} |".format(_md(stage["label"]), stage["reached"], stage["n"], stage["unknown"]))
        lines += ["", report["journey"]["note"]]
    else:
        lines += ["", "Достижение отдельных этапов не было оценено со ссылками на действия. Воронка по этим данным не строится."]
    lines += ["", "## Удовлетворённость и впечатления", "", satisfaction["note"]]
    nps, csat, choice = satisfaction["nps"], satisfaction["csat"], satisfaction["return_intent"]
    lines += ["", "- Синтетический NPS: {}; n={}.".format(_fmt(nps["value"]), nps["n"]), "- CSAT: {} из {} поставили четыре или пять; средняя оценка {} из пяти.".format(csat["satisfied"], csat["n"], _fmt(csat["mean"])), "- Выбрали бы продукт снова: {} из {} ответивших.".format(choice["yes"], choice["n"]), "", "NPS = доля оценок девять–десять минус доля оценок ноль–шесть. Оценка рекомендации отделена от удовлетворённости; намерение вернуться отделено от фактического удержания.", "", "### Что понравилось", ""]
    for item in report["positives"]:
        lines.append("- {} · {} агентов. {}".format(_md(item["text"]), item["count"], ", ".join("[{}](#{})".format(_md(r["id"]), r["anchor"]) for r in item["evidence"])))
    if not report["positives"]:
        lines.append("Положительные отзывы с подтверждёнными ссылками на действия не записаны.")
    lines += ["", "## Прогноз продуктовых метрик", "", "Условные расчёты из переданных внешних допущений. Они не предсказывают причинный эффект изменений по отзывам агентов.", "", "Источник: " + _md(forecast["source_info"]["source"])]
    if not forecast["available"]:
        lines += ["", "Числовой прогноз пока недоступен: нужны внешние данные."]
    for key, value in forecast["scenarios"].items():
        lines.append("- **{}:** {} {}".format(_scenario_label(key), _scenario_range(key, value), _md(value["unit"])))
    for scenario in ([forecast["baseline"]] if forecast["baseline"] else []) + forecast["named_scenarios"]:
        lines += ["", "### " + _md(scenario["label"]), "", "| Метрика | Значение |", "| --- | --- |"]
        for metric in scenario["metrics"].values():
            value = _percent(metric["value"]) if metric["unit"] == "доля" else _fmt(metric["value"])
            lines.append("| {} | {} {} |".format(_md(metric["label"]), value, _md(metric["unit"])))
    for heading, values in [("Допущения", forecast["assumptions"]), ("Какие данные нужны", forecast["needed"])]:
        if values:
            lines += ["", "### " + heading, ""] + ["- " + _md(value) for value in values]
    if forecast["invalid"]:
        lines += ["", "Некорректные входные поля исключены: " + ", ".join(_md(value) for value in forecast["invalid"])]
    lines += ["", "## План проверки изменений", "", "Сначала повторите выбранные задачи с тем же составом групп и моделями. Сравните долю успешных задач, понятность интерфейса и причины остановки. Затем проверьте эффект на реальных пользователях."]
    if report["improvement_plan"]["next"]:
        lines += ["", "### После основных изменений", ""]
        for rec in report["improvement_plan"]["next"]:
            lines.extend(recommendation(rec))
    hypotheses = [rec for rec in report["recommendations"] if not rec["evidence"]]
    if hypotheses:
        lines += ["", "### Гипотезы без подтверждения", ""]
        for rec in hypotheses:
            lines.append("- " + _md(rec["change"]))
    lines.extend(_cost_markdown(report["costs"]))
    lines += ["", "## Статусы и модели", "", "| Текущий статус | Сессии |", "| --- | --- |"]
    for status, count in metrics["statuses"].items():
        lines.append("| {} | {} |".format(_md(STATUS.get(status, status)), count))
    lines += ["", "| Модель | Успешно / оценено | Ошибки / всего | Блокировки / всего |", "| --- | --- | --- | --- |"]
    for model, group in metrics["by_model"].items():
        lines.append("| {} | {} / {} | {} / {} | {} / {} |".format(_md(model), group["task_success"], group["eligible"], group["infrastructure_errors"], group["total"], group["blocked"], group["total"]))
    lines += ["", "Сравнение моделей описательное: состав групп и задачи могут различаться. Несколько агентов одной модели не являются независимой выборкой людей."]
    if exp["warnings"]:
        lines += ["", "Ограничения запуска:", ""] + ["- " + _md(value) for value in exp["warnings"]]
    lines += ["", "## Записи сессий", "", "Полные исходные записи также сохранены в report.json. Текст ниже передан без содержательных дополнений."]
    for index, session in enumerate(sessions):
        row = metrics["sessions"][index]
        lines += ["", '<a id="{}"></a>'.format(row["anchor"]), "", "### Сессия " + _md(row["id"]), "", "Модель: {} · Режим: {} · Статус: {}".format(_md(row["model"]), _md(MODE.get(row["mode"], row["mode"])), _md(STATUS.get(row["status"], row["status"]))), "", "**Отзыв:**", "", _md(_text(session.get("feedback", {})))]
        for event_index, event in enumerate(item for item in _list(session.get("events")) if isinstance(item, dict)):
            anchor = "session-{}-event-{}".format(index + 1, event_index + 1)
            lines += ["", '<a id="{}"></a>'.format(anchor), "", "#### Событие " + _md(event.get("id", event_index + 1)), "", _md(_text(event))]
    return "\n".join(lines) + "\n"


def build_report(run: dict, output_dir: Path) -> dict:
    """Write report.json, report.md and report.html; return their absolute paths.

    ``feedback.evidence_ids`` must cite unique event IDs in the same session.
    Optional ``forecast_inputs`` contains external assumptions only. Rate
    ranges use fractions (0..1), and active_days refers to a 30-day month.
    """
    if not isinstance(run, dict):
        raise TypeError("run must be a dict")
    from .engine import redact
    run = redact(run)  # Copy; never mutate caller evidence or persist accidental secrets.
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sessions = [item for item in _list(run.get("sessions")) if isinstance(item, dict)]
    metrics = _aggregate(sessions)
    report = {
        "schema_version": 2,
        "synthetic": True,
        "metrics": metrics,
        "costs": _costs(run.get("ledger"), run.get("plan")),
        "forecast": _forecast({} if any(key in _dict(run.get("forecast_inputs")) for key in ("baseline", "scenarios")) else run.get("forecast_inputs")),
        "focus": _focus_sections(_dict(run.get("plan")), sessions, metrics),
        "run": run,
    }
    from .analysis import analyze
    from .forecast import extend_forecast
    report.update(analyze(run, sessions, metrics))
    report["forecast"] = extend_forecast(run.get("forecast_inputs"), report["forecast"])
    paths = {extension: str((output_dir / ("report." + extension)).resolve()) for extension in ("json", "md", "html")}
    # Keep the complete recorded run for audit/replay; do not invent trace rows.
    Path(paths["json"]).write_text(json.dumps(_json_safe(report), ensure_ascii=False, indent=2, default=str, allow_nan=False), encoding="utf-8")
    Path(paths["md"]).write_text(_markdown(run, sessions, report), encoding="utf-8")
    from .report_view import render_html
    Path(paths["html"]).write_text(render_html(_json_safe(run), _json_safe(sessions), _json_safe(report)), encoding="utf-8")
    return paths
