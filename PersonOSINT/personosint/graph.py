"""Netzwerkanalyse ohne externe Abhängigkeiten: Zentralität, Gruppen, Pfade, Layout."""
from __future__ import annotations

import math
import random
from collections import defaultdict, deque
from typing import Any, Iterable


def adjacency(node_ids: Iterable[int], edges: Iterable[dict[str, Any]]) -> dict[int, set[int]]:
    adj: dict[int, set[int]] = {n: set() for n in node_ids}
    for e in edges:
        s, t = e["source_id"], e["target_id"]
        if s in adj and t in adj and s != t:
            adj[s].add(t)
            adj[t].add(s)
    return adj


def betweenness(adj: dict[int, set[int]]) -> dict[int, float]:
    """Brandes-Algorithmus (ungewichtet), normalisiert auf 0..1."""
    cb = dict.fromkeys(adj, 0.0)
    for s in adj:
        stack: list[int] = []
        pred: dict[int, list[int]] = defaultdict(list)
        sigma = dict.fromkeys(adj, 0)
        sigma[s] = 1
        dist = dict.fromkeys(adj, -1)
        dist[s] = 0
        q = deque([s])
        while q:
            v = q.popleft()
            stack.append(v)
            for w in adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    q.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = dict.fromkeys(adj, 0.0)
        while stack:
            w = stack.pop()
            for v in pred[w]:
                delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
            if w != s:
                cb[w] += delta[w]
    n = len(adj)
    norm = (n - 1) * (n - 2) if n > 2 else 1
    return {k: round(v / norm, 4) for k, v in cb.items()}


def communities(adj: dict[int, set[int]], seed: int = 7) -> dict[int, int]:
    """Label Propagation – deterministisch durch festen Seed."""
    rnd = random.Random(seed)
    labels = {n: n for n in adj}
    nodes = sorted(adj)
    for _ in range(20):
        rnd.shuffle(nodes)
        changed = False
        for n in nodes:
            if not adj[n]:
                continue
            counts: dict[int, int] = defaultdict(int)
            for m in adj[n]:
                counts[labels[m]] += 1
            best = max(counts.values())
            choice = min(l for l, c in counts.items() if c == best)
            if labels[n] != choice:
                labels[n] = choice
                changed = True
        if not changed:
            break
    remap: dict[int, int] = {}
    return {n: remap.setdefault(l, len(remap)) for n, l in sorted(labels.items())}


def shortest_paths(adj: dict[int, set[int]], a: int, b: int, limit: int = 10) -> list[list[int]]:
    if a not in adj or b not in adj:
        return []
    if a == b:
        return [[a]]
    dist = {a: 0}
    preds: dict[int, list[int]] = defaultdict(list)
    q = deque([a])
    while q:
        v = q.popleft()
        if v == b:
            continue
        for w in sorted(adj[v]):
            if w not in dist:
                dist[w] = dist[v] + 1
                q.append(w)
            if dist[w] == dist[v] + 1:
                preds[w].append(v)
    if b not in dist:
        return []
    paths: list[list[int]] = []

    def walk(node: int, acc: list[int]) -> None:
        if len(paths) >= limit:
            return
        if node == a:
            paths.append([a, *reversed(acc)])
            return
        for p in preds[node]:
            walk(p, [*acc, node])

    walk(b, [])
    return paths


def simple_paths(adj: dict[int, set[int]], a: int, b: int, max_len: int = 5, limit: int = 15) -> list[list[int]]:
    """Alle einfachen Pfade bis max_len Kanten (begrenzte Tiefensuche)."""
    out: list[list[int]] = []
    if a not in adj or b not in adj:
        return out
    stack = [(a, [a])]
    while stack and len(out) < limit:
        node, path = stack.pop()
        for nxt in sorted(adj[node], reverse=True):
            if nxt in path:
                continue
            if nxt == b:
                out.append([*path, b])
            elif len(path) < max_len:
                stack.append((nxt, [*path, nxt]))
    out.sort(key=len)
    return out[:limit]


def force_layout(node_ids: list[int], adj: dict[int, set[int]], width: float = 1000, height: float = 700,
                 iterations: int = 300, seed: int = 3) -> dict[int, tuple[float, float]]:
    """Fruchterman-Reingold-Layout für den Dossier-Export."""
    rnd = random.Random(seed)
    n = len(node_ids)
    if n == 0:
        return {}
    if n == 1:
        return {node_ids[0]: (width / 2, height / 2)}
    pos = {v: [width / 2 + math.cos(2 * math.pi * i / n) * width / 3 + rnd.random(),
               height / 2 + math.sin(2 * math.pi * i / n) * height / 3 + rnd.random()] for i, v in enumerate(node_ids)}
    k = math.sqrt(width * height / n) * 0.75
    temp = width / 8
    for _ in range(iterations):
        disp = {v: [0.0, 0.0] for v in node_ids}
        for i, v in enumerate(node_ids):
            for u in node_ids[i + 1:]:
                dx, dy = pos[v][0] - pos[u][0], pos[v][1] - pos[u][1]
                d = math.hypot(dx, dy) or 0.01
                f = k * k / d
                disp[v][0] += dx / d * f
                disp[v][1] += dy / d * f
                disp[u][0] -= dx / d * f
                disp[u][1] -= dy / d * f
        for v in node_ids:
            for u in adj.get(v, ()):
                if u <= v or u not in pos:
                    continue
                dx, dy = pos[v][0] - pos[u][0], pos[v][1] - pos[u][1]
                d = math.hypot(dx, dy) or 0.01
                f = d * d / k
                disp[v][0] -= dx / d * f
                disp[v][1] -= dy / d * f
                disp[u][0] += dx / d * f
                disp[u][1] += dy / d * f
        for v in node_ids:
            # leichte Schwerkraft zur Mitte, damit isolierte Knoten nicht wegdriften
            disp[v][0] += (width / 2 - pos[v][0]) * 0.02
            disp[v][1] += (height / 2 - pos[v][1]) * 0.02
            d = math.hypot(*disp[v]) or 0.01
            pos[v][0] += disp[v][0] / d * min(d, temp)
            pos[v][1] += disp[v][1] / d * min(d, temp)
        temp *= 0.985
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    pad_x, pad_y = max(70.0, width * 0.12), 60.0  # Platz für Beschriftungen am Rand
    sx = (width - 2 * pad_x) / ((max(xs) - min(xs)) or 1)
    sy = (height - 2 * pad_y - 40) / ((max(ys) - min(ys)) or 1)
    return {v: (pad_x + (p[0] - min(xs)) * sx, pad_y + (p[1] - min(ys)) * sy) for v, p in pos.items()}


# --------------------------------------------------------------------------- gewichtete Verfahren (gemeinsamer Kern)
# Schritt 503 der Zusammenführung: Diese Funktionen nutzen PersonOSINT *und* die EagleEye-Fallakte. Gewicht = Belegstärke
# einer Verbindung (0..1); als Weglänge zählt 1/Gewicht, gut belegte Verbindungen sind also „kurz“.

def _weighted(edges: Iterable[tuple[Any, Any, float]]) -> dict[Any, dict[Any, float]]:
    adj: dict[Any, dict[Any, float]] = defaultdict(dict)
    for a, b, w in edges:
        if a == b or w <= 0:
            continue
        adj[a][b] = adj[b][a] = max(w, adj[a].get(b, 0.0))
    return adj


def weighted_betweenness(node_ids: Iterable[Any], edges: Iterable[tuple[Any, Any, float]]) -> dict[Any, float]:
    """Brandes mit Dijkstra (Weglänge 1/Gewicht), normalisiert wie NetworkX (ungerichtet, normalized=True)."""
    import heapq
    from itertools import count

    nodes = list(dict.fromkeys(node_ids))
    adj = _weighted(edges)
    cb = dict.fromkeys(nodes, 0.0)
    tie = count()
    for s in nodes:
        stack: list[Any] = []
        pred: dict[Any, list[Any]] = defaultdict(list)
        sigma: dict[Any, float] = dict.fromkeys(nodes, 0.0)
        sigma[s] = 1.0
        dist: dict[Any, float] = {}
        seen = {s: 0.0}
        heap = [(0.0, next(tie), s, s)]
        while heap:
            d, _, prev, v = heapq.heappop(heap)
            if v in dist:
                continue
            sigma[v] += sigma[prev] if prev != v else 0.0
            stack.append(v)
            dist[v] = d
            for w, weight in adj.get(v, {}).items():
                vw = d + 1.0 / weight
                if w not in dist and (w not in seen or vw < seen[w]):
                    seen[w] = vw
                    heapq.heappush(heap, (vw, next(tie), v, w))
                    sigma[w] = 0.0
                    pred[w] = [v]
                elif vw == seen.get(w):
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = dict.fromkeys(stack, 0.0)
        while stack:
            w = stack.pop()
            for v in pred[w]:
                delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
            if w != s:
                cb[w] += delta[w]
    n = len(nodes)
    scale = 1.0 / ((n - 1) * (n - 2)) if n > 2 else 1.0
    return {k: v * scale for k, v in cb.items()}


def louvain(node_ids: Iterable[Any], edges: Iterable[tuple[Any, Any, float]], resolution: float = 1.0) -> list[set[Any]]:
    """Louvain-Gruppen (gewichtete Modularität), deterministisch: Knoten werden in fester Reihenfolge besucht."""
    nodes = sorted(dict.fromkeys(node_ids), key=str)
    base = _weighted(edges)
    graph: dict[Any, dict[Any, float]] = {n: dict(base.get(n, {})) for n in nodes}
    members: dict[Any, set[Any]] = {n: {n} for n in nodes}
    m = sum(sum(w for b, w in nb.items() if b != a) for a, nb in graph.items()) / 2 + sum(nb.get(a, 0.0) for a, nb in graph.items())
    if m <= 0:
        return [{n} for n in nodes]
    while True:
        degree = {a: sum(w for b, w in nb.items() if b != a) + 2 * nb.get(a, 0.0) for a, nb in graph.items()}
        comm = {a: a for a in graph}
        tot = dict(degree)
        order = sorted(graph, key=str)
        moved_any = False
        improved = True
        while improved:
            improved = False
            for i in order:
                current = comm[i]
                links: dict[Any, float] = defaultdict(float)
                for j, w in graph[i].items():
                    if j != i:
                        links[comm[j]] += w
                tot[current] -= degree[i]
                best, best_gain = current, links.get(current, 0.0) - resolution * tot[current] * degree[i] / (2 * m)
                for c in sorted(links, key=str):
                    gain = links[c] - resolution * tot[c] * degree[i] / (2 * m)
                    if gain > best_gain + 1e-12:
                        best, best_gain = c, gain
                tot[best] += degree[i]
                if best != current:
                    comm[i] = best
                    improved = moved_any = True
        if not moved_any:
            break
        new_members: dict[Any, set[Any]] = defaultdict(set)
        new_graph: dict[Any, dict[Any, float]] = defaultdict(lambda: defaultdict(float))
        for a in graph:
            new_members[comm[a]] |= members[a]
            new_graph[comm[a]]  # Knoten auch ohne Kanten anlegen
        for a, nb in graph.items():
            for b, w in nb.items():
                ca, cb_ = comm[a], comm[b]
                if a == b:
                    new_graph[ca][ca] += w
                elif ca == cb_:
                    if str(a) < str(b):
                        new_graph[ca][ca] += w
                else:
                    new_graph[ca][cb_] += w
        graph = {a: dict(nb) for a, nb in new_graph.items()}
        members = dict(new_members)
    return sorted(members.values(), key=lambda s: (-len(s), sorted(map(str, s))))


def best_path(edges: Iterable[tuple[Any, Any, float]], a: Any, b: Any) -> list[Any]:
    """Am besten belegter Weg (kleinste Summe 1/Gewicht) von a nach b; leer, wenn keiner existiert."""
    import heapq

    adj = _weighted(edges)
    if a not in adj or b not in adj:
        return [a] if a == b else []
    dist, prev, heap = {a: 0.0}, {}, [(0.0, str(a), a)]
    done: set[Any] = set()
    while heap:
        d, _, v = heapq.heappop(heap)
        if v in done:
            continue
        done.add(v)
        if v == b:
            break
        for w, weight in adj[v].items():
            nd = d + 1.0 / weight
            if nd < dist.get(w, float("inf")):
                dist[w], prev[w] = nd, v
                heapq.heappush(heap, (nd, str(w), w))
    if b not in done:
        return []
    path = [b]
    while path[-1] != a:
        path.append(prev[path[-1]])
    return path[::-1]
