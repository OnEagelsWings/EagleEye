"""Desktop startup with a stable work directory and credential-free diagnostics."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
import re
from pathlib import Path
import threading
import tempfile
import time
from contextlib import contextmanager
from .runtime_lock import workspace_runtime_lock
from eagleeye_pro.version import BUILD
from .paths import default_runtime_root, _internal_release_build

_STATUS_LOCK=threading.Lock()
_SETTINGS_LOCK=threading.Lock()
_START_STAGES={'starting','healthy','stopped','health-timeout','browser-requested','browser-unavailable','start-failed'}


def settings_directory():
    configured=os.environ.get('EAGLEEYE_SETTINGS_DIR')
    if configured:return Path(configured).expanduser().resolve()
    namespace = ('EagleEye-500' if str(BUILD).split('.', 1)[0] == '500' else
                 'EagleEye-490' if _internal_release_build(BUILD) else 'EagleEye')
    if os.name=='nt':return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/namespace
    return Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/namespace


def _local_path(value):
    if not isinstance(value,(str,Path)):
        raise ValueError('Bitte einen gültigen lokalen Arbeitsordner auswählen.')
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


def remember_workspace(path, install_dir=None):
    root=_local_path(path)
    if install_dir is not None:
        _reject_internal_install_as_workspace(root, install_dir)
    # The folder picker must enforce the same isolation gate as startup.
    # Validate before creating directories or persisting a selection.
    _reject_legacy_internal_workspace(root)
    root.mkdir(parents=True,exist_ok=True)
    with _settings_guard() as directory:
        _atomic_json(directory/'workspace.json',{'workspace_directory':str(root)})
    return root


def _reject_legacy_internal_workspace(root):
    """Never initialize the internal release inside an existing legacy database root."""
    if not _internal_release_build(BUILD):
        return
    # Older installations can also keep the database directly at the
    # workspace root. Neither layout may be adopted by Build 490–500.
    # Reject redirected workspace subdirectories before persisting a selection.
    # Otherwise a folder picker could save an alias into a legacy data tree.
    # Check nested evidence and report module roots *before* the folder picker
    # persists the selection. RuntimePaths.resolve also validates these paths,
    # but a failed launch must not leave a poisoned workspace.json behind.
    module_roots = (
        root / 'data', root / 'reports',
        root / 'data' / 'evidence_vault',
        root / 'data' / 'search_captures',
        root / 'data' / 'secure_storage',
        root / 'reports' / 'report_builder_pro_89',
    )
    for directory in module_roots:
        if directory.is_symlink() or not directory.resolve().is_relative_to(root.resolve()):
            raise ValueError('Arbeitsordner enthält umgeleitete Datenverzeichnisse; bitte einen eigenen lokalen Ordner wählen.')
    if any((directory / ('eagleeye_pro_95_0.db' + suffix)).exists()
           for directory in (root, root / 'data')
           for suffix in ('', '-wal', '-shm')):
        raise ValueError('Dieser Arbeitsordner enthält eine ältere EagleEye-Datenbank. Für Build 490–500 bitte einen eigenen neuen Arbeitsordner wählen.')


def _reject_internal_install_as_workspace(root, install_dir):
    """An internal-release data workspace must not be the program directory."""
    if _internal_release_build(BUILD):
        installed = _local_path(install_dir)
        # A nested workspace (e.g. <install>/data) is just as unsafe as the
        # installation root: upgrades and removals must not touch case data.
        if root == installed or installed in root.parents or root in installed.parents:
            raise ValueError('Programm- und Arbeitsordner müssen für Build 490–500 getrennt sein.')


def resolve_workspace(install_dir):
    with _settings_guard() as directory:
        explicit=os.environ.get('EAGLEEYE_DATA_DIR')
        settings=directory/'workspace.json'
        if explicit:
            root=_local_path(explicit)
        elif settings.is_file():
            # Never silently fall back to an empty workspace if a saved data
            # location is corrupt or temporarily unavailable. Existing cases
            # may live in that directory, including older Build-398 installs.
            try:
                saved=json.loads(settings.read_text(encoding='utf-8'))
                if not isinstance(saved,dict):
                    raise ValueError('workspace settings are not an object')
                root=_local_path(saved['workspace_directory'])
            except (OSError,ValueError,KeyError,TypeError) as exc:
                raise ValueError('Arbeitsordner-Konfiguration unlesbar. Bestehende Daten bleiben unverändert; bitte den bisherigen Datenordner ausdrücklich auswählen.') from exc
            if not root.is_dir():
                raise ValueError('Der gespeicherte Arbeitsordner fehlt. Bestehende Daten nicht überschreiben; bitte den bisherigen Datenordner auswählen.')
            _reject_legacy_internal_workspace(root)
            _reject_internal_install_as_workspace(root, install_dir)
            return root
        else:
            installed=_local_path(install_dir)
            if _internal_release_build(BUILD):
                root=directory/'workspace'
            else:
                candidates=[candidate for candidate in (installed,default_runtime_root())
                    if any((candidate/'data'/name).is_file() for name in ('eagleeye.db','eagleeye_pro_95_0.db'))]
                root=candidates[0] if candidates else directory/'workspace'
        _reject_legacy_internal_workspace(root)
        _reject_internal_install_as_workspace(root, install_dir)
        root.mkdir(parents=True,exist_ok=True)
        _atomic_json(settings,{'workspace_directory':str(root)})
        return root


def write_start_status(root,stage,**details):
    # Status and diagnostics are intentionally credential-free. Only known
    # enum values, exception class names and numeric ports may be persisted.
    stage=stage if stage in _START_STAGES else 'start-failed'
    allowed={}
    if details.get('browser') in {'firefox','default','unavailable'}:
        allowed['browser']=details['browser']
    error_type=details.get('error_type')
    if isinstance(error_type,str) and error_type.isidentifier() and len(error_type)<=80:
        allowed['error_type']=error_type
    try:
        port=int(details.get('port',0))
        if 1<=port<=65535:allowed['port']=port
    except (TypeError,ValueError,OverflowError):
        pass
    with _STATUS_LOCK:
        _atomic_json(Path(root)/'data/runtime_126_0/start-status.json',
            {'build':BUILD,'stage':stage,'updated_at':datetime.now(timezone.utc).isoformat(),**allowed})


def diagnostics(root):
    from eagleeye.interfaces.web.server import _read_running_workspace
    root=_local_path(root);runtime=_read_running_workspace(root,accept_other_build=True)
    status_path=root/'data/runtime_126_0/start-status.json'
    try:status=json.loads(status_path.read_text(encoding='utf-8'))
    except (OSError,ValueError):status={'stage':'unknown'}
    safe_status={'stage':status.get('stage') if status.get('stage') in _START_STAGES else 'unknown'}
    timestamp=status.get('updated_at')
    if isinstance(timestamp,str) and len(timestamp)<=48 and re.fullmatch(r'[0-9TZ:+.-]+',timestamp):
        safe_status['updated_at']=timestamp
    if status.get('browser') in {'firefox','default','unavailable'}:
        safe_status['browser']=status['browser']
    error_type=status.get('error_type')
    if isinstance(error_type,str) and error_type.isidentifier() and len(error_type)<=80:
        safe_status['error_type']=error_type
    return {'build':BUILD,'workspace_directory':str(root),'database_present':(root/'data'/'eagleeye.db').is_file() if _internal_release_build(BUILD) else any((root/'data'/n).is_file() for n in ('eagleeye.db','eagleeye_pro_95_0.db')),
        'server_reachable':bool(runtime and runtime['build']==BUILD),'running_build':runtime['build'] if runtime else None,
        'version_conflict':bool(runtime and runtime['build']!=BUILD),'port':runtime['port'] if runtime else None,
        'last_start':safe_status,
        'contains_credentials':False}


def choose_workspace(install_dir=None):
    import tkinter
    from tkinter import filedialog
    window=tkinter.Tk();window.withdraw()
    try:
        selected=filedialog.askdirectory(title='EagleEye: bisherigen oder neuen Arbeitsordner wählen')
    finally:window.destroy()
    return remember_workspace(selected, install_dir=install_dir) if selected else None


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-root',required=True)
    parser.add_argument('--choose-workspace',action='store_true')
    parser.add_argument('--diagnose',action='store_true')
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args(argv)
    root=None
    try:
        root=choose_workspace(args.install_root) if args.choose_workspace else resolve_workspace(args.install_root)
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
