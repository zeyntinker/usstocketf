from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLAG = ROOT / "cache" / "shutdown.flag"
URL = "http://127.0.0.1:8517"
LOG_FILE = ROOT / "cache" / "launcher.log"


def browser_command() -> list[str]:
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    browser = next((path for path in candidates if path.exists()), None)
    if not browser:
        raise RuntimeError("Microsoft Edge 또는 Google Chrome을 찾을 수 없습니다.")
    profile = ROOT / "cache" / "app-browser-profile"
    profile.mkdir(parents=True, exist_ok=True)
    return [str(browser), f"--app={URL}", f"--user-data-dir={profile}", "--no-first-run"]


def wait_for_server(process: subprocess.Popen[bytes]) -> bool:
    for _ in range(40):
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(URL, timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def main() -> None:
    FLAG.unlink(missing_ok=True)
    command = [sys.executable, "-m", "streamlit", "run", "app.py", "--server.address", "127.0.0.1", "--server.port", "8517", "--server.headless", "true"]
    LOG_FILE.parent.mkdir(exist_ok=True)
    log = LOG_FILE.open("w", encoding="utf-8")
    log.write(f"Starting: {' '.join(command)}\n")
    log.flush()
    server = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    try:
        if not wait_for_server(server):
            raise RuntimeError("Local app server did not start. See cache/launcher.log.")
        browser = subprocess.Popen(browser_command(), cwd=ROOT)
        while browser.poll() is None and not FLAG.exists():
            time.sleep(0.3)
        if FLAG.exists() and browser.poll() is None:
            browser.terminate()
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
        FLAG.unlink(missing_ok=True)
        log.close()


if __name__ == "__main__":
    main()
