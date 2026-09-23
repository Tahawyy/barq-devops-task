# Technical decisions

Recorded decisions with alternatives, trade-offs, and limitations. Each
decision points to the commit that introduced it and to the production
improvement if we were to ship this beyond a lab exercise.

---

## Decision 1 — Base image choice: python:3.12-slim-bookworm

Choice:
  Use python:3.12-slim-bookworm (pinned by digest) as the app base image.

Why:
  - Matches the task's stated Python 3.12 requirement.
  - Slim variant drops build toolchains and docs, giving a smaller image
    and a smaller attack surface.
  - Pinning by sha256 digest makes builds reproducible and prevents
    tag-hijack drift.
  - Debian bookworm is a stable, well-supported LTS base.

Alternative:
  - python:3.12-alpine: smaller still, but musl libc can break some
    Python wheels (psycopg, cryptography) at build time.
  - python:3.12 (full): larger and ships unneeded build tools.

Trade-off:
  - slim lacks curl, wget, kill. Health checks and diagnostics must use
    Python instead of shell tools. This shaped the health check design
    (see Decision 2).

Evidence / commit:
  - Dockerfile: FROM python:3.12-slim-bookworm@sha256:782412e8...
  - Fix commit: b264945 ("run apps as non-root")

Production improvement:
  - Multi-stage build to compile wheels in a builder stage and copy only
    runtime artifacts.
  - Image scanning in CI (trivy/grype) to catch CVEs automatically.

---

## Decision 2 — Health checks: python -c urllib instead of curl

Choice:
  The healthcheck runs python -c "import urllib.request; ..." against
  http://127.0.0.1:8080/health.

Why:
  - The slim base image has no curl/wget/kill. Only Python is guaranteed.
  - Using tools present in the image avoids an extra apt-get layer just
    for a health probe.
  - The endpoint is HTTP, so urllib is enough.

Alternative:
  - Install curl via apt (adds image layers, packages, and CVE surface).
  - Use wget (also not in slim).

Trade-off:
  - Longer healthcheck command, harder to read at a glance.
  - Cannot use the same healthcheck line for non-Python services.

Evidence / commit:
  - docker-compose.yml, x-app anchor: healthcheck test uses python -c.
  - Fix commit: 98bd203 ("healthcheck endpoint, depends_on, restart")

Production improvement:
  - Use a dedicated tiny probe binary (grpc_health_probe style) or move
    readiness out of the container into orchestrator-level checks.

---

## Decision 3 — Two-network layout: frontend + backend

Choice:
  - frontend network: nginx + app-01 + app-02
  - backend network:  postgres + redis + app-01 + app-02
  - nginx is NOT on backend.

Why:
  - Matches the task's required topology.
  - Defense in depth: compromising nginx does not give reachability to
    Postgres or Redis.
  - Apps are the only components that touch both sides, so they act as
    the bridge.

Alternative:
  - Single flat network for everything (simpler, but no isolation).
  - Three networks with a proxy tier between apps and DB (more complex).

Trade-off:
  - Slightly more YAML and stricter service placement.
  - Debugging requires remembering which container can reach what.

Evidence / commit:
  - docker-compose.yml: networks: frontend, backend at the top level and
    per service.
  - Fix commit: b264945 ("network isolation")

Production improvement:
  - Network policies / segmentation in Kubernetes (NetworkPolicy).
  - Zero-trust service mesh (mTLS between apps and DB).

---

## Decision 4 — Persistence: named volumes + Postgres data dir + Redis AOF

Choice:
  - Named volume postgres-data mounted at /var/lib/postgresql/data.
  - Named volume redis-data mounted at /data.
  - Redis runs with --appendonly yes --appendfsync everysec.
  - No tmpfs for Postgres.

Why:
  - Task requires the record to survive container recreation.
  - The starter mounted the Postgres volume at /backup and put the real
    data dir on tmpfs; data was lost on container stop.
  - Redis with AOF survives restarts; RDB-only or appendonly no would
    lose the counter.

Alternative:
  - Bind mounts (./data:/var/lib/postgresql/data): simpler to inspect,
    but couples the container to a host path and often breaks on
    Windows/WSL file permissions.
  - Redis with RDB only: simpler, but can lose the last few seconds.

Trade-off:
  - Volumes are opaque: harder to inspect directly, need docker volume
    commands to look inside.
  - Named volumes survive docker compose down but not down -v; that
    safety trade-off is intentional (documented in README).

Evidence / commit:
  - docker-compose.yml: volumes: postgres-data, redis-data.
  - Fix commit: 98fee21 ("persistence via named volumes and AOF")
  - Proof: created a record, force-recreated postgres and redis, record
    still present; counter went 4 -> 5 after recreation.

Production improvement:
  - Managed database service (RDS, Cloud SQL) with PITR.
  - Automated nightly backup to object storage.

---

## Decision 5 — Restart policies: unless-stopped

Choice:
  All long-running services use restart: unless-stopped.

Why:
  - A crashed process should come back automatically.
  - "unless-stopped" respects an explicit docker stop: if an operator
    stops a container on purpose, it stays stopped.

Alternative:
  - restart: always: also restarts after docker stop, which is usually
    not what an operator wants.
  - restart: on-failure: does not restart after a clean exit; useful for
    jobs, not for long-running services.

Trade-off:
  - Crash loops are possible if the process cannot start at all; Docker
    backs off exponentially but does not give up.
  - Not a substitute for orchestrator-level self-healing.

Evidence / commit:
  - docker-compose.yml: restart: unless-stopped on nginx, postgres,
    redis, and the x-app anchor.
  - Fix commit: 98bd203 ("healthcheck endpoint, depends_on, restart")

Production improvement:
  - Kubernetes: liveness and readiness probes with pod restart policies.
  - Alerting on restart count / crashloop backoff.