#!/usr/bin/env python3
"""
Install or uninstall the chess agent as a macOS LaunchAgent.

Install (runs automatically at login):
    python chess_agent/install_service.py

Uninstall:
    python chess_agent/install_service.py uninstall

Logs:
    tail -f /tmp/chess_agent.log
"""

import subprocess
import sys
from pathlib import Path

LABEL = "com.reachy.chess-agent"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
PROJECT_DIR = Path(__file__).parent.parent.resolve()
PYTHON = sys.executable
SCRIPT = PROJECT_DIR / "chess_agent" / "laptop_agent.py"
LOG = "/tmp/chess_agent.log"

PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{script}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{project_dir}</string>

    <!-- Start immediately and restart if it exits -->
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>

    <!-- Throttle restarts to avoid a crash loop -->
    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>StandardOutPath</key>
    <string>{log}</string>
    <key>StandardErrorPath</key>
    <string>{log}</string>
</dict>
</plist>
"""


def install():
    plist = PLIST_TEMPLATE.format(
        label=LABEL,
        python=PYTHON,
        script=SCRIPT,
        project_dir=PROJECT_DIR,
        log=LOG,
    )
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist)

    # Unload first in case a stale version is already registered
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    result = subprocess.run(["launchctl", "load", "-w", str(PLIST_PATH)])

    if result.returncode == 0:
        print(f"✓ Chess agent installed — starts automatically at login")
        print(f"  Python:  {PYTHON}")
        print(f"  Script:  {SCRIPT}")
        print(f"  Logs:    tail -f {LOG}")
        print(f"  Remove:  python chess_agent/install_service.py uninstall")
    else:
        print("✗ launchctl load failed — check the plist at:")
        print(f"  {PLIST_PATH}")


def uninstall():
    if not PLIST_PATH.exists():
        print("Chess agent service is not installed.")
        return
    subprocess.run(["launchctl", "unload", "-w", str(PLIST_PATH)], capture_output=True)
    PLIST_PATH.unlink()
    print("✓ Chess agent service removed.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "install"
    if cmd == "uninstall":
        uninstall()
    else:
        install()
