import datetime
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

import sis_register_uc as uc


class LoginBrowser:
    """Exercise the real login loop against a sequence of SSO screens."""

    def __init__(self, reject_password=False):
        self.stage = "landing"
        self.reject_password = reject_password
        self.entered = []
        self.uc_open_with_reconnect = Mock()

    @property
    def current_url(self):
        host = "sis.jhu.edu" if self.stage in ("landing", "continue", "ready") else "login.microsoftonline.com"
        return f"https://{host}/"

    def find_elements(self, by, value):
        locators = {
            "landing": (By.XPATH, "//a[contains(normalize-space(.), 'Sign In')]"),
            "email": (By.NAME, "loginfmt"),
            "password": (By.NAME, "passwd"),
            "mfa": (By.ID, "idRichContext_DisplaySign"),
            "stay": (By.ID, "KmsiCheckboxField"),
            "continue": (By.ID, "ctl00_contentPlaceHolder_btnContinueToIsis"),
            "ready": uc.REGISTRATION,
            "rejected": (By.ID, "passwordError"),
        }
        if (by, value) != locators[self.stage] and not (self.stage == "stay" and value == "idSIButton9"):
            return []
        element = Mock()
        element.is_displayed.return_value = True
        element.is_enabled.return_value = True
        element.text = "42" if self.stage == "mfa" else ""
        element.click.side_effect = self.advance

        def send_keys(value):
            if value == Keys.RETURN:
                self.advance()
            else:
                self.entered.append(value)

        element.send_keys.side_effect = send_keys
        return [element]

    def advance(self):
        transitions = {"landing": "email", "email": "password", "password": "mfa", "mfa": "stay", "stay": "continue", "continue": "ready"}
        if self.stage == "password" and self.reject_password:
            self.stage = "rejected"
        else:
            self.stage = transitions[self.stage]

    def phone_approval(self, seconds):
        if self.stage == "mfa":
            self.advance()


class UCRegistrationTests(unittest.TestCase):
    def test_passkey_options_preserve_unrelated_browser_settings(self):
        options = Options()
        options.add_argument("--deny-permission-prompts")
        options.add_argument("--disable-features=Translate,WebAuthentication,PasskeyAuth,NetworkPrediction")
        options.add_argument("--remote-debugging-port=9222")
        uc.allow_authenticator_passkeys(options)
        self.assertEqual(options.arguments, [
            "--disable-features=Translate,NetworkPrediction", "--remote-debugging-port=9222",
        ])

    def test_passkey_only_disabled_features_leave_no_empty_flag(self):
        options = Options()
        options.add_argument("--disable-features=WebAuthentication,PasskeyAuth")
        uc.allow_authenticator_passkeys(options)
        self.assertEqual(options.arguments, [])

    def test_option_adapter_is_applied_before_launch_and_always_restored(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                options = Options()
                options.add_argument("--deny-permission-prompts")
                original = Mock(return_value=options)
                launcher = SimpleNamespace(_set_chrome_options=original)
                browser = Mock()

                def driver(**kwargs):
                    self.assertEqual(launcher._set_chrome_options().arguments, [])
                    if fail:
                        raise RuntimeError("Launch failed")
                    return browser

                modules = {
                    "seleniumbase": SimpleNamespace(Driver=driver),
                    "seleniumbase.core": SimpleNamespace(browser_launcher=launcher),
                }
                with patch.dict("sys.modules", modules):
                    factory = uc.load_driver_factory()
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, "Launch failed"):
                            factory(uc=True)
                    else:
                        self.assertIs(factory(uc=True), browser)
                self.assertIs(launcher._set_chrome_options, original)

    def test_full_login_advances_through_mfa_stay_signed_in_and_continue(self):
        browser = LoginBrowser()
        with patch.object(uc.time, "sleep", side_effect=browser.phone_approval), patch("builtins.print") as output:
            uc.login(browser, "student@jhu.edu", "test-password")
        self.assertEqual(browser.stage, "ready")
        self.assertEqual(browser.entered, ["student@jhu.edu", "test-password"])
        browser.uc_open_with_reconnect.assert_called_once_with(uc.SIS_URL, reconnect_time=3)
        output.assert_any_call("\aEnter 42 in Microsoft Authenticator.")

    def test_rejected_password_stops_without_resubmission(self):
        browser = LoginBrowser(reject_password=True)
        with patch.object(uc.time, "sleep"), patch("builtins.print"):
            with self.assertRaisesRegex(RuntimeError, "rejected"):
                uc.login(browser, "student@jhu.edu", "bad-password")
        self.assertEqual(browser.entered, ["student@jhu.edu", "bad-password"])

    def test_untrusted_or_insecure_page_never_receives_credentials(self):
        for url in ("https://login.microsoftonline.com.example.org/", "http://login.microsoftonline.com/"):
            with self.subTest(url=url):
                browser = Mock()
                browser.current_url = url
                with patch.object(uc.time, "monotonic", side_effect=[0, 1, 601]), \
                        patch.object(uc.time, "sleep"), patch("builtins.print"):
                    with self.assertRaisesRegex(RuntimeError, "did not finish"):
                        uc.login(browser, "student@jhu.edu", "test-password")
                browser.find_elements.assert_not_called()

    def test_automated_flow_has_no_handoff_prompt_before_registration(self):
        events = []
        browser = Mock()
        factory = Mock(return_value=browser)
        target = datetime.datetime(2099, 1, 1, 7)
        with patch.object(uc, "load_driver_factory", return_value=factory), \
                patch("builtins.input", side_effect=["student@jhu.edu", "07:00"]) as prompt, \
                patch.object(uc.getpass, "getpass", return_value="test-password"), \
                patch.object(uc, "registration_datetime", return_value=target), \
                patch.object(uc, "wait_until", side_effect=lambda _: events.append("wait")) as wait, \
                patch.object(uc, "login", side_effect=lambda *a, **k: events.append("login")), \
                patch.object(uc, "select_sis_tab", side_effect=lambda _: events.append("tab")), \
                patch.object(uc, "prepare_cart", side_effect=lambda _: events.append("cart")), \
                patch.object(uc, "register_at", side_effect=lambda *a: events.append("register")), \
                patch.object(uc, "review_and_close", side_effect=lambda _: events.append("review")), \
                patch("builtins.print"):
            self.assertEqual(uc.main([]), 0)
        self.assertEqual(events, ["wait", "login", "tab", "cart", "register", "review"])
        self.assertEqual(prompt.call_count, 2)
        wait.assert_called_once_with(target - datetime.timedelta(minutes=10))
        factory.assert_called_once_with(browser="chrome", uc=True, headless=False, headed=True)

    def test_login_failure_never_reaches_cart_or_register(self):
        browser = Mock()
        with patch.object(uc, "load_driver_factory", return_value=Mock(return_value=browser)), \
                patch("builtins.input", side_effect=["student@jhu.edu", "07:00"]), \
                patch.object(uc.getpass, "getpass", return_value="test-password"), \
                patch.object(uc, "login", side_effect=RuntimeError("Login timed out")), \
                patch.object(uc, "prepare_cart") as cart, patch.object(uc, "register_at") as register, \
                patch.object(uc, "review_and_close") as review, patch("builtins.print"):
            self.assertEqual(uc.main(["--login-now"]), 1)
        cart.assert_not_called()
        register.assert_not_called()
        review.assert_called_once_with(browser)

    def test_review_keeps_browser_available_until_enter(self):
        browser = Mock()

        def review(prompt):
            browser.disconnect.assert_called_once()
            browser.quit.assert_not_called()
            return ""

        with patch("builtins.input", side_effect=review):
            uc.review_and_close(browser)
        browser.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
