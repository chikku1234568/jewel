# 0015. Branching

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

Production will be one VM that runs a commit of this repo. CI already runs on pushes to `main` and on pull requests. It does not deploy. Direct pushes to `main` were enough while the only runner was a laptop. A public hostname needs a rule for which commit is allowed to be running.

## Decision

GitHub Flow, one long-lived branch.

- `main` is the only long-lived branch. The VM deploys `main` and nothing else.
- Each change starts as a new branch from current `main`, named `feature/<what>` or `fix/<what>`.
- The change comes back through a pull request into `main`. CI must be green. Then it is merged, and the branch is deleted.
- There is no `develop` branch and no release branch. A second long-lived branch would make the laptop, GitHub, and the VM disagree about which commit is real.
- Do not force-push `main`.
- A production fix uses the same path: branch from `main`, pull request, green CI, merge. The Deploy workflow then checks out that commit on the VM and runs Compose. `infra/prod.env` stays on the VM and is never committed. A dry run of the same workflow only prints the commit id and `docker compose ps`. A green CI run on `main` deploys by itself only when the repository variable `JEWEL_AUTO_DEPLOY` is `true`.

## Consequences

- The commit on the VM is one that the backend and frontend jobs have already run.
- A pull request is required before a change is something the VM is allowed to run. Turning on "require a pull request and the CI check" in the GitHub branch settings is what enforces this. Until that setting is on, the rule is only a habit.
- Day-to-day local work does not change. Postgres and Neo4j still come from `infra/docker-compose.yml`.
