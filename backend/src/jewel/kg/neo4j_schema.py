"""Uniqueness constraints applied when the API connects to Neo4j.

Community edition accepts these. They match the keys the writes already MERGE on, so a
second file cannot create a second node for the same user and id, or the same name.
"""

import logging

logger = logging.getLogger(__name__)

# One node per user for a document id, a folded name, and a statement id.
_CONSTRAINTS = (
    """
    CREATE CONSTRAINT document_user_id IF NOT EXISTS
    FOR (n:Document) REQUIRE (n.user_id, n.id) IS UNIQUE
    """,
    """
    CREATE CONSTRAINT entity_user_name IF NOT EXISTS
    FOR (n:Entity) REQUIRE (n.user_id, n.name_key) IS UNIQUE
    """,
    """
    CREATE CONSTRAINT statement_user_id IF NOT EXISTS
    FOR (n:Statement) REQUIRE (n.user_id, n.id) IS UNIQUE
    """,
)

_INDEXES = (
    """
    CREATE INDEX statement_document IF NOT EXISTS
    FOR (n:Statement) ON (n.user_id, n.document_id)
    """,
)


def constraint_statements() -> tuple[str, ...]:
    return _CONSTRAINTS + _INDEXES


def ensure_schema(driver) -> None:
    """Create the constraints and indexes. Existing ones are left in place."""
    with driver.session() as session:
        for statement in constraint_statements():
            session.run(statement).consume()
    logger.info("Neo4j constraints are in place")
