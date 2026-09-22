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
  but the compose file sets the same value for both. /instance returned 
  {"instance_id":"app-01"} for both backends.
- Hypothesis: INSTANCE_ID is hardcoded to "app-01" in both app-01 and 
  app-02 service definitions, instead of being overridden per service.
- Command or test:
  1. `grep -n "INSTANCE_ID" docker-compose.yml`
  2. `docker exec app-01 python -c "... urlopen('http://127.0.0.1:8080/instance')"`
  3. `docker exec app-02 python -c "... urlopen('http://127.0.0.1:8080/instance')"`
- Actual output (before fix):
  - docker-compose.yml line 53: `INSTANCE_ID: "app-01"`
  - docker-compose.yml line 59: `INSTANCE_ID: "app-01"`
  - Both /instance calls returned `{"instance_id":"app-01"}` — identical.
- Failed attempt and what changed your thinking: none — the first 
  hypothesis was confirmed by grep and at runtime.
- Root cause: The app-02 service block in docker-compose.yml 
  hardcoded INSTANCE_ID to "app-01" instead of "app-02". The x-app 
  anchor does not set INSTANCE_ID, so app/server.py's default of 
  "local" is never used — both services explicitly override to the 
  same value.
- Fix: Changed docker-compose.yml line 59 (app-02 service) from 
  `INSTANCE_ID: "app-01"` to `INSTANCE_ID: "app-02"`. Recreated only 
  app-02 with `docker compose -p barq-assessment up -d app-02`.
- Retest evidence:
  - `for i in 1..10; curl -s http://127.0.0.1:8080/instance` alternates 
    cleanly between {"instance_id":"app-01"} and {"instance_id":"app-02"} 
    through NGINX.
  - X-Instance-ID header alternates correspondingly.
  - This also proves NGINX round-robin is working across both backends.
- Related commit: 79e32cc
- Remaining uncertainty: none.

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
- Root cause: The x-app anchor set restart: "no", so if an app process 
  crashed, Docker would not restart the container. This violates the 
  task requirement to set correct restart policies.
- Fix: Changed restart from "no" to unless-stopped in the x-app anchor. 
  Force-recreated all services with docker compose -p barq-assessment up -d --force-recreate.
- Retest evidence:
  - `docker inspect app-01 --format='{{.HostConfig.RestartPolicy.Name}}'` → unless-stopped
  - `docker exec app-01 python -c "import os, signal; os.kill(1, signal.SIGTERM)"` 
    (simulates an app crash) → 15s later `docker compose ps -a app-01` shows 
    `Up 14 seconds (healthy)`. The container restarted automatically.
- Related commit: 98bd203
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
  4. `docker compose -p barq-assessment logs app-01 | grep healthz`
- Actual output (runtime):
  - `docker compose ps -a` shows app-01 and app-02 as `Up ... (unhealthy)`.
  - App route is /health (grep line 96), healthcheck calls /healthz.
  - app-01 and app-02 logs show repeated `"GET /healthz HTTP/1.1" 404 -` 
    every few seconds, directly proving the healthcheck is hitting a 
    nonexistent endpoint.
- Failed attempt and what changed your thinking: none yet
- Root cause: docker-compose.yml's healthcheck called GET /healthz, 
  but the Flask app only exposes GET /health. Every healthcheck attempt 
  returned 404, so Docker permanently marked the app containers as unhealthy.
- Fix: Changed the healthcheck test URL from /healthz to /health in the 
  x-app anchor. Force-recreated the app containers.
- Retest evidence:
  - Before fix: `docker compose ps -a` showed app-01 and app-02 as `Up (unhealthy)`.
  - After fix: `docker compose ps -a` shows app-01 and app-02 as `Up (healthy)`.
  - App logs no longer show repeated `"GET /healthz HTTP/1.1" 404 -` entries.
- Related commit: 98bd203
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
- Root cause: nginx/nginx.conf listed app-01 in the upstream on port 8081, 
  but app-01 listens on APP_PORT 8080 (from the x-app anchor). Nothing 
  was listening on 8081, so every request routed to app-01 got 
  "connect() failed (111: Connection refused)" and returned 502.
- Fix: Changed nginx/nginx.conf upstream from `server app-01:8081` to 
  `server app-01:8080`. Recreated nginx with 
  `docker compose -p barq-assessment up -d --force-recreate nginx`.
- Retest evidence:
  - Before: `for i in 1..5; curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/`
    → 502 502 502 502 502
  - After: same loop → 200 200 200 200 200
  - nginx logs no longer show `connect() failed ... 8081`.
- Related commit: b0060d1
- Remaining uncertainty: none.

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
- Root cause: The nginx service in docker-compose.yml listed both frontend 
  and backend in its networks array. That gave nginx a route to Postgres 
  and Redis, violating the task's isolation requirement ("Block direct NGINX 
  access to PostgreSQL/Redis").
- Fix: Changed nginx's networks to [frontend] only. Force-recreated the 
  nginx container with `docker compose -p barq-assessment up -d --force-recreate nginx`.
- Retest evidence:
  - `docker network inspect barq-assessment_frontend --format='{{range .Containers}}{{.Name}} {{end}}'`
    → `app-01 app-02 nginx`
  - `docker network inspect barq-assessment_backend --format='{{range .Containers}}{{.Name}} {{end}}'`
    → `app-01 app-02 postgres redis` (no nginx)
  - End-to-end still works: `curl http://127.0.0.1:8080/` returns 200 through 
    nginx -> apps on the frontend network.
- Related commit: b264945
- Remaining uncertainty: none — network layout verified.

## Entry 8 — 2026-09-21 15:40 — Postgres and Redis publish ports to the host
- Symptom: Postgres and Redis are reachable from the host, which the task forbids ("Publish only NGINX on host port 8080").
- Hypothesis: The redis and postgres services define ports mappings.
- Command or test: Read redis and postgres service blocks in docker-compose.yml.
- Actual output:
    - redis: `["127.0.0.1:16379:6379"]`
    - postgres: `["127.0.0.1:15432:5432"]`
- Failed attempt and what changed your thinking: none yet
- Root cause: The postgres service published 127.0.0.1:15432:5432 and the 
  redis service published 127.0.0.1:16379:6379. The task requires only 
  NGINX to publish a host port, so both violated the rule.
- Fix: Removed the `ports:` mappings from the postgres and redis services 
  in docker-compose.yml. (This was applied alongside the persistence fix 
  in Entries 16, 17, 19 where the postgres/redis blocks were already 
  being edited.) Force-recreated both containers.
- Retest evidence:
  - `docker compose -p barq-assessment ps -a` shows `postgres 5432/tcp` 
    and `redis 6379/tcp` — container ports only, no host mapping.
  - `nc -zv 127.0.0.1 15432` → Connection refused
  - `nc -zv 127.0.0.1 16379` → Connection refused
  - `/ready` still reports both dependencies as "ready" (apps reach 
    Postgres/Redis internally via the backend network).
- Related commit: b264945
- Remaining uncertainty: none.

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
- Root cause: config/app.env's DATABASE_URL pointed at postgres:5433, but 
  the Postgres container listens on port 5432 (confirmed by the compose 
  port mapping `127.0.0.1:15432:5432` and by psycopg connect tests).
- Fix: Changed config/app.env DATABASE_URL from postgres:5433 to 
  postgres:5432. Recreated app-01 and app-02.
- Retest evidence:
  - `docker exec app-01 python -c "socket.create_connection(('postgres',5432))"` → OK (before fix; this was the runtime confirmation)
  - After fix + Entry 21: `curl /ready` reports `"postgres": "ready"`.
- Related commit: e5784d6
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
- Root cause: config/app.env's REDIS_URL pointed at redis:6380, but the 
  Redis container listens on port 6379 (confirmed by the compose port 
  mapping `127.0.0.1:16379:6379` and by socket connect tests).
- Fix: Changed config/app.env REDIS_URL from redis:6380 to redis:6379. 
  Recreated app-01 and app-02.
- Retest evidence:
  - `docker exec app-01 python -c "socket.create_connection(('redis',6379))"` → OK (before fix)
  - After fix: `curl /counter` returns `{"counter":1}`; `/ready` reports `"redis": "ready"`.
- Related commit: e5784d6
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
- Root cause: config/app.env was committed to the repository and contained 
  the Postgres password inside DATABASE_URL.
- Fix: Added .env and config/app.env to .gitignore. Ran 
  `git rm --cached config/app.env` to stop tracking while keeping the file 
  locally. Redacted the password from troubleshooting.md.
- Retest evidence:
  - `git check-ignore .env` → ignored
  - `git check-ignore config/app.env` → ignored
  - No tracked file contains the real password 
    (verified with `git ls-files | while read f; do grep -l ... "$f"; done`).
- Related commit: 094b9c4
- Remaining uncertainty: The password remains in earlier commits (starter 
  baseline). It is a synthetic lab value for a disposable environment; 
  documented in security_review.md.

## Entry 12 — 2026-09-21 16:18 — Dockerfile switches to USER root, defeating non-root setup
- Symptom: The image creates a non-root user `app` but then switches back to root before CMD, so the container runs as root.
- Hypothesis: The Dockerfile contains a `USER root` line after the useradd.
- Command or test: `Read Dockerfile`.
- Actual output (runtime): `docker exec app-01 whoami` → `root`
- Failed attempt and what changed your thinking: none yet
- Root cause: The Dockerfile created a non-root `app` user with useradd, 
  but then contained the line `USER root`, which overrode the non-root 
  setting. Containers therefore ran as root.
- Fix: Changed the line from `USER root` to `USER app` in the Dockerfile. 
  Rebuilt the app images with `docker compose -p barq-assessment up -d --build --force-recreate app-01 app-02`.
- Retest evidence:
  - `docker exec app-01 whoami` → `app` (no longer root).
  - `docker compose -p barq-assessment ps -a` still shows both apps healthy.
- Related commit: b264945
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
- Root cause: Dockerfile contained `COPY config/app.env /srv/app.env`, 
  baking the env file (with the password) into the image.
- Fix: Removed the COPY line. Rebuilt the app images.
- Retest evidence:
  - `docker run --rm barq-assessment-app-01 ls /srv` → only `app` and 
    `requirements.txt`, no `app.env`.
  - App still works: /ready reports both deps ready.
- Related commit: 094b9c4
- Remaining uncertainty: none.

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
- Root cause: .env.example contained only PUBLIC_PORT.
- Fix: Expanded with all keys (POSTGRES_*, APP_*, DATABASE_URL, REDIS_URL) 
  using placeholder values.
- Retest evidence: `cat .env.example` shows full key set with safe values.
- Related commit: 094b9c4
- Remaining uncertainty: none.

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
- Root cause: nginx depended on app-01 and app-02 using the short 
  depends_on: [app-01, app-02] syntax, which only waits for containers 
  to start, not for their healthcheck to pass. In the initial broken 
  state this led to transient 502s at startup.
- Fix: Changed nginx's depends_on to long form with condition: service_healthy 
  for both app-01 and app-02. Also added depends_on with condition: 
  service_healthy to app-01 and app-02 so they wait for postgres and redis 
  to be healthy before starting.
- Retest evidence:
  - After force-recreate of the whole stack, `docker compose ps -a` shows 
    all five containers healthy, with nginx starting only after apps 
    became healthy (no 502 startup window observed).
- Related commit: 98bd203
- Remaining uncertainty: none.

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
- Root cause: The named volume postgres-data was mounted to 
  /var/lib/postgresql/backup, a directory Postgres does not use for its 
  data. The real data directory (/var/lib/postgresql/data) was mounted as 
  tmpfs, so Postgres never wrote to the named volume.
- Fix: Changed the volume mount in docker-compose.yml from 
  /var/lib/postgresql/backup to /var/lib/postgresql/data.
- Retest evidence: After recreating postgres with the new mount and 
  creating a record via POST /records, force-recreating the postgres 
  container (docker compose up -d --force-recreate postgres) left the 
  record intact. GET /records after recreation still returned id 1, 2, 3 
  including the newly created "Persist me".
- Related commit: 98fee21
- Remaining uncertainty: none — persistence verified.


## Entry 17 — 2026-09-21 17:17 — Postgres data directory on tmpfs (no persistence)
- Symptom: Postgres stores its data in memory, so it is lost when the 
  container stops. The task's persistence test would fail.
- Hypothesis: The postgres service uses tmpfs on 
  /var/lib/postgresql/data.
- Command or test: Read postgres service block in docker-compose.yml.
- Actual output: `tmpfs: [/var/lib/postgresql/data]`
- Failed attempt and what changed your thinking: none yet
- Root cause: docker-compose.yml set tmpfs: [/var/lib/postgresql/data], 
  making Postgres's data directory memory-backed. Data was lost whenever 
  the container stopped or was removed.
- Fix: Removed the tmpfs line entirely. Postgres data now goes to disk 
  (via the named volume mounted at /var/lib/postgresql/data — see Entry 16).
- Retest evidence: Same test as Entry 16. Records and Redis counter both 
  survived a force-recreate of postgres and redis. If tmpfs were still in 
  place, the records would have been lost.
- Related commit: 98fee21
- Remaining uncertainty: none.


## Entry 18 — 2026-09-21 17:25 — Postgres password hardcoded in compose
- Symptom: POSTGRES_PASSWORD is a plain value in docker-compose.yml, 
  violating "Keep secrets out of images, code and Compose."
- Hypothesis: The postgres service sets POSTGRES_PASSWORD inline.
- Command or test: Read postgres service block in docker-compose.yml.
- Actual output: `POSTGRES_PASSWORD: BarqLabOnly_REDACTED`
- Failed attempt and what changed your thinking: none yet
- Root cause: POSTGRES_PASSWORD was hardcoded in docker-compose.yml.
- Fix: Changed to ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}, 
  with the actual value in .env (gitignored).
- Retest evidence:
  - docker compose config shows the value resolved from .env.
  - /ready reports postgres ready.
  - No tracked file contains the real password.
- Related commit: 094b9c4
- Remaining uncertainty: none.


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
- Root cause: The redis command disabled both RDB and AOF 
  ("--save", "", "--appendonly", "no"), and the service had no volume 
  mounted. Even if persistence had been enabled, /data was inside the 
  container and would be lost on container removal.
- Fix: Changed the command to ["redis-server", "--appendonly", "yes", 
  "--appendfsync", "everysec"] and added a redis-data:/data volume mount. 
  Declared redis-data: under the top-level volumes: block.
- Retest evidence: Bumped the counter three times (values 1, 2, 3, then 4 
  after the create-record call). Force-recreated the redis container 
  (docker compose up -d --force-recreate redis). Next counter call returned 
  5 (not reset to 1), proving the Redis counter survived container recreation.
- Related commit: 98fee21
- Remaining uncertainty: none — persistence verified.


## Entry 20 — 2026-09-21 17:40 — nginx, postgres, redis have no restart policies
- Symptom: Only the x-app anchor sets a restart policy (and it is "no"). 
  nginx, postgres and redis have no restart: line at all.
- Hypothesis: The services simply omit restart.
- Command or test: Read nginx, postgres and redis service blocks in 
  docker-compose.yml.
- Actual output: No restart: line in any of the three blocks.
- Failed attempt and what changed your thinking: none yet
- Root cause: nginx, postgres and redis services had no restart: line. 
  If any of them crashed, they would remain down until manually started.
- Fix: Added restart: unless-stopped to nginx, postgres and redis services.
- Retest evidence:
  - `docker inspect redis --format='{{.HostConfig.RestartPolicy.Name}}'` → unless-stopped
  - `docker exec redis kill 1` (simulates crash) → 15s later 
    `docker compose ps -a redis` shows `Up 14 seconds (healthy)`.
- Related commit: 98bd203
- Remaining uncertainty: none.

## Entry 21 — 2026-09-21 20:05 — Postgres password mismatch between config/app.env and docker-compose.yml
- Symptom: After fixing Entry 9 (port 5433 -> 5432), /ready still reported 
  `"postgres": "unavailable"` and /records returned `error: postgres_unavailable`. 
  Redis worked (Entry 10), so the issue was Postgres-specific.
- Hypothesis: The DATABASE_URL password in config/app.env did not match the 
  POSTGRES_PASSWORD that initializes the Postgres container in docker-compose.yml.
- Command or test:
  1. `grep -E "POSTGRES_PASSWORD" docker-compose.yml`
  2. `grep -E "DATABASE_URL" config/app.env`
  3. Compare the password substrings.
  4. Runtime test: `docker exec app-01 python -c "... psycopg.connect(DATABASE_URL) ..."` 
     (or simply call /ready and inspect the error)
- Actual output (before fix):
  - docker-compose.yml: POSTGRES_PASSWORD: BarqLabOnly_REDACTED
  - config/app.env: DATABASE_URL=postgresql://barq_app:BarqLabOnly_REDACTED@postgres:5432/barq_tasks
  - The passwords differ in their last character: c vs d.
  - /ready returned {"postgres": "unavailable", "redis": "ready"}.
- Failed attempt and what changed your thinking: Initially assumed the port 
  change (Entry 9) alone would fix /ready. After seeing redis: ready but 
  postgres: unavailable, compared the two passwords character by character 
  and found the mismatch.
- Root cause: The Postgres container was initialized with POSTGRES_PASSWORD 
  = BarqLabOnly_REDACTED, but the app authenticates using the value embedded 
  in config/app.env's DATABASE_URL, which ends in ...K8d. Password 
  authentication therefore failed with no schema-level error visible from 
  the app.
- Fix: Changed the password inside config/app.env's DATABASE_URL from 
  BarqLabOnly_REDACTED to BarqLabOnly_REDACTED so it matches compose. 
  Recreated app-01 and app-02 with `docker compose -p barq-assessment up -d app-01 app-02`.
  (Long-term fix belongs to Entries 11 and 18 — parameterize the password 
  from a single source; tracked separately.)
- Retest evidence:
  - `curl -s http://127.0.0.1:8080/ready` → {"status":"ready", "dependencies": {"postgres":"ready","redis":"ready"}, ...}
  - `curl -s http://127.0.0.1:8080/records` → returns the 2 seeded records
  - `curl -i -X POST -H 'Content-Type: application/json' -d '{"title":"Persistence test"}' http://127.0.0.1:8080/records` → 201 CREATED, record id 3
- Related commit: e5784d6
- Remaining uncertainty: none — Postgres now authenticates and serves reads/writes.

## Entry 22 — 2026-09-22 22:41 — Restore failed: "relation already exists"
- Symptom: Running ./restore.sh against a backup failed with 
  "relation 'records' already exists", "duplicate key value violates 
  unique constraint", and "multiple primary keys not allowed". The 
  deleted record did not come back.
- Hypothesis: pg_dump without --clean assumes the target database is 
  empty. Restoring into a populated database causes every CREATE / 
  ALTER / COPY statement to fail.
- Command or test:
  1. `./backup.sh` (initial version, plain pg_dump)
  2. Delete a record with psql
  3. `./restore.sh ./backups/barq_<timestamp>.sql`
- Actual output (failed restore):
    -ERROR: relation "records" already exists
    -ERROR: relation "records_id_seq" already exists
    -ERROR: duplicate key value violates unique constraint "records_pkey"
    -ERROR: multiple primary keys for table "records" are not allowed
    -[restore] OK — records table has 4 rows. ← but the deleted record was not back
- Failed attempt and what changed your thinking: The first restore 
silently failed — the script still reported "OK" because the count 
matched, but the deleted row was not actually restored. Realised the 
dump needs DROP statements to be restorable into a non-empty database.
- Root cause: pg_dump without --clean produces a dump designed for an 
empty target. It contains CREATE TABLE / ALTER TABLE / COPY but no 
DROP TABLE. When the target already has those objects, every 
statement fails and the data is not restored.
- Fix: Added `--clean --if-exists` to the pg_dump call in backup.sh. 
Regenerated the backup.
- Retest evidence:
- Backup: `./backup.sh` → 86-line dump file
- Delete: removed record id 4 → records = [1, 2, 3]
- Restore output now shows `DROP TABLE` → `CREATE TABLE` → `COPY 4`
  with no errors.
- After restore: records = [1, 2, 3, 4] — the deleted record returned.
- Related commit: (fill after commit)
- Remaining uncertainty: none — the pattern is standard for 
non-empty restores.