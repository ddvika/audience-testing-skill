"""Budget, transport, persistence and untrusted-output tests; no network calls."""

import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import traceback
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audience_core.openrouter import (AudienceError, BudgetExceeded, OpenRouterClient,
                                     _NoRedirect, _http_transport,
                                     estimate_request_cost, model_eligibility, model_prices)


def model(**changes):
    result = {"id": "example/test-model", "context_length": 32768,
              "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
              "pricing": {"prompt": "0.000001", "completion": "0.000002", "request": "0"},
              "supported_parameters": ["max_tokens", "response_format"],
              "top_provider": {"context_length": 32768, "max_completion_tokens": 4096}}
    result.update(changes)
    return result


MESSAGES = [{"role": "user", "content": "Return a JSON object about this draft."}]


def completion(content='{"ok": true}', cost=0.0001, **extra):
    data = {"model": "example/returned-model", "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}}
    if cost is not None:
        data["usage"]["cost"] = cost
    data.update(extra)
    return 200, json.dumps(data).encode()


class FakeTransport:
    def __init__(self, response=None):
        self.response = completion() if response is None else response
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class CatalogueTests(unittest.TestCase):
    def test_catalogue_is_complete_unfiltered_and_unauthenticated(self):
        records = [model(), {"id": "image/model", "architecture": {"output_modalities": ["image"]}},
                   {"id": "future/model", "pricing": {"prompt": "-1"}}]
        transport = FakeTransport((200, json.dumps({"data": records}).encode()))
        client = OpenRouterClient(api_key="secret-key", _transport=transport)
        self.assertEqual(client.list_models(), records)
        request = transport.calls[0][0]
        self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/models?output_modalities=all")
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(client.ledger, [])

    def test_catalogue_does_not_require_key(self):
        with patch.dict(os.environ, {}, clear=True):
            client = OpenRouterClient(_transport=FakeTransport((200, b'{"data":[]}')))
            self.assertEqual(client.list_models(), [])
            with self.assertRaises(AudienceError):
                client.complete_json(model(), MESSAGES)

    def test_candidate_tariffs_and_modalities(self):
        self.assertEqual(model_prices(model())["prompt"], Decimal("0.000001"))
        self.assertTrue(model_eligibility(model())[0])
        invalid = [model(context_length=8000),
                   model(architecture={"input_modalities": ["text"], "output_modalities": ["text", "image"]}),
                   model(endpoints=["/api/v1/embeddings"]), model(id="example/test-model:online")]
        for bad_price in ["-1", "NaN", "Infinity", None, True, "unpriced"]:
            candidate = model()
            candidate["pricing"]["prompt"] = bad_price
            invalid.append(candidate)
        for key, price in [("request", "-1"), ("internal_reasoning", "0.1"),
                           ("input_cache_write", "0.0000001"), ("future_tariff", "0.001"),
                           ("overrides", [{"min_prompt_tokens": 20000, "prompt": "1"}])]:
            candidate = model()
            candidate["pricing"][key] = price
            invalid.append(candidate)
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                self.assertFalse(model_eligibility(candidate)[0])
        safe = model()
        safe["pricing"].update(image="0.01", web_search="0.01", input_cache_read="0.0000001")
        self.assertTrue(model_eligibility(safe)[0])

    def test_optional_search_price_is_inactive_but_intrinsic_search_is_refused(self):
        candidate = model(id="openai/gpt-4.1-mini")
        candidate["pricing"]["web_search"] = "0.01"
        self.assertTrue(model_eligibility(candidate)[0])
        transport = FakeTransport()
        client = OpenRouterClient("key", _transport=transport)
        client.complete_json(candidate, MESSAGES)
        payload = json.loads(transport.calls[0][0].data)
        self.assertTrue({"tools", "plugins", "web_search_options"}.isdisjoint(payload))
        for identifier in ["openai/gpt-4.1-mini:online", "perplexity/sonar", "perplexity/sonar-pro",
                           "openai/gpt-4o-mini-search-preview"]:
            self.assertFalse(model_eligibility(model(id=identifier))[0], identifier)


class RequestTests(unittest.TestCase):
    def test_payload_caps_correct_units_and_records_actual_usage(self):
        candidate = model()
        candidate["pricing"]["request"] = "0.0005"
        transport = FakeTransport(completion(cost=0.0006))
        client = OpenRouterClient("test-api-key", _transport=transport)
        self.assertEqual(client.complete_json(candidate, MESSAGES, 500), {"ok": True})
        request = transport.calls[0][0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-api-key")
        self.assertEqual(body["provider"]["max_price"], {"prompt": 1, "completion": 2, "request": 0.0005})
        self.assertTrue(body["provider"]["require_parameters"])
        self.assertFalse(body["provider"]["allow_fallbacks"])
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertNotIn("tools", body)
        self.assertNotIn("plugins", body)
        self.assertNotIn("usage", body)
        self.assertAlmostEqual(client.spent_usd, 0.0006)
        self.assertAlmostEqual(client.budget_remaining, 0.9994)
        entry = client.ledger[0]
        self.assertEqual(entry["requested_model"], "example/test-model")
        self.assertEqual(entry["returned_model"], "example/returned-model")
        self.assertEqual(entry["cost_status"], "actual")
        self.assertEqual(entry["usage"]["total_tokens"], 30)
        client.ledger[0]["cost_usd"] = 0  # Returned ledger is a defensive copy.
        self.assertEqual(client.ledger[0]["cost_usd"], 0.0006)

    def test_json_mode_only_when_catalogue_advertises_parameter(self):
        for params in [[], ["tools"], ["structured_outputs"], None]:
            transport = FakeTransport()
            client = OpenRouterClient("key", _transport=transport)
            client.complete_json(model(supported_parameters=params), MESSAGES)
            self.assertNotIn("response_format", json.loads(transport.calls[0][0].data))

    def test_fenced_json_and_strict_root(self):
        for valid in ['{"a": 1}', '  ```json\n{"a": 1}\n```  ', '```\n{"a": 1}\n```']:
            client = OpenRouterClient("key", _transport=FakeTransport(completion(valid)))
            self.assertEqual(client.complete_json(model(), MESSAGES), {"a": 1})
        for invalid in ['[]', 'null', '42', 'Here is JSON: {"a": 1}', '{"a":1} trailing',
                        '```json\n{"a":1}\n``` extra', '{"a":1,"a":2}', '{"a":NaN}']:
            transport = FakeTransport(completion(invalid))
            client = OpenRouterClient("key", _transport=transport)
            with self.assertRaises(AudienceError):
                client.complete_json(model(), MESSAGES)
            self.assertEqual(len(transport.calls), 1)
            self.assertEqual(client.ledger[0]["cost_status"], "actual")
            self.assertEqual(client.ledger[0]["status"], "error")

    def test_plain_text_only_and_utf8_conservative_input(self):
        messages = [{"role": "user", "content": "Привет 👋"}]
        encoded = json.dumps(messages, ensure_ascii=False, separators=(",", ":")).encode()
        expected = (len(encoded) + 1024 + 64) * Decimal("0.000001") + 1200 * Decimal("0.000002")
        self.assertEqual(estimate_request_cost(model(), messages), expected)
        for bad in [[{"role": "user", "content": [{"type": "image_url", "image_url": "secret"}]}],
                    [{"role": "user", "content": "text", "tools": ["run_shell"]}],
                    [{"role": "user", "content": "\ud800"}]]:
            transport = FakeTransport()
            client = OpenRouterClient("key", _transport=transport)
            with self.assertRaises(AudienceError):
                client.complete_json(model(), bad)
            self.assertEqual(transport.calls, [])


class BudgetTests(unittest.TestCase):
    def test_preflight_blocks_before_network(self):
        transport = FakeTransport()
        client = OpenRouterClient("key", budget_usd=0.00001, _transport=transport)
        with self.assertRaises(BudgetExceeded):
            client.complete_json(model(), MESSAGES)
        self.assertEqual(transport.calls, [])
        self.assertEqual(client.ledger, [])

    def test_concurrent_reservations_prevent_overspend(self):
        candidate = model(pricing={"prompt": "0", "completion": "0", "request": "0.6"})
        in_transport = threading.Event()
        release = threading.Event()
        calls = []
        def transport(request, timeout):
            calls.append(request)
            in_transport.set()
            self.assertTrue(release.wait(5))
            return completion(cost=0.6)
        client = OpenRouterClient("key", budget_usd=1, _transport=transport)
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(client.complete_json, candidate, MESSAGES)
            self.assertTrue(in_transport.wait(5))
            second = executor.submit(client.complete_json, candidate, MESSAGES)
            with self.assertRaises(BudgetExceeded):
                second.result(timeout=5)
            self.assertEqual(client.spent_usd, 0.6)
            self.assertEqual(client.budget_remaining, 0.4)
            release.set()
            self.assertEqual(first.result(timeout=5), {"ok": True})
        self.assertEqual(len(calls), 1)

    def test_missing_cost_uses_visible_estimate(self):
        client = OpenRouterClient("key", _transport=FakeTransport(completion(cost=None)))
        client.complete_json(model(), MESSAGES)
        self.assertEqual(client.spent_usd, float(estimate_request_cost(model(), MESSAGES)))
        self.assertEqual(client.ledger[0]["cost_status"], "estimated")

    def test_ambiguous_failure_holds_reservation_without_retry(self):
        candidate = model(pricing={"prompt": "0", "completion": "0", "request": "0.6"})
        for response in [TimeoutError("possibly billed"), (503, b"unsafe body"), (200, b"broken JSON")]:
            transport = FakeTransport(response)
            client = OpenRouterClient("key", budget_usd=1, _transport=transport)
            with self.assertRaises(AudienceError):
                client.complete_json(candidate, MESSAGES)
            with self.assertRaises(BudgetExceeded):
                client.complete_json(candidate, MESSAGES)
            self.assertEqual(len(transport.calls), 1)
            self.assertEqual(client.ledger[0]["cost_status"], "unknown")
            self.assertIsNone(client.ledger[0]["cost_usd"])
            self.assertEqual(client.spent_usd, 0.6)

    def test_definitive_auth_rejection_releases_reservation(self):
        client = OpenRouterClient("key", _transport=FakeTransport((401, b"private body")))
        with self.assertRaises(AudienceError):
            client.complete_json(model(), MESSAGES)
        self.assertEqual(client.spent_usd, 0)
        self.assertEqual(client.ledger[0]["cost_status"], "not_charged")

    def test_reported_cost_breach_stops_future_calls(self):
        transport = FakeTransport(completion(cost=2))
        client = OpenRouterClient("key", _transport=transport)
        with self.assertRaises(BudgetExceeded):
            client.complete_json(model(), MESSAGES)
        with self.assertRaises(BudgetExceeded):
            client.complete_json(model(), MESSAGES)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(client.spent_usd, 2)
        self.assertEqual(client.budget_remaining, 0)
        self.assertTrue(client.ledger[0]["budget_bound_exceeded"])


class SafetyAndPersistenceTests(unittest.TestCase):
    def test_http_and_transport_errors_never_expose_secrets(self):
        secret = "sk-or-v1-test-secret-never-persist"
        messages = [{"role": "user", "content": "private-survey-answer"}]
        for response in [(503, (secret + " injected-error").encode()), RuntimeError(secret)]:
            client = OpenRouterClient(secret, _transport=FakeTransport(response))
            try:
                client.complete_json(model(), messages)
            except AudienceError:
                visible = traceback.format_exc() + json.dumps(client.ledger)
            self.assertNotIn(secret, visible)
            self.assertNotIn("private-survey-answer", visible)
            self.assertNotIn("injected-error", visible)

    def test_ledger_whitelists_usage_and_redacts_identifier_secrets(self):
        secret = "sk-or-v1-test-secret"
        response = completion(model=secret, usage={"cost": 0.0001, "prompt_tokens": 12,
                              "secret": secret, "prompt_tokens_details": {"cached_tokens": 4, "injection": secret}})
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.json"
            client = OpenRouterClient(secret, ledger_path=ledger, _transport=FakeTransport(response))
            client.complete_json(model(), [{"role": "user", "content": "raw-sensitive-question"}])
            saved = ledger.read_text()
            self.assertNotIn(secret, saved)
            self.assertNotIn("raw-sensitive-question", saved)
            self.assertNotIn('"choices"', saved)
            self.assertNotIn('"content"', saved)
            self.assertEqual(client.ledger[0]["returned_model"], "[redacted]")
            self.assertEqual(client.ledger[0]["usage"]["prompt_tokens_details"], {"cached_tokens": 4})
            self.assertEqual(ledger.stat().st_mode & 0o777, 0o600)
            client.close()

    def test_budget_and_unknown_reservation_survive_resume(self):
        candidate = model(pricing={"prompt": "0", "completion": "0", "request": "0.6"})
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.json"
            with OpenRouterClient("key", ledger_path=ledger, _transport=FakeTransport(TimeoutError())) as first:
                with self.assertRaises(AudienceError):
                    first.complete_json(candidate, MESSAGES)
            with OpenRouterClient("key", ledger_path=ledger, _transport=FakeTransport()) as second:
                self.assertEqual(second.spent_usd, 0.6)
                self.assertEqual(second.ledger[0]["cost_status"], "unknown")
                with self.assertRaises(BudgetExceeded):
                    second.complete_json(candidate, MESSAGES)
            with self.assertRaises(AudienceError):
                OpenRouterClient("key", budget_usd=2, ledger_path=ledger)

    def test_ledger_refuses_overlapping_process_writers(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.json"
            with OpenRouterClient("key", ledger_path=ledger):
                script = ("from audience_core.openrouter import OpenRouterClient, AudienceError\n"
                          "import sys\ntry:\n OpenRouterClient('key', ledger_path=sys.argv[1])\n"
                          "except AudienceError:\n sys.exit(0)\nelse:\n sys.exit(1)\n")
                env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
                result = subprocess.run([sys.executable, "-c", script, str(ledger)],
                                        env=env, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_redirects_are_refused_and_http_body_is_not_read(self):
        request = Request("https://openrouter.ai/api/v1/chat/completions", data=b"{}",
                          headers={"Authorization": "Bearer private-key"})
        self.assertIsNone(_NoRedirect().redirect_request(request, None, 302, "Found", {}, "https://evil.invalid"))
        body = io.BytesIO(b"secret body")
        error = HTTPError(request.full_url, 302, "Found", {"Location": "https://evil.invalid"}, body)
        opener = unittest.mock.Mock()
        opener.open.side_effect = error
        with patch("audience_core.openrouter.build_opener", return_value=opener):
            self.assertEqual(_http_transport(request, 1), (302, b""))
        self.assertTrue(body.closed)
        self.assertEqual(opener.open.call_count, 1)


if __name__ == "__main__":
    unittest.main()
