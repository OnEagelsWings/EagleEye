from __future__ import annotations
from pathlib import Path
from html import escape
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class GraphUI76Service:
    def __init__(self, db: Database, audit: AuditService, out_dir: str | Path, graph: Any):
        self.db=db; self.audit=audit; self.out_dir=Path(out_dir); self.out_dir.mkdir(parents=True, exist_ok=True); self.graph=graph; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS graph_ui_exports_76 (
          export_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, html_path TEXT NOT NULL, markdown_path TEXT NOT NULL,
          node_count INTEGER DEFAULT 0, edge_count INTEGER DEFAULT 0, created_at TEXT NOT NULL, metadata_json TEXT NOT NULL);
        """); self.db.conn.commit()
    def render(self, case_id: str, title: str='Investigation Graph', persist: bool=True) -> Dict[str, Any]:
        g=self.graph.build_graph(case_id); nodes=g.get('nodes',[]); edges=g.get('edges',[]); metrics=g.get('metrics',{})
        rows=''.join(f"<tr><td>{escape(n.get('node_type',''))}</td><td>{escape(n.get('label',''))}</td><td>{n.get('confidence',0)}</td><td>{escape(n.get('sensitivity',''))}</td></tr>" for n in nodes)
        erows=''.join(f"<tr><td>{escape(e.get('edge_type',''))}</td><td>{escape(e.get('source_node_id',''))}</td><td>{escape(e.get('target_node_id',''))}</td><td>{escape(e.get('review_status','candidate'))}</td><td>{e.get('confidence',0)}</td></tr>" for e in edges)
        html=f"<!doctype html><meta charset='utf-8'><title>{escape(title)}</title><h1>{escape(title)}</h1><p>Case: {escape(case_id)}</p><h2>Metriken</h2><pre>{escape(dumps(metrics))}</pre><h2>Knoten</h2><table border='1'><tr><th>Typ</th><th>Label</th><th>Confidence</th><th>Sensitivity</th></tr>{rows}</table><h2>Kanten</h2><table border='1'><tr><th>Typ</th><th>Quelle</th><th>Ziel</th><th>Review</th><th>Confidence</th></tr>{erows}</table>"
        md='\n'.join([f"# {title}", f"Case: `{case_id}`", '', f"Nodes: {len(nodes)}", f"Edges: {len(edges)}", '', '## Review-Hinweis', 'Candidate-Kanten sind keine Fakten und müssen manuell geprüft werden.'])
        export_id=new_id('gui76'); html_path=self.out_dir/f'{case_id}_{export_id}.html'; md_path=self.out_dir/f'{case_id}_{export_id}.md'
        html_path.write_text(html, encoding='utf-8'); md_path.write_text(md, encoding='utf-8')
        if persist:
            self.db.execute('INSERT INTO graph_ui_exports_76(export_id,case_id,html_path,markdown_path,node_count,edge_count,created_at,metadata_json) VALUES(?,?,?,?,?,?,?,?)',[export_id,case_id,str(html_path),str(md_path),len(nodes),len(edges),now_ts(),dumps(metrics)])
            self.audit.log('render','graph_ui_76',export_id,case_id,{'node_count':len(nodes),'edge_count':len(edges)})
        return {'export_id':export_id,'case_id':case_id,'html_path':str(html_path),'markdown_path':str(md_path),'node_count':len(nodes),'edge_count':len(edges),'metrics':metrics}
    def latest(self, case_id: str) -> Dict[str, Any]:
        return self.db.one('SELECT * FROM graph_ui_exports_76 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',[case_id]) or {}
