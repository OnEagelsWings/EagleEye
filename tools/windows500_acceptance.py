"""Build 500 Windows: real installed-runtime start, loopback health, restart and data continuity."""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

def _check(root,install,python):
    env=dict(os.environ, EAGLEEYE_DATA_DIR=str(root),
             EAGLEEYE_SETTINGS_DIR=str(root.parent/"config"),
             EAGLEEYE_BROWSER="none")
    command=[str(python),"-I","-m","eagleeye.bootstrap.desktop476",
             "--install-root",str(install),"--no-browser"]
    proc=subprocess.Popen(command,cwd=install,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                          text=True)
    try:
        runtime=root/"data"/"runtime_126_0"/"workspace.json"
        for i in range(150):
            if proc.poll() is not None:raise RuntimeError("Server exited before healthy: "+str(proc.returncode))
            if runtime.is_file():
                try:
                    body=json.loads(runtime.read_text(encoding="utf-8"))
                    port=int(body["port"])
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                            "http://127.0.0.1:"+str(port)+"/health",timeout=0.4) as response:
                        data=json.loads(response.read(16000))
                    if data.get("ok") and data.get("build")=="500.0":
                        return True
                except (OSError,ValueError,KeyError,TimeoutError):pass
            time.sleep(0.3)
        raise RuntimeError("Installed runtime did not become healthy")
    finally:
        # The desktop launcher may spawn the web server as a child process.
        # Killing only the launcher leaves that child holding eagleeye.db open
        # on Windows, preventing workspace cleanup and masking restart issues.
        if proc.poll() is None:
            tree = subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            if tree.returncode != 0 and proc.poll() is None:
                proc.kill()
        try:
            proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate(timeout=5)

def main():
    if os.name!="nt":raise SystemExit("Windows acceptance runs on Windows runner only")
    install=Path(__file__).resolve().parents[1]
    python=install/".eagleeye-runtime-500"/"Scripts"/"python.exe"
    if not python.is_file():raise RuntimeError("Installed runtime missing")
    with tempfile.TemporaryDirectory(prefix="eagleeye-500-smoke-") as td:
        root=Path(td)/"workspace";root.mkdir()
        if root.resolve().is_relative_to(install.resolve()):raise RuntimeError("Workspace not separated")
        assert _check(root,install,python)
        main_db=root/"data"/"eagleeye.db"
        if not main_db.is_file():raise RuntimeError("First start did not create case database")
        # Verify persisted database content, not merely that a database file exists.
        with sqlite3.connect(main_db) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS build500_acceptance_marker (value TEXT NOT NULL)")
            connection.execute("INSERT INTO build500_acceptance_marker(value) VALUES (?)", ("restart-preserved",))
            connection.commit()
        sentinel=root/"retention-test.txt";sentinel.write_text("test-case-data-unchanged",encoding="utf-8")
        checksum=hashlib.sha256(sentinel.read_bytes()).hexdigest()
        assert _check(root,install,python)
        assert main_db.is_file()
        with sqlite3.connect(main_db) as connection:
            persisted=connection.execute("SELECT value FROM build500_acceptance_marker").fetchall()
        if persisted != [("restart-preserved",)]:
            raise RuntimeError("Case database content was not preserved across restart")
        if hashlib.sha256(sentinel.read_bytes()).hexdigest()!=checksum:
            raise RuntimeError("Workspace data altered across restart")
        print("BUILD500 Windows installed runtime: health, restart, same external workspace PASS")

if __name__=="__main__":main()
