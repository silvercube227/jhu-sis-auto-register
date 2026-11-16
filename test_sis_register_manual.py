import datetime
import unittest
from unittest.mock import Mock, patch

import sis_register_manual as manual


class ManualRegistrationTests(unittest.TestCase):
    def test_attach_capabilities_exclude_launch_only_options(self):
        with patch.object(manual.webdriver, "Chrome") as chrome:
            browser = manual.attach_browser("127.0.0.1:9222")
        self.assertIs(browser, chrome.return_value)
        capabilities = chrome.call_args.kwargs["options"].to_capabilities()
        chrome_options = capabilities["goog:chromeOptions"]
        self.assertEqual(chrome_options["debuggerAddress"], "127.0.0.1:9222")
        self.assertNotIn("detach", chrome_options)
        self.assertEqual(capabilities["unhandledPromptBehavior"], "ignore")

    def test_registration_time_today_and_tomorrow(self):
        now = datetime.datetime(2026, 11, 16, 6, 55, 10)
        self.assertEqual(manual.registration_datetime("07:00", now), now.replace(hour=7, minute=0, second=0))
        self.assertEqual(manual.registration_datetime("06:00", now), datetime.datetime(2026, 11, 17, 6))
        with self.assertRaises(ValueError):
            manual.registration_datetime("25:00", now)

    def test_selenium_attaches_only_after_manual_handoff(self):
        events = []

        def respond(prompt):
            if prompt.startswith("Time to register"):
                return "07:00"
            events.append("manual handoff")
            return ""

        browser = Mock()
        with patch("builtins.input", side_effect=respond), patch("builtins.print"), \
                patch.object(manual, "registration_datetime", return_value=datetime.datetime(2099, 1, 1)), \
                patch.object(manual, "find_chrome", return_value="chrome"), \
                patch.object(manual, "launch_chrome", side_effect=lambda _: events.append("launch") or "127.0.0.1:1234"), \
                patch.object(manual, "attach_browser", side_effect=lambda _: events.append("attach") or browser), \
                patch.object(manual, "select_sis_tab"), patch.object(manual, "prepare_cart"), \
                patch.object(manual, "register_at"):
            self.assertEqual(manual.main([]), 0)
        self.assertEqual(events, ["launch", "manual handoff", "attach"])
        browser.quit.assert_not_called()
        browser.service.stop.assert_called_once()

    def test_cancel_during_login_never_attaches(self):
        with patch("builtins.input", side_effect=["07:00", KeyboardInterrupt]), \
                patch("builtins.print"), patch.object(manual, "find_chrome"), \
                patch.object(manual, "launch_chrome"), patch.object(manual, "attach_browser") as attach:
            self.assertEqual(manual.main([]), 130)
        attach.assert_not_called()

    def test_attach_mode_reuses_browser_without_launching_or_navigating(self):
        for arguments, port in [(["--attach"], 9222), (["--attach", "9333"], 9333)]:
            with self.subTest(arguments=arguments), \
                    patch("builtins.input", side_effect=["07:00", ""]), patch("builtins.print"), \
                    patch.object(manual, "registration_datetime", return_value=datetime.datetime(2099, 1, 1)), \
                    patch.object(manual, "find_chrome") as find, \
                    patch.object(manual, "launch_chrome") as launch, \
                    patch.object(manual, "attach_browser") as attach, \
                    patch.object(manual, "select_sis_tab"), patch.object(manual, "prepare_cart"), \
                    patch.object(manual, "register_at"):
                self.assertEqual(manual.main(arguments), 0)
                find.assert_not_called()
                launch.assert_not_called()
                attach.assert_called_once_with(f"127.0.0.1:{port}")
                attach.return_value.get.assert_not_called()
                attach.return_value.quit.assert_not_called()
                attach.return_value.service.stop.assert_called_once()

    def test_invalid_attach_port_is_rejected_before_prompts(self):
        for port in ("0", "65536", "not-a-port"):
            with self.subTest(port=port), patch("builtins.input") as prompt, patch("sys.stderr"):
                with self.assertRaises(SystemExit) as error:
                    manual.main(["--attach", port])
                self.assertEqual(error.exception.code, 2)
                prompt.assert_not_called()

    def test_failed_attachment_does_not_launch_browser_or_register(self):
        with patch("builtins.input", side_effect=["07:00", ""]), patch("builtins.print"), \
                patch.object(manual, "launch_chrome") as launch, \
                patch.object(manual, "attach_browser", side_effect=manual.WebDriverException("connection refused")), \
                patch.object(manual, "register_at") as register:
            self.assertEqual(manual.main(["--attach"]), 1)
        launch.assert_not_called()
        register.assert_not_called()

    def test_existing_cart_selection_is_not_toggled_off(self):
        browser = Mock()
        browser.find_elements.return_value = [Mock()]
        checkbox = Mock()
        checkbox.is_selected.return_value = True
        with patch.object(manual, "WebDriverWait") as wait, patch("builtins.print"):
            wait.return_value.until.side_effect = [checkbox, Mock()]
            manual.prepare_cart(browser)
        checkbox.click.assert_not_called()

    def test_selects_unchecked_cart(self):
        browser = Mock()
        browser.find_elements.return_value = [Mock()]
        checkbox = Mock()
        checkbox.is_selected.return_value = False
        with patch.object(manual, "WebDriverWait") as wait, patch("builtins.print"):
            wait.return_value.until.side_effect = [checkbox, Mock()]
            manual.prepare_cart(browser)
        checkbox.click.assert_called_once()

    def test_finds_cart_tab_and_rejects_lookalike_domain(self):
        browser = Mock()
        browser.window_handles = ["unrelated", "sis"]
        browser.current_url = "https://sis.jhu.edu.example.org/"

        def switch(handle):
            browser.current_url = "https://sis.jhu.edu/sswf/" if handle == "sis" else "https://sis.jhu.edu.example.org/"

        browser.switch_to.window.side_effect = switch
        browser.find_elements.return_value = [Mock()]
        manual.select_sis_tab(browser)
        self.assertEqual(browser.switch_to.window.call_args.args, ("sis",))
        browser.window_handles = ["unrelated"]
        with self.assertRaises(RuntimeError):
            manual.select_sis_tab(browser)

    def test_ambiguous_sis_tabs_stop(self):
        browser = Mock()
        browser.window_handles = ["one", "two"]
        browser.current_url = manual.SIS_URL
        browser.find_elements.return_value = [Mock()]
        with self.assertRaisesRegex(RuntimeError, "Multiple SIS tabs"):
            manual.select_sis_tab(browser)

    def test_register_fetches_fresh_button_and_clicks_once(self):
        browser = Mock()
        browser.current_url = manual.SIS_URL
        browser.find_element.return_value.is_selected.return_value = True
        with patch.object(manual, "WebDriverWait") as wait, patch("builtins.print"):
            manual.register_at(browser, datetime.datetime(2000, 1, 1))
        wait.return_value.until.return_value.click.assert_called_once()

    def test_changed_selection_stops_without_clicking(self):
        browser = Mock()
        browser.current_url = manual.SIS_URL
        browser.find_element.return_value.is_selected.return_value = False
        with patch.object(manual, "WebDriverWait") as wait, patch("builtins.print"):
            with self.assertRaisesRegex(RuntimeError, "selection changed"):
                manual.register_at(browser, datetime.datetime(2000, 1, 1))
        wait.assert_not_called()


if __name__ == "__main__":
    unittest.main()
