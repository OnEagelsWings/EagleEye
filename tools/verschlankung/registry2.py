"""Registry services requested by code (AST: attribute access or get/resolve('name')), per caller group."""
import ast, json, sys
from collections import defaultdict, deque
from pathlib import Path
SP = Path(sys.argv[1]); REPO = Path(".").resolve()
reg = json.load(open(SP / "registry.json"))["regs"]
static = json.load(open(SP / "static.json")); rt = json.load(open(SP / "runtime.json"))
crawl = json.load(open(SP / "crawl.json"))
loaded = set(rt["loaded"])
names = set(reg)
def requests(path):
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and n.attr in names:
            out.add(n.attr)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("get", "resolve", "service") \
                and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value in names:
            out.add(n.args[0].value)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "getattr" and len(n.args) > 1 \
                and isinstance(n.args[1], ast.Constant) and n.args[1].value in names:
            out.add(n.args[1].value)
    return out
by_module = {}
for m in loaded:
    if m in static and m != "eagleeye_pro.core.app_context":
        r = requests(REPO / static[m]["path"])
        if r: by_module[m] = r
# app_context itself outside the register lines (properties etc.)
ctx_src = (REPO / "eagleeye_pro/core/app_context.py").read_text(encoding="utf-8")
ctx_tree = ast.parse(ctx_src)
ctx_req = set()
for fn in ast.walk(ctx_tree):
    if isinstance(fn, (ast.FunctionDef,)) and fn.name != "build_service_registry":
        for n in ast.walk(fn):
            if isinstance(n, ast.Attribute) and n.attr in names: ctx_req.add(n.attr)
            if isinstance(n, ast.Constant) and n.value in names: ctx_req.add(n.value)
def closure(start):
    live = set(); q = deque(start)
    while q:
        n = q.popleft()
        if n in live or n not in reg: continue
        live.add(n); q.extend(reg[n]["deps"])
    return live
all_req = set().union(*by_module.values()) | ctx_req
print("Dienste registriert", len(reg))
print("von geladenem Code angefordert", len(all_req), "inkl. Abhaengigkeiten", len(closure(all_req)))
# requested only from route modules whose routes the user can reach?
route_mods_ui = {r["module"] for r in crawl["routes"] if r["link"] or r["form"]}
ui_req = set().union(*[v for m, v in by_module.items() if m in route_mods_ui]) if route_mods_ui else set()
print("app_context selbst fordert an", len(ctx_req))
json.dump({"by_module": {k: sorted(v) for k, v in by_module.items()}, "ctx_req": sorted(ctx_req),
           "live": sorted(closure(all_req)), "dead": sorted(set(reg) - closure(all_req))}, open(SP / "registry2.json", "w"), indent=1)
dead = set(reg) - closure(all_req)
print("nie angefordert", len(dead), sorted(dead)[:40])
