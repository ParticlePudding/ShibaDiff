/* ページ表示・注釈（DocuWorks Viewer風） */
const PV = (() => {
  const SVGNS = 'http://www.w3.org/2000/svg';
  const wrap = $('#pvWrap'), cols = $$('.pv-col', wrap);
  const COLORS = ['#e53935', '#1e88e5', '#43a047', '#fb8c00', '#8e24aa', '#212121', '#fdd835'];
  const st = {
    tool: 'select', color: store.get('pv:color', '#e53935'), width: +store.get('pv:width', 2), zoom: store.get('pv:zoom', 'fitw'),
    rot: [0, 0], sides: [null, null], ann: [{}, {}], sel: null, dirty: [true, true], driver: null, driverTimer: 0
  };
  const scrollEl = side => $('.pv-scroll', cols[side]);

  /* ---------- annotations storage ---------- */
  const annKey = side => 'ann:' + S[side].key;
  /* ---------- 注釈データの検証（読み込んだJSONや保存データは信用しない） ---------- */
  const COLOR_RE = /^#[0-9a-fA-F]{3,8}$/;
  const num = (v, lo = -1e5, hi = 1e5) => { const n = Number(v); return Number.isFinite(n) ? Math.max(lo, Math.min(hi, n)) : null; };
  const str = (v, max = 2000) => (typeof v === 'string' ? v.slice(0, max) : '');
  const col = (v, def) => (typeof v === 'string' && COLOR_RE.test(v) ? v : def);
  function cleanAnnot(a) {
    if (!a || typeof a !== 'object') return null;
    const t = a.t;
    if (t === 'pen' || t === 'marker') {
      if (!Array.isArray(a.p)) return null;
      const p = a.p.slice(0, 20000).map(q => Array.isArray(q) ? [num(q[0]), num(q[1])] : null).filter(q => q && q[0] !== null && q[1] !== null);
      if (!p.length) return null;
      return { t, c: col(a.c, '#e53935'), w: num(a.w, 0.2, 40) || 2, p };
    }
    if (t === 'rect') {
      const x = num(a.x), y = num(a.y), w = num(a.w, 0), h = num(a.h, 0);
      if ([x, y, w, h].includes(null)) return null;
      return { t, c: col(a.c, '#e53935'), lw: num(a.lw, 0.2, 40) || 2, x, y, w, h };
    }
    if (t === 'note') {
      const x = num(a.x), y = num(a.y); if (x === null || y === null) return null;
      return { t, x, y, text: str(a.text), bg: col(a.bg, '#fff59d') };
    }
    if (t === 'stamp') {
      const x = num(a.x), y = num(a.y); if (x === null || y === null) return null;
      return { t, x, y, top: str(a.top, 40), date: str(a.date, 40), name: str(a.name, 40), c: col(a.c, '#d6281f'), kind: a.kind === 'name' ? 'name' : 'date', r: num(a.r, 12, 60) || 26 };
    }
    return null;
  }
  function cleanAnnMap(m) {
    const out = {};
    if (!m || typeof m !== 'object' || Array.isArray(m)) return out;
    for (const k of Object.keys(m)) {
      if (!/^\d{1,5}$/.test(k) || !Array.isArray(m[k])) continue;
      const arr = m[k].slice(0, 5000).map(cleanAnnot).filter(Boolean);
      if (arr.length) out[k] = arr;
    }
    return out;
  }
  // 「ブラウザに保存しない」設定のときは、開いている間だけメモリに持つ
  const mem = new Map();
  const persist = () => Settings.get('persist') !== false;
  function loadAnn(side) {
    if (!S[side]) { st.ann[side] = {}; st.rot[side] = 0; return; }
    const k = annKey(side);
    st.ann[side] = cleanAnnMap(mem.has(k) ? mem.get(k) : persist() ? store.get(k, {}) : {});
    st.rot[side] = mem.has('rot:' + S[side].key) ? mem.get('rot:' + S[side].key) : persist() ? store.get('rot:' + S[side].key, 0) : 0;
  }
  function saveRot(side) { if (!S[side]) return; mem.set('rot:' + S[side].key, st.rot[side]); if (persist()) store.set('rot:' + S[side].key, st.rot[side]); }
  function saveAnn(side) {
    if (!S[side]) return;
    const a = st.ann[side];
    const any = Object.values(a).some(x => x && x.length);
    mem.set(annKey(side), a);
    if (!persist()) return;
    if (any) store.set(annKey(side), a); else store.del(annKey(side));
  }
  const list = (side, i) => (st.ann[side][i] || (st.ann[side][i] = []));

  /* ---------- SVG for annotations ---------- */
  function textW(s, fs) { let w = 0; for (const ch of s) w += ch.charCodeAt(0) > 0x2E7F ? fs : fs * 0.58; return w; }
  function noteDims(a) {
    const lines = (a.text || '').split('\n'), fs = a.fs || 11;
    return { lines, fs, w: Math.max(40, Math.max(...lines.map(l => textW(l, fs))) + 14), h: lines.length * fs * 1.35 + 10 };
  }
  function bbox(a) {
    if (a.t === 'pen' || a.t === 'marker') {
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      for (const [x, y] of a.p) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
      const m = (a.t === 'marker' ? a.w * 3 : a.w) / 2 + 2; return { x: x0 - m, y: y0 - m, w: x1 - x0 + m * 2, h: y1 - y0 + m * 2 };
    }
    if (a.t === 'rect') return { x: a.x - 2, y: a.y - 2, w: a.w + 4, h: a.h + 4 };
    if (a.t === 'note') { const d = noteDims(a); return { x: a.x - 2, y: a.y - 2, w: d.w + 4, h: d.h + 4 }; }
    if (a.t === 'stamp') { const r = (a.r || 26) + 3; return { x: a.x - r, y: a.y - r, w: r * 2, h: r * 2 }; }
    return { x: 0, y: 0, w: 0, h: 0 };
  }
  function annSvg(raw, i, selected) {
    const a = cleanAnnot(raw); // 描画直前にも必ず検証（属性に入る値は色・数値のみ）
    if (!a) return '';
    let s = '';
    const pts = a.p ? a.p.map(([x, y]) => x.toFixed(1) + ',' + y.toFixed(1)).join(' ') : '';
    if (a.t === 'pen') {
      s = `<g data-i="${i}"><polyline points="${pts}" fill="none" stroke="transparent" stroke-width="${a.w + 8}" pointer-events="stroke"/>` +
        `<polyline points="${pts}" fill="none" stroke="${a.c}" stroke-width="${a.w}" stroke-linecap="round" stroke-linejoin="round" pointer-events="none"/></g>`;
    } else if (a.t === 'marker') {
      s = `<g data-i="${i}" style="mix-blend-mode:multiply"><polyline points="${pts}" fill="none" stroke="${a.c}" stroke-opacity=".38" stroke-width="${a.w * 3}" stroke-linecap="butt" stroke-linejoin="round" pointer-events="stroke"/></g>`;
    } else if (a.t === 'rect') {
      s = `<g data-i="${i}"><rect x="${a.x}" y="${a.y}" width="${a.w}" height="${a.h}" fill="none" stroke="transparent" stroke-width="${a.lw + 8}" pointer-events="stroke"/>` +
        `<rect x="${a.x}" y="${a.y}" width="${a.w}" height="${a.h}" fill="none" stroke="${a.c}" stroke-width="${a.lw}" pointer-events="none"/></g>`;
    } else if (a.t === 'note') {
      const d = noteDims(a);
      s = `<g data-i="${i}"><rect x="${a.x + 1.5}" y="${a.y + 1.5}" width="${d.w}" height="${d.h}" fill="rgba(0,0,0,.15)"/>` +
        `<rect x="${a.x}" y="${a.y}" width="${d.w}" height="${d.h}" fill="${a.bg || '#fff59d'}" stroke="#c9ad00" stroke-width=".6"/>` +
        `<text x="${a.x + 7}" y="${a.y + 5 + d.fs}" font-size="${d.fs}" fill="#222" font-family="BIZ UDPGothic,Meiryo,sans-serif">` +
        d.lines.map((l, k) => `<tspan x="${a.x + 7}" dy="${k ? d.fs * 1.35 : 0}">${esc(l) || ' '}</tspan>`).join('') + `</text></g>`;
    } else if (a.t === 'stamp') {
      const r = a.r || 26, k = r / 26, cx = a.x, cy = a.y, c = a.c || '#d6281f';
      const ch = d => 2 * Math.sqrt(Math.max(0, r * r - d * d));
      const fit = (t, base, w) => Math.max(4, Math.min(base, t ? w / (textW(t, 1) || 1) : base)); // 円からはみ出さない文字の大きさ
      const f = 'font-family="BIZ UDPGothic,Meiryo,sans-serif" text-anchor="middle" fill="' + c + '"';
      s = `<g data-i="${i}" style="mix-blend-mode:multiply"><circle cx="${cx}" cy="${cy}" r="${r}" fill="rgba(255,255,255,.01)" stroke="${c}" stroke-width="${1.6 * k}"/>`;
      if (a.kind === 'name') { // 認印：氏名だけ（4文字までは縦書き）
        const nm = Array.from(a.name || ''); const n = nm.length || 1;
        if (n <= 4) { const fs = Math.min(r * 0.95, (r * 1.6) / n); s += nm.map((ch1, j) => `<text x="${cx}" y="${cy - (n * fs) / 2 + fs * (j + 0.85)}" font-size="${fs}" font-weight="bold" ${f}>${esc(ch1)}</text>`).join(''); }
        else { const fs = fit(a.name, 10 * k, r * 1.7); s += `<text x="${cx}" y="${cy + fs * 0.35}" font-size="${fs}" font-weight="bold" ${f}>${esc(a.name)}</text>`; }
      } else { // 日付印：上段・日付・氏名
        const d1 = 8 * k;
        s += `<line x1="${cx - ch(d1) / 2}" y1="${cy - d1}" x2="${cx + ch(d1) / 2}" y2="${cy - d1}" stroke="${c}" stroke-width="${k}"/>` +
          `<line x1="${cx - ch(d1) / 2}" y1="${cy + d1}" x2="${cx + ch(d1) / 2}" y2="${cy + d1}" stroke="${c}" stroke-width="${k}"/>`;
        const fsT = fit(a.top, 9 * k, ch(13 * k) * 0.92), fsD = fit(a.date, 9.5 * k, ch(0) * 0.86), fsN = fit(a.name, 9 * k, ch(13 * k) * 0.92);
        s += `<text x="${cx}" y="${cy - 12 * k}" font-size="${fsT}" ${f}>${esc(a.top || '')}</text>` +
          `<text x="${cx}" y="${cy + fsD * 0.36}" font-size="${fsD}" font-weight="bold" ${f}>${esc(a.date || '')}</text>` +
          `<text x="${cx}" y="${cy + 12 * k + fsN * 0.75}" font-size="${fsN}" ${f}>${esc(a.name || '')}</text>`;
      }
      s += '</g>';
    }
    if (selected) { const b = bbox(a); s += `<rect class="selbox" x="${b.x - 2}" y="${b.y - 2}" width="${b.w + 4}" height="${b.h + 4}" pointer-events="none"/>`; }
    return s;
  }
  function drawAnn(side, i) {
    const sd = st.sides[side]; if (!sd || !sd.slots[i]) return;
    const arr = st.ann[side][i] || [];
    sd.slots[i].svg.innerHTML = arr.map((a, k) => annSvg(a, k, st.sel && st.sel.side === side && st.sel.page === i && st.sel.i === k)).join('');
  }
  function select(sel) {
    const old = st.sel; st.sel = sel;
    if (old) drawAnn(old.side, old.page);
    if (sel && (!old || old.side !== sel.side || old.page !== sel.page)) drawAnn(sel.side, sel.page);
  }

  /* ---------- building pages ---------- */
  function zoomFor(side) {
    const sd = st.sides[side]; if (!sd || !sd.pages.length) return 1;
    const sc = scrollEl(side), rot = st.rot[side] % 180 !== 0;
    if (st.zoom === 'fitw') {
      const maxW = Math.max(...sd.pages.map(p => rot ? p.h : p.w));
      return Math.max(0.1, (sc.clientWidth - 36) / maxW);
    }
    if (st.zoom === 'fitp') {
      const p = sd.pages[0], w = rot ? p.h : p.w, h = rot ? p.w : p.h;
      return Math.max(0.1, Math.min((sc.clientWidth - 36) / w, (sc.clientHeight - 50) / h));
    }
    return +st.zoom * 96 / 72;
  }
  let observers = [null, null];
  async function build(side) {
    st.dirty[side] = false;
    const col = cols[side], sc = scrollEl(side);
    if (observers[side]) observers[side].disconnect();
    sc.innerHTML = ''; st.sides[side] = null;
    if (st.sel && st.sel.side === side) st.sel = null;
    $('.nm', col).textContent = S[side] ? S[side].name : (side ? '右' : '左') + '（未読込）';
    $('.pvTotal', col).textContent = '/ 0';
    if (!S[side]) { sc.innerHTML = `<div class="pv-empty">${side ? '右' : '左'}のファイルが読み込まれていません<br>上の欄にドロップしてください</div>`; return; }
    let pages;
    try { pages = await S[side].getPages(); }
    catch (e) { sc.innerHTML = `<div class="pv-empty">ページを表示できません: ${esc(e.message || String(e))}</div>`; return; }
    loadAnn(side);
    const sd = st.sides[side] = { pages, slots: [], z: 1 };
    const frag = document.createDocumentFragment();
    pages.forEach((pg, i) => {
      const slot = document.createElement('div'); slot.className = 'pv-slot'; slot.dataset.i = i;
      const page = document.createElement('div'); page.className = 'pv-page';
      const cv = document.createElement('canvas');
      const svg = document.createElementNS(SVGNS, 'svg');
      svg.setAttribute('viewBox', `0 0 ${pg.w} ${pg.h}`); svg.setAttribute('preserveAspectRatio', 'none');
      const num = document.createElement('div'); num.className = 'pv-num'; num.textContent = `${i + 1} / ${pages.length}`;
      page.append(cv, svg); slot.append(page, num); frag.append(slot);
      sd.slots.push({ slot, page, cv, svg, pg, rendered: 0, busy: false, pending: false, visible: false });
      attachPointer(side, i, svg);
    });
    sc.append(frag);
    $('.pvTotal', col).textContent = '/ ' + pages.length;
    layout(side);
    sd.slots.forEach((_, i) => drawAnn(side, i));
    observers[side] = new IntersectionObserver(ents => {
      for (const en of ents) {
        const s = sd.slots[+en.target.dataset.i]; s.visible = en.isIntersecting;
        if (en.isIntersecting) renderSlot(side, +en.target.dataset.i);
        else if (s.rendered) { s.cv.width = 0; s.cv.height = 0; s.rendered = 0; }
      }
    }, { root: sc, rootMargin: '600px 0px' });
    sd.slots.forEach(s => observers[side].observe(s.slot));
  }
  function layout(side) {
    const sd = st.sides[side]; if (!sd) return;
    const z = zoomFor(side), rot = st.rot[side];
    sd.z = z;
    for (const s of sd.slots) {
      const w = s.pg.w * z, h = s.pg.h * z, sw = rot % 180 ? h : w, sh = rot % 180 ? w : h;
      s.slot.style.width = sw + 'px'; s.slot.style.height = sh + 'px';
      s.page.style.width = w + 'px'; s.page.style.height = h + 'px';
      s.page.style.transform = `translate(-50%,-50%) rotate(${rot}deg)`;
      if (s.visible) renderSlot(side, +s.slot.dataset.i);
    }
  }
  async function renderSlot(side, i) {
    const sd = st.sides[side]; if (!sd) return;
    const s = sd.slots[i];
    let scale = sd.z * (window.devicePixelRatio || 1);
    const maxPx = 4096 * 4096; if (s.pg.w * s.pg.h * scale * scale > maxPx) scale = Math.sqrt(maxPx / (s.pg.w * s.pg.h));
    if (Math.abs(s.rendered - scale) < 1e-3) return;
    if (s.busy) { s.pending = true; return; }
    s.busy = true;
    try { const ok = await s.pg.draw(s.cv, scale); if (ok !== false) s.rendered = scale; }
    catch (e) { console.warn('render failed', e); }
    finally { s.busy = false; }
    if (s.pending) { s.pending = false; if (st.sides[side] === sd && s.visible) renderSlot(side, i); }
  }

  /* ---------- pointer / tools ---------- */
  function pt(svg, e) {
    const p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY;
    return p.matrixTransform(svg.getScreenCTM().inverse());
  }
  function today() {
    const d = new Date(), mm = String(d.getMonth() + 1).padStart(2, '0'), dd = String(d.getDate()).padStart(2, '0');
    const fmt = Settings.get('dateFmt');
    if (fmt === 'yyyy') return `${d.getFullYear()}.${mm}.${dd}`;
    if (fmt === 'wareki') {
      try {
        const parts = new Intl.DateTimeFormat('ja-JP-u-ca-japanese', { era: 'narrow', year: 'numeric' }).formatToParts(d);
        const era = (parts.find(p => p.type === 'era') || {}).value || '', yr = (parts.find(p => p.type === 'year') || {}).value || '';
        return `${era}${yr}.${mm}.${dd}`;
      } catch (e) { /* 和暦が使えないブラウザは西暦にする */ }
    }
    return `'${String(d.getFullYear()).slice(2)}.${mm}.${dd}`;
  }
  const STAMP_R = { s: 20, m: 26, l: 34 };
  function attachPointer(side, i, svg) {
    let drag = null;
    svg.addEventListener('pointerdown', async e => {
      if (e.button !== 0) return;
      const tool = st.tool, p = pt(svg, e), target = e.target.closest('[data-i]');
      const arr = list(side, i);
      if (tool === 'select') {
        if (target) {
          const k = +target.dataset.i;
          if (!arr[k]) return;
          select({ side, page: i, i: k });
          drag = { mode: 'move', k, start: p, orig: JSON.parse(JSON.stringify(arr[k])) };
        } else {
          select(null);
          const sc = scrollEl(side);
          drag = { mode: 'pan', x: e.clientX, y: e.clientY, sl: sc.scrollLeft, st: sc.scrollTop };
        }
      } else if (tool === 'eraser') {
        if (target) { arr.splice(+target.dataset.i, 1); st.sel = null; drawAnn(side, i); saveAnn(side); }
        return;
      } else if (tool === 'pen' || tool === 'marker') {
        arr.push({ t: tool, c: tool === 'marker' && st.color === '#212121' ? '#fdd835' : st.color, w: st.width, p: [[p.x, p.y]] });
        drag = { mode: 'draw', k: arr.length - 1 };
      } else if (tool === 'rect') {
        arr.push({ t: 'rect', c: st.color, lw: st.width, x: p.x, y: p.y, w: 0, h: 0 });
        drag = { mode: 'rect', k: arr.length - 1, start: p };
      } else if (tool === 'note') {
        e.preventDefault();
        const text = await askText('付箋の内容を入力', '', { label: 'クリックした位置に付箋を貼ります（改行可）' });
        if (text && text.trim()) {
          const a = { t: 'note', x: p.x, y: p.y, text, bg: '#fff59d' }, pg = st.sides[side].pages[i], d = noteDims(a);
          a.x = Math.max(2, Math.min(a.x, pg.w - d.w - 4)); a.y = Math.max(2, Math.min(a.y, pg.h - d.h - 4)); // ページからはみ出さないように
          arr.push(a); drawAnn(side, i); saveAnn(side);
        }
        return;
      } else if (tool === 'stamp') {
        const pg = st.sides[side].pages[i];
        const r = STAMP_R[Settings.get('stampSize')] || 26;
        arr.push({ t: 'stamp', kind: Settings.get('stampKind'), r, x: Math.max(r + 2, Math.min(p.x, pg.w - r - 2)), y: Math.max(r + 2, Math.min(p.y, pg.h - r - 2)), top: Settings.get('stampTop'), name: Settings.get('stampName'), date: today(), c: '#d6281f' });
        drawAnn(side, i); saveAnn(side);

        return;
      }
      if (drag) { svg.setPointerCapture(e.pointerId); e.preventDefault(); }
    });
    svg.addEventListener('pointermove', e => {
      if (!drag) return;
      if (drag.mode === 'pan') {
        const sc = scrollEl(side); sc.scrollLeft = drag.sl - (e.clientX - drag.x); sc.scrollTop = drag.st - (e.clientY - drag.y); return;
      }
      const p = pt(svg, e), a = list(side, i)[drag.k]; if (!a) return;
      if (drag.mode === 'draw') {
        const last = a.p[a.p.length - 1];
        if (Math.hypot(p.x - last[0], p.y - last[1]) > 0.7) a.p.push([p.x, p.y]);
      } else if (drag.mode === 'rect') {
        a.x = Math.min(p.x, drag.start.x); a.y = Math.min(p.y, drag.start.y); a.w = Math.abs(p.x - drag.start.x); a.h = Math.abs(p.y - drag.start.y);
      } else if (drag.mode === 'move') {
        const dx = p.x - drag.start.x, dy = p.y - drag.start.y, o = drag.orig;
        if (a.p) a.p = o.p.map(([x, y]) => [x + dx, y + dy]); else { a.x = o.x + dx; a.y = o.y + dy; }
      }
      drawAnn(side, i);
    });
    const end = () => {
      if (!drag) return;
      const arr = list(side, i), a = arr[drag.k];
      if (drag.mode === 'rect' && a && (a.w < 2 || a.h < 2)) arr.splice(drag.k, 1);
      if (drag.mode === 'draw' && a && a.p.length === 1) a.p.push([a.p[0][0] + 0.5, a.p[0][1] + 0.5]);
      if (drag.mode !== 'pan') { drawAnn(side, i); saveAnn(side); }
      drag = null;
    };
    svg.addEventListener('pointerup', end);
    svg.addEventListener('pointercancel', end);
    svg.addEventListener('dblclick', async e => {
      const target = e.target.closest('[data-i]'); if (!target || st.tool !== 'select') return;
      const a = list(side, i)[+target.dataset.i];
      if (a.t === 'note') {
        const t = await askText('付箋を編集', a.text); if (t == null) return;
        if (!t.trim()) list(side, i).splice(+target.dataset.i, 1); else a.text = t;
      } else if (a.t === 'stamp') {
        const t = await askText('日付印を編集（上段 / 日付 / 名前 を改行区切り）', [a.top, a.date, a.name].join('\n')); if (t == null) return;
        [a.top, a.date, a.name] = t.split('\n').concat(['', '', '']);
      } else return;
      st.sel = null; drawAnn(side, i); saveAnn(side);
    });
  }
  function deleteSelected() {
    if (!st.sel) return false;
    const { side, page, i } = st.sel;
    list(side, page).splice(i, 1); st.sel = null; drawAnn(side, page); saveAnn(side); return true;
  }

  /* ---------- scroll / page indicator / sync ---------- */
  function currentPage(side) {
    const sd = st.sides[side]; if (!sd) return { i: 0, f: 0 };
    const sc = scrollEl(side), y = sc.scrollTop + 8;
    let lo = 0, hi = sd.slots.length - 1, best = 0;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (sd.slots[m].slot.offsetTop <= y) { best = m; lo = m + 1; } else hi = m - 1; }
    const s = sd.slots[best].slot;
    return { i: best, f: Math.max(0, Math.min(1, (y - s.offsetTop) / (s.offsetHeight + 14))) };
  }
  function goPage(side, i) {
    const sd = st.sides[side]; if (!sd) return;
    i = Math.max(0, Math.min(sd.slots.length - 1, i));
    scrollEl(side).scrollTop = sd.slots[i].slot.offsetTop - 10;
  }
  [0, 1].forEach(side => {
    const sc = scrollEl(side), col = cols[side];
    sc.addEventListener('scroll', () => {
      const cp = currentPage(side);
      const inp = $('.pvPage', col); if (document.activeElement !== inp) inp.value = cp.i + 1;
      if (!$('#pvSync').checked || st.driver === 1 - side) return;
      st.driver = side; clearTimeout(st.driverTimer); st.driverTimer = setTimeout(() => st.driver = null, 150);
      const o = 1 - side, osd = st.sides[o]; if (!osd || $('#pvShow').value !== 'both') return;
      const j = Math.min(cp.i, osd.slots.length - 1), os = osd.slots[j].slot;
      scrollEl(o).scrollTop = os.offsetTop - 8 + cp.f * (os.offsetHeight + 14);
      const r = sc.scrollWidth - sc.clientWidth, or = scrollEl(o).scrollWidth - scrollEl(o).clientWidth;
      if (r > 0 && or > 0) scrollEl(o).scrollLeft = sc.scrollLeft / r * or;
    }, { passive: true });
    $('.pvPrev', col).onclick = () => goPage(side, currentPage(side).i - 1);
    $('.pvNext', col).onclick = () => goPage(side, currentPage(side).i + 1);
    $('.pvPage', col).addEventListener('keydown', e => { if (e.key === 'Enter') { goPage(side, (parseInt(e.target.value, 10) || 1) - 1); e.target.blur(); } });
    $('.pvRot', col).onclick = () => {
      if (!S[side]) return;
      const cp = currentPage(side).i;
      st.rot[side] = (st.rot[side] + 90) % 360; saveRot(side);
      layout(side); goPage(side, cp);
    };
    $('.pvClearAnn', col).onclick = async () => {
      if (!S[side]) return;
      const n = Object.values(st.ann[side]).reduce((s, x) => s + (x ? x.length : 0), 0);
      if (!n) return toast('注釈はありません');
      const ok = await modal({ title: '注釈の削除', html: `「${esc(S[side].name)}」の注釈 ${n} 件をすべて削除しますか？`, buttons: [{ label: 'キャンセル', value: false }, { label: '削除する', primary: true, value: true }] });
      if (!ok) return;
      st.ann[side] = {}; st.sel = null; saveAnn(side); st.sides[side] && st.sides[side].slots.forEach((_, i) => drawAnn(side, i));
    };
  });
  let resizeTimer = 0;
  window.addEventListener('resize', () => {
    if (App.tab !== 'page' || !/^fit/.test(st.zoom)) return;
    clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { relayoutKeep(0); relayoutKeep(1); }, 120);
  });
  function relayoutKeep(side) {
    if (!st.sides[side]) return;
    const cp = currentPage(side); layout(side);
    const s = st.sides[side].slots[cp.i].slot; scrollEl(side).scrollTop = s.offsetTop - 8 + cp.f * (s.offsetHeight + 14);
  }

  /* ---------- toolbar ---------- */
  let stampAsked = false;
  function setTool(t) {
    if (t === 'stamp' && !Settings.get('stampName') && !stampAsked) { stampAsked = true; toast('日付印に入れる氏名を設定してください'); Settings.open('stamp'); }
    st.tool = t; wrap.dataset.tool = t;
    $$('#toolGrp .toolbtn').forEach(b => b.classList.toggle('on', b.dataset.tool === t));
    if (t !== 'select') select(null);
  }
  $$('#toolGrp .toolbtn').forEach(b => b.onclick = () => setTool(b.dataset.tool));
  const sw = $('#swatches');
  const CNAME = { '#e53935': '赤', '#1e88e5': '青', '#43a047': '緑', '#fb8c00': '橙', '#8e24aa': '紫', '#212121': '黒', '#fdd835': '黄' };
  sw.setAttribute('role', 'group'); sw.setAttribute('aria-label', '注釈の色');
  sw.innerHTML = COLORS.map(c => `<button type="button" data-c="${c}" style="background:${c}" title="${CNAME[c]}" aria-label="${CNAME[c]}"></button>`).join('');
  const markSw = () => $$('button', sw).forEach(s => { s.classList.toggle('on', s.dataset.c === st.color); s.setAttribute('aria-pressed', s.dataset.c === st.color); });
  sw.onclick = e => {
    const c = e.target.dataset && e.target.dataset.c; if (!c) return;
    st.color = c; store.set('pv:color', c); markSw();
    if (st.sel) { const a = list(st.sel.side, st.sel.page)[st.sel.i]; if (a && a.t !== 'note') { a.c = c; drawAnn(st.sel.side, st.sel.page); saveAnn(st.sel.side); } }
  };
  markSw();
  $('#annWidth').value = String(st.width);
  $('#annWidth').onchange = e => { st.width = +e.target.value; store.set('pv:width', st.width); };
  $('#stampCfg').onclick = () => Settings.open('stamp');
  const zSel = $('#zSel');
  zSel.value = st.zoom;
  function setZoom(z) {
    st.zoom = z; store.set('pv:zoom', z);
    if ([...zSel.options].some(o => o.value === String(z))) zSel.value = String(z);
    else { const o = document.createElement('option'); o.value = z; o.textContent = Math.round(z * 100) + '%'; zSel.appendChild(o); zSel.value = String(z); }
    relayoutKeep(0); relayoutKeep(1);
  }
  zSel.onchange = () => setZoom(zSel.value);
  const curPct = () => { const sd = st.sides[0] || st.sides[1]; return sd ? sd.z * 72 / 96 : 1; };
  const STEPS = [0.25, 0.33, 0.5, 0.67, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 4];
  $('#zIn').onclick = () => { const c = curPct(); setZoom(STEPS.find(s => s > c + 0.01) || 4); };
  $('#zOut').onclick = () => { const c = curPct(); setZoom([...STEPS].reverse().find(s => s < c - 0.01) || 0.25); };
  $('#pvShow').onchange = e => {
    const v = e.target.value;
    cols[0].classList.toggle('hide', v === '1'); cols[1].classList.toggle('hide', v === '0');
    relayoutKeep(0); relayoutKeep(1);
  };
  wrap.addEventListener('wheel', e => {
    if (!e.ctrlKey) return;
    e.preventDefault(); (e.deltaY < 0 ? $('#zIn') : $('#zOut')).click();
  }, { passive: false });

  /* ---------- export / import / print ---------- */
  $('#annExport').onclick = () => {
    const files = [0, 1].filter(s => S[s]).map(s => ({ side: s, name: S[s].name, size: S[s].size, rot: st.rot[s], annotations: st.ann[s] }));
    if (!files.length) return toast('ファイルが読み込まれていません');
    const n = files.reduce((t, f) => t + Object.values(f.annotations).reduce((s, x) => s + (x ? x.length : 0), 0), 0);
    if (!n) return toast('保存する注釈がありません');
    const withAnn = files.filter(f => Object.values(f.annotations).some(x => x && x.length));
    download(`注釈_${withAnn.map(f => baseName(f.name)).join('_')}.json`, JSON.stringify({ app: 'doc-compare', version: 1, files }, null, 1), 'application/json');
  };
  $('#annImport').onclick = () => $('#annFile').click();
  $('#annFile').onchange = async e => {
    const f = e.target.files[0]; e.target.value = ''; if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      let applied = 0;
      for (const fe of data.files || []) {
        if (!fe || typeof fe !== 'object') continue;
        fe.side = fe.side === 1 ? 1 : 0;
        let side = [0, 1].find(s => S[s] && S[s].name === fe.name);
        if (side === undefined && S[fe.side]) {
          const ok = await modal({ title: '注釈の読み込み', html: `注釈ファイルは「${esc(String(fe.name || ''))}」用ですが、${fe.side ? '右' : '左'}には「${esc(S[fe.side].name)}」が開かれています。<br>この文書に注釈を読み込みますか？`, buttons: [{ label: '読み込まない', value: false }, { label: '読み込む', primary: true, value: true }] });
          if (ok) side = fe.side;
        }
        if (side === undefined) continue;
        st.ann[side] = cleanAnnMap(fe.annotations); st.rot[side] = [0, 90, 180, 270].includes(fe.rot) ? fe.rot : 0; saveAnn(side); saveRot(side);
        applied++; await build(side);
      }
      toast(applied ? `注釈を読み込みました（${applied} ファイル）` : '対応するファイルが見つかりませんでした', !applied);
    } catch (err) { toast('注釈ファイルを読み込めません: ' + err.message, true); }
  };

  function svgImage(pg, arr) {
    return new Promise(res => {
      const inner = arr.map((a, k) => annSvg(a, k, false)).join('');
      const src = `<svg xmlns="${SVGNS}" viewBox="0 0 ${pg.w} ${pg.h}" width="${pg.w * 2}" height="${pg.h * 2}">${inner}</svg>`;
      const img = new Image();
      img.onload = () => res(img); img.onerror = () => res(null);
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(src);
    });
  }
  async function renderWithAnn(side, i, scale) {
    const sd = st.sides[side], pg = sd.pages[i];
    const base = document.createElement('canvas'); await pg.draw(base, scale);
    const arr = st.ann[side][i] || [];
    if (arr.length) { const img = await svgImage(pg, arr); if (img) { const bc = base.getContext('2d'); bc.setTransform(1, 0, 0, 1, 0, 0); bc.drawImage(img, 0, 0, base.width, base.height); } }
    const rot = st.rot[side]; if (!rot) return base;
    const out = document.createElement('canvas');
    out.width = rot % 180 ? base.height : base.width; out.height = rot % 180 ? base.width : base.height;
    const c = out.getContext('2d'); c.translate(out.width / 2, out.height / 2); c.rotate(rot * Math.PI / 180); c.drawImage(base, -base.width / 2, -base.height / 2);
    return out;
  }
  $('#pvPrint').onclick = async () => {
    const avail = [0, 1].filter(s => st.sides[s]);
    if (!avail.length) return toast('ファイルが読み込まれていません');
    let sides = avail;
    if (avail.length === 2) {
      const v = await modal({ title: '印刷 / PDF保存', html: 'どの文書を印刷しますか？<br><span class="muted">印刷ダイアログで「PDFに保存」を選ぶと、注釈入りのPDFとして保存できます。</span>', buttons: [{ label: 'キャンセル', value: null }, { label: '左のみ', value: [0] }, { label: '右のみ', value: [1] }, { label: '両方', primary: true, value: [0, 1] }] });
      if (!v) return; sides = v;
    }
    const area = $('#printArea'); area.innerHTML = '';
    const urls = [];
    await withBusy('印刷用に準備中…', async () => {
      for (const s of sides) {
        const sd = st.sides[s];
        for (let i = 0; i < sd.pages.length; i++) {
          $('#busyMsg').textContent = `印刷用に準備中… ${i + 1} / ${sd.pages.length}`;
          const cv = await renderWithAnn(s, i, Math.min(2.5, 2400 / Math.max(sd.pages[i].w, sd.pages[i].h)));
          const blob = await new Promise(r => cv.toBlob(r, 'image/jpeg', 0.92));
          const url = URL.createObjectURL(blob); urls.push(url);
          const img = new Image(); img.src = url; area.appendChild(img);
          await img.decode().catch(() => { });
        }
      }
    });
    const cleanup = () => { area.innerHTML = ''; urls.forEach(u => URL.revokeObjectURL(u)); window.removeEventListener('afterprint', cleanup); };
    window.addEventListener('afterprint', cleanup);
    window.print();
  };

  function activate() {
    if (window.innerWidth < 760 && $('#pvShow').value === 'both') {
      // 狭い画面では片側ずつ表示
      $('#pvShow').value = S[0] || !S[1] ? '0' : '1';
      $('#pvShow').dispatchEvent(new Event('change'));
    }
    for (const s of [0, 1]) if (st.dirty[s]) build(s);
    else relayoutKeep(s);
  }
  function invalidate(side) {
    st.dirty[side] = true;
    if (App.tab === 'page') build(side);
  }
  function onKey(e) {
    if ((e.key === 'Delete' || e.key === 'Backspace') && deleteSelected()) { e.preventDefault(); return true; }
    if (e.key === 'Escape') { setTool('select'); select(null); return true; }
    return false;
  }
  return { activate, invalidate, onKey, st };
})();
