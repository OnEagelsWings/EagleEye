"""Desktop startup with a stable work directory and credential-free diagnostics."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import threading
import tempfile
import time
from contextlib import contextmanager
from .runtime_lock import workspace_runtime_lock
from eagleeye_pro.version import BUILD
from .paths import default_runtime_root

_STATUS_LOCK=threading.Lock()
_SETTINGS_LOCK=threading.Lock()


def settings_directory():
    configured=os.environ.get('EAGLEEYE_SETTINGS_DIR')
    if configured:return Path(configured).expanduser().resolve()
    if os.name=='nt':return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'EagleEye'
    return Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'EagleEye'


def _local_path(value):
    text=str(value).strip()
    if not text or text.startswith(('\\\\','//')):
        raise ValueError('Bitte einen lokalen Arbeitsordner auswählen.')
    return Path(text).expanduser().resolve()


def _atomic_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
            prefix=path.name+'.',suffix='.tmp',delete=False) as handle:
        temp=Path(handle.name)
        handle.write(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    try:
        try:temp.chmod(0o600)
        except OSError:pass
        for attempt in range(6):
            try:
                temp.replace(path)
                break
            except PermissionError:
                if attempt==5:raise
                time.sleep(.025*(attempt+1))
    finally:temp.unlink(missing_ok=True)


@contextmanager
def _settings_guard():
    directory=settings_directory()
    with _SETTINGS_LOCK:
        with workspace_runtime_lock(directory,timeout=5):
            yield directory


def remember_workspace(path):
    root=_local_path(path);root.mkdir(parents=True,exist_ok=True)
    with _settings_guard() as directory:
        _atomic_json(directory/'workspace.json',{'workspace_directory':str(root)})
    return root


def resolve_workspace(install_dir):
    with _settings_guard() as directory:
        explicit=os.environ.get('EAGLEEYE_DATA_DIR')
        settings=directory/'workspace.json'
        if explicit:
            root=_local_path(explicit)
        elif settings.is_file():
            saved=json.loads(settings.read_text(encoding='utf-8'))
            root=_local_path(saved['workspace_directory'])
            if not root.is_dir():raise ValueError('Der gespeicherte Arbeitsordner fehlt. Bitte Datenordner auswählen.')
            return root
        else:
            installed=_local_path(install_dir)
            candidates=[candidate for candidate in (installed,default_runtime_root())
                if any((candidate/'data'/name).is_file() for name in ('eagleeye.db','eagleeye_pro_95_0.db'))]
            root=candidates[0] if candidates else directory/'workspace'
        root.mkdir(parents=True,exist_ok=True)
        _atomic_json(settings,{'workspace_directory':str(root)})
        return root


def write_start_status(root,stage,**details):
    allowed={k:v for k,v in details.items() if k in {'browser','error_type','port'}}
    with _STATUS_LOCK:
        _atomic_json(Path(root)/'data/runtime_126_0/start-status.json',
            {'build':BUILD,'stage':stage,'updated_at':datetime.now(timezone.utc).isoformat(),**allowed})


def diagnostics(root):
    from eagleeye.interfaces.web.server import _read_running_workspace
    root=_local_path(root);runtime=_read_running_workspace(root,accept_other_build=True)
    status_path=root/'data/runtime_126_0/start-status.json'
    try:status=json.loads(status_path.read_text(encoding='utf-8'))
    except (OSError,ValueError):status={'stage':'unknown'}
    return {'build':BUILD,'workspace_directory':str(root),'database_present':any((root/'data'/n).is_file() for n in ('eagleeye.db','eagleeye_pro_95_0.db')),
        'server_reachable':bool(runtime and runtime['build']==BUILD),'running_build':runtime['build'] if runtime else None,
        'version_conflict':bool(runtime and runtime['build']!=BUILD),'port':runtime['port'] if runtime else None,
        'last_start':{k:status[k] for k in ('stage','updated_at','browser','error_type') if k in status},
        'contains_credentials':False}


def choose_workspace():
    import tkinter
    from tkinter import filedialog
    window=tkinter.Tk();window.withdraw()
    try:
        selected=filedialog.askdirectory(title='EagleEye: bisherigen oder neuen Arbeitsordner wählen')
    finally:window.destroy()
    return remember_workspace(selected) if selected else None


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-root',required=True)
    parser.add_argument('--choose-workspace',action='store_true')
    parser.add_argument('--diagnose',action='store_true')
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args(argv)
    root=None
    try:
        root=choose_workspace() if args.choose_workspace else resolve_workspace(args.install_root)
        if root is None:return 0
        print('EagleEye '+BUILD+' | Arbeitsordner: '+str(root),flush=True)
        if args.diagnose:
            report=diagnostics(root)
            path=root/'data/runtime_126_0/start-diagnose.json';_atomic_json(path,report)
            print(json.dumps(report,ensure_ascii=False,indent=2));print('Diagnose: '+str(path))
            return 0
        from eagleeye.interfaces.web.server import serve_workspace
        return serve_workspace(base_dir=root,browser=os.environ.get('EAGLEEYE_BROWSER','firefox'),open_browser=not args.no_browser)
    except Exception as exc:
        if root is not None:
            try:write_start_status(root,'start-failed',error_type=type(exc).__name__)
            except OSError:pass
        print('EagleEye konnte nicht starten ('+type(exc).__name__+').',flush=True)
        if root is not None:
            try:
                if diagnostics(root)['version_conflict']:
                    print('Ein älteres EagleEye läuft in diesem Arbeitsordner. Bitte dessen Serverfenster schließen und erneut starten.',flush=True)
            except (OSError,ValueError):pass
        print('Bitte EAGLEEYE_START_DIAGNOSE.bat oder EAGLEEYE_DATENORDNER_WAEHLEN.bat öffnen.',flush=True)
        return 1

if __name__=='__main__':raise SystemExit(main())
