#!/usr/bin/env python3
"""
validate.py — Bounded environment validation for the BARQ assessment stack.

Checks:
  - Public access via NGINX
  - All required endpoints
  - Both backends serve requests
  - PostgreSQL + Redis readiness
  - Network isolation (NGINX cannot reach DB/cache)
  - No prohibited host ports published
  - Non-root container user

Output: PASS/FAIL per check, summary, non-zero exit on any failure.
"""

import sys
import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://127.0.0.1:8080"

def wait_for_stack(max_seconds=60):
    """Wait up to max_seconds for the stack to respond at all."""
    print(f"Waiting up to {max_seconds}s for the stack to be ready...")
    start = time.time()
    while time.time() - start < max_seconds:
        try:
            status, _ = http_get("/health", timeout=2)
            if status == 200:
                elapsed = time.time() - start
                print(f"Stack responded after {elapsed:.1f}s\n")
                return True
        except Exception:
            pass
        time.sleep(2)
    print(f"FAIL: stack did not respond within {max_seconds}s\n")
    return False

def http_get(path, timeout=3):
    """GET a path, return (status_code, body_str) or raise."""
    url = BASE_URL + path
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def check_public_access():
    """GET / returns 200 with instance_id."""
    try:
        status, body = http_get("/")
        data = json.loads(body)
        if status == 200 and "instance_id" in data:
            print("PASS: / returns 200 with instance_id")
            return True
        print(f"FAIL: / returned {status}, body={body[:100]}")
    except Exception as e:
        print(f"FAIL: / — {e}")
    return False

def check_health():
    """GET /health returns 200."""
    try:
        status, _ = http_get("/health")
        if status == 200:
            print("PASS: /health returns 200")
            return True
        print(f"FAIL: /health returned {status}")
    except Exception as e:
        print(f"FAIL: /health — {e}")
    return False

def check_ready():
    """GET /ready returns 200 with both deps ready."""
    try:
        status, body = http_get("/ready")
        data = json.loads(body)
        deps = data.get("dependencies", {})
        if status == 200 and deps.get("postgres") == "ready" and deps.get("redis") == "ready":
            print("PASS: /ready — postgres and redis ready")
            return True
        print(f"FAIL: /ready — status={status}, deps={deps}")
    except Exception as e:
        print(f"FAIL: /ready — {e}")
    return False

def check_instance():
    """GET /instance returns 200 with instance_id."""
    try:
        status, body = http_get("/instance")
        data = json.loads(body)
        if status == 200 and "instance_id" in data:
            print(f"PASS: /instance returns {data['instance_id']}")
            return True
        print(f"FAIL: /instance — status={status}")
    except Exception as e:
        print(f"FAIL: /instance — {e}")
    return False

def check_both_backends():
    """Hit /instance 10 times, verify both app-01 and app-02 respond."""
    seen = set()
    try:
        for _ in range(10):
            status, body = http_get("/instance")
            data = json.loads(body)
            seen.add(data.get("instance_id"))
        if "app-01" in seen and "app-02" in seen:
            print(f"PASS: both backends served requests: {seen}")
            return True
        print(f"FAIL: only saw {seen}, expected both app-01 and app-02")
    except Exception as e:
        print(f"FAIL: backend sampling — {e}")
    return False

def check_records():
    """POST /records creates a row, GET /records lists it."""
    try:
        # GET first
        status, body = http_get("/records")
        if status != 200:
            print(f"FAIL: GET /records returned {status}")
            return False

        # POST a new record
        title = "validate.py test record"
        data = json.dumps({"title": title}).encode()
        req = urllib.request.Request(
            BASE_URL + "/records",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            if r.status != 201:
                print(f"FAIL: POST /records returned {r.status}")
                return False
            posted = json.loads(r.read().decode())

        # GET again to verify
        status, body = http_get("/records")
        records = json.loads(body).get("records", [])
        if any(rec.get("title") == title for rec in records):
            print(f"PASS: /records create+list works (id={posted.get('record', {}).get('id')})")
            return True
        print("FAIL: created record not found in list")
    except Exception as e:
        print(f"FAIL: /records — {e}")
    return False

def check_counter():
    """GET /counter increments and returns integer."""
    try:
        status1, body1 = http_get("/counter")
        status2, body2 = http_get("/counter")
        c1 = json.loads(body1).get("counter")
        c2 = json.loads(body2).get("counter")
        if status1 == 200 and status2 == 200 and isinstance(c2, int) and c2 > c1:
            print(f"PASS: /counter increments ({c1} -> {c2})")
            return True
        print(f"FAIL: /counter did not increment ({c1} -> {c2})")
    except Exception as e:
        print(f"FAIL: /counter — {e}")
    return False

def check_404():
    """Unknown route returns 404."""
    try:
        status, _ = http_get("/this-route-does-not-exist")
        if status == 404:
            print("PASS: unknown route returns 404")
            return True
        print(f"FAIL: unknown route returned {status}, expected 404")
    except Exception as e:
        print(f"FAIL: unknown route — {e}")
    return False

def check_non_root_user():
    """app-01 container runs as 'app', not 'root'."""
    import subprocess
    try:
        r = subprocess.run(
            ["docker", "exec", "app-01", "whoami"],
            capture_output=True, text=True, timeout=5,
        )
        user = r.stdout.strip()
        if user == "app":
            print("PASS: app-01 runs as non-root user 'app'")
            return True
        print(f"FAIL: app-01 runs as '{user}', expected 'app'")
    except Exception as e:
        print(f"FAIL: could not check container user — {e}")
    return False

def check_network_isolation():
    """NGINX must not be on the backend network."""
    import subprocess
    try:
        r = subprocess.run(
            ["docker", "network", "inspect", "barq-assessment_backend",
             "--format", "{{range .Containers}}{{.Name}} {{end}}"],
            capture_output=True, text=True, timeout=5,
        )
        containers = r.stdout.strip().split()
        if "nginx" in containers:
            print(f"FAIL: nginx found on backend network: {containers}")
            return False
        expected = {"postgres", "redis", "app-01", "app-02"}
        if expected.issubset(set(containers)):
            print(f"PASS: backend network isolation correct: {sorted(containers)}")
            return True
        print(f"FAIL: backend network containers unexpected: {containers}")
    except Exception as e:
        print(f"FAIL: network isolation — {e}")
    return False

def check_no_prohibited_ports():
    """Ports 15432 and 16379 must not be listening on the host."""
    import socket
    ok = True
    for port in (15432, 16379):
        s = socket.socket()
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            print(f"FAIL: host port {port} is open (should be closed)")
            ok = False
        except (socket.timeout, ConnectionRefusedError, OSError):
            print(f"PASS: host port {port} is closed")
        finally:
            s.close()
    return ok

def main():
    print("=" * 60)
    print("BARQ environment validation")
    print("=" * 60)

    if not wait_for_stack(max_seconds=60):
        sys.exit(1)
        
    checks = [
        check_public_access,
        check_health,
        check_ready,
        check_instance,
        check_both_backends,
        check_records,
        check_counter,
        check_404,
        check_non_root_user,
        check_network_isolation,
        check_no_prohibited_ports,
    ]
    results = [c() for c in checks]
    passed = sum(results)
    total = len(results)
    print("=" * 60)
    print(f"{passed}/{total} checks passed")
    print("=" * 60)
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()