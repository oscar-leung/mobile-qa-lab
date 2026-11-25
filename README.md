# Mobile QA Lab: real-device testing on iPhone and Android

A small, practical setup for testing apps on **real phones** from a Mac:
installing from the store, launching, recording the screen, and handing the
client a readable report with screenshots and a recording.

Built by [Oscar Leung](https://oscar-leung.github.io), QA/SDET engineer in Davis, CA.

## Devices
| Device | OS | How it's driven |
|---|---|---|
| OnePlus 11 (CPH2451) | Android 15 | ADB over Wi-Fi, scripted with Python |
| iPhone 17 Pro Max | iOS | iPhone Mirroring / Vysor on macOS, screen recording, XCUITest via Xcode |
| MacBook Pro | macOS | Host for ADB, Xcode tools, and recording |

## What the Android script does
`android_install_smoke.py <package>`:
1. Confirms the device is connected and unlocked.
2. Starts an on-device screen recording.
3. Opens the app's Google Play listing and taps **Install** (found by reading the UI tree, not hard-coded coordinates).
4. Waits for the install to finish, launches the app, checks it stays running.
5. Scrolls the first screen, goes back, and checks Android's crash log for the app.
6. Writes `runs/<timestamp>-<package>/report.md` with a PASS/FAIL table, screenshots, crash log and `screen-recording.mp4`.

```bash
adb connect <phone-ip>:5555        # or plug in by USB
python3 android_install_smoke.py org.wikipedia
```

## Why this matters for clients
- **Google Play closed testing** (the 14-day / 12+ tester rule): install, open daily, report what breaks.
- **TestFlight / App Store betas**: real-device installs with screen-recorded walkthroughs.
- **"Install and record" usability tests**: think-aloud recordings of onboarding.
- **Cross-device bug reports**: same steps on iOS and Android, with device, OS, build, steps, expected vs actual and evidence.

## Sample runs
- [iPhone 17 Pro Max report](runs/sample-iphone17-wikipedia/report.md): same app installed from the App Store and tested through iPhone Mirroring on the Mac, 6/6 steps passed.
- [Real report from the OnePlus 11](runs/sample-oneplus11-wikipedia/report.md): Wikipedia installed from Google Play in 7 s, launched, scrolled, 8/8 checks passed, with screenshots and a screen recording.

## Requirements
- Python 3.9+, `adb` (Android platform-tools), `scrcpy` for recording (`brew install scrcpy`)
- USB debugging or Wireless debugging on the phone, screen unlocked

## Appium suite (same flow, real device)
`appium/test_wikipedia_android.py` drives the OnePlus 11 through Appium + UiAutomator2 and searches Wikipedia for "Davis, California". **Passes in ~10 s.**

Real-device problems it handles, found while building it:
- **First-launch onboarding** on a fresh install: taps Skip / Forward until the feed shows.
- **A promo sheet** ("A Faster way to Search" widget offer) covering the nav bar: dismissed with Back before continuing.
- **Results re-render while typing** (StaleElementReference): the wait re-finds rows on every poll.
- **Result rows have no resource-id** in this app version: matched by class + text instead.

```bash
npm i -g appium && appium driver install uiautomator2
pip install Appium-Python-Client pytest
export ANDROID_HOME=~/Library/Android/sdk
appium &
ANDROID_UDID=<serial or ip:5555> pytest appium/test_wikipedia_android.py -v
```
