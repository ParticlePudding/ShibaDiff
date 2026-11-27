/* ページ表示・注釈（DocuWorks Viewer風） */
const PV = (() => {
  const SVGNS = 'http://www.w3.org/2000/svg';
  const wrap = $('#pvWrap'), cols = $$('.pv-col', wrap);
  const COLORS = ['#e53935', '#1e88e5', '#43a047', '#fb8c00', '#8e24aa', '#212121', '#fdd835'];
  const st = {
    tool: 'select', color: '#e53935', width: +store.get('pv:width', 2), zoom: store.get('pv:zoom', 'fitw'),
    rot: [0, 0], sides: [null, null], ann: [{}, {}], sel: null, dirty: [true, true], expect: [null, null],
    // 道具ごとの色（マーカーは黄色の蛍光ペン、枠は印影の赤と見分けやすい青、付箋は黄色）
    toolColor: Object.assign({ pen: '#e53935', marker: '#fdd835', rect: '#1e88e5', note: '#fdd835' }, store.get('pv:toolColor', {})),
    undo: [], redo: []
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
      const fs = num(a.fs, 6, 200);
      return Object.assign({ t, x, y, text: str(a.text), bg: col(a.bg, '#fff59d') }, fs ? { fs } : {});
    }
    // 日付印（stamp）は v1.2.0 で廃止。古い注釈に残っていても読み込まない
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
  // 付箋は全角20文字ほどの幅で折り返す（本文を横に長く隠さない・ページからはみ出さない）
  function noteDims(a) {
    const fs = a.fs || 11, maxW = fs * 20, lines = [];
    for (const raw of (a.text || '').split('\n')) {
      let cur = '', w = 0;
      for (const ch of raw) { const cw = textW(ch, fs); if (w + cw > maxW && cur) { lines.push(cur); cur = ''; w = 0; } cur += ch; w += cw; }
      lines.push(cur);
    }
    return { lines, fs, w: Math.max(fs * 4, Math.max(...lines.map(l => textW(l, fs))) + fs * 1.3), h: lines.length * fs * 1.35 + fs * 0.9 };
  }
  // 付箋の文字の大きさ：ページの大きさに合わせる（A4 で 11pt、A1 の図面でも読める大きさ）
  const noteFs = pg => Math.round(Math.max(11, Math.min(60, pg.w / 54)) * 10) / 10;
  function bbox(a) {
    if (a.t === 'pen' || a.t === 'marker') {
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      for (const [x, y] of a.p) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
      const m = (a.t === 'marker' ? a.w * 5 : a.w) / 2 + 2; return { x: x0 - m, y: y0 - m, w: x1 - x0 + m * 2, h: y1 - y0 + m * 2 };
    }
    if (a.t === 'rect') return { x: a.x - 2, y: a.y - 2, w: a.w + 4, h: a.h + 4 };
    if (a.t === 'note') { const d = noteDims(a); return { x: a.x - 2, y: a.y - 2, w: d.w + 4, h: d.h + 4 }; }
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
      s = `<g data-i="${i}" style="mix-blend-mode:multiply"><polyline points="${pts}" fill="none" stroke="${a.c}" stroke-opacity=".38" stroke-width="${a.w * 5}" stroke-linecap="butt" stroke-linejoin="round" pointer-events="stroke"/></g>`;
    } else if (a.t === 'rect') {
      s = `<g data-i="${i}"><rect x="${a.x}" y="${a.y}" width="${a.w}" height="${a.h}" fill="none" stroke="transparent" stroke-width="${a.lw + 8}" pointer-events="stroke"/>` +
        `<rect x="${a.x}" y="${a.y}" width="${a.w}" height="${a.h}" fill="none" stroke="${a.c}" stroke-width="${a.lw}" pointer-events="none"/></g>`;
    } else if (a.t === 'note') {
      const d = noteDims(a);
      s = `<g data-i="${i}"><rect x="${a.x + 1.5}" y="${a.y + 1.5}" width="${d.w}" height="${d.h}" fill="rgba(0,0,0,.15)"/>` +
        `<rect x="${a.x}" y="${a.y}" width="${d.w}" height="${d.h}" fill="${a.bg || '#fff59d'}" stroke="#c9ad00" stroke-width=".6"/>` +
        `<text x="${a.x + d.fs * 0.6}" y="${a.y + d.fs * 0.35 + d.fs}" font-size="${d.fs}" fill="#222" font-family="BIZ UDPGothic,Meiryo,sans-serif">` +
        d.lines.map((l, k) => `<tspan x="${a.x + d.fs * 0.6}" dy="${k ? d.fs * 1.35 : 0}">${esc(l) || ' '}</tspan>`).join('') + `</text></g>`;
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
      const chg = document.createElementNS(SVGNS, 'svg'); chg.setAttribute('class', 'pv-chg');
      chg.setAttribute('viewBox', `0 0 ${pg.w} ${pg.h}`); chg.setAttribute('preserveAspectRatio', 'none');
      page.append(cv, svg, chg); slot.append(page, num); frag.append(slot);
      sd.slots.push({ slot, page, cv, svg, chg, pg, rendered: 0, busy: false, pending: false, visible: false });
      attachPointer(side, i, svg);
    });
    sc.append(frag);
    $('.pvTotal', col).textContent = '/ ' + pages.length;
    layout(side);
    sd.slots.forEach((_, i) => drawAnn(side, i));
    observers[side] = new IntersectionObserver(ents => {
      for (const en of ents) {
        const s = sd.slots[+en.target.dataset.i]; s.visible = en.isIntersecting;
        if (en.isIntersecting) { renderSlot(side, +en.target.dataset.i); drawChanges(side, +en.target.dataset.i); }
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
      if (s.visible) { renderSlot(side, +s.slot.dataset.i); drawChanges(side, +s.slot.dataset.i); }
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

  /* ---------- 変更箇所の表示（重ね合わせの結果）とコメント ---------- */
  st.showChg = !!store.get('pvChanges', true);
  const chgBtn = $('#pvChanges');
  const syncChgBtn = () => { chgBtn.classList.toggle('on', st.showChg); chgBtn.setAttribute('aria-pressed', st.showChg); };
  syncChgBtn();
  chgBtn.onclick = () => { st.showChg = !st.showChg; store.set('pvChanges', st.showChg); syncChgBtn(); redrawChanges(); };
  const pagePairs = () => {
    const nl = st.sides[0] ? st.sides[0].pages.length : 0, nr = st.sides[1] ? st.sides[1].pages.length : 0;
    return PageMatch.ready() || Array.from({ length: Math.max(nl, nr) }, (_, i) => ({ l: i < nl ? i : -1, r: i < nr ? i : -1 }));
  };
  // そのページの組（左右とも読み込み、反対側に対応するページがあるとき）
  function pairOf(side, i) { const p = pagePairs().find(q => (side ? q.r : q.l) === i); return p && p.l >= 0 && p.r >= 0 ? p : null; }
  const NCOL = { ok: '#2f9e44', ask: '#d9480f', '': '#f08c00' };
  function chgSvg(info, side, z) {
    const fs = 12 / z, sw = 2 / z, pad = 3 / z;
    return info.regions.map((g, k) => {
      const b = info.toPt(side, g), id = info.ids[k], nv = Notes.get(id), col = NCOL[nv ? nv.st : ''];
      const lab = `${k + 1}${nv && nv.st === 'ok' ? ' ✓' : nv && nv.st === 'ask' ? ' !' : ''}${nv && nv.text ? '  ' + (nv.text.length > 40 ? nv.text.slice(0, 40) + '…' : nv.text) : ''}`;
      const lw = Math.max(fs * 1.4, Array.from(lab).reduce((w, c) => w + (c.charCodeAt(0) > 255 ? fs : fs * 0.6), 0) + pad * 2), lh = fs * 1.45;
      return `<g class="cb" data-k="${k}"><rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" fill="none" stroke="${col}" stroke-width="${sw}" stroke-dasharray="${4 / z} ${2 / z}"/>` +
        `<rect class="cb-lab" x="${b.x}" y="${b.y - lh}" width="${lw}" height="${lh}" rx="${pad}" fill="${col}"/>` +
        `<text x="${b.x + pad}" y="${b.y - lh + fs * 1.1}" font-size="${fs}" fill="#fff" font-weight="700" font-family="BIZ UDPGothic,Meiryo,sans-serif">${esc(lab)}</text></g>`;
    }).join('');
  }
  async function drawChanges(side, i) {
    const sd = st.sides[side]; if (!sd || !sd.slots[i]) return;
    const s = sd.slots[i];
    if (!st.showChg || !st.sides[0] || !st.sides[1] || !s.visible || App.tab !== 'page') { if (!st.showChg) s.chg.innerHTML = ''; return; }
    const p = pairOf(side, i); if (!p) { s.chg.innerHTML = ''; return; }
    const info = await OV.regionsFor(p.l, p.r);
    if (!info || st.sides[side] !== sd || !st.showChg) return;
    s.chg.innerHTML = chgSvg(info, side, sd.z);
    s.chgInfo = info;
  }
  function redrawChanges() {
    for (const side of [0, 1]) { const sd = st.sides[side]; if (!sd) continue; sd.slots.forEach((s, i) => { if (!st.showChg) s.chg.innerHTML = ''; else if (s.visible) drawChanges(side, i); }); }
  }
  Notes.on(() => { if (App.tab === 'page' && st.showChg) redrawChanges(); });
  // 枠の番号をクリック → コメントの入力欄を、その枠の近くに出す
  const pop = document.createElement('div'); pop.id = 'pvNotePop'; pop.hidden = true; document.body.appendChild(pop);
  function openNotePop(side, i, k, x, y) {
    const s = st.sides[side].slots[i], info = s.chgInfo; if (!info) return;
    const g = info.regions[k];
    pop.innerHTML = `<div class="pop-h"><b>変更箇所 ${k + 1}</b><span class="muted">左 ${info.l + 1} ／ 右 ${info.r + 1} ページ</span><button type="button" class="x" aria-label="閉じる"><i data-i="x"></i></button></div>`;
    pop.querySelector('.x').onclick = () => { pop.hidden = true; };
    pop.appendChild(Notes.editor(info.ids[k], `左 ${info.l + 1} ページ ／ 右 ${info.r + 1} ページ　変更箇所 ${k + 1}（${info.pos(g)}）`, { onEscape: () => { pop.hidden = true; } }));
    pop.hidden = false;
    const w = pop.offsetWidth, h = pop.offsetHeight;
    pop.style.left = Math.max(8, Math.min(innerWidth - w - 8, x - 20)) + 'px';
    pop.style.top = Math.max(8, Math.min(innerHeight - h - 8, y + 14)) + 'px';
    setTimeout(() => { const ta = $('textarea', pop); if (ta) ta.focus(); }, 0);
  }
  document.addEventListener('pointerdown', e => { if (!pop.hidden && !pop.contains(e.target) && !e.target.closest('.pv-chg .cb')) pop.hidden = true; }, true);
  pop.addEventListener('keydown', e => { if (e.key === 'Escape') { pop.hidden = true; e.stopPropagation(); } });
  [0, 1].forEach(side => scrollEl(side).addEventListener('click', e => {
    const cb = e.target.closest('.pv-chg .cb'); if (!cb) return;
    const slot = cb.closest('.pv-slot'); openNotePop(side, +slot.dataset.i, +cb.dataset.k, e.clientX, e.clientY);
  }));

  /* ---------- 注釈の取り消し・やり直し（Ctrl+Z／Ctrl+Y） ---------- */
  const snap = side => JSON.stringify(st.ann[side]);
  function pushHist(side, before) {
    st.undo.push({ side, s: before == null ? snap(side) : before }); if (st.undo.length > 200) st.undo.shift();
    st.redo = []; histBtns();
  }
  function redrawSide(side) { const sd = st.sides[side]; if (sd) sd.slots.forEach((_, i) => drawAnn(side, i)); }
  function stepHist(from, to) {
    const h = from.pop(); if (!h) { toast(from === st.undo ? '元に戻す操作はありません' : 'やり直す操作はありません'); return; }
    to.push({ side: h.side, s: snap(h.side) });
    st.ann[h.side] = cleanAnnMap(JSON.parse(h.s)); st.sel = null; saveAnn(h.side); redrawSide(h.side); histBtns();
  }
  const undoAnn = () => stepHist(st.undo, st.redo), redoAnn = () => stepHist(st.redo, st.undo);
  function histBtns() { $('#annUndo').disabled = !st.undo.length; $('#annRedo').disabled = !st.redo.length; }
  $('#annUndo').onclick = undoAnn; $('#annRedo').onclick = redoAnn;
  // 付箋の入力欄：クリックした位置にその場で出す（画面の中央に出すと、貼る位置が隠れるため）
  function inlineNote(x, y, initial = '') {
    return new Promise(res => {
      const box = document.createElement('div'); box.className = 'pv-noteinput';
      box.innerHTML = `<textarea rows="3" maxlength="2000" placeholder="付箋の内容（Ctrl+Enter で貼る、Esc でやめる）" aria-label="付箋の内容"></textarea><div class="row2"><span class="muted">改行できます</span><button type="button" class="c">キャンセル</button><button type="button" class="primary ok">${initial ? '直す' : '貼る'}</button></div>`;
      document.body.appendChild(box);
      const ta = $('textarea', box); ta.value = initial;
      box.style.left = Math.max(8, Math.min(innerWidth - box.offsetWidth - 8, x)) + 'px';
      box.style.top = Math.max(8, Math.min(innerHeight - box.offsetHeight - 8, y)) + 'px';
      const done = v => { box.remove(); document.removeEventListener('pointerdown', outside, true); res(v); };
      const outside = e => { if (!box.contains(e.target)) done(ta.value.trim() ? ta.value : null); };
      setTimeout(() => document.addEventListener('pointerdown', outside, true), 0);
      $('.ok', box).onclick = () => done(ta.value);
      $('.c', box).onclick = () => done(null);
      ta.addEventListener('keydown', e => {
        e.stopPropagation();
        if (e.key === 'Escape') done(null);
        else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); done(ta.value); }
      });
      ta.focus();
    });
  }
  const PASTEL = { '#fdd835': '#fff59d', '#e53935': '#ffcdd2', '#1e88e5': '#bbdefb', '#43a047': '#c8e6c9', '#fb8c00': '#ffe0b2', '#8e24aa': '#e1bee7', '#212121': '#eeeeee' };

  /* ---------- pointer / tools ---------- */
  function pt(svg, e) {
    const p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY;
    return p.matrixTransform(svg.getScreenCTM().inverse());
  }
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
          // ダブルクリック（付箋の編集）：ドラッグのためにポインタを捕まえると click・dblclick が届かないので、押した間隔で判定する
          const ld = st.lastDown, now = Date.now();
          st.lastDown = { side, i, k, at: now };
          if (ld && ld.side === side && ld.i === i && ld.k === k && now - ld.at < 450 && arr[k].t === 'note') { st.lastDown = null; editNote(side, i, k, e.clientX, e.clientY); return; }
          drag = { mode: 'move', k, start: p, orig: JSON.parse(JSON.stringify(arr[k])), before: snap(side) };
        } else {
          select(null);
          const sc = scrollEl(side);
          drag = { mode: 'pan', x: e.clientX, y: e.clientY, sl: sc.scrollLeft, st: sc.scrollTop };
        }
      } else if (tool === 'eraser') {
        if (target) { pushHist(side); arr.splice(+target.dataset.i, 1); st.sel = null; drawAnn(side, i); saveAnn(side); }
        return;
      } else if (tool === 'pen' || tool === 'marker') {
        const before = snap(side);
        arr.push({ t: tool, c: st.color, w: st.width, p: [[p.x, p.y]] });
        drag = { mode: 'draw', k: arr.length - 1, before };
      } else if (tool === 'rect') {
        const before = snap(side);
        arr.push({ t: 'rect', c: st.color, lw: st.width, x: p.x, y: p.y, w: 0, h: 0 });
        drag = { mode: 'rect', k: arr.length - 1, start: p, before };
      } else if (tool === 'note') {
        e.preventDefault();
        const text = await inlineNote(e.clientX, e.clientY);
        if (text && text.trim()) {
          const pg = st.sides[side].pages[i], a = { t: 'note', x: p.x, y: p.y, text, bg: PASTEL[st.color] || '#fff59d', fs: noteFs(pg) }, d = noteDims(a);
          a.x = Math.max(2, Math.min(a.x, pg.w - d.w - 4)); a.y = Math.max(2, Math.min(a.y, pg.h - d.h - 4)); // ページからはみ出さないように
          pushHist(side); arr.push(a); drawAnn(side, i); saveAnn(side);
        }
        setTool('select'); // 1枚貼ったら選択に戻す（続けてクリックしても、次の入力欄が出ないように）
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
      if (drag.mode !== 'pan') { if (drag.before != null && drag.before !== snap(side)) pushHist(side, drag.before); drawAnn(side, i); saveAnn(side); }
      drag = null;
    };
    svg.addEventListener('pointerup', end);
    svg.addEventListener('pointercancel', end);
  }
  async function editNote(side, i, k, x, y) {
    const a = list(side, i)[k]; if (!a || a.t !== 'note') return;
    const t = await inlineNote(x, y, a.text); if (t == null) return;
    pushHist(side);
    if (!t.trim()) list(side, i).splice(k, 1); else a.text = t;
    st.sel = null; drawAnn(side, i); saveAnn(side);
  }
  function deleteSelected() {
    if (!st.sel) return false;
    const { side, page, i } = st.sel;
    pushHist(side); list(side, page).splice(i, 1); st.sel = null; drawAnn(side, page); saveAnn(side); return true;
  }

  /* ---------- scroll / page indicator / sync ---------- */
  // 今のページ＝表示領域の上端から PEEK px 下にあるページ。ページへ移動したとき（ページの上端の 10px 上を表示）に、
  // 前のページと判定しないよう、移動の余白（10px）より大きくする
  const PEEK = 16;
  function currentPage(side) {
    const sd = st.sides[side]; if (!sd) return { i: 0, f: 0 };
    const sc = scrollEl(side), y = sc.scrollTop + PEEK;
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
      // 連動で動かした側の scroll イベント（こちらが設定した位置そのもの）は無視する。
      // 以前は「動かした側を0.15秒固定」していたため、その間の利用者のスクロールが反対側に伝わらず、左右がずれることがあった
      const ex = st.expect[side];
      if (ex && Math.abs(sc.scrollTop - ex.top) <= 1 && Math.abs(sc.scrollLeft - ex.left) <= 1) { st.expect[side] = null; return; }
      st.expect[side] = null;
      if (!$('#pvSync').checked) return;
      const o = 1 - side, osd = st.sides[o]; if (!osd || $('#pvShow').value !== 'both') return;
      const j = PageMatch.other(side, cp.i, osd.slots.length), os = osd.slots[j].slot, osc = scrollEl(o);
      const before = { top: osc.scrollTop, left: osc.scrollLeft };
      osc.scrollTop = os.offsetTop - PEEK + cp.f * (os.offsetHeight + 14);
      const r = sc.scrollWidth - sc.clientWidth, or = osc.scrollWidth - osc.clientWidth;
      if (r > 0 && or > 0) osc.scrollLeft = sc.scrollLeft / r * or;
      // 実際に設定された位置（端では切り詰められる）を覚えておき、その scroll イベントだけを無視する。
      // 位置が変わらなかったときはイベントが来ないので、覚えない
      const exp = { top: osc.scrollTop, left: osc.scrollLeft };
      st.expect[o] = (exp.top !== before.top || exp.left !== before.left) ? exp : null;
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
      pushHist(side); st.ann[side] = {}; st.sel = null; saveAnn(side); st.sides[side] && st.sides[side].slots.forEach((_, i) => drawAnn(side, i));
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
    const s = st.sides[side].slots[cp.i].slot; scrollEl(side).scrollTop = s.offsetTop - PEEK + cp.f * (s.offsetHeight + 14);
  }

  /* ---------- toolbar ---------- */
  function setTool(t) {
    st.tool = t; wrap.dataset.tool = t;
    $$('#toolGrp .toolbtn').forEach(b => b.classList.toggle('on', b.dataset.tool === t));
    if (st.toolColor[t]) { st.color = st.toolColor[t]; markSw(); }
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
    st.color = c; markSw();
    if (st.toolColor[st.tool]) { st.toolColor[st.tool] = c; store.set('pv:toolColor', st.toolColor); }
    if (st.sel) {
      const a = list(st.sel.side, st.sel.page)[st.sel.i];
      if (a) { pushHist(st.sel.side); if (a.t === 'note') a.bg = PASTEL[c] || a.bg; else a.c = c; drawAnn(st.sel.side, st.sel.page); saveAnn(st.sel.side); }
    }
  };
  markSw();
  $('#annWidth').value = String(st.width);
  $('#annWidth').onchange = e => { st.width = +e.target.value; store.set('pv:width', st.width); };
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
  $('#annExport').onclick = async () => {
    const files = [0, 1].filter(s => S[s]).map(s => ({ side: s, name: S[s].name, size: S[s].size, rot: st.rot[s], annotations: st.ann[s] }));
    if (!files.length) return toast('ファイルが読み込まれていません');
    const n = files.reduce((t, f) => t + Object.values(f.annotations).reduce((s, x) => s + (x ? x.length : 0), 0), 0);
    if (!n && !(S[0] && S[1] && Object.keys(Notes.all()).length)) return toast('保存する注釈・コメントがありません');
    const withAnn = files.filter(f => Object.values(f.annotations).some(x => x && x.length));
    // 変更点のコメント（確認の状態・ひとこと）も一緒に保存する。記入者・保存日時・対象ファイルの SHA-256 も入れる（取り違えの確認用）
    const notes = S[0] && S[1] ? Notes.all() : {};
    const hashes = await Promise.all([0, 1].map(s2 => S[s2] ? Report.sha256(S[s2].bytes) : ''));
    files.forEach(f => { f.sha256 = hashes[f.side] || ''; });
    const nn = Object.keys(notes).length;
    download(`注釈_${(withAnn.length ? withAnn : files).map(f => baseName(f.name)).join('_')}.json`, JSON.stringify({ app: 'shibadiff', version: 2, savedAt: new Date().toISOString(), author: Settings.get('author') || '', files, notes }, null, 1), 'application/json');
    if (nn) toast(`注釈と、変更点のコメント ${nn} 件を保存しました`);
  };
  $('#annImport').onclick = () => $('#annFile').click();
  $('#annFile').onchange = async e => {
    const f = e.target.files[0]; e.target.value = ''; if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      if (!data || !Array.isArray(data.files)) throw new Error('ShibaDiff の注釈ファイルの形式ではありません');
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
        pushHist(side); st.ann[side] = cleanAnnMap(fe.annotations); st.rot[side] = [0, 90, 180, 270].includes(fe.rot) ? fe.rot : 0; saveAnn(side); saveRot(side);
        applied++; await build(side);
      }
      // 変更点のコメント：左右とも読み込んでいて、どちらも注釈ファイルの文書と同じとき（名前で照合）に読み込む
      let nn = 0;
      if (data.notes && S[0] && S[1] && (data.files || []).length >= 1) nn = Notes.merge(data.notes);
      const withAnn = (data.files || []).filter(fe => fe && fe.annotations && Object.values(fe.annotations).some(x => Array.isArray(x) && x.length)).length;
      toast(applied || nn ? `読み込みました：注釈 ${withAnn} ファイル分${nn ? `・変更点のコメント ${nn} 件` : ''}` : '対応するファイルが見つかりませんでした（注釈ファイルの文書と、開いている文書が違います）', !(applied || nn));
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
  /* ---- レポート：注釈を付けたページの画像と、注釈・付箋の一覧 ---- */
  const TNAME = { pen: 'ペン', marker: 'マーカー', rect: '枠', note: '付箋' };
  $('#pvReport').onclick = async () => {
    const avail = [0, 1].filter(s => st.sides[s]);
    if (!avail.length) return toast('ファイルを読み込んでください');
    const both = avail.length === 2;
    const o = await Report.options('page', 'ページ表示・注釈のレポート',
      '出力する内容を選び、下のボタンで載せるページを選んでください。<br><span class="muted">ページを注釈ごと画像にして載せます。「左右に並べる」では、左右の対応するページ（挿入・削除されたページは対応付けの結果）を横に並べます。</span>',
      [...(both ? [{ k: 'layout', label: 'ページの並べ方', type: 'radio', def: 'side', choices: [['side', '左右に並べる'], ['single', '1ページずつ（左の全ページ→右の全ページ）']] }] : []),
        Report.qualityField,
        { k: 'files', label: 'ファイル情報（SHA-256）', type: 'check', def: true },
        { k: 'list', label: '注釈の一覧表', type: 'check', def: true },
        { k: 'notes', label: '各ページの付箋の内容', type: 'check', def: true },
        ...(both ? [{ k: 'chg', label: '変更箇所の枠とコメント（重ね合わせの結果）', type: 'check', def: true }] : [])],
      [{ label: 'すべてのページ', value: 'all' }, { label: '注釈のあるページだけ', value: 'ann', primary: true }]);
    if (!o) return;
    const scope = o.scope, side2 = both && o.layout === 'side', maxW = Report.width(o.quality), w = side2 ? Math.round(maxW * 0.7) : maxW;
    // 変更点のコメントがあるページも「注釈のあるページ」に含める
    const notedPair = (l, r) => Object.keys(Notes.all()).some(id => id.startsWith(`o:${l}:${r}:`));
    const hasNote = (side, i) => { if (!both || !o.chg) return false; const p = pairOf(side, i); return !!p && notedPair(p.l, p.r); };
    const has = (side, i) => i >= 0 && ((st.ann[side][i] || []).length > 0 || hasNote(side, i));
    let html;
    await withBusy('レポートを作成しています…', async () => {
      const secs = [], rows = [];
      // 1ページ分の画像（注釈込み）・注釈の数・付箋
      const one = async (side, i) => {
        const sd = st.sides[side], arr = st.ann[side][i] || [], pg = sd.pages[i];
        const cv = await renderWithAnn(side, i, Math.min(3, w * 1.2 / Math.max(pg.w, pg.h)));
        // 変更箇所の枠と番号（コメントの状態の色）を重ね、コメントを一覧にする
        let chgList = '';
        const pr = both && o.chg && !st.rot[side] ? pairOf(side, i) : null;
        if (pr) {
          const info = await OV.regionsFor(pr.l, pr.r);
          if (info) {
            const c = cv.getContext('2d'), k = cv.width / pg.w, fs = Math.max(12, cv.width / 70);
            const items = [];
            info.regions.forEach((g, n) => {
              const b = info.toPt(side, g), nv = Notes.get(info.ids[n]), colr = NCOL[nv ? nv.st : ''];
              c.save(); c.strokeStyle = colr; c.lineWidth = Math.max(2, fs / 6); c.setLineDash([fs / 2, fs / 4]); c.strokeRect(b.x * k, b.y * k, b.w * k, b.h * k); c.restore();
              const lab = String(n + 1) + (nv && nv.st === 'ok' ? ' ✓' : nv && nv.st === 'ask' ? ' !' : '');
              c.font = `bold ${fs}px sans-serif`; const tw = c.measureText(lab).width + fs * 0.6;
              c.fillStyle = colr; c.fillRect(b.x * k, b.y * k - fs * 1.4, tw, fs * 1.4); c.fillStyle = '#fff'; c.fillText(lab, b.x * k + fs * 0.3, b.y * k - fs * 0.35);
              if (nv) items.push(`<li><b>${n + 1}</b> ${nv.st === 'ok' ? '<span class="nst ok">確認済</span>' : nv.st === 'ask' ? '<span class="nst ask">要確認</span>' : ''} ${esc(nv.text || '').replace(/\n/g, '<br>')}${nv.by ? `<span class="by">（${esc(nv.by)}）</span>` : ''}</li>`);
            });
            if (items.length && side === 1) chgList = `<div class="notes"><b>変更箇所のコメント</b><ul class="chg">${items.join('')}</ul></div>`;
          }
        }
        const cnt = Object.entries(arr.reduce((m, a) => (m[a.t] = (m[a.t] || 0) + 1, m), {})).map(([t, n]) => `${TNAME[t] || t} ${n}`).join('・');
        const notes = o.notes ? arr.filter(a => a.t === 'note').map(a => `<li>${esc(a.text).replace(/\n/g, '<br>')}</li>`).join('') : '';
        const nm = side ? '右' : '左';
        const fig = `<figure><img src="${Report.jpeg(cv, w)}" alt=""><figcaption>${nm}：${esc(S[side].name)}　${i + 1} / ${sd.pages.length} ページ　${cnt ? '注釈：' + cnt : '注釈なし'}</figcaption></figure>` + (notes ? `<div class="notes"><b>付箋</b><ol>${notes}</ol></div>` : '') + chgList;
        cv.width = cv.height = 0;
        if (arr.length) rows.push(`<tr><td>${nm}</td><td class="num">${i + 1}</td><td>${cnt}</td><td>${arr.filter(a => a.t === 'note').map(a => esc(a.text).replace(/\n/g, ' ')).join('<br>')}</td></tr>`);
        return { fig, n: arr.length };
      };
      if (side2) {
        // 左右の対応するページを組にする（対応付けがあればその結果、なければ同じページ番号どうし）
        const nl = st.sides[0].pages.length, nr = st.sides[1].pages.length;
        const pairs = PageMatch.ready() || Array.from({ length: Math.max(nl, nr) }, (_, i) => ({ l: i < nl ? i : -1, r: i < nr ? i : -1 }));
        const use = pairs.filter(p => scope === 'all' || has(0, p.l) || has(1, p.r));
        for (let k = 0; k < use.length; k++) {
          const p = use[k];
          $('#busyMsg').textContent = `レポートを作成しています… ${k + 1} / ${use.length} 組`;
          const a = p.l >= 0 ? await one(0, p.l) : null, b = p.r >= 0 ? await one(1, p.r) : null;
          const n = (a ? a.n : 0) + (b ? b.n : 0);
          secs.push(`<h2>左 ${p.l < 0 ? '—' : p.l + 1} ページ ／ 右 ${p.r < 0 ? '—' : p.r + 1} ページ　${n ? `<span class="tag note">注釈 ${n}</span>` : ''}</h2>` +
            `<div class="pair"><div>${a ? a.fig : '<div class="none">（対応するページなし）</div>'}</div><div>${b ? b.fig : '<div class="none">（対応するページなし）</div>'}</div></div>`);
          await sleep(0);
        }
      } else {
        for (const side of avail) {
          const sd = st.sides[side], nm = side ? '右' : '左';
          const idx = sd.pages.map((_, i) => i).filter(i => scope === 'all' || has(side, i));
          for (const i of idx) {
            $('#busyMsg').textContent = `レポートを作成しています… ${nm} ${i + 1} / ${sd.pages.length} ページ`;
            const r = await one(side, i);
            secs.push(`<h2>${nm}：${esc(S[side].name)}　${i + 1} / ${sd.pages.length} ページ　${r.n ? `<span class="tag note">注釈 ${r.n}</span>` : ''}</h2>` + r.fig);
            await sleep(0);
          }
        }
      }
      const total = avail.reduce((n, s) => n + Object.values(st.ann[s]).reduce((m, a) => m + a.length, 0), 0);
      const list = !o.list ? '' : `<h2>注釈の一覧</h2>` + (rows.length ? `<table class="list"><thead><tr><th style="width:40px">側</th><th class="num" style="width:50px">頁</th><th style="width:28%">注釈</th><th>付箋の内容</th></tr></thead><tbody>${rows.join('')}</tbody></table>` : '<p>注釈はありません。</p>');
      html = Report.page({
        title: `注釈レポート - ${avail.map(s => S[s].name).join(' / ')}`, heading: 'ページ表示・注釈レポート',
        meta: `<b>注釈 ${total} 件</b>（${avail.map(s => s ? '右' : '左').join('・')}の文書）` + (o.files ? '' : '<br>' + avail.map(s => `${s ? '右' : '左'}: ${esc(S[s].name)}`).join('　')),
        body: (o.files ? await Report.bothInfo() : '') + list + (secs.length ? secs.join('') : '<p>載せるページはありません。</p>'),
        css: '.pair figure{margin:4px 0 6px}.notes{font-size:12.5px;margin-bottom:12px}ul.chg{list-style:none;padding-left:4px;margin:4px 0}ul.chg b{display:inline-block;min-width:20px}.nst{font-weight:700}.nst.ok{color:#1b5e20}.nst.ask{color:#c2410c}.by{color:#777;font-size:11px}.none{border:1px dashed #bbb;color:#888;display:flex;align-items:center;justify-content:center;min-height:120px;margin:4px 0 14px}'
      });
    });
    if (html) download(`注釈レポート_${baseName(S[avail[0]].name)}.html`, html, 'text/html;charset=utf-8');
  };
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
    // 左右の連動で、挿入・削除されたページを飛ばして対応するページに合わせられるよう、裏で対応付けを調べておく
    if (S[0] && S[1] && PageMatch.enabled() && !PageMatch.ready()) PageMatch.compute().then(() => { if (App.tab === 'page') redrawChanges(); }).catch(() => { });
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
    if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'z' || e.key === 'Z') && !e.shiftKey) { e.preventDefault(); undoAnn(); return true; }
    if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'y' || e.key === 'Y' || ((e.key === 'z' || e.key === 'Z') && e.shiftKey))) { e.preventDefault(); redoAnn(); return true; }
    if ((e.key === 'Delete' || e.key === 'Backspace') && deleteSelected()) { e.preventDefault(); return true; }
    if (e.key === 'Escape') { setTool('select'); select(null); return true; }
    return false;
  }
  return { activate, invalidate, onKey, st, cleanAnnot };
})();
