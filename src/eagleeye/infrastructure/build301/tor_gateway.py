from __future__ import annotations
import hashlib,socket,ssl
from dataclasses import dataclass
from urllib.parse import urljoin,urlsplit

_ALLOWED_SCHEMES={'http','https'}
_ALLOWED_MIME={'text/html','text/plain','application/json','application/xhtml+xml','application/xml','text/xml'}
_LOOPBACK={'127.0.0.1','localhost','::1'}

class TorGatewayError(RuntimeError): pass
class TorPolicyError(ValueError): pass

@dataclass(frozen=True)
class TorFetchResult:
    requested_url:str
    final_url:str
    status_code:int
    headers:dict[str,str]
    content_type:str
    body:bytes
    sha256:str
    redirect_count:int
    proxy_host:str
    proxy_port:int


def validate_onion_url(url:str)->tuple[str,str,int,str]:
    raw=(url or '').strip()
    p=urlsplit(raw)
    if p.scheme.lower() not in _ALLOWED_SCHEMES: raise TorPolicyError('only http/https onion URLs are allowed')
    if p.username is not None or p.password is not None: raise TorPolicyError('credentials/userinfo are forbidden')
    host=(p.hostname or '').lower().rstrip('.')
    label=host[:-6] if host.endswith('.onion') else ''
    if len(label)!=56 or any(ch not in 'abcdefghijklmnopqrstuvwxyz234567' for ch in label):
        raise TorPolicyError('only Tor v3 .onion hosts are allowed')
    port=p.port or (443 if p.scheme.lower()=='https' else 80)
    if port not in (80,443): raise TorPolicyError('Build 301 permits only standard onion HTTP/HTTPS ports')
    path=p.path or '/'
    if p.query: path += '?' + p.query
    return p.scheme.lower(),host,port,path

class TorReadOnlyGateway:
    def __init__(self,proxy_host='127.0.0.1',proxy_port=9050,*,connect_timeout=8.0,read_timeout=15.0):
        if proxy_host not in _LOOPBACK: raise TorPolicyError('Tor SOCKS proxy must be local loopback')
        self.proxy_host=proxy_host; self.proxy_port=int(proxy_port); self.connect_timeout=float(connect_timeout); self.read_timeout=float(read_timeout)
    @staticmethod
    def allowed_mime_types(): return sorted(_ALLOWED_MIME)
    def health_check(self)->dict:
        try:
            s=socket.create_connection((self.proxy_host,self.proxy_port),timeout=min(self.connect_timeout,1.5)); s.settimeout(1.5)
            with s:
                s.sendall(b'\x05\x01\x00'); reply=self._recv_exact(s,2)
                healthy=reply==b'\x05\x00'
                return {'healthy':healthy,'proxy_host':self.proxy_host,'proxy_port':self.proxy_port,'socks5_noauth':healthy,'error':'' if healthy else f'unexpected greeting {reply!r}'}
        except Exception as exc:
            return {'healthy':False,'proxy_host':self.proxy_host,'proxy_port':self.proxy_port,'socks5_noauth':False,'error':f'{type(exc).__name__}: {exc}'}
    def fetch(self,url:str,*,max_bytes=524288,max_redirects=2)->TorFetchResult:
        if max_bytes<1024 or max_bytes>2*1024*1024: raise TorPolicyError('max_bytes must be between 1 KiB and 2 MiB')
        if max_redirects<0 or max_redirects>3: raise TorPolicyError('max_redirects must be between 0 and 3')
        requested=url; original_host=validate_onion_url(url)[1]; current=url
        for redirects in range(max_redirects+1):
            scheme,host,port,path=validate_onion_url(current)
            if host!=original_host: raise TorPolicyError('cross-host redirects are outside the approved Build 301 scope')
            status,headers,body=self._single_get(scheme,host,port,path,max_bytes=max_bytes)
            if status in (301,302,303,307,308):
                location=headers.get('location','').strip()
                if not location: raise TorGatewayError('redirect without Location header')
                if redirects>=max_redirects: raise TorGatewayError('redirect budget exhausted')
                current=urljoin(current,location); continue
            ctype=headers.get('content-type','').split(';',1)[0].strip().lower()
            if not ctype: raise TorPolicyError('response without Content-Type is not accepted in Build 301')
            if ctype not in _ALLOWED_MIME: raise TorPolicyError(f'blocked MIME type: {ctype}')
            if 'attachment' in headers.get('content-disposition','').lower(): raise TorPolicyError('attachment responses are blocked')
            return TorFetchResult(requested,current,status,headers,ctype,body,hashlib.sha256(body).hexdigest(),redirects,self.proxy_host,self.proxy_port)
        raise TorGatewayError('unreachable redirect state')
    def _single_get(self,scheme,host,port,path,*,max_bytes):
        s=socket.create_connection((self.proxy_host,self.proxy_port),timeout=self.connect_timeout); s.settimeout(self.read_timeout)
        try:
            self._socks_connect(s,host,port)
            if scheme=='https':
                ctx=ssl.create_default_context(); s=ctx.wrap_socket(s,server_hostname=host); s.settimeout(self.read_timeout)
            request=(f'GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: EagleEye/301 ReadOnlyDarknetResearch\r\nAccept: text/html,text/plain,application/json,application/xhtml+xml,application/xml,text/xml\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n').encode('ascii')
            s.sendall(request)
            head,rest=self._read_headers(s)
            status,headers=self._parse_headers(head)
            if 'content-length' in headers:
                try:
                    if int(headers['content-length'])>max_bytes: raise TorPolicyError('response exceeds approved byte budget')
                except ValueError: raise TorGatewayError('invalid Content-Length')
            if headers.get('transfer-encoding','').lower()=='chunked': body=self._read_chunked(s,rest,max_bytes)
            else: body=self._read_to_eof(s,rest,max_bytes)
            return status,headers,body
        finally:
            try:s.close()
            except Exception:pass
    def _socks_connect(self,s,host,port):
        s.sendall(b'\x05\x01\x00')
        if self._recv_exact(s,2)!=b'\x05\x00': raise TorGatewayError('SOCKS5 proxy did not accept no-auth negotiation')
        hb=host.encode('ascii')
        if len(hb)>255: raise TorPolicyError('host too long')
        s.sendall(b'\x05\x01\x00\x03'+bytes([len(hb)])+hb+int(port).to_bytes(2,'big'))
        head=self._recv_exact(s,4)
        if head[0]!=5 or head[1]!=0: raise TorGatewayError(f'SOCKS5 CONNECT failed with code {head[1] if len(head)>1 else -1}')
        atyp=head[3]
        if atyp==1:self._recv_exact(s,4)
        elif atyp==3:self._recv_exact(s,self._recv_exact(s,1)[0])
        elif atyp==4:self._recv_exact(s,16)
        else:raise TorGatewayError('invalid SOCKS5 bind address type')
        self._recv_exact(s,2)
    @staticmethod
    def _recv_exact(s,n):
        b=bytearray()
        while len(b)<n:
            chunk=s.recv(n-len(b))
            if not chunk:raise TorGatewayError('unexpected EOF')
            b.extend(chunk)
        return bytes(b)
    def _read_headers(self,s):
        buf=bytearray()
        while b'\r\n\r\n' not in buf:
            chunk=s.recv(4096)
            if not chunk:raise TorGatewayError('EOF before HTTP headers')
            buf.extend(chunk)
            if len(buf)>65536:raise TorGatewayError('HTTP headers exceed 64 KiB')
        head,rest=bytes(buf).split(b'\r\n\r\n',1); return head,rest
    @staticmethod
    def _parse_headers(raw):
        lines=raw.decode('iso-8859-1').split('\r\n')
        parts=lines[0].split(' ',2)
        if len(parts)<2 or not parts[1].isdigit(): raise TorGatewayError('invalid HTTP status line')
        headers={}
        for line in lines[1:]:
            if ':' not in line:continue
            k,v=line.split(':',1); headers[k.strip().lower()]=v.strip()
        return int(parts[1]),headers
    @staticmethod
    def _read_to_eof(s,initial,max_bytes):
        b=bytearray(initial)
        if len(b)>max_bytes:raise TorPolicyError('response exceeds approved byte budget')
        while True:
            chunk=s.recv(min(65536,max_bytes+1-len(b)))
            if not chunk:break
            b.extend(chunk)
            if len(b)>max_bytes:raise TorPolicyError('response exceeds approved byte budget')
        return bytes(b)
    def _read_chunked(self,s,initial,max_bytes):
        buf=bytearray(initial); out=bytearray()
        def need_line():
            while b'\r\n' not in buf:
                chunk=s.recv(4096)
                if not chunk:raise TorGatewayError('EOF in chunk header')
                buf.extend(chunk)
            line,_,rem=bytes(buf).partition(b'\r\n'); buf.clear(); buf.extend(rem); return line
        while True:
            line=need_line().split(b';',1)[0]
            try:size=int(line,16)
            except ValueError:raise TorGatewayError('invalid chunk size')
            if size==0:break
            while len(buf)<size+2:
                chunk=s.recv(min(65536,size+2-len(buf)))
                if not chunk:raise TorGatewayError('EOF in chunk body')
                buf.extend(chunk)
            out.extend(buf[:size]); del buf[:size+2]
            if len(out)>max_bytes:raise TorPolicyError('response exceeds approved byte budget')
        return bytes(out)
