# 💾 JHU SIS Auto Registration Bot

Automate the cart and timed Register click on [JHU SIS](https://sis.jhu.edu/sswf/) with Selenium.

**Recommended workflow: `sis_register_manual.py --attach`.** Open Chrome with
debugging enabled, log in yourself, and let Selenium take over after you press
Enter in the terminal. Your Microsoft Authenticator sign-in stays in the browser;
the script does not ask for your email or password.

The SeleniumBase UC version remains experimental: it continued asking for a
security key instead of offering the expected Authenticator option in this setup.
The attempted browser-setting adjustment did not resolve that issue.

## Requirements and setup

- macOS for the Chrome launch command below
- Python 3.10+ recommended for the current dependencies; required for the UC version
- Google Chrome and a compatible ChromeDriver
- Your intended courses already added to the SIS Enrollment Cart

From the repository folder:

```bash
python3 -m venv sis-bot-venv
source sis-bot-venv/bin/activate
python -m pip install -r requirements.txt
```

If the virtual environment already exists and dependencies are installed, just
activate it with `source sis-bot-venv/bin/activate`.

## Recommended: log in yourself, then attach Selenium

Start about **10 minutes before registration** so you have time to finish login.

### 1. Open Chrome with debugging enabled

Run this command in Terminal:

```bash
open -na "Google Chrome" --args \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/SIS Manual Chrome" \
  "https://sis.jhu.edu/sswf/"
```

This opens a separate, reusable Chrome profile. You can keep your usual Chrome
windows open. Selenium connects through the debugging port; it cannot use this
attachment method with an ordinary window opened from the Dock without debugging
enabled. Chrome requires a separate profile for this debugging flag.
See [Chrome's debugging-profile requirements](https://developer.chrome.com/blog/remote-debugging-port)
and [existing-session attachment](https://developer.chrome.com/docs/chromedriver/help/operation-not-supported-when-using-remote-debugging).

If this separate SIS profile is already open without debugging enabled, close
its windows and reopen it with the command above.

### 2. Log in and open your cart

In that Chrome window, sign in yourself and complete Microsoft Authenticator,
any human-verification checks, and any **Continue to SIS** screen. Open
**Registration → My Cart** for the intended term. Check the courses: the script
will select **all classes** in that cart.

### 3. Start the script and hand over control

From the repository folder:

```bash
source sis-bot-venv/bin/activate
python sis_register_manual.py --attach
```

Enter your registration time in 24-hour `HH:MM` format, then press **Enter** at
the handoff prompt when your SIS tab is ready. Selenium connects to that existing
browser, selects all courses, and clicks Register once at the scheduled time.
It can also navigate to My Cart if you leave the logged-in SIS menu visible.

Use `--attach 9333` if you launched Chrome with `--remote-debugging-port=9333`.

### Timing, cancellation, and results

- Times use your computer's **local timezone and clock**. Check both before running.
- A time that has already passed when you start schedules **tomorrow**; check the printed date.
- If login or cart setup runs past the scheduled time, the manual version asks before registering immediately.
- Keep the SIS tab logged in and dismiss inactivity prompts yourself.
- Press `Ctrl+C` to cancel. Chrome stays open after cancellation, errors, or completion.
- Check SIS for enrollment results and complete any further confirmation screens. A Register click alone does not confirm enrollment.

Manual login does not guarantee that SIS will allow automation after attachment.
If verification blocks progress, complete registration manually in Chrome.

### Keep your Mac awake

Keep your computer plugged in and awake while waiting for registration. In a
separate terminal, you can run the built-in command below to prevent idle sleep
for 7.5 hours (27,000 seconds):

```bash
caffeinate -t 27000
```

### Optional: let the script open Chrome

```bash
python sis_register_manual.py
```

Without `--attach`, the script opens a new Chrome window immediately using a
temporary profile. Log in there manually, open your intended cart, and press
Enter in the terminal to hand over control. Use `--chrome /path/to/chrome` to
specify an executable. The temporary profile path is printed; after closing that
Chrome window, you can delete the directory to remove its saved session.

## Experimental: SeleniumBase UC version

`sis_register_uc.py` uses [SeleniumBase UC Mode](https://seleniumbase.io/help_docs/uc_mode/)
to automate email/password entry, cart navigation, course selection, and the
scheduled Register click. It launches its own browser and shares the cart/timing
helpers in `sis_register_manual.py`, so keep both files together.

**Known unresolved issue:** the UC browser continued to request a security key
without offering the expected Microsoft Authenticator option. Removing
SeleniumBase's passkey-related disable flags and automatic permission denial did
not resolve it. Use the manual attachment workflow above for the current setup.

To experiment with UC, install its optional dependencies with Python 3.10+:

```bash
python -m pip install -r requirements-uc.txt
python sis_register_uc.py
```

It prompts for email, password (hidden), and registration time, then starts login
10 minutes before registration. Authenticator approval or human verification
still requires you when requested. It waits up to 10 minutes for login.

- `--login-now`: begin login immediately.
- `--login-timeout 900`: allow 15 minutes for login.
- `--chrome /path/to/chrome`: use a specific Chrome executable.

There is no manual handoff prompt before submission in this version. If setup
runs past the scheduled time, it registers as soon as the cart is ready. After
submission or an error, Chrome remains available for review until you press
Enter to close it. The first run may download SeleniumBase's UC ChromeDriver.
Live SIS registration with this version has not been verified.

## Original automated-login script

The upstream project reports testing this original version on macOS Sequoia and
Windows 11. The manual Chrome launch instructions above are for macOS.

```bash
python sis_register.py
```

The original script asks for your JHU email, password, and registration time. It
starts login 10 minutes early, waits for Microsoft 2FA, and proceeds to the cart.
It has encountered SIS human-verification blocks in the automated browser. Use
manual attachment if those prevent login, or complete registration yourself.

## Troubleshooting manual attachment

- **Cannot connect to `127.0.0.1:9222`:** check that the Chrome window launched with the command above is still open and that the script's port matches Chrome's port.
- **ChromeDriver version error:** use a ChromeDriver compatible with your installed Chrome version.
- **No logged-in SIS tab found:** finish login and verification, then open My Cart before pressing Enter at the handoff prompt.
- **Multiple SIS tabs found:** leave only the intended SIS tab open in the debugging browser and rerun the script.
- **SIS requires further authentication or verification:** complete it in Chrome. If automation remains blocked, register manually.

## License

[MIT License](LICENSE)

## Credits

Created by Charissa. Feel free to fork and improve.
