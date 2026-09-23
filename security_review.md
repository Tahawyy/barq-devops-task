# Security and production-readiness review

Concrete risks and improvements relevant to the final solution. Separate
"implemented" from "production follow-up". Every risk has evidence in the
repository, a fix or plan, and a verification method.

---

## Risk 1 — Secret committed to docker-compose.yml (Postgres password)

Risk and evidence:
  docker-compose.yml set POSTGRES_PASSWORD to a literal string, and
  config/app.env was tracked by git with the same password inside
  DATABASE_URL.

Impact:
  Anyone with repo access (or a leaked image) obtains the database
  password. High for production, moderate for a lab.

Implemented fix / commit:
  POSTGRES_PASSWORD is now ${POSTGRES_PASSWORD:?...} sourced from .env
  (gitignored). config/app.env is untracked (git rm --cached) and
  gitignored. troubleshooting.md was redacted.

Production follow-up:
  Use a secret manager (Vault, AWS Secrets Manager) and inject secrets
  at deploy time. Never store secrets in the repo, even in a lab.

How to verify:
  git ls-files | while read f; do grep -l "BarqLabOnly_7qN2vK8" "$f"; done
  (should output nothing)

Commit:
  094b9c4

---

## Risk 2 — config/app.env baked into the image

Risk and evidence:
  Dockerfile contained COPY config/app.env /srv/app.env, baking the
  env file into every image layer.

Impact:
  Anyone with the image can extract the file with docker save. The
  secret travels with the image to any registry.

Implemented fix / commit:
  Removed the COPY line. App reads env vars from the process environment
  only, verified via grep on app/server.py.

Production follow-up:
  Multi-stage build; secret injection at runtime; image scan (trivy)
  in CI to detect filesystem secrets.

How to verify:
  docker run --rm barq-assessment-app-01 ls /srv
  (should list only app/ and requirements.txt)

Commit:
  094b9c4

---

## Risk 3 — Containers running as root

Risk and evidence:
  Dockerfile created a non-root "app" user, then overrode it with
  USER root. Every container ran as root.

Impact:
  A container compromise becomes a host compromise via container
  escape techniques. Standard defense-in-depth violation.

Implemented fix / commit:
  Changed USER root to USER app. Rebuilt images.

Production follow-up:
  Add user namespace remapping, read-only root filesystem, and
  drop all Linux capabilities except those required.

How to verify:
  docker exec app-01 whoami
  (should print "app")

Commit:
  b264945

---

## Risk 4 — Databases published on the host

Risk and evidence:
  Postgres and Redis published host ports 15432 and 16379 respectively.

Impact:
  Any local process (or remote attacker if the host were exposed) can
  reach the databases directly, bypassing the app's authentication and
  logic.

Implemented fix / commit:
  Removed the ports mappings for postgres and redis. Only nginx
  publishes a host port.

Production follow-up:
  Network policies in Kubernetes; databases in a private subnet with no
  public route; VPC peering for access.

How to verify:
  nc -zv 127.0.0.1 15432
  nc -zv 127.0.0.1 16379
  (both should be refused)

Commit:
  b264945

---

## Risk 5 — NGINX could reach Postgres and Redis

Risk and evidence:
  nginx was attached to both frontend and backend networks. If nginx
  were compromised, the attacker could reach the data layer.

Impact:
  Lateral movement from the public edge to the data tier.
  Violates the task's explicit isolation requirement.

Implemented fix / commit:
  Removed backend from nginx's networks array. Verified via
  docker network inspect.

Production follow-up:
  Zero-trust network policies; mTLS between services.

How to verify:
  docker network inspect barq-assessment_backend --format '{{range .Containers}}{{.Name}} {{end}}'
  (should not include nginx)

Commit:
  b264945

---

## Risk 6 — Persistence: no backups and ephemeral data risk

Risk and evidence:
  Starter used tmpfs for Postgres and disabled Redis persistence.
  Records would vanish on container stop.

Impact:
  Data loss on any restart. Guaranteed failure of the persistence
  requirement.

Implemented fix / commit:
  Named volumes for Postgres and Redis; Postgres data dir correct;
  Redis AOF enabled. backup.sh and restore.sh provide round-trip
  proof.

Production follow-up:
  Automated daily backups to object storage; PITR via WAL archiving;
  restore drills on a schedule.

How to verify:
  ./backup.sh
  docker exec postgres psql ... -c "DELETE FROM records WHERE id=...;"
  ./restore.sh ./backups/barq_*.sql
  (deleted row returns)

Commit:
  98fee21 and a35e6a0

---

## Risk 7 — No monitoring or alerting

Risk and evidence:
  No metrics, no log aggregation, no alerts. A failure would be
  invisible until a user complains.

Impact:
  Slow detection and response. The 2026-08-20 historical incident
  shows a 13.1% error rate sustained for ~30 minutes before any
  human would have noticed.

Implemented fix / commit:
  None — documented as production follow-up. This is a review
  requirement, not a defect in the current solution.

Production follow-up:
  Prometheus for metrics; Loki/ELK for logs; Grafana dashboards;
  alerts on 5xx rate, p95 latency, and container restarts.

How to verify:
  n/a — planned work.

---

## Risk 8 — Default resource limits and no per-service quotas

Risk and evidence:
  No cpu/memory limits in docker-compose.yml. A runaway container
  could starve the host.

Impact:
  Noisy-neighbor effects; OOM kills without a limit; unpredictable
  performance under load.

Implemented fix / commit:
  Not applied yet — documented as production follow-up. In a
  single-developer lab the risk is low.

Production follow-up:
  Set per-service deploy.resources.limits (cpu, memory) and requests.
  Use cgroup v2 enforcement; alert on limit hits.

How to verify:
  docker inspect app-01 --format '{{.HostConfig.Memory}}'
  docker inspect app-01 --format '{{.HostConfig.NanoCpus}}'
  (currently 0 — unlimited)

---

## Risk 9 — Restart policies do not cover crash loops

Risk and evidence:
  restart: unless-stopped covers ordinary crashes but a persistently
  failing container will crash-loop silently.

Impact:
  Service appears "up" from docker ps but delivers no traffic.

Implemented fix / commit:
  Not applied yet — documented as production follow-up.

Production follow-up:
  Alert on container restart count; use orchestrator backoff caps;
  readiness probes to remove crash-looping instances from rotation.

How to verify:
  docker inspect app-01 --format '{{.RestartCount}}'
  (grows on repeated crashes; no alert currently)

---

## Risk 10 — Logging: logs are local, unstructured, and unrotated

Risk and evidence:
  Docker json-file logging grows unbounded; no log rotation configured.
  Logs live only on the host.

Impact:
  Disk fills; logs lost on container removal; no central correlation.

Implemented fix / commit:
  Not applied yet — documented as production follow-up.

Production follow-up:
  Configure logging driver with max-size / max-file; ship logs to a
  central store (Loki, ELK); structured JSON logs already used by the
  app.

How to verify:
  docker inspect app-01 --format '{{.HostConfig.LogConfig}}'
  (currently json-file with no rotation options)

---

## Summary

Implemented fixes (commits 094b9c4, b264945, 98fee21, 98bd203, a35e6a0):
  - secrets out of git and images
  - no root user
  - database ports closed
  - network isolation enforced
  - persistence and backup/restore proven

Production follow-ups (not implemented — planned):
  - secret manager
  - image scanning in CI
  - resource limits
  - monitoring and alerting
  - log rotation and centralization
  - crash-loop alerting