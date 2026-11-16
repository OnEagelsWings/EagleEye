"""Produce Build 500 offline installer ZIP from tracked clean source and wheelhouse."""
from __future__ import annotations
from pathlib import Path, PurePosixPath
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED
import hashlib
import json
import subprocess
import sys

OUT_PREFIX="EagleEye-500-Internal-Windows-RC"
ZIP_TIME=(2026,11,10,0,0,0)
BLOCKED={".git",".venv","venv","__pycache__","node_modules","data","secrets",
         ".pytest_cache","credentials",".eagleeye-runtime"}
DENIED={".db",".sqlite3",".sqlite",".pem",".key",".p12",".pfx",".log",".zip"}

def _write(z:ZipFile,name:str,data:bytes):
    info=ZipInfo(name,ZIP_TIME);info.compress_type=ZIP_DEFLATED
    info.external_attr=0o100644<<16
    z.writestr(info,data,compress_type=ZIP_DEFLATED,compresslevel=6)

def build(root:Path,out:Path):
    root=root.resolve(strict=True)
    names=subprocess.check_output(["git","-C",str(root),"ls-files","-z"]).split(b"\x00")
    files={}
    for raw in names:
        if not raw:continue
        relative=PurePosixPath(raw.decode("utf-8"))
        if relative.is_absolute() or ".." in relative.parts:raise ValueError("Unsafe source path")
        if (any(p in BLOCKED or p.startswith(".eagleeye-") for p in relative.parts) or
            relative.suffix.lower() in DENIED or relative.name==".env" or
            (relative.name.startswith(".env.") and relative.name!=".env.example")):continue
        path=root.joinpath(*relative.parts)
        if path.is_symlink() or not path.is_file():continue
        if path.stat().st_size>40*1024*1024:raise ValueError("Unexpected large tracked source")
        files[relative.as_posix()]=path.read_bytes()
    wheelhouse=root/"wheelhouse"
    from importlib.util import spec_from_file_location,module_from_spec
    spec=spec_from_file_location("wheelmanifest500",root/"tools"/"build500_wheel_manifest.py")
    helper=module_from_spec(spec);spec.loader.exec_module(helper)
    helper.main(wheelhouse)
    manifest=json.loads((wheelhouse/"MANIFEST-SHA256.json").read_text(encoding="utf-8"))
    for name,sha in manifest.items():
        path=wheelhouse/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError("Wheelhouse tampered")
        files["wheelhouse/"+name]=path.read_bytes()
    files["wheelhouse/MANIFEST-SHA256.json"]=(wheelhouse/"MANIFEST-SHA256.json").read_bytes()
    for needed in ("INSTALL_EAGLEEYE_500.py","START_EAGLEEYE_PRO.bat",
                   "START_EAGLEEYE_PRO.sh","pyproject.toml","eagleeye_pro/version.py"):
        if needed not in files:raise ValueError("Release lacks "+needed)
    inventory={name:hashlib.sha256(data).hexdigest() for name,data in sorted(files.items())}
    header={
        "type":"offline-windows-internal-release-candidate",
        "build":"500.0","release_status":"CANDIDATE_NOT_OPERATIONALLY_APPROVED",
        "python":"3.12+","source_commit":subprocess.check_output(
            ["git","-C",str(root),"rev-parse","HEAD"],text=True).strip(),
        "wheels":len(manifest),"file_sha256":inventory
    }
    files["RELEASE_MANIFEST_500_SHA256.json"]=json.dumps(
        header,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8")
    out.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(out,"w") as z:
        for name,data in sorted(files.items()):
            _write(z,"EagleEye-500/"+name,data)
    with ZipFile(out) as z:
        if z.testzip() is not None:raise ValueError("ZIP CRC failure")
        for name,sha in inventory.items():
            if hashlib.sha256(z.read("EagleEye-500/"+name)).hexdigest()!=sha:
                raise ValueError("ZIP SHA-256 verification failed: "+name)
    digest=hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix(out.suffix+".sha256").write_text(digest+"  "+out.name+"\n",encoding="utf-8")
    print("Created offline installer candidate ZIP",out,"wheels",len(manifest),
          "source files",len(files)-len(manifest)-2,"sha256",digest)

if __name__=="__main__":
    build(Path(sys.argv[1] if len(sys.argv)>1 else "."),
          Path(sys.argv[2] if len(sys.argv)>2 else OUT_PREFIX+".zip"))
