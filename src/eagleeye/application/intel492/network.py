"""Network analysis of the case entity graph (shared core in ``personosint.network``; NetworkX only for GEXF export).

Relations are hypotheses unless a reviewer accepted them; the analysis therefore
weights relations by their review state and reports metrics as orientation only.
"""
from __future__ import annotations

import io

from eagleeye.infrastructure.providers.personosint_bridge import _personosint

_personosint()
from personosint import graph as po_graph  # noqa: E402
from personosint import network as po_network  # noqa: E402

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


def _core_input(graph: dict) -> tuple[list[dict], list[dict], dict]:
    nodes = [{"id": str(e["id"]), "label": e["label"], "kind": e["kind"]} for e in graph["entities"]]
    edges, predicates = [], {}
    for rel in graph["relations"]:
        a, b = str(rel["source_id"]), str(rel["target_id"])
        weight = relation_weight(rel)
        edges.append({"source": a, "target": b, "weight": weight})
        if weight > 0:
            predicates.setdefault((a, b) if a <= b else (b, a), []).append(rel["predicate"])
    return nodes, edges, predicates


def analyse(graph: dict) -> dict:
    """Schritt 503: dieselbe Analyse wie in PersonOSINT (``personosint.network.analyse_weighted``)."""
    nodes, edges, _ = _core_input(graph)
    result = po_network.analyse_weighted(nodes, edges, brief_keys=("id", "label", "kind"))
    for bridge in result["bridges"]:
        bridge.pop("cut_point", None)
    return result


def path_between(graph: dict, source: str, target: str) -> list[dict]:
    """Best-supported path (lowest total 1/weight)."""
    nodes, edges, predicates = _core_input(graph)
    labels = {n["id"]: n["label"] for n in nodes}
    usable = [(e["source"], e["target"], e["weight"]) for e in edges
              if e["source"] in labels and e["target"] in labels and e["weight"] > 0]
    weight = {}
    for a, b, w in usable:
        key = (a, b) if a <= b else (b, a)
        weight[key] = max(w, weight.get(key, 0.0))
    if source not in labels or target not in labels:
        return []
    nodes_on_path = po_graph.best_path(usable, source, target)
    steps = []
    for a, b in zip(nodes_on_path, nodes_on_path[1:]):
        key = (a, b) if a <= b else (b, a)
        steps.append({"from": labels[a], "to": labels[b], "predicates": predicates[key], "weight": weight[key]})
    return steps


def gexf(graph: dict) -> bytes:
    import networkx as nx

    g = build_graph(graph)
    for _, _, data in g.edges(data=True):
        data["predicates"] = "; ".join(data["predicates"])
    out = io.BytesIO()
    nx.write_gexf(g, out)
    return out.getvalue()
