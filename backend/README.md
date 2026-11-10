# jewel backend

Python 3.11+ / FastAPI. The root [README](../README.md) is the guide for running the app.

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
JEWEL_TEST_DATABASE_URL=postgresql://jewel:jewel@localhost:5432/jewel_test uv run pytest
uv run uvicorn jewel.api.app:app --reload --env-file ../.env
```

Point `JEWEL_TEST_DATABASE_URL` at a database the tests may wipe. They truncate `users`, `sessions`, `oauth_states`, `documents`, and `extraction_cache`.

`jewel.llm.kimi` is a small client for optional live agent tests. It reads `KIMI_API_KEY` from the environment when those tests run. The API does not use that variable. Build and Ask take the key from the request and do not store it.
