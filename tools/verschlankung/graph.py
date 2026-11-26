"""Verschlankungsanalyse, Schritt 1. Static import graph of the EagleEye repository (all imports, also inside functions, plus module-name strings)."""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()

# package roots: directory that contains the top-level package
ROOTS = {
    "eagleeye": REPO / "src",
    "eagleeye_pro": REPO,
    "personosint": REPO / "PersonOSINT",
}


def module_name(path: Path, base: Path) -> str:
    rel = path.relative_to(base).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


modules: dict[str, Path] = {}
for top, base in ROOTS.items():
    for p in (base / top).rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        modules[module_name(p, base)] = p
packages = {m for m, p in modules.items() if p.name == "__init__.py"}

# script-like files (not importable as package modules): entry scripts, tests, tools
scripts: dict[str, Path] = {}
for p in list(REPO.glob("*.py")) + list((REPO / "tools").rglob("*.py")) + list((REPO / "tests").rglob("*.py")) \
        + list((REPO / "PersonOSINT" / "tests").rglob("*.py")) + list((REPO / "alembic_104_1").rglob("*.py")) \
        + list((REPO / "eval").rglob("*.py")):
    if "__pycache__" in p.parts or "verschlankung" in p.parts:  # the analysis itself is no consumer
        continue
    scripts["file:" + str(p.relative_to(REPO))] = p

STRING_RE = re.compile(r"^[A-Za-z_][\w]*(\.[A-Za-z_]\w*)+(:[A-Za-z_]\w*)?$")
TOPS = tuple(t + "." for t in ROOTS) + tuple(ROOTS)


def with_parents(name: str) -> set[str]:
    out = set()
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        cand = ".".join(parts[:i])
        if cand in modules:
            out.add(cand)
    return out


def resolve(target: str) -> set[str]:
    """A dotted name -> the longest existing module plus its parent packages."""
    parts = target.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in modules:
            return with_parents(cand)
    return set()


def edges_of(name: str, path: Path, is_pkg: bool) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    out: set[str] = set()
    pkg = name if is_pkg else name.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out |= resolve(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = pkg.split(".") if pkg else []
                if node.level > 1:
                    base_parts = base_parts[: len(base_parts) - (node.level - 1)]
                base = ".".join(base_parts + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            out |= resolve(base)
            for a in node.names:
                if a.name != "*":
                    full = base + "." + a.name if base else a.name
                    if full in modules:
                        out |= with_parents(full)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value.strip()
            if s.startswith(TOPS) and STRING_RE.match(s):
                out |= resolve(s.split(":")[0])
    out.discard(name)
    return out


graph: dict[str, set[str]] = {}
for m, p in modules.items():
    graph[m] = edges_of(m, p, m in packages)
for s, p in scripts.items():
    graph[s] = edges_of(s, p, False)
    # scripts in tools/research_exchange and tools/analysis import siblings by bare name; not package modules


def reach(starts) -> set[str]:
    seen, queue = set(), deque()
    for s in starts:
        for m in ([s] if s.startswith("file:") else with_parents(s) or [s]):
            if m not in seen:
                seen.add(m)
                queue.append(m)
    while queue:
        cur = queue.popleft()
        for nxt in graph.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


PRODUCT_ENTRIES = [
    "eagleeye.bootstrap.desktop476",        # START_EAGLEEYE_PRO.bat (Menü 3), Diagnose/Datenordner .bat
    "eagleeye.bootstrap.windows_start",     # Startmenü des Windows-Installers
    "eagleeye.interfaces.web.server",
    "eagleeye.interfaces.cli.main",         # console script "eagleeye"
    "personosint.__main__",                 # Menü 1, 2, V, Quellenprüfung
    "personosint",
    "file:tools/quellen_pruefen_fallakte.py",
    "file:INSTALL_EAGLEEYE_500.py",
]
product = reach(PRODUCT_ENTRIES)
tests = reach([s for s in scripts if s.startswith(("file:tests/", "file:PersonOSINT/tests/"))])
tools_other = reach([s for s in scripts if s.startswith("file:tools/") or (s.count("/") == 0)])

lines = {m: sum(1 for _ in p.open(encoding="utf-8", errors="replace")) for m, p in modules.items()}
result = {}
for m in modules:
    if m in product:
        cat = "produkt"
    elif m in tests:
        cat = "nur_tests"
    elif m in tools_other:
        cat = "nur_altwerkzeuge"
    else:
        cat = "unerreichbar"
    result[m] = {"cat": cat, "lines": lines[m], "path": str(modules[m].relative_to(REPO))}

OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
summary = defaultdict(lambda: [0, 0])
for v in result.values():
    summary[v["cat"]][0] += 1
    summary[v["cat"]][1] += v["lines"]
for k, (n, l) in sorted(summary.items()):
    print(f"{k:20s} {n:5d} Module {l:7d} Zeilen")

if __name__ == "__main__" and len(sys.argv) > 3:
    for e in PRODUCT_ENTRIES:
        r = reach([e])
        per = defaultdict(int)
        for m in r:
            if m in modules: per[m.split(".")[0]] += 1
        print(e, dict(per))
