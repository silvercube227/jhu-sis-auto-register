import os
import sys
import time
import datetime
from dateutil import parser
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoAlertPresentException
from selenium.common.exceptions import TimeoutException, NoSuchElementException, NoAlertPresentException, StaleElementReferenceException
from urllib.parse import urlparse
import tempfile
import getpass
import threading

# --------------------------
# Interactive input setup
# --------------------------
print("📝 Enter the following information to set up the SIS bot:")
email = input("📧 Your JHU email address: ")
password = getpass.getpass("🔐 Your JHU password: ")
time_input = input("⏰ Time to register (24-hour format HH:MM): ")

# --------------------------
# Time setup
# --------------------------
registration_time = parser.parse(time_input)
now = datetime.datetime.now()
registration_time = registration_time.replace(year=now.year, month=now.month, day=now.day)

# If it's already past the input time today, register tomorrow
if registration_time <= now:
    registration_time += datetime.timedelta(days=1)

# --------------------------
# Wait until 10 minutes before registration to log in to avoid inactivity log out
# --------------------------
login_time = registration_time - datetime.timedelta(minutes=10)
print(f"📱 Have your phone ready at {login_time.strftime('%H:%M:%S')} to approve Microsoft's 2FA prompt.")
print(f"⏳ Waiting until {login_time.strftime('%H:%M:%S')} to begin login...")
while datetime.datetime.now() < login_time:
    time.sleep(1)
# --------------------------
# Chrome Setup: Use saved Chrome login session
# --------------------------
unique_user_data_dir = tempfile.mkdtemp()
chrome_options = Options()
chrome_options.add_argument(f"--user-data-dir={unique_user_data_dir}")
chrome_options.add_argument("profile-directory=Default")
chrome_options.add_experimental_option("detach", True)

browser = webdriver.Chrome(options=chrome_options)
browser.get("https://sis.jhu.edu/sswf/")

# Background thread to handle inactivity popup
def stay_logged_in_watcher(browser):
    while True:
        try:
            alert = browser.switch_to.alert
            print("⚠️ Inactivity alert detected! Clicking 'OK' to stay logged in.")
            alert.accept()
            print("✅ Alert dismissed.")
        except NoAlertPresentException:
            pass
        time.sleep(5)  # Check every 5 seconds

# Start the watcher in background
watcher_thread = threading.Thread(target=stay_logged_in_watcher, args=(browser,), daemon=True)
watcher_thread.start()


# --------------------------
# Microsoft 2FA helpers
# --------------------------
MFA_TIMEOUT = 300  # seconds allowed to finish 2FA on your phone before giving up

def find_visible(browser, by, value):
    """Return the first visible element matching the locator, or None."""
    for element in browser.find_elements(by, value):
        if element.is_displayed():
            return element
    return None

def wait_for_two_factor(browser):
    """Wait for you to finish Microsoft's 2FA on your phone, until we land back on SIS."""
    print("\a📱 Complete Microsoft's 2FA on your phone now (approve the Authenticator prompt or scan the QR code in Chrome).")
    deadline = time.time() + MFA_TIMEOUT
    shown_number = None

    while time.time() < deadline:
        try:
            if (urlparse(browser.current_url).hostname or "").endswith("sis.jhu.edu"):
                print("✅ 2FA complete, back on SIS.")
                return

            if find_visible(browser, By.ID, "passwordError"):
                raise Exception("Microsoft rejected the password.")

            # Number matching: Authenticator asks you to type the number shown on screen
            number = find_visible(browser, By.ID, "idRichContext_DisplaySign")
            if number and number.text.strip() and number.text.strip() != shown_number:
                shown_number = number.text.strip()
                print(f"\a🔢 Enter {shown_number} in Microsoft Authenticator to approve the sign-in.")

            # "Stay signed in?" page that appears after 2FA
            if browser.find_elements(By.ID, "KmsiCheckboxField"):
                yes_button = find_visible(browser, By.ID, "idSIButton9")
                if yes_button:
                    yes_button.click()
                    print("✅ Clicked 'Yes' on 'Stay signed in?'.")
        except StaleElementReferenceException:
            pass  # page changed while we were reading it, just check again

        time.sleep(1)

    raise Exception(f"2FA wasn't completed within {MFA_TIMEOUT // 60} minutes.")

BOT_CHECK_TIMEOUT = 300  # seconds allowed to click through SIS's bot check before giving up

def wait_for_bot_check(browser):
    """Give you time to click SIS's "verify you aren't a bot" check, until the SIS menu loads."""
    registration_link = (By.XPATH, "//a[span[text()='Registration']]")
    try:
        WebDriverWait(browser, 10).until(EC.presence_of_element_located(registration_link))
        return
    except TimeoutException:
        print(f"\a🤖 If Chrome shows a \"verify you aren't a bot\" check, click it now. Waiting up to {BOT_CHECK_TIMEOUT // 60} minutes...")

    try:
        WebDriverWait(browser, BOT_CHECK_TIMEOUT).until(EC.presence_of_element_located(registration_link))
        print("✅ Past the bot check, SIS loaded.")
    except TimeoutException:
        raise Exception(f"SIS didn't load within {BOT_CHECK_TIMEOUT // 60} minutes of the bot check.")


# --------------------------
# Handling "Sign In" Button
# --------------------------
print("🔑 Searching for the 'Sign In' button and logging in with provided credentials...")

try:
    sign_in_button = WebDriverWait(browser, 60).until(
        EC.presence_of_element_located((By.XPATH, "//a[contains(text(),'Sign In')]"))
    )
    sign_in_button.click()
    print("✅ 'Sign In' button clicked.")

    # Wait for the Microsoft login page and make sure the email field is visible & interactable
    WebDriverWait(browser, 69).until(
        EC.visibility_of_element_located((By.NAME, "loginfmt"))
    )
    email_field = browser.find_element(By.NAME, "loginfmt")

    # Ensure it's clickable
    WebDriverWait(browser, 69).until(EC.element_to_be_clickable((By.NAME, "loginfmt")))
    email_field.click()  # This helps in some cases
    email_field.clear()  # Just in case it's prefilled and can't be typed into
    email_field.send_keys(email)
    email_field.send_keys(Keys.RETURN)

    time.sleep(2)

    WebDriverWait(browser, 69).until(EC.element_to_be_clickable((By.NAME, "passwd")))
    password_field = browser.find_element(By.NAME, "passwd")
    password_field.send_keys(password)
    password_field.send_keys(Keys.RETURN)

    # --------------------------
    # Handling Microsoft 2FA
    # --------------------------
    wait_for_two_factor(browser)

    # --------------------------
    # Handling "verify you aren't a bot" check
    # --------------------------
    wait_for_bot_check(browser)
    # Enable the following block only for an active survey with a Continue to SIS button.
    """
    try:
        continue_btn = WebDriverWait(browser, 60).until(
            EC.presence_of_element_located((By.ID, 'ctl00_contentPlaceHolder_btnContinueToIsis'))
        )
        print("✅ SIS post-login page loaded.")
        browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", continue_btn)
        browser.execute_script("arguments[0].click();", continue_btn)
        print("✅ Clicked 'Continue to SIS' button.")
    except Exception as e:
        print(f"❌ Failed to click 'Continue to SIS'. Error: {e}")
        sys.exit(1)
    """

except Exception as e:
    print(f"❌ Login failed. Error: {str(e)}")
    sys.exit(1)

# --------------------------
# Navigate to My Cart
# --------------------------
try:
    registration_link = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//a[span[text()='Registration']]"))
    )
    registration_link.click()
    print("✅ Clicked 'Registration'")
except Exception as e:
    print(f"❌ Failed to click 'Registration': {e}")
    browser.quit()
    sys.exit(1)

try:
    my_cart_link = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable((By.LINK_TEXT, "My Cart"))
    )
    my_cart_link.click()
    print("✅ Clicked 'My Cart'")
except Exception as e:
    print(f"❌ Failed to click 'My Cart': {e}")
    browser.quit()
    sys.exit(1)

MAX_RETRIES = 10
WAIT_TIME = 120

for attempt in range(MAX_RETRIES):
    try:
        print(f"🔄 Attempt {attempt + 1} to load cart elements...")

        WebDriverWait(browser, WAIT_TIME).until(
            EC.element_to_be_clickable((By.ID, 'SelectAllCheckBox'))
        )
        select_all = browser.find_element(By.ID, 'SelectAllCheckBox')
        select_all.click()
        print("✅ Clicked 'Select All' checkbox.")

        WebDriverWait(browser, WAIT_TIME).until(
            EC.element_to_be_clickable((By.ID, 'ctl00_contentPlaceHolder_ibEnroll'))
        )
        register_button = browser.find_element(By.ID, 'ctl00_contentPlaceHolder_ibEnroll')
        print("✅ Register button is ready.")
        break

    except (TimeoutException, NoSuchElementException) as e:
        print(f"⚠️ Attempt {attempt + 1} failed: {str(e)}")
        if attempt == MAX_RETRIES - 1:
            print("❌ SIS is too slow or DOM broke. Exiting.")
            browser.save_screenshot("load_cart_fail.png")
            browser.quit()
            sys.exit(1)
        else:
            print("🔁 Retrying...")

# WAIT for registration time
print(f"⏳ Waiting for registration at {registration_time.strftime('%H:%M:%S')}...")
while datetime.datetime.now() < registration_time:
    time.sleep(0.1) # checks every 10th of a second for registration time

# Click register
try:
    print("🚀 Clicking Register...")
    register_button.click()
    print("✅ Register clicked!")
    time.sleep(10)
except Exception as e:
    print(f"❌ Failed to click register: {e}")
    browser.quit()
    sys.exit(1)
