"""Network analysis of the case entity graph (NetworkX).

Relations are hypotheses unless a reviewer accepted them; the analysis therefore
weights relations by their review state and reports metrics as orientation only.
"""
from __future__ import annotations

import io

# A relation with reviewed sources counts fully; open hypotheses count less.
STATE_WEIGHT = {"supported": 0.8, "hypothesis": 0.5,
              "disputed": 0.2, "rejected": 0.0}


def relation_weight(rel: dict) -> float:
    base = STATE_WEIGHT.get(str(rel.get("state") or "hypothesis"), 0.5)
    reviewed = sum(1 for s in rel.get("sources", []) if str(s.get("review_state")) == "reviewed")
    return round(min(1.0, base + 0.1 * reviewed), 3)


def build_graph(graph: dict):
    import networkx as nx

    g = nx.Graph()
    for e in graph["entities"]:
        g.add_node(str(e["id"]), label=e["label"], kind=e["kind"])
    for rel in graph["relations"]:
        a, b = str(rel["source_id"]), str(rel["target_id"])
        weight = relation_weight(rel)
        if a not in g or b not in g or a == b or weight <= 0:
            continue
        if g.has_edge(a, b):
            g[a][b]["weight"] = max(g[a][b]["weight"], weight)
            g[a][b]["predicates"].append(rel["predicate"])
        else:
            g.add_edge(a, b, weight=weight, predicates=[rel["predicate"]],
                       sources=len(rel.get("sources", [])), state=str(rel.get("state") or ""))
    return g


def analyse(graph: dict) -> dict:
    import networkx as nx
    from networkx.algorithms import community

    g = build_graph(graph)
    if g.number_of_nodes() == 0:
        return {"nodes": 0, "edges": 0, "groups": [], "bridges": [], "central": [], "isolated": [],
                "components": 0, "truth_determined": False}
    # distance = 1/weight so well-supported links count as "short"
    for _, _, data in g.edges(data=True):
        data["distance"] = 1.0 / data["weight"]
    betweenness = nx.betweenness_centrality(g, weight="distance", normalized=True) if g.number_of_edges() else {}
    degree = dict(g.degree(weight="weight"))
    groups = []
    if g.number_of_edges():
        found = community.louvain_communities(g, weight="weight", seed=492)
        for members in sorted(found, key=len, reverse=True):
            if len(members) < 2:
                continue
            groups.append(sorted(({"id": n, "label": g.nodes[n]["label"], "kind": g.nodes[n]["kind"]} for n in members),
                                 key=lambda x: (-degree.get(x["id"], 0), x["label"])))
    group_of = {m["id"]: i for i, grp in enumerate(groups) for m in grp}
    bridges = []
    for node, score in sorted(betweenness.items(), key=lambda kv: -kv[1]):
        neighbour_groups = {group_of.get(n) for n in g.neighbors(node)} - {None}
        if score > 0 and (len(neighbour_groups) > 1 or node in set(nx.articulation_points(g))):
            bridges.append({"id": node, "label": g.nodes[node]["label"], "kind": g.nodes[node]["kind"],
                            "betweenness": round(score, 3), "connects_groups": len(neighbour_groups)})
        if len(bridges) >= 10:
            break
    central = [{"id": n, "label": g.nodes[n]["label"], "kind": g.nodes[n]["kind"],
                "weighted_degree": round(d, 2), "links": g.degree(n)}
               for n, d in sorted(degree.items(), key=lambda kv: (-kv[1], g.nodes[kv[0]]["label"]))[:10] if d > 0]
    isolated = [{"id": n, "label": g.nodes[n]["label"], "kind": g.nodes[n]["kind"]} for n in nx.isolates(g)]
    return {"nodes": g.number_of_nodes(), "edges": g.number_of_edges(), "groups": groups, "bridges": bridges,
            "central": central, "isolated": isolated, "components": nx.number_connected_components(g),
            "truth_determined": False}


def path_between(graph: dict, source: str, target: str) -> list[dict]:
    """Best-supported path (lowest total 1/weight)."""
    import networkx as nx

    g = build_graph(graph)
    for _, _, data in g.edges(data=True):
        data["distance"] = 1.0 / data["weight"]
    try:
        nodes = nx.shortest_path(g, source, target, weight="distance")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []
    steps = []
    for a, b in zip(nodes, nodes[1:]):
        steps.append({"from": g.nodes[a]["label"], "to": g.nodes[b]["label"],
                      "predicates": g[a][b]["predicates"], "weight": g[a][b]["weight"]})
    return steps


def gexf(graph: dict) -> bytes:
    import networkx as nx

    g = build_graph(graph)
    for _, _, data in g.edges(data=True):
        data["predicates"] = "; ".join(data["predicates"])
    out = io.BytesIO()
    nx.write_gexf(g, out)
    return out.getvalue()
