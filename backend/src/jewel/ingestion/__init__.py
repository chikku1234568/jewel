"""Fixed ingestion pipeline for one document of one user. Not an agent, no role split.

Steps, same order every time: parse -> chunk -> extract -> embed -> write.
Runs only when the user has a saved key; otherwise the document waits
(``waiting_for_key``). Building the graph spends the user's key.
"""
