from __future__ import annotations
import hashlib,json,stat,zipfile
from pathlib import Path
BUILD='364.0'; PREFIX='EagleEye_PersonOSINT_Pro_Build_364_0'; FIXED=(1980,1,1,0,0,0)
EXCLUDE_PARTS={'.git','.pytest_cache','__pycache__','build','dist','.mypy_cache','.ruff_cache','data','exports','logs'}
EXCLUDE_SUFFIX={'.pyc','.pyo'}

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()

def selected(root:Path):
 out=[]
 for p in root.rglob('*'):
  if not p.is_file():continue
  rel=p.relative_to(root)
  if any(x in EXCLUDE_PARTS or x.endswith('.egg-info') for x in rel.parts):continue
  if p.suffix in EXCLUDE_SUFFIX:continue
  if p.name.endswith('.zip') or p.name.endswith('.whl') or p.name.endswith('.sha256'):continue
  out.append(p)
 return sorted(out,key=lambda x:x.relative_to(root).as_posix())

def build(root:Path,out:Path):
 files=selected(root);out.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in files:
   rel=p.relative_to(root).as_posix();info=zipfile.ZipInfo(f'{PREFIX}/{rel}',FIXED);info.compress_type=zipfile.ZIP_DEFLATED;mode=0o755 if p.suffix=='.sh' else 0o644;info.external_attr=(stat.S_IFREG|mode)<<16;info.create_system=3;z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
 return {'build':BUILD,'file_count':len(files),'sha256':sha(out),'size':out.stat().st_size}
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();print(json.dumps(build(Path(__file__).resolve().parents[1],a.output),sort_keys=True))
