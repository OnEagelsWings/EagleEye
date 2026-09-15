from __future__ import annotations
import socket,threading
from dataclasses import dataclass
from .tor_gateway import TorReadOnlyGateway

TEST_ONION='a'*56+'.onion'
@dataclass
class HarnessResult:
 result:str; target_host:str; target_port:int; status_code:int; body:str; proxy_port:int

def run_local_socks5_http_selftest()->HarnessResult:
    ready=threading.Event(); captured={}; errors=[]
    listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM); listener.bind(('127.0.0.1',0)); listener.listen(1); port=listener.getsockname()[1]
    def rx_exact(c,n):
        b=b''
        while len(b)<n:
            x=c.recv(n-len(b))
            if not x: raise RuntimeError('selftest EOF')
            b+=x
        return b
    def server():
        try:
            ready.set(); c,_=listener.accept(); c.settimeout(4)
            with c:
                assert rx_exact(c,3)==b'\x05\x01\x00'; c.sendall(b'\x05\x00')
                h=rx_exact(c,4); assert h==b'\x05\x01\x00\x03'; ln=rx_exact(c,1)[0]; host=rx_exact(c,ln).decode('ascii'); target_port=int.from_bytes(rx_exact(c,2),'big'); captured.update(host=host,port=target_port)
                c.sendall(b'\x05\x00\x00\x01\x7f\x00\x00\x01\x1f\x90')
                req=b''
                while b'\r\n\r\n' not in req:req+=c.recv(4096)
                captured['request']=req.decode('iso-8859-1','replace')
                body=b'<html><body>phase13-tor-selftest</body></html>'
                resp=b'HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body
                c.sendall(resp)
        except Exception as exc:errors.append(repr(exc))
        finally:listener.close()
    t=threading.Thread(target=server,daemon=True); t.start(); ready.wait(2)
    g=TorReadOnlyGateway('127.0.0.1',port,connect_timeout=2,read_timeout=3); r=g.fetch('http://'+TEST_ONION+'/',max_bytes=65536,max_redirects=0); t.join(3)
    if errors:raise RuntimeError('; '.join(errors))
    if captured.get('host')!=TEST_ONION or captured.get('port')!=80:raise RuntimeError('SOCKS target mismatch')
    if 'GET / HTTP/1.1' not in captured.get('request',''):raise RuntimeError('GET request missing')
    return HarnessResult('pass',captured['host'],captured['port'],r.status_code,r.body.decode('utf-8'),port)
