"""Offline workspace backup and restore into a new local directory."""
from __future__ import annotations
import argparse,hashlib,json,os,secrets,shutil,sqlite3,stat,tempfile,zipfile
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from .runtime_lock import workspace_runtime_lock
from eagleeye_pro.version import BUILD

FORMAT='eagleeye-offline-workspace-v1'
MANIFEST='EAGLEEYE_BACKUP_MANIFEST.json'
MAX_BYTES=2*1024*1024*1024
MAX_FILES=100000
MAX_MANIFEST=32*1024*1024

def now():return datetime.now(timezone.utc).isoformat()

def sha_file(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

def safe_name(value):
    if not isinstance(value,str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise ValueError('Ungültiger Archivpfad.')
    path=PurePosixPath(value)
    if path.is_absolute() or any(p in ('','.','..') for p in value.split('/')):
        raise ValueError('Archivpfad verlässt den Zielordner.')
    for part in path.parts:
        if part.endswith((' ','.')) or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
            raise ValueError('Nicht portabler Dateiname.')
    if not (path.parts[0] in {'data','reports','exports'} or (len(path.parts)==1 and value.startswith('entity_registry') and value.endswith(('.sqlite3','.db')))):
        raise ValueError('Pfad außerhalb des gesicherten Arbeitsbestands.')
    return path

def excluded(name):
    return (name.startswith('data/runtime_126_0/') or name in {'data/.workspace.runtime.lock','data/security_364/local_session_token'}
        or name.endswith(('-wal','-shm','-journal')))

def local_path(value):
    value=str(value)
    if value.startswith(('//','\\\\')):raise ValueError('Lokalen Ordner auswählen.')
    return Path(value).expanduser().resolve()

def collect_files(root):
    files=[]
    candidates=[root/'data',root/'reports',root/'exports',*root.glob('entity_registry*.sqlite3'),*root.glob('entity_registry*.db')]
    def visit(path):
        if path.is_symlink() or getattr(path,'is_junction',lambda:False)():
            raise ValueError('Verknüpfungen sind nicht Teil einer portablen Sicherung.')
        if not path.exists():return
        relative=path.relative_to(root).as_posix()
        if excluded(relative) or relative=='data/runtime_126_0':return
        if path.is_dir():
            for child in sorted(path.iterdir()):visit(child)
        elif path.is_file():
            safe_name(relative)
            if root not in path.resolve().parents:raise ValueError('Datei außerhalb des Arbeitsordners.')
            files.append((relative,path))
            if len(files)>MAX_FILES:raise ValueError('Zu viele Dateien.')
        else:raise ValueError('Nicht reguläre Datei im Arbeitsbestand.')
    for candidate in candidates:visit(candidate)
    names=[name.casefold() for name,_ in files]
    if len(names)!=len(set(names)):raise ValueError('Mehrdeutige Dateinamen.')
    return sorted(files)

def sqlite_snapshot(source,target):
    connection=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    destination=sqlite3.connect(target)
    try:
        connection.backup(destination)
        if destination.execute('PRAGMA quick_check').fetchone()[0]!='ok':
            raise ValueError('SQLite-Sicherung ist nicht konsistent.')
    finally:destination.close();connection.close()

def create_backup(root,archive):
    root=local_path(root);archive=local_path(archive)
    if not (root/'data/eagleeye.db').is_file():raise ValueError('Kein bestehender EagleEye-Arbeitsordner.')
    if archive==root or root in archive.parents:raise ValueError('Sicherung außerhalb des Arbeitsordners speichern.')
    if archive.exists():raise FileExistsError('Zieldatei existiert bereits.')
    created=False
    try:
        with workspace_runtime_lock(root,timeout=0),tempfile.TemporaryDirectory(prefix='eagleeye-backup-') as temporary:
            files=collect_files(root);entries=[];total=0
            with archive.open('xb') as raw:
                created=True
                try:archive.chmod(0o600)
                except OSError:pass
                with zipfile.ZipFile(raw,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
                    for index,(name,path) in enumerate(files):
                        before=path.stat()
                        with path.open('rb') as handle:magic=handle.read(16)
                        source=path
                        application_db=(name in {'data/eagleeye.db','data/eagleeye_pro_95_0.db','data/operational_notes_478.sqlite3'}
                            or name in {'entity_registry_461.sqlite3','entity_registry_462.sqlite3'})
                        if application_db and magic==b'SQLite format 3\x00':
                            source=Path(temporary)/str(index);sqlite_snapshot(path,source)
                        size=source.stat().st_size
                        if total+size>MAX_BYTES:raise ValueError('Sicherung überschreitet 2 GiB.')
                        digest=hashlib.sha256();written=0
                        with source.open('rb') as incoming,out.open(name,'w',force_zip64=True) as outgoing:
                            for chunk in iter(lambda:incoming.read(1024*1024),b''):
                                written+=len(chunk)
                                if total+written>MAX_BYTES:raise ValueError('Sicherung überschreitet 2 GiB.')
                                outgoing.write(chunk);digest.update(chunk)
                        after=path.stat()
                        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                            raise ValueError('Datei wurde während der Sicherung geändert.')
                        total+=written;entries.append({'path':name,'bytes':written,'sha256':digest.hexdigest()})
                        if source!=path:source.unlink()
                    manifest={'format':FORMAT,'source_build':BUILD,'created_at':now(),
                        'scope':['data','reports','exports','root entity_registry databases'],'files':entries,
                        'total_bytes':total,'sessions_reactivated_on_restore':False}
                    payload=json.dumps(manifest,ensure_ascii=False,sort_keys=True).encode()
                    if len(payload)>MAX_MANIFEST:raise ValueError('Manifest zu groß.')
                    out.writestr(MANIFEST,payload)
            return {'archive':str(archive),'sha256':sha_file(archive),'files':len(entries),'bytes':total,'build':BUILD}
    except BaseException:
        if created:archive.unlink(missing_ok=True)
        raise

def restore_backup(archive,target):
    archive=local_path(archive);target=local_path(target)
    if target.exists():raise FileExistsError('Wiederherstellung erfordert einen neuen, nicht vorhandenen Ordner.')
    if not target.parent.is_dir():raise ValueError('Ziel-Elternordner fehlt.')
    owned=False
    with zipfile.ZipFile(archive) as incoming:
        infos=incoming.infolist();names=[info.filename for info in infos]
        if len(infos)>MAX_FILES+1 or len(names)!=len(set(n.casefold() for n in names)) or names.count(MANIFEST)!=1:
            raise ValueError('Mehrdeutiges oder zu großes Archiv.')
        meta=incoming.getinfo(MANIFEST)
        if meta.file_size>MAX_MANIFEST:raise ValueError('Manifest zu groß.')
        payload=incoming.read(meta);manifest=json.loads(payload)
        if manifest.get('format')!=FORMAT:raise ValueError('Unbekanntes Sicherungsformat.')
        entries=manifest.get('files')
        if not isinstance(entries,list) or len(entries)>MAX_FILES:raise ValueError('Ungültige Dateiliste.')
        expected={};total=0
        for entry in entries:
            name=entry['path'];safe_name(name)
            size=entry['bytes'];digest=entry['sha256']
            if excluded(name) or name in expected or type(size) is not int or size<0 or not isinstance(digest,str) or len(digest)!=64:
                raise ValueError('Ungültiger Dateieintrag.')
            total+=size;expected[name]=entry
        if total>MAX_BYTES or total!=manifest.get('total_bytes') or set(names)!={*expected,MANIFEST} or 'data/eagleeye.db' not in expected:
            raise ValueError('Sicherungsumfang stimmt nicht mit dem Manifest überein.')
        for info in infos:
            mode=info.external_attr>>16
            if info.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0,stat.S_IFREG}):
                raise ValueError('Nur reguläre Dateien sind erlaubt.')
            if info.filename!=MANIFEST and info.file_size!=expected[info.filename]['bytes']:
                raise ValueError('Dateigröße stimmt nicht überein.')
        try:
            target.mkdir(mode=0o700,exist_ok=False);owned=True
            for name,entry in expected.items():
                path=target.joinpath(*PurePosixPath(name).parts);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                digest=hashlib.sha256();written=0
                with incoming.open(name) as source,path.open('xb') as out:
                    try:path.chmod(0o600)
                    except OSError:pass
                    for chunk in iter(lambda:source.read(1024*1024),b''):
                        written+=len(chunk)
                        if written>entry['bytes']:raise ValueError('Entpackbudget überschritten.')
                        out.write(chunk);digest.update(chunk)
                if written!=entry['bytes'] or digest.hexdigest()!=entry['sha256']:
                    raise ValueError('Datei-Hash stimmt nicht überein.')
            db=sqlite3.connect(target/'data/eagleeye.db')
            try:
                if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Wiederhergestellte Datenbank beschädigt.')
                present=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='phase15_team_sessions'").fetchone()
                reset=0
                if present:
                    reset=db.execute("UPDATE phase15_team_sessions SET revoked=1,revoked_reason='workspace_restore' WHERE revoked=0").rowcount
                    db.commit()
            finally:db.close()
            receipt={'format':FORMAT,'restored_at':now(),'source_build':manifest.get('source_build'),
                'manifest_sha256':hashlib.sha256(payload).hexdigest(),'verified_files':len(expected),'verified_bytes':total,
                'archived_bytes_verified_before_session_reset':True,'sessions_revoked':reset,
                'database_sha256_after_session_reset':sha_file(target/'data/eagleeye.db'),
                'existing_workspace_overwritten':False}
            (target/'restore-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
            return receipt
        except BaseException:
            if owned:shutil.rmtree(target)
            raise

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-root',required=True)
    actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--backup',action='store_true');actions.add_argument('--restore',action='store_true')
    parser.add_argument('--archive');parser.add_argument('--target')
    args=parser.parse_args(argv)
    from .desktop476 import resolve_workspace,remember_workspace
    try:
        if args.archive:archive=local_path(args.archive)
        else:
            import tkinter
            from tkinter import filedialog
            window=tkinter.Tk();window.withdraw()
            try:
                selected=(filedialog.asksaveasfilename(title='Eigene Sicherung außerhalb des Arbeitsordners speichern',defaultextension='.zip')
                    if args.backup else filedialog.askopenfilename(title='Eigene vertrauenswürdige EagleEye-Sicherung wählen',filetypes=[('ZIP','*.zip')]))
            finally:window.destroy()
            if not selected:return 0
            archive=local_path(selected)
        if args.backup:result=create_backup(resolve_workspace(args.install_root),archive)
        else:
            if args.target:target=local_path(args.target)
            else:
                import tkinter
                from tkinter import filedialog
                window=tkinter.Tk();window.withdraw()
                try:selected=filedialog.askdirectory(title='Elternordner für einen NEUEN Wiederherstellungsordner wählen')
                finally:window.destroy()
                if not selected:return 0
                target=local_path(selected)/('EagleEye-Restore-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3))
            result=restore_backup(archive,target)
            if not args.target:remember_workspace(target)
            result['workspace_directory']=str(target)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,RuntimeError,sqlite3.Error,zipfile.BadZipFile) as exc:
        print('Sicherung/Wiederherstellung fehlgeschlagen: '+str(exc));return 1

if __name__=='__main__':raise SystemExit(main())
