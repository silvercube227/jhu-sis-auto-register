"""Log in yourself, then let Selenium register the courses in your SIS cart."""

import argparse
import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import NoSuchWindowException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


SIS_URL = "https://sis.jhu.edu/sswf/"
SELECT_ALL = (By.ID, "SelectAllCheckBox")
REGISTER = (By.ID, "ctl00_contentPlaceHolder_ibEnroll")
REGISTRATION = (By.XPATH, "//a[span[text()='Registration']]")


def registration_datetime(value, now=None):
    """Use the next occurrence of HH:MM in the computer's local timezone."""
    now = now or datetime.datetime.now()
    parsed = datetime.datetime.strptime(value.strip(), "%H:%M")
    target = now.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return target


def find_chrome(explicit_path=None):
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if path.is_file():
            return str(path)
        raise RuntimeError(f"Chrome executable not found: {path}")
    mac_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if mac_path.is_file():
        return str(mac_path)
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome not found. Pass --chrome /path/to/chrome/executable.")


def launch_chrome(chrome_path):
    """Launch Chrome directly; Selenium is not involved during login."""
    profile = Path(tempfile.mkdtemp(prefix="sis-manual-chrome-"))
    process = subprocess.Popen(
        [
            chrome_path,
            "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            SIS_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"Chrome profile: {profile}")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Chrome exited before it was ready. Try --chrome with its executable path.")
        try:
            port = int((profile / "DevToolsActivePort").read_text().splitlines()[0])
            if 0 < port < 65536:
                return f"127.0.0.1:{port}"
        except (OSError, ValueError, IndexError):
            pass
        time.sleep(0.1)
    raise RuntimeError("Chrome's debugging port did not become ready within 30 seconds.")


def attach_browser(address):
    options = Options()
    options.debugger_address = address
    # Attach mode rejects launch-only options such as "detach". Cleanup below
    # stops ChromeDriver without sending a quit command to the existing browser.
    # Leave unexpected alerts for the user instead of accepting registration dialogs.
    options.set_capability("unhandledPromptBehavior", "ignore")
    return webdriver.Chrome(options=options)


def select_sis_tab(browser):
    """Find an authenticated SIS page, even if login opened another tab."""
    candidates = []
    for handle in browser.window_handles:
        try:
            browser.switch_to.window(handle)
            if urlparse(browser.current_url).hostname != "sis.jhu.edu":
                continue
            if browser.find_elements(*SELECT_ALL):
                candidates.append((0, handle))
            elif browser.find_elements(*REGISTRATION):
                candidates.append((1, handle))
        except NoSuchWindowException:
            continue
    if not candidates:
        raise RuntimeError(
            "No logged-in SIS tab found. Finish login, 2FA, any verification and "
            "'Continue to SIS' screens before handing control to Selenium."
        )
    best_rank = min(rank for rank, _ in candidates)
    matches = [handle for rank, handle in candidates if rank == best_rank]
    if len(matches) != 1:
        raise RuntimeError("Multiple SIS tabs found. Leave only the intended SIS tab open and retry.")
    browser.switch_to.window(matches[0])


def prepare_cart(browser):
    wait = WebDriverWait(browser, 120)
    if not browser.find_elements(*SELECT_ALL):
        wait.until(EC.element_to_be_clickable(REGISTRATION)).click()
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "My Cart"))).click()
    select_all = wait.until(EC.element_to_be_clickable(SELECT_ALL))
    if not select_all.is_selected():
        select_all.click()
    wait.until(EC.element_to_be_clickable(REGISTER))
    print("Cart ready: all classes selected. Check the intended term and courses in Chrome.")


def register_at(browser, target):
    print(f"Waiting to click Register at {target:%Y-%m-%d %H:%M:%S} (computer local time).")
    print("Keep this SIS tab logged in. Dismiss inactivity prompts yourself. Ctrl+C cancels.")
    while datetime.datetime.now() < target:
        time.sleep(0.1)
    # Re-find controls after the wait: SIS may have replaced the original DOM nodes.
    if urlparse(browser.current_url).hostname != "sis.jhu.edu":
        raise RuntimeError("The tab left SIS. Log in again and check your cart manually.")
    if not browser.find_element(*SELECT_ALL).is_selected():
        raise RuntimeError("Cart selection changed. Check your courses and register manually.")
    button = WebDriverWait(browser, 10).until(EC.element_to_be_clickable(REGISTER))
    button.click()
    print("Register clicked once. Check SIS for results and complete any confirmation screens.")


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument("--chrome", help="Path to the Chrome executable (auto-detected on macOS/Linux)")
    mode.add_argument(
        "--attach", nargs="?", const=9222, type=int, metavar="PORT",
        help="Attach to Chrome you already opened with remote debugging (default port: 9222)",
    )
    args = cli.parse_args(argv)
    if args.attach is not None and not 1 <= args.attach <= 65535:
        cli.error("--attach PORT must be between 1 and 65535")
    browser = None
    try:
        while True:
            value = input("Time to register (24-hour HH:MM, computer local time): ")
            try:
                target = registration_datetime(value)
                break
            except ValueError:
                print("Enter a valid time such as 07:00 or 14:30.")
        print(f"Registration scheduled for {target:%Y-%m-%d %H:%M:%S}.")
        if args.attach is not None:
            address = f"127.0.0.1:{args.attach}"
            print(f"Using your existing Chrome session at {address}.")
            print("Chrome must already be running with remote debugging enabled; see README.md.")
            print("Finish signing in to SIS, including 2FA and any verification, in that window.")
        else:
            print("Chrome opens now. For a short wait, run this about 10 minutes before registration.")
            address = launch_chrome(find_chrome(args.chrome))
            print("In the NEW Chrome window, sign in to SIS and complete 2FA and any verification.")
        print("Open Registration > My Cart for the intended term, or leave the SIS menu visible.")
        print("Selenium will select ALL classes in that cart and click Register at the scheduled time.")
        input("When you are ready for Selenium to take control, press Enter here (Ctrl+C cancels): ")
        try:
            browser = attach_browser(address)
        except WebDriverException as error:
            raise RuntimeError(
                f"Could not attach to Chrome at {address}. Check that Chrome is still open "
                "with the matching remote-debugging port and a separate user-data-dir, "
                f"and that ChromeDriver matches your Chrome version. Details: {error}"
            ) from error
        select_sis_tab(browser)
        prepare_cart(browser)
        if datetime.datetime.now() >= target:
            input("The scheduled time has passed. Press Enter to register NOW, or Ctrl+C to cancel: ")
        register_at(browser, target)
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. Chrome remains open for manual registration.")
        return 130
    except (OSError, RuntimeError, WebDriverException) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        print("Chrome remains open. Check SIS and finish manually if needed; no click will be retried.")
        return 1
    finally:
        # Stop only ChromeDriver; quitting the browser would discard the user's session.
        if browser is not None:
            browser.service.stop()


if __name__ == "__main__":
    sys.exit(main())
