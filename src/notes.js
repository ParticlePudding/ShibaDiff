/* 変更点へのコメント：見つけた変更点ごとに「確認の状態」と「ひとこと」を付ける。
   テキスト比較の差分のまとまり（t:）と、重ね合わせの変更箇所（o:）に付け、レポート・CSV・注釈ファイルに出す。
   左右のファイルの組（識別キー）ごとに持つ。ブラウザへの保存は設定 persist に従う（既定はオフ） */
const Notes = (() => {
  const mem = new Map(); // 組のキー -> { id: {st, text, at, by, label} }
  const subs = [];
  const STATES = { '': '未確認', ok: '確認済', ask: '要確認' };
  const pairKey = () => (S[0] && S[1] ? `${S[0].key}||${S[1].key}` : '');
  const storeKey = k => 'notes:' + k;
  const persist = () => Settings.get('persist') === true;

  // 保存データ・注釈ファイルは信用しない：項目ごとに形と長さを確かめる
  function clean(o) {
    const out = {};
    if (!o || typeof o !== 'object') return out;
    let n = 0;
    for (const [id, v] of Object.entries(o)) {
      if (++n > 20000) break;
      if (typeof id !== 'string' || id.length > 200 || !/^[to]:[\w:.\-]+$/.test(id) || !v || typeof v !== 'object') continue;
      const st = v.st === 'ok' || v.st === 'ask' ? v.st : '';
      const text = typeof v.text === 'string' ? v.text.slice(0, 2000) : '';
      if (!st && !text) continue;
      out[id] = { st, text, at: Number.isFinite(v.at) ? v.at : 0, by: typeof v.by === 'string' ? v.by.slice(0, 40) : '', label: typeof v.label === 'string' ? v.label.slice(0, 200) : '' };
    }
    return out;
  }
  function load(k) {
    if (!mem.has(k)) mem.set(k, clean(persist() ? store.get(storeKey(k), null) : null));
    return mem.get(k);
  }
  function save(k) {
    if (!persist()) return;
    const o = mem.get(k) || {};
    if (Object.keys(o).length) store.set(storeKey(k), o); else store.del(storeKey(k));
  }
  const all = () => { const k = pairKey(); return k ? load(k) : {}; };
  const get = id => all()[id] || null;
  function set(id, patch) {
    const k = pairKey(); if (!k) return;
    const o = load(k), cur = o[id] || { st: '', text: '', at: 0, by: '', label: '' };
    const v = { ...cur, ...patch, at: Date.now(), by: Settings.get('author') || cur.by || '' };
    if (!v.st && !v.text) delete o[id]; else o[id] = v;
    save(k); subs.forEach(f => f(id));
  }
  // 注釈ファイルからの読み込み（今の組に足す。同じ id は読み込んだ方を使う）
  function merge(obj) { const k = pairKey(); if (!k) return 0; const o = load(k), c = clean(obj); Object.assign(o, c); save(k); subs.forEach(f => f(null)); return Object.keys(c).length; }
  function clear() { const k = pairKey(); if (!k) return; mem.set(k, {}); save(k); subs.forEach(f => f(null)); }
  const on = f => subs.push(f);

  /* ---- 変更点の id ---- */
  function hash(s) { let h = 0x811c9dc5; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); } return (h >>> 0).toString(36); }
  // テキスト：差分のまとまりの中身（左の行・右の行）から作る。同じ中身のまとまりは出てくる順の番号で区別する
  function textIds(blocks, A, B) {
    const seen = new Map();
    return blocks.map(b => {
      const h = hash(A.slice(b.a0, b.a1).join('\n') + '\u0000' + B.slice(b.b0, b.b1).join('\n'));
      const n = seen.get(h) || 0; seen.set(h, n + 1);
      return `t:${h}:${n}`;
    });
  }
  // 重ね合わせ：ページの組と、枠の中心の位置（ページに対する割合を 2% 刻み）。感度を変えて枠が少し動いても、近くのコメントを引き継ぐ
  const G = 50;
  function ovId(l, r, reg, W, H) {
    const gx = Math.round((reg.x + reg.w / 2) / W * G), gy = Math.round((reg.y + reg.h / 2) / H * G);
    const exact = `o:${l}:${r}:${gx}:${gy}`, o = all();
    if (o[exact]) return exact;
    for (const id of Object.keys(o)) {
      const m = /^o:(-?\d+):(-?\d+):(\d+):(\d+)$/.exec(id);
      if (m && +m[1] === l && +m[2] === r && Math.abs(m[3] - gx) <= 1 && Math.abs(m[4] - gy) <= 1) return id;
    }
    return exact;
  }

  /* ---- 入力欄（確認の状態とひとこと） ---- */
  function editor(id, label, opt = {}) {
    const v = get(id) || { st: '', text: '' };
    const el = document.createElement('div'); el.className = 'nt-ed'; el.dataset.id = id;
    el.innerHTML = `<div class="nt-st" role="radiogroup" aria-label="確認の状態">` +
      Object.entries(STATES).map(([k, t]) => `<button type="button" role="radio" data-st="${k}" class="st-${k || 'none'}${v.st === k ? ' on' : ''}" aria-checked="${v.st === k}">${t}</button>`).join('') +
      `</div><textarea rows="2" maxlength="2000" placeholder="ひとこと（理由・指示・確認結果など）" aria-label="コメント">${esc(v.text)}</textarea>` +
      `<div class="nt-meta muted">${v.at ? `${v.by ? esc(v.by) + '・' : ''}${fmtDate(v.at)}` : ''}</div>`;
    const ta = $('textarea', el);
    const grow = () => { ta.style.height = 'auto'; ta.style.height = Math.min(160, ta.scrollHeight + 2) + 'px'; };
    $$('.nt-st button', el).forEach(b => b.onclick = () => {
      set(id, { st: b.dataset.st, label });
      $$('.nt-st button', el).forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-checked', x === b); });
      if (opt.onChange) opt.onChange();
    });
    let t = 0;
    ta.addEventListener('input', () => { grow(); clearTimeout(t); t = setTimeout(() => { set(id, { text: ta.value, label }); if (opt.onChange) opt.onChange(); }, 250); });
    ta.addEventListener('blur', () => { clearTimeout(t); const cur = get(id); if ((cur ? cur.text : '') !== ta.value) { set(id, { text: ta.value, label }); if (opt.onChange) opt.onChange(); } });
    // 入力中のキー（Delete・矢印・N など）を、画面のショートカットに渡さない
    ta.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Escape') { ta.blur(); if (opt.onEscape) opt.onEscape(); } });
    setTimeout(grow, 0);
    return el;
  }
  // 一覧の1行に出す短い表示（状態の札とコメントの先頭）
  function chip(id) {
    const v = get(id); if (!v) return '';
    return `${v.st ? `<span class="nt-chip st-${v.st}">${STATES[v.st]}</span>` : ''}${v.text ? `<span class="nt-txt">${esc(v.text.length > 60 ? v.text.slice(0, 60) + '…' : v.text)}</span>` : ''}`;
  }
  const stateName = s => STATES[s || ''] || '未確認';
  // CSV の1セル（数式として実行されないよう、= + - @ で始まる値の先頭に ' を付ける）
  const csvCell = v => { let t = String(v == null ? '' : v); if (/^[=+\-@\t\r]/.test(t)) t = "'" + t; return `"${t.replace(/"/g, '""')}"`; };
  function downloadCsv(name, header, rows) {
    download(name, '﻿' + [header, ...rows].map(r => r.map(csvCell).join(',')).join('\r\n') + '\r\n', 'text/csv;charset=utf-8');
  }
  return { pairKey, all, get, set, merge, clear, on, textIds, ovId, editor, chip, stateName, STATES, downloadCsv, clean };
})();
