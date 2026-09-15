from __future__ import annotations
import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

class InvestigationWorkspaceDesktop:
    """Case-centered Build 122 desktop shell.

    It intentionally delegates all domain decisions to the workspace service and
    only renders stored state. No candidate is promoted automatically.
    """
    def __init__(self, root: tk.Tk, context):
        self.root,self.context=root,context
        self.workspace=context.investigation_workspace_122
        self.root.title('EagleEye Build 123.0 – Adaptive Search & Obsidian Graph')
        self.root.geometry('1280x800')
        self.case_id=tk.StringVar()
        self.status=tk.StringVar(value='Select a case')
        self._build()
        self._load_cases()
    def _build(self):
        top=ttk.Frame(self.root,padding=8); top.pack(fill='x')
        ttk.Label(top,text='Case').pack(side='left')
        self.case_box=ttk.Combobox(top,textvariable=self.case_id,state='readonly',width=52); self.case_box.pack(side='left',padx=8)
        self.case_box.bind('<<ComboboxSelected>>',lambda _e:self.refresh())
        ttk.Button(top,text='Refresh',command=self.refresh).pack(side='left')
        ttk.Label(top,textvariable=self.status).pack(side='right')
        self.nav=ttk.Notebook(self.root); self.nav.pack(fill='both',expand=True,padx=8,pady=(0,8))
        self.views={}
        for key,title in [('overview','Overview'),('research','Research'),('intake','Intake'),('entities','Entities'),('evidence','Evidence'),('graph','Knowledge Graph'),('timeline','Timeline'),('contradictions','Contradictions'),('review','Review'),('export','Export'),('audit','Audit')]:
            frame=ttk.Frame(self.nav,padding=10); self.nav.add(frame,text=title)
            text=tk.Text(frame,wrap='word'); text.pack(fill='both',expand=True)
            self.views[key]=text
    def _load_cases(self):
        rows=self.context.db.all('SELECT case_id,title FROM cases ORDER BY updated_at DESC')
        self._case_map={f"{r['title']} [{r['case_id']}]":r['case_id'] for r in rows}
        self.case_box['values']=list(self._case_map)
        if rows:
            self.case_box.current(0); self.case_id.set(rows[0]['case_id']); self.refresh()
    def _selected_case(self):
        raw=self.case_box.get()
        return self._case_map.get(raw, self.case_id.get())
    def _show(self,key,value):
        w=self.views[key]; w.configure(state='normal'); w.delete('1.0','end'); w.insert('1.0',json.dumps(value,ensure_ascii=False,indent=2,default=str)); w.configure(state='disabled')
    def refresh(self):
        case_id=self._selected_case()
        if not case_id: return
        try:
            snap=self.workspace.case_snapshot(case_id)
            self._show('overview',snap)
            self._show('intake',self.workspace.intake(case_id,limit=200))
            for key,obj_type,table,idcol in [('entities','entity','resolution_entities_115','entity_id'),('evidence','evidence','evidence_packages_121','package_id'),('graph','relation','graph_relations_116','relation_id'),('timeline','timeline','timeline_events_117','event_id'),('contradictions','contradiction','contradictions_118','contradiction_id')]:
                rows=self.context.db.all(f'SELECT * FROM {table} WHERE case_id=? ORDER BY rowid DESC LIMIT 200',(case_id,)) if self.workspace._table(table) else []
                self._show(key,rows)
            self._show('research',{'open_search_tasks':snap['metrics']['open_search_tasks'],'next_actions':snap['next_actions']})
            self._show('review',{'pending_reviews':snap['metrics']['pending_reviews'],'next_actions':[a for a in snap['next_actions'] if a['section']=='review']})
            self._show('export',{'notice':'Exports require explicit Evidence Preservation policy approval and integrity verification.'})
            self._show('audit',self.workspace.recent_actions(case_id))
            self.status.set('Workspace refreshed')
        except Exception as exc:
            self.status.set('Refresh failed'); messagebox.showerror('EagleEye',str(exc))

EagleEyeDesktop=InvestigationWorkspaceDesktop

def run_desktop(base_dir: str | Path | None = None):
    from eagleeye_pro.core.app_context import AppContext
    root=tk.Tk(); ctx=AppContext(base_dir=base_dir)
    root.protocol('WM_DELETE_WINDOW',lambda:(ctx.close(),root.destroy()))
    InvestigationWorkspaceDesktop(root,ctx); root.mainloop()
