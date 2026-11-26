import json, sys
from collections import deque, defaultdict
from pathlib import Path
SP = Path(sys.argv[2])
sys.argv = [sys.argv[0], sys.argv[1], str(SP / "static.json")]
exec(open(Path(__file__).with_name("graph.py")).read().split("\nproduct = reach")[0])
static = json.load(open(SP / "static.json")); rt = json.load(open(SP / "runtime.json"))
fr = json.load(open(SP / "frontier.json")); r2 = json.load(open(SP / "registry2.json"))
reg = json.load(open(SP / "registry.json"))["regs"]
loaded = set(rt["loaded"]) & set(static)
start = set(loaded) | set(fr["lazy"])
for name in r2["live"]:
    for p in reg[name]["paths"]:
        start |= resolve(p.split(":")[0])
SKIP = {"eagleeye_pro.core.app_context"}
seen, q = set(start), deque(start)
while q:
    c = q.popleft()
    if c in SKIP: continue
    for n in graph.get(c, ()):
        if n in modules and n not in seen:
            seen.add(n); q.append(n)
# edges from app_context only for live services were added above; anything else from app_context is dead
cats = {}
for m, v in static.items():
    if v["cat"] == "unerreichbar": cats[m] = "A_unerreichbar"
    elif v["cat"] == "nur_tests": cats[m] = "B_nur_tests"
    elif m in loaded: cats[m] = "D_geladen"
    elif m in seen: cats[m] = "C2_bei_bedarf"
    else: cats[m] = "C1_nur_registriert_nie_angefordert"
tot = defaultdict(lambda: [0, 0])
for m, c in cats.items():
    tot[c][0] += 1; tot[c][1] += static[m]["lines"]
for c in sorted(tot): print(f"{c:40s} {tot[c][0]:5d} Module {tot[c][1]:7d} Zeilen")
json.dump(cats, open(SP / "classes.json", "w"), indent=0)
