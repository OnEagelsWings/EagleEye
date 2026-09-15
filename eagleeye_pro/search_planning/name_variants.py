from __future__ import annotations

import itertools
import re
from typing import Iterable, List

GERMAN_NAME_VARIANTS = {
    "johann": ["Johann", "Johannes", "Hans"],
    "johannes": ["Johannes", "Johann", "Hans"],
    "hans": ["Hans", "Johann", "Johannes"],
    "josef": ["Josef", "Joseph"],
    "joseph": ["Joseph", "Josef"],
    "catharina": ["Catharina", "Katharina", "Katarina"],
    "katharina": ["Katharina", "Catharina", "Katarina", "Käthe"],
    "sara": ["Sara", "Sarah"],
    "sarah": ["Sarah", "Sara"],
    "maria": ["Maria", "Marie"],
}

SURNAME_VARIANTS = {
    "meyer": ["Meyer", "Meier", "Maier", "Mayer"],
    "meier": ["Meier", "Meyer", "Maier", "Mayer"],
    "levi": ["Levi", "Levy"],
    "levy": ["Levy", "Levi"],
    "cohen": ["Cohen", "Cohn", "Kohn"],
    "cohn": ["Cohn", "Cohen", "Kohn"],
    "kohn": ["Kohn", "Cohn", "Cohen"],
    "schmidt": ["Schmidt", "Schmitt", "Schmid"],
    "schmitt": ["Schmitt", "Schmidt", "Schmid"],
    "mueller": ["Mueller", "Müller"],
    "müller": ["Müller", "Mueller"],
}


def clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())


def split_name(name: str) -> tuple[list[str], str]:
    name = clean_name(name)
    if not name:
        return [], ""
    if "," in name:
        last, rest = [p.strip() for p in name.split(",", 1)]
        firsts = rest.split()
        return firsts, last
    parts = name.split()
    if len(parts) == 1:
        return [], parts[0]
    return parts[:-1], parts[-1]


def generate_name_variants(name: str, aliases: Iterable[str] | None = None, max_variants: int = 36) -> List[str]:
    raw = [clean_name(name)] + [clean_name(a) for a in (aliases or []) if clean_name(a)]
    variants: list[str] = []
    for base in raw:
        if not base:
            continue
        firsts, last = split_name(base)
        if not last:
            continue
        first_options: list[list[str]] = []
        for fn in firsts:
            first_options.append(GERMAN_NAME_VARIANTS.get(fn.lower(), [fn]))
        last_options = SURNAME_VARIANTS.get(last.lower(), [last])
        combos = list(itertools.product(*(first_options or [[]]), last_options))
        for combo in combos:
            if first_options:
                *fns, surname = combo
                full = " ".join([*fns, surname]).strip()
            else:
                full = combo[-1]
            variants.extend([full, f"{surname}, {' '.join(fns)}".strip() if first_options else surname])
            if first_options and fns:
                variants.append(f"{fns[0][0]}. {surname}")
                if len(fns) > 1:
                    variants.append(f"{fns[0]} {fns[-1]} {surname}")
        if firsts:
            variants.append(f"{firsts[0]} {last}")
            variants.append(f"{firsts[0][0]}. {last}")
    seen = set()
    out = []
    for v in variants:
        v = clean_name(v).strip(",")
        key = v.lower()
        if v and key not in seen:
            seen.add(key); out.append(v)
        if len(out) >= max_variants:
            break
    return out
