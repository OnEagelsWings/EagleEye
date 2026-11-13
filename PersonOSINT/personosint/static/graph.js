/* Interaktiver Netzwerkgraph (Canvas, Kraftsimulation) – ohne externe Bibliotheken. */
(function () {
  "use strict";
  const COLORS = {
    person: "#2563eb", organisation: "#7c3aed", ort: "#059669", konto: "#ea580c", telefon: "#db2777",
    email: "#ca8a04", fahrzeug: "#475569", ereignis: "#dc2626", dokument: "#64748b", domain: "#0891b2", sonstiges: "#94a3b8",
  };

  class NetworkGraph {
    constructor(canvas, opts = {}) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.opts = opts;
      this.nodes = []; this.edges = []; this.byId = new Map();
      this.view = { x: 0, y: 0, k: 1 };
      this.hidden = new Set(); this.minConf = 0;
      this.selected = null; this.hover = null; this.hoverEdge = null;
      this.pathNodes = new Set(); this.pathEdges = new Set();
      this.alpha = 1; this.running = false;
      this._bind();
      this._resize();
      this._ro = new ResizeObserver(() => { this._resize(); this.draw(); });
      this._ro.observe(canvas.parentElement);
    }

    static colors() { return COLORS; }

    destroy() {
      this._ro.disconnect(); this.running = false;
      window.removeEventListener("mousemove", this._onMove); window.removeEventListener("mouseup", this._onUp);
    }

    setData(nodes, edges) {
      const old = this.byId;
      const w = this.W || 800, h = this.H || 600;
      this.nodes = nodes.map((n, i) => {
        const prev = old.get(n.id);
        const a = (2 * Math.PI * i) / Math.max(1, nodes.length);
        return Object.assign({}, n, {
          x: prev ? prev.x : w / 2 + Math.cos(a) * Math.min(w, h) * 0.3 + Math.random() * 10,
          y: prev ? prev.y : h / 2 + Math.sin(a) * Math.min(w, h) * 0.3 + Math.random() * 10,
          vx: 0, vy: 0, fixed: prev ? prev.fixed : false,
          r: 9 + Math.min(16, n.degree * 2.2) + (n.subject ? 7 : 0),
        });
      });
      this.byId = new Map(this.nodes.map((n) => [n.id, n]));
      this.edges = edges.filter((e) => this.byId.has(e.source) && this.byId.has(e.target));
      if (!old.size) this.view = { x: 0, y: 0, k: 1 };
      this.reheat(old.size ? 0.5 : 1);
    }

    visibleNode(n) { return !this.hidden.has(n.type); }
    visibleEdge(e) {
      return e.confidence >= this.minConf && this.visibleNode(this.byId.get(e.source)) && this.visibleNode(this.byId.get(e.target));
    }

    setFilter(hiddenTypes, minConf) { this.hidden = new Set(hiddenTypes); this.minConf = minConf; this.draw(); }

    highlightPath(ids) {
      this.pathNodes = new Set(ids || []);
      this.pathEdges = new Set();
      if (ids) for (let i = 0; i < ids.length - 1; i++) this.pathEdges.add(this._key(ids[i], ids[i + 1]));
      this.draw();
    }

    select(id, center) {
      this.selected = id == null ? null : this.byId.get(id) || null;
      if (center && this.selected) this.centerOn(this.selected);
      this.draw();
    }

    centerOn(n) {
      this.view.x = this.W / 2 - n.x * this.view.k;
      this.view.y = this.H / 2 - n.y * this.view.k;
    }

    focusLabel(q) {
      q = (q || "").toLowerCase().trim();
      if (!q) return null;
      const n = this.nodes.find((x) => x.label.toLowerCase().includes(q));
      if (n) { this.select(n.id, true); if (this.opts.onSelect) this.opts.onSelect(n); }
      return n;
    }

    fit() {
      const vis = this.nodes.filter((n) => this.visibleNode(n));
      if (!vis.length) return;
      const xs = vis.map((n) => n.x), ys = vis.map((n) => n.y);
      const minX = Math.min(...xs) - 80, maxX = Math.max(...xs) + 80, minY = Math.min(...ys) - 60, maxY = Math.max(...ys) + 70;
      const k = Math.min(2, Math.min(this.W / (maxX - minX || 1), this.H / (maxY - minY || 1)));
      this.view.k = k;
      this.view.x = (this.W - (maxX + minX) * k) / 2;
      this.view.y = (this.H - (maxY + minY) * k) / 2;
      this.draw();
    }

    relayout() {
      this.nodes.forEach((n) => { n.fixed = false; n.x = this.W / 2 + (Math.random() - 0.5) * this.W * 0.6; n.y = this.H / 2 + (Math.random() - 0.5) * this.H * 0.6; });
      this._fitAfter = true;
      this.reheat(1);
    }

    reheat(a) {
      this.alpha = Math.max(this.alpha, a);
      if (!this.running) { this.running = true; this._fitAfter = this._fitAfter || a >= 1; requestAnimationFrame(() => this._tick()); }
    }

    _tick() {
      if (!this.running) return;
      for (let i = 0; i < 3; i++) this._step();
      this.draw();
      if (this.alpha > 0.02) requestAnimationFrame(() => this._tick());
      else { this.running = false; if (this._fitAfter) { this._fitAfter = false; this.fit(); } }
    }

    _step() {
      const ns = this.nodes, a = this.alpha, cx = this.W / 2, cy = this.H / 2;
      for (let i = 0; i < ns.length; i++) {
        const p = ns[i];
        for (let j = i + 1; j < ns.length; j++) {
          const q = ns[j];
          let dx = p.x - q.x, dy = p.y - q.y, d2 = dx * dx + dy * dy;
          if (d2 < 0.01) { dx = Math.random(); dy = Math.random(); d2 = 1; }
          const f = (2600 * a) / d2;
          const d = Math.sqrt(d2);
          p.vx += (dx / d) * f; p.vy += (dy / d) * f; q.vx -= (dx / d) * f; q.vy -= (dy / d) * f;
        }
        p.vx += (cx - p.x) * 0.004 * a; p.vy += (cy - p.y) * 0.004 * a;
      }
      for (const e of this.edges) {
        const s = this.byId.get(e.source), t = this.byId.get(e.target);
        const dx = t.x - s.x, dy = t.y - s.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
        const target = 110 + (s.r + t.r);
        const f = (d - target) * 0.04 * a;
        s.vx += (dx / d) * f; s.vy += (dy / d) * f; t.vx -= (dx / d) * f; t.vy -= (dy / d) * f;
      }
      for (const n of ns) {
        if (n.fixed || n === this.dragNode) { n.vx = n.vy = 0; continue; }
        n.vx *= 0.6; n.vy *= 0.6;
        n.x += Math.max(-30, Math.min(30, n.vx)); n.y += Math.max(-30, Math.min(30, n.vy));
      }
      this.alpha *= 0.985;
    }

    _key(a, b) { return a < b ? a + "-" + b : b + "-" + a; }

    _resize() {
      const r = this.canvas.parentElement.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      this.W = r.width; this.H = r.height;
      this.canvas.width = r.width * dpr; this.canvas.height = r.height * dpr;
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    _neighbours(n) {
      const s = new Set([n.id]);
      for (const e of this.edges) { if (e.source === n.id) s.add(e.target); if (e.target === n.id) s.add(e.source); }
      return s;
    }

    draw() {
      const c = this.ctx, v = this.view;
      c.save();
      c.clearRect(0, 0, this.W, this.H);
      c.translate(v.x, v.y); c.scale(v.k, v.k);
      const focus = this.pathNodes.size ? this.pathNodes : (this.selected ? this._neighbours(this.selected) : null);
      const showLabels = v.k > 0.75;
      for (const e of this.edges) {
        if (!this.visibleEdge(e)) continue;
        const s = this.byId.get(e.source), t = this.byId.get(e.target);
        const onPath = this.pathEdges.has(this._key(e.source, e.target));
        const dim = focus && !(focus.has(s.id) && focus.has(t.id)) && !onPath;
        c.globalAlpha = dim ? 0.12 : 1;
        c.strokeStyle = onPath ? "#eab308" : e === this.hoverEdge ? "#1d4ed8" : e.confidence >= 50 ? "#94a3b8" : "#cbd5e1";
        c.lineWidth = (onPath ? 4 : 1 + e.confidence / 40) / Math.max(0.6, v.k * 0.9);
        c.setLineDash(e.confidence < 50 ? [6, 5] : []);
        c.beginPath(); c.moveTo(s.x, s.y); c.lineTo(t.x, t.y); c.stroke();
        if ((showLabels && !dim) || onPath || e === this.hoverEdge) {
          const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2;
          c.setLineDash([]);
          c.font = `${11 / Math.max(1, v.k * 0.8)}px system-ui, sans-serif`;
          const txt = e.relation;
          const w = c.measureText(txt).width + 6;
          c.fillStyle = "rgba(255,255,255,.9)"; c.fillRect(mx - w / 2, my - 8, w, 15);
          c.fillStyle = onPath ? "#854d0e" : "#475569"; c.textAlign = "center"; c.textBaseline = "middle";
          c.fillText(txt, mx, my);
        }
      }
      c.setLineDash([]);
      for (const n of this.nodes) {
        if (!this.visibleNode(n)) continue;
        const dim = focus && !focus.has(n.id);
        c.globalAlpha = dim ? 0.2 : 1;
        if (this.pathNodes.has(n.id) || n === this.selected) {
          c.beginPath(); c.arc(n.x, n.y, n.r + 6, 0, 2 * Math.PI); c.fillStyle = this.pathNodes.has(n.id) ? "#fde047" : "#bfdbfe"; c.fill();
        }
        c.beginPath(); c.arc(n.x, n.y, n.r, 0, 2 * Math.PI);
        c.fillStyle = COLORS[n.type] || "#94a3b8"; c.fill();
        c.lineWidth = n.subject ? 4 : 2; c.strokeStyle = n.subject ? "#0f172a" : "#fff"; c.stroke();
        if (n.subject) {
          c.fillStyle = "#facc15"; c.font = `bold ${n.r}px system-ui`; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText("★", n.x, n.y + 1);
        }
        if (showLabels || n.subject || n === this.hover || n === this.selected || this.pathNodes.has(n.id)) {
          const fs = (n.subject ? 14 : 12) / Math.max(1, v.k * 0.8);
          c.font = `${n.subject ? "bold " : ""}${fs}px system-ui, sans-serif`;
          const label = n.label.length > 32 ? n.label.slice(0, 31) + "…" : n.label;
          const w = c.measureText(label).width + 8;
          c.fillStyle = "rgba(255,255,255,.92)"; c.fillRect(n.x - w / 2, n.y + n.r + 3, w, fs + 5);
          c.fillStyle = "#0f172a"; c.textAlign = "center"; c.textBaseline = "top"; c.fillText(label, n.x, n.y + n.r + 5);
        }
      }
      c.restore();
    }

    _toWorld(ev) {
      const r = this.canvas.getBoundingClientRect();
      return { x: (ev.clientX - r.left - this.view.x) / this.view.k, y: (ev.clientY - r.top - this.view.y) / this.view.k, sx: ev.clientX - r.left, sy: ev.clientY - r.top };
    }

    _hit(p) {
      for (let i = this.nodes.length - 1; i >= 0; i--) {
        const n = this.nodes[i];
        if (!this.visibleNode(n)) continue;
        if ((n.x - p.x) ** 2 + (n.y - p.y) ** 2 <= (n.r + 4) ** 2) return n;
      }
      return null;
    }

    _hitEdge(p) {
      let best = null, bd = 7 / this.view.k;
      for (const e of this.edges) {
        if (!this.visibleEdge(e)) continue;
        const s = this.byId.get(e.source), t = this.byId.get(e.target);
        const dx = t.x - s.x, dy = t.y - s.y, l2 = dx * dx + dy * dy || 1;
        const u = Math.max(0, Math.min(1, ((p.x - s.x) * dx + (p.y - s.y) * dy) / l2));
        const d = Math.hypot(p.x - (s.x + u * dx), p.y - (s.y + u * dy));
        if (d < bd) { bd = d; best = e; }
      }
      return best;
    }

    _bind() {
      const cv = this.canvas;
      let panning = null, moved = false;
      cv.addEventListener("mousedown", (ev) => {
        const p = this._toWorld(ev); moved = false;
        const n = this._hit(p);
        if (n) { this.dragNode = n; cv.classList.add("dragging"); }
        else panning = { x: ev.clientX - this.view.x, y: ev.clientY - this.view.y };
      });
      this._onMove = (ev) => {
        if (!this.canvas.isConnected) return;
        const p = this._toWorld(ev);
        if (this.dragNode) { moved = true; this.dragNode.x = p.x; this.dragNode.y = p.y; this.dragNode.fixed = true; this.reheat(0.15); this.draw(); return; }
        if (panning) { moved = true; this.view.x = ev.clientX - panning.x; this.view.y = ev.clientY - panning.y; this.draw(); return; }
        if (ev.target !== cv) return;
        const n = this._hit(p);
        const e = n ? null : this._hitEdge(p);
        if (n !== this.hover || e !== this.hoverEdge) { this.hover = n; this.hoverEdge = e; this.draw(); }
        const tip = this.opts.tooltip;
        if (tip) {
          if (n) { tip.innerHTML = `<b>${esc(n.label)}</b><br>${esc(n.type_label)} · ${n.degree} Verbindungen`; }
          else if (e) { tip.innerHTML = `<b>${esc(this.byId.get(e.source).label)}</b> — ${esc(e.relation)} → <b>${esc(this.byId.get(e.target).label)}</b><br>Sicherheit ${e.confidence} %${e.evidence ? "<br>" + esc(e.evidence) : ""}`; }
          tip.style.display = n || e ? "block" : "none";
          tip.style.left = Math.min(p.sx + 14, this.W - 270) + "px"; tip.style.top = p.sy + 14 + "px";
        }
      };
      this._onUp = (ev) => {
        if (!this.canvas.isConnected) return;
        const wasDrag = this.dragNode;
        if (!moved && (wasDrag || panning) && ev.target === cv) {
          const n = wasDrag || null;
          this.selected = n; this.draw();
          if (this.opts.onSelect) this.opts.onSelect(n);
        }
        this.dragNode = null; panning = null; cv.classList.remove("dragging");
      };
      window.addEventListener("mousemove", this._onMove);
      window.addEventListener("mouseup", this._onUp);
      cv.addEventListener("dblclick", (ev) => {
        const n = this._hit(this._toWorld(ev));
        if (n) { n.fixed = false; this.reheat(0.3); }
      });
      cv.addEventListener("mouseleave", () => { if (this.opts.tooltip) this.opts.tooltip.style.display = "none"; });
      cv.addEventListener("wheel", (ev) => {
        ev.preventDefault();
        const p = this._toWorld(ev);
        const k = Math.max(0.15, Math.min(4, this.view.k * (ev.deltaY < 0 ? 1.12 : 1 / 1.12)));
        this.view.x = p.sx - p.x * k; this.view.y = p.sy - p.y * k; this.view.k = k;
        this.draw();
      }, { passive: false });
      // Touch: Ein-Finger-Verschieben
      let touch = null;
      cv.addEventListener("touchstart", (ev) => {
        if (ev.touches.length !== 1) return;
        const t = ev.touches[0]; const p = this._toWorld(t);
        const n = this._hit(p);
        touch = { n, x: t.clientX - this.view.x, y: t.clientY - this.view.y, moved: false };
      }, { passive: true });
      cv.addEventListener("touchmove", (ev) => {
        if (!touch || ev.touches.length !== 1) return;
        ev.preventDefault();
        const t = ev.touches[0]; touch.moved = true;
        if (touch.n) { const p = this._toWorld(t); touch.n.x = p.x; touch.n.y = p.y; touch.n.fixed = true; }
        else { this.view.x = t.clientX - touch.x; this.view.y = t.clientY - touch.y; }
        this.draw();
      }, { passive: false });
      cv.addEventListener("touchend", () => {
        if (touch && !touch.moved) { this.selected = touch.n; this.draw(); if (this.opts.onSelect) this.opts.onSelect(touch.n); }
        touch = null;
      });
    }

    toPNG() { return this.canvas.toDataURL("image/png"); }
  }

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  window.NetworkGraph = NetworkGraph;
})();
