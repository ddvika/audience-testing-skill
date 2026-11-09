"""Offline editorial HTML report. All values come from computed study records.

The renderer has no model calls, dependencies, web requests, or demo defaults.
Literal transcripts and cited observations are readable in the HTML appendix.
The complete raw trace, including uncited events, also stays in report.json.
"""
from __future__ import annotations

import html
import json
import math
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ASSETS = Path(__file__).with_name('report_assets')
STAGES = {'entry': 'Первое впечатление', 'start': 'Начало задачи', 'action': 'Выполнение', 'result': 'Получение результата', 'return': 'Повторное использование'}
MODES = {'first_use': 'Первый визит', 'resume': 'Продолжение задачи', 'regular': 'Повторный визит'}
STATUSES = {'pending': 'Не запускалась', 'running': 'В работе', 'completed': 'Цель визита достигнута', 'abandoned': 'Задача не завершена', 'blocked': 'Доступ ограничен', 'error': 'Ошибка выполнения', 'step_limit': 'Лимит шагов', 'budget_limit': 'Лимит бюджета', 'time_limit': 'Лимит времени'}
DEVICES = {'desktop': 'Компьютер', 'mobile': 'Телефон'}
SCOPE = {'product': 'Польза продукта', 'flow': 'Клиентский путь', 'detail': 'Деталь интерфейса'}
GLYPH = '<svg viewBox="0 0 20 28" aria-hidden="true"><circle cx="10" cy="5" r="4"/><path d="M4 27v-9H2v-5c0-3 2-5 5-5h6c3 0 5 2 5 5v5h-2v9h-5v-8H9v8z"/></svg>'


def obj(v):
    return v if isinstance(v, dict) else {}


def arr(v):
    return v if isinstance(v, list) else []


def txt(v):
    return '' if v is None else str(v)


def esc(v):
    return html.escape(txt(v), quote=True)


def num(v, decimals=1):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return '—'
    if v == int(v):
        return f'{int(v):,}'.replace(',', ' ')
    return f'{v:,.{decimals}f}'.replace(',', ' ').replace('.', ',')


def fraction(v):
    return num(v * 100) + '%' if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else '—'


def agent_words(n):
    """Return the Russian count noun and singular/plural agreement."""
    n = int(n) if isinstance(n, (int, float)) and math.isfinite(n) else 0
    singular = n % 10 == 1 and n % 100 != 11
    noun = 'AI-агент' if singular else 'AI-агента' if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else 'AI-агентов'
    return noun, singular


def ratio(a, b):
    return max(0, min(1, a / b)) if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b > 0 else 0


def safe_url(value):
    try:
        p = urlsplit(txt(value))
        if p.scheme in {'https', 'http'} and p.hostname and not p.username and not p.password and not any(ord(c) < 32 for c in txt(value)):
            return txt(value)
    except ValueError:
        pass
    return ''


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def badge(text, tone=''):
    return f'<span class="badge {tone}">{esc(text)}</span>'


def section_head(kicker, title, description=''):
    return f'<div class="section-head reveal"><div><div class="eyebrow">{esc(kicker)}</div><h2>{esc(title)}</h2></div>' + (f'<p>{esc(description)}</p>' if description else '') + '</div>'


def evidence_links(refs, label='Основание'):
    links = []
    for ref in arr(refs)[:8]:
        ref = obj(ref)
        if ref.get('anchor'):
            links.append(f'<a href="#{esc(ref["anchor"])}" data-evidence-link>{esc(ref.get("id", "Событие"))} ↗</a>')
    return f'<div class="evidence-links"><span>{esc(label)}</span> ' + ' '.join(links) + '</div>' if links else ''


def metric(n, denominator, label, note='', accent=False):
    value = f'{num(n)}<span> / {num(denominator)}</span>' if denominator else '—'
    return f'<div class="metric {"accent" if accent else ""}"><strong>{value}</strong><span>{esc(label)}</span><small>{esc(note or ("Нет ответов для оценки" if not denominator else ""))}</small></div>'


def bar_row(label, value, total, classes='', tail=''):
    width = ratio(value, total)
    result = f'{num(value)}<small> / {num(total)}</small>' if total else '<small>нет оценки</small>'
    return f'<div class="bar-row {classes}"><span class="bar-label">{esc(label)}</span><div class="bar-track"><i style="transform:scaleX({width:.6f})"></i></div><strong>{result}</strong>{tail}</div>'


def rec_scene(rec, index):
    stage = rec.get('stage', 'action')
    nodes = ''.join(f'<span class="{"active" if k == stage else ""}">{esc(v)}</span>' for k, v in STAGES.items())
    affected = rec.get('affected_count', len(arr(rec.get('affected_personas'))))
    noun, single = agent_words(affected)
    return f'''<div class="scene-metric"><b>{num(affected)}</b><p>{noun} {"столкнулся" if single else "столкнулись"}<br>с этой проблемой</p></div><div class="journey-strip" aria-label="Этап клиентского пути">{nodes}</div><div class="change-diagram"><div><span class="label">Что наблюдали</span><p>{esc(rec.get('observed') or ' '.join(arr(rec.get('reasons'))))}</p></div><span class="change-arrow" aria-hidden="true">↓</span><div class="proposed"><span class="label">Что изменить</span><p>{esc(rec.get('proposed') or rec.get('change'))}</p></div></div>'''


def _people(run, sessions, audience):
    people = {}
    for group in audience:
        for person in arr(group.get('personas')):
            p = dict(person)
            p['group'] = group.get('id', '')
            p['group_label'] = group.get('label', '')
            people[txt(p.get('id'))] = p
    for p in arr(obj(run.get('plan')).get('personas')):
        key = txt(p.get('id'))
        if key and key not in people:
            people[key] = {**p, 'group': p.get('segment', ''), 'group_label': p.get('segment', '')}
    for index, s in enumerate(sessions):
        key = txt(s.get('persona_id') or s.get('id') or index)
        if key not in people:
            people[key] = {'id': key, 'name': key, 'group': '', 'group_label': 'Группа не указана', 'model': s.get('model', '')}
    by_person = {}
    for i, s in enumerate(sessions):
        by_person.setdefault(txt(s.get('persona_id') or s.get('id') or i), []).append(s)
    for key, p in people.items():
        ss = by_person.get(key, [])
        p['executed'] = any(arr(s.get('events')) for s in ss)
        p['sessions'] = [{'id': s.get('id'), 'mode': MODES.get(s.get('mode'), s.get('mode')), 'status': STATUSES.get(s.get('status'), s.get('status')), 'summary': obj(s.get('feedback')).get('summary', ''), 'evidence_ids': arr(obj(s.get('feedback')).get('evidence_ids'))[:8]} for s in ss]
    return list(people.values())


def _dialogues(sessions, people):
    """Expose saved messages only; never infer a conversation from a draft or review."""
    persons = {txt(p.get('id')): p for p in people}
    dialogues = []
    for index, session in enumerate(sessions):
        events = [obj(e) for e in arr(session.get('events'))]
        if not events:
            continue
        transcript = obj(session.get('transcript'))
        anchors = {txt(e.get('id')): f'session-{index + 1}-event-{j + 1}' for j, e in enumerate(events) if e.get('id')}
        messages = []
        for message in arr(transcript.get('messages')):
            message = obj(message)
            if message.get('role') not in {'user', 'assistant'} or not isinstance(message.get('text'), str) or not message['text'].strip():
                continue
            refs = [txt(eid) for eid in arr(message.get('event_ids')) if txt(eid) in anchors]
            messages.append({'role': message['role'], 'text': message['text'], 'event_ids': refs,
                             'evidence': [{'id': eid, 'anchor': anchors[eid]} for eid in refs]})
        if not messages:
            continue
        person = persons.get(txt(session.get('persona_id')), {})
        dialogues.append({'id': session.get('id'), 'anchor': f'dialogue-{index + 1}',
                          'persona_id': session.get('persona_id'), 'name': person.get('name') or session.get('persona_id') or session.get('id'),
                          'group': person.get('group_label', ''), 'goal': person.get('goal', ''),
                          'model': session.get('model') or person.get('model', ''),
                          'mode': MODES.get(session.get('mode'), session.get('mode')),
                          'status': {'success': 'Задача выполнена', 'partial': 'Частичный результат', 'failure': 'Задача не выполнена'}.get(obj(session.get('feedback')).get('outcome'), STATUSES.get(session.get('status'), session.get('status'))),
                          'runtime_status': session.get('status'),
                          'conversation_url': safe_url(session.get('conversation_url')),
                          'product_name': txt(transcript.get('product_name')),
                          'source': transcript.get('source') or 'saved_transcript',
                          'capture_status': transcript.get('capture_status', 'unspecified'),
                          'capture_note': transcript.get('capture_note') or 'Показан сохранённый текст сообщений. Исходное оформление и вложения могут отличаться.',
                          'messages': messages})
    return dialogues


def _dialogue_appendix(dialogues, sessions):
    h = ['<section id="dialogues" class="section dialogue-section">',
         section_head('Приложение', 'Диалоги агентов с продуктом',
                      'Запросы AI-агентов и ответы продукта — отдельно от оценок и выводов исследования.')]
    if not dialogues:
        h.append('<p class="empty">Отдельная выгрузка сообщений не сохранена.</p><p class="caption">Ниже доступны записанные наблюдения браузера. Это текст экранов, а не восстановленная переписка.</p><a href="#evidence">Открыть записанные наблюдения ↘</a></section>')
        return ''.join(h)
    h.append(f'<div class="dialogue-toolbar"><p class="caption">Сохранено диалогов: {num(len(dialogues))}.</p><div class="dialogue-downloads"><button type="button" class="button secondary" data-download-dialogues="txt" hidden>Скачать все диалоги · TXT</button><button type="button" class="button secondary" data-download-dialogues="json" hidden>JSON</button></div></div>')
    for index, item in enumerate(dialogues):
        h.append(f'<details id="{esc(item["anchor"])}" class="dialogue-record" {"open" if index == 0 else ""}><summary><span><b>{esc(item["name"])}</b><small>{esc(item["group"])} · {esc(item["mode"])}</small></span><span class="dialogue-status">{esc(item["status"])}</span></summary><div class="details-body">')
        h.append(f'<p class="caption">Модель: {esc(item["model"] or "Не указана")}</p>')
        if item['capture_status'] == 'partial':
            h.append('<p class="caption"><b>Запись неполная.</b> Причина указана в разделе «Задача и источник записи».</p>')
        h.append('<div class="dialogue-messages">')
        for message in item['messages']:
            label = 'Запрос AI-агента' if message['role'] == 'user' else ('Ответ · ' + item['product_name'] if item['product_name'] else 'Ответ продукта')
            h.append(f'<article class="dialogue-message {message["role"]}"><span class="label">{esc(label)}</span><div class="message-text">{esc(message["text"])}</div>{evidence_links(message["evidence"], "Записанное событие")}</article>')
        h.append(f'</div><details class="dialogue-source"><summary>Задача и источник записи</summary><div class="details-body"><p class="dialogue-goal"><b>Задача:</b> {esc(item["goal"] or "Не указана.")}</p><p class="caption">Сессия: {esc(item["id"])}</p><p class="caption">{esc(item["capture_note"])}</p>')
        if item['conversation_url']:
            h.append(f'<p class="caption"><a href="{esc(item["conversation_url"])}" rel="noopener noreferrer">Открыть исходный чат ↗</a> · может потребоваться вход в тестовый аккаунт</p>')
        h.append('</div></details></div></details>')
    missing = sum(bool(arr(s.get('events'))) and not any(d['id'] == s.get('id') for d in dialogues) for s in sessions)
    if missing:
        h.append(f'<p class="caption">Ещё для {num(missing)} визитов отдельная выгрузка сообщений не сохранена. Их наблюдения доступны ниже; реплики по ним не восстанавливались.</p>')
    h.append('</section>')
    return ''.join(h)


def _forecast(forecast):
    scenarios = obj(forecast.get('scenarios'))
    labels = {'paying_customers': 'Новые платящие клиенты', 'cac': 'CAC · стоимость привлечения', 'mau': 'MAU · активные за месяц', 'dau': 'Средний DAU · активные за день', 'return_rate': 'Доля возвращений', 'activation': 'Доля получивших первый результат', 'activation_rate': 'Доля получивших первый результат', 'activated_users': 'Получили первый результат', 'd7_retention': 'D7 · возвращение на 7-й день', 'd30_retention': 'D30 · возвращение на 30-й день', 'd7_returners': 'Вернулись на 7-й день', 'd30_returners': 'Вернулись на 30-й день', 'stickiness': 'DAU / MAU'}
    rate_keys = {'return_rate', 'activation', 'activation_rate', 'd7_retention', 'd30_retention', 'stickiness'}
    named = [obj(v) for v in arr(forecast.get('named_scenarios'))]
    baseline = obj(forecast.get('baseline'))
    comparisons = [obj(v) for v in arr(forecast.get('comparison'))]
    named_out = ''
    if named:
        first = named[0]
        base_metrics, after_metrics = obj(baseline.get('metrics')), obj(first.get('metrics'))
        keys = list(dict.fromkeys([*base_metrics, *[key for item in named for key in obj(item.get('metrics'))]]))
        named_out = '<div class="forecast-card reveal"><div class="eyebrow">Условный расчёт · внешние данные</div><h3>Что получится при заданных условиях</h3><div class="forecast-switch" role="group" aria-label="Сценарий расчёта">'
        for index, item in enumerate(named):
            named_out += f'<button data-forecast="{index}" aria-pressed="{str(index == 0).lower()}">{esc(item.get("label") or item.get("name"))}</button>'
        named_out += '</div>'
        before_rate = obj(base_metrics.get('activation_rate')).get('value')
        after_rate = obj(after_metrics.get('activation_rate')).get('value')
        before_count = obj(base_metrics.get('activated_users')).get('value')
        after_count = obj(after_metrics.get('activated_users')).get('value')
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in [before_rate, after_rate, before_count, after_count]):
            delta = after_count - before_count
            named_out += f'<div class="forecast-visual"><div><span class="label">Первый полезный результат · доля посетителей</span><div class="forecast-bar-row"><span>До</span><div class="bar-track"><i style="transform:scaleX({ratio(before_rate, 1):.6f})"></i></div><b>{fraction(before_rate)}</b></div><div class="forecast-bar-row accent"><span>После</span><div class="bar-track"><i id="forecast-bar" style="transform:scaleX({ratio(after_rate, 1):.6f})"></i></div><b id="forecast-percent">{fraction(after_rate)}</b></div></div><div class="forecast-lift"><b id="forecast-delta">{("+" if delta > 0 else "") + num(delta)}</b><p>пользователей с первым полезным результатом</p><small>При заданных условиях расчёта</small></div></div>'
        named_out += '<div class="table-wrap"><table><thead><tr><th>Показатель</th><th>До · исходные условия</th><th>После · выбранный сценарий</th></tr></thead><tbody>'
        for key in keys:
            bm, am = obj(base_metrics.get(key)), obj(after_metrics.get(key))
            fmt = fraction if key in rate_keys else num
            named_out += f'<tr data-forecast-metric="{esc(key)}"><td>{esc(labels.get(key, key))}</td><td>{fmt(bm.get("value"))}<small class="forecast-unit">{esc(bm.get("unit"))}</small></td><td class="forecast-number"><span data-forecast-after>{fmt(am.get("value"))}</span><small class="forecast-unit" data-forecast-unit>{esc(am.get("unit"))}</small></td></tr>'
        named_out += '</tbody></table></div><p class="caption">Это пересчёт заданных допущений. Рост после изменения ещё не доказан тестом.</p>'
        source = obj(forecast.get('source_info')).get('source')
        if source:
            named_out += f'<p class="caption">Источник исходных данных: {esc(source)}</p>'
        named_out += '</div>'
        named_out += '<details><summary>Все сценарии и исходные условия</summary><div class="details-body">'
        for item in ([baseline] if baseline else []) + named:
            named_out += f'<h3>{esc(item.get("label") or item.get("name") or "Исходные условия")}</h3><div class="table-wrap"><table><tbody>'
            for key, value in obj(item.get('metrics')).items():
                value = obj(value)
                fmt = fraction if key in rate_keys else num
                named_out += f'<tr><td>{esc(labels.get(key, key))}</td><td>{fmt(value.get("value"))} {esc(value.get("unit"))}</td></tr>'
            named_out += '</tbody></table></div>'
            if item.get('provenance'):
                named_out += f'<p class="caption">{esc(item["provenance"])}</p>'
            if arr(item.get('assumptions')):
                named_out += '<ul>' + ''.join(f'<li>{esc(x)}</li>' for x in item['assumptions']) + '</ul>'
            if arr(item.get('invalid')):
                named_out += '<p class="caption">Исключены некорректные поля: ' + esc(', '.join(map(txt, item['invalid']))) + '</p>'
        named_out += '</div></details>'
    rows = ''
    for key, value in scenarios.items():
        value = obj(value)
        fmt = fraction if key in rate_keys else num
        rows += f'<tr><td>{esc(labels.get(key, key))}</td><td class="forecast-number">{fmt(value.get("low"))} — {fmt(value.get("high"))}</td><td>{esc(value.get("unit", ""))}</td></tr>'
    if named_out:
        out = named_out
        if rows:
            out += '<details><summary>Дополнительные диапазоны из внешних данных</summary><div class="details-body table-wrap"><table><tbody>' + rows + '</tbody></table></div></details>'
    elif baseline and obj(baseline.get('metrics')):
        out = '<div class="forecast-card reveal"><div class="eyebrow">Исходные условия · внешний источник</div><h3>Что следует из заданных данных</h3><div class="table-wrap"><table><tbody>'
        for key, value in obj(baseline.get('metrics')).items():
            value = obj(value)
            fmt = fraction if key in rate_keys else num
            out += f'<tr><td>{esc(labels.get(key, key))}</td><td class="forecast-number">{fmt(value.get("value"))}</td><td>{esc(value.get("unit"))}</td></tr>'
        out += '</tbody></table></div><p class="caption">Сценарий после изменений не задан. Это расчёт исходных условий, а не прогноз эффекта нового релиза.</p></div>'
    elif rows:
        out = '<div class="forecast-card reveal"><div class="eyebrow">Условный расчёт · внешние данные</div><h3>Что получится при заданных условиях</h3><div class="table-wrap"><table><thead><tr><th>Показатель</th><th>Диапазон сценария</th><th>Единица</th></tr></thead><tbody>' + rows + '</tbody></table></div><p class="caption">Диапазоны отражают заданные допущения. Это не статистическая погрешность и не эффект, доказанный тестом.</p></div>'
    else:
        out = '<div class="forecast-empty reveal"><div class="eyebrow">Для расчёта нужны исходные данные</div><h3>Поведение AI-агентов<br>не определяет retention или CAC.</h3><p>В этом отчёте нет исходных данных для числового прогноза. Для расчёта нужны данные о трафике, расходах, конверсии и возвращении пользователей.</p></div>'
    needed = arr(forecast.get('needed'))
    assumptions = arr(forecast.get('assumptions'))
    invalid = arr(forecast.get('invalid'))
    if needed:
        out += '<details><summary>Каких данных не хватает</summary><div class="details-body"><ul>' + ''.join(f'<li>{esc(x)}</li>' for x in needed) + '</ul></div></details>'
    if assumptions or invalid:
        out += '<details><summary>Допущения и ограничения расчёта</summary><div class="details-body"><ul>' + ''.join(f'<li>{esc(x)}</li>' for x in assumptions) + '</ul>'
        if invalid:
            out += f'<p>Некорректные поля исключены: {esc(", ".join(map(txt, invalid)))}.</p>'
        out += '</div></details>'
    return out


def render_html(run, sessions, report):
    """Render one self-contained HTML file with progressive-enhancement motion."""
    run, report = obj(run), obj(report)
    sessions = [s for s in arr(sessions) if isinstance(s, dict)]
    plan = obj(run.get('plan'))
    experiment = obj(report.get('experiment'))
    metrics = obj(report.get('metrics'))
    satisfaction = obj(report.get('satisfaction'))
    audience = [obj(g) for g in arr(report.get('audience'))]
    priorities = [obj(r) for r in arr(report.get('priorities'))][:3]
    recs = [obj(r) for r in arr(report.get('recommendations'))]
    people = _people(run, sessions, audience)
    dialogues = _dialogues(sessions, people)
    dialogue_anchors = {d['id']: d['anchor'] for d in dialogues}
    for person in people:
        for visit in person['sessions']:
            visit['dialogue_anchor'] = dialogue_anchors.get(visit['id'])
    product = experiment.get('product') or plan.get('product_summary') or urlsplit(safe_url(plan.get('url'))).hostname or 'Продукт'
    # A planning summary can be long; keep it in the methodology and use the host as the visual label.
    product_label = product if len(txt(product)) <= 70 else (urlsplit(safe_url(plan.get('url'))).hostname or 'Продукт')
    date = txt(run.get('created_at', ''))[:10]
    executed = experiment.get('executed_agents', sum(bool(p.get('executed')) for p in people))
    planned = experiment.get('planned_agents', len(people))
    total_sessions = experiment.get('executed_sessions', sum(bool(arr(s.get('events'))) for s in sessions))
    eligible = metrics.get('eligible', 0)
    successful = metrics.get('task_success', 0)
    feedback_n = obj(satisfaction.get('return_intent')).get('n', 0)
    selected_group = audience[0].get('id') if audience else ''
    warning_demo = bool(run.get('demo') or run.get('synthetic_fixture') or plan.get('demo'))
    band = 'ДЕМОНСТРАЦИОННЫЕ ДАННЫЕ · проверка шаблона, без теста продукта' if warning_demo else 'AI-агенты · результаты синтетического тестирования'
    title = f'Audience — {txt(product_label)} · продуктовый отчёт'
    h = [f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>{esc(title)}</title><style>', (ASSETS / 'report.css').read_text(encoding='utf-8'), '</style></head><body><div class="reading-progress" aria-hidden="true"><i></i></div><header class="sticky"><div class="study-band">', esc(band), '</div><nav class="nav" aria-label="Разделы отчёта"><a class="brand" href="#top">Audience<span>.</span></a><div class="nav-links">']
    for key, label in [('experiment', 'Эксперимент'), ('decisions', 'Решения'), ('audience', 'Аудитория'), ('ux', 'Интерфейс'), ('forecast', 'Метрики'), ('plan', 'План'), ('dialogues', 'Диалоги')]:
        h.append(f'<a href="#{key}">{label}</a>')
    h.append('<button class="button secondary" id="print-report" type="button">Печать / PDF</button></div></nav></header><main id="top"><div class="eyebrow top-kicker">Audience / отчёт для команды продукта</div>')
    hero_title = 'Что улучшить<br>в следующем<br>релизе.' if priorities else 'Что удалось<br>проверить<br>в продукте.'
    agent_noun, single_agent = agent_words(executed)
    hero_copy = f'{num(executed)} {agent_noun} {"приступил" if single_agent else "приступили"} к тесту.<br>' + ('Подтверждённые наблюдения и приоритеты для команды.' if priorities else 'Результаты проверенных сценариев и границы теста.' if eligible else 'Доступных оценок результата пока нет.')
    h.append(f'<section class="report-hero"><div class="hero-copy"><div class="report-date">{esc(product_label)}{(" / " + esc(date)) if date else ""}</div><h1>{hero_title}</h1><p>{hero_copy}</p><a href="#decisions" class="button hero-cta">Смотреть выводы <span aria-hidden="true">↘</span></a><a href="#dialogues" class="hero-dialogues">Запросы и ответы ↘</a></div><aside class="agent-board" aria-label="Агенты исследования"><div class="board-top"><span>Аудитория исследования</span><span>{num(executed)}<small> / {num(planned)}</small></span></div><div class="agent-matrix">')
    for index, p in enumerate(people[:120]):
        selected = p.get('group') == selected_group
        h.append(f'<button class="hero-agent {"selected" if selected else ""} {"not-executed" if not p.get("executed") else ""}" data-person="{index}" data-agent-group="{esc(p.get("group"))}" aria-label="{esc(p.get("name") or p.get("id"))} — AI-агент. Открыть профиль">{GLYPH}</button>')
    if not people:
        h.append('<p class="muted">Профили агентов не сохранены.</p>')
    h.append('</div><div class="board-tabs" role="group" aria-label="Выделить группу">')
    for index, group in enumerate(audience[:8]):
        h.append(f'<button data-board="{esc(group.get("id"))}" aria-pressed="{str(index == 0).lower()}" data-caption="{esc(group.get("label"))} · {num(group.get("executed", 0))} из {num(group.get("planned", 0))} приступили к тесту">{esc(group.get("label"))}</button>')
    initial = audience[0] if audience else {}
    h.append(f'</div><p class="board-caption"><b id="board-caption">{esc(initial.get("label", "Профили AI-агентов"))}</b><span>Цвет выделяет группу. Контур — агент без записанных наблюдений. Нажмите на человечка, чтобы увидеть его задачу.</span></p>')
    if len(people) > 120:
        h.append(f'<p class="caption">На карте первые 120 из {num(len(people))} агентов. Все профили доступны в разделе аудитории и в report.json.</p>')
    h.append('</aside></section>')

    h.append('<section id="experiment" class="experiment">' + section_head('Как устроен тест', 'Дизайн эксперимента', experiment.get('task') or plan.get('task', '')))
    product_url = safe_url(experiment.get('url') or plan.get('url'))
    if product_url:
        h.append(f'<p class="caption">Продукт: <a href="{esc(product_url)}" rel="noopener noreferrer">{esc(product_url)}</a></p>')
    h.append('<div class="passport reveal">')
    for number, label in [(executed, f'агентов с наблюдениями · запланировано {num(planned)}'), (total_sessions, f'визитов с наблюдениями · запланировано {num(experiment.get("planned_sessions", len(sessions)))}'), (len(arr(experiment.get('models'))), 'моделей в плане'), (experiment.get('evaluable_sessions', eligible), 'визитов доступны для оценки результата')]:
        h.append(f'<div><strong>{num(number)}</strong><span>{esc(label)}</span></div>')
    h.append('</div>')
    if 'tasks_started' in experiment:
        unknown_tasks = experiment.get('tasks_unknown', 0)
        h.append(f'<p class="caption"><b>Подтверждённо запущено новых задач: {num(experiment.get("tasks_started", 0))}.</b> Продолжений прежней задачи: {num(experiment.get("resume_sessions", 0))}. {esc(experiment.get("task_count_note"))}</p>')
        if unknown_tasks:
            h.append(f'<p class="caption">Для {num(unknown_tasks)} визитов запуск новой задачи не размечен; они не прибавлены к числу подтверждённых запусков.</p>')
    h.append('<div class="experiment-brief reveal">')
    for label, text in [('Кого выбрали', experiment.get('audience') or plan.get('audience') or 'Группы сформированы как гипотезы по назначению продукта и задаче теста.'), ('Почему именно их', experiment.get('why') or 'Проверяем разные задачи и условия использования. Это гипотеза о целевой аудитории, а не измерение её состава.'), ('Что проверяли', ' → '.join(MODES.get(x, txt(x)) for x in arr(experiment.get('scenario_modes') or plan.get('scenario_modes'))) or 'Режимы указаны в записях сессий ниже.')]:
        h.append(f'<div><b>{esc(label)}</b><p>{esc(text)}</p></div>')
    h.append('</div><p class="caption">' + esc(experiment.get('session_mode_note', '')) + '</p><p class="caption">AI-персоны не являются независимыми респондентами. Их оценки показывают гипотезы о пользовательском опыте; модельные повторные визиты не измеряют D7 или D30 retention.</p><details><summary>Состав групп, модели и ограничения теста</summary><div class="details-body">')
    if audience:
        h.append('<div class="table-wrap"><table><thead><tr><th>Группа</th><th>Зачем проверять</th><th>С наблюдениями / план</th></tr></thead><tbody>')
        for group in audience:
            h.append(f'<tr><td>{esc(group.get("label"))}</td><td>{esc(group.get("why"))}</td><td>{num(group.get("executed"))} / {num(group.get("planned"))}</td></tr>')
        h.append('</tbody></table></div>')
    for model in arr(experiment.get('models')):
        h.append(f'<p><b>{esc(model.get("id"))}</b> · {num(model.get("executed"))} из {num(model.get("planned"))} агентов с наблюдениями</p>')
    devices = obj(experiment.get('devices'))
    if devices:
        h.append('<p>Устройства по плану: ' + ' · '.join(f'{esc(DEVICES.get(k, k))}: {num(v)}' for k, v in devices.items()) + '. Это назначенные условия, не подтверждение фактически использованного экрана.</p>')
    measured_devices = obj(experiment.get('measured_devices'))
    if measured_devices:
        h.append('<p>По записанному размеру экрана: ' + ' · '.join(f'{esc(DEVICES.get(k, "Размер не записан" if k == "unknown" else k))}: {num(v)}' for k, v in measured_devices.items()) + '.</p>')
    h.append(f'<p>Блокировки: {num(experiment.get("blocked_sessions", metrics.get("blocked", 0)))}. Ошибки выполнения: {num(experiment.get("failed_sessions", metrics.get("infrastructure_errors", 0)))}. Без наблюдений: {num(experiment.get("not_executed_sessions", 0))}.</p>')
    warnings = arr(experiment.get('warnings')) + arr(experiment.get('assumptions'))
    if warnings:
        h.append('<ul>' + ''.join(f'<li>{esc(x)}</li>' for x in warnings) + '</ul>')
    h.append('</div></details></section>')

    h.append(f'<section id="decisions" class="conclusion reveal"><div class="eyebrow">Главный вывод</div><h2>{esc(report.get("insight") or "Для вывода нужны завершённые прохождения.")}</h2>')
    if priorities:
        h.append(f'<p class="lead">Следующий релиз стоит сосредоточить на {len(priorities)} {"изменении" if len(priorities) == 1 else "изменениях"}. Ниже — наблюдения, предложение и способ проверить результат.</p>')
    else:
        h.append('<p class="lead">Подтверждённых изменений для плана релиза пока нет. Доступные наблюдения и ограничения показаны ниже.</p>')
    h.append('<div class="metrics">')
    h.append(metric(successful, eligible, 'Визиты с достигнутой целью', ('После проверки по событиям · исходные оценки сохранены в аудите' if run.get('quality_review') else 'Новая задача или продолжение — согласно цели визита'), True))
    h.append(metric(obj(satisfaction.get('csat')).get('satisfied', 0), obj(satisfaction.get('csat')).get('n', 0), 'Положительно оценили опыт', 'Оценки 4–5 из 5 · последнее допустимое мнение каждого агента'))
    h.append(metric(obj(satisfaction.get('return_intent')).get('yes', 0), feedback_n, 'Выбрали бы продукт снова', 'Ответ AI-агента, не реальное удержание'))
    h.append('</div></section>')

    h.append('<section id="priorities" class="section">' + section_head('Решения для команды', 'С чего начать следующий релиз' if priorities else 'Есть ли основания менять продукт', 'Подтверждённые изменения — от основных препятствий к деталям.' if priorities else 'В план попадают только рекомендации, связанные с наблюдениями.'))
    if priorities:
        h.append('<div class="story-layout"><aside class="story-sticky"><div class="story-stage"><div class="stage-index"><span>Предлагаемое изменение</span><b id="story-index">01 / ' + f'{len(priorities):02d}' + '</b></div>')
        for index, rec in enumerate(priorities):
            h.append(f'<div class="story-scene" data-scene="{index}" {"hidden" if index else ""}>{rec_scene(rec, index)}</div>')
        h.append('<p class="caption">Схема рекомендации, не снимок интерфейса. Результат изменения ещё нужно проверить.</p><div class="stage-dots">')
        for index in range(len(priorities)):
            h.append(f'<a href="#priority-{index + 1}" data-story-jump="{index}" {"aria-current=step" if not index else ""}>{index + 1:02d}</a>')
        h.append('</div></div></aside><div class="story-steps">')
        for index, rec in enumerate(priorities):
            h.append(f'<article id="priority-{index + 1}" class="story-step" data-step="{index}"><div class="story-kicker"><span>{index + 1:02d}</span>{esc(SCOPE.get(rec.get("scope"), "Изменение продукта"))}</div><h3>{esc(rec.get("change"))}</h3><p class="proof-line">{esc(rec.get("observed") or " ".join(arr(rec.get("reasons"))))}</p><div class="step-action"><span class="label">Что сделать</span><p>{esc(rec.get("proposed") or rec.get("change"))}</p></div>{evidence_links(rec.get("evidence"))}<div class="mobile-scene">{rec_scene(rec, index)}</div><details><summary>Как проверить улучшение</summary><div class="details-body"><p>{esc(rec.get("how_to_verify") or "Повторите тот же сценарий после изменения и сравните результаты при одинаковых условиях.")}</p><p class="accept"><b>Показатель:</b> {esc(rec.get("expected_metric") or "Доля визитов с выполненной задачей")}</p><p class="caption">Величина эффекта пока не измерена.</p></div></details></article>')
        h.append('</div></div>')
    else:
        h.append('<p class="empty">Подтверждённых приоритетов пока нет. Не стоит превращать техническую блокировку или неподтверждённое мнение в задачу для продуктовой команды.</p>')
    h.append('</section>')

    h.append('<section id="audience" class="section">' + section_head('Разные задачи — разный опыт', 'Кому продукт помогает,<br>а кому пока трудно'.replace('<br>', ' '), 'Сравните результаты групп. Число под каждой полосой относится только к визитам или ответам, доступным для оценки.'))
    if audience:
        h.append('<div class="audience-chart reveal"><div class="chart-header"><h3 id="audience-chart-title">Решили первую задачу</h3><div class="chart-switch" role="group" aria-label="Показатель для сравнения">')
        for key, label in [('first_use', 'Первый визит'), ('repeat', 'Новая задача при повторном визите'), ('choose_again', 'Выбрали бы снова')]:
            h.append(f'<button data-measure="{key}" aria-pressed="{str(key == "first_use").lower()}">{label}</button>')
        h.append('</div></div>')
        for index, group in enumerate(audience):
            measure = obj(group.get('first_use'))
            h.append(f'<div class="audience-row" data-chart-group="{index}"><span class="chart-label"><small>{index + 1:02d}</small>{esc(group.get("label"))}</span><div class="bar-track"><i style="transform:scaleX({ratio(measure.get("success", 0), measure.get("n", 0)):.6f})"></i></div><strong><span data-chart-count>{num(measure.get("success")) if measure.get("n") else "—"}</span><small data-chart-denominator>{(" / " + num(measure.get("n"))) if measure.get("n") else "нет оценки"}</small></strong><p data-chart-unknown class="row-caption">Без оценки: {num(measure.get("unknown", 0))}</p></div>')
        h.append('<p class="chart-caption" id="audience-chart-note">Первый визит каждой персоны. Технические ошибки, блокировки, незавершённые запуски и лимит бюджета показаны отдельно; это не отказ пользователя.</p></div><details><summary>Сравнить все показатели групп</summary><div class="details-body table-wrap"><table><thead><tr><th>Группа</th><th>Первая задача</th><th>Новая задача при повторном визите</th><th>Продолжение прежней задачи</th><th>Выбрали бы снова</th><th>Удовлетворённость</th></tr></thead><tbody>')
        for group in audience:
            cells = []
            for key in ['first_use', 'repeat', 'resume', 'choose_again']:
                m = obj(group.get(key))
                cells.append(f'{num(m.get("success", m.get("yes")))} / {num(m.get("n"))}' if m.get('n') else 'нет оценки')
            sat = obj(group.get('satisfaction'))
            cells.append(f'{num(sat.get("mean"))} / 5 · n={num(sat.get("n"))}' if sat.get('n') else 'нет оценки')
            h.append('<tr><td>' + esc(group.get('label')) + '</td>' + ''.join('<td>' + x + '</td>' for x in cells) + '</tr>')
        h.append('</tbody></table></div></details>')
    else:
        h.append('<p class="empty">Группы аудитории не были сохранены в этом запуске.</p>')
    h.append('<details class="roster"><summary>Кто тестировал продукт</summary><div class="details-body"><div class="roster-tools"><label for="person-search">Найти агента или задачу</label><input id="person-search" type="search" placeholder="Имя, группа или задача" autocomplete="off"></div><div id="person-list" class="person-list">')
    for index, person in enumerate(people[:60]):
        h.append(f'<details class="person-record"><summary>{esc(person.get("name") or person.get("id"))}<span>{esc(person.get("group_label"))}</span></summary><div class="details-body"><p>{esc(person.get("goal"))}</p><p class="caption">{esc(DEVICES.get(person.get("device"), person.get("device", "")))} · {esc(person.get("model"))}</p>')
        for session in arr(person.get('sessions')):
            h.append(f'<p><b>{esc(session.get("mode"))}:</b> {esc(session.get("status"))}. {esc(session.get("summary"))}</p>')
        h.append('</div></details>')
    h.append('</div>')
    if len(people) > 60:
        h.append(f'<p class="caption">Показаны первые 60 из {num(len(people))}. Поиск с JavaScript доступен по всем профилям; полный набор также сохранён в report.json.</p>')
    h.append('</div></details></section>')

    h.append('<section id="ux" class="section">' + section_head('Понятно ли, что делать', 'Где интерфейс помогает,<br>а где мешает'.replace('<br>', ' '), 'Только оценки, привязанные к записанным действиям. Отсутствие ответа не считается отрицательной оценкой.'))
    assessment = obj(satisfaction.get('assessment'))
    h.append('<div class="clarity-chart reveal">')
    for key, label in [('purpose_clear', 'Понятна польза продукта'), ('next_step_clear', 'Понятен следующий шаг'), ('result_clear', 'Понятно, получен ли результат')]:
        m = obj(assessment.get(key))
        h.append(bar_row(label, m.get('yes', 0), m.get('n', 0), tail=f'<p class="row-caption">Без оценки: {num(m.get("unknown", 0))}</p>'))
    h.append('</div>')
    journey = obj(report.get('journey'))
    if journey.get('available') and arr(journey.get('stages')):
        h.append('<details><summary>Наблюдения по этапам клиентского пути</summary><div class="details-body">')
        for stage in arr(journey.get('stages')):
            h.append(bar_row(stage.get('label'), stage.get('reached', 0), stage.get('n', 0)))
        h.append(f'<p class="caption">{esc(journey.get("note"))}</p></div></details>')
    ui_recs = [r for r in recs if r.get('evidence')][:6]
    if ui_recs:
        h.append('<div class="interface-list">')
        for index, r in enumerate(ui_recs):
            h.append(f'<details><summary><span class="list-index">{index + 1:02d}</span>{esc(r.get("change"))}</summary><div class="details-body"><div class="before-after"><div><span class="label">Наблюдение</span><p>{esc(r.get("observed") or " ".join(arr(r.get("reasons"))))}</p></div><div><span class="label">Предложение</span><p>{esc(r.get("proposed") or r.get("change"))}</p></div></div>{evidence_links(r.get("evidence"))}</div></details>')
        h.append('</div>')
    h.append('</section>')

    h.append('<section id="satisfaction" class="section">' + section_head('Оценка опыта AI-агентами', 'Что понравилось.<br>Что стоит сохранить.'.replace('<br>', ' '), 'У каждого агента учитывается последнее допустимое мнение. Это синтетические оценки, а не удовлетворённость реальных клиентов.'))
    csat, nps = obj(satisfaction.get('csat')), obj(satisfaction.get('nps'))
    h.append(f'<div class="sentiment-grid"><div class="sentiment-score reveal"><span class="label">Положительная оценка · 4–5 из 5</span><strong>{fraction(csat.get("rate"))}</strong><p>{num(csat.get("satisfied", 0))} из {num(csat.get("n", 0))} ответивших AI-агентов</p><div class="distribution" aria-label="Распределение оценок удовлетворённости">')
    counts = arr(csat.get('distribution')) or [0] * 5
    max_count = max([c for c in counts if isinstance(c, (int, float))] + [1])
    for i, count in enumerate(counts[:5]):
        h.append(f'<div><b>{num(count)}</b><div><i style="height:{ratio(count, max_count) * 100:.2f}%"></i></div><span>{i + 1}</span></div>')
    h.append(f'</div><p class="caption">Средняя оценка: {num(csat.get("mean"))} / 5. Без оценки: {num(csat.get("unknown", 0))}.</p></div><div class="nps-card reveal"><span class="label">Синтетический NPS</span><strong>{("+" if isinstance(nps.get("value"), (int, float)) and nps["value"] > 0 else "") + num(nps.get("value"))}</strong><p>По {num(nps.get("n", 0))} ответам AI-агентов</p><div class="nps-breakdown"><span><b>{num(nps.get("promoters", 0))}</b>Оценки 9–10</span><span><b>{num(nps.get("passives", 0))}</b>Оценки 7–8</span><span><b>{num(nps.get("detractors", 0))}</b>Оценки 0–6</span></div><p class="caption">Доля оценок 9–10 минус доля оценок 0–6. Не сравнивайте с рыночными бенчмарками NPS реальных клиентов.</p></div></div>')
    positives = arr(report.get('positives'))[:4]
    if positives:
        h.append('<div class="positives">')
        for item in positives:
            h.append(f'<article><span class="positive-mark" aria-hidden="true">+</span><div><h3>{esc(item.get("text"))}</h3><p class="caption">Число AI-агентов, отметивших это: {num(item.get("count"))}</p>{evidence_links(item.get("evidence"))}</div></article>')
        h.append('</div>')
    else:
        h.append('<p class="caption">Положительные отзывы с допустимыми ссылками на действия не записаны. Это не означает, что в продукте нет сильных сторон.</p>')
    h.append('</section>')

    h.append('<section id="forecast" class="section">' + section_head('От наблюдений к гипотезам роста', 'Прогноз продуктовых метрик', 'Условные сценарии из внешних данных. Ни количество агентов, ни их желание вернуться не превращаются автоматически в прогноз бизнеса.') + _forecast(obj(report.get('forecast'))) + '</section>')

    h.append('<section id="plan" class="section">' + section_head('Что делать дальше', 'План следующего релиза' if priorities else 'Следующий шаг исследования', 'Проверьте изменения на том же наборе задач и затем — на реальных пользователях.' if priorities else 'Расширьте проверку там, где пока не хватает наблюдений.'))
    if priorities:
        h.append('<div class="release-plan">')
        for index, rec in enumerate(priorities):
            h.append(f'<article class="reveal"><span>{index + 1:02d}</span><div><h3>{esc(rec.get("change"))}</h3><p>{esc(rec.get("how_to_verify") or "Повторить сценарий после изменения и сравнить результат.")}</p><small>Проверяем: {esc(rec.get("expected_metric") or "выполнение задачи")}</small></div></article>')
        h.append('</div>')
    else:
        h.append('<div class="final-decision"><h3>Дополнить проверку продукта</h3><p>Проверьте оставшиеся задачи и группы аудитории. Если запуск прервали блокировки или ошибки, сначала устраните их. Сохраните критерии успеха для сравнения результатов.</p></div>')
    rest = [r for r in recs if r not in priorities]
    if rest:
        h.append('<details><summary>Остальные наблюдения и гипотезы</summary><div class="details-body">')
        for r in rest[:30]:
            label = 'Наблюдение по сессиям' if r.get('evidence') else 'Гипотеза · нет достаточного подтверждения'
            h.append(f'<article class="secondary-finding"><span class="label">{esc(label)}</span><h3>{esc(r.get("change"))}</h3><p>{esc(" ".join(arr(r.get("reasons"))))}</p>{evidence_links(r.get("evidence"))}</article>')
        h.append('</div></details>')
    h.append('</section>')

    h.append(_dialogue_appendix(dialogues, sessions))

    # Keep cited message sources and findings reachable, without shortening evidence.
    wanted = {eid for dialogue in dialogues for message in dialogue['messages'] for eid in message['event_ids']}
    for item in recs + arr(report.get('positives')):
        for ref in arr(obj(item).get('evidence')):
            if obj(ref).get('id'):
                wanted.add(txt(ref['id']))
    for s in sessions:
        wanted.update(txt(x) for x in arr(obj(s.get('feedback')).get('evidence_ids')))
    h.append('<section id="evidence" class="section evidence-section">' + section_head('Проверить основания', 'На чём основаны выводы', 'Ниже — записанные события браузера без сокращения текста. Сообщения продукта доступны в приложении выше; полный технический журнал и расчёты — в report.json.'))
    shown_events = 0
    h.append('<details id="evidence-details"><summary>Сессии и доказательства</summary><div class="details-body">')
    for i, s in enumerate(sessions):
        events = [e for e in arr(s.get('events')) if isinstance(e, dict)]
        chosen = [(j, e) for j, e in enumerate(events) if txt(e.get('id')) in wanted or s.get('id') not in dialogue_anchors]
        # Every session gets an anchor, so existing downstream evidence links remain usable.
        h.append(f'<details id="session-{i + 1}" class="session-record"><summary>{esc(s.get("id", str(i + 1)))}<span>{esc(STATUSES.get(s.get("status"), s.get("status")))}</span></summary><div class="details-body"><p class="caption">{esc(s.get("model"))} · {esc(MODES.get(s.get("mode"), s.get("mode")))}</p><p>{esc(obj(s.get("feedback")).get("summary") or s.get("stop_reason") or s.get("error") or "Отзыв не записан.")}</p>')
        for j, event in chosen:
            shown_events += 1
            obs, action, result = obj(event.get('observation')), obj(event.get('action')), obj(event.get('result'))
            url = safe_url(obs.get('url'))
            action_label = ' · '.join(txt(action.get(k)) for k in ['type', 'target', 'value'] if action.get(k))
            h.append(f'<article id="session-{i + 1}-event-{j + 1}" class="event-record"><span class="label">{esc(event.get("id"))}</span><h4>{esc(obs.get("title") or "Записанное событие")}</h4><p><b>Действие:</b> {esc(action_label or "Наблюдение")}</p><p class="caption">Сохранённое наблюдение браузера · текст экрана</p><div class="observation-text">{esc(txt(obs.get("text")))}</div><p class="caption">Результат действия: {esc(result.get("status") or result.get("reason") or "См. полную запись")}</p>')
            if url:
                h.append(f'<a href="{esc(url)}" rel="noopener noreferrer">{esc(url)}</a>')
            h.append('</article>')
        if events and not chosen:
            h.append(f'<p class="caption">Событий в полном файле: {len(events)}. На эту сессию нет ссылок из выводов.</p>')
        h.append('</div></details>')
    h.append('</div></details>')
    costs = obj(report.get('costs'))
    h.append('<details><summary>Расходы, модели и полнота результата</summary><div class="details-body"><div class="table-wrap"><table><tbody>')
    for label, key in [('Подтверждено провайдером', 'confirmed_usd'), ('Оценка расходов', 'estimated_usd'), ('Неопределённая стоимость', 'unknown_usd'), ('Резерв активных запросов', 'reserved_usd'), ('Учтено в лимите', 'accounted_usd'), ('Лимит', 'budget_usd')]:
        h.append(f'<tr><td>{label}</td><td>{num(costs.get(key), 4)} USD</td></tr>')
    h.append('</tbody></table></div><p class="caption">Учтённая сумма включает резервы и оценки. Это не счёт провайдера. Непрошедшие сессии не считаются отказом пользователя.</p>')
    for status, count in obj(metrics.get('statuses')).items():
        h.append(f'<p>{esc(STATUSES.get(status, status))}: {num(count)}</p>')
    h.append('</div></details></section><footer class="footer"><a class="brand" href="#top">Audience<span>.</span></a><p>Наблюдения → решения → повторная проверка.</p><p class="caption">AI-агенты моделируют поведение. Синтетические результаты не заменяют исследование реальных пользователей.</p></footer></main>')
    h.append('<dialog id="person-dialog" aria-labelledby="person-title"><button type="button" class="dialog-close" aria-label="Закрыть профиль">×</button><div class="eyebrow">Профиль AI-агента</div><h2 id="person-title"></h2><p id="person-goal"></p><p id="person-meta" class="caption"></p><div id="person-sessions"></div></dialog>')
    # Only compact persona summaries and precomputed group values are needed by the UI.
    payload = {'people': [{k: p.get(k) for k in ['id', 'name', 'goal', 'device', 'model', 'group', 'group_label', 'executed', 'sessions']} for p in people], 'audience': [{k: g.get(k) for k in ['id', 'label', 'first_use', 'repeat', 'choose_again']} for g in audience], 'story_count': len(priorities), 'dialogues': dialogues, 'forecast': {'baseline': obj(report.get('forecast')).get('baseline'), 'named_scenarios': obj(report.get('forecast')).get('named_scenarios')}}
    h.append('<script type="application/json" id="report-data">' + compact_json(payload) + '</script><script>' + (ASSETS / 'report.js').read_text(encoding='utf-8') + '</script></body></html>')
    return ''.join(h)
