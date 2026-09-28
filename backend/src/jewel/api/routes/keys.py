"""API-key routes (stub, NOT mounted yet). Session required.

* ``PUT /me/api-key``: store the user's xAI key as ciphertext (``KEY_ENCRYPTION_SECRET``).
  The paste field is never echoed back.
* ``DELETE /me/api-key``: delete it. Stops new model calls; the graph stays.
* ``POST /me/api-key/check``: one cheap authenticated call to ``https://api.x.ai/v1`` with
  the stored key; report success or failure.

The key is never logged, never sent to the frontend bundle, and never returned in full.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/me/api-key", tags=["keys"])  # no endpoints yet
