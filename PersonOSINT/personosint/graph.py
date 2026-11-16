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
