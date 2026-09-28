"""Ask routes (stub, NOT mounted yet). Session required.

* ``POST /ask``: start an agent run for a question; returns a run id. Disabled when no key
  is saved or no document is ``ready``.
* ``GET /ask/{run_id}/events``: Server-Sent Events stream of tool calls, graph highlights,
  the answer, and errors (see ``jewel.agents.graph``).
* ``POST /ask/{run_id}/compare``: the text-search comparison for the same question
  (``jewel.retrieval.baseline_rag``). Not a tool and not an agent.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/ask", tags=["ask"])  # no endpoints yet
