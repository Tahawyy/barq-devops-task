# Evidence and submission index

- Repository URL: https://github.com/Tahawyy/barq-devops-task
- Final commit: (fill after final push — leave blank for now)
- Matching CI run: https://github.com/Tahawyy/barq-devops-task/actions/runs/35780594956
- Continuous 12-18 minute video URL: (fill after recording)
- Challenge receipt ID: (fill after video — from .assessment/challenge.json)
- Starting video commit: (fill before recording — the commit HEAD is at when recording starts)
- Later documentation-only commits, if any: (fill after submission if any)

This index maps each task requirement to the file that implements it, the
commit that produced it, and (where applicable) the timestamp in the
recorded video. Video timestamps are filled after recording.

Note: the final system state shown in the video and the final README will
be three app instances on public port 8090. The commits below reflect the
work as performed; the final video demonstrates the live change from two
instances on 8080 to three instances on 8090.

---

## Repository and baseline

| Requirement | File / output | Commit | Video timestamp |
|---|---|---|---|
| GitHub repository with baseline preserved | repo | 8442da3 | opening |
| Baseline committed before technical changes | git log | 8442da3 | opening |
| Progressive commits with meaningful messages | git log | (all commits) | throughout |

---

## Investigation and troubleshooting

| Requirement | File / output | Commit | Video timestamp |
|---|---|---|---|
| Investigation journal (symptoms, hypotheses, commands, results, failed attempts) | troubleshooting.md | 7c422dc, 57de30c, later fix commits | throughout |
| Root cause, fix, retest, commit per issue | troubleshooting.md | all fix commits | per fix |
| Historical log analysis (10 questions, commands, counts, timeline) | log_analysis.md | ece5d48 | video: historical-log finding |

---

## Docker, networking, NGINX

| Requirement | File / output | Commit | Video timestamp |
|---|---|---|---|
| Two Flask instances behind NGINX (final: three) | docker-compose.yml, nginx/nginx.conf | 98bd203, b0060d1, b264945 | live demo |
| Only NGINX published on host port 8080 (final: 8090) | docker-compose.yml | b264945 | port change |
| NGINX + apps on frontend; apps + DB + cache on backend | docker-compose.yml | b264945 | network demo |
| NGINX cannot reach Postgres or Redis | docker-compose.yml | b264945 | isolation check |
| Service names used (no container IPs) | docker-compose.yml | 98bd203 | — |
| Container names app-01, app-02, nginx, postgres, redis | docker-compose.yml | as cloned | ps output |
| Named PostgreSQL volume | docker-compose.yml | 98fee21 | persistence demo |
| Redis persistence (AOF) | docker-compose.yml | 98fee21 | counter demo |
| Correct env vars, healthchecks, restart, depends_on | docker-compose.yml | 98bd203 | health demo |
| Non-root user | Dockerfile | 094b9c4 | whoami check |
| Secrets out of image | Dockerfile | 094b9c4 | docker run ls /srv |
| .env.example safe template | .env.example | 094b9c4 | — |

---

## Required endpoints

| Requirement | File / output | Commit | Video timestamp |
|---|---|---|---|
| GET / returns 200 with instance_id | validate.py | e166ddc | endpoint test |
| GET /health returns 200 (process liveness) | validate.py | e166ddc | endpoint test |
| GET /ready checks Postgres + Redis | validate.py | e166ddc | endpoint test |
| GET /instance returns distinct identity | validate.py | e166ddc | /instance demo |
| POST /records stores and returns 201 | validate.py, failure_test.py | e166ddc | records demo |
| GET /records lists records | validate.py | e166ddc | records demo |
| GET /counter increments shared Redis counter | validate.py | e166ddc | counter demo |

---

## Validation, persistence, CI

| Requirement | File / output | Commit | Video timestamp |
|---|---|---|---|
| validate.py with bounded waits and PASS/FAIL | validate.py | e166ddc | validation demo |
| failure_test.py stops backend, measures, restores | failure_test.py | 9e83ca7 | failure demo |
| backup.sh PostgreSQL backup | backup.sh | a35e6a0 | — |
| restore.sh proves restore works | restore.sh | a35e6a0 | — |
| Record survives container recreation | docker-compose.yml, troubleshooting.md Entry 16/17/19 | 98fee21 | persistence demo |
| CI workflow on push and PR | .github/workflows/ci.yml | aaf9e9a, earlier ci commit | — |
| CI green | Actions run | https://github.com/Tahawyy/barq-devops-task/actions/runs/35780594956 | — |

---

## Documentation

| Requirement | File / output | Commit | Video timestamp |
|---|---|---|---|
| README with copyable commands | README.md | 814456b | opening |
| troubleshooting.md journal | troubleshooting.md | all fix commits | throughout |
| log_analysis.md | log_analysis.md | ece5d48 | log demo |
| decisions.md (>=5 decisions) | decisions.md | 71ae139 | — |
| security_review.md (>=8 risks) | security_review.md | 71ae139 | — |
| AI_USAGE.md disclosure | AI_USAGE.md | 71ae139 | — |
| architecture.png | architecture.png | (final diagram commit) | — |
| All 7 questions answered | README.md | 814456b | — |

---

## Video

| Requirement | File / output | Commit | Video timestamp |
|---|---|---|---|
| Show repo, starting commit, clean git status | terminal | — | 00:00-01:00 |
| Build/start stopped environment; show health | terminal | — | 01:00-03:00 |
| Test /, /health, /ready, /records, /counter | terminal | — | 03:00-05:00 |
| /instance proves both backends via NGINX | terminal | — | 05:00-06:00 |
| Stop one backend; traffic continues; recover | terminal | — | 06:00-08:00 |
| Record survives app + postgres recreation | terminal | 98fee21 | 08:00-10:00 |
| Run validation and failure test | terminal | e166ddc, 9e83ca7 | 10:00-12:00 |
| Demonstrate one historical-log finding | terminal, log_analysis.md | ece5d48 | 12:00-13:00 |
| Run ./video_challenge.sh once | terminal | (live) | 13:00-14:00 |
| Diagnose and fix its runtime fault live | terminal | (live) | 14:00-15:00 |
| Change public port 8080 → 8090 live | docker-compose.yml | (live commit) | 15:00-16:00 |
| Add third app instance live | docker-compose.yml | (live commit) | 16:00-17:00 |
| Rerun validation with three instances | terminal | (live) | 17:00-18:00 |
| git status / git diff, commit on screen, push | terminal | (live commit) | 18:00-19:00 |

---

## Challenge receipt

The video_challenge.sh run produces a receipt at .assessment/challenge.json
(gitignored). The receipt UUID is recorded here after recording:

- Challenge receipt ID: (fill after video)

The challenge lock is one-shot per working copy. It is not deleted or
reset. First-run compliance is judged from the video evidence.