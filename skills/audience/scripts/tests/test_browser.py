"""Pure policy and mocked browser tests. No browser process is ever started."""

import copy
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audience_core.browser import (
    BrowserSession, MAX_TEXT, PolicyError, _SNAPSHOT_SCRIPT,
    normalize_origins, origin_of, validate_action, validate_url,
)


ORIGINS = {"https://example.com"}
TARGET_ID = "aud-123456abcdef-1-0"


def target(**overrides):
    result = {
        "id": TARGET_ID, "tag": "button", "role": "button", "name": "Explore",
        "input_type": "", "field_name": "", "href": "", "disabled": False,
        "fillable": False, "form_action": "", "form_method": "", "form_sensitive": False,
        "form_submit": False, "download": False, "opens_popup": False, "options": [],
    }
    result.update(overrides)
    return result


def decide(action, element=None, mode="production"):
    return validate_action(action, {TARGET_ID: element or target()}, ORIGINS, mode)


class URLPolicyTests(unittest.TestCase):
    def test_origin_normalization(self):
        self.assertEqual(origin_of("HTTPS://EXAMPLE.com:443/path?q=1"), "https://example.com")
        self.assertEqual(normalize_origins(["https://example.com/"]), ORIGINS)
        self.assertEqual(origin_of("http://[::1]:8080/path"), "http://[::1]:8080")

    def test_disallowed_urls(self):
        urls = [
            "javascript:alert(1)", "file:///etc/passwd", "data:text/html,test", "about:blank",
            "https://user:password@example.com/", "https://@example.com/", "https://evil.example/",
            "https://example.com:443@evil.example/", "https://example.com\\@evil.example/",
            "https://example.com/\npath", "https://example.com./", "http://127.0.0.1/",
            "http://10.0.0.1/", "http://169.254.169.254/", "http://192.168.1.1/",
            "http://[::1]/", "http://[fe80::1]/", "http://2130706433/", "http://127.1/",
            "http://0177.0.0.1/", "http://0x7f000001/", "http://%31%32%37.0.0.1/",
            "http://１２７.０.０.１/", "http://224.0.0.1/", "http://internal.local/",
        ]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(PolicyError):
                validate_url(url, ORIGINS)

    def test_private_resource_urls_are_also_blocked(self):
        for url in ["http://10.0.0.1/image", "http://2130706433/image", "http://１２７.０.０.１/image"]:
            with self.subTest(url=url), self.assertRaises(PolicyError):
                validate_url(url, ORIGINS, navigation=False)

    def test_explicit_localhost_fixture(self):
        origins = normalize_origins(["http://localhost:8000", "http://127.0.0.1:9000", "http://[::1]:7000"])
        for origin in origins:
            self.assertEqual(validate_url(origin + "/fixture", origins), origin + "/fixture")
        with self.assertRaises(PolicyError):
            validate_url("http://localhost:9999/", origins)
        with self.assertRaises(PolicyError):
            normalize_origins(["http://10.0.0.1"])

    def test_origin_allowlist_requires_origins(self):
        for invalid in [[], ["https://example.com/path"], ["https://example.com?q=1"], ["https://example.com#x"], "https://example.com"]:
            with self.subTest(invalid=invalid), self.assertRaises(PolicyError):
                normalize_origins(invalid)

    def test_third_party_get_resources_may_be_loaded(self):
        self.assertEqual(validate_url("https://cdn.example.org/image.png", ORIGINS, navigation=False), "https://cdn.example.org/image.png")


class ActionPolicyTests(unittest.TestCase):
    def test_normal_click(self):
        self.assertTrue(decide({"type": "click", "target": TARGET_ID}).allowed)

    def test_unsupported_actions_and_fields(self):
        for action in [
            {"type": "evaluate", "code": "1+1"}, {"type": "click", "selector": "button"},
            {"type": "click", "target": TARGET_ID, "code": "alert(1)"},
            {"type": "fill", "target": TARGET_ID, "value": "hello", "tool": "exec"},
            {"type": "scroll", "amount": True}, {"type": "scroll", "amount": 2001},
            {"type": "navigate"}, {"type": []}, None,
        ]:
            with self.subTest(action=action):
                self.assertFalse(decide(action).allowed)

    def test_requires_latest_captured_id(self):
        for bad_id in ["button", "aud-123456abcdef-0-0", 'x"] button', 1, None]:
            self.assertEqual(decide({"type": "click", "target": bad_id}).category, "unknown-target")

    def test_risky_english_and_russian_targets_blocked_in_both_modes(self):
        labels = [
            "Pay now", "Purchase", "PlaceOrder", "sendmessage", "Send message", "Delete account",
            "Log out", "Register", "Contact us", "Password", "Upload file", "Save token",
            "Купить", "Оплатить", "Заказать", "Оформить заказ", "Отправить сообщение",
            "Связаться с нами", "Удаление аккаунта", "Выйти", "Регистрация", "Пароль", "Кодподтверждения",
        ]
        for mode in ["production", "staging"]:
            for label in labels:
                with self.subTest(mode=mode, label=label):
                    self.assertFalse(decide({"type": "click", "target": TARGET_ID}, target(name=label), mode).allowed)

    def test_risky_href_encoding_cannot_bypass(self):
        for path in ["/delete_account", "/send_message", "/%64elete", "/%2564elete", "/%D0%BA%D1%83%D0%BF%D0%B8%D1%82%D1%8C", "/formsubmit"]:
            with self.subTest(path=path):
                self.assertFalse(decide({"type": "click", "target": TARGET_ID}, target(href="https://example.com" + path)).allowed)
                self.assertFalse(decide({"type": "navigate", "url": "https://example.com" + path}).allowed)

    def test_staging_allows_only_normal_allowed_origin_submissions(self):
        submit = target(name="Submit", form_submit=True, form_action="https://example.com/preferences")
        action = {"type": "click", "target": TARGET_ID}
        self.assertFalse(decide(action, submit).allowed)
        self.assertTrue(decide(action, submit, "staging").allowed)
        for changes in [{"form_sensitive": True}, {"form_action": "https://outside.example/"}, {"form_action": ""}, {"name": "Pay"}]:
            with self.subTest(changes=changes):
                self.assertFalse(decide(action, {**submit, **changes}, "staging").allowed)

    def test_password_upload_and_hidden_inputs_never_operated(self):
        for input_type in ["password", "file", "hidden"]:
            for mode in ["production", "staging"]:
                with self.subTest(input_type=input_type, mode=mode):
                    self.assertFalse(decide({"type": "fill", "target": TARGET_ID, "value": "x"}, target(input_type=input_type, fillable=True), mode).allowed)

    def test_fill_and_select_contract(self):
        fill = {"type": "fill", "target": TARGET_ID, "value": "Search terms"}
        field = target(tag="input", role="textbox", fillable=True, name="Search")
        self.assertTrue(decide(fill, field).allowed)
        self.assertFalse(decide(fill, field, "readonly").allowed)
        self.assertFalse(decide({**fill, "value": 3}, field).allowed)
        self.assertFalse(decide({**fill, "value": "x" * 4001}, field).allowed)
        select = target(tag="select", options=[{"value": "a", "label": "A", "disabled": False}, {"value": "b", "label": "B", "disabled": True}])
        self.assertTrue(decide({"type": "select", "target": TARGET_ID, "value": "a"}, select).allowed)
        self.assertFalse(decide({"type": "select", "target": TARGET_ID, "value": "b"}, select).allowed)
        self.assertFalse(decide({"type": "select", "target": TARGET_ID, "value": "unknown"}, select).allowed)

    def test_download_popup_and_external_targets_blocked(self):
        for changes in [{"download": True}, {"opens_popup": True}, {"href": "https://other.example/"}, {"disabled": True}]:
            with self.subTest(changes=changes):
                self.assertFalse(decide({"type": "click", "target": TARGET_ID}, target(**changes)).allowed)

    def test_snapshot_code_does_not_read_browser_secrets(self):
        self.assertNotIn("localStorage", _SNAPSHOT_SCRIPT)
        self.assertNotIn("sessionStorage", _SNAPSHOT_SCRIPT)
        self.assertNotIn("document.cookie", _SNAPSHOT_SCRIPT)
        self.assertNotIn("input.value", _SNAPSHOT_SCRIPT)
        self.assertIn("['submit','button','reset'].includes(type) ? el.value", _SNAPSHOT_SCRIPT)


class MockBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_viewport_reaches_mocked_browser_context(self):
        # Fake the complete optional package before start() can import it.
        # No Playwright installation or real browser is used by this test.
        for viewport, expected in [(None, {"width": 1280, "height": 900}),
                                   ({"width": 390, "height": 844}, {"width": 390, "height": 844})]:
            with self.subTest(viewport=viewport):
                page = Mock(url="https://example.com/", goto=AsyncMock())
                context = Mock(route=AsyncMock(), route_web_socket=AsyncMock(),
                               new_page=AsyncMock(return_value=page), close=AsyncMock())
                browser = Mock(new_context=AsyncMock(return_value=context), close=AsyncMock())
                runtime = Mock(stop=AsyncMock())
                runtime.chromium.launch = AsyncMock(return_value=browser)
                factory = Mock(return_value=Mock(start=AsyncMock(return_value=runtime)))
                package = ModuleType("playwright")
                api = ModuleType("playwright.async_api")
                api.async_playwright = factory
                with patch.dict(sys.modules, {"playwright": package, "playwright.async_api": api}):
                    session = BrowserSession("https://example.com", ["https://example.com"], viewport=viewport)
                    await session.start()
                    self.assertEqual(browser.new_context.call_args.kwargs["viewport"], expected)
                    await session.close()

    def test_viewport_is_validated_and_copied(self):
        viewport = {"width": 390, "height": 844}
        session = BrowserSession("https://example.com", ["https://example.com"], viewport=viewport)
        viewport["width"] = 1
        self.assertEqual(session.viewport, {"width": 390, "height": 844})
        for invalid in [{}, {"width": 0, "height": 844}, {"width": True, "height": 844},
                        {"width": 390, "height": "844"}, {"width": 390, "height": 844, "extra": 1}]:
            with self.subTest(viewport=invalid), self.assertRaises(PolicyError):
                BrowserSession("https://example.com", ["https://example.com"], viewport=invalid)

    def make_session(self, mode="production"):
        session = BrowserSession("https://example.com", ["https://example.com"], mode)
        page = Mock()
        page.url = "https://example.com/"
        page.evaluate = AsyncMock(return_value={"url": page.url, "title": "Page", "text": "hello", "elements": [target()]})
        page.goto = AsyncMock()
        page.go_back = AsyncMock()
        page.mouse.wheel = AsyncMock()
        session._page = page
        session._targets = {TARGET_ID: target()}
        return session, page

    async def test_invalid_action_cannot_execute(self):
        session, page = self.make_session()
        session._execute = AsyncMock()
        result = await session.act({"type": "evaluate", "code": "bad"})
        self.assertEqual(result["status"], "blocked")
        session._execute.assert_not_awaited()
        self.assertEqual(result["before_url"], page.url)
        self.assertIsInstance(result["snapshot"], dict)

    async def test_target_change_is_blocked_before_click(self):
        session, page = self.make_session()
        locator = Mock()
        locator.count = AsyncMock(return_value=1)
        locator.is_visible = AsyncMock(return_value=True)
        locator.evaluate = AsyncMock(return_value=target(name="Delete account"))
        locator.click = AsyncMock()
        page.locator.return_value = locator
        result = await session.act({"type": "click", "target": TARGET_ID})
        self.assertEqual(result["status"], "blocked")
        locator.click.assert_not_awaited()

    async def test_safe_captured_click_and_session_reuse(self):
        session, page = self.make_session()
        locator = Mock()
        locator.count = AsyncMock(return_value=1)
        locator.is_visible = AsyncMock(return_value=True)
        locator.evaluate = AsyncMock(return_value=copy.deepcopy(target()))
        locator.click = AsyncMock()
        page.locator.return_value = locator
        result = await session.act({"type": "click", "target": TARGET_ID})
        self.assertEqual(result["status"], "ok")
        locator.click.assert_awaited_once()
        await session.act({"type": "navigate", "url": "https://example.com/another"})
        self.assertIs(session._page, page)
        page.goto.assert_awaited_once()

    async def test_snapshot_text_capped(self):
        session, page = self.make_session()
        page.evaluate.return_value["text"] = "x" * 12000
        result = await session.snapshot()
        self.assertEqual(len(result["text"]), MAX_TEXT)
        self.assertEqual(session._targets[TARGET_ID]["name"], "Explore")

    async def test_initial_network_barrier_is_reported_with_observation(self):
        session, _ = self.make_session()
        route = Mock(abort=AsyncMock(), continue_=AsyncMock())
        request = Mock(url="https://example.com/api/search", method="POST")
        request.is_navigation_request.return_value = False
        await session._guard_request(route, request)
        observed = await session.snapshot()
        self.assertEqual(route.abort.await_count, 1)
        self.assertEqual(observed["text"], "hello")
        self.assertIn("State-changing HTTP methods", observed["policy_barriers"][0])
        self.assertNotIn("policy_barriers", await session.snapshot())

    async def test_background_barrier_before_action_prevents_execution(self):
        session, _ = self.make_session()
        await session.snapshot()
        session._execute = AsyncMock()
        route = Mock(abort=AsyncMock(), continue_=AsyncMock())
        request = Mock(url="https://example.com/api/search", method="POST")
        request.is_navigation_request.return_value = False
        await session._guard_request(route, request)
        result = await session.act({"type": "scroll"})
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["policy"], "network")
        self.assertTrue(result["snapshot"]["policy_barriers"])
        session._execute.assert_not_awaited()

    async def test_finish_blocks_later_actions(self):
        session, _ = self.make_session()
        self.assertEqual((await session.act({"type": "finish"}))["status"], "ok")
        self.assertEqual((await session.act({"type": "scroll"}))["status"], "blocked")

    async def test_network_policy_with_mock_requests(self):
        cases = [
            ("production", "https://example.com/api", "POST", False, False),
            ("production", "https://cdn.example.org/image", "GET", False, True),
            ("production", "https://cdn.example.org/api", "POST", False, False),
            ("production", "https://cdn.example.org/", "GET", True, False),
            ("production", "http://127.0.0.1/", "GET", False, False),
            ("production", "https://example.com/delete", "GET", False, False),
            ("production", "https://example.com/formsubmit", "GET", False, False),
            ("staging", "https://example.com/preferences", "POST", False, True),
            ("staging", "https://example.com/delete", "POST", False, False),
            ("staging", "https://outside.example/api", "POST", False, False),
        ]
        for mode, url, method, navigation, allowed in cases:
            with self.subTest(mode=mode, url=url, method=method):
                session, _ = self.make_session(mode)
                route = Mock(abort=AsyncMock(), continue_=AsyncMock())
                request = Mock(url=url, method=method)
                request.is_navigation_request.return_value = navigation
                await session._guard_request(route, request)
                self.assertEqual(route.continue_.await_count, int(allowed))
                self.assertEqual(route.abort.await_count, int(not allowed))

    async def test_close_does_not_write_storage_state(self):
        session, _ = self.make_session()
        context = Mock(close=AsyncMock(), storage_state=AsyncMock())
        session._context = context
        await session.close()
        context.close.assert_awaited_once()
        context.storage_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
