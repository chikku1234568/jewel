"""Personalized PageRank over one user's subgraph.

Damping is 0.5 so the walk stays near the seeds. Passage nodes get a weak prior of
0.05 times their similarity to the question. The walk graph is undirected: predicates
are labels for the UI, not edge types the walk follows.
"""

import networkx as nx

DAMPING = 0.5
PASSAGE_PRIOR = 0.05


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


def walk_graph(
    entity_ids: list[str], document_ids: list[str], edges: list[tuple[str, str, float]]
) -> nx.Graph:
    """Undirected weighted graph. ``edges`` are pairs plus a weight."""
    graph = nx.Graph()
    graph.add_nodes_from(entity_ids)
    graph.add_nodes_from(document_ids)
    for source, target, weight in edges:
        if graph.has_edge(source, target):
            graph[source][target]["weight"] += weight
        else:
            graph.add_edge(source, target, weight=weight)
    return graph
