"""Personalized PageRank over one user's statements.

Damping is 0.5 so the walk stays near the seed facts. A statement node connects to its
two names. Another fact that shares a name can pick up weight even when its wording
did not match the question. Predicates are labels, not edge types. File nodes are not
in this graph: a whole file cannot name the next fact.
"""

import networkx as nx

from jewel.kg.records import GraphTriple

DAMPING = 0.5


def personalized_pagerank(
    graph: nx.Graph,
    personalization: dict[str, float],
) -> dict[str, float]:
    """Rank every node. Teleport probability is ``1 - DAMPING``."""
    nodes = list(graph.nodes)
    if not nodes:
        return {}
    raw = {node: max(personalization.get(node, 0.0), 0.0) for node in nodes}
    total = sum(raw.values())
    if total <= 0:
        teleport = {node: 1.0 / len(nodes) for node in nodes}
    else:
        teleport = {node: raw[node] / total for node in nodes}
    rank = dict(teleport)
    for _ in range(40):
        nxt = {node: (1.0 - DAMPING) * teleport[node] for node in nodes}
        for node in nodes:
            edges = graph[node]
            out = sum(data.get("weight", 1.0) for data in edges.values())
            if out <= 0:
                share = DAMPING * rank[node]
                for other in nodes:
                    nxt[other] += share * teleport[other]
                continue
            share = DAMPING * rank[node] / out
            for neighbor, data in edges.items():
                nxt[neighbor] += share * data.get("weight", 1.0)
        rank = nxt
    return rank


def statement_graph(entity_ids: list[str], triples: list[GraphTriple]) -> nx.Graph:
    """Undirected graph: each fact node linked to the names it joins."""
    graph = nx.Graph()
    graph.add_nodes_from(entity_ids)
    for triple in triples:
        graph.add_node(triple.id)
        _link(graph, triple.id, triple.source_id)
        if triple.target_id != triple.source_id:
            _link(graph, triple.id, triple.target_id)
    return graph


def _link(graph: nx.Graph, left: str, right: str) -> None:
    if graph.has_edge(left, right):
        graph[left][right]["weight"] += 1.0
    else:
        graph.add_edge(left, right, weight=1.0)
