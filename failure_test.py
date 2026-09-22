#!/usr/bin/env python3
"""
failure_test.py — Stop one backend, verify continued service, restore, prove recovery.

Steps:
  1. Baseline: sample /instance 20x, expect both app-01 and app-02
  2. Stop app-02
  3. During failure: sample /instance 20x, count successes and errors
  4. Restore app-02
  5. Post-recovery: sample /instance 20x, expect both again

Exits 0 if all steps behave as expected; exits 1 otherwise.
"""

import sys
import time
import json
import subprocess
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8080"
SAMPLES = 20
TARGET = "app-02"  # the backend we will stop


def sample_instances(n=SAMPLES):
    """Hit /instance n times. Return (seen_set, success_count, error_count)."""
    seen = set()
    success = 0
    errors = 0
    for _ in range(n):
        try:
            with urllib.request.urlopen(BASE_URL + "/instance", timeout=3) as r:
                if r.status == 200:
                    data = json.loads(r.read().decode())
                    seen.add(data.get("instance_id"))
                    success += 1
                else:
                    errors += 1
        except Exception:
            errors += 1
    return seen, success, errors


def docker(action, container):
    """Run a docker command. Return (rc, stdout, stderr)."""
    r = subprocess.run(
        ["docker", action, container],
        capture_output=True, text=True, timeout=30,
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def wait_healthy(container, max_seconds=30):
    """Wait for a container to be running (not necessarily healthy)."""
    for _ in range(max_seconds):
        rc, out, _ = docker("inspect", container)
        if rc == 0 and '"Running": true' in out:
            return True
        time.sleep(1)
    return False


def main():
    print("=" * 60)
    print("BARQ failure test")
    print("=" * 60)

    # Step 1 — baseline
    print(f"\n[1] Baseline: sampling /instance {SAMPLES} times...")
    seen, ok, err = sample_instances()
    print(f"    successes={ok} errors={err} instances_seen={sorted(seen)}")
    if err > 0 or len(seen) < 2:
        print("FAIL: baseline should show 0 errors and both backends.")
        return 1
    if TARGET not in seen:
        print(f"FAIL: {TARGET} not in baseline ({sorted(seen)})")
        return 1

    # Step 2 — stop target
    print(f"\n[2] Stopping {TARGET}...")
    rc, _, err_msg = docker("stop", TARGET)
    if rc != 0:
        print(f"FAIL: could not stop {TARGET}: {err_msg}")
        return 1
    print(f"    {TARGET} stopped")

    # Step 3 — during failure
    print(f"\n[3] During failure: sampling /instance {SAMPLES} times...")
    seen, ok, err = sample_instances()
    print(f"    successes={ok} errors={err} instances_seen={sorted(seen)}")
    if TARGET in seen:
        print(f"FAIL: {TARGET} still responding after stop")
        return 1
    if ok == 0:
        print("FAIL: no successful requests while one backend was down")
        return 1
    print(f"    ✅ {ok}/{SAMPLES} requests succeeded with only one backend up")

    # Step 4 — restore
    print(f"\n[4] Restoring {TARGET}...")
    rc, _, err_msg = docker("start", TARGET)
    if rc != 0:
        print(f"FAIL: could not start {TARGET}: {err_msg}")
        return 1
    if not wait_healthy(TARGET, max_seconds=30):
        print(f"FAIL: {TARGET} did not come back within 30s")
        return 1
    print(f"    {TARGET} running again")

    # Give nginx a moment to re-include the upstream
    time.sleep(3)

    # Step 5 — post-recovery
    print(f"\n[5] Post-recovery: sampling /instance {SAMPLES} times...")
    seen, ok, err = sample_instances()
    print(f"    successes={ok} errors={err} instances_seen={sorted(seen)}")
    if TARGET not in seen:
        print(f"FAIL: {TARGET} not serving after recovery ({sorted(seen)})")
        return 1
    if len(seen) < 2:
        print(f"FAIL: only one backend seen after recovery ({sorted(seen)})")
        return 1
    print(f"    ✅ {TARGET} is serving requests again")

    print("\n" + "=" * 60)
    print("FAILURE TEST PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())