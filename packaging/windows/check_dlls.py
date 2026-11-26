"""Check that the installed runtime is complete: every DLL that a shipped .exe/.dll/.pyd imports is either in
the program folder or a fixed part of Windows. Something only an optional install provides (Visual C++
Redistributable, another Python) counts as missing, because a fresh office PC may not have it.

    python check_dlls.py "C:\\Program Files\\EagleEye\\runtime"
"""
from __future__ import annotations

import os
import re
import struct
import sys
from pathlib import Path

# Installed separately on Windows (Visual C++ Redistributable), so they must be shipped app-local.
REDIST = re.compile(r"^(msvcp140.*|vcruntime140.*|concrt140|vcomp140|vccorlib140|mfc140.*|vcamp140)\.dll$", re.I)


def imports(path: Path) -> list[str]:
    """Names from the PE import directory (load-time dependencies; delay imports are optional by design)."""
    data = path.read_bytes()
    if data[:2] != b"MZ":
        return []
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        return []
    sections_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    directories = optional + (112 if magic == 0x20B else 96)
    import_rva = struct.unpack_from("<I", data, directories + 8)[0]
    if not import_rva:
        return []
    sections = []
    table = optional + optional_size
    for i in range(sections_count):
        vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, table + 40 * i + 8)
        sections.append((vaddr, max(vsize, rsize), raddr))

    def offset(rva: int) -> int:
        for vaddr, size, raddr in sections:
            if vaddr <= rva < vaddr + size:
                return rva - vaddr + raddr
        raise ValueError("RVA outside sections")

    names, pos = [], offset(import_rva)
    while True:
        entry = struct.unpack_from("<IIIII", data, pos)
        if not any(entry):
            break
        start = offset(entry[3])
        names.append(data[start:data.index(b"\0", start)].decode("ascii", "replace"))
        pos += 20
    return names


def check(runtime: Path, system32: Path | None = None) -> list[str]:
    system32 = system32 or Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    shipped = {}
    for item in runtime.rglob("*"):
        if item.suffix.lower() in (".dll", ".pyd", ".exe") and item.is_file():
            shipped.setdefault(item.name.lower(), []).append(item)
    problems = []
    for name, items in sorted(shipped.items()):
        for item in items:
            try:
                needed = imports(item)
            except (ValueError, struct.error) as exc:
                problems.append(f"{item.relative_to(runtime)}: nicht lesbar ({exc})")
                continue
            for dep in needed:
                low = dep.lower()
                if low.startswith(("api-ms-win-", "ext-ms-")) or low in shipped:
                    continue  # Windows API sets, or shipped in the program folder
                if REDIST.match(dep):
                    problems.append(f"{item.relative_to(runtime)} braucht {dep}: nur mit Visual C++ Redistributable vorhanden")
                elif not (system32 / dep).exists():
                    problems.append(f"{item.relative_to(runtime)} braucht {dep}: weder im Paket noch in Windows")
    return problems


def main(argv: list[str] | None = None) -> int:
    runtime = Path((argv or sys.argv[1:])[0])
    problems = check(runtime)
    files = sum(1 for p in runtime.rglob("*") if p.suffix.lower() in (".dll", ".pyd", ".exe"))
    if problems:
        print("\n".join(problems))
        print(f"{len(problems)} fehlende Abhängigkeiten in {files} Programmdateien")
        return 1
    print(f"Alle {files} Programmdateien finden ihre Abhängigkeiten im Paket oder in Windows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
