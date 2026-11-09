"""Small, stdlib-only OpenRouter client with conservative, shared budget accounting.

Only plain-text chat requests are supported. A reservation counts against the
budget *before* any network operation, including concurrently running calls.
Unknown bills keep their reservations and are never retried automatically.
``spent_usd`` is accounted spending: actual charges plus estimates/reservations,
not a claim that every reserved dollar has been charged by OpenRouter.

Provider price ceilings bound routing rates, not an independently enforceable
account spending limit. The byte-based input estimate includes a generous chat
template allowance; provider-side accounting remains authoritative. Set an
OpenRouter key credit limit as an additional account-side safeguard if needed.
"""

from __future__ import annotations

import copy
import fcntl
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_ORIGIN = "https://openrouter.ai"
MODELS_URL = API_ORIGIN + "/api/v1/models?output_modalities=all"
COMPLETIONS_URL = API_ORIGIN + "/api/v1/chat/completions"
MIN_CONTEXT = 16_000
_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,299}\Z")
_DEFINITIVE_REJECTIONS = {400, 401, 402, 403, 404, 405, 413, 415, 422, 429}


class AudienceError(Exception):
    """A safe, user-facing error that never includes provider response bodies."""


class BudgetExceeded(AudienceError):
    """A request would exceed the budget or provider accounting broke its bound."""


class _RequestFailure(AudienceError):
    def __init__(self, message, *, rejected=False):
        super().__init__(message)
        self.rejected = rejected


def _money(value, label="price"):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise AudienceError("Missing or unsupported " + label + ".")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise AudienceError("Missing or unsupported " + label + ".") from None
    if not result.is_finite() or result < 0 or result > Decimal("1e12"):
        raise AudienceError("Missing or unsupported " + label + ".")
    return result


def model_prices(model: dict) -> dict:
    """Return finite flat prompt/completion USD/token and request USD/request.

Prices for features absent from our text-only payload cannot be incurred.
Separate reasoning/cache-write fees and conditional tariffs are not safely
bounded by our provider ceilings and are deliberately rejected.
"""
    if not isinstance(model, dict) or not isinstance(model.get("pricing"), dict):
        raise AudienceError("Model has no usable pricing metadata.")
    pricing = model["pricing"]
    prices = {name: _money(pricing.get(name), name + " price")
              for name in ("prompt", "completion")}
    prices["request"] = _money(pricing.get("request", "0"), "request price")
    inactive = {"image", "image_token", "image_output", "audio", "audio_output",
                "input_audio_cache", "web_search"}
    for name, value in pricing.items():
        if name in prices:
            continue
        if name == "overrides":
            if value not in (None, []):
                raise AudienceError("Conditional pricing is not supported by this budget guard.")
            continue
        rate = _money(value, "additional tariff")
        if name in inactive:
            continue
        if name == "input_cache_read" and rate <= prices["prompt"]:
            continue
        if name == "input_cache_write" and rate:
            raise AudienceError("Cache-write pricing is not supported by this budget guard.")
        if name == "internal_reasoning" and rate:
            raise AudienceError("Separate reasoning pricing has no universally supported token cap.")
        if rate != 0:
            raise AudienceError("Additional tariff cannot be safely capped.")
    return prices


def _context_length(model):
    value = model.get("context_length")
    if isinstance(value, bool) or not isinstance(value, int) or value < MIN_CONTEXT:
        raise AudienceError("Model needs a context window of at least 16000 tokens.")
    top = model.get("top_provider")
    if isinstance(top, dict):
        provider_context = top.get("context_length")
        if isinstance(provider_context, int) and not isinstance(provider_context, bool):
            value = min(value, provider_context)
    if value < MIN_CONTEXT:
        raise AudienceError("Model provider needs at least 16000 context tokens.")
    return value


def model_eligibility(model: dict) -> tuple[bool, str]:
    """Conservative automatic candidate gate; the full catalogue stays unfiltered."""
    try:
        if not isinstance(model, dict):
            raise AudienceError("Model metadata must be an object.")
        model_id = model.get("id")
        if not isinstance(model_id, str) or not _IDENTIFIER.fullmatch(model_id):
            raise AudienceError("Model identifier is invalid.")
        # Optional web_search catalogue prices do not activate a search. This
        # client sends no tools/plugins/web_search_options. Intrinsic search
        # products and routing suffixes can search without those parameters.
        if (":online" in model_id.lower()
                or model_id.lower().startswith("perplexity/sonar")
                or re.search(r"(?:^|[-_:])(?:search|deep-research)(?:$|[-_:])", model_id.lower().split("/", 1)[-1])):
            raise AudienceError("Search-enabled model variants have uncapped auxiliary costs.")
        architecture = model.get("architecture")
        if not isinstance(architecture, dict):
            raise AudienceError("Model modalities are unknown.")
        if architecture.get("output_modalities") != ["text"]:
            raise AudienceError("Model must produce only text output.")
        inputs = architecture.get("input_modalities")
        if not isinstance(inputs, list) or "text" not in inputs:
            raise AudienceError("Model must accept text input.")
        endpoints = model.get("endpoints")
        if endpoints is not None and (not isinstance(endpoints, list)
                                      or "/api/v1/chat/completions" not in endpoints):
            raise AudienceError("Model does not serve chat completions.")
        _context_length(model)
        model_prices(model)
        return True, "eligible"
    except AudienceError as exc:
        return False, str(exc)


def _validated_messages(messages):
    if not isinstance(messages, list) or not messages:
        raise AudienceError("Messages must be a nonempty list of plain-text messages.")
    result = []
    for message in messages:
        if (not isinstance(message, dict) or set(message) != {"role", "content"}
                or message.get("role") not in {"system", "user", "assistant"}
                or not isinstance(message.get("content"), str)):
            raise AudienceError("Only role/content plain-text chat messages are supported.")
        result.append({"role": message["role"], "content": message["content"]})
    return result


def _input_bound(messages):
    try:
        serialized = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
        return len(serialized.encode("utf-8")) + 1024 + 64 * len(messages)
    except (ValueError, UnicodeError, TypeError):
        raise AudienceError("Messages cannot be encoded as UTF-8 JSON.") from None


def estimate_request_cost(model: dict, messages: list, max_tokens=1200) -> Decimal:
    """Use UTF-8 bytes as token bound, plus 1024 + 64/message template tokens."""
    eligible, reason = model_eligibility(model)
    if not eligible:
        raise AudienceError(reason)
    messages = _validated_messages(messages)
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
        raise AudienceError("max_tokens must be a positive integer.")
    tokens = _input_bound(messages)
    if tokens + max_tokens > _context_length(model):
        raise AudienceError("Conservative request size exceeds the model context window.")
    top = model.get("top_provider")
    completion_limit = top.get("max_completion_tokens") if isinstance(top, dict) else None
    if isinstance(completion_limit, int) and max_tokens > completion_limit:
        raise AudienceError("Requested output exceeds the provider completion limit.")
    prices = model_prices(model)
    return tokens * prices["prompt"] + max_tokens * prices["completion"] + prices["request"]


def _reject_constant(_value):
    raise ValueError("Non-finite JSON constant")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _loads(value):
    return json.loads(value, parse_constant=_reject_constant, object_pairs_hook=_unique_object)


def _json_object(content):
    if not isinstance(content, str):
        raise AudienceError("OpenRouter response has no plain-text JSON content.")
    content = content.strip()
    if content.startswith("```"):
        fenced = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n?```", content, re.DOTALL | re.IGNORECASE)
        if not fenced:
            raise AudienceError("Model returned malformed JSON fencing.")
        content = fenced.group(1).strip()
    try:
        result = _loads(content)
    except (ValueError, TypeError, RecursionError):
        raise AudienceError("Model returned invalid JSON; billed calls are not retried.") from None
    if not isinstance(result, dict):
        raise AudienceError("Model JSON must contain an object at its root.")
    return result


def _canonical_action_object(item):
    """Normalize only documented action/feedback fields, without judging success."""
    if not isinstance(item, dict):
        raise AudienceError('Model returned no action object.')
    action = item.get('action')
    flat = isinstance(action, str)
    kind = action if flat else action.get('type') if isinstance(action, dict) else None
    if not isinstance(kind, str) or kind not in {'click', 'fill', 'select', 'scroll', 'back', 'navigate', 'wait', 'finish'}:
        raise AudienceError('Model returned an unsupported action.')
    allowed = {'action', 'feedback', 'block'}
    if flat:
        allowed |= {'target', 'value', 'url', 'amount', 'seconds'}
    feedback_fields = {'outcome', 'stop_reason', 'summary', 'evidence_ids', 'rating',
                       'likes', 'dislikes', 'return_intent', 'assessment', 'journey', 'recommendations'}
    if kind == 'finish':
        allowed |= feedback_fields
    if set(item) - allowed:
        raise AudienceError('Model action contains unsupported fields.')
    flattened = set(item) & feedback_fields if kind == 'finish' else set()
    if flattened:
        if 'feedback' in item or isinstance(action, dict) and 'feedback' in action:
            raise AudienceError('Model returned ambiguous feedback fields.')
        feedback = {key: item[key] for key in flattened}
        item = {key: value for key, value in item.items() if key not in flattened}
        # Exact relocation only: outcome/evidence/rating are still checked by
        # the engine, including proof that the task was actually executed.
        item['feedback'] = feedback
    return item


def _action_object(content):
    """Read one action; tolerate only a fully valid stream of action objects.

    Some providers emit a fill followed by a speculative click in one response.
    Parse the *entire* response before returning its first object. The remaining
    objects are discarded, never queued: the executor must observe the browser
    again and validate the returned action against that current observation.
    Planning/synthesis never use this parser. This is syntax normalization only;
    the engine remains responsible for target, permission and feedback checks.
    """
    try:
        return _canonical_action_object(_json_object(content)), 1
    except AudienceError as original:
        if not isinstance(content, str):
            raise original
        source = content.strip()
        if source.startswith('```'):
            raise original
        decoder = json.JSONDecoder(parse_constant=_reject_constant,
                                   object_pairs_hook=_unique_object)
        objects = []
        position = 0
        try:
            while position < len(source):
                item, end = decoder.raw_decode(source, position)
                item = _canonical_action_object(item)
                objects.append(item)
                if len(objects) > 16:
                    raise ValueError('Too many action objects')
                position = end
                while position < len(source) and source[position].isspace():
                    position += 1
        except (AudienceError, ValueError, TypeError, RecursionError):
            raise original from None
        if len(objects) < 2:
            raise original
        return objects[0], len(objects)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a bearer header, even to another OpenRouter URL.
        return None


def _http_transport(request, timeout):
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
            return response.status, raw
    except HTTPError as exc:
        # Do not read, log, interpolate, or attach provider error bodies.
        status = exc.code
        exc.close()
        return status, b""


def _safe_usage(usage):
    """Keep numeric accounting only, never arbitrary strings/provider metadata."""
    if not isinstance(usage, dict):
        return {}
    number_keys = {"prompt_tokens", "completion_tokens", "total_tokens", "cost",
                   "cached_tokens", "cache_write_tokens", "audio_tokens", "reasoning_tokens",
                   "upstream_inference_cost", "upstream_inference_prompt_cost",
                   "upstream_inference_completions_cost", "upstream_inference_input_cost",
                   "upstream_inference_output_cost"}
    nested_keys = {"prompt_tokens_details", "completion_tokens_details", "cost_details"}
    safe = {}
    for key, value in usage.items():
        if key in number_keys:
            try:
                number = _money(value, "usage value")
                safe[key] = int(number) if number == number.to_integral_value() else float(number)
            except AudienceError:
                continue
        elif key in nested_keys and isinstance(value, dict):
            safe[key] = _safe_usage(value)
        elif key == "is_byok" and isinstance(value, bool):
            safe[key] = value
    return safe


class OpenRouterClient:
    def __init__(self, api_key=None, budget_usd=1.0, timeout=60, ledger_path=None, *, _transport=None):
        self._api_key = os.environ.get("OPENROUTER_API_KEY", "") if api_key is None else api_key
        if (not isinstance(self._api_key, str) or len(self._api_key) > 8192
                or any(ord(char) < 33 or ord(char) > 126 for char in self._api_key)):
            raise AudienceError("OpenRouter API key has an invalid format.")
        self._budget = _money(budget_usd, "budget")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise AudienceError("Timeout must be a positive finite number.")
        self._timeout = timeout
        self._transport = _transport or _http_transport
        self._lock = threading.RLock()
        self._entries = []
        self._charges = []  # Decimal, never round currency for budget decisions.
        self._halted = False
        self._closed = False
        self._deadline_monotonic = None
        self._response_diagnostics = []
        self._ledger_lock_handle = None
        self._ledger_path = Path(ledger_path) if ledger_path is not None else None
        if self._ledger_path is not None:
            # A ledger belongs to one live client/process. Its threads share the
            # RLock. Holding flock until close/exit makes sequential CLI resumes
            # safe without permitting independent clients to reset the budget.
            try:
                descriptor = os.open(str(self._ledger_path) + ".lock",
                                     os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
                self._ledger_lock_handle = os.fdopen(descriptor, "a+")
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if self._ledger_path.exists():
                    self._restore()
                self._persist()
            except (OSError, AudienceError):
                if self._ledger_lock_handle is not None:
                    self._ledger_lock_handle.close()
                    self._ledger_lock_handle = None
                raise AudienceError("Cannot open budget ledger: it is in use, invalid, or has a different budget.") from None

    def close(self):
        """Release the process lock after all concurrent requests have finished."""
        with self._lock:
            if any(entry["cost_status"] == "reserved" for entry in self._entries):
                raise AudienceError("Cannot close the client while requests are pending.")
            self._closed = True
            if self._ledger_lock_handle is not None:
                self._ledger_lock_handle.close()
                self._ledger_lock_handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def _restore(self):
        try:
            data = _loads(self._ledger_path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("version") != 1
                    or _money(data.get("budget_usd"), "ledger budget") != self._budget
                    or not isinstance(data.get("halted"), bool)
                    or not isinstance(data.get("ledger"), list)
                    or not isinstance(data.get("accounted_exact"), list)
                    or len(data["ledger"]) != len(data["accounted_exact"])):
                raise ValueError("Invalid ledger")
            self._halted = data["halted"]
            for previous, exact in zip(data["ledger"], data["accounted_exact"]):
                amount = _money(exact, "ledger amount")
                if (not isinstance(previous, dict)
                        or previous.get("cost_status") not in {"reserved", "actual", "estimated", "unknown", "not_charged"}
                        or previous.get("status") not in {"pending", "complete", "error"}):
                    raise ValueError("Invalid ledger entry")
                entry = {"sequence": len(self._entries) + 1,
                         "requested_model": self._identifier(previous.get("requested_model")),
                         "returned_model": self._identifier(previous.get("returned_model")),
                         "accounted_usd": float(amount), "usage": _safe_usage(previous.get("usage")),
                         "status": previous["status"], "cost_status": previous["cost_status"]}
                for key in ("timestamp", "input_token_bound", "max_tokens"):
                    value = previous.get(key)
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        raise ValueError("Invalid ledger counter")
                    entry[key] = value
                entry["reserved_usd"] = float(_money(previous.get("reserved_usd"), "ledger reservation"))
                cost = previous.get("cost_usd")
                entry["cost_usd"] = None if cost is None else float(_money(cost, "ledger cost"))
                if previous.get("budget_bound_exceeded") is True:
                    entry["budget_bound_exceeded"] = True
                    self._halted = True
                if entry["cost_status"] == "reserved":
                    entry.update(status="error", cost_status="unknown", cost_usd=None, error="interrupted_call")
                elif entry["status"] == "error":
                    entry["error"] = "previous_call_error"
                self._entries.append(entry)
                self._charges.append(amount)
            if sum(self._charges, Decimal(0)) > self._budget:
                self._halted = True
        except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            raise AudienceError("Existing budget ledger is invalid.") from None

    @property
    def spent_usd(self):
        with self._lock:
            return float(sum(self._charges, Decimal(0)))

    @property
    def budget_remaining(self):
        with self._lock:
            return float(max(Decimal(0), self._budget - sum(self._charges, Decimal(0))))

    @property
    def ledger(self):
        with self._lock:
            return copy.deepcopy(self._entries)

    @property
    def response_diagnostics(self):
        """Private action-response audit, separate from the numeric cost ledger.

        Hosts may redact and persist these with their run evidence. This never
        includes request prompts, HTTP headers or provider error bodies.
        """
        with self._lock:
            return copy.deepcopy(self._response_diagnostics)

    def set_deadline(self, deadline_monotonic):
        if (isinstance(deadline_monotonic, bool)
                or not isinstance(deadline_monotonic, (int, float))
                or not math.isfinite(deadline_monotonic)):
            raise AudienceError('Deadline must be a finite monotonic timestamp.')
        with self._lock:
            self._deadline_monotonic = float(deadline_monotonic)

    def _request_timeout(self):
        remaining = (self._timeout if self._deadline_monotonic is None else
                     min(self._timeout, self._deadline_monotonic - time.monotonic()))
        if remaining <= 0:
            raise _RequestFailure('Study time limit reached; no request was sent.', rejected=True)
        return remaining

    def _identifier(self, value):
        if not isinstance(value, str):
            return None
        if self._api_key and self._api_key in value:
            return "[redacted]"
        return value if _IDENTIFIER.fullmatch(value) else "[invalid identifier]"

    def _persist(self):
        if self._ledger_path is None:
            return
        temporary = None
        try:
            descriptor, temporary = tempfile.mkstemp(prefix=".audience-ledger-", dir=self._ledger_path.parent)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                document = {"version": 1, "budget_usd": str(self._budget), "halted": self._halted,
                            "accounted_exact": [str(amount) for amount in self._charges],
                            "ledger": self._entries}
                json.dump(document, handle, ensure_ascii=False, allow_nan=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._ledger_path)
        except OSError:
            self._halted = True
            raise AudienceError("Budget ledger could not be saved; further requests are disabled.") from None
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass

    def _reserve(self, model, amount, input_tokens, max_tokens):
        with self._lock:
            self._request_timeout()
            if self._closed:
                raise AudienceError("OpenRouter client has been closed.")
            if self._halted:
                raise BudgetExceeded("Further requests are disabled after an accounting error.")
            if sum(self._charges, Decimal(0)) + amount > self._budget:
                raise BudgetExceeded("Conservative request reservation exceeds the remaining budget.")
            index = len(self._entries)
            self._charges.append(amount)
            self._entries.append({"sequence": index + 1, "requested_model": self._identifier(model["id"]),
                                  "returned_model": None, "timestamp": int(time.time()),
                                  "input_token_bound": input_tokens, "max_tokens": max_tokens,
                                  "reserved_usd": float(amount), "accounted_usd": float(amount),
                                  "cost_usd": None, "cost_status": "reserved", "status": "pending", "usage": {}})
            self._persist()
            return index

    def _settle(self, index, *, response=None, rejected=False, error=None):
        with self._lock:
            entry = self._entries[index]
            usage = response.get("usage") if isinstance(response, dict) else None
            actual = None
            if isinstance(usage, dict) and "cost" in usage:
                try:
                    actual = _money(usage["cost"], "reported cost")
                except AudienceError:
                    pass
            entry["usage"] = _safe_usage(usage)
            if isinstance(response, dict):
                entry["returned_model"] = self._identifier(response.get("model"))
            if actual is not None:
                if actual > self._charges[index]:
                    self._halted = True
                    entry["budget_bound_exceeded"] = True
                self._charges[index] = actual
                entry.update(cost_usd=float(actual), cost_status="actual", accounted_usd=float(actual))
            elif rejected:
                self._charges[index] = Decimal(0)
                entry.update(cost_usd=0.0, cost_status="not_charged", accounted_usd=0.0)
            elif response is not None and error is None:
                entry.update(cost_usd=float(self._charges[index]), cost_status="estimated")
            else:
                entry["cost_status"] = "unknown"
            entry["status"] = "error" if error else "complete"
            if error:
                entry["error"] = error  # Internal fixed category, never provider text.
            self._persist()
            if entry.get("budget_bound_exceeded"):
                raise BudgetExceeded("Provider-reported cost exceeded its reservation; further requests are disabled.")

    def _request(self, request):
        timeout = self._request_timeout()
        try:
            status, raw = self._transport(request, timeout)
        except Exception:
            raise _RequestFailure("OpenRouter transport failed; billing is unknown and no retry was made.") from None
        if not isinstance(status, int) or isinstance(status, bool):
            raise _RequestFailure("OpenRouter returned an invalid HTTP status.")
        if not 200 <= status < 300:
            raise _RequestFailure("OpenRouter HTTP " + str(status) + "; no automatic retry was made.",
                                  rejected=status in _DEFINITIVE_REJECTIONS)
        if not isinstance(raw, bytes) or len(raw) > _MAX_RESPONSE_BYTES:
            raise _RequestFailure("OpenRouter returned an invalid or oversized response.")
        try:
            data = _loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError):
            raise _RequestFailure("OpenRouter returned invalid JSON; billing may be unknown.") from None
        if not isinstance(data, dict):
            raise _RequestFailure("OpenRouter response envelope must be an object.")
        return data

    def list_models(self) -> list[dict]:
        # Public endpoint: never attach a key, even when this client has one.
        request = Request(MODELS_URL, headers={"Accept": "application/json", "User-Agent": "Audience/1.0"})
        data = self._request(request)
        models = data.get("data")
        if not isinstance(models, list) or not all(isinstance(item, dict) for item in models):
            raise AudienceError("OpenRouter catalogue has an invalid model list.")
        # No default modality or price filter: callers can inspect every model.
        return models

    def probe_model(self, model: dict) -> bool:
        """One small, accounted request to qualify a catalogue candidate for this account."""
        try:
            reply = self.complete_json(model, [
                {"role": "system", "content": "Return only a JSON object. This checks API availability."},
                {"role": "user", "content": 'Return {"ok":true} exactly.'}], max_tokens=128)
            return reply.get("ok") is True
        except BudgetExceeded:
            raise
        except AudienceError:
            return False

    def complete_json(self, model: dict, messages: list, max_tokens=1200) -> dict:
        return self._complete(model, messages, max_tokens, action_response=False)

    def complete_action(self, model: dict, messages: list, max_tokens=1200) -> dict:
        return self._complete(model, messages, max_tokens, action_response=True)

    def _complete(self, model: dict, messages: list, max_tokens=1200, *, action_response=False) -> dict:
        if not self._api_key:
            raise AudienceError("Set OPENROUTER_API_KEY before running a live audience.")
        # Freeze caller-owned metadata before computing a reservation and caps.
        model = copy.deepcopy(model)
        messages = _validated_messages(messages)
        reservation = estimate_request_cost(model, messages, max_tokens)
        prices = model_prices(model)
        payload = {"model": model["id"], "messages": messages, "max_tokens": max_tokens,
                   "stream": False,
                   "provider": {"require_parameters": True, "allow_fallbacks": False,
                                "max_price": {"prompt": float(prices["prompt"] * 1_000_000),
                                              "completion": float(prices["completion"] * 1_000_000),
                                              "request": float(prices["request"])}}}
        supported = model.get("supported_parameters", [])
        if isinstance(supported, list) and "response_format" in supported:
            payload["response_format"] = {"type": "json_object"}
        try:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
            request = Request(COMPLETIONS_URL, data=body,
                              headers={"Authorization": "Bearer " + self._api_key,
                                       "Content-Type": "application/json", "Accept": "application/json",
                                       "User-Agent": "Audience/1.0"}, method="POST")
        except (ValueError, UnicodeError, TypeError):
            raise AudienceError("Request cannot be encoded as UTF-8 JSON.") from None
        index = self._reserve(model, reservation, _input_bound(messages), max_tokens)
        try:
            response = self._request(request)
        except _RequestFailure as exc:
            self._settle(index, rejected=exc.rejected, error="http_rejected" if exc.rejected else "billing_unknown")
            raise AudienceError(str(exc)) from None
        error = None
        result = None
        content = None
        object_count = 0
        try:
            if "error" in response:
                raise AudienceError("OpenRouter returned an API error; no automatic retry was made.")
            choices = response.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise AudienceError("OpenRouter response has no valid completion choice.")
            message = choices[0].get("message")
            if not isinstance(message, dict):
                raise AudienceError("OpenRouter response has no valid message.")
            content = message.get('content')
            if action_response:
                result, object_count = _action_object(content)
            else:
                result = _json_object(content)
        except AudienceError as exc:
            error = exc
        if action_response:
            # Do not put free-form provider text in the persistent cost ledger.
            # Preserve it separately in memory, redact the known key even if a
            # malicious provider accidentally echoes it, and bound audit size.
            raw = content if isinstance(content, str) else None
            if raw is not None and self._api_key:
                raw = raw.replace(self._api_key, '[REDACTED]')
            with self._lock:
                self._response_diagnostics.append({
                    'sequence': index + 1, 'model': self._identifier(model['id']),
                    'protocol': ('invalid_action_json' if error else
                                 'first_action_only' if object_count > 1 else 'single_object'),
                    'object_count': object_count, 'discarded_actions': max(0, object_count - 1),
                    'raw_content': raw[:65536] if raw is not None else None,
                    'raw_truncated': bool(raw is not None and len(raw) > 65536),
                })
        self._settle(index, response=response, error="invalid_completion" if error else None)
        if error:
            raise error from None
        return result
