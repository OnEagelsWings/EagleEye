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
    # A Windows venv launcher may resolve to the base interpreter in CIM.
    # Match the exact private python.exe command prefix as well as its image
    # path; never match a generic install directory or unrelated Python.
    runtime_path = (install / ".eagleeye-runtime-500").resolve()
    runtime = str(runtime_path).lower().replace("'", "''")
    interpreter = str(runtime_path / "Scripts" / "python.exe").lower().replace("'", "''")
    script = (
        "$root='" + runtime + "';$py='" + interpreter + "';"
        "Get-CimInstance Win32_Process | Where-Object {"
        " $exe=([string]$_.ExecutablePath).ToLower();"
        " $cmd=([string]$_.CommandLine).TrimStart().ToLower();"
        " ($exe.StartsWith($root + '\\')) -or"
        " ($cmd -eq $py) -or ($cmd -eq (([char]34) + $py + ([char]34))) -or"
        " ($cmd.StartsWith(([char]34) + $py + ([char]34) + ' ') -or"
        "  $cmd.StartsWith($py + ' '))"
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


def _windows_workspace_workers(root, install):
    """Find only Python processes whose command explicitly names this test workspace.

    This catches workers detached from both launcher and listener trees. Require
    a Python executable as well as both workspace and runtime identity: the
    PowerShell discovery command itself contains these strings and must never
    be selected for termination.
    """
    workspace = str(root.resolve()).lower().replace("'", "''")
    runtime = str((install / ".eagleeye-runtime-500").resolve()).lower().replace("'", "''")
    script = (
        "$ws='" + workspace + "';$rt='" + runtime + "';"
        "Get-CimInstance Win32_Process | Where-Object {"
        " $cmd=([string]$_.CommandLine).ToLower();"
        " $exe=([string]$_.ExecutablePath).ToLower();"
        " $isPython=($exe.EndsWith('\\python.exe') -or $exe.EndsWith('\\pythonw.exe'));"
        " $isPython -and $cmd.Contains($ws) -and"
        " ($cmd.Contains($rt) -or $exe.StartsWith($rt + '\\'))"
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
        value = json.loads(raw)
        return [int(pid) for pid in (value if isinstance(value, list) else [value])]
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print("Workspace worker discovery failed: " + str(exc), flush=True)
        return []



def _windows_sqlite_lock_owners(db):
    """Ask Windows Restart Manager which processes hold the exact SQLite file."""
    if os.name != "nt":
        return []
    from ctypes import wintypes
    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD),
                    ("dwHighDateTime", wintypes.DWORD)]
    class UNIQUE_PROCESS(ctypes.Structure):
        _fields_ = [("dwProcessId", wintypes.DWORD),
                    ("ProcessStartTime", FILETIME)]
    class PROCESS_INFO(ctypes.Structure):
        _fields_ = [("Process", UNIQUE_PROCESS),
                    ("strAppName", wintypes.WCHAR * 256),
                    ("strServiceShortName", wintypes.WCHAR * 64),
                    ("ApplicationType", wintypes.DWORD),
                    ("AppStatus", wintypes.ULONG),
                    ("TSSessionId", wintypes.DWORD),
                    ("bRestartable", wintypes.BOOL)]
    manager = ctypes.WinDLL("Rstrtmgr", use_last_error=True)
    manager.RmStartSession.argtypes = [
        ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, wintypes.LPWSTR]
    manager.RmRegisterResources.argtypes = [
        wintypes.DWORD, wintypes.UINT, ctypes.POINTER(wintypes.LPCWSTR),
        wintypes.UINT, ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p]
    manager.RmGetList.argtypes = [
        wintypes.DWORD, ctypes.POINTER(wintypes.UINT),
        ctypes.POINTER(wintypes.UINT), ctypes.POINTER(PROCESS_INFO),
        ctypes.POINTER(wintypes.DWORD)]
    manager.RmEndSession.argtypes = [wintypes.DWORD]
    session = wintypes.DWORD()
    key = ctypes.create_unicode_buffer(33)
    status = manager.RmStartSession(ctypes.byref(session), 0, key)
    if status:
        return [{"restart_manager_error": int(status)}]
    try:
        resources = (wintypes.LPCWSTR * 1)(str(db.resolve()))
        status = manager.RmRegisterResources(session, 1, resources, 0, None, 0, None)
        if status:
            return [{"register_error": int(status)}]
        needed = wintypes.UINT()
        count = wintypes.UINT()
        reboot = wintypes.DWORD()
        status = manager.RmGetList(session, ctypes.byref(needed),
                                   ctypes.byref(count), None, ctypes.byref(reboot))
        if status not in (0, 234):  # ERROR_MORE_DATA
            return [{"list_error": int(status)}]
        if not needed.value:
            return []
        entries = (PROCESS_INFO * needed.value)()
        count.value = needed.value
        status = manager.RmGetList(session, ctypes.byref(needed),
                                   ctypes.byref(count), entries, ctypes.byref(reboot))
        if status:
            return [{"list_error": int(status)}]
        return [{"pid": int(item.Process.dwProcessId), "application": item.strAppName}
                for item in entries[:count.value]]
    finally:
        manager.RmEndSession(session)

def _check(root,install,python):
    env=dict(os.environ, EAGLEEYE_DATA_DIR=str(root),
             EAGLEEYE_SETTINGS_DIR=str(root.parent/"config"),
             EAGLEEYE_BROWSER="none")
    command=[str(python),"-I","-m","eagleeye.bootstrap.desktop476",
             "--install-root",str(install),"--no-browser"]
    # A PIPE can fill during a verbose first start and deadlock the launcher.
    # Keep the output in a private file so health polling and shutdown progress.
    log = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    proc=subprocess.Popen(command,cwd=install,env=env,stdout=log,stderr=subprocess.STDOUT,
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
        # Stop the *verified* loopback listener and its subprocess tree before
        # terminating the launcher job. A detached server may have workers
        # outside that job; killing the launcher first can orphan them and
        # leave the SQLite handle open on Windows.
        if os.name == "nt" and server_pid is not None:
            completed = subprocess.run(
                ["taskkill", "/PID", str(server_pid), "/T", "/F"],
                capture_output=True, text=True, timeout=20, check=False,
            )
            print("Verified server tree stop " + str(server_pid) + ": "
                  + str(completed.returncode), flush=True)
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
        if os.name == "nt":
            # A server worker can escape the launcher's job and lose its
            # original parent. Restrict this final cleanup to processes that
            # explicitly identify BOTH this disposable workspace and runtime.
            for pid in _windows_workspace_workers(root, install):
                completed = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True, text=True, timeout=20, check=False,
                )
                print("Verified workspace worker stop " + str(pid) + ": "
                      + str(completed.returncode), flush=True)
        # The acceptance process must not retain a SQLite connection of its own.
        # Collect any finalized connection wrappers before testing exclusive access;
        # this does not weaken the lock assertion or touch unrelated processes.
        import gc
        gc.collect()
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
                        log.seek(0)
                        print("Installed launcher output (last 12000 chars): " + log.read()[-12000:], flush=True)
                        # Capture a bounded process inventory to identify an
                        # escaped worker without terminating unrelated processes.
                        try:
                            snapshot = subprocess.run(
                                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                 "Get-CimInstance Win32_Process | Where-Object {"
                                 " $_.Name -match 'python|eagleeye' } |"
                                 " Select-Object ProcessId,ParentProcessId,Name,CommandLine |"
                                 " ConvertTo-Json -Compress"],
                                capture_output=True, text=True, timeout=12, check=False,
                            )
                            print("Windows Python process snapshot: " + snapshot.stdout[-8000:], flush=True)
                            print("SQLite lock owners (Restart Manager): " +
                                  json.dumps(_windows_sqlite_lock_owners(db)), flush=True)
                        except (OSError, subprocess.SubprocessError) as diagnostic_error:
                            print("Windows lock diagnostics unavailable: " + str(diagnostic_error), flush=True)
                        raise RuntimeError("Windows server retained SQLite database handle after stop") from exc
                    time.sleep(0.2)
        log.close()

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
