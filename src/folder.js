/* フォルダ比較 */
const FD = (() => {
  const st = { files: [null, null], names: ['', ''], rows: [], sort: { k: 'path', d: 1 }, running: false, sel: -1, gen: 0, readGen: 0 };
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
  /* ---- ドロップされたフォルダを読む ----
     読み方は2つ。先に File System Access API（getAsFileSystemHandle のフォルダのハンドル）を使い、使えなければ古い方式
     （webkitGetAsEntry の readEntries）を使う。ダウンロードした HTML をファイルとして開いたとき（file://）は、古い方式が
     EncodingError で失敗してフォルダを読めないため（GitHub Pages などの https では、どちらでも読める）。
     ctl：{ alive()：中止されていないか、tick(n)：読んだファイルの数、skipped：読めなかったファイルの名前 } */
  const CANCELLED = new Error('cancelled');
  const BATCH = 32; // 1つのフォルダの中のファイルは、この数ずつ並行して取り出す（1つずつだと、数千ファイルで時間がかかる）
  async function takeFiles(list, get, map, ctl) {
    for (let i = 0; i < list.length; i += BATCH) {
      if (!ctl.alive()) throw CANCELLED;
      await Promise.all(list.slice(i, i + BATCH).map(async ([path, src]) => {
        try { map.set(path, await get(src)); } catch (e) { ctl.skipped.push(path); }
      }));
      ctl.tick(map.size);
    }
  }
  async function fromHandle(root, ctl) {
    const map = new Map();
    async function walk(dir, prefix) {
      const files = [], dirs = [];
      for await (const [name, h] of dir.entries()) { if (!ctl.alive()) throw CANCELLED; (h.kind === 'file' ? files : dirs).push([prefix + name, h]); }
      await takeFiles(files, h => h.getFile(), map, ctl);
      for (const [path, h] of dirs) await walk(h, path + '/');
    }
    await walk(root, '');
    return map;
  }
  async function fromEntry(entry, ctl) {
    const map = new Map();
    const readAll = dir => new Promise((res, rej) => {
      const r = dir.createReader(), out = [];
      const next = () => r.readEntries(es => { if (!es.length) res(out); else { out.push(...es); next(); } }, rej);
      next();
    });
    const fileOf = fe => new Promise((res, rej) => fe.file(res, rej));
    async function walk(dir, prefix) {
      const es = await readAll(dir);
      if (!ctl.alive()) throw CANCELLED;
      await takeFiles(es.filter(e => e.isFile).map(e => [prefix + e.name, e]), fileOf, map, ctl);
      for (const e of es) if (e.isDirectory) await walk(e, prefix + e.name + '/');
    }
    await walk(entry, '');
    return map;
  }
  async function readDropped(src, ctl) {
    if (src.handle) {
      try {
        const h = await src.handle;
        if (h && h.kind === 'directory') return await fromHandle(h, ctl);
      } catch (e) { if (e === CANCELLED) throw e; console.warn('フォルダのハンドルで読めないため、別の方式で読みます', e); }
    }
    return fromEntry(src.entry, ctl);
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
      return { path: p, a, b, st: !a ? 'right' : !b ? 'left' : a.size !== b.size ? 'diff' : (content ? 'wait' : 'size') };
      // サイズだけで判定するときは、大きさが同じでも中身は確かめていないので「同一」とはしない（「サイズ同じ」）
    });
    st.sel = -1; render();
    // 内容の比較：結果が出た行だけを、その場で書き換える。比較の途中で表全体を描き直さない
    // （25件ごとに全行を描き直していたときは、数千ファイルで描画ばかりになり、画面が止まったようになった）。
    // 4つまで並行して比べ、0.1秒ごとに画面へ制御を返して、進み具合を表示する
    const todo = st.rows.filter(r => r.st === 'wait');
    let next = 0, done = 0, last = performance.now();
    const worker = async () => {
      while (next < todo.length && gen === st.gen) {
        const r = todo[next++];
        let same;
        // 読めなかったもの（比較のあいだに書き換えられた・消えた・開けない）は「相違」にしない。比べられていないので、別の状態にする
        try { same = await sameContent(r.a, r.b); } catch (e) { same = null; r.err = (e && (e.name || e.message)) || String(e); }
        if (gen !== st.gen) return;
        r.st = same === null ? 'error' : same ? 'same' : 'diff'; paintRow(r); done++;
        if (performance.now() - last > 100) { last = performance.now(); $('#fdStatus').textContent = `内容を比較中… ${fmtNum(done)} / ${fmtNum(todo.length)}`; await sleep(0); }
      }
    };
    await Promise.all([worker(), worker(), worker(), worker()]);
    if (gen !== st.gen) return;
    st.running = false; render(true);
  }
  const ST = { same: ['同一', 'st-same'], size: ['サイズ同じ（内容は未確認）', 'st-size'], diff: ['相違', 'st-diff'], left: ['左のみ', 'st-left'], right: ['右のみ', 'st-right'], wait: ['比較中', 'st-wait'], error: ['読み取りエラー（未比較）', 'st-error'] };
  const ORDER = { error: 0, diff: 1, left: 2, right: 3, wait: 4, size: 5, same: 6 }; // 並べ替え・レポートの順（確かめる必要のあるものを先に）
  const count = () => { const c = { same: 0, size: 0, diff: 0, left: 0, right: 0, wait: 0, error: 0 }; st.rows.forEach(r => c[r.st]++); return c; };
  // 1行の中身（セル）。比較の結果が出たとき、その行だけを書き換えるのにも使う
  function cellsHtml(r) {
    const s = ST[r.st];
    const newer = r.a && r.b && r.st === 'diff' ? (r.a.lastModified > r.b.lastModified ? 0 : r.a.lastModified < r.b.lastModified ? 1 : -1) : -1;
    return `<td class="path">${esc(r.path)}</td><td><span class="st ${s[1]}"${r.st === 'error' ? ` title="読めなかった理由：${esc(r.err || '')}"` : ''}>${s[0]}</span></td>` +
      `<td class="num">${r.a ? fmtSize(r.a.size) : ''}</td><td class="num">${r.b ? fmtSize(r.b.size) : ''}</td>` +
      `<td${newer === 0 ? ' style="font-weight:700"' : ''}>${r.a ? fmtDate(r.a.lastModified) : ''}</td><td${newer === 1 ? ' style="font-weight:700"' : ''}>${r.b ? fmtDate(r.b.lastModified) : ''}</td>`;
  }
  /* 表には、絞り込み・並べ替えのあとの先頭の PAGE 行だけを出し、下までスクロールしたら続きを足す。
     数千行の表は、1行書き換えるたびに表全体の列の幅を計算し直すので、比較の間じゅう画面が止まったようになる
     （3,000 ファイルで約50秒かかっていた）。件数・CSV・レポートは、表に出している行数に関係なく全件が対象 */
  const PAGE = 300;
  let view = [], shown = PAGE; // view：絞り込み・並べ替えのあとの行（{r, i}）。shown：表に出している行数の上限
  let trOf = new Map(); // 行（st.rows の要素）→ 表の tr（表に出している行だけ）
  function paintRow(r) { const tr = trOf.get(r); if (tr) tr.innerHTML = cellsHtml(r); }
  const rowHtml = ({ r, i }) => `<tr data-i="${i}" class="${i === st.sel ? 'sel' : ''}" aria-selected="${i === st.sel}">${cellsHtml(r)}</tr>`;
  const moreHtml = () => view.length > shown ? `<tr class="more"><td colspan="6">ほか ${fmtNum(view.length - shown)} 行（下へスクロールすると続きを表示します。件数・CSV・レポートは全件が対象です）</td></tr>` : '';
  function drawRows() {
    const tb = $('#fdTable tbody'), part = view.slice(0, shown);
    tb.innerHTML = part.map(rowHtml).join('') + moreHtml();
    trOf = new Map(); part.forEach(({ r }, k) => trOf.set(r, tb.children[k]));
  }
  // 続きの PAGE 行を表の末尾に足す（足したら true）
  function showMore() {
    if (shown >= view.length) return false;
    const tb = $('#fdTable tbody'), more = $('tr.more', tb), from = shown, part = view.slice(from, from + PAGE);
    shown = from + part.length;
    if (more) more.remove();
    tb.insertAdjacentHTML('beforeend', part.map(rowHtml).join('') + moreHtml());
    part.forEach(({ r }, k) => trOf.set(r, tb.children[from + k]));
    return true;
  }
  // keep：表に出している行数を保つ（比較が終わったとき・行を開くとき）。絞り込み・並べ替えを変えたときは先頭の PAGE 行に戻す
  function render(keep) {
    const show = new Set($$('.fdFilter').filter(c => c.checked).map(c => c.value)); show.add('wait'); if (show.has('same')) show.add('size');
    show.add('error'); // 読めなかったものは、絞り込みにかかわらず出す
    const { k, d } = st.sort;
    const val = r => k === 'path' ? r.path : k === 'st' ? ORDER[r.st] : k === 'ls' ? (r.a ? r.a.size : -1) : k === 'rs' ? (r.b ? r.b.size : -1) : k === 'lm' ? (r.a ? r.a.lastModified : 0) : (r.b ? r.b.lastModified : 0);
    const rows = st.rows.map((r, i) => ({ r, i })).filter(x => show.has(x.r.st)).sort((x, y) => { const a = val(x.r), b = val(y.r); return (a < b ? -1 : a > b ? 1 : x.r.path < y.r.path ? -1 : 1) * d; });
    view = rows; shown = keep === true ? Math.max(shown, PAGE) : PAGE;
    // 選んでいる行は、表に出す範囲に入れる
    const at = st.sel >= 0 ? view.findIndex(x => x.i === st.sel) : -1; if (at >= shown) shown = at + 1 + PAGE;
    drawRows();
    const c = count();
    if (!st.running) $('#fdStatus').innerHTML = st.rows.length
      ? `全 <b>${fmtNum(st.rows.length)}</b> ファイル　${c.error ? `<span class="st st-error">読み取りエラー ${c.error}</span> ` : ''}<span class="st st-diff">相違 ${c.diff}</span> <span class="st st-left">左のみ ${c.left}</span> <span class="st st-right">右のみ ${c.right}</span> <span class="st st-same">同一 ${c.same}</span>${c.size ? ` <span class="st st-size">サイズ同じ ${c.size}</span>` : ''}　<span class="muted">（更新日時が新しい方を太字で表示）</span>`
      : '左右にフォルダを指定して「比較」を押してください';
    $$('#fdTable th').forEach(th => { th.textContent = th.textContent.replace(/ [▲▼]$/, '') + (th.dataset.k === k ? (d > 0 ? ' ▲' : ' ▼') : ''); });
  }
  async function openRow(i) {
    const r = st.rows[i]; if (!r) return;
    st.sel = i; render(true);
    const sides = [r.a, r.b];
    await App.loadPair(sides);
  }

  slots.forEach((sl, side) => {
    const inp = $('input', sl);
    $('.fdPick', sl).onclick = () => inp.click();
    inp.onchange = () => { fromInput(side, inp.files); inp.value = ''; };
  });
  async function dropFolders(dt, side = 0) {
    // ドロップされたもの（DataTransferItem）は、このイベントの間しか使えない。待つ前に、読むための手がかり（ハンドルとエントリ）を取っておく
    const srcs = Array.from(dt.items || []).map(it => {
      const entry = it.webkitGetAsEntry && it.webkitGetAsEntry();
      if (!entry || !entry.isDirectory) return null;
      let handle = null;
      try { if (it.getAsFileSystemHandle) handle = it.getAsFileSystemHandle(); } catch (e) { }
      if (handle) handle.catch(() => { }); // 使わずに終わっても、失敗を未処理のまま残さない
      return { name: entry.name, entry, handle };
    }).filter(Boolean);
    if (!srcs.length) return toast('フォルダをドロップしてください', true);
    const targets = srcs.length >= 2 ? [[0, srcs[0]], [1, srcs[1]]] : [[side, srcs[0]]];
    // 中止できるようにする（大きなフォルダやネットワーク上のフォルダは時間がかかる。読み取りが返ってこないときも、画面を取り戻せる）
    const gen = ++st.readGen, ctl = { alive: () => gen === st.readGen, skipped: [], tick: () => { } };
    let cancel; const stopped = new Promise((_, rej) => { cancel = () => { st.readGen++; rej(CANCELLED); }; });
    stopped.catch(() => { });
    const got = [];
    try {
      await withBusy('フォルダを読み込み中…', async () => {
        for (const [sd, src] of targets) {
          ctl.tick = n => { $('#busyMsg').textContent = `フォルダを読み込み中…（${sd ? '右' : '左'}：${fmtNum(n)} ファイル）`; };
          got.push([sd, src.name, await Promise.race([readDropped(src, ctl), stopped])]);
        }
      }, { onCancel: () => cancel() });
    } catch (e) {
      if (e === CANCELLED) return toast('フォルダの読み込みを中止しました');
      console.error(e);
      return toast(`フォルダを読み込めませんでした（${(e && (e.name || e.message)) || e}）。「フォルダを選択」のボタンから指定してください`, true);
    }
    for (const [sd, name, map] of got) setFolder(sd, name, map);
    if (ctl.skipped.length) toast(`読めないファイルが ${fmtNum(ctl.skipped.length)} 個あり、一覧に入っていません（${ctl.skipped.slice(0, 3).join('、')}${ctl.skipped.length > 3 ? ' ほか' : ''}）`, true, 8000);
  }
  /* ---- CSV・レポート ---- */
  const ROWS_SORTED = () => st.rows.slice().sort((x, y) => x.path < y.path ? -1 : x.path > y.path ? 1 : 0);
  const dt = f => f && f.lastModified ? fmtDate(f.lastModified) : '';
  $('#fdCsv').onclick = () => {
    if (!st.rows.length) return toast('先にフォルダを比較してください');
    // 表計算ソフトで数式として実行されないよう、= + - @ タブ CR で始まる値の先頭に ' を付ける（CSV インジェクション対策）
    const q = v => { let t = String(v); if (/^[=+\-@\t\r]/.test(t)) t = "'" + t; return `"${t.replace(/"/g, '""')}"`; };
    const lines = [['ファイル', '状態', '左サイズ', '右サイズ', '左 更新日時', '右 更新日時'].map(q).join(',')];
    for (const r of ROWS_SORTED()) lines.push([r.path, ST[r.st][0], r.a ? r.a.size : '', r.b ? r.b.size : '', dt(r.a), dt(r.b)].map(q).join(','));
    // Excel で文字化けしないよう、BOM 付き UTF-8・CRLF にする
    download(`フォルダ比較_${st.names[0] || '左'}_${st.names[1] || '右'}.csv`, '\ufeff' + lines.join('\r\n') + '\r\n', 'text/csv;charset=utf-8');
  };
  $('#fdReport').onclick = async () => {
    if (!st.rows.length) return toast('先にフォルダを比較してください');
    const o = await Report.options('folder', 'フォルダ比較のレポート', '出力する内容を選んでください。',
      [{ k: 'rows', label: '載せるファイル', type: 'radio', def: 'all', choices: [['all', 'すべて'], ['diff', '違いのあるものだけ（同一を除く）']] },
        { k: 'dates', label: '更新日時', type: 'check', def: true }, { k: 'sizes', label: 'サイズ', type: 'check', def: true }],
      [{ label: '出力', value: 'ok', primary: true }]);
    if (!o) return;
    const c = count();
    const rows = ROWS_SORTED().filter(r => o.rows === 'all' || r.st !== 'same').sort((x, y) => ORDER[x.st] - ORDER[y.st]);
    const sz = o.sizes, dts = o.dates;
    const body = `<table class="files"><tr><th>左</th><td>${esc(st.names[0])}</td></tr><tr><th>右</th><td>${esc(st.names[1])}</td></tr></table>` +
      `<table class="list"><thead><tr><th>ファイル</th><th>状態</th>${sz ? '<th class="num">左サイズ</th><th class="num">右サイズ</th>' : ''}${dts ? '<th>左 更新日時</th><th>右 更新日時</th>' : ''}</tr></thead><tbody>` +
      rows.map(r => `<tr><td>${esc(r.path)}</td><td><span class="tag ${r.st}">${ST[r.st][0]}</span></td>${sz ? `<td class="num">${r.a ? fmtSize(r.a.size) : ''}</td><td class="num">${r.b ? fmtSize(r.b.size) : ''}</td>` : ''}${dts ? `<td>${dt(r.a)}</td><td>${dt(r.b)}</td>` : ''}</tr>`).join('') + '</tbody></table>' +
      (o.rows === 'diff' && c.same ? `<p class="sub">同一の ${c.same} ファイルは省略しています。</p>` : '');
    const html = Report.page({
      title: `フォルダ比較レポート - ${st.names[0]} / ${st.names[1]}`, heading: 'フォルダ比較レポート',
      meta: `<b>全 ${fmtNum(st.rows.length)} ファイル</b>　${c.error ? `<b style="color:#b42318">読み取りエラー（未比較）${c.error}</b>・` : ''}相違 ${c.diff}・左のみ ${c.left}・右のみ ${c.right}・同一 ${c.same}${c.size ? `・サイズ同じ（内容は未確認）${c.size}` : ''}${c.wait ? `・比較中 ${c.wait}` : ''}<br>比較方法: ${$('#fdContent').checked ? '内容まで比較' : 'サイズだけで判定'}`,
      body, css: '.tag.wait{background:#888}.tag.size{background:#8a6d00}.tag.error{background:#7c2d92}'
    });
    download(`フォルダ比較レポート_${st.names[0] || '左'}.html`, html, 'text/html;charset=utf-8');
  };
  $('#fdRun').onclick = run;
  $('#fdContent').onchange = () => { if (st.files[0] && st.files[1]) run(); };
  $$('.fdFilter').forEach(c => c.onchange = () => render());
  // 下の方までスクロールしたら、続きの行を足す
  $('.fd-table-wrap').addEventListener('scroll', e => { const w = e.currentTarget; if (w.scrollTop + w.clientHeight > w.scrollHeight - 800) showMore(); }, { passive: true });
  $$('#fdTable th').forEach(th => th.onclick = () => { const k = th.dataset.k; st.sort = { k, d: st.sort.k === k ? -st.sort.d : 1 }; render(); });
  // 行を選ぶ。表は描き直さない（描き直すとダブルクリックが成立しなくなるため）
  function selectRow(tr, scroll) {
    st.sel = +tr.dataset.i;
    $$('#fdTable tbody tr[data-i]').forEach(x => { x.classList.toggle('sel', x === tr); x.setAttribute('aria-selected', x === tr); });
    if (scroll) tr.scrollIntoView({ block: 'nearest' });
  }
  $('#fdTable tbody').addEventListener('click', e => { const tr = e.target.closest('tr[data-i]'); if (tr) selectRow(tr, false); });
  // キーボード：↑↓（Home・End）で、表示している順に行を選ぶ。Enter で中身を比較する
  document.addEventListener('keydown', e => {
    if (App.mode !== 'folder' || $('#modal').classList.contains('on') || e.target.matches('input,select,textarea')) return;
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key) && !e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      let trs = $$('#fdTable tbody tr[data-i]'); if (!trs.length) return;
      const cur = trs.findIndex(x => +x.dataset.i === st.sel), down = e.key === 'ArrowDown';
      // 表に出している最後の行から ↓ で先へ進むときは、続きの行を足してから動く
      // （End は、今、表に出している最後の行へ。そこまでスクロールすると続きが足される）
      if (down && cur === trs.length - 1 && showMore()) trs = $$('#fdTable tbody tr[data-i]');
      const k = e.key === 'Home' ? 0 : e.key === 'End' ? trs.length - 1 : cur < 0 ? (down ? 0 : trs.length - 1) : Math.max(0, Math.min(trs.length - 1, cur + (down ? 1 : -1)));
      // 矢印で行を選んだら、フォーカスも一覧に移す（ボタンにフォーカスが残っていると、Enter がそのボタンを押してしまう）
      const wrap = $('.fd-table-wrap'); if (document.activeElement !== wrap) wrap.focus({ preventScroll: true });
      e.preventDefault(); selectRow(trs[k], true); return;
    }
    if (e.key !== 'Enter' || st.sel < 0 || e.target.matches('button')) return;
    e.preventDefault(); openRow(st.sel);
  });
  $('#fdTable tbody').addEventListener('dblclick', e => { const tr = e.target.closest('tr[data-i]'); if (tr) openRow(+tr.dataset.i); });
  return { dropFolders, st };
})();
