#!/usr/bin/env python3
"""Install an app from Google Play on a real Android device and smoke-test it.

Everything runs over ADB (USB or Wi-Fi). The run is screen-recorded, and the
output folder gets screenshots, the recording, a crash-log check and a
Markdown report a client can read.

Usage:  python3 android_install_smoke.py org.wikipedia
"""
import re
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

PKG = sys.argv[1] if len(sys.argv) > 1 else "org.wikipedia"
OUT = Path("runs") / f"{datetime.now():%Y%m%d-%H%M%S}-{PKG}"
OUT.mkdir(parents=True, exist_ok=True)
steps = []  # (step, result, note)


def adb(*args, check=True):
    r = subprocess.run(["adb", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"adb {' '.join(args)} failed: {r.stderr.strip()}")
    return (r.stdout or "").strip()


def record(step, ok, note=""):
    steps.append((step, "PASS" if ok else "FAIL", note))
    print(f"[{'PASS' if ok else 'FAIL'}] {step} {note}")


def screenshot(name):
    path = OUT / f"{len(list(OUT.glob('*.png'))) + 1:02d}-{name}.png"
    with open(path, "wb") as f:
        subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=f, check=True)
    return path.name


def find_node(pattern):
    """Return the screen center of the first UI element whose text or
    content-desc matches pattern, using a uiautomator dump."""
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    xml = adb("shell", "cat", "/sdcard/ui.xml")
    for node in ET.fromstring(xml).iter("node"):
        label = f"{node.get('text', '')} {node.get('content-desc', '')}"
        if re.search(pattern, label, re.I) and node.get("enabled") == "true":
            x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds")))
            return (x1 + x2) // 2, (y1 + y2) // 2
    return None


def installed():
    return bool(adb("shell", "pm", "path", PKG, check=False))


def main():
    model = adb("shell", "getprop", "ro.product.model")
    android = adb("shell", "getprop", "ro.build.version.release")
    record("Device connected", True, f"{model}, Android {android}")

    adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    locked = "isKeyguardShowing=true" in adb("shell", "dumpsys", "window")
    record("Device unlocked", not locked)
    if locked:
        return

    # Record from the Mac with scrcpy (some OEMs, e.g. OnePlus, block on-device screenrecord).
    rec = subprocess.Popen(["scrcpy", "--no-window", "--no-audio", "--no-control",
                            "--max-size", "1080", "--record", str(OUT / "screen-recording.mp4")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    try:
        run_steps()
    finally:
        rec.send_signal(signal.SIGINT)
        rec.wait(timeout=20)


def run_steps():
    adb("logcat", "-b", "crash", "-c", check=False)
    was_installed = installed()
    adb("shell", "am", "start", "-a", "android.intent.action.VIEW",
        "-d", f"market://details?id={PKG}")
    time.sleep(4)
    record("Play Store listing opened", True, screenshot("play-store-listing"))

    if was_installed:
        record("Install from Play Store", True, "already installed, skipped")
    else:
        btn = find_node(r"^\s*Install\s*$|^Install ")
        record("Install button found", btn is not None)
        if not btn:
            return
        adb("shell", "input", "tap", str(btn[0]), str(btn[1]))
        t0 = time.time()
        while not installed() and time.time() - t0 < 150:
            time.sleep(3)
        ok = installed()
        record("Install from Play Store", ok, f"{time.time() - t0:.0f}s")
        if not ok:
            return
        screenshot("install-complete")

    adb("shell", "monkey", "-p", PKG, "-c", "android.intent.category.LAUNCHER", "1")
    time.sleep(6)
    pid = adb("shell", "pidof", PKG, check=False)
    record("App launches and stays running", bool(pid), screenshot("first-launch"))

    adb("shell", "input", "swipe", "720", "2400", "720", "1000", "400")
    time.sleep(2)
    record("Scroll on first screen", True, screenshot("after-scroll"))

    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
    crashes = adb("logcat", "-b", "crash", "-d", check=False)
    hit = PKG in crashes
    (OUT / "crash-log.txt").write_text(crashes or "(no crashes logged)\n")
    record("No crashes in crash buffer", not hit)


def write_report():
    lines = [f"# Smoke test: `{PKG}`", "",
             f"Run: {datetime.now():%Y-%m-%d %H:%M}  ", f"Output: `{OUT}`", "",
             "| Step | Result | Notes |", "|---|---|---|"]
    lines += [f"| {s} | {r} | {n} |" for s, r, n in steps]
    passed = sum(r == "PASS" for _, r, _ in steps)
    lines += ["", f"**{passed}/{len(steps)} steps passed.**", ""]
    lines += [f"![{p.stem}]({p.name})" for p in sorted(OUT.glob("*.png"))]
    (OUT / "report.md").write_text("\n".join(lines) + "\n")
    print(f"\nReport: {OUT / 'report.md'}")


if __name__ == "__main__":
    try:
        main()
    finally:
        subprocess.run(["adb", "shell", "pkill", "-INT", "screenrecord"],
                       capture_output=True)
        write_report()
