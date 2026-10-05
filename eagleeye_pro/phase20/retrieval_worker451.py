"""One request per process; never accepts a case, DB path, identity or GO token."""
import base64
import json
import os
from pathlib import Path
import sys

# Source-tree and installed-package layouts; neither path is taken from input.
root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root), str(root / "src")]

from eagleeye_pro.phase19.surface_retrieval441 import PinnedSurfaceTransport441
from eagleeye_pro.phase20.retrieval_isolation451 import validate_request451, worker_error_category451


def main():
    if sys.argv[1:] == ["--probe"]:
        sys.stdout.write(json.dumps({"protocol": "retrieval451.v1", "pid": os.getpid(),
                                    "external_network_contacted": False}))
        return
    if len(sys.argv) != 1:
        raise ValueError("unknown worker command")
    payload = sys.stdin.buffer.read(32_769)
    if len(payload) > 32_768:
        raise ValueError("request IPC budget exceeded")
    request = json.loads(payload)
    validate_request451(request)
    response = PinnedSurfaceTransport441().fetch(**request)
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
