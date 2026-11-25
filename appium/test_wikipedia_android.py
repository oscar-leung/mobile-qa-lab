"""Appium version of the Android smoke test: search Wikipedia on a real OnePlus 11.

Run:
    appium &                                   # server on :4723
    pytest appium/test_wikipedia_android.py -v
"""
import os

import pytest
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

UDID = os.environ.get("ANDROID_UDID", "192.168.1.76:5555")
OUT = os.path.join(os.path.dirname(__file__), "..", "runs", "appium-android")


@pytest.fixture
def driver():
    o = UiAutomator2Options()
    o.udid = UDID
    o.app_package = "org.wikipedia"
    o.app_activity = "org.wikipedia.main.MainActivity"
    o.no_reset = True
    o.new_command_timeout = 120
    d = webdriver.Remote("http://127.0.0.1:4723", options=o)
    os.makedirs(OUT, exist_ok=True)
    yield d
    d.quit()


def skip_onboarding(driver):
    """First launch shows intro screens; tap Skip / Get started / Forward until the feed shows."""
    for _ in range(6):
        for label in ("Skip", "Get started", "Continue"):
            els = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{label}")')
            if els:
                els[0].click()
                break
        else:
            fwd = driver.find_elements(AppiumBy.ACCESSIBILITY_ID, "Forward")
            if not fwd:
                return
            fwd[0].click()


def test_search_returns_davis(driver):
    wait = WebDriverWait(driver, 20)
    skip_onboarding(driver)
    # Promo sheets (e.g. "A Faster way to Search" widget offer) cover the nav bar: dismiss with Back.
    for _ in range(3):
        if driver.find_elements(AppiumBy.ID, "org.wikipedia:id/nav_tab_search"):
            break
        driver.back()
    wait.until(EC.element_to_be_clickable((AppiumBy.ID, "org.wikipedia:id/nav_tab_search"))).click()
    bar = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Search Wikipedia")')
    if bar:
        bar[0].click()
    box = wait.until(EC.presence_of_element_located((AppiumBy.ID, "org.wikipedia:id/search_src_text")))
    box.send_keys("Davis, California")
    # Results re-render as you type, so re-find them on every poll (avoids StaleElementReference).
    def davis_titles(d):
        try:
            # Result rows are plain TextViews (no resource-id in this app version).
            texts = [e.text for e in d.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().className("android.widget.TextView").textContains("Davis")')]
        except StaleElementReferenceException:
            return False
        return [t for t in texts if "Davis" in t] or False

    hits = WebDriverWait(driver, 20, ignored_exceptions=[StaleElementReferenceException]).until(davis_titles)
    driver.save_screenshot(os.path.join(OUT, "search-results.png"))
    assert hits
