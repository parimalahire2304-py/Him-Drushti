#!/usr/bin/env python3
"""
PHASE 7A — ORCHESTRATED SINGLE-MACHINE TEST (PUBLISH + VALIDATE)

Runs the Laptop-1 publisher and the LAN-broker validator in the correct
order so the subscriber is already listening when messages are published.
This exercises the SAME LAN broker path (10.20.231.143:1883) that Laptop-2
would use; it is the reproducible pre-check before the true two-machine run.

Requires: Mosquitto bound to all interfaces (phase7a_enable_broker.ps1).

Run (on Laptop-1):
    python scripts\\communication\\run_phase7a_test.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

COMM_DIR = Path(__file__).resolve().parent
PUB = COMM_DIR / "run_offshore_publish.py"
VAL = COMM_DIR / "validate_phase7a.py"


def main() -> int:
    print("=" * 68)
    print("PHASE 7A — SINGLE-MACHINE LAN-BROKER TEST")
    print("  (publisher + validator over the real LAN broker address)")
    print("=" * 68)

    print("\n[1/2] Starting validator in background (listening on LAN broker)...")
    val = subprocess.Popen([sys.executable, str(VAL)], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True)

    print("[ ] waiting for validator to connect & subscribe...")
    time.sleep(6)

    print("\n[2/2] Running Laptop-1 publisher (publishes decision cycle)...")
    pub_res = subprocess.run([sys.executable, str(PUB)], capture_output=True, text=True)
    print(pub_res.stdout)
    if pub_res.stderr:
        print("  [publisher stderr]", pub_res.stderr)

    print("\n[.] waiting for validator to collect messages...")
    time.sleep(8)

    print("\n--- VALIDATOR OUTPUT ---")
    out, _ = val.communicate(timeout=20)
    print(out)
    print("--- END VALIDATOR OUTPUT ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
