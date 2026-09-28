"""One LangGraph tool-using agent (stub).

A loop, not a fixed ``retrieve -> answer`` function and not a supervisor:

    agent (model) --tool call--> tools (search_graph | read_document) --> agent ...
    agent --answer--> END

* Tools: ``search_graph`` and ``read_document`` only (``jewel.agents.tools``).
* Cap: after at most **4** tool calls the agent must answer.
* The agent never receives a Neo4j session, a Cypher string parameter, or the API key;
  the application binds the user id and the key outside the model.
* Trace: each tool call (name, arguments, short result summary) and each
  ``search_graph`` highlight (node and relationship ids) is streamed to the browser with
  Server-Sent Events, followed by the answer. Citations must match tool results; the UI
  drops any that do not.

LangGraph is not a dependency yet; it is added in the pass that imports it.
"""
