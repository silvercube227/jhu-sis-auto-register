"""Automate SIS login and timed registration using SeleniumBase UC Mode."""

import argparse
import datetime
import getpass
import sys
import time
from urllib.parse import urlparse

from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from sis_register_manual import (
    REGISTRATION,
    SELECT_ALL,
    SIS_URL,
    prepare_cart,
    register_at,
    registration_datetime,
    select_sis_tab,
)


MICROSOFT_LOGIN_HOSTS = {"login.microsoftonline.com", "login.microsoft.com", "login.live.com"}


def allow_authenticator_passkeys(options):
    """Preserve Chrome's native passkey and device-permission UI in UC Mode."""
    arguments = []
    for argument in options.arguments:
        if argument == "--deny-permission-prompts":
            continue
        if argument.startswith("--disable-features="):
            features = argument.split("=", 1)[1].split(",")
            features = [feature for feature in features if feature not in {"WebAuthentication", "PasskeyAuth"}]
            if not features:
                continue
            argument = "--disable-features=" + ",".join(features)
        arguments.append(argument)
    options.arguments[:] = arguments
    return options


def load_driver_factory():
    try:
        from seleniumbase import Driver
        from seleniumbase.core import browser_launcher
    except ImportError as error:
        raise RuntimeError(
            "Install the UC dependencies first: python -m pip install -r requirements-uc.txt"
        ) from error
    # Driver has no public option for removing its built-in disabled features.
    # Scope this adapter to our single browser launch; never edit site-packages.
    def launch(**kwargs):
        original = browser_launcher._set_chrome_options

        def build_options(*args, **options_kwargs):
            return allow_authenticator_passkeys(original(*args, **options_kwargs))

        browser_launcher._set_chrome_options = build_options
        try:
            return Driver(**kwargs)
        finally:
            browser_launcher._set_chrome_options = original

    return launch


def visible(browser, by, value):
    for element in browser.find_elements(by, value):
        if element.is_displayed() and element.is_enabled():
            return element
    return None


def login(browser, email, password, timeout=600):
    """Handle SIS and Microsoft SSO; wait for user-required authentication steps."""
    browser.uc_open_with_reconnect(SIS_URL, reconnect_time=3)
    deadline = time.monotonic() + timeout
    email_sent = password_sent = sign_in_clicked = continue_clicked = kmsi_clicked = False
    account_picker_clicked = False
    shown_number = None
    print("Logging in automatically. Complete any verification or 2FA requests in Chrome/on your phone.")
    print("For an Authenticator passkey, use Chrome's phone/device option and scan its QR code.")
    print("Allow any requested Bluetooth/device permission; keep Bluetooth on for your computer and phone.")
    while time.monotonic() < deadline:
        try:
            location = urlparse(browser.current_url)
            if location.scheme != "https":
                time.sleep(0.5)
                continue
            if location.hostname == "sis.jhu.edu":
                if visible(browser, *REGISTRATION) or visible(browser, *SELECT_ALL):
                    print("Logged in: SIS is ready.")
                    return
                continue_button = visible(browser, By.ID, "ctl00_contentPlaceHolder_btnContinueToIsis")
                sign_in = visible(browser, By.XPATH, "//a[contains(normalize-space(.), 'Sign In')]")
                if continue_button and not continue_clicked:
                    continue_button.click()
                    continue_clicked = True
                elif sign_in and not sign_in_clicked:
                    sign_in.click()
                    sign_in_clicked = True
            elif location.hostname in MICROSOFT_LOGIN_HOSTS:
                # Do not repeatedly submit rejected credentials (which can lock an account).
                for error_id in ("usernameError", "passwordError"):
                    if visible(browser, By.ID, error_id):
                        raise RuntimeError("Microsoft rejected the sign-in. Check the message in Chrome.")
                email_field = visible(browser, By.NAME, "loginfmt")
                password_field = visible(browser, By.NAME, "passwd")
                other_account = visible(browser, By.ID, "otherTile")
                if email_field and not email_sent:
                    email_field.clear()
                    email_field.send_keys(email)
                    email_sent = True
                    email_field.send_keys(Keys.RETURN)
                elif password_field and not password_sent:
                    password_field.clear()
                    password_field.send_keys(password)
                    password_sent = True
                    password_field.send_keys(Keys.RETURN)
                    print("\aApprove Microsoft Authenticator if prompted; the script will continue automatically.")
                elif other_account and not email_sent and not account_picker_clicked:
                    other_account.click()
                    account_picker_clicked = True
                elif browser.find_elements(By.ID, "KmsiCheckboxField") and not kmsi_clicked:
                    yes_button = visible(browser, By.ID, "idSIButton9")
                    if yes_button:
                        yes_button.click()
                        kmsi_clicked = True

                number = visible(browser, By.ID, "idRichContext_DisplaySign")
                if number and number.text.strip() and number.text.strip() != shown_number:
                    shown_number = number.text.strip()
                    print(f"\aEnter {shown_number} in Microsoft Authenticator.")
        except StaleElementReferenceException:
            pass  # SSO navigated while a field was being inspected.
        time.sleep(0.5)
    raise RuntimeError(
        f"SIS login did not finish within {timeout} seconds. "
        "Check Chrome for 2FA, verification, an unexpected login page, or a sign-in error."
    )


def wait_until(moment):
    while datetime.datetime.now() < moment:
        time.sleep(min(1, max(0, (moment - datetime.datetime.now()).total_seconds())))


def review_and_close(browser):
    """Keep results available until the user finishes reviewing them."""
    try:
        browser.disconnect()
    except (OSError, WebDriverException):
        pass
    try:
        input("Chrome is available for review/manual completion. Press Enter to close this UC browser: ")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        try:
            browser.quit()
        except (OSError, WebDriverException):
            pass  # The user may have already closed the window.


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--login-now", action="store_true", help="Start login now instead of 10 minutes before registration")
    cli.add_argument("--chrome", help="Optional path to the Chrome executable")
    cli.add_argument("--login-timeout", type=int, default=600, metavar="SECONDS", help="Time allowed for login/2FA (default: 600)")
    args = cli.parse_args(argv)
    if args.login_timeout <= 0:
        cli.error("--login-timeout must be positive")
    browser = None
    try:
        driver_factory = load_driver_factory()
        email = input("JHU email address: ").strip()
        password = getpass.getpass("JHU password: ")
        if not email or not password:
            raise RuntimeError("Email and password must not be empty.")
        while True:
            try:
                target = registration_datetime(input("Time to register (24-hour HH:MM, computer local time): "))
                break
            except ValueError:
                print("Enter a valid time such as 07:00 or 14:30.")
        print(f"Registration scheduled for {target:%Y-%m-%d %H:%M:%S}.")
        print("This will select ALL classes in My Cart and click Register once. Ctrl+C cancels.")
        login_time = target - datetime.timedelta(minutes=10)
        if not args.login_now and datetime.datetime.now() < login_time:
            print(f"Waiting until {login_time:%Y-%m-%d %H:%M:%S} to log in. Have your phone ready then.")
            wait_until(login_time)
        options = {"browser": "chrome", "uc": True, "headless": False, "headed": True}
        if args.chrome:
            options["binary_location"] = args.chrome
        browser = driver_factory(**options)
        try:
            login(browser, email, password, timeout=args.login_timeout)
        finally:
            password = None
        select_sis_tab(browser)
        prepare_cart(browser)
        if datetime.datetime.now() >= target:
            print("The scheduled time passed during setup. Registering now.")
        register_at(browser, target)
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nRegistration automation stopped.")
        return 130
    except (RuntimeError, OSError, WebDriverException) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        print("Check SIS manually. A Register click is never retried automatically.")
        return 1
    finally:
        if browser is not None:
            review_and_close(browser)


if __name__ == "__main__":
    sys.exit(main())
