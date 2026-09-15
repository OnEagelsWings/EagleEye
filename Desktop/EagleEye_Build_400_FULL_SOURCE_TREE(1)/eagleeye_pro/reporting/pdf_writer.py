from __future__ import annotations
from pathlib import Path
from typing import Iterable, List

def _escape_pdf(text: str) -> str:
    return (text or "").replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

def _wrap(text: str, width: int=92) -> List[str]:
    words = str(text or "").split()
    lines=[]; current=''
    for w in words:
        if len(current) + len(w) + 1 > width:
            lines.append(current); current=w
        else:
            current = (current + ' ' + w).strip()
    if current: lines.append(current)
    return lines or ['']

def write_pdf(path: str | Path, title: str, lines: Iterable[str]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    all_lines = [title, ""]
    for line in lines:
        all_lines.extend(_wrap(line))
    pages=[]; chunk=[]
    for line in all_lines:
        chunk.append(line)
        if len(chunk) >= 48:
            pages.append(chunk); chunk=[]
    if chunk: pages.append(chunk)
    objects=[]
    def add(obj: str) -> int:
        objects.append(obj); return len(objects)
    font_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids=[]
    contents=[]
    for page in pages:
        y = 790
        stream_parts=["BT", "/F1 10 Tf", "50 790 Td"]
        first=True
        for line in page:
            if first:
                stream_parts.append(f"({_escape_pdf(line)}) Tj")
                first=False
            else:
                stream_parts.append("0 -15 Td")
                stream_parts.append(f"({_escape_pdf(line)}) Tj")
        stream_parts.append("ET")
        stream='\n'.join(stream_parts)
        content_id = add(f"<< /Length {len(stream.encode('latin-1', errors='replace'))} >>\nstream\n{stream}\nendstream")
        contents.append(content_id)
        page_ids.append(add(f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"))
    kids=' '.join(f"{pid} 0 R" for pid in page_ids)
    pages_id = add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>")
    # patch page parent refs
    for pid in page_ids:
        objects[pid-1] = objects[pid-1].replace('/Parent 0 0 R', f'/Parent {pages_id} 0 R')
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")
    pdf = ["%PDF-1.4\n"]
    offsets=[]
    for i, obj in enumerate(objects, start=1):
        offsets.append(sum(len(part.encode('latin-1', errors='replace')) for part in pdf))
        pdf.append(f"{i} 0 obj\n{obj}\nendobj\n")
    xref_pos = sum(len(part.encode('latin-1', errors='replace')) for part in pdf)
    pdf.append(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n")
    for off in offsets:
        pdf.append(f"{off:010d} 00000 n \n")
    pdf.append(f"trailer\n<< /Size {len(objects)+1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF")
    path.write_bytes(''.join(pdf).encode('latin-1', errors='replace'))
    return path
