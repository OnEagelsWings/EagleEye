"""One request per process; never accepts a case, DB path, identity or GO token."""
import base64
import json
import os
from pathlib import Path
import sys
import http.client
import socket
import ssl
import time


# Source-tree and installed-package layouts; neither path is taken from input.
root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root), str(root / "src")]

from eagleeye.crawler.engine import FetchResponse, USER_AGENT
from eagleeye_pro.phase20.containment451 import confine_worker451

from eagleeye_pro.phase19.surface_retrieval441 import PinnedSurfaceTransport441
from eagleeye_pro.phase20.retrieval_isolation451 import validate_request451, worker_error_category451


def contained_fetch451(request, fd):
    from urllib.parse import urlsplit
    parsed = urlsplit(request["url"])
    import resource
    import encodings.idna
    context = ssl.create_default_context()  # load trust before denying file reads
    resource.setrlimit(resource.RLIMIT_CPU, (request["timeout_seconds"] + 5,) * 2)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    wire = socket.socket(fileno=fd)
    wire.settimeout(request["timeout_seconds"])
    confine_worker451()
    started = time.monotonic()
    if parsed.scheme == "https":
        wire = context.wrap_socket(wire, server_hostname=parsed.hostname)
    connection = http.client.HTTPConnection(parsed.hostname)
    connection.sock = wire
    try:
        target = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")
        headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity", "Connection": "close"}
        headers.update(request["headers"])
        connection.request("GET", target, headers=headers)
        response = connection.getresponse()
        body = response.read(request["max_bytes"] + 1)
        if len(body) > request["max_bytes"]:
            raise ValueError("response exceeds byte budget")
        return FetchResponse(request["url"], response.status,
                             dict(response.getheaders()), body,
                             int((time.monotonic() - started) * 1000))
    finally:
        connection.close()


def containment_probe451():
    # No source traffic; exercise real kernel denials inside this child only.
    import subprocess
    report = confine_worker451()
    denied = {}
    for name, action in {
        "file_read": lambda: open("/etc/passwd", "rb"),
        "file_write": lambda: open("probe451-write", "wb"),
        "new_socket": lambda: socket.socket(),
        "new_process": lambda: subprocess.run([sys.executable, "-V"]),
    }.items():
        try:
            result = action()
            if hasattr(result, "close"):
                result.close()
            denied[name] = False
        except PermissionError:
            denied[name] = True
    if not all(denied.values()):
        raise RuntimeError("containment denial probe failed")
    return {**report, "denied": denied, "external_network_contacted": False}


def main():
    if sys.argv[1:] == ["--probe"]:
        sys.stdout.write(json.dumps({"protocol": "retrieval451.v1", "pid": os.getpid(),
                                    "external_network_contacted": False}))
        return
    if sys.argv[1:] == ["--containment-probe"]:
        sys.stdout.write(json.dumps(containment_probe451()))
        return
    contained = len(sys.argv) == 3 and sys.argv[1] == "--connected-fd"
    if len(sys.argv) != 1 and not contained:
        raise ValueError("unknown worker command")
    payload = sys.stdin.buffer.read(32_769)
    if len(payload) > 32_768:
        raise ValueError("request IPC budget exceeded")
    request = json.loads(payload)
    validate_request451(request)
    response = (contained_fetch451(request, int(sys.argv[2])) if contained
                else PinnedSurfaceTransport441().fetch(**request))
    result = {"url": response.url, "status": response.status,
              "headers": dict(response.headers), "elapsed_ms": response.elapsed_ms,
              "body": base64.b64encode(response.body).decode("ascii")}
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Fixed category only; no upstream content/credentials/exception text.
        sys.stdout.write(json.dumps({"error": worker_error_category451(exc)}))
        sys.exit(1)
