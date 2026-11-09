"""Conditional metric arithmetic. All numbers must be supplied by the caller."""
from __future__ import annotations
import math

FIELDS = {"monthly_visitors", "registration_rate", "activation_rate", "retention_cohort_size", "d7_retention", "d30_retention", "paid_conversion", "marketing_spend", "mau", "active_days", "currency", "cohort_definition", "active_definition"}
RATE_FIELDS = {"registration_rate", "activation_rate", "d7_retention", "d30_retention", "paid_conversion"}
LABELS = {"activated_users": "Получили первый полезный результат", "activation_rate": "Доля посетителей с первым результатом", "d7_retention": "Доля вернувшихся на седьмой день", "d7_returners": "Вернулись на седьмой день", "d30_retention": "Доля вернувшихся на тридцатый день", "d30_returners": "Вернулись на тридцатый день", "paying_customers": "Новые платящие клиенты", "cac": "CAC", "mau": "MAU", "dau": "Средний DAU", "stickiness": "DAU / MAU"}


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _calculate(name, label, values, provenance, source):
    data, invalid, assumptions, metrics = {}, [], [], {}
    for key in FIELDS - {"currency", "cohort_definition", "active_definition"}:
        if key not in values:
            continue
        number = _number(values[key])
        if number is None or (key in RATE_FIELDS and number > 1) or (key == "active_days" and number > 30):
            invalid.append(key)
        else:
            data[key] = number
    def add(key, value, unit):
        if value is not None and _number(value) is None:
            invalid.append("calculated." + key)
            value = None
        metrics[key] = {"value": value, "unit": unit, "label": LABELS[key]}
    currency = values.get("currency")
    currency = currency.upper() if isinstance(currency, str) and len(currency) == 3 and currency.isalpha() else "ед. валюты расходов"
    if all(key in data for key in ("monthly_visitors", "registration_rate", "activation_rate")):
        rate = data["registration_rate"] * data["activation_rate"]
        add("activation_rate", rate, "доля")
        add("activated_users", data["monthly_visitors"] * rate, "пользователей / месяц")
        assumptions.append("Первый результат = посетители × доля зарегистрировавшихся × доля зарегистрировавшихся, получивших первый результат. Обе доли заданы извне.")
    cohort = data.get("retention_cohort_size")
    if "retention_cohort_size" not in values and "activated_users" in metrics:
        cohort = metrics["activated_users"]["value"]
        assumptions.append("Для возвращений взята когорта новых пользователей, получивших первый результат; это не весь MAU.")
    if isinstance(values.get("cohort_definition"), str) and values["cohort_definition"].strip():
        assumptions.append("Когорта: " + values["cohort_definition"].strip())
    for day in (7, 30):
        rate_key = f"d{day}_retention"
        if rate_key in data:
            add(rate_key, data[rate_key], "доля")
            if cohort is not None:
                add(f"d{day}_returners", cohort * data[rate_key], "пользователей в когорте")
            assumptions.append(f"D{day} — внешнее допущение о доле когорты, вернувшейся именно на день {day}; не ответ агента о желании вернуться.")
    if "monthly_visitors" in data and "paid_conversion" in data:
        paid = data["monthly_visitors"] * data["paid_conversion"]
        add("paying_customers", paid, "новых клиентов / месяц")
        assumptions.append("Платная конверсия — доля месячных посетителей, ставших новыми платящими клиентами за тот же период.")
        if "marketing_spend" in data:
            add("cac", data["marketing_spend"] / paid if paid else None, currency + " / клиент")
            assumptions.append("CAC = расходы на привлечение / новые платящие клиенты; расходы целиком отнесены к этой когорте. При нуле клиентов CAC не определён.")
    if "mau" in data:
        add("mau", data["mau"], "активных пользователей / месяц")
        assumptions.append("MAU задан извне. Он не выводится из доли вернувшихся AI-агентов.")
        if "active_days" in data:
            dau = data["mau"] * (data["active_days"] / 30)
            add("dau", dau, "активных пользователей / день")
            add("stickiness", dau / data["mau"] if data["mau"] else None, "доля")
            assumptions.append("Средний DAU = MAU × средние активные дни одного пользователя / тридцать дней. DAU / MAU не определён при нулевом MAU.")
    if isinstance(values.get("active_definition"), str) and values["active_definition"].strip():
        assumptions.append("Активный пользователь: " + values["active_definition"].strip())
    return {"name": name, "label": label, "metrics": metrics, "inputs": values, "provenance": provenance, "source": source, "invalid": invalid, "assumptions": assumptions}


def extend_forecast(inputs, legacy):
    inputs = inputs if isinstance(inputs, dict) else {}
    result = dict(legacy)
    result.update(baseline=None, named_scenarios=[], comparison=[], source_info={"source": inputs.get("source") if isinstance(inputs.get("source"), str) else "Переданные внешние допущения; источник не описан", "supplied": bool(inputs)})
    # Legacy range inputs retain their original arithmetic; named scenarios are
    # additional explicit alternatives, never auto-generated optimistic values.
    if "baseline" not in inputs and "scenarios" not in inputs:
        return result
    common = {key: inputs[key] for key in FIELDS if key in inputs}
    source = result["source_info"]["source"]
    def scenario(raw, index, baseline=False):
        if not isinstance(raw, dict):
            return None
        local = raw.get("assumptions") if isinstance(raw.get("assumptions"), dict) else raw
        values = {**common, **{key: local[key] for key in FIELDS if key in local}}
        name = str(raw.get("name") or ("baseline" if baseline else "scenario-" + str(index)))[:80]
        label = str(raw.get("label") or ("До изменений" if baseline else name))[:120]
        prefix = "baseline" if baseline else f"scenarios[{index}]"
        local_prefix = prefix + (".assumptions" if isinstance(raw.get("assumptions"), dict) else "")
        provenance = {key: local_prefix + "." + key if key in local else key for key in values}
        return _calculate(name, label, values, provenance, source)
    if "baseline" in inputs:
        result["baseline"] = scenario(inputs["baseline"], 0, True)
        if result["baseline"] is None:
            result["invalid"].append("baseline")
    raw_scenarios = inputs.get("scenarios", [])
    if isinstance(raw_scenarios, dict):
        raw_scenarios = [{**v, "name": k} if isinstance(v, dict) else v for k, v in raw_scenarios.items()]
    if not isinstance(raw_scenarios, list):
        result["invalid"].append("scenarios")
        raw_scenarios = []
    seen = set()
    for index, raw in enumerate(raw_scenarios[:20]):
        item = scenario(raw, index)
        if item is None or item["name"] in seen:
            result["invalid"].append(f"scenarios[{index}]")
            continue
        seen.add(item["name"])
        result["named_scenarios"].append(item)
    baseline = result["baseline"]
    if baseline:
        for item in result["named_scenarios"]:
            changes = {}
            for key in baseline["metrics"].keys() & item["metrics"].keys():
                if baseline["metrics"][key]["unit"] != item["metrics"][key]["unit"]:
                    result["assumptions"].append("Изменение " + LABELS[key] + " не рассчитано: единицы или валюты до и после различаются. Нужен явный пересчёт в одну единицу.")
                    continue
                before, after = baseline["metrics"][key]["value"], item["metrics"][key]["value"]
                valid = before is not None and after is not None
                delta = after - before if valid else None
                relative = delta / before if valid and before else None
                if relative is not None and not math.isfinite(relative):
                    relative = None
                changes[key] = {"before": before, "after": after, "delta": delta, "relative_change": relative, "unit": item["metrics"][key]["unit"]}
            result["comparison"].append({"name": item["name"], "label": item["label"], "metrics": changes})
    for item in ([baseline] if baseline else []) + result["named_scenarios"]:
        result["invalid"].extend(f"{item['name']}.{key}" for key in item["invalid"])
        result["assumptions"].extend(x for x in item["assumptions"] if x not in result["assumptions"])
    result["available"] = bool(result["scenarios"] or (baseline and baseline["metrics"]) or any(s["metrics"] for s in result["named_scenarios"]))
    if result["named_scenarios"] or baseline:
        all_metrics = set().union(*(set(item["metrics"]) for item in ([baseline] if baseline else []) + result["named_scenarios"]))
        needed = []
        needs = [("activated_users", "Для первого результата: месячные посетители, доля регистрации и доля зарегистрировавшихся, получивших первый результат."), ("d7_returners", "Для D7: размер и определение когорты, внешнее допущение о возвращении на седьмой день."), ("d30_returners", "Для D30: размер и определение когорты, внешнее допущение о возвращении на тридцатый день."), ("cac", "Для CAC: посетители, платная конверсия и расходы на привлечение за один период."), ("mau", "Для MAU: число активных пользователей за месяц и определение активности."), ("dau", "Для DAU: MAU и среднее число активных дней за тридцатидневный месяц.")]
        for key, explanation in needs:
            if key not in all_metrics:
                needed.append(explanation)
        result["needed"] = needed
    return result
