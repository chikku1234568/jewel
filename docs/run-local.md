# Run jewel locally

Commands are for Command Prompt (`cmd.exe`). From the repo root, `jewel\`. Open the app at `localhost`, not `127.0.0.1`. `.env` must already have Google, Postgres, Neo4j, `SESSION_SECRET`, and `JEWEL_ENV=local`. Node 20.19 or newer.

Use two windows. The API window stays open. Start the frontend in a second window.

Postgres and Neo4j, from `jewel\`:

```cmd
docker compose -f infra/docker-compose.yml --env-file .env up -d postgres neo4j
```

If `docker` is not recognized, call it by full path:

```cmd
"%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe" compose -f infra/docker-compose.yml --env-file .env up -d postgres neo4j
```

API. `uv sync` and `uv run` hit Access denied on this OneDrive tree. Start the existing venv. In Command Prompt the variable is `set PYTHONPATH=src` with no `$`, no quotes, and no space around `=`.

```cmd
cd backend
set PYTHONPATH=src
.venv\Scripts\python.exe -m uvicorn jewel.api.app:app --reload --env-file ../.env --host 127.0.0.1 --port 8000
```

Health is http://localhost:8000/health. If the log stops at `Reloading...` and never prints `Application startup complete`, close that window and run the three lines above again.

If startup dies with `cannot import name '__version__' from 'websockets'`, the package's `.py` files are missing and only `.pyc` files are left. From `backend`, reinstall it, then start the API again:

```cmd
.venv\Scripts\python.exe -m pip install "websockets>=14,<17"
```

Frontend, in a new Command Prompt. Skip `npm ci`. On this OneDrive folder it deletes `node_modules` and then fails with `EPERM` on `node_modules\.bin`, which removes the `vite` command.

```cmd
cd /d C:\Users\Srikar\OneDrive\crown-jewel\jewel\frontend
npm run dev
```

If that says `'vite' is not recognized`, install in place and start again. `npm install` does not wipe the folder.

```cmd
npm install
npm run dev
```

Open http://localhost:5173
