# Log analysis

Analysis of the three historical logs. All numbers come from the commands
listed in the "Commands / scripts" section. Original log files were not
modified.

## Commands / scripts

All commands run from the repository root against the original files.

Line counts:

    wc -l logs/access.log logs/error.log logs/application.log

Malformed line detection (JSON parse):

    python3 -c "
    import json
    for name in ['access','application']:
        bad = 0
        with open(f'logs/{name}.log') as f:
            for line in f:
                try: json.loads(line)
                except: bad += 1
        print(f'{name}.log: malformed={bad}')
    "

Duplicate request_id detection:

    python3 -c "
    import json
    from collections import Counter
    c = Counter()
    with open('logs/access.log') as f:
        for line in f:
            try: c[json.loads(line)['request_id']] += 1
            except: pass
    dupes = sum(1 for v in c.values() if v > 1)
    print(f'distinct={len(c)} duplicated={dupes}')
    "

Status counts and error rate:

    python3 -c "
    import json
    from collections import Counter
    c = Counter()
    with open('logs/access.log') as f:
        for line in f:
            try: c[json.loads(line)['status']] += 1
            except: pass
    total = sum(c.values())
    err = sum(v for k,v in c.items() if k >= 500)
    print(dict(sorted(c.items())))
    print(f'total={total} 5xx={err} err_rate={100*err/total:.1f}%')
    "

Latency percentiles (request_time is in seconds):

    python3 -c "
    import json, statistics
    times = []
    with open('logs/access.log') as f:
        for line in f:
            try:
                t = json.loads(line).get('request_time')
                if t is not None: times.append(t)
            except: pass
    times.sort()
    n = len(times)
    print(f'n={n}')
    print(f'median={statistics.median(times)*1000:.1f}ms')
    print(f'p95={times[int(0.95*n)]*1000:.1f}ms')
    print(f'max={max(times)*1000:.1f}ms')
    "

Error timeline (minute buckets):

    python3 -c "
    import json
    from collections import Counter
    b = Counter()
    with open('logs/access.log') as f:
        for line in f:
            try:
                d = json.loads(line)
                if d.get('status',0) >= 500:
                    b[d['timestamp'][:16]] += 1
            except: pass
    for k in sorted(b): print(f'{k}  {b[k]}')
    "

Error message types:

    grep -oE 'connect\(\) failed|upstream timed out|no live upstreams|recv\(\) failed' logs/error.log | sort | uniq -c

## Results

### Q1 — UTC interval, valid / malformed / duplicate lines

  File                Total    Malformed    Valid
  access.log          726      1            725
  error.log           68       n/a          68
  application.log     730      1            729

Time range (UTC): 2026-08-20 11:00:00Z to 11:29:57Z (about 30 minutes).
Duplicate request_ids in access.log: 5 (720 distinct vs 725 valid lines).

### Q2 — Distinct client requests

720 distinct request_id values in access.log.

Deduplication: built a set of request_ids. The 5 duplicates are retried
requests logged more than once. Counting raw lines would over-count by 5.

### Q3 — Status counts and error rate

  200  : 620
  404  : 10
  502  : 40
  503  : 47
  504  : 8
  Total: 725
  5xx  : 95

Error rate = 95 / 725 = 13.1%

Denominator = 725 (all valid access lines).

### Q4 — Failures by path and upstream

By path:

  /records : 26
  /counter : 26
  /ready   : 23
  /health  : 10
  /        : 10

By upstream:

  172.23.0.12:8080 : 68
  172.23.0.11:8080 : 27

Conclusion: one upstream (172.23.0.12) accounts for 68 of 95 failures.

### Q5 — Latency (request_time in seconds)

  n      : 725
  median : 54.0 ms
  p95    : 2001.0 ms
  max    : 2025.0 ms

Method: sorted request_time, index-based percentile times[int(0.95*n)].
Units: milliseconds (converted from seconds x 1000).

Interpretation: median is healthy; p95 of ~2s reflects timeouts.

### Q6 — Upstream retries

19 lines in access.log have a comma-separated upstream field: multiple
attempts for one client request. Some succeeded after retry; some
exhausted all upstreams.

### Q7 — Incident timeline (5xx per minute, UTC)

  11:05  8
  11:06  8
  11:07  8
  11:08  8
  11:09  8
  11:12  8
  11:13  7
  11:14  8
  11:15  8
  11:20  8
  11:21  8
  11:25  4
  11:26  4

Pattern: bursts of about 8 failures per minute, consistent with a periodic
probe against a failing upstream.

### Q8 — Correlated requests

Failed request lab-000122:

  access.log:
    {"timestamp":"2026-08-20T11:05:02.503Z","request_id":"lab-000122",
     "method":"GET","path":"/health","status":502,
     "upstream":"172.23.0.12:8080","upstream_status":"502",
     "request_time":0.003,"client":"192.0.2.24"}

  error.log:
    2026/08/20 11:05:02 [error] connect() failed (111: Connection refused)
    while connecting to upstream, request_id=lab-000122,
    request: "GET /health HTTP/1.1", upstream: "http://172.23.0.12:8080/health"

Successful request lab-000002:

  access.log:
    {"timestamp":"2026-08-20T11:00:02.532Z","request_id":"lab-000002",
     "method":"GET","path":"/health","status":200,
     "upstream":"172.23.0.12:8080","upstream_status":"200",
     "request_time":0.032,"client":"192.0.2.24"}

  application.log:
    {"timestamp": "2026-08-20T11:00:02.532Z", "level": "INFO",
     "event": "http_request", "request_id": "lab-000002",
     "instance_id": "app-02", "method": "GET", "path": "/health",
     "status": 200, "duration_ms": 32.0}

The same upstream 172.23.0.12 served a 200 early and a 502 later: it was
healthy at the start of the window and began failing.

### Q9 — Error classification

From error.log (68 lines):

  connect() failed      : 59
  upstream timed out    : 8

Classification:

  Proxy/connectivity: 59 connect() failed events -> 502s.
  Timeout:            8 upstream timed out events -> 504s.
  Application:        no direct app errors in error.log.

Proof: connect() failed (111: Connection refused) means the TCP handshake
was refused. This is a proxy/connectivity problem, not an application fault.

### Q10 — What the logs do NOT prove

The logs prove NGINX could not reach the upstream. They do NOT prove:

  - whether the app process crashed or restarted
  - whether the container was healthy from Docker's perspective
  - whether the network was at fault versus the app
  - root cause of the p95 latency spike (~2s)

What to check next in a running environment:

  1. docker compose ps -a
  2. docker logs <container>
  3. docker inspect <container> --format '{{.State.Health.Status}}'
  4. network-level checks between NGINX and the failing backend
  5. app metrics (GC, CPU, memory) around 11:05-11:26

Note: these logs describe a historical training incident, separate from
the current environment's pre-fix issues documented in troubleshooting.md.

## Timeline and correlated examples

See Q7 (timeline) and Q8 (correlated failed and successful requests).

## Conclusions and limits

  - 13.1% error rate driven primarily by one upstream (172.23.0.12).
  - Two failure modes: connect() failed (502s) and upstream timed out (504s).
  - Failures come in bursts of about 8 per minute.
  - Median latency is healthy (54 ms); p95 reflects the timeout window (~2 s).
  - Logs alone cannot determine root cause (app crash vs network vs config).