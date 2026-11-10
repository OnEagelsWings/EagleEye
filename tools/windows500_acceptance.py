"""Build 500 Windows: real installed-runtime start, loopback health, restart and data continuity."""
from __future__ import annotations
import ctypes
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

def _windows_job_for_process(proc):
    """Own the launcher and its descendants, including a detached web server."""
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.AssignProcessToJobObject(job, wintypes.HANDLE(int(proc._handle))):
        error = ctypes.get_last_error()
        kernel.CloseHandle(job)
        raise ctypes.WinError(error)
    return kernel, job


def _windows_descendant_pids(parent_pid):
    """Snapshot descendants before the launcher exits (taskkill /T then loses them)."""
    script = (
        "$p=Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId;"
        "$ids=@(" + str(int(parent_pid)) + ");$out=@();"
        "do {$found=@($p | Where-Object { $ids -contains [int]$_.ParentProcessId -and "
        "$out -notcontains [int]$_.ProcessId });"
        "$new=@($found | ForEach-Object {[int]$_.ProcessId});"
        "$out+= $new;$ids=$new} while ($ids.Count -gt 0);"
        "$out | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=12, check=True,
        )
        raw = result.stdout.strip()
        if not raw:
            return []
        value = json.loads(raw)
        return [int(pid) for pid in (value if isinstance(value, list) else [value])]
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print("Windows descendant discovery failed: " + str(exc), flush=True)
        return []


def _windows_port_owner_pid(port, install):
    """Identify only the installed EagleEye process listening on our health port."""
    import re
    netstat = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                             capture_output=True, text=True, timeout=12, check=True)
    candidates = set()
    for line in netstat.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
            if parts[1].rsplit(":", 1)[-1] == str(port):
                candidates.add(int(parts[4]))
    for pid in candidates:
        script = ("$p=Get-CimInstance Win32_Process -Filter 'ProcessId=" + str(pid) +
                  "'; if($p){$p.CommandLine}")
        result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                                 "-Command", script], capture_output=True,
                                text=True, timeout=12, check=True)
        command = result.stdout.strip().lower()
        if str(install.resolve()).lower() in command and "python" in command:
            return pid
    return None



def _windows_installed_runtime_pids(install):
    """Find lingering Python workers from this isolated CI installation only."""
    runtime = str((install / ".eagleeye-runtime-500").resolve()).lower().replace("'", "''")
    script = (
        "$root='" + runtime + "';"
        "Get-CimInstance Win32_Process | Where-Object {"
        " $_.ExecutablePath -and $_.ExecutablePath.ToLower().StartsWith($root + '\\')"
        "} | Select-Object -ExpandProperty ProcessId | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=12, check=True,
        )
        raw = result.stdout.strip()
        if not raw:
            return []
        ids = json.loads(raw)
        return [int(pid) for pid in (ids if isinstance(ids, list) else [ids])]
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print("Installed-runtime worker discovery failed: " + str(exc), flush=True)
        return []


def _check(root,install,python):
    env=dict(os.environ, EAGLEEYE_DATA_DIR=str(root),
             EAGLEEYE_SETTINGS_DIR=str(root.parent/"config"),
             EAGLEEYE_BROWSER="none")
    command=[str(python),"-I","-m","eagleeye.bootstrap.desktop476",
             "--install-root",str(install),"--no-browser"]
    proc=subprocess.Popen(command,cwd=install,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                          text=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
    job = None
    job_error = None
    descendant_pids = []
    server_pid = None
    try:
        if os.name == "nt":
            try:
                job = _windows_job_for_process(proc)
            except OSError as exc:
                # Hosted Windows runners may already place processes in a job
                # that rejects nested assignment. Preserve an explicit fallback.
                job_error = str(exc)
                print("Windows job assignment unavailable; using process-tree fallback: " + job_error, flush=True)
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
                        if os.name == "nt":
                            # A Windows job can miss a detached/breakaway server.
                            # Record the verified listener even when assignment succeeded.
                            descendant_pids = _windows_descendant_pids(proc.pid)
                            server_pid = _windows_port_owner_pid(port, install)
                            if server_pid is None:
                                raise RuntimeError("Cannot identify installed EagleEye server process on health port")
                        return True
                except (OSError,ValueError,KeyError,TimeoutError):pass
            time.sleep(0.3)
        raise RuntimeError("Installed runtime did not become healthy")
    finally:
        # The desktop launcher may spawn the web server as a child process.
        # Killing only the launcher leaves that child holding eagleeye.db open
        # on Windows, preventing workspace cleanup and masking restart issues.
        # First request a graceful Uvicorn shutdown: it closes SQLite pools,
        # worker threads and the workspace lock. Force termination is fallback.
        if proc.poll() is None and os.name == "nt":
            import signal
            try:
                proc.send_signal(signal.CTRL_BREAK_EVENT)
                proc.communicate(timeout=12)
            except (OSError, subprocess.TimeoutExpired):
                pass
        # The launcher can exit before its server child. Always terminate the
        # entire Windows job, even when proc.poll() already reports exit.
        if job is not None:
            kernel, handle = job
            try:
                if not kernel.TerminateJobObject(handle, 1):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                kernel.CloseHandle(handle)
        if os.name == "nt":
            # A detached server can escape the job; stop only PIDs identified
            # from this launcher or its verified installed-runtime listener.
            # The launcher may already have exited, so /T on its PID alone
            # cannot find an orphaned server. Stop the captured children too.
            for pid in reversed(list(dict.fromkeys(descendant_pids + ([server_pid] if server_pid else [])))):
                completed = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                           capture_output=True, text=True, timeout=20, check=False)
                print("Windows descendant stop " + str(pid) + ": " + str(completed.returncode), flush=True)
            if proc.poll() is None:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               capture_output=True, text=True, timeout=20, check=False)
        elif proc.poll() is None:
            proc.kill()
        try:
            proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate(timeout=5)
        if os.name == "nt":
            # Detached multiprocessing workers may no longer be descendants of
            # the desktop launcher or the health-port listener. The CI install
            # is unique: only terminate Python executables inside its private
            # venv, never a global Python process or another EagleEye install.
            for pid in _windows_installed_runtime_pids(install):
                completed = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True, text=True, timeout=20, check=False,
                )
                print("Isolated runtime worker stop " + str(pid) + ": "
                      + str(completed.returncode), flush=True)
        # Windows may release SQLite file handles after the launcher exits.
        # Do not proceed to restart or remove the temporary workspace until
        # the database is actually free of handles (including child servers).
        db = root / "data" / "eagleeye.db"
        if db.exists():
            deadline = time.monotonic() + 20
            while True:
                try:
                    probe = db.with_name(db.name + ".handle-probe")
                    db.rename(probe)
                    probe.rename(db)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Windows server retained SQLite database handle after stop") from exc
                    time.sleep(0.2)

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
