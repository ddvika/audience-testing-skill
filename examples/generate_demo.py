#!/usr/bin/env python3
"""Build Audience's public example from deterministic fictional data.

No product is contacted and no model/API key is used. Every persona, response,
event and assessment below is authored fixture data, not an experiment result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def fixture():
    model = "fixture/scripted-persona"
    groups = [
        {"id": "quick", "name": "Выбрать быстро", "selection_reason": "Вымышленные покупатели с ограниченным временем: проверяем короткий путь до понятного выбора."},
        {"id": "compare", "name": "Сравнить условия", "selection_reason": "Вымышленные покупатели с фиксированным бюджетом: проверяем итоговую цену и условия билета."},
        {"id": "return", "name": "Продолжить выбор", "selection_reason": "Вымышленные покупатели, которые выбирают вместе с другим человеком: проверяем сохранение выбора и возврат к нему."},
    ]
    definitions = [
        ("ira", "Ира", "quick", "mobile", "Выбрать два билета на вечерний концерт за несколько минут.", "success", 4, 8, True),
        ("sasha", "Саша", "quick", "desktop", "Выбрать два соседних места и понять, готовы ли они к оплате.", "partial", 2, 5, False),
        ("dasha", "Даша", "compare", "mobile", "Сравнить варианты и уложиться в общий бюджет на два билета.", "partial", 2, 6, False),
        ("maksim", "Максим", "compare", "desktop", "Проверить полную стоимость выбранных билетов до оплаты.", "success", 4, 8, True),
        ("lena", "Лена", "return", "mobile", "Выбрать места, обсудить их с другом и вернуться к выбору.", "success", 5, 9, True),
        ("oleg", "Олег", "return", "desktop", "Сравнить два концерта и продолжить с сохранённой подборки.", "success", 4, 9, True),
    ]
    personas = []
    for pid, name, group, device, goal, *_ in definitions:
        g = next(g for g in groups if g["id"] == group)
        personas.append({"id": pid, "name": name, "group_id": group, "segment": g["name"], "selection_reason": g["selection_reason"],
            "goal": goal, "device": device, "model": model, "experience": "Вымышленный профиль для демонстрации отчёта",
            "scenario_modes": ["first_use", "resume"] if group == "return" else ["first_use"],
            "scenario_goals": {"first_use": goal, "resume": "Продолжить сохранённый выбор без повторного поиска."},
            "success_criteria": ["Событие и места выбраны", "Понятна итоговая сумма", "Понятен следующий шаг; покупка не выполняется"]})
    prompts = {
        "ira": "Найди два билета на небольшой джазовый концерт в субботу после 19:00. Хочу быстро выбрать, до 6 000 ₽ за двоих.",
        "sasha": "Хочу два соседних места на концерт «Вечер джаза». Выбери ряд поближе к сцене и покажи, что выбрано. Пока без оплаты.",
        "dasha": "Подбери два билета на концерт в субботу. Общий бюджет — 5 000 ₽, включая все сборы. Покажи итоговую цену сразу.",
        "maksim": "Сравни два варианта мест на «Вечер джаза». Мне важны итоговая цена за двоих и условия возврата, до оплаты.",
        "lena": "Подбери два места на джазовый концерт и сохрани выбор, чтобы я могла обсудить его и вернуться позже.",
        "oleg": "Сравни камерный джаз и фортепианный концерт в субботу. Сохрани оба варианта, решение приму позже.",
    }
    replies = {
        "ira": "Подходит «Вечер джаза», суббота, 19:30. Небольшой зал, 120 мест.\nДва соседних места: ряд 5, места 7 и 8. Цена билетов — 4 400 ₽. На следующем шаге сервисный сбор — 400 ₽. Итого — 4 800 ₽.\nВыбраны: два билета, ряд 5, места 7 и 8. Следующий шаг — проверить заказ. Оплата ещё не выполнена.",
        "sasha": "Готово.",
        "dasha": "«Вечер джаза», суббота, 19:30. Два билета по 2 400 ₽ — 4 800 ₽.\nНа шаге проверки заказа добавлен сервисный сбор 480 ₽. Итого — 5 280 ₽. Это больше указанного общего бюджета.\nВыбор можно изменить, вернувшись к списку мест.",
        "maksim": "Вариант А: ряд 5 — 4 400 ₽ за два билета, сбор 400 ₽, итого 4 800 ₽.\nВариант Б: ряд 3 — 5 200 ₽ за два билета, сбор 400 ₽, итого 5 600 ₽.\nПолная сумма отображается на проверке заказа; в списке указана только цена билетов. Оба варианта допускают возврат по условиям организатора, которые открываются отдельной ссылкой.\nВыбран вариант А. Следующий шаг — проверить заказ; оплата не выполнялась.",
        "lena": "Выбор сохранён: «Вечер джаза», суббота, 19:30, ряд 5, места 9 и 10.\nДва билета — 4 400 ₽, сервисный сбор — 400 ₽. Итого — 4 800 ₽.\nВернуться к выбору можно в разделе «Сохранённое». Оплата не выполнена; наличие мест может измениться.",
        "oleg": "Подборка сохранена.",
    }
    summaries = {
        "ira": "Выбор сделан быстро, но полная сумма появилась только после выбора мест.",
        "sasha": "После выбора мест непонятно, сохранились ли они и как продолжить.",
        "dasha": "Сервисный сбор появился поздно; итог превысил заданный бюджет.",
        "maksim": "Варианты удалось сравнить, но итоговая цена потребовала дополнительного шага.",
        "lena": "Выбор сохранён; понятны итоговая сумма и способ вернуться.",
        "oleg": "Подборка сохранена, но короткое «Готово» не объясняет, где она находится.",
    }
    sessions = []
    for pid, name, group, device, goal, outcome, csat, rating, returns in definitions:
        sid = pid + "-first"
        price_issue = pid in {"ira", "dasha", "maksim"}
        final_id = sid + (":e3" if price_issue else ":e2")
        refs = [final_id]
        visible_result = replies[pid]
        if pid == "sasha":
            visible_result += "\nСобытия\nВечер джаза · суббота · 19:30\nФортепианный вечер · суббота · 20:00\nНайти событие"
        elif pid == "oleg":
            visible_result += "\nСобытия\nВечер джаза · от 2 200 ₽\nФортепианный вечер · от 1 800 ₽\nСохранённое"
        records = [
            {"id": sid + ":e1", "action": {"type": "click", "target": "send"}, "observation": {"url": "https://seatly.example/chat/" + pid, "title": "Seatly · демонстрационный продукт", "text": prompts[pid], "task_state": "running", "viewport": {"width": 390 if device == "mobile" else 1360, "height": 900}, "elements": [{"id": "send", "role": "button", "name": "Отправить"}]}, "result": {"status": "ok", "task_started": True}},
            {"id": final_id, "action": {"type": "observe"}, "observation": {"url": "https://seatly.example/chat/" + pid, "title": "Результат выбора", "text": visible_result, "task_state": "completed", "elements": []}, "result": {"status": "ok", "task_completed": True}},
        ]
        if price_issue:
            records.insert(1, {"id": sid + ":e2", "action": {"type": "click", "target": "choose-seats"},
                "observation": {"url": "https://seatly.example/chat/" + pid, "title": "Места на концерт", "text": "Вечер джаза\nДва билета — " + ("4 800 ₽" if pid == "dasha" else "4 400 ₽") + "\nВыбрать места",
                    "elements": [{"id": "choose-seats", "role": "button", "name": "Выбрать места"}]}, "result": {"status": "ok"}})
        recs = []
        if pid in {"ira", "dasha", "maksim"}:
            recs.append({"issue_key": "upfront_total", "scope": "product", "stage": "action", "change": "Показывать полную цену до выбора мест.",
                "reason": "Поздний сбор заставляет перепроверять бюджет или начинать выбор заново.",
                "observed": "В списке видна цена билетов, а сбор добавляется только на проверке заказа.",
                "proposed": "Показывать стоимость за нужное число билетов вместе со сбором и фильтровать по итоговой сумме.",
                "expected_metric": "Доля сценариев, где выбор укладывается в общий бюджет.",
                "how_to_verify": "Повторить выбор с фиксированным бюджетом. Сумма в списке и перед оплатой должна совпадать.", "evidence_ids": refs})
        if pid in {"sasha", "oleg"}:
            recs.append({"issue_key": "selection_confirmation", "scope": "product", "stage": "result", "change": "После выбора показывать итог и следующий шаг.",
                "reason": "Без итога пользователь не понимает, сохранился ли результат и где его продолжить.",
                "observed": "После действия нет заметной карточки сохранённого выбора; приходится искать продолжение.",
                "proposed": "Оставлять на экране выбранное событие, места и сумму; показывать «Продолжить» и «Изменить выбор».",
                "expected_metric": "Доля пользователей, правильно объяснивших результат действия.",
                "how_to_verify": "После выбора проверить, может ли агент назвать выбранное событие и продолжить без повторного поиска.", "evidence_ids": refs})
        sessions.append({"id": sid, "persona_id": pid, "mode": "first_use", "model": model, "status": "completed", "events": records,
            "task_started": True, "task_completed": True, "task_started_event_id": sid + ":e1", "task_completed_event_id": final_id,
            "conversation_url": "https://seatly.example/chat/" + pid,
            "transcript": {"source": "authored_demo_fixture", "capture_status": "complete", "product_name": "Seatly", "capture_note": "Авторский пример. Все сообщения, действия и оценки вымышлены; реальный продукт не тестировался.",
                "messages": [{"role": "user", "text": prompts[pid], "event_ids": [sid + ":e1"]}, {"role": "assistant", "text": replies[pid], "event_ids": refs}]},
            "feedback": {"outcome": outcome, "rating": rating, "return_intent": returns, "summary": summaries[pid], "evidence_ids": refs,
                "assessment": {"satisfaction": csat, "effort": 2 if outcome == "success" else 4, "purpose_clear": True, "next_step_clear": pid != "sasha", "result_clear": pid not in {"sasha", "oleg"}, "evidence_ids": refs},
                "journey": [{"stage": stage, "reached": outcome == "success" if stage == "result" else True, "note": summaries[pid], "evidence_ids": refs} for stage in ["entry", "start", "action", "result"]],
                "likes": ["События удобно сравнивать в одном месте."] if outcome == "success" else [],
                "dislikes": [r["observed"] for r in recs], "recommendations": recs}})
    for pid in ["lena", "oleg"]:
        sid = pid + "-resume"
        request = "Продолжим сохранённый выбор. Покажи, что было выбрано, и как перейти к проверке заказа. Пока без оплаты."
        answer = ("Сохранённый выбор открыт: «Вечер джаза», суббота, 19:30. "
            + ("Ряд 5, места 9 и 10. Итого — 4 800 ₽ со сбором. " if pid == "lena" else "В подборке также остался «Фортепианный вечер». Можно выбрать места на любом из событий. ")
            + "Следующий шаг — «Проверить заказ». Оплата не выполнялась.")
        refs = [sid + ":e2"]
        sessions.append({"id": sid, "persona_id": pid, "mode": "resume", "model": model, "status": "completed", "task_started": False, "task_completed": True,
            "conversation_url": "https://seatly.example/chat/" + pid,
            "events": [{"id": sid + ":e1", "action": {"type": "click", "target": "saved"}, "observation": {"url": "https://seatly.example/chat/" + pid, "text": request, "title": "Сохранённое", "elements": []}, "result": {"status": "ok"}},
                {"id": sid + ":e2", "action": {"type": "observe"}, "observation": {"url": "https://seatly.example/chat/" + pid, "text": answer, "title": "Продолжение выбора", "elements": []}, "result": {"status": "ok"}}],
            "transcript": {"source": "authored_demo_fixture", "capture_status": "complete", "product_name": "Seatly", "capture_note": "Авторская демонстрация продолжения; между визитами не проходили реальные дни.", "messages": [{"role": "user", "text": request, "event_ids": [sid + ":e1"]}, {"role": "assistant", "text": answer, "event_ids": refs}]},
            "feedback": {"outcome": "success", "rating": 9, "return_intent": True, "summary": "Сохранённый выбор найден; повторный поиск не понадобился.", "evidence_ids": refs,
                "assessment": {"satisfaction": 5, "effort": 1, "purpose_clear": True, "next_step_clear": True, "result_clear": True, "evidence_ids": refs},
                "likes": ["Сохранённый выбор помогает продолжить без повторного поиска."], "dislikes": [], "recommendations": [],
                "journey": [{"stage": "return", "reached": True, "note": "Выбор восстановлен.", "evidence_ids": refs}]}})
    run = {"schema_version": "1.0", "id": "audience-public-demo", "created_at": "2026-11-09T00:00:00Z", "demo": True, "synthetic_fixture": True,
        "plan": {"demo": True, "url": "https://seatly.example", "product_summary": "Seatly · вымышленный сервис выбора билетов",
            "task": "Проверить путь от поиска события до понятного выбора билетов, без покупки. Это полностью вымышленный пример отчёта.",
            "audience": "Вымышленные покупатели билетов с разными задачами и ограничениями.", "budget_usd": 0, "scenario_modes": ["first_use", "resume"],
            "report_focus": ["usability", "conversion", "retention"], "personas": personas,
            "experiment_design": {"groups": groups, "research_question": "Понятны ли итоговая цена, результат выбора и способ вернуться к нему?"},
            "assumptions": ["Все данные написаны вручную для демонстрации структуры отчёта; они не получены от людей, моделей или реального сайта.",
                "Шесть вымышленных персон, шесть первых визитов и два моделируемых продолжения. Повторные визиты не являются измерением удержания.",
                "fixture/scripted-persona — условное имя, а не доступная модель OpenRouter. Платных вызовов нет.",
                "seatly.example — зарезервированный демонстрационный адрес. Переходы по внешним ссылкам не нужны для чтения отчёта."]},
        "sessions": sessions, "ledger": [], "warnings": ["DEMO: authored fixture, no live product or model calls."],
        "runtime": {"session_mode": "isolated", "demo": True}}
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    repo = Path(__file__).resolve().parents[1]
    parser.add_argument("--skill-root", type=Path, default=repo / "skills" / "audience")
    parser.add_argument("--output", type=Path, default=repo / "examples")
    args = parser.parse_args()
    sys.path.insert(0, str(args.skill_root.resolve() / "scripts"))
    from audience_core.report import build_report
    from audience_core.synthesis import source_fingerprint, validate_synthesis, _collect
    run = fixture()
    _, allowed = _collect(run)
    recs = []
    for key in ["upfront_total", "selection_confirmation"]:
        entries = [rec for session in run["sessions"] for rec in session["feedback"]["recommendations"] if rec["issue_key"] == key]
        rec = {**entries[0], "evidence_ids": [eid for item in entries for eid in item["evidence_ids"]], "hypothesis": True}
        recs.append(rec)
    raw = {"summary": "Покажите полную цену и понятный итог выбора.", "summary_evidence_ids": ["dasha-first:e3", "sasha-first:e2"],
        "recommendations": recs, "positives": [{"title": "Сохранённый выбор помогает продолжить без повторного поиска.", "description": "В вымышленном сценарии подборка доступна при возвращении.", "evidence_ids": ["lena-resume:e2", "oleg-resume:e2"]}],
        "caveats": ["Полностью вымышленная демонстрация; цифры не характеризуют реальный продукт."]}
    run["product_synthesis"] = {"status": "completed", "source": "authored_demo_fixture", "model": None, "fingerprint": source_fingerprint(run),
        "coverage": {"eligible_sessions": len(run["sessions"]), "sampled_sessions": len(run["sessions"]), "sampled": False, "evidence_ids": list(allowed)}, **validate_synthesis(raw, allowed)}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "demo-run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths = build_report(run, args.output)
    report = json.loads(Path(paths["json"]).read_text())
    assert report["experiment"]["executed_agents"] == 6
    assert report["metrics"]["eligible"] == 8
    assert report["metrics"]["task_success"] == 6
    assert len(report["priorities"]) == 2
    print(json.dumps({"demo": True, "agents": 6, "visits": 8, "successful_visit_goals": 6, "priorities": 2, "html": paths["html"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
