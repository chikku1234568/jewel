"""Fixed ingestion pipeline for one document of one user. Not an agent.

Steps for that document only: extract, embed, write. Earlier documents are not
reprocessed. The extraction model is local and open source. The user's API key is
not spent here.
"""
