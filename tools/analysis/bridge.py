"""EagleEye loopback interface for the local analysis tools."""
import argparse
import hmac
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from engine import analyze, capabilities, OUT

PORT = 48137
HOST = f"127.0.0.1:{PORT}"
ORIGIN = "http://" + HOST
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, data, mime="application/json"):
        raw = json.dumps(data, ensure_ascii=False).encode() if mime=="application/json" else data
        self.send_response(status)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.headers.get("Host") != HOST: return self.reply(403, {})
        if self.path == "/":
            html = Path(__file__).with_name("local.html").read_text(encoding="utf-8")
            return self.reply(200, html.replace("{{token}}", TOKEN).encode(), "text/html")
        if self.path == "/status": return self.reply(200, capabilities())
        return self.reply(404, {})

    def do_POST(self):
        if self.headers.get("Host") != HOST or self.headers.get("Origin") != ORIGIN or not hmac.compare_digest(self.headers.get("X-Local-Key",""),TOKEN):
            return self.reply(403, {"error":"Lokale Sitzung erforderlich."})
        if self.path != "/run": return self.reply(404, {})
        if not LOCK.acquire(False): return self.reply(409, {"error":"Eine Analyse läuft bereits."})
        try:
            n = int(self.headers.get("Content-Length","0"))
            if not 0<n<=48000: raise ValueError("Ungültige Anfragegröße.")
            req = json.loads(self.rfile.read(n))
            report = analyze(req["caseId"],req["tool"],req["paths"],req["query"],req["offset"])
            self.reply(200, {"report":report,"folder":str(OUT / report["id"])})
        except Exception as exc:
            self.reply(400, {"error":str(exc)})
        finally: LOCK.release()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT),Handler)
    except OSError:
        if not args.no_browser: webbrowser.open(ORIGIN)
        raise SystemExit("Port 48137 bereits belegt.")
    if not args.no_browser: webbrowser.open(ORIGIN)
    print("EagleEye Analyse: "+ORIGIN,flush=True)
    server.serve_forever()
