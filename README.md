# BARQ DevOps Assessment — Fixed Environment

A repaired Flask + PostgreSQL + Redis stack running behind NGINX, built
for the BARQ DevOps internship task. This README documents how to build,
start, test, back up, restore, and clean up the environment.

- Two Flask instances (app-01, app-02) behind NGINX
- Only NGINX publishes a host port (default 8080)
- PostgreSQL and Redis are on a private backend network
- NGINX is on the frontend network only
- Postgres and Redis persist via named Docker volumes
- CI runs on every push (see .github/workflows/ci.yml)

---

## Requirements

- Linux or WSL2 with Docker and Docker Compose
- Python 3.10+ (used by scripts and validator)
- Docker Desktop must be set to Linux containers
- Port 8080 free on the host

---

## Setup

Copy the example env files and fill in local values:

    cp .env.example .env

Edit .env and set POSTGRES_PASSWORD to a value of your choosing.
The compose file will refuse to start if POSTGRES_PASSWORD is missing.

The app's env file (config/app.env) is gitignored. It must exist
locally. If it is missing, create it:

    cat > config/app.env <<'EOF'
    DATABASE_URL=postgresql://barq_app:<your-password>@postgres:5432/barq_tasks
    REDIS_URL=redis://redis:6379/0
    EOF

Make sure the password here matches POSTGRES_PASSWORD in .env.

---

## Build

    docker compose -p barq-assessment build

---

## Start

    docker compose -p barq-assessment up -d

Wait for services to become healthy:

    sleep 20
    docker compose -p barq-assessment ps -a

Expected: app-01, app-02, nginx, postgres, redis all Up; app-01 and
app-02 show (healthy).

---

## Test the endpoints

    curl -i http://127.0.0.1:8080/
    curl -i http://127.0.0.1:8080/health
    curl -i http://127.0.0.1:8080/ready
    curl -i http://127.0.0.1:8080/instance
    curl    http://127.0.0.1:8080/counter
    curl -H 'Content-Type: application/json' \
         -d '{"title":"README proof"}' \
         http://127.0.0.1:8080/records
    curl    http://127.0.0.1:8080/records

Repeat /instance several times to see both backends respond:

    for i in $(seq 1 8); do curl -s http://127.0.0.1:8080/instance; echo; done

---

## Run the validator

    python3 validate.py

Runs 11 checks with PASS/FAIL output and exits non-zero on failure.
The validator waits up to 60 seconds for the stack to become ready
before checking anything.

---

## Failure test

Simulates a backend outage, verifies continued service, restores the
backend, and proves recovery.

    python3 failure_test.py

Expected: baseline shows both backends; during the outage the stopped
backend is absent from responses while the other backend serves traffic;
after restore, both backends respond again.

---

## Backup

Dumps the PostgreSQL database to ./backups/barq_<timestamp>.sql:

    ./backup.sh

The script uses pg_dump with --clean --if-exists so the dump can be
restored into a non-empty database. The backups/ directory is
gitignored.

---

## Restore

Restores a dump produced by backup.sh:

    ./restore.sh ./backups/barq_<timestamp>.sql

Prove restore works end to end:

    # 1. Note current records
    curl -s http://127.0.0.1:8080/records

    # 2. Create a fresh backup
    ./backup.sh

    # 3. Delete a record
    docker exec postgres psql -U barq_app -d barq_tasks \
      -c "DELETE FROM records WHERE id = (SELECT MAX(id) FROM records);"

    # 4. Confirm it is gone
    curl -s http://127.0.0.1:8080/records

    # 5. Restore
    ./restore.sh ./backups/barq_<timestamp>.sql

    # 6. Confirm it is back
    curl -s http://127.0.0.1:8080/records

---

## Persistence proof

Demonstrates that records and the Redis counter survive container
recreation:

    # Create a record and bump the counter
    curl -H 'Content-Type: application/json' \
         -d '{"title":"Persist me"}' \
         http://127.0.0.1:8080/records
    curl http://127.0.0.1:8080/counter
    curl http://127.0.0.1:8080/counter

    # Force-recreate the stateful containers (volumes are preserved)
    docker compose -p barq-assessment up -d --force-recreate postgres redis
    sleep 10

    # Confirm records and counter survived
    curl http://127.0.0.1:8080/records
    curl http://127.0.0.1:8080/counter

The record is still present and the counter has not reset.

---

## CI

The repository includes .github/workflows/ci.yml. On every push and pull
request to main, GitHub Actions:

  1. Checks out the repo
  2. Creates .env and config/app.env from the templates
  3. Validates the compose config
  4. Builds the images
  5. Starts the stack
  6. Waits (bounded) for readiness
  7. Runs validate.py
  8. Dumps logs on failure
  9. Tears down

CI fails when validate.py exits non-zero.

---

## Stop

Stop the stack but keep data:

    docker compose -p barq-assessment down

Stop and delete volumes (DESTROYS DATA — do not use during persistence
tests):

    docker compose -p barq-assessment down -v

---

## Cleanup

Remove stopped containers, unused images, and unused networks created by
this project:

    docker compose -p barq-assessment down --rmi local --remove-orphans

If you also want to remove the named volumes:

    docker volume rm barq-assessment_postgres-data barq-assessment_redis-data

---

## Architecture

Request flow:

  client
    |
    v
  nginx (frontend network, host port 8080 -> container port 80)
    |
    +--> app-01:8080
    +--> app-02:8080
             |
             v
        backend network
             |
             +--> postgres:5432  (named volume postgres-data)
             +--> redis:6379     (named volume redis-data, AOF enabled)

Networks:

  frontend: nginx, app-01, app-02
  backend : postgres, redis, app-01, app-02
  nginx is not on the backend network.

Ports:

  Host 8080 -> nginx:80   (only published host port)
  app-01, app-02, postgres, redis publish no host ports.

Storage:

  postgres-data -> /var/lib/postgresql/data
  redis-data    -> /data

See architecture.png for the diagram.

---

## Historical logs

The logs/ directory contains three historical logs from a training
incident on 2026-08-20 (access, error, application). They are analyzed
in log_analysis.md. They describe a past incident, not the current
environment's faults.

---

## Reports

  - troubleshooting.md — investigation journal (22 entries)
  - log_analysis.md    — historical log analysis (10 questions)
  - decisions.md       — 5 technical decisions with trade-offs
  - security_review.md — 10 risks and production follow-ups
  - AI_USAGE.md        — AI tool disclosure
  - docs/EVIDENCE_INDEX.md — requirement -> file -> commit -> timestamp

---

## Questions (from the task)

What failed first?
  The first thing I noticed was that the NGINX container mapped host
  port 8080 to container port 81, but NGINX listened on port 80. So
  every request to the public URL was refused. Full detail in
  troubleshooting.md Entry 6.

What proved the cause?
  The curl output changed from "connection reset by peer" (before the
  fix) to "502 Bad Gateway" (after the port was corrected). That error
  change proved the request reached NGINX and the next failure was
  NGINX-to-app reachability.

Which failed attempt taught something?
  The first restore attempt (Entry 22) failed with "relation already
  exists" because pg_dump was run without --clean. This taught me that
  dumps intended for non-empty targets need --clean --if-exists.

How did I avoid double-counting?
  In log_analysis.md I built a set of request_id values and counted
  each ID once. Raw lines over-count retried requests by 5.

How do requests flow?
  Client -> NGINX (frontend network) -> one of app-01/app-02 -> backend
  network -> Postgres and Redis. Only NGINX is reachable from the host.

Why these ports, networks, and readiness checks?
  Port 8080 is the only public entry point. Frontend/backend split gives
  isolation: compromising NGINX does not reach the data tier. /ready
  checks real dependencies so traffic only routes to instances that can
  serve it.

Why these timeouts, retries, restart settings, resource limits?
  Healthcheck intervals are 3-5s with 3-10 retries, matching the small
  lab size. Restart policy is unless-stopped so crashed services return
  automatically. Resource limits are documented as a production
  follow-up rather than enabled here.

When should validation fail?
  On any of the 11 checks: public access, all endpoints, both backends,
  Postgres+Redis readiness, network isolation, host-port closure, and
  non-root user. validate.py exits 1 on any failure.

What does green CI prove or not prove?
  It proves the stack builds and runs from a clean checkout with no
  hidden local state. It does not prove production performance, load
  behaviour, or security of external dependencies.

Which single points of failure remain?
  One NGINX instance, one Postgres instance, one Redis instance, one
  host. In production: multiple NGINX replicas, managed Postgres with
  replicas and PITR, Redis Sentinel or Cluster, multi-host scheduling.

What would I improve?
  Add monitoring and alerting, log rotation, resource limits, image
  scanning in CI, and secret management.

How did I verify AI-assisted work?
  Every AI-drafted file was read, edited for accuracy, and verified by
  running the commands against this live environment. Every commit
  reflects a change I can explain. See AI_USAGE.md.