/* フォルダ比較 */
const FD = (() => {
  const st = { files: [null, null], names: ['', ''], rows: [], sort: { k: 'path', d: 1 }, running: false, sel: -1, gen: 0 };
  const slots = $$('.fd-slot');

  function setFolder(side, name, map) {
    st.files[side] = map; st.names[side] = name;
    const sl = slots[side]; sl.classList.add('loaded');
    $('.nm', sl).classList.remove('muted');
    $('.nm', sl).textContent = `${name}（${fmtNum(map.size)} ファイル）`;
    if (st.files[0] && st.files[1]) run();
  }
  function fromInput(side, fileList) {
    const map = new Map(); let root = '';
    for (const f of fileList) {
      const rel = f.webkitRelativePath || f.name; const parts = rel.split('/');
      if (!root) root = parts[0];
      map.set(parts.length > 1 ? parts.slice(1).join('/') : rel, f);
    }
    if (map.size) setFolder(side, root, map);
  }
  async function fromEntry(entry) {
    const map = new Map();
    const readAll = dir => new Promise((res, rej) => {
      const r = dir.createReader(), out = [];
      const next = () => r.readEntries(es => { if (!es.length) res(out); else { out.push(...es); next(); } }, rej);
      next();
    });
    const fileOf = fe => new Promise((res, rej) => fe.file(res, rej));
    async function walk(dir, prefix) {
      for (const e of await readAll(dir)) {
        if (e.isFile) map.set(prefix + e.name, await fileOf(e));
        else if (e.isDirectory) await walk(e, prefix + e.name + '/');
      }
    }
    await walk(entry, '');
    return map;
  }
  async function sameContent(a, b) {
    const CH = 4 * 1024 * 1024;
    for (let off = 0; off < a.size; off += CH) {
      const [x, y] = await Promise.all([a.slice(off, off + CH).arrayBuffer(), b.slice(off, off + CH).arrayBuffer()]);
      const u = new Uint8Array(x), v = new Uint8Array(y);
      if (u.length !== v.length) return false;
      // compare 32-bit words where possible
      const n4 = u.length >> 2, U = new Uint32Array(x, 0, n4), V = new Uint32Array(y, 0, n4);
      for (let i = 0; i < n4; i++) if (U[i] !== V[i]) return false;
      for (let i = n4 * 4; i < u.length; i++) if (u[i] !== v[i]) return false;
    }
    return true;
  }
  async function run() {
    if (!st.files[0] || !st.files[1]) return toast('左右にフォルダを指定してください');
    const gen = ++st.gen; // 比較中にフォルダが変わったら、前の比較は打ち切る
    st.running = true;
    const [A, B] = st.files, paths = Array.from(new Set([...A.keys(), ...B.keys()]));
    const content = $('#fdContent').checked;
    st.rows = paths.map(p => {
      const a = A.get(p), b = B.get(p);
      return { path: p, a, b, st: !a ? 'right' : !b ? 'left' : a.size !== b.size ? 'diff' : (content ? 'wait' : 'same') };
    });
    st.sel = -1; render();
    let done = 0; const todo = st.rows.filter(r => r.st === 'wait');
    for (const r of todo) {
      let same;
      try { same = await sameContent(r.a, r.b); } catch (e) { same = false; r.err = e.message; }
      if (gen !== st.gen) return;
      r.st = same ? 'same' : 'diff';
      if (++done % 25 === 0) { render(); $('#fdStatus').textContent = `内容を比較中… ${done} / ${todo.length}`; await sleep(0); }
    }
    st.running = false; render();
  }
  const ST = { same: ['同一', 'st-same'], diff: ['相違', 'st-diff'], left: ['左のみ', 'st-left'], right: ['右のみ', 'st-right'], wait: ['比較中', 'st-wait'] };
  const ORDER = { diff: 0, left: 1, right: 2, wait: 3, same: 4 };
  function render() {
    const show = new Set($$('.fdFilter').filter(c => c.checked).map(c => c.value)); show.add('wait');
    const { k, d } = st.sort;
    const val = r => k === 'path' ? r.path : k === 'st' ? ORDER[r.st] : k === 'ls' ? (r.a ? r.a.size : -1) : k === 'rs' ? (r.b ? r.b.size : -1) : k === 'lm' ? (r.a ? r.a.lastModified : 0) : (r.b ? r.b.lastModified : 0);
    const rows = st.rows.map((r, i) => ({ r, i })).filter(x => show.has(x.r.st)).sort((x, y) => { const a = val(x.r), b = val(y.r); return (a < b ? -1 : a > b ? 1 : x.r.path < y.r.path ? -1 : 1) * d; });
    const tb = $('#fdTable tbody');
    tb.innerHTML = rows.map(({ r, i }) => {
      const s = ST[r.st];
      const newer = r.a && r.b && r.st === 'diff' ? (r.a.lastModified > r.b.lastModified ? 0 : r.a.lastModified < r.b.lastModified ? 1 : -1) : -1;
      return `<tr data-i="${i}" class="${i === st.sel ? 'sel' : ''}"><td class="path">${esc(r.path)}</td><td><span class="st ${s[1]}">${s[0]}</span></td>` +
        `<td class="num">${r.a ? fmtSize(r.a.size) : ''}</td><td class="num">${r.b ? fmtSize(r.b.size) : ''}</td>` +
        `<td${newer === 0 ? ' style="font-weight:700"' : ''}>${r.a ? fmtDate(r.a.lastModified) : ''}</td><td${newer === 1 ? ' style="font-weight:700"' : ''}>${r.b ? fmtDate(r.b.lastModified) : ''}</td></tr>`;
    }).join('');
    const c = { same: 0, diff: 0, left: 0, right: 0, wait: 0 }; st.rows.forEach(r => c[r.st]++);
    if (!st.running) $('#fdStatus').innerHTML = st.rows.length
      ? `全 <b>${fmtNum(st.rows.length)}</b> ファイル　<span class="st st-diff">相違 ${c.diff}</span> <span class="st st-left">左のみ ${c.left}</span> <span class="st st-right">右のみ ${c.right}</span> <span class="st st-same">同一 ${c.same}</span>　<span class="muted">（更新日時が新しい方を太字で表示）</span>`
      : '左右にフォルダを指定して「比較」を押してください';
    $$('#fdTable th').forEach(th => { th.textContent = th.textContent.replace(/ [▲▼]$/, '') + (th.dataset.k === k ? (d > 0 ? ' ▲' : ' ▼') : ''); });
  }
  async function openRow(i) {
    const r = st.rows[i]; if (!r) return;
    st.sel = i; render();
    const sides = [r.a, r.b];
    await App.loadPair(sides);
  }

  slots.forEach((sl, side) => {
    const inp = $('input', sl);
    $('.fdPick', sl).onclick = () => inp.click();
    inp.onchange = () => { fromInput(side, inp.files); inp.value = ''; };
  });
  async function dropFolders(dt, side = 0) {
    const ents = Array.from(dt.items || []).map(it => it.webkitGetAsEntry && it.webkitGetAsEntry()).filter(e => e && e.isDirectory);
    if (!ents.length) return toast('フォルダをドロップしてください', true);
    await withBusy('フォルダを読み込み中…', async () => {
      if (ents.length >= 2) { setFolder(0, ents[0].name, await fromEntry(ents[0])); setFolder(1, ents[1].name, await fromEntry(ents[1])); }
      else setFolder(side, ents[0].name, await fromEntry(ents[0]));
    });
  }
  /* ---- CSV・レポート ---- */
  const ROWS_SORTED = () => st.rows.slice().sort((x, y) => x.path < y.path ? -1 : x.path > y.path ? 1 : 0);
  const dt = f => f && f.lastModified ? fmtDate(f.lastModified) : '';
  $('#fdCsv').onclick = () => {
    if (!st.rows.length) return toast('先にフォルダを比較してください');
    const q = v => `"${String(v).replace(/"/g, '""')}"`;
    const lines = [['ファイル', '状態', '左サイズ', '右サイズ', '左 更新日時', '右 更新日時'].map(q).join(',')];
    for (const r of ROWS_SORTED()) lines.push([r.path, ST[r.st][0], r.a ? r.a.size : '', r.b ? r.b.size : '', dt(r.a), dt(r.b)].map(q).join(','));
    // Excel で文字化けしないよう、BOM 付き UTF-8・CRLF にする
    download(`フォルダ比較_${st.names[0] || '左'}_${st.names[1] || '右'}.csv`, '\ufeff' + lines.join('\r\n') + '\r\n', 'text/csv;charset=utf-8');
  };
  $('#fdReport').onclick = () => {
    if (!st.rows.length) return toast('先にフォルダを比較してください');
    const c = { same: 0, diff: 0, left: 0, right: 0, wait: 0 }; st.rows.forEach(r => c[r.st]++);
    const order = { diff: 0, left: 1, right: 2, wait: 3, same: 4 };
    const rows = ROWS_SORTED().sort((x, y) => order[x.st] - order[y.st]);
    const body = `<table class="files"><tr><th>左</th><td>${esc(st.names[0])}</td></tr><tr><th>右</th><td>${esc(st.names[1])}</td></tr></table>` +
      `<table class="list"><thead><tr><th>ファイル</th><th>状態</th><th class="num">左サイズ</th><th class="num">右サイズ</th><th>左 更新日時</th><th>右 更新日時</th></tr></thead><tbody>` +
      rows.map(r => `<tr><td>${esc(r.path)}</td><td><span class="tag ${r.st}">${ST[r.st][0]}</span></td><td class="num">${r.a ? fmtSize(r.a.size) : ''}</td><td class="num">${r.b ? fmtSize(r.b.size) : ''}</td><td>${dt(r.a)}</td><td>${dt(r.b)}</td></tr>`).join('') + '</tbody></table>';
    const html = Report.page({
      title: `フォルダ比較レポート - ${st.names[0]} / ${st.names[1]}`, heading: 'フォルダ比較レポート',
      meta: `<b>全 ${fmtNum(st.rows.length)} ファイル</b>　相違 ${c.diff}・左のみ ${c.left}・右のみ ${c.right}・同一 ${c.same}${c.wait ? `・比較中 ${c.wait}` : ''}<br>比較方法: ${$('#fdContent').checked ? '内容まで比較' : 'サイズだけで判定'}`,
      body, css: '.tag.wait{background:#888}'
    });
    download(`フォルダ比較レポート_${st.names[0] || '左'}.html`, html, 'text/html;charset=utf-8');
  };
  $('#fdRun').onclick = run;
  $('#fdContent').onchange = () => { if (st.files[0] && st.files[1]) run(); };
  $$('.fdFilter').forEach(c => c.onchange = render);
  $$('#fdTable th').forEach(th => th.onclick = () => { const k = th.dataset.k; st.sort = { k, d: st.sort.k === k ? -st.sort.d : 1 }; render(); });
  // クリックでは表を描き直さない（描き直すとダブルクリックが成立しなくなるため）
  $('#fdTable tbody').addEventListener('click', e => {
    const tr = e.target.closest('tr'); if (!tr) return;
    st.sel = +tr.dataset.i;
    $$('#fdTable tbody tr').forEach(x => x.classList.toggle('sel', x === tr));
  });
  document.addEventListener('keydown', e => {
    if (App.mode !== 'folder' || e.key !== 'Enter' || st.sel < 0 || e.target.matches('input,select,textarea,button')) return;
    e.preventDefault(); openRow(st.sel);
  });
  $('#fdTable tbody').addEventListener('dblclick', e => { const tr = e.target.closest('tr'); if (tr) openRow(+tr.dataset.i); });
  return { dropFolders, st };
})();
