"""Graph vocabulary.

* ``Document``: the file record (raw text, filename, embedding). PageRank does not score it.
* ``Entity``: a name (``name``, ``type``, ``embedding`` of the name). The bridge between facts.
* ``Statement``: one extracted fact. PageRank scores these nodes. The fact string
  ``subject predicate object`` is the embedding. ``quote`` is the file sentence.
* ``MENTIONS``: Entity -> Document. Which file contains a name. Not a walk edge.
* ``ABOUT``: Statement -> Entity, ``role`` ``subject`` or ``object``.
* ``RELATED_TO``: Entity -> Entity on graphs built before statement nodes. Still loaded
  and still deletable. A rebuild of that file replaces it with statement nodes.

Every node and relationship carries ``user_id``.
"""

from enum import StrEnum


class NodeLabel(StrEnum):
    DOCUMENT = "Document"
    ENTITY = "Entity"
    STATEMENT = "Statement"


class RelationshipType(StrEnum):
    MENTIONS = "MENTIONS"
    ABOUT = "ABOUT"
    RELATED_TO = "RELATED_TO"


class EntityType(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    PLACE = "place"
    CONCEPT = "concept"
    OTHER = "other"
