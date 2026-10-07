"""Check the installed wheel's worker, outside the checkout, without network."""
from pathlib import Path
import argparse
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel-dir", required=True)
    args = parser.parse_args()
    wheels = list(Path(args.wheel_dir).resolve().glob("eagleeye_personosint_pro-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("exactly one EagleEye wheel required")
    with tempfile.TemporaryDirectory(prefix="eagleeye-wheel451-") as directory:
        target = Path(directory) / "installed"
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps",
                        "--no-compile", "--target", str(target), str(wheels[0])], check=True)
        code = '''
import json, sys
from pathlib import Path
target = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(target))
from eagleeye_pro.phase20 import retrieval_isolation451 as isolation
assert Path(isolation.__file__).is_relative_to(target)
report = isolation.ProcessSurfaceTransport451().probe()
assert report["external_network_contacted"] is False
assert report["protocol"] == "retrieval451.v1"
print(json.dumps({"wheel_worker_startup": "PASS", "external_network_contacted": False}))
'''
        subprocess.run([sys.executable, "-I", "-c", code, str(target)],
                       cwd=directory, check=True, timeout=20)


if __name__ == "__main__":
    main()
