from __future__ import annotations
from collections import Counter, defaultdict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class AdvancedGraphAnalytics96Service:
    """Build 96.0: advanced graph analytics with risk-focused clustering."""
    HIGH_RISK_EDGE_TYPES = {"same_as_candidate", "belongs_to_possible", "associated_with"}
    def __init__(self, db: Database, audit: AuditService):
        self.db=db; self.audit=audit; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS graph_analytics_96 (
          analysis_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, created_at TEXT NOT NULL,
          node_count INTEGER DEFAULT 0, edge_count INTEGER DEFAULT 0, risk_score INTEGER DEFAULT 0,
          findings_json TEXT NOT NULL, clusters_json TEXT NOT NULL, recommendations_json TEXT NOT NULL
        );"""); self.db.conn.commit()
    def analyze(self, case_id: str):
        nodes=self.db.all('SELECT * FROM investigation_graph_nodes_68 WHERE case_id=?',[case_id])
        edges=self.db.all('SELECT * FROM investigation_graph_edges_68 WHERE case_id=?',[case_id])
        type_counts=Counter(n.get('node_type','unknown') for n in nodes)
        edge_counts=Counter(e.get('edge_type','unknown') for e in edges)
        degree=Counter(); unresolved=[]; high_risk=[]; adj=defaultdict(set)
        for e in edges:
            degree[e['source_node_id']]+=1; degree[e['target_node_id']]+=1
            adj[e['source_node_id']].add(e['target_node_id']); adj[e['target_node_id']].add(e['source_node_id'])
            if e.get('review_status') in {'candidate','unreviewed','pending'}: unresolved.append(e['edge_id'])
            if e.get('edge_type') in self.HIGH_RISK_EDGE_TYPES and e.get('review_status') not in {'accepted','reviewed','confirmed'}:
                high_risk.append(e['edge_id'])
        hubs=[{'node_id': nid, 'degree': deg} for nid,deg in degree.most_common(10) if deg>=2]
        clusters=[]; seen=set()
        for n in nodes:
            start=n['node_id']
            if start in seen: continue
            stack=[start]; comp=[]; seen.add(start)
            while stack:
                cur=stack.pop(); comp.append(cur)
                for nxt in adj.get(cur,()):
                    if nxt not in seen:
                        seen.add(nxt); stack.append(nxt)
            if len(comp)>1: clusters.append({'cluster_id': f'cluster_{len(clusters)+1}', 'node_ids': comp, 'size': len(comp)})
        risk=min(100, len(unresolved)*8 + len(high_risk)*18 + max(0, len(hubs)-2)*5)
        findings={'node_type_counts':dict(type_counts),'edge_type_counts':dict(edge_counts),'unresolved_edge_ids':unresolved,'high_risk_edge_ids':high_risk,'hub_nodes':hubs,'risk_level':'high' if risk>=70 else 'medium' if risk>=35 else 'low'}
        rec=[]
        if high_risk: rec.append('Review high-risk identity/association edges before report export.')
        if unresolved: rec.append('Resolve candidate edges or keep them clearly labeled as hypotheses.')
        if not nodes: rec.append('Add graph nodes from public captures or pasted findings.')
        if not rec: rec.append('Graph appears ready for claim-layer review.')
        aid=new_id('ga96'); ts=now_ts()
        self.db.execute('INSERT INTO graph_analytics_96 VALUES(?,?,?,?,?,?,?,?,?)',[aid,case_id,ts,len(nodes),len(edges),risk,dumps(findings),dumps(clusters),dumps(rec)])
        self.audit.log('analyze','graph_analytics_96',aid,case_id,{'risk_score':risk,'node_count':len(nodes),'edge_count':len(edges)})
        return self.get(aid)
    def get(self, analysis_id: str):
        r=self.db.one('SELECT * FROM graph_analytics_96 WHERE analysis_id=?',[analysis_id])
        if not r: raise KeyError(analysis_id)
        r['findings']=loads(r.pop('findings_json','{}'),{}); r['clusters']=loads(r.pop('clusters_json','[]'),[]); r['recommendations']=loads(r.pop('recommendations_json','[]'),[])
        return r
    def latest(self, case_id: str):
        r=self.db.one('SELECT analysis_id FROM graph_analytics_96 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',[case_id])
        return self.get(r['analysis_id']) if r else self.analyze(case_id)
