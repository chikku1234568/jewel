"""``parse`` node (stub).

Loads the run's ``:Episode`` nodes, runs ``jewel.kg.extraction`` (LLM triple
extraction) and classifies each episode (order / progress note / lab). Writes nothing
to the clinical schema itself; typed writes are left to the role agents.
"""
