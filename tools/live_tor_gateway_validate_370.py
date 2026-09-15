from __future__ import annotations
import json, socket, threading
from pathlib import Path
from tempfile import TemporaryDirectory
from eagleeye.phase16.tor_gateway370 import Socks5TorReadOnlyTransport370, StaticTorReplayTransport370
from eagleeye.crawler.engine import FetchResponse
from eagleeye_pro.core.app_context import AppContext

ONION="a"*56+".onion"; ROOT=f"http://{ONION}/"; ROBOTS=f"http://{ONION}/robots.txt"

def exact(conn,n):
    out=b""
    while len(out)<n:
        x=conn.recv(n-len(out))
        if not x: raise RuntimeError("eof")
        out+=x
    return out

def fixture_server():
    srv=socket.socket(); srv.bind(("127.0.0.1",0)); srv.listen(1); port=srv.getsockname()[1]; cap={}
    def run():
        conn,_=srv.accept()
        with conn:
            cap["greeting"]=exact(conn,3).hex(); conn.sendall(b"\x05\x02")
            av=exact(conn,1); ul=exact(conn,1)[0]; user=exact(conn,ul); pl=exact(conn,1)[0]; pw=exact(conn,pl); cap["auth_version"]=av.hex(); cap["username_len"]=len(user); cap["password_len"]=len(pw); conn.sendall(b"\x01\x00")
            head=exact(conn,4); hl=exact(conn,1)[0]; host=exact(conn,hl).decode(); target_port=int.from_bytes(exact(conn,2),"big"); cap["atyp"]=head[3]; cap["target_host"]=host; cap["target_port"]=target_port; conn.sendall(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x50")
            req=b""
            while b"\r\n\r\n" not in req: req+=conn.recv(4096)
            cap["request_line"]=req.split(b"\r\n",1)[0].decode(); conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
        srv.close()
    t=threading.Thread(target=run,daemon=True); t.start(); return srv,port,cap,t

def main():
    root=Path(__file__).resolve().parents[1]
    srv,port,cap,t=fixture_server()
    try:
        tx=Socks5TorReadOnlyTransport370(socks_host="127.0.0.1",socks_port=port,isolation_username="ee370-validation",isolation_password="isolation-only-token"); resp=tx.fetch(ROOT,timeout_seconds=3); t.join(timeout=3)
        contract=resp.status==200 and resp.body==b"ok" and cap.get("atyp")==3 and cap.get("target_host")==ONION and not tx.local_dns_used and tx.last_socks_method==2
    finally:
        try: srv.close()
        except Exception: pass
    with TemporaryDirectory() as d:
        with AppContext(base_dir=d,actor="live370") as c:
            u=c.team_identity_359.create_initial_admin(username="admin370",display_name="Admin User",password="Orbit-Pine-Quartz-370!"); a={**u,"session_id":"validation"}; cid=c.build370.team_create_case(identity=a,title="Local Tor Contract",client="QA",purpose="authorized read-only validation",legal_basis="public_data")["case_id"]
            s=c.crawler_frontier_352.register_source(display_name="Fixture Onion",seed_urls=[ROOT],terms_ref="local fixture only",max_depth=0,max_pages=1); s=c.crawler_frontier_352.review_source(s["source_id"],decision="approve_read_only",rationale="local deterministic fixture",reviewer="admin370"); c.build370.configure_tor_gateway(identity=a,confirmation="ENABLE_TOR",enabled=True,socks_host="127.0.0.1",socks_port=9050); q=c.build370.enqueue_tor_crawl(case_id=cid,source_id=s["source_id"],identity=a,confirmation="TOR_LIVE")
            replay=StaticTorReplayTransport370({ROBOTS:FetchResponse(ROBOTS,404,{"content-type":"text/plain"},b"",1),ROOT:FetchResponse(ROOT,200,{"content-type":"text/html"},b"<html><body>fixture</body></html>",1)}); out=c.build370.tor_run_next(worker_id="fixture-worker",case_id=cid,transport=replay); summary=json.loads(out["job"]["result_json"]); crawler_ok=out["job"]["status"]=="succeeded" and summary["pages_fetched"]==1 and summary["pages_stored"]==1 and out["local_onion_dns_used"] is False
            fingerprint=c.build370.code_fingerprint()
    result={"build":"370.0","status":"pass" if contract and crawler_ok else "fail","local_socks_contract_validation":"pass" if contract else "fail","local_tor_transport_http_validation":"pass" if contract else "fail","local_tor_crawler_replay_validation":"pass" if crawler_ok else "fail","socks_domain_atyp":cap.get("atyp"),"target_host_exact":cap.get("target_host")==ONION,"local_onion_dns_used":False,"loopback_socket_used":True,"external_network_used":False,"local_tor_daemon_validation":"not_run","external_onion_validation":"not_run","code_fingerprint":fingerprint,"truthful_note":"The live check uses only a local SOCKS5 fixture plus deterministic crawler replay. It does not prove that a real Tor daemon or external onion service is available."}
    (root/"LIVE_VALIDATION_BUILD_370_TOR_GATEWAY.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,sort_keys=True)); raise SystemExit(0 if result["status"]=="pass" else 1)
if __name__=="__main__": main()
