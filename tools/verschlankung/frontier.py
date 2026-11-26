"""Why is a statically reachable module never loaded? Classify the edges that reach it."""
import ast, json, sys
from collections import defaultdict, deque
from pathlib import Path
sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2] + "/static.json"]
SP = Path(sys.argv[2]).parent
exec(open(Path(__file__).with_name("graph.py")).read().split("\nproduct = reach")[0])  # modules, graph, resolve, with_parents, reach, PRODUCT_ENTRIES

def kinds_of(name, path, is_pkg):
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    pkg = name if is_pkg else name.rpartition(".")[0]
    out = defaultdict(set)
    def visit(node, func):
        for child in ast.iter_child_nodes(node):
            f = func
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                f = (func + "." if func else "") + getattr(child, "name", "<lambda>")
            targets = set()
            if isinstance(child, ast.Import):
                for a in child.names: targets |= resolve(a.name)
                kind = "lazy" if func else "top"
            elif isinstance(child, ast.ImportFrom):
                if child.level:
                    bp = pkg.split(".") if pkg else []
                    if child.level > 1: bp = bp[:len(bp) - (child.level - 1)]
                    base = ".".join(bp + ([child.module] if child.module else []))
                else:
                    base = child.module or ""
                targets |= resolve(base)
                for a in child.names:
                    full = base + "." + a.name
                    if full in modules: targets |= with_parents(full)
                kind = "lazy" if func else "top"
            elif isinstance(child, ast.Constant) and isinstance(child.value, str):
                s = child.value.strip()
                if s.startswith(TOPS) and STRING_RE.match(s): targets |= resolve(s.split(":")[0])
                kind = "string"
            for t in targets:
                if t != name: out[t].add((kind, f or "<modul>"))
            visit(child, f)
    visit(tree, "")
    return out

rt = json.load(open(SP / "runtime.json"))
loaded = set(rt["loaded"])
static = json.load(open(SP / "static.json"))
prod = {m for m, v in static.items() if v["cat"] == "produkt"}
notloaded = prod - loaded
# edges from loaded modules into not-loaded ones
frontier = defaultdict(list)
for m in loaded:
    if m not in modules: continue
    for t, ks in kinds_of(m, modules[m], m in packages).items():
        if t in notloaded:
            for k in ks: frontier[t].append((m, k[0], k[1]))
direct_lazy = {t for t, es in frontier.items() if any(k == "lazy" for _, k, _ in es)}
direct_string_only = {t for t, es in frontier.items() if all(k == "string" for _, k, _ in es)}
direct_top = {t for t, es in frontier.items() if any(k == "top" for _, k, _ in es)}
# closure: modules reachable from lazy frontier vs only via string frontier
def closure(starts):
    seen, q = set(starts), deque(starts)
    while q:
        c = q.popleft()
        for n in graph.get(c, ()):
            if n in notloaded and n not in seen: seen.add(n); q.append(n)
    return seen
lazy_cl = closure(direct_lazy | direct_top)
string_cl = closure(direct_string_only) - lazy_cl
rest = notloaded - lazy_cl - string_cl
lines = lambda s: sum(static[m]["lines"] for m in s)
print("geladen", len(loaded & set(static)), lines(loaded & set(static)))
print("statisch-produkt nicht geladen", len(notloaded), lines(notloaded))
print("  ueber Bedarfs-Import erreichbar", len(lazy_cl), lines(lazy_cl), "(direkt:", len(direct_lazy), ", top-level aber nicht geladen:", len(direct_top), ")")
print("  nur ueber Text-Verweise erreichbar", len(string_cl), lines(string_cl))
print("  sonst", len(rest), lines(rest))
json.dump({"lazy": sorted(lazy_cl), "string": sorted(string_cl), "rest": sorted(rest),
           "frontier": {t: es for t, es in frontier.items()}}, open(SP / "frontier.json", "w"), indent=1)
