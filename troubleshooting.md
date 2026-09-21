# Troubleshooting journal

Keep chronological entries. Copy this block for each meaningful investigation.

## Entry / date / time
- Symptom:
- Hypothesis:
- Command or test:
- Actual output:
- Failed attempt and what changed your thinking:
- Root cause:
- Fix:
- Retest evidence:
- Related commit:
- Remaining uncertainty:

Do not fabricate a failed attempt just to fill the template. Record actual attempts.


## Entry 1 — 2026-09-21 14:50 — app-01 and app-02 share the same INSTANCE_ID
- Symptom: Both app services are expected to return distinct identities, 
  but the compose file sets the same value for both.
- Hypothesis: INSTANCE_ID is hardcoded to "app-01" in both app-01 and 
    app-02 service definitions, instead of being overridden per service.
- Command or test: `grep -n "INSTANCE_ID" docker-compose.yml`
- Actual output:    53:      INSTANCE_ID: "app-01"
                    59:      INSTANCE_ID: "app-01"
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none — /instance on both apps returned 
  {"instance_id":"app-01"} confirming the same value at runtime.

## Entry 2 — 2026-09-21 14:52 — APP_HOST set to 127.0.0.1 makes apps unreachable from NGINX
- Symptom: NGINX cannot reach the apps because the Flask app binds to 
  loopback (127.0.0.1) inside its container instead of all interfaces.
- Hypothesis: docker-compose.yml overrides the code's safe default 
  (0.0.0.0) with APP_HOST: "127.0.0.1".
- Command or test:
  1. `grep -n "APP_HOST" docker-compose.yml`
  2. `grep -n "APP_HOST" app/server.py`
- Actual output (runtime):
  - From inside app-01: `docker exec app-01 python -c "... urlopen('http://127.0.0.1:8080/health')"` → 200
  - From inside nginx: `docker exec nginx wget -q -O- http://app-01:8080/health` → "can't connect to remote host (172.18.0.2): Connection refused"
- Failed attempt and what changed your thinking: none yet
- Root cause: docker-compose.yml overrides the Flask app's safe default 
  (0.0.0.0 from app/server.py line 144) with APP_HOST: "127.0.0.1", 
  forcing the app to bind only to its container's loopback interface. 
  NGINX, running in a different container, cannot reach it.
- Fix: Changed APP_HOST in the x-app anchor from "127.0.0.1" to "0.0.0.0". 
  Recreated app-01 and app-02 with `docker compose -p barq-assessment up -d app-01 app-02`.
- Retest evidence:
  - `docker exec nginx wget -q -O- http://app-01:8080/health` → 
    returned the JSON health response ({"instance_id":"app-01","status":"alive",...}), 
    no longer "Connection refused".
  - After also fixing Entry 5, `curl http://127.0.0.1:8080/` returns 200 OK.
- Related commit: d62930b
- Remaining uncertainty: none.

## Entry 3 — 2026-09-21 14:55 — restart policy set to "no"
- Symptom: App containers will not restart if they crash, violating the task's requirement for correct restart policies.
- Hypothesis: The x-app anchor sets restart: "no".
- Command or test: `grep -n "restart" docker-compose.yml`
- Actual output: `restart: "no"` in the x-app anchor.
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none.

## Entry 4 — 2026-09-21 — healthcheck hits /healthz, but the app only exposes /health
- Symptom: App containers will always be marked unhealthy because the 
  compose healthcheck calls an endpoint that does not exist.
- Hypothesis: docker-compose.yml's healthcheck uses /healthz; the app 
  exposes /health only.
- Command or test:
  1. Read healthcheck block in docker-compose.yml (x-app anchor)
  2. `grep -n "health" app/server.py`
  3. `grep -n "app.get\|app.post\|app.route" app/server.py`
- Actual output (runtime):
  - `docker compose ps -a` shows app-01 and app-02 as `Up ... (unhealthy)`.
  - App route is /health (grep line 96), healthcheck calls /healthz.
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none.

## Entry 5 — 2026-09-21 15:04 — NGINX upstream points app-01 to port 8081
- Symptom: NGINX will return 502 for requests routed to app-01 because nothing is listening on port 8081.
- Hypothesis: The upstream block references app-01:8081, but both apps run on APP_PORT 8080.
- Command or test:
  1. Read nginx/nginx.conf upstream block
  2. `grep -n "APP_PORT" docker-compose.yml`
- Actual output:
  - nginx/nginx.conf: upstream application_pool {
        server app-01:8081 max_fails=0;
        server app-02:8080 max_fails=0;
        }
- docker-compose.yml x-app anchor: `APP_PORT: "8080"` (inherited by both apps)
- Conclusion: app-01 does not listen on 8081; NGINX will fail to reach it.
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: Not yet verified at runtime because the request 
  path fails earlier (Entry 6 blocks reaching nginx; Entry 2 blocks nginx 
  reaching apps). Will be verified after Entries 2 and 6 are fixed.

## Entry 6 — 2026-09-21 15:18 — NGINX container port mismatch (host:8080 -> container:81 vs listen 80)
- Symptom: Requests to `http://127.0.0.1:8080` never reach NGINX because 
  the container is not listening on the mapped container port. curl 
  returns "Connection reset by peer".
- Hypothesis: docker-compose publishes NGINX's port 81, but 
  nginx/nginx.conf listens on 80.
- Command or test:
  1. Read nginx ports mapping in docker-compose.yml
  2. Read listen directive in nginx/nginx.conf
  3. `curl -i http://127.0.0.1:8080/`
  4. `docker compose -p barq-assessment ps -a nginx`
- Actual output (before fix):
  - docker-compose.yml line 63: `"127.0.0.1:${PUBLIC_PORT:-8080}:81"`
  - nginx/nginx.conf: `listen 80;`
  - `curl -i http://127.0.0.1:8080/` → `curl: (56) Recv failure: Connection reset by peer`
  - `docker compose ps -a nginx` → `127.0.0.1:8080->81/tcp`
- Failed attempt and what changed your thinking: none — the first 
  hypothesis was correct on inspection.
- Root cause: The compose port mapping forwarded host port 8080 to the 
  nginx container's port 81, but nginx listens on container port 80. 
  Nothing was listening on 81, so the TCP connection was accepted and 
  immediately reset by the kernel.
- Fix: Changed docker-compose.yml line 63 from `:81` to `:80`. Recreated 
  only the nginx container with `docker compose -p barq-assessment up -d nginx`.
- Retest evidence:
  - `docker compose -p barq-assessment ps -a nginx` → `127.0.0.1:8080->80/tcp`
  - `curl -i http://127.0.0.1:8080/` → `HTTP/1.1 502 Bad Gateway` 
    (nginx/1.28.3). The error changed from connection reset (couldn't 
    reach nginx) to 502 (nginx reachable but cannot reach apps), 
    confirming Entry 6 is fixed and the next layer is Entries 2 and 5.
- Related commit: cd2fc8f
- Remaining uncertainty: none — fix verified. The 502 is expected and 
  is addressed by Entries 2 and 5.

## Entry 7 — 2026-09-21 15:25 — NGINX attached to backend network, violating isolation
- Symptom: NGINX can reach Postgres and Redis directly, which the task forbids ("Block direct NGINX access to PostgreSQL/Redis").
- Hypothesis: The nginx service declares both frontend and backend in its networks list.
- Command or test: Read nginx service block in docker-compose.yml.
- Actual output: nginx service lists `networks: [frontend, backend]`.
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: Need to confirm at runtime that removing 
    backend does not break NGINX's ability to route to apps (apps are on frontend too, so it should be fine).

## Entry 8 — 2026-09-21 15:40 — Postgres and Redis publish ports to the host
- Symptom: Postgres and Redis are reachable from the host, which the task forbids ("Publish only NGINX on host port 8080").
- Hypothesis: The redis and postgres services define ports mappings.
- Command or test: Read redis and postgres service blocks in docker-compose.yml.
- Actual output:
    - redis: `["127.0.0.1:16379:6379"]`
    - postgres: `["127.0.0.1:15432:5432"]`
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none — the ports mappings are present and violate the stated rule.

## Entry 9 — 2026-09-21 15:50— DATABASE_URL uses port 5433, Postgres listens on 5432
- Symptom: /ready and /records will fail because the app cannot connect to Postgres.
- Hypothesis: config/app.env sets DATABASE_URL to postgres:5433, but the Postgres container listens on its default port 5432.
- Command or test:
1. `cat config/app.env`
2. `grep -n -A10 "postgres:" docker-compose.yml`
- Actual output (runtime):
  - `docker exec app-01 python -c "socket.create_connection(('postgres',5432))"` → OK
  - Same on port 5433 → ConnectionRefusedError
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none.

## Entry 10 — 2026-09-21 16:00 — REDIS_URL uses port 6380, Redis listens on 6379
- Symptom: /counter and /ready will fail because the app cannot connect to Redis.
- Hypothesis: config/app.env sets REDIS_URL to redis:6380, but the Redis container listens on its default port 6379.
- Command or test:
1. `cat config/app.env`
2. `grep -n -A10 "redis:" docker-compose.yml`
- Actual output (runtime):
  - `docker exec app-01 python -c "socket.create_connection(('redis',6379))"` → OK
  - Same on port 6380 → ConnectionRefusedError
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none.

## Entry 11 — 2026-09-21 16:10 — config/app.env tracked in git, contains credential-like value
- Symptom: The task says "Keep secrets out of images, code and Compose. 
    Ignore secret files; provide a safe .env.example." config/app.env is 
    tracked and contains a password-like value.
- Hypothesis: The starter intentionally ships this file so students can 
    run the app, but best practice is to gitignore it and ship a safe 
    .env.example instead.
- Command or test: `git ls-files config/app.env`
- Actual output: `config/app.env`
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: Removing this file may break the starter; may 
    need to keep it while adding it to .gitignore for future commits and 
    documenting the trade-off in security_review.md. Also need to check 
    whether the value is truly sensitive or a lab placeholder.

## Entry 12 — 2026-09-21 16:18 — Dockerfile switches to USER root, defeating non-root setup
- Symptom: The image creates a non-root user `app` but then switches back to root before CMD, so the container runs as root.
- Hypothesis: The Dockerfile contains a `USER root` line after the useradd.
- Command or test: `Read Dockerfile`.
- Actual output (runtime): `docker exec app-01 whoami` → `root`
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none.

## Entry 13 — 2026-09-21 16:30 — Dockerfile copies config/app.env into the image
- Symptom: Secrets are baked into the image layer, violating "Keep secrets out of images."
- Hypothesis: The Dockerfile has `COPY config/app.env /srv/app.env`.
- Command or test:
  1. Read Dockerfile (found COPY config/app.env /srv/app.env)
  2. `grep -n -i "dotenv\|app.env\|load_dotenv\|environ\|getenv" app/server.py`
- Actual output:
  - Dockerfile: `COPY config/app.env /srv/app.env`
  - app/server.py: only `os.getenv(...)` calls at lines 51, 52, 59, 60, 
    142, 143, 144, 145. No file reads, no dotenv.
  - Conclusion: the app never opens /srv/app.env. The COPY line is 
    unnecessary and bakes an env file into the image layer.
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none — grep of app/server.py shows the app 
  reads env vars only via os.getenv(); it does not open /srv/app.env. 
  The COPY line is unused and can be safely removed.

## Entry 14 — 2026-09-21 16:50 — .env.example is incomplete
- Symptom: .env.example only documents PUBLIC_PORT; the app also needs 
  DATABASE_URL, REDIS_URL, INSTANCE_ID, APP_MESSAGE, APP_HOST and APP_PORT 
  (per app/server.py and assessment/APPLICATION.md).
- Hypothesis: The starter ships a minimal .env.example.
- Command or test:
  1. `cat .env.example`
  2. `grep -n "getenv" app/server.py`
  3. Compare against env vars used in docker-compose.yml and 
     assessment/APPLICATION.md.
- Actual output:
  - .env.example contains only `PUBLIC_PORT=8080`.
  - app/server.py reads: INSTANCE_ID, APP_MESSAGE, DATABASE_URL, 
    REDIS_URL, APP_HOST, APP_PORT.
  - docker-compose.yml x-app anchor sets APP_HOST, APP_PORT, APP_MESSAGE.
  - Conclusion: .env.example should document all app-required vars 
    (with safe placeholder values), not only PUBLIC_PORT.
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none — the missing variables are all enumerated by grepping app/server.py.

## Entry 15 — 2026-09-21 17:00 — depends_on uses short syntax, no service_healthy gating
- Symptom: nginx starts as soon as the app containers exist, not when 
  they are ready to serve requests. This can cause startup races and 
  transient 502s on first requests.
- Hypothesis: nginx's depends_on uses the short list syntax 
  (depends_on: [app-01, app-02]), which only waits for container 
  start, not for health.
- Command or test:
  1. `grep -n -A15 "^  nginx:" docker-compose.yml`
  2. Check whether app-01 / app-02 have a healthcheck that could be 
     used for service_healthy gating.
- Actual output:
  - nginx depends_on: [app-01, app-02] — short syntax only.
  - x-app anchor has a healthcheck, but it calls /healthz (which does 
    not exist — see Entry 4). So even the long-form condition would 
    fail until Entry 4 is fixed.
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: Need to confirm at runtime whether nginx actually returns 502s before apps are ready (short-lived race).

## Entry 16 — 2026-09-21 17:08 — Postgres named volume mounts wrong path
- Symptom: The named volume postgres-data is attached, but Postgres 
  writes its database files elsewhere, so data is not persisted in it.
- Hypothesis: The volume is mounted to /var/lib/postgresql/backup 
  instead of /var/lib/postgresql/data.
- Command or test: Read postgres service block in docker-compose.yml.
- Actual output:
  - volumes:
      - postgres-data:/var/lib/postgresql/backup
  - tmpfs: [/var/lib/postgresql/data]
  - Conclusion: the named volume points at a directory Postgres does 
    not use for data. The real data directory is on tmpfs (ephemeral).
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none — the mount path is visibly wrong.


## Entry 17 — 2026-09-21 17:17 — Postgres data directory on tmpfs (no persistence)
- Symptom: Postgres stores its data in memory, so it is lost when the 
  container stops. The task's persistence test would fail.
- Hypothesis: The postgres service uses tmpfs on 
  /var/lib/postgresql/data.
- Command or test: Read postgres service block in docker-compose.yml.
- Actual output: `tmpfs: [/var/lib/postgresql/data]`
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none.


## Entry 18 — 2026-09-21 17:25 — Postgres password hardcoded in compose
- Symptom: POSTGRES_PASSWORD is a plain value in docker-compose.yml, 
  violating "Keep secrets out of images, code and Compose."
- Hypothesis: The postgres service sets POSTGRES_PASSWORD inline.
- Command or test: Read postgres service block in docker-compose.yml.
- Actual output: `POSTGRES_PASSWORD: BarqLabOnly_7qN2vK8c`
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: Need to confirm whether the same password also 
  appears in config/app.env (it does, inside DATABASE_URL). Both must 
  come from an environment variable instead.


## Entry 19 — 2026-09-21 17:30 — Redis persistence disabled and no volume
- Symptom: Redis is configured not to persist, and has no volume, so 
  /counter resets after a restart.
- Hypothesis: The redis command disables RDB and AOF, and the service 
  has no volume mounted.
- Command or test: Read redis service block in docker-compose.yml.
- Actual output:
  - command: ["redis-server", "--save", "", "--appendonly", "no"]
  - no volumes: section
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: Need to confirm the task requires Redis 
  persistence to survive container recreation. Task says "Configure 
  Redis persistence where appropriate" — likely yes.


## Entry 20 — 2026-09-21 17:40 — nginx, postgres, redis have no restart policies
- Symptom: Only the x-app anchor sets a restart policy (and it is "no"). 
  nginx, postgres and redis have no restart: line at all.
- Hypothesis: The services simply omit restart.
- Command or test: Read nginx, postgres and redis service blocks in 
  docker-compose.yml.
- Actual output: No restart: line in any of the three blocks.
- Failed attempt and what changed your thinking: none yet
- Root cause: (pending)
- Fix: (pending)
- Retest evidence: (pending)
- Related commit: (pending)
- Remaining uncertainty: none.