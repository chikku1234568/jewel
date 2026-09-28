# 0008. Google OAuth sign-in with server-side sessions

- **Status:** Accepted (settled by `docs/problem-statement.md`, 2026-09-28)

## Context

Each person has one account, one graph and their own files. A second Google account must
not see the first account's files, graph, key or questions.

## Decision

- Google is the only sign-in: authorization-code flow, scopes `openid`, `email`,
  `profile` (no Gmail or Drive scopes).
- The OAuth `state` is stored server-side for the round trip. The server verifies the ID
  token (`iss`, `aud`, `exp`) and creates a session stored in Postgres.
- The browser gets an `httpOnly`, `Secure`, `SameSite=Lax` cookie with a random session
  id. Logout deletes the session.
- No passwords, no second provider, no guest mode; the scaffold ships no fake user.
- Environment: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
  (localhost during development), `SESSION_SECRET`.

## Consequences

- Every route except health and the two Google routes requires a session; the session
  user id is the tenancy key for Postgres and Neo4j.
- Code lives in `jewel.auth` (`google`, `sessions`) and `jewel.api.routes.auth`.
