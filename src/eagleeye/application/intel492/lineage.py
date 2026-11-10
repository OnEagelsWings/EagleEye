"""Source families: near-duplicate detection across a case's documents (MinHash/LSH).

Twenty copies of one agency text are one origin, not twenty confirmations. The result
is an analytical hint for the investigator; it decides nothing about truth or origin.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

NUM_PERM = 128
SHINGLE = 5
MIN_WORDS = 30
LEVELS = {"streng": 0.7, "normal": 0.5, "locker": 0.3}
_HEADER_PREFIXES = ("Web-Beleg – ungeprüfte Extraktion", "Public source snapshot")
_WORD = re.compile(r"\w+", re.UNICODE)


def document_text(anchors: list[dict]) -> str:
    parts = []
    for anchor in anchors:
        text = str(anchor.get("text_excerpt") or "")
        if anchor.get("anchor_kind") in ("heading", "table") or text.startswith(_HEADER_PREFIXES):
            continue
        parts.append(text)
    return "\n".join(parts)


def shingles(text: str, size: int = SHINGLE) -> set[str]:
    words = [w.casefold() for w in _WORD.findall(text)]
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}


def source_families(documents: list[dict], *, level: str = "normal") -> dict:
    """documents: [{document_id,title,source_url,first_seen,text}] of ONE case."""
    from datasketch import MinHash, MinHashLSH

    if level not in LEVELS:
        raise ValueError("unknown level")
    threshold = LEVELS[level]
    usable, skipped, sketches = [], [], {}
    for doc in documents:
        words = _WORD.findall(doc.get("text") or "")
        if len(words) < MIN_WORDS:
            skipped.append(doc)
            continue
        mh = MinHash(num_perm=NUM_PERM, seed=492)
        for sh in shingles(doc["text"]):
            mh.update(sh.encode("utf-8"))
        sketches[doc["document_id"]] = mh
        usable.append(doc)
    lsh = MinHashLSH(threshold=threshold, num_perm=NUM_PERM)
    for doc in usable:
        lsh.insert(doc["document_id"], sketches[doc["document_id"]])
    parent = {d["document_id"]: d["document_id"] for d in usable}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    similarities: dict[tuple, float] = {}
    for doc in usable:
        for other in lsh.query(sketches[doc["document_id"]]):
            if other == doc["document_id"]:
                continue
            score = sketches[doc["document_id"]].jaccard(sketches[other])
            if score >= threshold:
                pair = tuple(sorted((doc["document_id"], other)))
                similarities[pair] = round(score, 3)
                a, b = find(pair[0]), find(pair[1])
                if a != b:
                    parent[b] = a
    groups: dict[str, list[dict]] = {}
    for doc in usable:
        groups.setdefault(find(doc["document_id"]), []).append(doc)
    families = []
    for members in groups.values():
        members = sorted(members, key=lambda d: (d.get("first_seen") or "9999", d["document_id"]))
        ids = {m["document_id"] for m in members}
        hosts = sorted({(urlsplit(m.get("source_url") or "").hostname or "ohne Quellen-URL") for m in members})
        pair_scores = [s for (a, b), s in similarities.items() if a in ids and b in ids]
        families.append({
            "members": members,
            "size": len(members),
            "hosts": hosts,
            "earliest": members[0],
            "max_similarity": max(pair_scores) if pair_scores else None,
            "min_similarity": min(pair_scores) if pair_scores else None,
        })
    families.sort(key=lambda f: (-f["size"], f["earliest"].get("first_seen") or ""))
    return {
        "level": level, "threshold": threshold,
        "documents": len(documents), "compared": len(usable), "skipped": skipped,
        "families": families, "independent_origins": len(families),
        "duplicate_documents": sum(f["size"] - 1 for f in families),
        "truth_determined": False,
    }
