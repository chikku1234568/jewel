# 0006. Deployment

- **Status:** Proposed (hosting is one of the three open items)

## Context

Components: static frontend, FastAPI backend, Neo4j 5.x Community, Postgres, a local
volume for uploaded files, Google OAuth (needs a registered redirect URI), and the xAI API
called with each user's own key.

## Decided so far

- **Local development:** `infra/docker-compose.yml` with Neo4j, Postgres, backend and
  frontend. No cache service.

## Still open

Where the deployed instance runs. Any option must provide: persistent storage for Neo4j,
Postgres and uploaded files; HTTPS (required for `Secure` cookies); and a stable
callback URL for Google. Choosing a custom domain and a production password policy
beyond Google and the session cookie are out of scope for this version.

## Open questions for review

1. Where should the deployed instance be hosted?
