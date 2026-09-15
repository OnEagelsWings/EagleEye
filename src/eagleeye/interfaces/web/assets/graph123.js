(() => {
  'use strict';
  const root = document.getElementById('graph123');
  if (!root) return;
  const svg = root.querySelector('svg');
  const viewport = svg.querySelector('.graph-viewport');
  const edgesLayer = svg.querySelector('.graph-edges');
  const nodesLayer = svg.querySelector('.graph-nodes');
  const detail = document.getElementById('graph-detail');
  const search = document.getElementById('graph-search');
  const reset = document.getElementById('graph-reset');
  const fit = document.getElementById('graph-fit');
  const caseId = root.dataset.caseId;
  const typeColors = {
    person:'#61dafb', alias:'#b388ff', username:'#7aa2f7', email:'#ff9e64', domain:'#73daca',
    organization:'#9ece6a', location:'#e0af68', source:'#7dcfff', evidence:'#bb9af7',
    document:'#c0caf5', finding:'#f7768e', claim:'#ff7a93', repository:'#2ac3de', default:'#8aa3c2'
  };
  let nodes = [], edges = [], transform = {x:0,y:0,k:1}, dragging = null, panning = null;

  function esc(s){ return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function color(t){ return typeColors[t] || typeColors.default; }
  function applyTransform(){ viewport.setAttribute('transform', `translate(${transform.x} ${transform.y}) scale(${transform.k})`); }
  function clientPoint(evt){ const r=svg.getBoundingClientRect(); return {x:evt.clientX-r.left,y:evt.clientY-r.top}; }
  function graphPoint(evt){ const p=clientPoint(evt); return {x:(p.x-transform.x)/transform.k,y:(p.y-transform.y)/transform.k}; }

  function showDetail(n){
    detail.innerHTML = `<div class="graph-detail-type">${esc(n.type)}</div><h3>${esc(n.label)}</h3>`+
      `<p>${esc(n.value || '')}</p><dl><dt>Konfidenz</dt><dd>${esc(n.confidence)}</dd><dt>Status</dt><dd>${n.candidate?'candidate_only':'reviewed'}</dd><dt>Quelle</dt><dd>${esc(n.source||'')}</dd><dt>ID</dt><dd><code>${esc(n.id)}</code></dd></dl>`;
  }

  function render(){
    edgesLayer.replaceChildren(); nodesLayer.replaceChildren();
    const byId = new Map(nodes.map(n => [n.id,n]));
    for (const e of edges){
      const a=byId.get(e.source), b=byId.get(e.target); if(!a||!b) continue;
      const line=document.createElementNS('http://www.w3.org/2000/svg','line');
      line.setAttribute('class','graph-edge'); line.dataset.source=e.source; line.dataset.target=e.target;
      line.setAttribute('x1',a.x); line.setAttribute('y1',a.y); line.setAttribute('x2',b.x); line.setAttribute('y2',b.y);
      line.style.opacity = e.candidate ? '.34' : '.64'; edgesLayer.appendChild(line);
    }
    for (const n of nodes){
      const g=document.createElementNS('http://www.w3.org/2000/svg','g'); g.setAttribute('class','graph-node');
      g.setAttribute('transform',`translate(${n.x} ${n.y})`); g.dataset.id=n.id;
      const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');
      circle.setAttribute('r', n.type==='person'?10:n.type==='evidence'?8:6); circle.setAttribute('fill',color(n.type));
      circle.setAttribute('class',n.candidate?'candidate':'reviewed');
      const text=document.createElementNS('http://www.w3.org/2000/svg','text'); text.setAttribute('x','12'); text.setAttribute('y','4');
      text.textContent=n.label.length>34?n.label.slice(0,34)+'…':n.label;
      g.append(circle,text); g.addEventListener('pointerdown',evt=>{evt.stopPropagation(); dragging=n; g.setPointerCapture(evt.pointerId);});
      g.addEventListener('click',evt=>{evt.stopPropagation(); showDetail(n); selectNode(n.id);});
      nodesLayer.appendChild(g);
    }
  }

  function updatePositions(){
    const byId=new Map(nodes.map(n=>[n.id,n]));
    [...edgesLayer.children].forEach((line,i)=>{const e=edges[i],a=byId.get(e.source),b=byId.get(e.target);if(a&&b){line.setAttribute('x1',a.x);line.setAttribute('y1',a.y);line.setAttribute('x2',b.x);line.setAttribute('y2',b.y);}});
    [...nodesLayer.children].forEach((g,i)=>g.setAttribute('transform',`translate(${nodes[i].x} ${nodes[i].y})`));
  }

  function layout(){
    const w=Math.max(900,svg.clientWidth), h=Math.max(620,svg.clientHeight); const byId=new Map(nodes.map(n=>[n.id,n]));
    nodes.forEach((n,i)=>{const a=(i/Math.max(1,nodes.length))*Math.PI*2; const ring=130+45*(i%5); n.x=w/2+Math.cos(a)*ring; n.y=h/2+Math.sin(a)*ring; n.vx=0;n.vy=0;});
    let steps=0;
    function tick(){
      const alpha=Math.max(.025,1-steps/260);
      for(let i=0;i<nodes.length;i++) for(let j=i+1;j<nodes.length;j++){
        const a=nodes[i],b=nodes[j],dx=a.x-b.x,dy=a.y-b.y,d2=Math.max(80,dx*dx+dy*dy),f=(1700/d2)*alpha;
        a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f;
      }
      for(const e of edges){const a=byId.get(e.source),b=byId.get(e.target);if(!a||!b)continue;const dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),desired=85+(e.candidate?30:0),f=(d-desired)*.006*alpha;a.vx+=dx/d*f;a.vy+=dy/d*f;b.vx-=dx/d*f;b.vy-=dy/d*f;}
      for(const n of nodes){n.vx+=(w/2-n.x)*.0008*alpha;n.vy+=(h/2-n.y)*.0008*alpha;n.vx*=.84;n.vy*=.84;n.x+=n.vx;n.y+=n.vy;}
      updatePositions(); steps++; if(steps<260) requestAnimationFrame(tick); else fitGraph();
    }
    requestAnimationFrame(tick);
  }

  function selectNode(id){
    [...nodesLayer.children].forEach(g=>g.classList.toggle('selected',g.dataset.id===id));
    [...edgesLayer.children].forEach(l=>l.classList.toggle('connected',l.dataset.source===id||l.dataset.target===id));
  }
  function filterGraph(){
    const q=(search.value||'').trim().toLowerCase();
    [...nodesLayer.children].forEach((g,i)=>{const n=nodes[i]; const hit=!q||`${n.label} ${n.value} ${n.type}`.toLowerCase().includes(q); g.classList.toggle('dimmed',!hit);});
  }
  function fitGraph(){
    if(!nodes.length)return; const xs=nodes.map(n=>n.x),ys=nodes.map(n=>n.y),minX=Math.min(...xs)-70,maxX=Math.max(...xs)+150,minY=Math.min(...ys)-70,maxY=Math.max(...ys)+70;
    const w=svg.clientWidth,h=svg.clientHeight,k=Math.min(1.5,Math.max(.18,Math.min(w/(maxX-minX),h/(maxY-minY))*.9));
    transform={k,x:(w-(minX+maxX)*k)/2,y:(h-(minY+maxY)*k)/2};applyTransform();
  }

  svg.addEventListener('pointerdown',evt=>{if(evt.target===svg||evt.target.classList.contains('graph-bg'))panning={...clientPoint(evt),ox:transform.x,oy:transform.y};});
  svg.addEventListener('pointermove',evt=>{if(dragging){const p=graphPoint(evt);dragging.x=p.x;dragging.y=p.y;dragging.vx=0;dragging.vy=0;updatePositions();}else if(panning){const p=clientPoint(evt);transform.x=panning.ox+p.x-panning.x;transform.y=panning.oy+p.y-panning.y;applyTransform();}});
  svg.addEventListener('pointerup',()=>{dragging=null;panning=null;}); svg.addEventListener('pointercancel',()=>{dragging=null;panning=null;});
  svg.addEventListener('wheel',evt=>{evt.preventDefault();const p=clientPoint(evt),old=transform.k,next=Math.max(.15,Math.min(3.5,old*(evt.deltaY<0?1.12:.89)));transform.x=p.x-(p.x-transform.x)*(next/old);transform.y=p.y-(p.y-transform.y)*(next/old);transform.k=next;applyTransform();},{passive:false});
  search.addEventListener('input',filterGraph); reset.addEventListener('click',()=>{search.value='';filterGraph();selectNode('');}); fit.addEventListener('click',fitGraph);

  fetch(`/api/graph123?case_id=${encodeURIComponent(caseId)}`,{credentials:'same-origin'})
    .then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();})
    .then(data=>{nodes=data.nodes||[];edges=data.edges||[];document.getElementById('graph-count').textContent=`${nodes.length} Knoten · ${edges.length} Kanten`;render();layout();})
    .catch(err=>{detail.innerHTML=`<div class="notice error">Graph konnte nicht geladen werden: ${esc(err.message)}</div>`;});
})();
