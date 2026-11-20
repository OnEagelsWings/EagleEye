"""Read-only security evidence workflows."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
LABELS = {"pcap":"TShark · Mitschnitt", "zap":"ZAP · passive HAR-Prüfung",
          "leaks":"Gitleaks · Repository", "yara":"YARA · Dateimuster",
          "inventory":"Nmap · Inventarvergleich", "lynis":"Lynis · Systemaudit / Bericht"}

def binary(name):
    if name == "tshark" and os.name == "nt":
        exe = Path(os.environ.get("ProgramFiles","C:/Program Files")) / "Wireshark/tshark.exe"
        if exe.is_file(): return str(exe)
    if name == "gitleaks" and (ROOT/"gitleaks/gitleaks.exe").is_file():
        return str(ROOT/"gitleaks/gitleaks.exe")
    return shutil.which(name)

def zap_command():
    jars = sorted(ROOT.glob("ZAP_*/zap-*.jar"))
    if jars and shutil.which("java"):
        return [shutil.which("java"), "-Xmx512m", "-jar", str(jars[-1])]
    script = shutil.which("zaproxy") or shutil.which("zap.sh")
    return [script] if script else []

def status():
    needs = {"pcap": [] if binary("tshark") else ["tshark"],
             "zap":[] if zap_command() else ["ZAP / Java"],
             "leaks":[n for n in ("gitleaks","git") if not binary(n)],
             "yara":[] if importlib.util.find_spec("yara") else ["yara-python"],
             "inventory":[], "lynis":[]}
    return {k:{"label":label,"missing":needs[k]} for k,label in LABELS.items()}

def run(args, codes=(0,), timeout=300, **kwargs):
    p = subprocess.run(args, capture_output=True,timeout=timeout,**kwargs)
    if p.returncode not in codes:
        raise ValueError(f"{Path(str(args[0])).name}: Ausführung fehlgeschlagen (Code {p.returncode}).")
    return p.stdout.decode("utf-8","replace").strip()

def nmap_inventory(path):
    root = ET.parse(path).getroot()
    if root.tag!="nmaprun": raise ValueError("Nmap-XML erwartet.")
    entries = {}
    for host in root.findall("host"):
        addr=next((a.get("addr") for a in host.findall("address") if a.get("addrtype") in ("ipv4","ipv6")),None)
        if not addr: continue
        for port in host.findall("./ports/port"):
            state,svc=port.find("state"),port.find("service")
            if state is not None and state.get("state")=="open":
                entries[(addr,port.get("protocol",""),port.get("portid",""))]=svc.get("name","?") if svc is not None else "?"
    return root.get("startstr") or root.get("start") or "unbekannt", entries

def text_json(value):
    return json.dumps(value,indent=2,ensure_ascii=False)

def inspect_files(mode, files):
    if mode in ("pcap","zap","leaks") and len(files)!=1:
        raise ValueError("Genau einen Eingabepfad angeben.")
    if mode=="pcap":
        exe=binary("tshark")
        fields=["frame.number","frame.time_epoch","ip.src","ipv6.src","ip.dst","ipv6.dst","_ws.col.Protocol","dns.qry.name","dns.flags.rcode","tcp.analysis.retransmission"]
        args=[exe,"-n","-r",str(files[0]),"-c","10000","-T","fields","-E","header=y"]
        for f in fields: args.extend(["-e",f])
        return "Erste bis zu 10.000 Pakete (TSV)\n"+run(args),{"TShark":run([exe,"--version"]).splitlines()[0]}
    if mode=="inventory":
        if len(files)!=2: raise ValueError("Zuerst älteres, dann neueres Nmap-XML auswählen.")
        (old_time,old),(new_time,new)=map(nmap_inventory,files)
        rows=[{"Adresse":k[0],"Protokoll":k[1],"Port":k[2],"vorher":old.get(k),"nachher":new.get(k)}
              for k in sorted(old.keys()|new.keys()) if old.get(k)!=new.get(k)]
        return f"Messzeit vorher: {old_time} · nachher: {new_time}\nUnterschiede der als offen gemeldeten Ports. Abweichender Scanumfang kann Unterschiede erklären.\n"+text_json(rows),{"Nmap-XML-Import":"1"}
    if mode=="yara":
        if len(files)<2: raise ValueError("Zuerst eine YARA-Regeldatei, danach die zu prüfenden Dateien auswählen.")
        import yara
        rules=yara.compile(source=files[0].read_text(encoding="utf-8-sig"),includes=False)
        results=[]
        for p in files[1:]:
            for match in rules.match(str(p),timeout=60):
                results.append({"Datei":p.name,"Regel":match.rule,"Fundstellen":[{"Muster":s.identifier,"Offsets":[i.offset for i in s.instances[:100]]} for s in match.strings]})
        return text_json(results) if results else "Keine passende Regel.",{"YARA":yara.__version__}
    if mode=="leaks":
        repo=files[0]
        if not repo.is_dir() or not (repo/".git").exists(): raise ValueError("Lokalen Git-Arbeitsordner auswählen.")
        exe=binary("gitleaks")
        head=run([binary("git"),"-C",str(repo),"rev-parse","HEAD"])
        with tempfile.TemporaryDirectory() as td:
            report=Path(td)/"report.json"
            cfg=Path(td)/"rules.toml"
            cfg.write_text("[extend]\nuseDefault = true\n",encoding="utf-8")
            run([exe,"git","--redact=100","--no-banner","--config",str(cfg),"--log-opts",head,"--report-format","json","--report-path",str(report),str(repo)],codes=(0,1))
            if not report.is_file(): raise ValueError("Gitleaks hat keinen auswertbaren Bericht erzeugt.")
            raw=json.loads(report.read_text(encoding="utf-8-sig"))
            safe=[{k:x.get(k) for k in ("RuleID","File","StartLine","EndLine","Commit")} for x in raw or []]
        return f"Geprüfter Commit: {head}\n{len(safe)} Treffer\n"+text_json(safe),{"Gitleaks":run([exe,"version"])}
    if mode=="lynis":
        if len(files)>1: raise ValueError("Einen Lynis-Bericht oder unter Linux ein leeres Pfadfeld verwenden.")
        with tempfile.TemporaryDirectory() as td:
            if files: path=files[0]
            else:
                exe=binary("lynis")
                if not exe or os.name=="nt": raise ValueError("Auf Windows bitte einen vorhandenen lynis-report.dat auswählen.")
                path=Path(td)/"report.dat"
                run([exe,"audit","system","--quick","--no-colors","--logfile",str(Path(td)/"audit.log"),"--report-file",str(path)],timeout=600,cwd=str(Path(exe).resolve().parent))
            values={}
            for line in path.read_text(encoding="utf-8",errors="replace").splitlines():
                key,sep,val=line.partition("=")
                if sep and key in ("lynis_version","hardening_index","warning[]","suggestion[]","report_version_major"):
                    values.setdefault(key,[]).append(val)
            if "lynis_version" not in values: raise ValueError("Lynis-Berichtsformat nicht erkannt.")
            return text_json(values),{"Lynis":values["lynis_version"][0]}
    if mode=="zap":
        har=json.loads(files[0].read_text(encoding="utf-8-sig"))
        entries=har.get("log",{}).get("entries")
        if not isinstance(entries,list) or not entries or len(entries)>5000:
            raise ValueError("HAR mit 1 bis 5.000 aufgezeichneten Vorgängen erforderlich.")
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            jobs=[{"type":"import","parameters":{"type":"har","fileName":str(files[0]),"sendRequests":False}},
                  {"type":"passiveScan-wait","parameters":{"maxDuration":5}},
                  {"type":"report","parameters":{"template":"traditional-json","reportDir":td,"reportFile":"report.json"}}]
            plan=tmp/"plan.yaml"
            plan.write_text(json.dumps({"env":{"contexts":[{"name":"Archiv","urls":["http://eagleeye.invalid"]}],"parameters":{"failOnWarning":False}},"jobs":jobs}),encoding="utf-8")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1",0))
                port=sock.getsockname()[1]
            args=zap_command()+["-cmd","-silent","-host","127.0.0.1","-port",str(port),"-dir",str(tmp/"home"),"-autorun",str(plan)]
            run(args,codes=(0,2),timeout=500,cwd=td)
            report=json.loads((tmp/"report.json").read_text(encoding="utf-8-sig"))
            alerts=[]
            for site in report.get("site",[]):
                for a in site.get("alerts",[]):
                    paths=set()
                    for i in a.get("instances",[]):
                        u=urlsplit(i.get("uri",""))
                        paths.add((u.hostname or "")+u.path)
                    alerts.append({"Regel":a.get("pluginid"),"Titel":a.get("alert") or a.get("name"),"Risiko":a.get("riskcode"),"Routen":sorted(paths)})
            return f"{len(entries)} HAR-Einträge · {len(alerts)} Warnungsgruppen\n"+text_json(alerts),{"ZAP":str(report.get("@version","unbekannt"))}
    raise ValueError("Unbekannter Prüfauftrag.")
