"""Literal message exports must be visible, complete and safe to open offline."""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audience_core.report_view import render_html
from test_report_view import Page, specimen


def with_transcript(status='completed'):
    run, sessions, report = specimen(status=status)
    for index, session in enumerate(sessions):
        session['conversation_url'] = 'https://example.test/chat/' + str(index)
        session['transcript'] = {
            'source': 'captured_browser_text',
            'product_name': 'Тестовый продукт',
            'capture_note': 'Дословный текст из сохранённого браузерного наблюдения.',
            'messages': [
                {'role': 'user', 'text': 'Покажи свободное время.\nПосле 18:00.', 'event_ids': [session['id'] + ':e1']},
                {'role': 'assistant', 'text': 'Есть время в 19:00.\nНажмите «Подтвердить».', 'event_ids': [session['id'] + ':e1']},
            ],
        }
    return run, sessions, report


class DialogueTests(unittest.TestCase):
    def test_discoverable_literal_messages_and_download_data(self):
        run, sessions, report = with_transcript()
        page = render_html(run, sessions, report)
        parsed = Page(page)
        self.assertIn('dialogues', parsed.ids)
        self.assertGreaterEqual(page.count('href="#dialogues"'), 2)
        self.assertIn('Запросы и ответы', page)
        self.assertIn('Ответ · Тестовый продукт', page)
        self.assertIn('Покажи свободное время.\nПосле 18:00.', page)
        self.assertIn('data-download-dialogues="txt"', page)
        self.assertIn('data-download-dialogues="json"', page)
        self.assertFalse(set(parsed.hrefs) - set(parsed.ids))
        self.assertFalse(parsed.external)
        payload = json.loads(re.search(r'<script type="application/json" id="report-data">(.*?)</script>', page, re.S).group(1))
        self.assertEqual(len(payload['dialogues']), 2)
        self.assertEqual(payload['dialogues'][0]['messages'][0]['text'], sessions[0]['transcript']['messages'][0]['text'])
        self.assertEqual(payload['people'][0]['sessions'][0]['dialogue_anchor'], 'dialogue-1')

    def test_messages_and_observations_are_not_truncated(self):
        run, sessions, report = with_transcript()
        message = 'Строка ответа\n' * 250 + 'КОНЕЦ ДЛИННОГО ОТВЕТА'
        observation = 'Наблюдение\n' * 250 + 'КОНЕЦ НАБЛЮДЕНИЯ'
        sessions[0]['transcript']['messages'][1]['text'] = message
        sessions[0]['events'][0]['observation']['text'] = observation
        page = render_html(run, sessions, report)
        self.assertIn(message, page)
        self.assertIn(observation, page)
        self.assertIn('white-space:pre-wrap', page)

    def test_hostile_message_is_text_not_active_markup(self):
        run, sessions, report = with_transcript()
        bad = '</script><script>alert(1)</script><img src=x onerror=alert(2)>'
        sessions[0]['transcript']['messages'][1]['text'] = bad
        sessions[0]['conversation_url'] = 'javascript:alert(3)'
        sessions[0]['transcript']['product_name'] = bad
        page = render_html(run, sessions, report)
        parsed = Page(page)
        self.assertEqual(len(parsed.scripts), 2)
        self.assertFalse(parsed.external)
        self.assertNotIn('href="javascript:', page)
        self.assertIn('&lt;/script&gt;&lt;script&gt;alert(1)', page)
        self.assertIn('\\u003c/script\\u003e', page)

    def test_pending_and_legacy_never_invent_dialogues(self):
        page = render_html(*with_transcript(status='pending'))
        self.assertIn('Отдельная выгрузка сообщений не сохранена', page)
        self.assertNotIn('class="dialogue-record"', page)
        self.assertNotIn('Есть время в 19:00', page)
        run, sessions, report = specimen()
        sessions[0]['feedback'] = {}
        sessions[0]['events'][0]['observation']['text'] = 'Только запись экрана, без отделённых сообщений.'
        page = render_html(run, sessions, report)
        self.assertIn('Отдельная выгрузка сообщений не сохранена', page)
        self.assertIn('Только запись экрана, без отделённых сообщений.', page)
        self.assertNotIn('class="dialogue-record"', page)

    def test_partial_visit_messages_are_retained_and_new_sources_reachable(self):
        run, sessions, report = with_transcript(status='abandoned')
        sessions[0]['status'] = 'completed'
        sessions[0]['feedback']['outcome'] = 'partial'
        sessions[0]['events'].append({'id': 'extra-event', 'observation': {'text': 'Фактический ответ', 'url': 'https://example.test'}, 'action': {}, 'result': {}})
        sessions[0]['transcript']['messages'][1]['event_ids'] = ['extra-event', 'not-a-real-event']
        page = render_html(run, sessions, report)
        self.assertIn('href="#session-1-event-2"', page)
        self.assertIn('id="session-1-event-2"', page)
        self.assertNotIn('href="#not-a-real-event"', page)
        self.assertEqual(page.count('class="dialogue-record"'), 2)
        self.assertIn('class="dialogue-status">Частичный результат', page)
        self.assertLess(page.index('class="message-text"'), page.index('class="dialogue-source"'))


if __name__ == '__main__':
    unittest.main()
