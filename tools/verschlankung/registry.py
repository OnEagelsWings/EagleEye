"""Which registry services can live code actually ask for?"""
import json, re, sys
from collections import deque
from pathlib import Path
SP = Path(sys.argv[1]); REPO = Path(".").resolve()
text = (REPO / "eagleeye_pro/core/app_context.py").read_text(encoding="utf-8")
regs = {}
for line in text.splitlines():
    m = re.search(r"registry\.register\('(\w+)',(.*)", line)
    if not m: continue
    name, rest = m.group(1), m.group(2)
    paths = re.findall(r"'((?:eagleeye|eagleeye_pro|personosint)\.[\w.]+:\w+)'", rest)
    deps = set(re.findall(r"\.get\('(\w+)'\)", rest))
    regs[name] = {"paths": sorted(set(paths)), "deps": sorted(deps)}
print("registrierte Dienste", len(regs))
static = json.load(open(SP / "static.json")); rt = json.load(open(SP / "runtime.json"))
loaded = set(rt["loaded"])
# sources of loaded modules, without the registration file itself
names = set(regs)
used = set()
pat = re.compile(r"(?:\.|\bget\(\s*['\"]|getattr\(\s*\w+\s*,\s*['\"]|['\"])(" + "|".join(sorted(names, key=len, reverse=True)) + r")\b")
for m in loaded:
    if m not in static or m == "eagleeye_pro.core.app_context": continue
    src = (REPO / static[m]["path"]).read_text(encoding="utf-8", errors="replace")
    for hit in pat.findall(src): used.add(hit)
# also inside app_context, outside register lines (e.g. eager access in AppContext methods)
for line in text.splitlines():
    if "registry.register(" in line: continue
    for hit in pat.findall(line): used.add(hit)
live = set(); q = deque(used)
while q:
    n = q.popleft()
    if n in live or n not in regs: continue
    live.add(n); q.extend(regs[n]["deps"])
print("von geladenem Code angefragt (direkt)", len(used & names), "inkl. Abhaengigkeiten", len(live))
json.dump({"regs": regs, "live": sorted(live), "used": sorted(used & names)}, open(SP / "registry.json", "w"), indent=1)
