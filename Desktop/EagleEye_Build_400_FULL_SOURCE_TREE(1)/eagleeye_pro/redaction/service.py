from __future__ import annotations
import re
from typing import Dict

class RedactionService:
    EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s()./-]{6,}\d)(?!\w)")
    IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

    def redact_text(self, text: str, mode: str="client") -> str:
        if not text:
            return ""
        out = text
        out = self.EMAIL_RE.sub("[E-MAIL REDACTED]", out)
        out = self.PHONE_RE.sub("[PHONE REDACTED]", out)
        if mode in ("client", "public"):
            out = self.IP_RE.sub("[IP REDACTED]", out)
        return out

    def redaction_summary(self, text: str) -> Dict[str, int]:
        return {
            "emails": len(self.EMAIL_RE.findall(text or "")),
            "phones": len(self.PHONE_RE.findall(text or "")),
            "ips": len(self.IP_RE.findall(text or "")),
        }
