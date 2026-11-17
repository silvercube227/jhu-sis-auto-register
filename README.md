# 💾 JHU SIS Auto Registration Bot

Automate the cart and timed Register click on [JHU SIS](https://sis.jhu.edu/sswf/) with Selenium.

**Recommended workflow: `sis_register_manual.py --attach`.** Open Chrome with
debugging enabled, log in yourself, and let Selenium take over after you press
Enter in the terminal. Your Microsoft Authenticator sign-in stays in the browser;
the script does not ask for your email or password.

The SeleniumBase UC version remains experimental: it continued asking for a
security key instead of offering the expected Authenticator option in this setup.
The attempted browser-setting adjustment did not resolve that issue.

## Features

- Log in manually with Microsoft Authenticator before Selenium takes control.
- Attach to an existing debugging-enabled Chrome session.
- Navigate to My Cart and select all courses without unchecking an existing selection.
- Wait for your chosen registration time and click Register once.
- Allow time for slow SIS pages with explicit element waits.
- Keep Chrome open afterward so you can check results and finish any confirmation screens.

## Requirements

- macOS for the Chrome launch command below
- Python 3.10+ recommended for the current dependencies; required for the UC version
- [Google Chrome](https://www.google.com/chrome/) and a compatible ChromeDriver
- Git to clone the repository
- Your intended courses already added to the SIS Enrollment Cart

The upstream project reports testing the original script on macOS Sequoia and
Windows 11. The setup and browser-launch commands here target macOS; they do not
establish Windows support for the new variants.

## Installation & setup

### 1. Clone this fork

```bash
git clone https://github.com/silvercube227/jhu-sis-auto-register.git
cd jhu-sis-auto-register
```

This fork includes the manual and UC variants. The original project is
[charissa-luk/jhu-sis-auto-register](https://github.com/charissa-luk/jhu-sis-auto-register).
If you already have this checkout, open a terminal in its folder and skip cloning.

### 2. Check Python, then create and activate a virtual environment

```bash
python3 --version
```

Use Python 3.10 or newer for this setup. If needed, install it from
[python.org](https://www.python.org/downloads/) before continuing.

```bash
python3 -m venv sis-bot-venv
source sis-bot-venv/bin/activate
```

If the virtual environment already exists, just activate it. Activate it again
in each new terminal before running a script.

### 3. Install the required packages

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

This installs Selenium and `python-dateutil`. SeleniumBase is only needed for the
experimental UC version; its installation command appears in that section.

### 4. Prepare Chrome and ChromeDriver

Install/update Chrome and launch it once to finish its first-run setup. Modern
Selenium uses [Selenium Manager](https://www.selenium.dev/documentation/selenium_manager/)
to find or download a compatible driver when one is not already supplied. Allow
internet access for that first run. If you manage ChromeDriver yourself, use the
[official version-selection guide](https://developer.chrome.com/docs/chromedriver/downloads/version-selection)
and choose a version compatible with your installed Chrome.

### 5. Prepare your SIS cart

Add the intended courses to your Enrollment Cart in advance and confirm your
registration date/time and term. The script selects **every course in the cart**.
Allow about 10 minutes for login, Authenticator, verification, and cart loading.

## Sync your clock (macOS)

The Register click is scheduled using your computer's clock, so enable automatic
network time and verify the timezone before registration.

1. Open **Apple menu → System Settings → General → Date & Time**.
2. Turn on **Set time and date automatically**.
3. Keep the default time server, or click **Set** to enter an appropriate network time server; authenticate if prompted.
4. Check the timezone and convert your SIS registration time to that local timezone before entering it in the script.

See [Apple's Date & Time settings guide](https://support.apple.com/guide/mac-help/mchlp1124/mac).
On older macOS releases, these controls are under **System Preferences → Date & Time**.

The Navy server from the original instructions is `tick.usno.navy.mil` (U.S. Naval
Observatory, or USNO). [USNO directs individual users to public time servers](https://www.cnmoc.usff.navy.mil/Our-Commands/United-States-Naval-Observatory/Precise-Time-Department/Network-Time-Protocol-NTP/),
so keep your operating system's default service unless you have arranged direct
USNO access. This project has not verified which time source SIS uses. USNO and
NIST are different organizations; selecting a 24-hour display alone does not
synchronize your clock.

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
- **Sync your computer's clock before registration** using the [clock setup steps above](#sync-your-clock-macos).
- A time that has already passed when you start schedules **tomorrow**; check the printed date.
- If login or cart setup runs past the scheduled time, the manual version asks before registering immediately.
- Keep the SIS tab logged in and dismiss inactivity prompts yourself.
- Press `Ctrl+C` to cancel. Chrome stays open after cancellation, errors, or completion.
- Check SIS for enrollment results and complete any further confirmation screens. A Register click alone does not confirm enrollment.

Manual login does not guarantee that SIS will allow automation after attachment.
If verification blocks progress, complete registration manually in Chrome.

### Keep your Mac awake

Keep your computer plugged in with the lid open while waiting for registration.
The built-in `caffeinate` command needs no installation. To keep the Mac from
idle sleeping while the manual script runs, use this in place of its normal run
command after activating your virtual environment:

```bash
caffeinate -i python sis_register_manual.py --attach
```

Alternatively, in a separate terminal, prevent idle sleep for 7.5 hours
(27,000 seconds, for example midnight to 7:30 AM):

```bash
caffeinate -t 27000
```

Leave that terminal running; `Ctrl+C` ends the keep-awake period. Keeping the Mac
awake does not prevent SIS from logging out an inactive session.

If you prefer a menu-bar app and already have [Homebrew](https://brew.sh/), the
[Caffeine cask](https://formulae.brew.sh/cask/caffeine) is another option:

```bash
brew install --cask caffeine
```

Open Caffeine and enable it before waiting. Caffeine is optional; the built-in
command avoids an additional app installation.

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

- **`python3` or `git` is missing:** install the prerequisite before cloning or creating the environment. If macOS prompts to install Command Line Tools when you run Git, finish that installation first.
- **`ModuleNotFoundError`:** activate `sis-bot-venv` and run `python -m pip install -r requirements.txt` in the repository folder. For the UC version, also install `requirements-uc.txt`.
- **Cannot connect to `127.0.0.1:9222`:** check that the Chrome window launched with the command above is still open and that the script's port matches Chrome's port.
- **ChromeDriver version error:** use a ChromeDriver compatible with your installed Chrome version.
- **No logged-in SIS tab found:** finish login and verification, then open My Cart before pressing Enter at the handoff prompt.
- **Multiple SIS tabs found:** leave only the intended SIS tab open in the debugging browser and rerun the script.
- **SIS requires further authentication or verification:** complete it in Chrome. If automation remains blocked, register manually.

## License

[MIT License](LICENSE)

## Credits

Created by Charissa. Feel free to fork and improve.
