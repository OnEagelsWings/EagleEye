"""Source families: near-duplicate detection across a case's documents (MinHash).

Twenty copies of one agency text are one origin, not twenty confirmations. The result
is an analytical hint for the investigator; it decides nothing about truth or origin.

Each document gets a MinHash fingerprint (128 values over five-word shingles). The
fingerprint is computed once and stored; a view only compares fingerprints.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit

import numpy as np

NUM_PERM = 128
SHINGLE = 5
MIN_WORDS = 30
ALGO = "minhash128-splitmix64-shingle5-v2"
LEVELS = {"streng": 0.7, "normal": 0.5, "locker": 0.3}
_HEADER_PREFIXES = ("Web-Beleg – ungeprüfte Extraktion", "Public source snapshot")
_WORD = re.compile(r"\w+", re.UNICODE)
# One 64-bit seed per hash function. Each function is the splitmix64 finaliser of
# (shingle hash XOR seed): a bijection on 64 bits that mixes all bits, so the 128 orderings
# are effectively independent. (A linear a*h+b with small multipliers is NOT: many of the
# functions then order the shingles identically and the estimate is far off.)
_SEEDS = np.random.RandomState(492).randint(0, 2**63 - 1, size=NUM_PERM, dtype=np.int64).astype(np.uint64)
_M1, _M2 = np.uint64(0xBF58476D1CE4E5B9), np.uint64(0x94D049BB133111EB)
_S30, _S27, _S31 = np.uint64(30), np.uint64(27), np.uint64(31)

TABLE = """CREATE TABLE IF NOT EXISTS lineage_sketch_492(
    document_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, anchor_count INTEGER NOT NULL,
    algo TEXT NOT NULL, word_count INTEGER NOT NULL, signature BLOB)"""


def initialize(ctx) -> None:
    ctx.db.conn.execute(TABLE)
    ctx.db.conn.execute("CREATE INDEX IF NOT EXISTS lineage_sketch_492_case ON lineage_sketch_492(case_id)")
    ctx.db.conn.commit()


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


def sketch(text: str) -> tuple[int, np.ndarray | None]:
    """(word count, fingerprint). Documents with too little text get no fingerprint."""
    words = len(_WORD.findall(text or ""))
    if words < MIN_WORDS:
        return words, None
    hashes = np.fromiter((int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest(), "big")
                          for s in shingles(text)), dtype=np.uint64)
    signature = np.full(NUM_PERM, np.iinfo(np.uint64).max, dtype=np.uint64)
    for start in range(0, len(hashes), 4096):  # bounded memory for very long documents
        z = hashes[start:start + 4096, None] ^ _SEEDS[None, :]
        z = (z ^ (z >> _S30)) * _M1  # uint64 array arithmetic wraps modulo 2**64 by design
        z = (z ^ (z >> _S27)) * _M2
        z = z ^ (z >> _S31)
        signature = np.minimum(signature, z.min(axis=0))
    return words, signature


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float((a == b).mean())


def families(documents: list[dict], *, level: str = "normal") -> dict:
    """documents: [{document_id,title,source_url,first_seen,word_count,signature}] of ONE case."""
    if level not in LEVELS:
        raise ValueError("unknown level")
    threshold = LEVELS[level]
    usable = [d for d in documents if d.get("signature") is not None]
    skipped = [d for d in documents if d.get("signature") is None]
    parent = list(range(len(usable)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    pair_scores: dict[tuple[int, int], float] = {}
    if len(usable) > 1:
        matrix = np.vstack([d["signature"] for d in usable])
        for i in range(len(usable) - 1):
            scores = (matrix[i + 1:] == matrix[i]).mean(axis=1)
            for offset in np.nonzero(scores >= threshold)[0]:
                j = i + 1 + int(offset)
                pair_scores[(i, j)] = round(float(scores[offset]), 3)
                a, b = find(i), find(j)
                if a != b:
                    parent[b] = a
    groups: dict[int, list[int]] = {}
    for index in range(len(usable)):
        groups.setdefault(find(index), []).append(index)
    out = []
    for members in groups.values():
        inside = set(members)
        scores = [s for (a, b), s in pair_scores.items() if a in inside and b in inside]
        docs = sorted((usable[i] for i in members), key=lambda d: (d.get("first_seen") or "9999", d["document_id"]))
        out.append({
            "members": docs, "size": len(docs),
            "hosts": sorted({(urlsplit(m.get("source_url") or "").hostname or "ohne Quellen-URL") for m in docs}),
            "earliest": docs[0],
            "max_similarity": max(scores) if scores else None,
            "min_similarity": min(scores) if scores else None,
        })
    out.sort(key=lambda f: (-f["size"], f["earliest"].get("first_seen") or ""))
    return {
        "level": level, "threshold": threshold,
        "documents": len(documents), "compared": len(usable), "skipped": skipped,
        "families": out, "independent_origins": len(out),
        "duplicate_documents": sum(f["size"] - 1 for f in out),
        "truth_determined": False,
    }


def source_families(documents: list[dict], *, level: str = "normal") -> dict:
    """Convenience for documents that carry their text: fingerprints are computed in memory."""
    prepared = []
    for doc in documents:
        words, signature = sketch(doc.get("text") or "")
        prepared.append({**doc, "word_count": words, "signature": signature})
    return families(prepared, level=level)


def case_sketches(ctx, *, identity: dict, documents: list[dict]) -> dict[str, tuple[int, np.ndarray | None]]:
    """Fingerprints for the given Build-458 documents of one case, computed once and stored.

    A stored fingerprint is reused while the document's number of anchors is unchanged
    (added OCR or structure anchors change the text and trigger a recomputation).
    """
    if not documents:
        return {}
    service = ctx.document_intelligence_458
    case_id = documents[0]["case_id"]
    counts = {row["document_id"]: int(row["n"]) for row in ctx.db.all(
        "SELECT document_id, COUNT(*) AS n FROM phase20_document_anchor_458 WHERE case_id=? GROUP BY document_id", (case_id,))}
    stored = {row["document_id"]: row for row in ctx.db.all(
        "SELECT * FROM lineage_sketch_492 WHERE case_id=?", (case_id,))}
    result: dict[str, tuple[int, np.ndarray | None]] = {}
    fresh = []
    for doc in documents:
        doc_id = doc["document_id"]
        row = stored.get(doc_id)
        if row and row["algo"] == ALGO and int(row["anchor_count"]) == counts.get(doc_id, 0):
            signature = np.frombuffer(row["signature"], dtype=np.uint64) if row["signature"] is not None else None
            if signature is None or signature.shape == (NUM_PERM,):
                result[doc_id] = (int(row["word_count"]), signature)
                continue
        anchors = service.anchors(identity=identity, document_id=doc_id)["anchors"]
        words, signature = sketch(document_text(anchors))
        result[doc_id] = (words, signature)
        fresh.append((doc_id, case_id, len(anchors), ALGO, words, signature.tobytes() if signature is not None else None))
    if fresh:
        with ctx.db.transaction():
            for values in fresh:
                ctx.db.execute("INSERT OR REPLACE INTO lineage_sketch_492(document_id,case_id,anchor_count,algo,word_count,signature) "
                               "VALUES(?,?,?,?,?,?)", values)
    return result
