"""Optional, host-permitted Playwright driver for Audience sessions.

Use the host's native browser bridge when available. Importing this module does
not import Playwright or start a browser; ``start`` is the only entry point that
does so. A session keeps one browser context across visits and never writes its
storage state. Supply a different session for each independent persona.

This is a conservative, best-effort interaction guard, NOT a security sandbox or
a guarantee that a click is harmless. Labels can be misleading, GET endpoints
can mutate data, and public DNS names can resolve to private addresses. URL
checks reject literal private IPs but cannot prevent DNS rebinding. Production
mode blocks state-changing HTTP methods; this also breaks some read-only APIs.
Third-party GET resources remain possible. WebSockets, service workers, popups,
downloads, uploads, and password entry are disabled. Host/network policy must
provide any stronger isolation required by the environment. Screenshots and
visible page text may still contain personal information already on the page.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit
import uuid


MODES = frozenset({"production", "readonly", "staging"})
ACTION_TYPES = frozenset({"click", "fill", "select", "scroll", "back", "navigate", "wait", "finish"})
MAX_TEXT = 10_000
MAX_VALUE = 4_000
MAX_ELEMENTS = 200
ACTION_TIMEOUT_MS = 5_000
NAVIGATION_TIMEOUT_MS = 10_000


class PolicyError(ValueError):
    """An invalid URL or action that must not reach the browser."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    category: str
    reason: str


def _parsed_url(url: str):
    if not isinstance(url, str) or not url or len(url) > 8_192:
        raise PolicyError("A nonempty HTTP(S) URL is required.")
    if re.search(r"[\s\\\x00-\x1f\x7f]", url):
        raise PolicyError("Whitespace, control characters, and backslashes are not allowed in URLs.")
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise PolicyError("Only absolute HTTP(S) URLs are allowed.")
        if parsed.username is not None or parsed.password is not None:
            raise PolicyError("Credentials-bearing URLs are not allowed.")
        # Accessing .port validates malformed and out-of-range ports.
        parsed.port
    except ValueError as exc:
        raise PolicyError(str(exc)) from exc
    host = parsed.hostname.lower().rstrip(".")
    if "%" in host or host != parsed.hostname.lower():
        raise PolicyError("Encoded hosts, zone identifiers, and trailing-dot hosts are not allowed.")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise PolicyError("Invalid host name.") from exc
    return parsed, host


def origin_of(url: str) -> str:
    """Return a normalized origin without permitting non-HTTP URL schemes."""
    parsed, host = _parsed_url(url)
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise PolicyError("Invalid host name.") from exc
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    suffix = "" if port is None or port == {"http": 80, "https": 443}[parsed.scheme.lower()] else f":{port}"
    return f"{parsed.scheme.lower()}://{host}{suffix}"


def _check_host(url: str, allowed_origins: set[str]) -> None:
    _, host = _parsed_url(url)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    explicit_loopback = origin_of(url) in allowed_origins and (
        host == "localhost" or (address is not None and address.is_loopback)
    )
    if explicit_loopback:
        return
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise PolicyError("Local hosts require an explicit localhost fixture origin.")
    if address is not None and (not address.is_global or address.is_multicast):
        raise PolicyError("Private, loopback, reserved, and link-local IP addresses are blocked.")
    # Browsers interpret these alternate spellings as IPv4 addresses.
    if address is None and (re.fullmatch(r"[0-9.]+", host) or re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*", host)):
        raise PolicyError("Noncanonical numeric hosts are blocked.")


def normalize_origins(origins: list[str]) -> set[str]:
    if not isinstance(origins, list) or not origins:
        raise PolicyError("Provide at least one explicit allowed origin.")
    normalized: set[str] = set()
    for item in origins:
        parsed, _ = _parsed_url(item)
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise PolicyError("Allowed origins must contain only scheme, host, and optional port.")
        normalized.add(origin_of(item))
    for item in normalized:
        _check_host(item, normalized)
    return normalized


def validate_url(url: str, allowed_origins: set[str], *, navigation: bool = True) -> str:
    """Validate URLs without resolving DNS or performing network requests."""
    _check_host(url, allowed_origins)
    if navigation and origin_of(url) not in allowed_origins:
        raise PolicyError("Navigation outside the explicit allowed origins is blocked.")
    return url


_RISK_PATTERNS = (
    ("payment", r"\b(pay|payment|payments|purchase|purchases|checkout|buy|billing|donate|donation|place[\s_-]*order|confirm[\s_-]*order|купить|покупка|оплат\w*|плат[её]ж\w*|заказать|оформить\s+заказ|подтвердить\s+заказ|пожертвовать)\b"),
    ("destructive", r"\b(delete|remove|destroy|erase|wipe|terminate|unsubscribe|revoke|cancel[\s_-]*(account|subscription)|close[\s_-]*account|factory[\s_-]*reset|удал\w*|уничтож\w*|стереть|отписаться|отменить\s+подписку|закрыть\s+аккаунт)\b"),
    ("logout", r"\b(log[\s_-]*out|sign[\s_-]*out|logout|signout|выйти|выход)\b"),
    ("registration", r"\b(register|registration|sign[\s_-]*up|signup|create[\s_-]*account|join[\s_-]*now|регистраци\w*|зарегистр\w*|создать\s+аккаунт)\b"),
    ("communication", r"\b(send[\s_-]*(?:message)?|post[\s_-]*message|publish|invite|contact|share|reply|subscribe|отправ\w*|связаться|связь|опубликовать|пригласить|поделиться|ответить|подписаться)\b"),
    ("sensitive-entry", r"\b(password|passphrase|secret|token|credit[\s_-]*card|card[\s_-]*number|cvv|cvc|ssn|social[\s_-]*security|iban|bank[\s_-]*account|one[\s_-]*time|otp|verification[\s_-]*code|парол\w*|секрет\w*|токен\w*|номер\s+карт\w*|код\s*подтверждения|банковский\s+сч[её]т)\b"),
    ("upload", r"\b(upload|attach[\s_-]*file|choose[\s_-]*file|загрузить\s+файл|прикрепить\s+файл|выбрать\s+файл)\b"),
)

_SUBMIT_PATTERN = r"\b(form\s*submit|submit|save|confirm|apply|сохранить|подтвердить|применить)\b"


def _semantic_text(text: str) -> str:
    # Decode URL paths/query text and split common camelCase/snake_case verbs.
    for _ in range(2):
        text = unquote(text)
    return re.sub(r"([a-zа-я])([A-ZА-Я])", r"\1 \2", text).replace("_", " ")


def _risk(text: str) -> str | None:
    text = _semantic_text(text)
    for category, pattern in _RISK_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return category
    return None


def validate_action(action: Mapping[str, Any], targets: Mapping[str, Mapping[str, Any]],
                    allowed_origins: set[str], mode: str = "production") -> Decision:
    """Pure action/schema policy. Captured targets are the only actionable IDs."""
    if mode not in MODES:
        return Decision(False, "invalid-mode", "Unknown session mode.")
    if not isinstance(action, dict) or not isinstance(action.get("type"), str):
        return Decision(False, "invalid-action", "An action object with a type is required.")
    kind = action["type"]
    keys = {"type"}
    if kind in {"click", "fill", "select"}:
        keys.add("target")
    if kind in {"fill", "select"}:
        keys.add("value")
    if kind == "navigate":
        keys.add("url")
    if kind == "scroll":
        keys.add("amount")
    if kind == "wait":
        keys.add("seconds")
    if kind not in ACTION_TYPES or set(action) - keys:
        return Decision(False, "invalid-action", "Unsupported action or action fields.")
    if kind == "navigate":
        try:
            validate_url(action.get("url"), allowed_origins)
        except (PolicyError, TypeError) as exc:
            return Decision(False, "navigation", str(exc))
        risk = _risk(action["url"])
        if re.search(_SUBMIT_PATTERN, _semantic_text(action["url"]), re.I):
            risk = risk or "form-submission"
        return Decision(not risk, risk or "navigation", f"Risky navigation ({risk}) is blocked." if risk else "Allowed-origin navigation.")
    if kind == "scroll":
        amount = action.get("amount", 600)
        if type(amount) is not int or not -2_000 <= amount <= 2_000:
            return Decision(False, "invalid-action", "Scroll amount must be an integer between -2000 and 2000.")
        return Decision(True, "view", "Scrolling is allowed.")
    if kind == "wait":
        seconds = action.get("seconds", 5)
        if type(seconds) not in {int, float} or not 1 <= seconds <= 10:
            return Decision(False, "invalid-action", "Wait must be between 1 and 10 seconds.")
        return Decision(True, "view", "Bounded wait followed by a fresh observation.")
    if kind in {"back", "finish"}:
        return Decision(True, "view", "Session navigation is allowed.")
    target_id = action.get("target")
    if not isinstance(target_id, str) or target_id not in targets:
        return Decision(False, "unknown-target", "Use an exact element ID from the latest snapshot.")
    target = targets[target_id]
    if target.get("disabled"):
        return Decision(False, "disabled-target", "The captured element is disabled.")
    input_type = str(target.get("input_type", "")).lower()
    if input_type in {"password", "file", "hidden"}:
        return Decision(False, "sensitive-entry", "Password, file, and hidden inputs cannot be operated.")
    if kind in {"fill", "select"}:
        value = action.get("value")
        if not isinstance(value, str) or len(value) > MAX_VALUE:
            return Decision(False, "invalid-action", f"Value must be text of at most {MAX_VALUE} characters.")
        if mode == "readonly":
            return Decision(False, "readonly", "Readonly mode does not edit controls.")
        if kind == "fill" and not target.get("fillable"):
            return Decision(False, "invalid-target", "The captured element is not a supported text field.")
        if kind == "select" and target.get("tag") != "select":
            return Decision(False, "invalid-target", "Select actions require a captured select element.")
        if kind == "select" and not any(o.get("value") == value and not o.get("disabled") for o in target.get("options", [])):
            return Decision(False, "invalid-option", "Select an enabled option value from the snapshot.")
    semantic_text = " ".join(str(target.get(k, "")) for k in ("name", "role", "href", "input_type", "field_name", "form_action"))
    risk = _risk(semantic_text)
    if risk:
        return Decision(False, risk, f"The target suggests a {risk} action; it is blocked.")
    for key in ("href", "form_action"):
        url = target.get(key)
        if url:
            try:
                validate_url(url, allowed_origins)
            except PolicyError as exc:
                return Decision(False, "navigation", str(exc))
    if kind == "click":
        if target.get("download") or target.get("opens_popup"):
            return Decision(False, "download-or-popup", "Download and popup targets are blocked.")
        form_submit = target.get("form_submit") or bool(re.search(_SUBMIT_PATTERN, _semantic_text(semantic_text), re.I))
        if form_submit:
            if mode != "staging":
                return Decision(False, "form-submission", "Form submissions require explicit staging mode.")
            if target.get("form_sensitive"):
                return Decision(False, "sensitive-entry", "Forms containing sensitive fields cannot be submitted.")
            if not target.get("form_action"):
                return Decision(False, "form-submission", "A staging submission needs a captured allowed-origin form action.")
            return Decision(True, "staging-form", "Normal form submission to an allowed staging origin.")
    return Decision(True, "interaction", "Captured target passed the conservative interaction policy.")


# These scripts are fixed implementation code, never supplied by a persona.
_ELEMENT_INFO = r"""(el) => {
  const tag = el.tagName.toLowerCase();
  const type = (el.getAttribute('type') || '').toLowerCase();
  const form = el.form || el.closest('form');
  const labelled = (el.getAttribute('aria-labelledby') || '').split(/\s+/)
    .map(id => document.getElementById(id)?.textContent || '').join(' ');
  const label = Array.from(el.labels || []).map(x => x.textContent || '').join(' ');
  const buttonText = tag === 'input' && ['submit','button','reset'].includes(type) ? el.value : '';
  const name = (el.getAttribute('aria-label') || labelled.trim() || label.trim() ||
    el.getAttribute('placeholder') || buttonText ||
    (!['input','textarea','select'].includes(tag) ? el.innerText : '') ||
    el.getAttribute('title') || '').replace(/\s+/g,' ').trim().slice(0,240);
  const role = el.getAttribute('role') || ({a:'link',button:'button',select:'combobox',textarea:'textbox'}[tag]) ||
    (tag === 'input' ? ({checkbox:'checkbox',radio:'radio',submit:'button',button:'button'}[type] || 'textbox') : 'control');
  const href = tag === 'a' ? (el.href || '') : '';
  const formSensitive = !!form && Array.from(form.querySelectorAll('input,textarea')).some(x =>
    ['password','file'].includes((x.type || '').toLowerCase()) ||
    /password|secret|token|credit.?card|card.?number|cvv|cvc|ssn|iban|otp|парол|секрет|токен|номер.?карт|код.?подтверждения/i.test(
      [x.name,x.id,x.autocomplete,x.getAttribute('aria-label')].join(' ')));
  return {id:el.getAttribute('data-audience-id'),tag,role,name,input_type:type,
    field_name:(el.getAttribute('name') || '').slice(0,120),href,
    disabled:!!el.disabled || el.getAttribute('aria-disabled') === 'true',
    fillable:tag === 'textarea' || (tag === 'input' && ['','text','search','email','tel','url','number'].includes(type)),
    form_action:form ? form.action : '',form_method:form ? (form.method || 'get').toLowerCase() : '',
    form_sensitive:formSensitive,
    form_submit:!!form && ((tag === 'button' && type !== 'button') || (tag === 'input' && ['submit','image','reset'].includes(type))),
    download:el.hasAttribute('download'),opens_popup:!!el.target && !['_self','_top','_parent'].includes(el.target),
    options:tag === 'select' ? Array.from(el.options).slice(0,50).map(o => ({value:o.value,label:o.label.slice(0,160),disabled:!!(o.disabled || o.parentElement?.disabled)})) : []};
}"""

_SNAPSHOT_SCRIPT = r"""({prefix, maxText, maxElements}) => {
  const visible = el => {const s=getComputedStyle(el); return s.display!=='none' && s.visibility!=='hidden' &&
    s.visibility!=='collapse' && s.opacity!=='0' && el.getClientRects().length > 0 && !el.closest('[hidden],[inert],[aria-hidden="true"]');};
  document.querySelectorAll('[data-audience-id]').forEach(el => el.removeAttribute('data-audience-id'));
  const info = ELEMENT_INFO;
  const selector = 'a[href],button,input,select,textarea,[role="button"],[role="link"],[role="checkbox"],[role="radio"],[tabindex]';
  const elements = Array.from(document.querySelectorAll(selector))
    .filter(el => visible(el) && !(el.tagName === 'INPUT' && el.type === 'hidden')).slice(0,maxElements)
    .map((el,i) => {el.setAttribute('data-audience-id',`${prefix}-${i}`);return info(el);});
  const chunks=[];let size=0;let truncated=false;
  const walker=document.createTreeWalker(document.body || document.documentElement,NodeFilter.SHOW_TEXT);
  while(walker.nextNode()) {
    const node=walker.currentNode, el=node.parentElement;
    if(!el || el.closest('script,style,noscript,input,textarea,select') || !visible(el)) continue;
    const text=(node.textContent || '').replace(/\s+/g,' ').trim();
    if(text){size+=text.length+(chunks.length?1:0);chunks.push(text);if(size>maxText){truncated=true;break;}}
  }
  return {url:location.href,title:document.title.slice(0,500),text:chunks.join('\n').slice(0,maxText),text_truncated:truncated,elements,viewport:{width:innerWidth,height:innerHeight}};
}""".replace("ELEMENT_INFO", _ELEMENT_INFO)


class BrowserSession:
    """One optional browser context with explicit origin and action boundaries."""

    def __init__(self, url: str, allowed_origins: list[str], mode: str = "production",
                 storage_state: str | dict | None = None, evidence_dir: str | Path | None = None,
                 viewport: dict[str, int] | None = None):
        if mode not in MODES:
            raise PolicyError(f"Mode must be one of: {', '.join(sorted(MODES))}.")
        self.allowed_origins = normalize_origins(allowed_origins)
        self.url = validate_url(url, self.allowed_origins)
        if _risk(url) or re.search(_SUBMIT_PATTERN, _semantic_text(url), re.I):
            raise PolicyError("The starting URL suggests a prohibited action.")
        self.mode = mode
        if viewport is None:
            viewport = {"width": 1280, "height": 900}
        if (not isinstance(viewport, dict) or set(viewport) != {"width", "height"}
                or any(type(value) is not int or value <= 0 for value in viewport.values())):
            raise PolicyError("Viewport must contain positive integer width and height values.")
        self.viewport = dict(viewport)
        self.storage_state = storage_state
        self.evidence_dir = Path(evidence_dir) if evidence_dir is not None else None
        self._session_id = uuid.uuid4().hex[:12]
        self._sequence = 0
        self._playwright = self._browser = self._context = self._page = None
        self._targets: dict[str, dict] = {}
        self._route_blocks: list[str] = []
        self._reported_blocks = 0
        self._finished = False
        self._lock = asyncio.Lock()

    async def start(self) -> "BrowserSession":
        if self._page is not None:
            return self
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("The optional standalone driver requires Playwright and its Chromium browser. Use it only where the host permits standalone browser automation.") from exc
        try:
            self._playwright = await asyncio.wait_for(async_playwright().start(), 15)
            self._browser = await self._playwright.chromium.launch(headless=True, timeout=15_000)
            options: dict[str, Any] = {"accept_downloads": False, "service_workers": "block", "viewport": dict(self.viewport)}
            if self.storage_state is not None:
                options["storage_state"] = self.storage_state
            self._context = await self._browser.new_context(**options)
            self._context.set_default_timeout(ACTION_TIMEOUT_MS)
            self._context.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
            await self._context.route("**/*", self._guard_request)
            route_web_socket = getattr(self._context, "route_web_socket", None)
            if route_web_socket is None:
                raise RuntimeError("This driver requires a Playwright version with BrowserContext.route_web_socket so WebSockets can be blocked.")
            await route_web_socket("**/*", self._block_websocket)
            self._page = await self._context.new_page()
            self._context.on("page", self._close_popup)
            self._page.on("download", self._cancel_download)
            self._page.on("dialog", self._dismiss_dialog)
            await self._page.goto(self.url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            validate_url(self._page.url, self.allowed_origins)
            self._finished = False
            return self
        except BaseException:
            await self.close()
            raise

    async def _guard_request(self, route, request) -> None:
        try:
            is_navigation = request.is_navigation_request()
            validate_url(request.url, self.allowed_origins, navigation=is_navigation)
            method = request.method.upper()
            if origin_of(request.url) not in self.allowed_origins and method != "GET":
                raise PolicyError("Off-origin non-GET requests are blocked.")
            if self.mode != "staging" and method not in {"GET", "HEAD", "OPTIONS"}:
                raise PolicyError("State-changing HTTP methods are blocked in production/readonly mode.")
            risk = _risk(request.url)
            if self.mode != "staging" and re.search(_SUBMIT_PATTERN, _semantic_text(request.url), re.I):
                risk = risk or "form-submission"
            if risk:
                raise PolicyError(f"Request URL suggests a prohibited {risk} action.")
        except PolicyError as exc:
            self._route_blocks.append(str(exc))
            await route.abort("blockedbyclient")
            return
        await route.continue_()

    async def _block_websocket(self, websocket) -> None:
        self._route_blocks.append("WebSocket connections are blocked.")
        await websocket.close()

    async def _close_popup(self, page) -> None:
        if page is not self._page:
            self._route_blocks.append("Popup windows are blocked.")
            await page.close()

    async def _cancel_download(self, download) -> None:
        self._route_blocks.append("Downloads are blocked.")
        await download.cancel()

    async def _dismiss_dialog(self, dialog) -> None:
        await dialog.dismiss()

    async def snapshot(self) -> dict:
        if self._page is None:
            raise RuntimeError("Start the browser session before taking a snapshot.")
        validate_url(self._page.url, self.allowed_origins)
        self._sequence += 1
        data = await asyncio.wait_for(self._page.evaluate(_SNAPSHOT_SCRIPT, {
            "prefix": f"aud-{self._session_id}-{self._sequence}", "maxText": MAX_TEXT, "maxElements": MAX_ELEMENTS,
        }), 8)
        data = dict(data)
        data["text"] = str(data.get("text", ""))[:MAX_TEXT]
        self._targets = {el["id"]: el for el in data.get("elements", [])}
        if self.evidence_dir is not None:
            destination = self.evidence_dir / f"session-{self._session_id}"
            destination.mkdir(parents=True, exist_ok=True)
            path = destination / f"snapshot-{self._sequence:04d}.png"
            await self._page.screenshot(path=str(path), full_page=False, timeout=ACTION_TIMEOUT_MS)
            data["screenshot_path"] = str(path.resolve())
        # Navigation and background API calls can be blocked outside act().
        # Carry each barrier with the next actual observation so a caller can
        # stop before asking a model to judge a page broken by this guard.
        barriers = self._route_blocks[self._reported_blocks:]
        if barriers:
            data["policy_barriers"] = list(barriers)
            self._reported_blocks = len(self._route_blocks)
        return data

    async def _result(self, status: str, reason: str, before: str | None, category: str) -> dict:
        try:
            snapshot = await self.snapshot() if self._page is not None else None
        except Exception as exc:
            snapshot = {"error": f"Snapshot unavailable: {type(exc).__name__}"}
        return {"status": status, "reason": reason, "policy": category,
                "before_url": before, "after_url": self._page.url if self._page is not None else None,
                "snapshot": snapshot}

    async def act(self, action: dict) -> dict:
        async with self._lock:
            before = self._page.url if self._page is not None else None
            if self._page is None:
                return await self._result("error", "The browser session has not started.", before, "session")
            if self._finished:
                return await self._result("blocked", "This session has already finished.", before, "session")
            if len(self._route_blocks) > self._reported_blocks:
                return await self._result("blocked", self._route_blocks[self._reported_blocks], before, "network")
            decision = validate_action(action, self._targets, self.allowed_origins, self.mode)
            if not decision.allowed:
                return await self._result("blocked", decision.reason, before, decision.category)
            block_count = len(self._route_blocks)
            try:
                await asyncio.wait_for(self._execute(action), 13)
                if len(self._route_blocks) > block_count:
                    return await self._result("blocked", self._route_blocks[block_count], before, "network")
                return await self._result("ok", decision.reason, before, decision.category)
            except PolicyError as exc:
                return await self._result("blocked", str(exc), before, "changed-target")
            except Exception as exc:
                # Do not return browser exceptions containing form values or credentials.
                return await self._result("error", f"Browser action failed: {type(exc).__name__}", before, "execution")

    async def _execute(self, action: dict) -> None:
        kind = action["type"]
        if kind in {"click", "fill", "select"}:
            captured = self._targets[action["target"]]
            # The selector is constructed only from an internally generated ID.
            element_id = captured["id"]
            if not re.fullmatch(r"aud-[0-9a-f]{12}-\d+-\d+", element_id):
                raise PolicyError("Invalid internally captured element ID.")
            locator = self._page.locator(f'[data-audience-id="{element_id}"]')
            if await locator.count() != 1 or not await locator.is_visible():
                raise PolicyError("The captured element is no longer uniquely visible.")
            current = await locator.evaluate(_ELEMENT_INFO, timeout=ACTION_TIMEOUT_MS)
            # Refuse moved/relabelled controls instead of silently operating a new target.
            if current != captured:
                raise PolicyError("The captured target changed. Take a new snapshot before acting.")
            decision = validate_action(action, {element_id: current}, self.allowed_origins, self.mode)
            if not decision.allowed:
                raise PolicyError(decision.reason)
            if kind == "click":
                await locator.click(timeout=ACTION_TIMEOUT_MS)
            elif kind == "fill":
                await locator.fill(action["value"], timeout=ACTION_TIMEOUT_MS)
            else:
                await locator.select_option(value=action["value"], timeout=ACTION_TIMEOUT_MS)
        elif kind == "navigate":
            await self._page.goto(action["url"], wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        elif kind == "back":
            await self._page.go_back(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        elif kind == "scroll":
            await self._page.mouse.wheel(0, action.get("amount", 600))
        elif kind == "wait":
            await asyncio.sleep(action.get("seconds", 5))
        elif kind == "finish":
            self._finished = True

    async def close(self) -> None:
        self._targets = {}
        self._page = None
        for name, method in (("_context", "close"), ("_browser", "close"), ("_playwright", "stop")):
            item = getattr(self, name)
            setattr(self, name, None)
            if item is not None:
                try:
                    await asyncio.wait_for(getattr(item, method)(), 5)
                except Exception:
                    pass

    async def __aenter__(self) -> "BrowserSession":
        return await self.start()

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()
