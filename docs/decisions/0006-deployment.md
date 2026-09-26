# 0006. Deployment

- **Status:** Proposed (hosting undecided)

## Context

Done means "a private URL". Components: static frontend, FastAPI backend, Neo4j, Redis,
an LLM provider. Synthetic data only; access should be restricted, not public.

## Proposed decision

- **Local dev:** `infra/docker-compose.yml` (neo4j, redis, backend, frontend). Exists as a
  placeholder now.
- **Hosting:** undecided; options below.

## Options

| Option | Frontend | Backend | Neo4j | Redis | Notes |
|---|---|---|---|---|---|
| A. PaaS mix | Vercel or Netlify | Render, Railway or Fly.io | Neo4j AuraDB Free, or a container on the same PaaS | Managed Redis free tier or a container | Least ops; free-tier limits and sleep behaviour to verify; GDS plugin availability on Aura to verify if we choose GDS |
| B. Single VM | same host | same host | container | container | Run the compose stack on one small VM behind Caddy/nginx with HTTPS + basic auth; cheapest and closest to local |
| C. Fly.io for everything | Fly static/app | Fly | Fly volume + container | Fly container | One platform; volumes needed for Neo4j data |

"Private URL" can be enforced with HTTP basic auth at the proxy, an access-controlled tunnel
(e.g. Cloudflare Access), or platform password protection (check plan requirements).

## Open questions for review

1. Budget: free tiers only, or a small paid VM acceptable?
2. What does "private" need to mean: unguessable URL, a shared password, or SSO?
3. Any provider preference or existing accounts?
