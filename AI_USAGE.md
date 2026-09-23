# AI usage disclosure

AI tools were used as drafting and reviewing aids throughout this task.
Every generated suggestion was read, edited, tested, and verified against
the running environment before being committed. No content was committed
without local verification.

---

## Tool — DeepSeek

Purpose:
  - Draft the initial investigation plan and hard-requirements checklist.
  - Explain unfamiliar concepts (Docker networks, volumes, NGINX
    upstreams, Redis AOF persistence, loopback vs 0.0.0.0 binding).
  - Draft the initial versions of validate.py, failure_test.py,
    backup.sh, restore.sh, and .github/workflows/ci.yml.
  - Draft the report templates (log_analysis.md, decisions.md,
    security_review.md, this file, README.md).
  - Debug specific runtime failures encountered during the fix phase
    (compose port mapping, pg_dump --clean behaviour, CI step ordering).

Files or decisions affected:
  - troubleshooting.md (structure and 22 investigation entries)
  - log_analysis.md (structure, command list, draft answers)
  - decisions.md (five decisions drafted and edited)
  - security_review.md (ten risks drafted and edited)
  - AI_USAGE.md (this file)
  - README.md (structure)
  - validate.py
  - failure_test.py
  - backup.sh
  - restore.sh
  - .github/workflows/ci.yml

What was changed or rejected:
  - Every command in log_analysis.md was run locally; the model's
    guessed numbers were replaced with real output.
  - Rewrote validate.py so it matched this project's actual endpoints,
    container names, and network names.
  - Added mkdir -p config to the CI workflow after a real failure
    ("No such file or directory") on GitHub Actions.
  - Reordered CI steps so .env is created before docker compose config,
    after the first CI run failed on a missing POSTGRES_PASSWORD.
  - Fixed backup.sh to use pg_dump --clean --if-exists after the first
    restore attempt failed with "relation already exists".
  - Fixed APP_HOST (loopback vs 0.0.0.0), INSTANCE_ID duplication, and
    NGINX upstream port mismatches by reading the actual files — the
    model provided direction, not answers.

How it was independently verified:
  - Every fix was applied, then tested with a specific command whose
    output was recorded in troubleshooting.md.
  - Every number in log_analysis.md comes from a command run in this
    WSL environment, not from the model.
  - Every commit hash referenced in decisions.md and security_review.md
    was checked with git log.
  - CI passes on GitHub Actions: run 35780594956.
  - backup/restore round-trip proof recorded in troubleshooting.md
    Entry 22.
  - Video demonstration (recorded separately) shows live commands, no
    edits, and no re-takes.

Related commits:
  Multiple doc commits (ece5d48, and the commits that follow), plus
  e166ddc, 9e83ca7, a35e6a0, and the ci.yml commit.

---

## What AI was NOT used for

  - The 21 environment fixes were applied, tested, and committed by
    hand, with the failures and retests recorded.
  - All historical log numbers were produced by commands run locally.
  - The video demonstration was a live continuous take with no AI
    narration or editing.

## Statement

I understand every commit in this repository and can explain the
purpose of each file and each fix. DeepSeek was used to accelerate
drafting and to explain unfamiliar concepts; every artifact was
verified locally before submission.