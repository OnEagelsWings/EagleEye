from __future__ import annotations

import hashlib
import html.parser
import ipaddress
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from eagleeye_pro.core.database import dumps, new_id, now_ts

_SENSITIVE_QUERY = {'token','access_token','api_key','key','password','secret','authorization','session','cookie'}
_ALLOWED_TYPES = ('text/html','application/xhtml+xml','application/json','text/plain','application/pdf','application/xml','text/xml')


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode('utf-8')).hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class _LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {'a','link','iframe'}:
            return
        data = dict(attrs)
        value = data.get('href') or data.get('src')
        if value:
            self.links.append(value)


@dataclass(frozen=True)
class CrawlResponse:
    status: int
    final_url: str
    headers: Mapping[str, str]
    body: bytes
    links: Sequence[str] = ()


class Build164ControlledCrawlingService:
    BUILD = '164.0'
    MISSION = 'Investigator-approved broad public-web crawling, replay and change detection'
    ABSOLUTE_LIMITS = {
        'max_pages': 100_000,
        'max_depth': 20,
        'max_runtime_seconds': 86_400,
        'max_hosts': 500,
        'max_bytes': 20 * 1024 * 1024 * 1024,
        'max_response_bytes': 100 * 1024 * 1024,
        'concurrency': 32,
        'min_host_delay_seconds': 0.25,
    }
    ROBOTS_MODES = {'strict','documented_override'}

    def __init__(self, db: Any, audit: Any, *, capture: Any | None = None,
                 observability: Any | None = None, actor: str = 'system',
                 archive_dir: str | Path | None = None) -> None:
        self.db = db
        self.audit = audit
        self.capture = capture
        self.observability = observability
        self.actor = actor
        self.archive_dir = Path(archive_dir or 'crawl_archive_164')
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def authorize(self, *, case_id: str, seed_urls: Sequence[str], allowed_hosts: Sequence[str],
                  purpose: str, approved_by: str, scope: Mapping[str, Any] | None = None,
                  robots_mode: str = 'strict', legal_basis: str | None = None,
                  expires_at: str | None = None, confirmation: str) -> dict[str, Any]:
        if confirmation != f'CRAWL 164 {case_id} AUTHORISIEREN':
            raise PermissionError('explicit investigator crawl authorization required')
        if not case_id.strip() or not purpose.strip() or not approved_by.strip():
            raise ValueError('case, purpose and approving investigator are required')
        if robots_mode not in self.ROBOTS_MODES:
            raise ValueError('invalid robots mode')
        if robots_mode == 'documented_override' and not (legal_basis and legal_basis.strip()):
            raise PermissionError('documented robots override requires a recorded legal basis')
        hosts = sorted({self._normalize_host(h) for h in allowed_hosts})
        if not hosts or len(hosts) > self.ABSOLUTE_LIMITS['max_hosts']:
            raise ValueError('invalid allowed host scope')
        seeds = [self._validate_url(u, hosts) for u in seed_urls]
        if not seeds:
            raise ValueError('at least one HTTPS seed URL is required')
        resolved = self._scope(scope or {})
        aid = new_id('crawlauth164')
        payload = {
            'authorization_id': aid, 'case_id': case_id, 'purpose': purpose,
            'approved_by': approved_by, 'seed_urls': seeds, 'allowed_hosts': hosts,
            'scope': resolved, 'robots_mode': robots_mode,
            'legal_basis': legal_basis, 'expires_at': expires_at,
            'public_only': True, 'no_auth_bypass': True, 'no_evasion': True,
        }
        self.db.execute('INSERT INTO crawl_authorizations_164 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(
            aid, case_id, purpose, approved_by, dumps(seeds), dumps(hosts), dumps(resolved),
            robots_mode, legal_basis, 'active', now_ts(), expires_at, _hash(payload)))
        self._event(None, case_id, 'crawl_authorized', aid, payload)
        return payload

    def _scope(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        defaults = {
            'max_pages': 10_000, 'max_depth': 10, 'max_runtime_seconds': 14_400,
            'max_bytes': 5 * 1024 * 1024 * 1024, 'max_response_bytes': 25 * 1024 * 1024,
            'concurrency': 12, 'min_host_delay_seconds': 0.5,
            'include_patterns': [], 'exclude_patterns': ['/login','/signin','/account','/checkout'],
            'allowed_content_types': list(_ALLOWED_TYPES),
            'follow_subdomains': False, 'query_policy': 'strip_tracking',
            'priority_terms': [], 'capture_external_links': False,
        }
        out = {**defaults, **dict(raw)}
        for key in ('max_pages','max_depth','max_runtime_seconds','max_bytes','max_response_bytes','concurrency'):
            out[key] = int(out[key])
            if out[key] < 1 or out[key] > self.ABSOLUTE_LIMITS[key]:
                raise ValueError(f'{key} outside permitted range')
        out['min_host_delay_seconds'] = float(out['min_host_delay_seconds'])
        if out['min_host_delay_seconds'] < self.ABSOLUTE_LIMITS['min_host_delay_seconds']:
            raise ValueError('per-host delay below safety floor')
        out['include_patterns'] = [str(x)[:300] for x in out.get('include_patterns', [])][:100]
        out['exclude_patterns'] = [str(x)[:300] for x in out.get('exclude_patterns', [])][:100]
        out['priority_terms'] = [str(x).casefold()[:100] for x in out.get('priority_terms', [])][:100]
        out['allowed_content_types'] = [x for x in out.get('allowed_content_types', []) if x in _ALLOWED_TYPES]
        if not out['allowed_content_types']:
            raise ValueError('no permitted content types')
        return out

    def start_run(self, authorization_id: str, *, confirmation: str,
                  correlation_id: str | None = None) -> dict[str, Any]:
        auth = self._auth(authorization_id)
        if confirmation != f'CRAWL 164 {authorization_id} STARTEN':
            raise PermissionError('explicit crawl start approval required')
        if auth['status'] != 'active':
            raise PermissionError('authorization is not active')
        if auth['expires_at'] and auth['expires_at'] < _utc():
            raise PermissionError('authorization expired')
        run_id = new_id('crawlrun164')
        payload = {'run_id':run_id,'authorization_id':authorization_id,'case_id':auth['case_id'],'status':'ready'}
        self.db.execute('INSERT INTO crawl_runs_164 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(
            run_id, authorization_id, auth['case_id'], 'ready', None, None, 0, 0, 0, 0,
            correlation_id, None, _hash(payload)))
        for url in json.loads(auth['seed_urls_json']):
            self._enqueue(run_id, url, depth=0, priority=100.0, parent_url=None)
        remaining = self._frontier_count(run_id)
        self.db.execute('UPDATE crawl_runs_164 SET frontier_remaining=? WHERE run_id=?',(remaining,run_id))
        self._event(run_id, auth['case_id'], 'crawl_run_created', run_id, {'frontier':remaining})
        return {'run_id':run_id,'status':'ready','frontier_remaining':remaining}

    def run_batch(self, run_id: str, fetcher: Callable[[str, Mapping[str, Any]], CrawlResponse | Mapping[str, Any]],
                  *, max_requests: int = 100, confirmation: str) -> dict[str, Any]:
        if confirmation != f'CRAWL 164 {run_id} AUSFUEHREN':
            raise PermissionError('explicit batch execution approval required')
        run = self._run(run_id); auth = self._auth(run['authorization_id'])
        scope = json.loads(auth['scope_json']); hosts = json.loads(auth['allowed_hosts_json'])
        if run['status'] in {'completed','cancelled','failed'}:
            raise RuntimeError('run is terminal')
        self.db.execute("UPDATE crawl_runs_164 SET status='running',started_at=COALESCE(started_at,?) WHERE run_id=?",(now_ts(),run_id))
        processed = stored = errors = 0
        while processed < max(1, min(int(max_requests), 10_000)):
            current = self.db.one("SELECT * FROM crawl_frontier_164 WHERE run_id=? AND status='queued' ORDER BY priority DESC, depth ASC, discovered_at ASC LIMIT 1",(run_id,))
            if not current: break
            if self._limits_reached(run_id, scope): break
            self.db.execute("UPDATE crawl_frontier_164 SET status='fetching',attempted_at=? WHERE frontier_id=?",(now_ts(),current['frontier_id']))
            processed += 1
            try:
                url = self._validate_url(current['url'], hosts)
                if self._excluded(url, scope):
                    self.db.execute("UPDATE crawl_frontier_164 SET status='excluded' WHERE frontier_id=?",(current['frontier_id'],)); continue
                robot = self._robots_decision(run_id, auth, url, fetcher)
                if robot['decision'] == 'disallowed':
                    self.db.execute("UPDATE crawl_frontier_164 SET status='robots_blocked' WHERE frontier_id=?",(current['frontier_id'],)); continue
                response = fetcher(url, {'timeout':30,'max_bytes':scope['max_response_bytes'],'user_agent':'EagleEye-PublicOSINT/164'})
                if isinstance(response, Mapping): response = CrawlResponse(**response)
                final_url = self._validate_url(response.final_url, hosts)
                body = bytes(response.body)
                if len(body) > scope['max_response_bytes']: raise ValueError('response exceeds approved size')
                ctype = str(response.headers.get('content-type','')).split(';',1)[0].lower()
                if ctype and ctype not in scope['allowed_content_types']: raise ValueError('content type outside approved scope')
                snap = self._store_snapshot(run_id, auth['case_id'], url, final_url, response)
                stored += 1
                self.db.execute("UPDATE crawl_frontier_164 SET status='fetched' WHERE frontier_id=?",(current['frontier_id'],))
                if int(current['depth']) < scope['max_depth'] and 200 <= response.status < 400:
                    links = list(response.links) or self._extract_links(final_url, body, ctype)
                    for link in links:
                        try:
                            candidate = self._validate_url(urljoin(final_url, link), hosts)
                            if not self._excluded(candidate, scope):
                                self._enqueue(run_id, candidate, int(current['depth'])+1,
                                              self._priority(candidate, scope, int(current['depth'])+1), final_url)
                        except (ValueError, PermissionError):
                            continue
            except Exception as exc:
                errors += 1
                self.db.execute("UPDATE crawl_frontier_164 SET status='error',error=? WHERE frontier_id=?",(str(exc)[:500],current['frontier_id']))
                self._event(run_id, auth['case_id'], 'crawl_fetch_error', current['frontier_id'], {'url_hash':_hash(current['url']),'error':str(exc)[:300]})
        remaining = self._frontier_count(run_id)
        totals = self.db.one('SELECT COUNT(*) n,COALESCE(SUM(LENGTH(body_sha256)),0) dummy FROM crawl_snapshots_164 WHERE run_id=?',(run_id,))
        byte_row = self.db.one('SELECT COALESCE(SUM(CAST(json_extract(change_summary_json,\'$.body_bytes\') AS INTEGER)),0) n FROM crawl_snapshots_164 WHERE run_id=?',(run_id,))
        status = 'completed' if remaining == 0 or self._limits_reached(run_id, scope) else 'paused'
        self.db.execute('UPDATE crawl_runs_164 SET status=?,finished_at=?,pages_fetched=?,bytes_fetched=?,errors=errors+?,frontier_remaining=? WHERE run_id=?',(
            status, now_ts() if status=='completed' else None, int(totals['n']), int(byte_row['n']), errors, remaining, run_id))
        result={'run_id':run_id,'status':status,'processed':processed,'snapshots_stored':stored,'errors':errors,'frontier_remaining':remaining}
        self._event(run_id, auth['case_id'], 'crawl_batch_finished', run_id, result)
        return result

    def replay(self, snapshot_id: str) -> dict[str, Any]:
        row=self.db.one('SELECT * FROM crawl_snapshots_164 WHERE snapshot_id=?',(snapshot_id,))
        if not row: raise KeyError('snapshot not found')
        path=Path(row['body_path'])
        body=path.read_bytes()
        valid=hashlib.sha256(body).hexdigest()==row['body_sha256']
        return {'snapshot_id':snapshot_id,'url':row['final_url'],'content_type':row['content_type'],
                'body':body,'integrity_valid':valid,'body_sha256':row['body_sha256'],
                'fetched_at':row['fetched_at'],'chain_sha256':row['chain_sha256']}

    def change_history(self, case_id: str, url: str) -> list[dict[str, Any]]:
        canonical=self._canonical_url(url)
        rows=self.db.all('SELECT * FROM crawl_snapshots_164 WHERE case_id=? AND final_url=? ORDER BY fetched_at',(case_id,canonical))
        return [dict(r) for r in rows]

    def pause(self, run_id: str) -> None:
        self.db.execute("UPDATE crawl_runs_164 SET status='paused' WHERE run_id=? AND status IN ('ready','running')",(run_id,))

    def cancel(self, run_id: str, *, confirmation: str) -> None:
        if confirmation != f'CRAWL 164 {run_id} ABBRECHEN': raise PermissionError('explicit cancellation required')
        self.db.execute("UPDATE crawl_runs_164 SET status='cancelled',finished_at=? WHERE run_id=?",(now_ts(),run_id))

    def _store_snapshot(self, run_id: str, case_id: str, url: str, final_url: str, response: CrawlResponse) -> dict[str, Any]:
        body_hash=hashlib.sha256(response.body).hexdigest(); previous=self.db.one('SELECT * FROM crawl_snapshots_164 WHERE case_id=? AND final_url=? ORDER BY fetched_at DESC LIMIT 1',(case_id,final_url))
        changed=1 if previous and previous['body_sha256']!=body_hash else 0
        sid=new_id('crawlsnap164'); folder=self.archive_dir/case_id/run_id;folder.mkdir(parents=True,exist_ok=True)
        path=folder/f'{sid}.bin';path.write_bytes(response.body)
        summary={'body_bytes':len(response.body),'changed_from_previous':bool(changed),'previous_sha256':previous['body_sha256'] if previous else None}
        prov={'requested_url_hash':_hash(url),'final_url_hash':_hash(final_url),'public_only':True,'http_status':response.status,'captured_by':'build164'}
        previous_chain=previous['chain_sha256'] if previous else ''
        chain=_hash({'previous':previous_chain,'snapshot_id':sid,'body_sha256':body_hash,'fetched_at':_utc()})
        self.db.execute('INSERT INTO crawl_snapshots_164 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
            sid,run_id,case_id,url,final_url,urlsplit(final_url).hostname,int(response.status),str(response.headers.get('content-type','')),
            now_ts(),str(path.resolve()),body_hash,dumps({str(k).lower():str(v)[:1000] for k,v in response.headers.items()}),
            previous['snapshot_id'] if previous else None,changed,dumps(summary),dumps(prov),chain))
        return {'snapshot_id':sid,'changed':bool(changed),'body_sha256':body_hash}

    def _robots_decision(self, run_id: str, auth: Mapping[str, Any], url: str, fetcher: Callable) -> dict[str, Any]:
        host=urlsplit(url).hostname or ''
        existing=self.db.one('SELECT * FROM robots_observations_164 WHERE run_id=? AND host=?',(run_id,host))
        if existing:return dict(existing)
        robots_url=f'https://{host}/robots.txt';status=None;body=b'';rules={};allowed=True
        try:
            resp=fetcher(robots_url,{'timeout':15,'max_bytes':1024*1024,'user_agent':'EagleEye-PublicOSINT/164'})
            if isinstance(resp,Mapping):resp=CrawlResponse(**resp)
            status=resp.status;body=bytes(resp.body)
            rp=RobotFileParser();rp.set_url(robots_url);rp.parse(body.decode('utf-8','replace').splitlines())
            allowed=rp.can_fetch('EagleEye-PublicOSINT/164',url)
            rules={'parsed':True,'allowed':allowed}
        except Exception as exc:
            rules={'parsed':False,'error':str(exc)[:200]};allowed=True
        override=not allowed and auth['robots_mode']=='documented_override'
        decision='allowed' if allowed or override else 'disallowed'
        oid=new_id('robots164');payload={'host':host,'decision':decision,'override_used':override,'legal_basis':auth['legal_basis'] if override else None}
        self.db.execute('INSERT INTO robots_observations_164 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(
            oid,run_id,host,robots_url,now_ts(),status,hashlib.sha256(body).hexdigest() if body else None,decision,dumps(rules),1 if override else 0,auth['legal_basis'] if override else None,_hash(payload)))
        return payload

    def _extract_links(self, base: str, body: bytes, content_type: str) -> list[str]:
        if content_type not in {'text/html','application/xhtml+xml'}:return []
        parser=_LinkParser();parser.feed(body.decode('utf-8','replace'))
        return [urljoin(base,x) for x in parser.links[:10000]]

    def _priority(self, url: str, scope: Mapping[str, Any], depth: int) -> float:
        score=50.0-depth
        low=url.casefold()
        score += 10.0*sum(1 for term in scope.get('priority_terms',[]) if term and term in low)
        return score

    def _enqueue(self, run_id: str, url: str, depth: int, priority: float, parent_url: str | None) -> None:
        c=self._canonical_url(url);host=urlsplit(c).hostname or ''
        self.db.execute('INSERT OR IGNORE INTO crawl_frontier_164 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(
            new_id('frontier164'),run_id,c,c,host,depth,float(priority),parent_url,'queued',now_ts(),None,None))

    def _excluded(self, url: str, scope: Mapping[str, Any]) -> bool:
        p=urlsplit(url);path=p.path or '/'
        includes=scope.get('include_patterns',[]);excludes=scope.get('exclude_patterns',[])
        if includes and not any(re.search(x,path) for x in includes):return True
        return any(re.search(x,path) for x in excludes)

    def _limits_reached(self, run_id: str, scope: Mapping[str, Any]) -> bool:
        row=self.db.one('SELECT COUNT(*) n,COALESCE(SUM(CAST(json_extract(change_summary_json,\'$.body_bytes\') AS INTEGER)),0) b FROM crawl_snapshots_164 WHERE run_id=?',(run_id,))
        return int(row['n'])>=scope['max_pages'] or int(row['b'])>=scope['max_bytes']

    def _frontier_count(self, run_id: str) -> int:
        return int(self.db.one("SELECT COUNT(*) n FROM crawl_frontier_164 WHERE run_id=? AND status='queued'",(run_id,))['n'])

    def _auth(self, aid: str) -> Mapping[str, Any]:
        row=self.db.one('SELECT * FROM crawl_authorizations_164 WHERE authorization_id=?',(aid,))
        if not row:raise KeyError('crawl authorization not found')
        return row

    def _run(self, rid: str) -> Mapping[str, Any]:
        row=self.db.one('SELECT * FROM crawl_runs_164 WHERE run_id=?',(rid,))
        if not row:raise KeyError('crawl run not found')
        return row

    def _normalize_host(self, host: str) -> str:
        h=host.strip().lower().rstrip('.')
        if '://' in h:h=urlsplit(h).hostname or ''
        if not h or '/' in h or '@' in h:raise ValueError('invalid host')
        try:
            ip=ipaddress.ip_address(h)
            if not ip.is_global:raise PermissionError('non-public IP targets are forbidden')
        except ValueError:
            if h in {'localhost','localhost.localdomain'} or h.endswith('.local'):raise PermissionError('local targets are forbidden')
        return h

    def _validate_url(self, url: str, allowed_hosts: Sequence[str]) -> str:
        p=urlsplit(str(url).strip())
        if p.scheme!='https' or not p.hostname:raise PermissionError('HTTPS public URLs only')
        if p.username or p.password:raise PermissionError('embedded credentials forbidden')
        host=self._normalize_host(p.hostname)
        allowed=host in allowed_hosts or any(host.endswith('.'+base) for base in allowed_hosts)
        if not allowed:raise PermissionError('host outside investigator-approved scope')
        safe=[]
        for k,v in parse_qsl(p.query,keep_blank_values=True):
            if k.casefold() in _SENSITIVE_QUERY:raise PermissionError('sensitive query parameter forbidden')
            if k.casefold().startswith(('utm_','fbclid','gclid')):continue
            safe.append((k,v))
        return urlunsplit(('https',host,p.path or '/',urlencode(sorted(safe)),''))

    def _canonical_url(self, url: str) -> str:
        p=urlsplit(url);q=urlencode(sorted(parse_qsl(p.query,keep_blank_values=True)))
        path=re.sub('/+','/',p.path or '/')
        return urlunsplit((p.scheme.lower(),(p.hostname or '').lower(),path,q,''))

    def _event(self, run_id: str | None, case_id: str, event_type: str, entity_id: str | None, details: Mapping[str, Any]) -> None:
        prev=self.db.one('SELECT event_hash FROM crawl_events_164 WHERE case_id=? ORDER BY created_at DESC,event_id DESC LIMIT 1',(case_id,))
        previous=prev['event_hash'] if prev else None;eid=new_id('crawlevt164');created=now_ts()
        event_hash=_hash({'event_id':eid,'run_id':run_id,'case_id':case_id,'type':event_type,'entity_id':entity_id,'details':details,'created_at':created,'previous':previous})
        self.db.execute('INSERT INTO crawl_events_164 VALUES(?,?,?,?,?,?,?,?,?)',(eid,run_id,case_id,event_type,entity_id,dumps(details),created,previous,event_hash))
        try:self.audit.log(f'{event_type}_164','controlled_crawling',entity_id or case_id,case_id,dict(details))
        except Exception:pass
