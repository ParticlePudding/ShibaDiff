/* テキスト比較ビュー（WinMerge風） */
const TV = (() => {
  let ROWH = 20;
  function applyMetrics() { ROWH = { s: 18, m: 20, l: 24 }[Settings.get('fontSize')] || 20; document.documentElement.style.setProperty('--rowh', ROWH + 'px'); }
  applyMetrics();
  const wrapEl = $('#wrapView');
  const wrapOn = () => !!Settings.get('wrap');
  const panes = [$('#paneL'), $('#paneR')];
  const st = {
    rows: [], blocks: [], view: [], rowToView: new Int32Array(0), cur: -1, hit: -1,
    expanded: new Set(), undo: [], redo: [], maxCols: 0, charW: 7.8, dirty: true, identicalBytes: false,
    unified: false, uv: [], vToU: new Int32Array(0)
  };
  /* view index -> display row index (differs in unified/一列 mode) */
  const D = v => (st.unified ? st.vToU[v] : v);
  const DN = () => (st.unified ? st.uv.length : st.view.length);

  function opts() {
    return { ws: $('#oWs').value, ignoreCase: $('#oCase').checked, blank: $('#oBlank').checked, zen: $('#oZen').checked, fold: $('#oFold').checked };
  }
  function saveOpts() { store.set('textopts', opts()); }
  function loadOpts() {
    const o = store.get('textopts', null); if (!o) return;
    $('#oWs').value = o.ws || 'none'; $('#oCase').checked = !!o.ignoreCase; $('#oBlank').checked = !!o.blank; $('#oZen').checked = !!o.zen; $('#oFold').checked = !!o.fold;
  }
  const L = side => (S[side] ? S[side].lines : []);

  function measureChar() {
    const s = document.createElement('span');
    s.style.cssText = `position:absolute;visibility:hidden;white-space:pre;font:${getComputedStyle(panes[0]).font}`;
    s.textContent = '0'.repeat(100); document.body.appendChild(s);
    st.charW = s.getBoundingClientRect().width / 100 || 7.8; s.remove();
  }
  function dispWidth(s) {
    let w = 0;
    for (let i = 0; i < s.length; i++) {
      const c = s.charCodeAt(i);
      if (c === 9) w += 4 - (w % 4); else if (c >= 0x1100 && !(c >= 0xFF61 && c <= 0xFF9F) && !(c >= 0xDC00 && c <= 0xDFFF)) w += 2; else w += 1;
    }
    return w;
  }

  function normalizer(o) {
    return s => {
      if (o.zen) s = s.normalize('NFKC');
      if (o.ignoreCase) s = s.toLowerCase();
      if (o.ws === 'all') s = s.replace(/\s+/g, '');
      else if (o.ws === 'change') s = s.replace(/\s+/g, ' ').trim();
      return s;
    };
  }

  function compare(keepPos = false) {
    st.dirty = false;
    const A = L(0), B = L(1), o = opts();
    const norm = normalizer(o), ids = new Map();
    const idOf = s => { s = norm(s); let v = ids.get(s); if (v === undefined) { v = ids.size; ids.set(s, v); } return v; };
    const ia = new Int32Array(A.length), ib = new Int32Array(B.length);
    for (let i = 0; i < A.length; i++) ia[i] = idOf(A[i]);
    for (let i = 0; i < B.length; i++) ib[i] = idOf(B[i]);
    let rows, blocks;
    if (!o.blank) ({ rows, blocks } = Diff.buildRows(Diff.seq(ia, ib), A, B, {}));
    else ({ rows, blocks } = diffIgnoringBlank(A, B, ia, ib));
    st.rows = rows; st.blocks = blocks; st.hit = -1;
    if (!keepPos) st.expanded.clear();
    let mx = 0;
    for (const arr of [A, B]) for (const s of arr) if (s.length * 2 > mx) { const w = dispWidth(s); if (w > mx) mx = w; }
    st.maxCols = mx;
    buildView();
    const gutDigits = String(Math.max(A.length, B.length, 1)).length;
    $('#diffwrap').style.setProperty('--gut', Math.max(40, gutDigits * st.charW * 0.92 + 18) + 'px');
    sizeSpacers();
    if (keepPos) { st.cur = Math.min(st.cur, blocks.length - 1); if (st.cur < 0 && blocks.length) st.cur = 0; }
    else st.cur = blocks.length ? 0 : -1;
    if (wrapOn()) {
      const keepTop = wrapEl.scrollTop;
      render(); if (!keepPos) { wrapEl.scrollTop = 0; if (st.cur >= 0) scrollToBlock(st.cur); } else wrapEl.scrollTop = keepTop;
    } else {
      if (!keepPos) { panes[0].scrollTop = 0; panes[0].scrollLeft = 0; if (st.cur >= 0) scrollToBlock(st.cur); }
      render();
    }
    status();
    $('#textHint').style.display = (S[0] || S[1]) ? 'none' : '';
  }

  /* 空行を取り除いてから比較し、空行は「無視した差」として戻す */
  function diffIgnoringBlank(A, B, ia, ib) {
    const blank = s => /^\s*$/.test(s);
    const ma = [], mb = [];
    A.forEach((s, i) => { if (!blank(s)) ma.push(i); }); B.forEach((s, i) => { if (!blank(s)) mb.push(i); });
    const A2 = ma.map(i => A[i]), B2 = mb.map(i => B[i]);
    const r2 = Diff.buildRows(Diff.seq(Int32Array.from(ma, i => ia[i]), Int32Array.from(mb, i => ib[i])), A2, B2, {}).rows;
    const rows = []; let na = 0, nb = 0;
    const flushBlanks = (ua, ub) => { // ua/ub: 次に出す元の行番号（ここより前の空行を出す）
      const ba = [], bb = [];
      while (na < ua) ba.push(na++);
      while (nb < ub) bb.push(nb++);
      for (let k = 0; k < Math.max(ba.length, bb.length); k++) {
        const a = k < ba.length ? ba[k] : -1, b = k < bb.length ? bb[k] : -1;
        rows.push({ a, b, t: a >= 0 && b >= 0 ? 'e' : 'w', blk: -1 });
      }
    };
    for (const r of r2) {
      const a = r.a >= 0 ? ma[r.a] : -1, b = r.b >= 0 ? mb[r.b] : -1;
      flushBlanks(a >= 0 ? a : na, b >= 0 ? b : nb);
      rows.push({ a, b, t: r.t, blk: -1 });
      if (a >= 0) na = a + 1; if (b >= 0) nb = b + 1;
    }
    flushBlanks(A.length, B.length);
    // ブロック（差分のまとまり）を作り直す
    const blocks = []; let pa = 0, pb = 0;
    for (let i = 0; i < rows.length;) {
      const r = rows[i];
      if (r.t !== 'c' && r.t !== 'd' && r.t !== 'i') { if (r.a >= 0) pa = r.a + 1; if (r.b >= 0) pb = r.b + 1; i++; continue; }
      const r0 = i, a0 = pa, b0 = pb;
      while (i < rows.length && 'cdi'.includes(rows[i].t)) { const x = rows[i]; x.blk = blocks.length; if (x.a >= 0) pa = x.a + 1; if (x.b >= 0) pb = x.b + 1; i++; }
      blocks.push({ r0, r1: i, a0, a1: pa, b0, b1: pb });
    }
    return { rows, blocks };
  }

  function buildView() {
    const R = st.rows, v = [], fold = opts().fold;
    if (!fold) { for (let i = 0; i < R.length; i++) v.push(i); }
    else {
      const ctx = 3, keep = new Uint8Array(R.length);
      for (let i = 0; i < R.length; i++) if (R[i].t !== 'e') for (let j = Math.max(0, i - ctx); j <= Math.min(R.length - 1, i + ctx); j++) keep[j] = 1;
      let i = 0;
      while (i < R.length) {
        if (keep[i]) { v.push(i++); continue; }
        let j = i; while (j < R.length && !keep[j]) j++;
        if (st.expanded.has(i) || j - i <= 1) for (let k = i; k < j; k++) v.push(k);
        else v.push({ fold: true, from: i, to: j });
        i = j;
      }
    }
    st.view = v;
    st.rowToView = new Int32Array(R.length).fill(-1);
    v.forEach((e, idx) => { if (typeof e === 'number') st.rowToView[e] = idx; });
    buildUnified();
    st.wrapDirty = true;
  }
  function buildUnified() {
    const uv = [], vToU = new Int32Array(st.view.length), A = L(0), B = L(1);
    st.view.forEach((e, v) => {
      vToU[v] = uv.length;
      if (typeof e === 'object') { uv.push({ v, k: 'f' }); return; }
      const r = st.rows[e];
      if (r.t === 'e' || (r.t === 'w' && r.a >= 0 && r.b >= 0 && A[r.a] === B[r.b])) uv.push({ v, k: 'e' });
      else { if (r.a >= 0) uv.push({ v, k: 'a' }); if (r.b >= 0) uv.push({ v, k: 'b' }); }
    });
    st.uv = uv; st.vToU = vToU;
  }
  function sizeSpacers() {
    const h = DN() * ROWH;
    const gut = parseFloat(getComputedStyle($('#diffwrap')).getPropertyValue('--gut')) || 56;
    const w = gut * (st.unified ? 2 : 1) + 24 + (st.maxCols + (st.unified ? 2 : 0)) * st.charW;
    for (const p of panes) { const sp = $('.spacer', p); sp.style.height = h + 'px'; sp.style.width = w + 'px'; }
  }

  // CSV・TSV では、カンマを3桁区切りとみなさない
  const isCsv = () => [0, 1].some(i => S[i] && /\.(csv|tsv)$/i.test(S[i].name || ''));
  const getCd = r => r.cd || (r.cd = Diff.chars(L(0)[r.a], L(1)[r.b], Settings.get('unit'), isCsv()));
  /* 文字列を HTML に（設定により空白・タブを記号で表示） */
  function txt(str) {
    const h = esc(str);
    if (!Settings.get('showWs')) return h;
    const WS = { '\t': '<span class="wsc wtab">\t</span>', ' ': '<span class="wsc wsp"> </span>', '\u3000': '<span class="wsc wzsp">\u3000</span>' };
    return h.replace(/[\t \u3000]/g, c => WS[c]); // 1回の置換で行う（置換後のタグ内の空白を壊さない）
  }
  function eolMark(side, li) {
    if (!Settings.get('showWs')) return '';
    const sd = S[side]; if (!sd) return '';
    if (li === sd.lines.length - 1 && sd.finalNL === false) return '';
    return sd.eol === '\r\n' ? '<span class="wsc weol" title="CRLF">↵</span>' : sd.eol === '\r' ? '<span class="wsc weol" title="CR">←</span>' : '<span class="wsc weol" title="LF">↓</span>';
  }
  /* 変更行の中身：変わった文字の色付け、挿入位置の印、数字の差 */
  function inlineHtml(r, side) {
    const cd = getCd(r), arr = side ? cd.B : cd.A, ranges = side ? cd.b : cd.a, pts = side ? cd.pb : cd.pa;
    const n = arr.length, mark = new Uint8Array(n);
    for (const [a, b] of ranges) for (let k = a; k < b; k++) mark[k] = 1;
    const ins = new Map();
    const add = (at, h) => ins.set(at, (ins.get(at) || '') + h);
    for (const q of pts) add(q, `<span class="ipt" title="${side ? 'ここにあった文字が削除されました' : 'ここに文字が追加されました'}"></span>`);
    if (side === 1 && Settings.get('numDelta')) for (const d of Diff.numberDeltas(cd)) add(d.at, `<span class="dnum">${esc(d.text)}</span>`);
    let out = '', buf = '', m = 0;
    const flush = () => { if (buf) out += m ? `<span class="cd">${txt(buf)}</span>` : txt(buf); buf = ''; };
    for (let k = 0; k <= n; k++) {
      if (ins.has(k)) { flush(); out += ins.get(k); }
      if (k === n) break;
      if (mark[k] !== m) { flush(); m = mark[k]; }
      buf += arr[k];
    }
    flush();
    return out;
  }
  const foldHtml = (v, e) => `<div class="row fold" data-v="${v}"><span class="ln">⋯</span><span class="tx">${fmtNum(e.to - e.from)} 行の一致部分を省略（クリックで展開）</span></div>`;
  const MK = { c: ['−', '+'], d: ['−', '+'], i: ['−', '+'] };
  /* 左右表示の1行（v: 表示上の行番号） */
  function rowHtml(v, side) {
    const e = st.view[v];
    if (typeof e === 'object') return foldHtml(v, e);
    const r = st.rows[e], li = side ? r.b : r.a;
    let cls = 'row t-' + r.t + ' side' + side;
    if (li < 0) cls += ' pad';
    if (r.blk >= 0 && r.blk === st.cur) {
      const b = st.blocks[r.blk]; cls += ' cur';
      if (e === b.r0) cls += ' first';
      if (e === b.r1 - 1) cls += ' last';
    }
    if (e === st.hit) cls += ' hit';
    let tx = '';
    if (li >= 0) tx = (r.t === 'c' ? inlineHtml(r, side) : txt(L(side)[li])) + eolMark(side, li);
    const mk = li >= 0 && MK[r.t] ? MK[r.t][side] : '';
    return `<div class="${cls}" data-v="${v}" data-s="${side}"><span class="ln">${li >= 0 ? li + 1 : ''}</span><span class="tx"><span class="mk" aria-hidden="true">${mk}</span>${tx}</span></div>`;
  }
  /* 一列表示の1行（d: 一列表示での行番号） */
  function unifiedRowHtml(d, fd = -1, ld = -1) {
    const u = st.uv[d], e = st.view[u.v];
    if (u.k === 'f') return foldHtml(u.v, e);
    const A = L(0), B = L(1), r = st.rows[e];
    let cls = 'row ' + (u.k === 'a' ? 't-d' : u.k === 'b' ? 't-i' : 't-' + r.t);
    if (d >= fd && d <= ld) { cls += ' cur'; if (d === fd) cls += ' first'; if (d === ld) cls += ' last'; }
    if (e === st.hit) cls += ' hit';
    const side = u.k === 'b' ? 1 : 0;
    const tx = u.k === 'e' ? txt(A[r.a]) + eolMark(0, r.a) : (r.t === 'c' ? inlineHtml(r, side) : txt((side ? B : A)[side ? r.b : r.a])) + eolMark(side, side ? r.b : r.a);
    const na = u.k !== 'b' && r.a >= 0 ? r.a + 1 : '', nb = u.k !== 'a' && r.b >= 0 ? r.b + 1 : '';
    return `<div class="${cls}" data-v="${u.v}" data-s="${side}"><span class="ln"><i>${na}</i><i>${nb}</i></span><span class="tx"><span class="mk" aria-hidden="true">${u.k === 'a' ? '−' : u.k === 'b' ? '+' : ' '}</span>${tx}</span></div>`;
  }
  function curRange() {
    if (!(st.cur >= 0 && st.blocks[st.cur])) return [-1, -1];
    const b = st.blocks[st.cur], v0 = st.rowToView[b.r0], v1 = st.rowToView[b.r1 - 1];
    return [st.vToU[v0], (v1 + 1 < st.view.length ? st.vToU[v1 + 1] : st.uv.length) - 1];
  }
  function renderUnified() {
    const pane = panes[0], rowsEl = $('.rows', pane);
    const top = pane.scrollTop, h = pane.clientHeight, N = st.uv.length;
    const first = Math.max(0, Math.floor(top / ROWH) - 4), last = Math.min(N, Math.ceil((top + h) / ROWH) + 4);
    const [fd, ld] = curRange();
    let html = '';
    for (let d = first; d < last; d++) html += unifiedRowHtml(d, fd, ld);
    rowsEl.style.transform = `translateY(${first * ROWH}px)`;
    rowsEl.innerHTML = html;
  }
  function renderPane(side) {
    if (st.unified) { if (side === 0) renderUnified(); return; }
    const pane = panes[side], rowsEl = $('.rows', pane);
    const top = pane.scrollTop, h = pane.clientHeight;
    const first = Math.max(0, Math.floor(top / ROWH) - 4), last = Math.min(st.view.length, Math.ceil((top + h) / ROWH) + 4);
    let html = '';
    for (let v = first; v < last; v++) html += rowHtml(v, side);
    rowsEl.style.transform = `translateY(${first * ROWH}px)`;
    rowsEl.innerHTML = html;
  }
  /* 折り返し表示：行の高さがそろわないので、左右を1行ずつ並べた表として全体を描く */
  function renderWrap() {
    st.wrapDirty = false;
    const N = st.unified ? st.uv.length : st.view.length, CH = 300;
    const [fd, ld] = curRange();
    const parts = [];
    for (let c = 0; c < N; c += CH) {
      let h = '<div class="wchunk">';
      for (let i = c; i < Math.min(N, c + CH); i++) h += st.unified ? unifiedRowHtml(i, fd, ld) : `<div class="wrow">${rowHtml(i, 0)}${rowHtml(i, 1)}</div>`;
      parts.push(h + '</div>');
    }
    wrapEl.innerHTML = parts.join('');
  }
  function markWrap() { // 選択中の差分・検索ヒットの印だけを付け直す
    $$('.row.cur,.row.hit', wrapEl).forEach(el => el.classList.remove('cur', 'first', 'last', 'hit'));
    if (st.cur >= 0 && st.blocks[st.cur]) {
      const b = st.blocks[st.cur], want = new Set();
      for (let r = b.r0; r < b.r1; r++) want.add(String(st.rowToView[r]));
      const v0 = st.rowToView[b.r0], from = $(`.row[data-v="${v0}"]`, wrapEl), els = [];
      // 差分の先頭行から順にたどる（全行を検索し直さない）
      for (let ch = from && from.closest('.wchunk'); ch; ch = ch.nextElementSibling) {
        let any = false;
        for (const x of ch.querySelectorAll('.row[data-v]')) if (want.has(x.dataset.v)) { els.push(x); any = true; }
        if (!any && els.length) break;
      }
      const bySide = st.unified ? [els] : [els.filter(x => x.dataset.s === '0'), els.filter(x => x.dataset.s === '1')];
      for (const g of bySide) { g.forEach(x => x.classList.add('cur')); if (g.length) { g[0].classList.add('first'); g[g.length - 1].classList.add('last'); } }
    }
    if (st.hit >= 0) $$(`.row[data-v="${st.rowToView[st.hit]}"]`, wrapEl).forEach(x => x.classList.add('hit'));
  }
  let raf = 0;
  function render() {
    cancelAnimationFrame(raf); raf = 0;
    $('#diffwrap').classList.toggle('wrapmode', wrapOn());
    if (wrapOn()) { if (st.wrapDirty) renderWrap(); markWrap(); }
    else { renderPane(0); renderPane(1); }
    drawMap();
  }
  function renderSoon() { if (!raf) raf = requestAnimationFrame(() => { raf = 0; if (wrapOn()) drawMap(); else { renderPane(0); renderPane(1); drawMap(); } }); }
  wrapEl.addEventListener('scroll', renderSoon, { passive: true });

  /* ---- location map ---- */
  const map = $('#locmap');
  // 削除＝赤、追加＝青（変更行は左を赤、右を青で描く）
  const COLL = { c: '#ef8f8a', d: '#d73a36', i: '#d73a36', w: '#d8d8d0' }, COLR = { c: '#80b8f5', d: '#1f6feb', i: '#1f6feb', w: '#d8d8d0' }, PADC = '#c9ced6';
  function drawMap() {
    const dpr = window.devicePixelRatio || 1, W = map.clientWidth, H = map.clientHeight;
    if (!W || !H) return;
    if (map.width !== Math.round(W * dpr) || map.height !== Math.round(H * dpr)) { map.width = Math.round(W * dpr); map.height = Math.round(H * dpr); }
    const c = map.getContext('2d'); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, W, H);
    const n = DN(); if (!n) return;
    const pad = 3, hh = H - pad * 2, rh = Math.max(1.5, hh / n);
    const colW = (W - 9) / 2;
    for (let v = 0; v < n; v++) {
      const e = st.view[v]; if (typeof e !== 'number') continue;
      const r = st.rows[e]; if (r.t === 'e') continue;
      const y = pad + D(v) / n * hh;
      c.fillStyle = r.a >= 0 ? COLL[r.t] : PADC; c.fillRect(3, y, colW, rh);
      c.fillStyle = r.b >= 0 ? COLR[r.t] : PADC; c.fillRect(6 + colW, y, colW, rh);
    }
    if (st.cur >= 0) {
      const b = st.blocks[st.cur], v0 = st.rowToView[b.r0], v1 = st.rowToView[b.r1 - 1];
      const y0 = pad + D(v0) / n * hh, y1 = pad + (D(v1) + (st.unified ? 2 : 1)) / n * hh;
      c.fillStyle = '#6e40c9'; c.fillRect(0, y0 - 1, 2.5, Math.max(3, y1 - y0 + 2));
    }
    const p = panes[0];
    const vy0 = wrapOn() ? pad + wrapEl.scrollTop / Math.max(1, wrapEl.scrollHeight) * hh : pad + (p.scrollTop / ROWH) / n * hh;
    const vh = wrapOn() ? wrapEl.clientHeight / Math.max(1, wrapEl.scrollHeight) * hh : (p.clientHeight / ROWH) / n * hh;
    c.strokeStyle = 'rgba(30,50,80,.55)'; c.lineWidth = 1; c.fillStyle = 'rgba(30,60,110,.08)';
    c.fillRect(1, vy0, W - 2, Math.max(4, vh)); c.strokeRect(1.5, vy0 + 0.5, W - 3, Math.max(4, vh) - 1);
  }
  function mapJump(e) {
    const rc = map.getBoundingClientRect(), n = DN(); if (!n) return;
    const f = (e.clientY - rc.top - 3) / (rc.height - 6);
    if (wrapOn()) { wrapEl.scrollTop = Math.max(0, f * wrapEl.scrollHeight - wrapEl.clientHeight / 2); return; }
    panes[0].scrollTop = Math.max(0, f * n * ROWH - panes[0].clientHeight / 2);
  }
  map.addEventListener('pointerdown', e => { map.setPointerCapture(e.pointerId); mapJump(e); });
  map.addEventListener('pointermove', e => { if (e.buttons & 1) mapJump(e); });

  /* ---- scroll sync ---- */
  panes.forEach((p, i) => {
    p.addEventListener('scroll', () => {
      const o = panes[1 - i];
      if (o.scrollTop !== p.scrollTop) o.scrollTop = p.scrollTop;
      if (o.scrollLeft !== p.scrollLeft) o.scrollLeft = p.scrollLeft;
      renderSoon();
    }, { passive: true });
  });
  for (const el of [...panes, wrapEl]) {
    el.addEventListener('click', e => {
      const row = e.target.closest('.row'); if (!row) return;
      const v = +row.dataset.v, ent = st.view[v];
      if (typeof ent === 'object') { st.expanded.add(ent.from); buildView(); sizeSpacers(); render(); return; }
      const r = st.rows[ent];
      if (r && r.blk >= 0 && r.blk !== st.cur) { st.cur = r.blk; render(); status(); }
    });
    el.addEventListener('dblclick', e => {
      const row = e.target.closest('.row'); if (!row) return;
      const ent = st.view[+row.dataset.v]; if (typeof ent !== 'number') return;
      const side = +(row.dataset.s || 0);
      const r = st.rows[ent], li = side ? r.b : r.a;
      App.openEditor(side, li >= 0 ? li : null);
    });
  }
  window.addEventListener('resize', () => { if (applyLayout()) return; if (App.tab === 'text') render(); });

  /* ---- 左右表示 / 一列表示 ---- */
  function applyLayout(force) {
    const pref = store.get('tvLayout', 'auto');
    const u = pref === 'uni' || (pref === 'auto' && window.innerWidth < 760);
    if (u === st.unified && !force) return false;
    const tv = topV();
    st.unified = u; st.wrapDirty = true;
    $('#diffwrap').classList.toggle('unified', u);
    $('#tLayout .lbl').textContent = u ? '左右表示' : '一列表示';
    $('#tLayout').querySelector('svg').outerHTML = u ? '<i data-i="columns-2"></i>' : '<i data-i="rows-2"></i>';
    $('#tLayout').title = u ? '左右に並べて表示' : '1列にまとめて表示';
    sizeSpacers(); render();
    setTopV(Math.min(tv, Math.max(0, st.view.length - 1)));
    return true;
  }
  $('#tLayout').onclick = () => { store.set('tvLayout', st.unified ? 'side' : 'uni'); applyLayout(); };

  /* ---- navigation ---- */
  /* 画面の一番上に見えている行（表示上の番号） */
  function topV() {
    if (wrapOn()) {
      const r = wrapEl.getBoundingClientRect(), el = document.elementFromPoint(r.left + 80, r.top + 6);
      const row = el && el.closest && el.closest('.row[data-v]'); return row ? +row.dataset.v : 0;
    }
    const d = Math.floor(panes[0].scrollTop / ROWH);
    return st.unified ? (st.uv[d] ? st.uv[d].v : 0) : d;
  }
  function setTopV(v) {
    if (wrapOn()) { const el = $(`.row[data-v="${v}"]`, wrapEl); if (el) wrapEl.scrollTop += el.getBoundingClientRect().top - wrapEl.getBoundingClientRect().top; return; }
    panes[0].scrollTop = D(v) * ROWH || 0;
  }
  /* 表示上の行 v が見えるようにスクロール（見えていれば動かさない） */
  function scrollToV(v) {
    if (wrapOn()) {
      const el = $(`.row[data-v="${v}"]`, wrapEl); if (!el) return;
      const er = el.getBoundingClientRect(), wr = wrapEl.getBoundingClientRect();
      if (er.top < wr.top + 10 || er.bottom > wr.bottom - 10) wrapEl.scrollTop += er.top - wr.top - wrapEl.clientHeight / 3;
      return;
    }
    const p = panes[0], y = D(v) * ROWH;
    if (y < p.scrollTop + 20 || y > p.scrollTop + p.clientHeight - ROWH * 3) p.scrollTop = Math.max(0, y - p.clientHeight / 3);
  }
  function scrollToBlock(i) {
    const b = st.blocks[i]; if (!b) return;
    if (wrapOn()) { scrollToV(st.rowToView[b.r0]); return; }
    const v = D(st.rowToView[b.r0]), p = panes[0];
    const y = v * ROWH, len = (b.r1 - b.r0) * ROWH * (st.unified ? 2 : 1);
    if (y < p.scrollTop + 20 || y + Math.min(len, p.clientHeight * 0.6) > p.scrollTop + p.clientHeight - 20)
      p.scrollTop = Math.max(0, y - p.clientHeight / 3);
    // 変更行なら、最初に変わった文字の位置まで横スクロール
    const r0 = st.rows[b.r0];
    if (r0 && r0.t === 'c') {
      const cd = getCd(r0), rg = cd.a[0] || cd.b[0];
      if (rg) hscrollTo(cd.a[0] ? L(0)[r0.a] : L(1)[r0.b], rg[0]);
    } else p.scrollLeft = 0;
  }
  function go(i) {
    if (!st.blocks.length) { toast('差分はありません'); return; }
    i = Math.max(0, Math.min(st.blocks.length - 1, i));
    st.cur = i;
    if (wrapOn()) { render(); scrollToBlock(i); } else { scrollToBlock(i); render(); }
    status();
  }
  function next() {
    if (st.cur < 0) {
      const tv = topV();
      const k = st.blocks.findIndex(b => st.rowToView[b.r0] >= tv); return go(k < 0 ? 0 : k);
    }
    if (st.cur >= st.blocks.length - 1) { toast('最後の差分です'); return go(st.cur); }
    go(st.cur + 1);
  }
  function prev() {
    if (st.cur <= 0) { if (st.cur === 0) toast('最初の差分です'); return go(0); }
    go(st.cur - 1);
  }

  /* ---- merge / undo ---- */
  function ensureSide(side) {
    if (!S[side]) S[side] = App.newTextSide();
    return S[side];
  }
  function snapshot() { return { L: S[0] ? S[0].lines : null, R: S[1] ? S[1].lines : null, nl: [S[0] ? S[0].finalNL : null, S[1] ? S[1].finalNL : null], cur: st.cur }; }
  function pushUndo() { st.undo.push(snapshot()); if (st.undo.length > 200) st.undo.shift(); st.redo = []; }
  function restore(s) {
    if (S[0] && s.L) { S[0].lines = s.L; if (s.nl && s.nl[0] != null) S[0].finalNL = s.nl[0]; }
    if (S[1] && s.R) { S[1].lines = s.R; if (s.nl && s.nl[1] != null) S[1].finalNL = s.nl[1]; }
    st.cur = s.cur; App.afterEdit(0, true); App.afterEdit(1, true); compare(true);
  }
  function undo() { if (!st.undo.length) return toast('元に戻す操作はありません'); st.redo.push(snapshot()); restore(st.undo.pop()); }
  function redo() { if (!st.redo.length) return toast('やり直す操作はありません'); st.undo.push(snapshot()); restore(st.redo.pop()); }
  function resetHistory() { st.undo = []; st.redo = []; }

  function canMerge() {
    if (!S[0] && !S[1]) return false;
    for (const s of S) if (s && s.noText) { toast('画像ファイルはテキストとして結合できません', true); return false; }
    return true;
  }
  function applyCopy(dir, b) {
    const src = dir === 0 ? 0 : 1, dst = 1 - src;
    const A = L(src), B = ensureSide(dst).lines;
    const [s0, s1, d0, d1] = src === 0 ? [b.a0, b.a1, b.b0, b.b1] : [b.b0, b.b1, b.a0, b.a1];
    S[dst].lines = B.slice(0, d0).concat(A.slice(s0, s1), B.slice(d1));
  }
  function copyCur(dir) {
    if (!canMerge()) return;
    const b = st.blocks[st.cur]; if (!b) return toast('差分を選択してください');
    pushUndo(); applyCopy(dir, b);
    App.afterEdit(dir === 0 ? 1 : 0); compare(true);
    if (st.blocks.length) go(Math.min(st.cur, st.blocks.length - 1));
  }
  async function copyAll(dir) {
    if (!canMerge()) return;
    if (!st.blocks.length) return toast('差分はありません');
    const to = dir === 0 ? '右' : '左', from = dir === 0 ? '左' : '右';
    const ok = await modal({ title: `すべての差分を${to}へコピー`, html: `${st.blocks.length} 箇所の差分すべてを、${from}の内容で${to}に上書きします。<br>${to}は${from}と同じ内容になり、比較結果は「同一」になります（${to}のファイルはまだ保存されません）。<br><span class="muted">元に戻す（Ctrl+Z）で戻せます。</span>`,
      buttons: [{ label: 'キャンセル', value: false }, { label: `${to}へコピーする`, primary: true, value: true }] });
    if (!ok) return;
    pushUndo();
    for (let i = st.blocks.length - 1; i >= 0; i--) applyCopy(dir, st.blocks[i]);
    App.afterEdit(dir === 0 ? 1 : 0); compare(true);
    toast(dir === 0 ? '左の内容を右へすべてコピーしました' : '右の内容を左へすべてコピーしました');
  }

  /* ---- search ---- */
  /* 行内の指定位置（文字数）が見えるように横スクロール */
  function hscrollTo(text, cpIndex) {
    const p = panes[0];
    const x = dispWidth(Array.from(text).slice(0, cpIndex).join('')) * st.charW;
    const gut = (parseFloat(getComputedStyle($('#diffwrap')).getPropertyValue('--gut')) || 56) * (st.unified ? 2 : 1);
    const w = p.clientWidth - gut - 30;
    if (x < p.scrollLeft || x > p.scrollLeft + w) p.scrollLeft = Math.max(0, x - w / 3);
  }
  const fold = t => t.normalize('NFKC').toLowerCase();
  function find() {
    const q = $('#searchBox').value; if (!q) { $('#searchBox').focus(); return; }
    const ql = fold(q), A = L(0), B = L(1), R = st.rows, n = R.length;
    if (!n) return;
    // 全角半角・大文字小文字・康熙部首などを区別せずに検索する
    const hits = [];
    for (let ri = 0; ri < n; ri++) {
      const r = R[ri];
      if ((r.a >= 0 && fold(A[r.a]).includes(ql)) || (r.b >= 0 && fold(B[r.b]).includes(ql))) hits.push(ri);
    }
    if (!hits.length) { st.hit = -1; render(); toast(`「${q}」は見つかりませんでした`); return; }
    const start = st.hit >= 0 ? st.hit + 1 : (() => { const v = st.view[topV()]; return typeof v === 'number' ? v : (v ? v.from : 0); })();
    let k = hits.findIndex(ri => ri >= start), wrapped = false;
    if (k < 0) { k = 0; wrapped = st.hit >= 0; }
    const ri = hits[k], r = R[ri];
    if (st.rowToView[ri] < 0) {
      const f = st.view.find(e => typeof e === 'object' && ri >= e.from && ri < e.to);
      if (f) { st.expanded.add(f.from); buildView(); sizeSpacers(); }
    }
    st.hit = ri;
    render(); scrollToV(st.rowToView[ri]);
    const line = r.a >= 0 && fold(A[r.a]).includes(ql) ? A[r.a] : B[r.b];
    if (!wrapOn()) hscrollTo(line, Math.max(0, fold(line).indexOf(ql)));
    render();
    toast(`「${q}」 ${k + 1} / ${hits.length} 件${wrapped ? '（先頭に戻りました）' : ''}`, false, 1800);
  }

  /* ---- status ---- */
  // 最初に違うバイトの位置（同一なら -1。長さが違えば短い方の長さ以下のどこか）
  function firstByteDiff(a, b) {
    if (!a || !b) return 0;
    const n = Math.min(a.length, b.length);
    for (let i = 0; i < n; i++) if (a[i] !== b[i]) return i;
    return a.length === b.length ? -1 : n;
  }
  function sideInfo(s) {
    if (!s) return '—';
    if (s.kind === 'pdf') return s.noTextLayer ? `PDF ${s.pageCount}ページ・文字情報なし（スキャン）` : `PDF ${s.pageCount}ページ・抽出 ${fmtNum(s.lines.length)}行`;
    if (s.noText) return '画像';
    if (/^(docx|xlsx|pptx)$/.test(s.kind)) return `${s.kind.toUpperCase()}・抽出 ${fmtNum(s.lines.length)}行`;
    return `${fmtNum(s.lines.length)}行・${Enc.NAMES[s.enc] || s.enc}・${Enc.EOLNAME[s.eol] || ''}${s.mixed ? '(混在)' : ''}`;
  }
  function status() {
    const n = st.blocks.length;
    let msg;
    const vis = [0, 1].filter(i => App.visualOnly(S[i]));
    if (!S[0] || !S[1]) msg = '<span>左右にファイルを読み込むと比較します</span>';
    else if (vis.length) msg = `<b style="color:#b45309">⚠ ${vis.map(i => (i ? '右' : '左')).join('と')}は文字情報のない画像（スキャン）のため、テキストでは比較できません</b><button id="goOverlay" style="padding:1px 8px">重ね合わせ比較で確認</button>`;
    else if (!n) {
      const o = opts();
      const ignored = o.ws !== 'none' || o.ignoreCase || o.blank || o.zen;
      const diffAt = firstByteDiff(S[0].bytes, S[1].bytes), same = diffAt < 0;
      if (!same && (S[0].kind === 'binary' || S[1].kind === 'binary')) {
        // バイナリの表示は先頭だけなので、表示上の差がなくても中身が違えば「同一」とは言わない
        msg = `<b style="color:#b45309">⚠ バイナリの内容が異なります</b><span>最初の違い：オフセット 0x${diffAt.toString(16).toUpperCase()}（${fmtNum(diffAt)}）。表示は先頭 ${fmtSize(Enc.DUMP_MAX)} のみです</span>`;
      } else {
      msg = `<b style="color:#21752f">✓ ${same ? '完全に同一です' : (ignored ? '比較オプションの範囲で同一です' : 'テキスト内容は同一です')}</b>`;
      if (!same && !ignored && S[0].kind === S[1].kind && S[0].kind === 'text' && (S[0].enc !== S[1].enc || S[0].eol !== S[1].eol)) msg += '<span>（文字コードまたは改行コードが異なります）</span>';
      if (!same && S[0].kind === 'text' && S[1].kind === 'text' && S[0].lines.length && (S[0].finalNL !== false) !== (S[1].finalNL !== false)) msg += '<span>（末尾の改行の有無が異なります）</span>';
      // 差分をコピーした・編集した結果の「同一」は、元のファイルが同一という意味ではないことを示す
      const ed = [0, 1].filter(i => S[i].dirty);
      if (ed.length) msg += `<span style="color:#b45309">（${ed.map(i => i ? '右' : '左').join('・')}は編集後・未保存の内容です。元のファイルどうしの結果ではありません。元に戻す：Ctrl+Z）</span>`;
      }
    } else {
      let dl = 0, il = 0, cl = 0;
      for (const r of st.rows) { if (r.t === 'c') cl++; else if (r.t === 'd') dl++; else if (r.t === 'i') il++; }
      msg = `差分 <b>${st.cur >= 0 ? st.cur + 1 : '-'} / ${n}</b> 箇所<span>変更 ${fmtNum(cl)}行・左のみ ${fmtNum(dl)}行・右のみ ${fmtNum(il)}行</span>`;
      if ([0, 1].some(i => S[i].kind === 'binary' && S[i].bytes && S[i].bytes.length > Enc.DUMP_MAX)) msg += `<span>（バイナリは先頭 ${fmtSize(Enc.DUMP_MAX)} だけを表示・比較しています。それより後ろの違いは数に含みません）</span>`;
    }
    $('#textStatus').innerHTML = `${msg}<span class="grow"></span><span>左: ${esc(sideInfo(S[0]))}</span><span>右: ${esc(sideInfo(S[1]))}</span>`;
    const go = $('#goOverlay'); if (go) go.onclick = () => App.setTab('overlay');
  }

  /* ---- export ---- */
  function exactRows() {
    const A = L(0), B = L(1), ids = new Map();
    const idOf = s => { let v = ids.get(s); if (v === undefined) { v = ids.size; ids.set(s, v); } return v; };
    const ia = Int32Array.from(A, idOf), ib = Int32Array.from(B, idOf);
    return Diff.buildRows(Diff.seq(ia, ib), A, B).rows;
  }
  /* unified diff（git形式）。各ファイルの改行コード・末尾改行の有無・文字コードを保つ */
  function unified() {
    const A = L(0), B = L(1), R = exactRows().slice(), ctx = 3;
    const sa = S[0], sb = S[1];
    const eolA = (sa && sa.eol) || '\n', eolB = (sb && sb.eol) || '\n';
    const nlA = !sa || sa.finalNL !== false, nlB = !sb || sb.finalNL !== false;
    // 一致行でも、片側だけ「改行のない最終行」なら行末が違うので、変更として扱う
    // （最終行が反対側では途中の行になる場合も含む。文脈行にすると git apply の結果が壊れる）
    const noEolA = i => i === A.length - 1 && !nlA, noEolB = i => i === B.length - 1 && !nlB;
    for (let i = 0; i < R.length; i++) {
      const x = R[i];
      if (x.t === 'e' && noEolA(x.a) !== noEolB(x.b)) R[i] = { ...x, t: 'c' };
    }
    const name = sa ? sa.name : 'file';
    const out = [`diff --git a/${name} b/${name}`, `--- a/${name}`, `+++ b/${name}`].map(l => l + '\n');
    const NONL = '\\ No newline at end of file\n';
    const lineA = (pre, i) => pre + A[i] + (i === A.length - 1 && !nlA ? '\n' + NONL : eolA === '\n' ? '\n' : eolA);
    const lineB = (pre, i) => pre + B[i] + (i === B.length - 1 && !nlB ? '\n' + NONL : eolB === '\n' ? '\n' : eolB);
    const aBefore = new Int32Array(R.length + 1), bBefore = new Int32Array(R.length + 1);
    for (let i = 0; i < R.length; i++) { aBefore[i + 1] = aBefore[i] + (R[i].a >= 0); bBefore[i + 1] = bBefore[i] + (R[i].b >= 0); }
    const chg = r => r.t !== 'e';
    let i = 0, hunks = 0;
    while (i < R.length) {
      if (!chg(R[i])) { i++; continue; }
      const start = Math.max(0, i - ctx);
      let j = i;
      for (; ;) {
        while (j < R.length && chg(R[j])) j++;
        let k = j; while (k < R.length && !chg(R[k]) && k - j <= 2 * ctx) k++;
        if (k < R.length && chg(R[k]) && k - j <= 2 * ctx) { j = k; continue; }
        break;
      }
      const stop = Math.min(R.length, j + ctx);
      const body = []; let dels = [], ins = [], ac = 0, bc = 0;
      const flush = () => { body.push(...dels, ...ins); dels = []; ins = []; };
      for (let r = start; r < stop; r++) {
        const x = R[r];
        if (x.t === 'e') { flush(); body.push(lineA(' ', x.a)); ac++; bc++; }
        else { if (x.a >= 0) { dels.push(lineA('-', x.a)); ac++; } if (x.b >= 0) { ins.push(lineB('+', x.b)); bc++; } }
      }
      flush();
      const as = ac ? aBefore[start] + 1 : aBefore[start], bs = bc ? bBefore[start] + 1 : bBefore[start];
      out.push(`@@ -${as},${ac} +${bs},${bc} @@\n`, ...body);
      hunks++; i = stop;
    }
    if (!hunks) return null;
    return out.join('');
  }
  function exportPatch() {
    if (!S[0] || !S[1]) return toast('左右にファイルを読み込んでください');
    const p = unified(); if (!p) return toast('差分がないため出力するものはありません');
    // 両方が同じ日本語の文字コードなら、その文字コードで書き出す（元ファイルに当てられるように）
    const e0 = S[0].kind === 'text' ? S[0].enc : 'utf-8', e1 = S[1].kind === 'text' ? S[1].enc : 'utf-8';
    let enc = e0 === e1 && /^(shift_jis|euc-jp)$/.test(e0) ? e0 : 'utf-8';
    let bytes = Enc.encode(p, enc).bytes;
    download(`${baseName(S[0].name)}.diff`, bytes, 'text/plain');
    toast(`パッチを出力しました（git形式・${Enc.NAMES[enc]}）。適用: git apply / patch -p1`);
  }
  async function exportReport() {
    if (!S[0] || !S[1]) return toast('左右にファイルを読み込んでください');
    const o = await Report.options('text', 'テキスト比較のレポート', '出力する内容を選んでください。',
      [{ k: 'range', label: '載せる行', type: 'radio', def: 'view', choices: [['view', '画面と同じ（差分のみ表示の設定に従う）'], ['all', 'すべての行'], ['ctx', '差分と前後3行だけ']] },
        { k: 'layout', label: '並べ方', type: 'radio', def: 'side', choices: [['side', '左右に並べる'], ['unified', '一列（変更前→変更後の順）']] },
        { k: 'files', label: 'ファイル情報（SHA-256）', type: 'check', def: true },
        { k: 'cond', label: '比較条件と凡例', type: 'check', def: true }],
      [{ label: '出力', value: 'ok', primary: true }]);
    if (!o) return;
    const A = L(0), B = L(1);
    const MARK = { c: '＊', d: '−', i: '＋', w: '' };
    // 載せる行：画面の表示上の行／すべての行／差分と前後3行（それ以外は「n 行省略」にまとめる）
    let items;
    if (o.range === 'view') items = st.view;
    else if (o.range === 'all') items = st.rows.map((_, i) => i);
    else {
      const keep = new Uint8Array(st.rows.length);
      st.rows.forEach((r, i) => { if (r.t !== 'e') for (let j = Math.max(0, i - 3); j <= Math.min(st.rows.length - 1, i + 3); j++) keep[j] = 1; });
      items = []; let from = -1;
      for (let i = 0; i <= st.rows.length; i++) {
        if (i < st.rows.length && !keep[i]) { if (from < 0) from = i; continue; }
        if (from >= 0) { items.push({ fold: true, from, to: i }); from = -1; }
        if (i < st.rows.length) items.push(i);
      }
    }
    const uni = o.layout === 'unified';
    let body = '';
    for (const e of items) {
      if (typeof e === 'object') { body += `<tr class="fold"><td colspan="${uni ? 4 : 4}">… ${e.to - e.from} 行省略 …</td></tr>`; continue; }
      const r = st.rows[e];
      if (uni) {
        // 一列：一致は1行、変更は変更前（−）と変更後（＋）の2行
        const line = (side, li, mk, cls) => `<tr><td class="ln">${side === 0 || mk === '' ? li + 1 : ''}</td><td class="ln">${side === 1 || mk === '' ? (mk === '' ? r.b : li) + 1 : ''}</td><td class="mk">${mk}</td><td class="${cls}">${r.t === 'c' ? inlineHtml(r, side) : esc((side ? B : A)[li])}</td></tr>`;
        if (r.t === 'e') body += line(0, r.a, '', '');
        else { if (r.a >= 0) body += line(0, r.a, '−', `t-${r.t === 'w' ? 'w' : r.t === 'c' ? 'c' : 'd'} s0`); if (r.b >= 0) body += line(1, r.b, '＋', `t-${r.t === 'w' ? 'w' : r.t === 'c' ? 'c' : 'i'} s1`); }
        continue;
      }
      const cell = (side, li) => li < 0 ? `<td class="ln"></td><td class="pad"></td>` :
        `<td class="ln">${r.t !== 'e' ? `<b>${MARK[r.t]}</b>` : ''}${li + 1}</td><td class="t-${r.t} s${side}">${r.t === 'c' ? inlineHtml(r, side) : esc((side ? B : A)[li])}</td>`;
      body += `<tr>${cell(0, r.a)}${cell(1, r.b)}</tr>`;
    }
    let cl = 0, dl = 0, il = 0; for (const r of st.rows) { if (r.t === 'c') cl++; else if (r.t === 'd') dl++; else if (r.t === 'i') il++; }
    const co = opts();
    const cond = [co.ws === 'change' ? '空白の量を無視' : co.ws === 'all' ? '空白を無視' : '', co.ignoreCase ? '大小文字無視' : '', co.blank ? '空行無視' : '', co.zen ? '全角半角無視' : '', co.fold ? '差分のみ表示' : ''].filter(Boolean).join('、') || 'なし（完全一致で比較）';
    const [h0, h1] = o.files ? await Promise.all([Report.sha256(S[0].bytes), Report.sha256(S[1].bytes)]) : ['', ''];
    const info = (s, h) => !o.files ? esc(s.name) : `${esc(s.name)}<br><span class="sub">${s.size ? fmtSize(s.size) + '・' : ''}更新 ${fmtDate(s.mtime)}${s.kind === 'text' ? '・' + (Enc.NAMES[s.enc] || s.enc) + '・' + (Enc.EOLNAME[s.eol] || '') : ''}${h ? `<br>SHA-256: ${h}` : ''}${s.dirty ? '<br><b style="color:#b42318">※ 未保存の編集を含む内容です（元のファイルとは異なります）</b>' : ''}</span>`;
    const css = `*{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:"BIZ UDPGothic","Meiryo",sans-serif;margin:20px;color:#222}h1{font-size:18px;margin:0 0 8px}
table{border-collapse:collapse;width:100%;table-layout:fixed;font-family:"BIZ UDGothic","MS Gothic",monospace;font-size:12.5px}
td{white-space:pre-wrap;word-break:break-all;padding:1px 6px;vertical-align:top;border-bottom:1px solid #f0f0f0}
td.ln{width:62px;text-align:right;color:#999;background:#f7f7f7}td.ln b{color:#444;margin-right:4px}th{background:#eee;padding:6px;text-align:left;vertical-align:top;font-family:"BIZ UDPGothic","Meiryo",sans-serif;font-weight:600}
th .sub{font-weight:400;color:#666;font-size:11px;word-break:break-all}
.t-c.s0,.t-d{background:#ffebe9}.t-c.s1,.t-i{background:#ddf4ff}.t-w{background:#f6f6f2}.pad{background:#eee}
.s0 .cd{background:#ffb8b3;text-decoration:line-through;text-decoration-color:#b3261e}.s1 .cd{background:#a8d4ff;text-decoration:underline;text-decoration-color:#0550ae;text-underline-offset:2px}
.ipt{display:inline-block;width:0;height:1em;border-left:2px solid #0550ae;margin:0 1px;vertical-align:-.15em}.s1 .ipt{border-left-color:#b3261e}
.dnum{font-family:sans-serif;font-size:10.5px;color:#0550ae;border:1px solid #a8d4ff;border-radius:8px;padding:0 4px;margin:0 3px}
.wsc,.weol{color:#9aa5b1}
td.mk{text-align:center;color:#444;font-weight:700}table.files{font-family:"BIZ UDPGothic","Meiryo",sans-serif;margin-bottom:10px}table.files th{width:40px}table.files td{white-space:normal}
tr.fold td{background:#eef3fb;color:#4c6a96;text-align:center;font-family:sans-serif}
.meta{color:#444;font-size:12.5px;margin-bottom:12px;line-height:1.7}.meta b{color:#222}
.legend span{display:inline-block;margin-right:14px}
@media print{body{margin:8mm}thead{display:table-header-group}tr{break-inside:avoid}}`;
    const html = `<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>比較レポート - ${esc(S[0].name)} / ${esc(S[1].name)}</title><style>${css}</style></head><body>
<h1>比較レポート</h1>
<div class="meta">作成日時: ${fmtDate(Date.now())}　<b>差分 ${st.blocks.length} 箇所</b>（変更 ${cl} 行・左のみ ${dl} 行・右のみ ${il} 行）${o.cond ? `　比較条件: ${esc(cond)}<br>
<span class="legend">${uni ? '<span>− 変更前・左だけにある行（赤）</span><span>＋ 変更後・右だけにある行（青）</span><span>変わった文字：変更前＝取り消し線、変更後＝下線</span>' : '<span>＊ 変更（変更前＝赤・取り消し線、変更後＝青・下線）</span><span>− 左だけにある行（赤）</span><span>＋ 右だけにある行（青）</span>'}</span>` : ''}</div>
${uni ? `<table class="files"><tr><th>左</th><td>${info(S[0], h0)}</td></tr><tr><th>右</th><td>${info(S[1], h1)}</td></tr></table>
<table><colgroup><col style="width:52px"><col style="width:52px"><col style="width:22px"><col></colgroup><thead><tr><th>左</th><th>右</th><th></th><th>内容</th></tr></thead><tbody>${body}</tbody></table>`
: `<table><colgroup><col style="width:62px"><col><col style="width:62px"><col></colgroup>
<thead><tr><th colspan="2">左: ${info(S[0], h0)}</th><th colspan="2">右: ${info(S[1], h1)}</th></tr></thead><tbody>${body}</tbody></table>`}</body></html>`;
    download(`比較レポート_${baseName(S[0].name)}.html`, html, 'text/html;charset=utf-8');
  }

  function activate() { measureChar(); applyLayout(); if (st.dirty) compare(); else { sizeSpacers(); render(); } }
  function invalidate() { st.dirty = true; if (App.tab === 'text') compare(); }

  /* ---- toolbar ---- */
  $('#tFirst').onclick = () => go(0);
  $('#tLast').onclick = () => go(st.blocks.length - 1);
  $('#tPrev').onclick = prev; $('#tNext').onclick = next;
  $('#tToR').onclick = () => copyCur(0); $('#tToL').onclick = () => copyCur(1);
  $('#tAllToR').onclick = () => copyAll(0); $('#tAllToL').onclick = () => copyAll(1);
  $('#tUndo').onclick = undo; $('#tRedo').onclick = redo;
  $('#tFind').onclick = find;
  $('#searchBox').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); find(); } else if (e.key === 'Escape') { st.hit = -1; render(); e.target.blur(); } });
  $('#searchBox').addEventListener('input', () => { st.hit = -1; });
  $('#tPatch').onclick = exportPatch; $('#tReport').onclick = exportReport;
  // 比較条件のうち、既定から変えている数をボタンに出す（たたんでいても条件が効いていることが分かるように）
  function markOpts() {
    const n = ($('#oWs').value !== 'none') + $('#oCase').checked + $('#oBlank').checked + $('#oZen').checked;
    $('#oBadge').hidden = !n; $('#oBadge').textContent = n;
  }
  for (const id of ['#oWs', '#oCase', '#oBlank', '#oZen']) $(id).addEventListener('change', () => { saveOpts(); markOpts(); compare(); });
  markOpts();
  $('#oFold').addEventListener('change', () => {
    saveOpts(); st.expanded.clear();
    const keepBlk = st.cur; buildView(); sizeSpacers(); st.cur = keepBlk;
    if (st.cur >= 0) { panes[0].scrollTop = 0; scrollToBlock(st.cur); }
    render();
  });
  loadOpts();
  Settings.on(k => {
    if (k === 'unit') for (const r of st.rows) r.cd = null;
    if (k === 'fontSize') { applyMetrics(); measureChar(); sizeSpacers(); }
    if (['unit', 'showWs', 'numDelta', 'wrap', 'fontSize'].includes(k)) { st.wrapDirty = true; if (App.tab === 'text') render(); }
  });

  return { compare, activate, invalidate, next, prev, go, copyCur, copyAll, undo, redo, find, resetHistory, pushUndo, status, render, st };
})();
