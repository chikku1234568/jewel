"""Graph vocabulary: two node labels and two relationship types.

* ``Document``: one uploaded file (raw text, filename, times, status, embedding). The
  passage node.
* ``Entity``: a phrase node (``name``, ``type``, ``embedding``).
* ``MENTIONS``: Entity -> Document, with ``quote``, offsets, ``valid_at``.
* ``RELATED_TO``: Entity -> Entity, with ``predicate`` (a property, not a relationship
  type), ``quote``, offsets, ``document_id``, ``valid_at``, ``invalid_at``.

Every node and relationship carries ``user_id``.
"""

from enum import StrEnum


class NodeLabel(StrEnum):
    DOCUMENT = "Document"
    ENTITY = "Entity"


class RelationshipType(StrEnum):
    MENTIONS = "MENTIONS"
    RELATED_TO = "RELATED_TO"


class EntityType(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    PLACE = "place"
    CONCEPT = "concept"
    OTHER = "other"
