"""Action protocol recovery and time limits, with no network or paid calls."""

import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audience_core.openrouter import AudienceError, OpenRouterClient
from audience_core.planner import _planning_messages, _study_details
from test_openrouter import model, completion, FakeTransport, MESSAGES


FILL = {'action': {'type': 'fill', 'target': 'prompt', 'value': 'Сравни два товара'}}
CLICK = {'action': {'type': 'click', 'target': 'send'}}
STREAM = json.dumps(FILL, ensure_ascii=False) + '\n\n' + json.dumps(CLICK)


class ActionProtocolTests(unittest.TestCase):
    def test_flat_finish_feedback_is_relocated_without_changing_values(self):
        fields = {'outcome': 'partial', 'rating': 4, 'summary': 'Нет результата',
                  'evidence_ids': ['s:e001'], 'stop_reason': 'decision_limit',
                  'assessment': {'satisfaction': 2, 'evidence_ids': ['s:e001']}}
        finish = {'action': {'type': 'finish'}, **fields}
        client = OpenRouterClient('test-key', _transport=FakeTransport(completion(json.dumps(finish))))
        self.assertEqual(client.complete_action(model(), MESSAGES),
                         {'action': {'type': 'finish'}, 'feedback': fields})
        self.assertEqual(json.loads(client.response_diagnostics[0]['raw_content']), finish)
        stream = STREAM + '\n' + json.dumps(finish)
        client = OpenRouterClient('test-key', _transport=FakeTransport(completion(stream)))
        self.assertEqual(client.complete_action(model(), MESSAGES), FILL)
        self.assertEqual(client.response_diagnostics[0]['discarded_actions'], 2)
        for bad in ({**finish, 'code': 'evil'}, {**finish, 'feedback': {'outcome': 'success'}}):
            client = OpenRouterClient('test-key', _transport=FakeTransport(completion(json.dumps(bad))))
            with self.assertRaises(AudienceError):
                client.complete_action(model(), MESSAGES)

    def test_flat_and_nested_action_stream_forms_are_both_supported(self):
        flat_fill = {'action': 'fill', 'target': 'prompt', 'value': 'Сравни наушники для метро'}
        flat_click = {'action': 'click', 'target': 'send'}
        for items in ((flat_fill, CLICK), (FILL, flat_click), (flat_fill, flat_click)):
            with self.subTest(items=items):
                stream = '\n\n'.join(json.dumps(item, ensure_ascii=False) for item in items)
                client = OpenRouterClient('test-key', _transport=FakeTransport(completion(stream)))
                self.assertEqual(client.complete_action(model(), MESSAGES), items[0])
                self.assertEqual(client.response_diagnostics[0]['discarded_actions'], 1)
        bad = json.dumps(flat_fill) + '\n' + json.dumps({'action': 'click', 'target': 'send', 'code': 'bad'})
        client = OpenRouterClient('test-key', _transport=FakeTransport(completion(bad)))
        with self.assertRaises(AudienceError):
            client.complete_action(model(), MESSAGES)

    def test_exact_stream_returns_only_first_and_preserves_audit_and_actual_cost(self):
        transport = FakeTransport(completion(STREAM))
        client = OpenRouterClient('test-key', _transport=transport)
        self.assertEqual(client.complete_action(model(), MESSAGES), FILL)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(client.spent_usd, 0.0001)
        diagnostic = client.response_diagnostics[0]
        self.assertEqual(diagnostic['protocol'], 'first_action_only')
        self.assertEqual(diagnostic['discarded_actions'], 1)
        self.assertEqual(diagnostic['raw_content'], STREAM)
        client.response_diagnostics[0]['raw_content'] = 'changed'
        self.assertEqual(client.response_diagnostics[0]['raw_content'], STREAM)

    def test_planner_and_synthesis_remain_strict(self):
        client = OpenRouterClient('test-key', _transport=FakeTransport(completion(STREAM)))
        with self.assertRaises(AudienceError):
            client.complete_json(model(), MESSAGES)
        self.assertEqual(client.ledger[0]['status'], 'error')
        self.assertEqual(client.ledger[0]['cost_status'], 'actual')
        self.assertEqual(client.response_diagnostics, [])

    def test_entire_stream_must_be_valid_before_any_action_is_returned(self):
        for suffix in (' junk', '{', '\n[]', '\n{"ok":true}', '\n{"action":{"type":"exec"}}',
                       '\n{"action":{"type":"click","type":"fill"}}',
                       '\n{"action":{"type":"scroll","amount":NaN}}'):
            with self.subTest(suffix=suffix):
                transport = FakeTransport(completion(STREAM + suffix))
                client = OpenRouterClient('test-key', _transport=transport)
                with self.assertRaises(AudienceError):
                    client.complete_action(model(), MESSAGES)
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(client.response_diagnostics[0]['protocol'], 'invalid_action_json')
                self.assertEqual(client.ledger[0]['cost_status'], 'actual')

    def test_single_object_still_requires_engine_semantic_validation(self):
        unknown = {'action': {'type': 'click', 'target': 'not-in-observation'}}
        client = OpenRouterClient('test-key', _transport=FakeTransport(completion(json.dumps(unknown))))
        self.assertEqual(client.complete_action(model(), MESSAGES), unknown)
        self.assertEqual(client.response_diagnostics[0]['protocol'], 'single_object')

    def test_response_audit_never_enters_numeric_ledger_and_key_is_redacted(self):
        key = 'sk-or-v1-fixture-sensitive'
        content = json.dumps({'action': {'type': 'fill', 'target': 'input', 'value': key}})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'usage.json'
            client = OpenRouterClient(key, ledger_path=path, _transport=FakeTransport(completion(content)))
            client.complete_action(model(), MESSAGES)
            self.assertNotIn(key, json.dumps(client.response_diagnostics))
            self.assertNotIn('raw_content', path.read_text())
            client.close()

    def test_expired_deadline_blocks_before_transport_or_reservation(self):
        transport = FakeTransport()
        client = OpenRouterClient('test-key', _transport=transport)
        client.set_deadline(time.monotonic() - 1)
        with self.assertRaisesRegex(AudienceError, 'time limit'):
            client.complete_action(model(), MESSAGES)
        self.assertEqual(transport.calls, [])
        self.assertEqual(client.ledger, [])

    def test_timeout_is_limited_by_time_left(self):
        transport = FakeTransport()
        client = OpenRouterClient('test-key', timeout=60, _transport=transport)
        client.set_deadline(time.monotonic() + 2)
        client.complete_json(model(), MESSAGES)
        self.assertGreater(transport.calls[0][1], 0)
        self.assertLessEqual(transport.calls[0][1], 2)

    def test_expired_catalogue_request_also_does_not_send(self):
        transport = FakeTransport()
        client = OpenRouterClient('test-key', _transport=transport)
        client.set_deadline(time.monotonic() - 1)
        with self.assertRaises(AudienceError):
            client.list_models()
        self.assertEqual(transport.calls, [])

    def test_default_goal_requires_result_not_empty_screen(self):
        blueprint = {'name': 'Покупатель', 'goal': 'Сравнить варианты по цене', 'segment': 'Выбор'}
        details = _study_details(blueprint, ['first_use', 'resume', 'regular'])
        self.assertIn('пустого экрана', details['success_criteria'][0])
        self.assertIn('новую задачу', details['scenario_goals']['regular'])
        self.assertIn('предыдущую задачу', details['scenario_goals']['resume'])

    def test_planning_prompt_keeps_normal_requests_separate_from_evaluation(self):
        messages = _planning_messages('Проверь помощника', '', {'title': 'Помощник'}, ['first_use'])
        self.assertIn('plain Russian', messages[0]['content'])
        self.assertIn('Do not instruct the product how to pass the test', messages[0]['content'])
        self.assertIn('Opening an empty chat', messages[0]['content'])


if __name__ == '__main__':
    unittest.main()
