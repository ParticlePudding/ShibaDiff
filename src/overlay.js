/* 重ね合わせ比較（画像差分） */
const OV = (() => {
  const view = $('#ovView');
  const st = {
    mode: 'diff', l: 0, r: 0, dx: 0, dy: 0, ang: 0, zoom: 'fit', regions: [], regIdx: -1, cache: new Map(),
    blink: 0, blinkOn: false, dirty: true, out: null, base: null, cl: null, cr: null, scanning: false, gen: 0,
    align: new Map() // ページの組み合わせごとの位置合わせ量 "l:r" -> [dx, dy]
  };
  /* スキャン画像（画像ファイル・文字情報のないPDF）を含むか */
  const scanMode = () => [0, 1].some(i => App.visualOnly(S[i]));
  const pairKey = () => `${st.l}:${st.r}`;
  function showOffset() { $('#ovDx').value = st.dx; $('#ovDy').value = st.dy; $('#ovRot').value = st.ang; }
  const pages = async side => (S[side] ? S[side].getPages() : null);

  async function renderAt(side, idx, W) {
    const key = `${S[side].key}:${idx}:${W}`;
    if (st.cache.has(key)) { const c = st.cache.get(key); st.cache.delete(key); st.cache.set(key, c); return c; }
    const pg = (await pages(side))[idx];
    const cv = document.createElement('canvas');
    await pg.draw(cv, W / pg.w);
    st.cache.set(key, cv);
    while (st.cache.size > 10) st.cache.delete(st.cache.keys().next().value);
    return cv;
  }
  function renderWidth(pl, pr) {
    const w = Math.max(pl ? pl.w : 0, pr ? pr.w : 0);
    return Math.round(Math.max(900, Math.min(2400, w * 2)));
  }

  function fillSelect(sel, n, v) {
    sel.innerHTML = Array.from({ length: n }, (_, i) => `<option value="${i}">${i + 1} / ${n}</option>`).join('');
    sel.value = String(Math.min(v, Math.max(0, n - 1)));
  }

  /* ---- pixel helpers ---- */
  /* 右画像を「中心で ang 度回転 → (dx,dy) 平行移動」して描く */
  function drawR(ctx, cv, dx, dy, ang) {
    if (!ang) { ctx.drawImage(cv, dx, dy); return; }
    ctx.save(); ctx.translate(dx + cv.width / 2, dy + cv.height / 2); ctx.rotate(ang * Math.PI / 180);
    ctx.drawImage(cv, -cv.width / 2, -cv.height / 2); ctx.restore();
  }
  function lumData(cv, W, H, dx = 0, dy = 0, ang = 0) {
    const c = document.createElement('canvas'); c.width = W; c.height = H;
    const x = c.getContext('2d', { willReadFrequently: true });
    x.fillStyle = '#fff'; x.fillRect(0, 0, W, H); drawR(x, cv, dx, dy, ang);
    const d = x.getImageData(0, 0, W, H).data, g = new Uint8Array(W * H);
    for (let i = 0, j = 0; j < g.length; i += 4, j++) g[j] = (d[i] * 77 + d[i + 1] * 150 + d[i + 2] * 29) >> 8;
    return g;
  }

  function diffImage(cl, cr, thr, faint) {
    const W = Math.max(cl.width, cr.width + Math.max(0, st.dx)), H = Math.max(cl.height, cr.height + Math.max(0, st.dy));
    const a = lumData(cl, W, H), b = lumData(cr, W, H, st.dx, st.dy, st.ang);
    // ずれの許容（px）：スキャン画像は既定で2px、CADやWordから作ったPDFは0px（小さな変更を見落とさないため）
    const rad = +$('#ovTolPx').value || 0, tol = rad > 0;
    // スキャン画像は濃淡（にじみ・かすれ）の差を拾わないよう白黒に二値化してから比べる
    if (scanMode() && tol) for (const g of [a, b]) for (let i = 0; i < g.length; i++) g[i] = g[i] < 170 ? 0 : 255;
    const mf = g => { let o = g; for (let k = 0; k < rad; k++) o = minFilter(o, W, H); return o; };
    const aMin = tol ? mf(a) : a, bMin = tol ? mf(b) : b;
    const img = new ImageData(W, H), d = img.data;
    const CELL = 16, gw = Math.ceil(W / CELL), gh = Math.ceil(H / CELL), grid = new Uint16Array(gw * gh);
    let changed = 0, ink = 0;
    for (let y = 0, j = 0; y < H; y++) {
      const gy = (y / CELL | 0) * gw;
      for (let x = 0; x < W; x++, j++) {
        const ga = a[j], gb = b[j], k = j * 4;
        if (ga < 200 || gb < 200) ink++;
        if (ga + thr < bMin[j]) { d[k] = 229; d[k + 1] = 50; d[k + 2] = 45; changed++; grid[gy + (x / CELL | 0)]++; }
        else if (gb + thr < aMin[j]) { d[k] = 26; d[k + 1] = 115; d[k + 2] = 232; changed++; grid[gy + (x / CELL | 0)]++; }
        else { const m = Math.min(ga, gb), v = faint ? 255 - ((255 - m) * 0.32 | 0) : m; d[k] = d[k + 1] = d[k + 2] = v; }
        d[k + 3] = 255;
      }
    }
    // regions: connected components of changed cells (with 1-cell dilation)
    const mark = new Uint8Array(gw * gh);
    for (let i = 0; i < grid.length; i++) if (grid[i] >= 3) mark[i] = 1;
    const seen = new Uint8Array(gw * gh), regions = [];
    for (let i = 0; i < mark.length; i++) {
      if (!mark[i] || seen[i]) continue;
      let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1, cnt = 0; const q = [i]; seen[i] = 1;
      while (q.length) {
        const c = q.pop(), cx = c % gw, cy = (c / gw) | 0; cnt += grid[c];
        x0 = Math.min(x0, cx); y0 = Math.min(y0, cy); x1 = Math.max(x1, cx); y1 = Math.max(y1, cy);
        for (let yy = cy - 2; yy <= cy + 2; yy++) for (let xx = cx - 2; xx <= cx + 2; xx++) {
          if (xx < 0 || yy < 0 || xx >= gw || yy >= gh) continue;
          const n = yy * gw + xx; if (mark[n] && !seen[n]) { seen[n] = 1; q.push(n); }
        }
      }
      if (cnt < 8) continue;
      regions.push({ x: x0 * CELL - 6, y: y0 * CELL - 6, w: (x1 - x0 + 1) * CELL + 12, h: (y1 - y0 + 1) * CELL + 12 });
    }
    regions.sort((p, q) => (Math.abs(p.y - q.y) < 30 ? p.x - q.x : p.y - q.y));
    return { img, W, H, changed, ink, regions };
  }

  /* 3x3 minimum filter (= ink dilation by 1px) */
  function minFilter(g, W, H) {
    const t = new Uint8Array(g.length), o = new Uint8Array(g.length);
    for (let y = 0; y < H; y++) {
      const r = y * W;
      for (let x = 0; x < W; x++) {
        let m = g[r + x]; if (x > 0 && g[r + x - 1] < m) m = g[r + x - 1]; if (x < W - 1 && g[r + x + 1] < m) m = g[r + x + 1]; t[r + x] = m;
      }
    }
    for (let y = 0; y < H; y++) {
      const r = y * W;
      for (let x = 0; x < W; x++) {
        let m = t[r + x]; if (y > 0 && t[r - W + x] < m) m = t[r - W + x]; if (y < H - 1 && t[r + W + x] < m) m = t[r + W + x]; o[r + x] = m;
      }
    }
    return o;
  }

  /* ---- auto alignment ---- */
  /* 自動位置合わせ：平行移動と回転（±1.2°）を推定して [dx, dy, ang] を返す */
  function autoAlign(cl, cr) {
    const W2 = Math.max(cl.width, cr.width), H2 = Math.max(cl.height, cr.height);
    const ink = (cv, f, ang) => {
      const w = Math.ceil(W2 / f), h = Math.ceil(H2 / f);
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      const x = c.getContext('2d', { willReadFrequently: true });
      x.fillStyle = '#fff'; x.fillRect(0, 0, w, h); x.imageSmoothingEnabled = true; x.imageSmoothingQuality = 'high'; x.scale(1 / f, 1 / f); drawR(x, cv, 0, 0, ang);
      const d = x.getImageData(0, 0, w, h).data, g = new Uint8Array(w * h);
      for (let i = 0, j = 0; j < g.length; i += 4, j++) g[j] = 255 - ((d[i] * 77 + d[i + 1] * 150 + d[i + 2] * 29) >> 8);
      return { g, w, h };
    };
    const score = (A, B, W, H, dx, dy, step) => {
      let s = 0, n = 0;
      for (let y = Math.max(0, dy); y < Math.min(H, H + dy); y += step) {
        const ra = y * W, rb = (y - dy) * W;
        for (let x = Math.max(0, dx); x < Math.min(W, W + dx); x += step) {
          const va = A[ra + x], vb = B[rb + x - dx];
          if (va | vb) { s += Math.abs(va - vb); n++; }
        }
      }
      return n ? s / n : 1e9;
    };
    const search = (f, angs, cx, cy, R, step) => {
      const A = ink(cl, f, 0); let best = { s: 1e18 };
      for (const ang of angs) {
        const B = ink(cr, f, ang);
        for (let dy = cy - R; dy <= cy + R; dy++) for (let dx = cx - R; dx <= cx + R; dx++) {
          const sc = score(A.g, B.g, A.w, A.h, dx, dy, step);
          if (sc < best.s) best = { s: sc, dx, dy, ang };
        }
      }
      return best;
    };
    const range = (c, r, st) => { const o = []; for (let v = c - r; v <= c + r + 1e-9; v += st) o.push(Math.round(v * 100) / 100); return o; };
    // 1) 1/4 に縮小して平行移動だけを ±14 で探す
    let b = search(4, [0], 0, 0, 14, 1);
    // 2) 1/3 で回転 -1.2～1.2°（0.1°刻み）と平行移動 ±3 を探す
    b = search(3, range(0, 1.2, 0.1), Math.round(b.dx * 4 / 3), Math.round(b.dy * 4 / 3), 3, 2);
    // 3) 1/3 で回転を 0.02° 刻みで詰める
    b = search(3, range(b.ang, 0.06, 0.02), b.dx, b.dy, 1, 2);
    // 4) 原寸で平行移動 ±3
    b = search(1, [b.ang], b.dx * 3, b.dy * 3, 3, 3);
    return [b.dx, b.dy, Math.abs(b.ang) < 0.01 ? 0 : b.ang];
  }

  /* ---- drawing ---- */
  function stopBlink() { clearInterval(st.blink); st.blink = 0; }
  function cssWidth(px) {
    if (st.zoom === 'fit') return Math.max(200, view.clientWidth - 30);
    return px * (+st.zoom) * (96 / 72) / (st.scale || 2);
  }
  function placeCanvas(cv, half = false) {
    let w = cssWidth(cv.width);
    if (half && st.zoom === 'fit') w = (view.clientWidth - 50) / 2;
    cv.style.width = w + 'px'; cv.style.height = (cv.height / cv.width * w) + 'px';
  }
  function drawBoxes() {
    if (!st.out || st.mode !== 'diff') return;
    const c = st.out.getContext('2d');
    c.putImageData(st.base.img, 0, 0);
    if (!$('#ovBoxes').checked) return;
    st.regions.forEach((r, i) => {
      c.lineWidth = i === st.regIdx ? 6 : 3; c.strokeStyle = i === st.regIdx ? '#ff6d00' : 'rgba(255,152,0,.9)';
      c.strokeRect(r.x, r.y, r.w, r.h);
      c.fillStyle = i === st.regIdx ? '#ff6d00' : 'rgba(255,152,0,.95)'; c.font = 'bold 20px sans-serif';
      const label = String(i + 1), tw = c.measureText(label).width + 10;
      c.fillRect(r.x, r.y - 24, tw, 24); c.fillStyle = '#fff'; c.fillText(label, r.x + 5, r.y - 5);
    });
  }

  async function update() {
    st.dirty = false; stopBlink();
    const gen = ++st.gen;
    const pl = await pages(0).catch(() => null), pr = await pages(1).catch(() => null);
    if (gen !== st.gen) return;
    fillSelect($('#ovLPage'), pl ? pl.length : 0, st.l); fillSelect($('#ovRPage'), pr ? pr.length : 0, st.r);
    if (!pl && !pr) { view.innerHTML = '<div class="pv-empty" style="color:#f2f4f6">左右にPDFまたは画像を読み込むと、ページを重ねて変更箇所を検出します<br><span style="font-size:12.5px">スキャン画像（PNG/JPEG）同士や、PDFとスキャン画像の比較にも使えます</span></div>'; $('#ovStats').textContent = '—'; return; }
    const pgL = pl && pl[st.l], pgR = pr && pr[st.r];
    const W = renderWidth(pgL, pgR); st.scale = W / Math.max(pgL ? pgL.w : 0, pgR ? pgR.w : 0);
    let cl, cr;
    try {
      [cl, cr] = await Promise.all([pgL ? renderAt(0, st.l, W) : null, pgR ? renderAt(1, st.r, W) : null]);
    } catch (e) { view.innerHTML = `<div class="pv-empty">描画に失敗しました: ${esc(e.message || '')}</div>`; return; }
    if (gen !== st.gen) return;
    st.cl = cl; st.cr = cr;
    // 位置合わせ：手動・自動で決めた量をページの組ごとに覚える。スキャンは初回に自動で合わせる
    let autoMsg = '';
    if (st.align.has(pairKey())) [st.dx, st.dy, st.ang] = st.align.get(pairKey());
    else if (cl && cr && scanMode()) { [st.dx, st.dy, st.ang] = autoAlign(cl, cr); st.align.set(pairKey(), [st.dx, st.dy, st.ang]); autoMsg = `<br><span class="muted">スキャン画像のため自動で位置合わせしました（X ${st.dx} / Y ${st.dy}px${st.ang ? ` / 回転 ${st.ang}°` : ''}）</span>`; }
    else { st.dx = 0; st.dy = 0; st.ang = 0; }
    showOffset();
    if (gen !== st.gen) return;
    view.innerHTML = '';
    if (!cl || !cr || st.mode === 'side') {
      const pair = document.createElement('div'); pair.className = 'pair';
      for (const c of [cl, cr]) if (c) { const d = document.createElement('canvas'); d.width = c.width; d.height = c.height; d.getContext('2d').drawImage(c, 0, 0); placeCanvas(d, !!(cl && cr)); pair.appendChild(d); }
      view.appendChild(pair);
      $('#ovStats').innerHTML = (!cl || !cr) ? '片側のみ読み込まれています' : '並べて表示中';
      return;
    }
    const out = document.createElement('canvas');
    const W2 = Math.max(cl.width, cr.width + Math.max(0, st.dx)), H2 = Math.max(cl.height, cr.height + Math.max(0, st.dy));
    out.width = W2; out.height = H2;
    const c = out.getContext('2d');
    st.out = out;
    if (st.mode === 'diff') {
      const res = diffImage(cl, cr, +$('#ovThr').value, $('#ovFaint').checked);
      st.base = res; st.regions = res.regions; st.regIdx = -1;
      drawBoxes();
      const pct = res.ink ? res.changed / res.ink * 100 : 0;
      $('#ovStats').innerHTML = res.regions.length
        ? `<b style="color:#b42318">${res.regions.length} 箇所</b>の変更を検出<br><span class="muted">変化量: ${pct.toFixed(2)}%（文字・図の部分に対する割合）</span>`
        : (res.changed ? `<b>目立った変更はありません</b><br><span class="muted">わずかな差 ${pct.toFixed(3)}%（位置ずれや描画の違い）</span>` : '<b style="color:#21752f">✓ 差異は見つかりませんでした</b>');
      $('#ovStats').innerHTML += autoMsg;
    } else if (st.mode === 'overlay') {
      c.fillStyle = '#fff'; c.fillRect(0, 0, W2, H2); c.drawImage(cl, 0, 0);
      c.globalAlpha = +$('#ovOpacity').value / 100; drawR(c, cr, st.dx, st.dy, st.ang); c.globalAlpha = 1;
      $('#ovStats').innerHTML = '左の上に右を半透明で重ねています';
    } else if (st.mode === 'swipe') {
      const drawSwipe = () => {
        const x = Math.round(W2 * +$('#ovSwipe').value / 100);
        c.fillStyle = '#fff'; c.fillRect(0, 0, W2, H2); c.drawImage(cl, 0, 0);
        c.save(); c.beginPath(); c.rect(x, 0, W2 - x, H2); c.clip(); c.fillStyle = '#fff'; c.fillRect(x, 0, W2 - x, H2); drawR(c, cr, st.dx, st.dy, st.ang); c.restore();
        c.fillStyle = '#1f6feb'; c.fillRect(x - 2, 0, 4, H2);
        c.font = 'bold 22px sans-serif'; c.fillStyle = 'rgba(192,80,77,.9)'; c.fillText('◀ 左', Math.max(8, x - 80), 30); c.fillStyle = 'rgba(58,143,74,.9)'; c.fillText('右 ▶', Math.min(W2 - 70, x + 12), 30);
      };
      drawSwipe(); st.drawSwipe = drawSwipe;
      const move = e => { const r = out.getBoundingClientRect(); $('#ovSwipe').value = Math.max(0, Math.min(100, (e.clientX - r.left) / r.width * 100)); drawSwipe(); };
      out.addEventListener('pointerdown', e => { out.setPointerCapture(e.pointerId); move(e); });
      out.addEventListener('pointermove', e => { if (e.buttons & 1) move(e); });
      out.style.cursor = 'ew-resize';
      $('#ovStats').innerHTML = '画像上をドラッグして境界を動かせます';
    } else if (st.mode === 'blink') {
      const frame = () => {
        st.blinkOn = !st.blinkOn;
        c.fillStyle = '#fff'; c.fillRect(0, 0, W2, H2);
        if (st.blinkOn) drawR(c, cr, st.dx, st.dy, st.ang); else c.drawImage(cl, 0, 0);
        c.font = 'bold 26px sans-serif'; c.fillStyle = st.blinkOn ? 'rgba(58,143,74,.95)' : 'rgba(192,80,77,.95)';
        c.fillText(st.blinkOn ? '右' : '左', 14, 34);
      };
      frame(); st.blink = setInterval(frame, 650);
      $('#ovStats').innerHTML = '左右を交互に表示しています（変わった部分がちらつきます）';
    }
    placeCanvas(out);
    view.appendChild(out);
  }

  function gotoRegion(d) {
    if (st.mode !== 'diff' || !st.regions.length) return toast('変更箇所はありません');
    st.regIdx = (st.regIdx + d + st.regions.length) % st.regions.length;
    drawBoxes();
    const r = st.regions[st.regIdx], k = st.out.clientWidth / st.out.width;
    view.scrollTo({ top: st.out.offsetTop + r.y * k - view.clientHeight / 3, left: st.out.offsetLeft + r.x * k - view.clientWidth / 3, behavior: 'smooth' });
  }

  async function scan() {
    if (st.scanning) { st.scanning = false; return; }
    const pl = await pages(0).catch(() => null), pr = await pages(1).catch(() => null);
    if (!pl || !pr) return toast('左右に文書を読み込んでください');
    const n = Math.min(pl.length, pr.length), res = $('#ovScanRes'), btn = $('#ovScan');
    st.scanning = true; btn.textContent = '中止'; res.innerHTML = '';
    const rows = [];
    for (let i = 0; i < n && st.scanning; i++) {
      res.innerHTML = `<span class="muted">調べています… ${i + 1} / ${n}</span>`;
      // 1ページずつ表示したときと同じ解像度・位置合わせで調べる（件数をそろえるため）
      const W = renderWidth(pl[i], pr[i]);
      const a = await renderAt(0, i, W), b = await renderAt(1, i, W);
      const key = `${i}:${i}`;
      let off = st.align.get(key);
      if (!off) { off = scanMode() ? autoAlign(a, b) : [0, 0, 0]; if (scanMode()) st.align.set(key, off); }
      const save = [st.dx, st.dy, st.ang]; [st.dx, st.dy, st.ang] = off;
      const r = diffImage(a, b, +$('#ovThr').value, $('#ovFaint').checked); [st.dx, st.dy, st.ang] = save;
      rows.push({ i, pct: r.ink ? r.changed / r.ink * 100 : 0, regs: r.regions.length });
      await sleep(0);
    }
    const stopped = !st.scanning; st.scanning = false; btn.textContent = '全ページの差分を調べる';
    const mx = Math.max(1, ...rows.map(r => r.pct));
    const changedPages = rows.filter(r => r.regs > 0).length;
    res.innerHTML = `<div style="margin-bottom:4px">${stopped ? '（途中で中止）' : ''}変更ありのページ: <b>${changedPages}</b> / ${rows.length}${pl.length !== pr.length ? `<br><span style="color:#b42318">ページ数が違います（左 ${pl.length} / 右 ${pr.length}）</span>` : ''}</div>` +
      `<table class="scan-table"><tr><th>頁</th><th>箇所</th><th style="width:50%">変化量</th></tr>` +
      rows.map(r => `<tr data-i="${r.i}"><td>${r.i + 1}</td><td>${r.regs ? `<b style="color:#b42318">${r.regs}</b>` : '<span class="muted">0</span>'}</td><td><div class="bar" style="width:${r.regs ? Math.max(3, r.pct / mx * 100) : 0}%"></div></td></tr>`).join('') + '</table>';
    $$('tr[data-i]', res).forEach(tr => tr.onclick = () => { st.l = st.r = +tr.dataset.i; setMode('diff'); });
  }

  function setMode(m) {
    st.mode = m;
    $$('#ovModes button').forEach(b => b.classList.toggle('on', b.dataset.mode === m));
    $('#ovOpacityRow').style.display = m === 'overlay' ? '' : 'none';
    $('#ovSwipeRow').style.display = m === 'swipe' ? '' : 'none';
    update();
  }
  function step(side, d) {
    const lsel = $('#ovLPage'), rsel = $('#ovRPage');
    const nl = lsel.options.length, nr = rsel.options.length;
    if ($('#ovLink').checked) { st.l = Math.max(0, Math.min(nl - 1, st.l + d)); st.r = Math.max(0, Math.min(nr - 1, st.r + d)); }
    else if (side === 0) st.l = Math.max(0, Math.min(nl - 1, st.l + d));
    else st.r = Math.max(0, Math.min(nr - 1, st.r + d));
    update();
  }

  $$('#ovModes button').forEach(b => b.onclick = () => setMode(b.dataset.mode));
  $('#ovLPrev').onclick = () => step(0, -1); $('#ovLNext').onclick = () => step(0, 1);
  $('#ovRPrev').onclick = () => step(1, -1); $('#ovRNext').onclick = () => step(1, 1);
  $('#ovLPage').onchange = e => { const v = +e.target.value, d = v - st.l; if ($('#ovLink').checked) st.r = Math.max(0, Math.min($('#ovRPage').options.length - 1, st.r + d)); st.l = v; update(); };
  $('#ovRPage').onchange = e => { st.r = +e.target.value; update(); };
  $('#ovOpacity').oninput = () => { if (st.mode === 'overlay') update(); };
  $('#ovSwipe').oninput = () => { if (st.mode === 'swipe' && st.drawSwipe) st.drawSwipe(); };
  let thrT = 0; $('#ovThr').oninput = () => { clearTimeout(thrT); thrT = setTimeout(() => { if (st.mode === 'diff') update(); }, 150); };
  $('#ovBoxes').onchange = drawBoxes;
  $('#ovFaint').onchange = () => update();
  let tolT = 0;
  $('#ovTolPx').oninput = () => { $('#ovTolVal').textContent = $('#ovTolPx').value; clearTimeout(tolT); tolT = setTimeout(update, 150); };
  const setOff = () => {
    st.dx = Math.round(+$('#ovDx').value || 0); st.dy = Math.round(+$('#ovDy').value || 0);
    st.ang = Math.max(-10, Math.min(10, Math.round((+$('#ovRot').value || 0) * 100) / 100));
    st.align.set(pairKey(), [st.dx, st.dy, st.ang]); update();
  };
  $('#ovDx').onchange = setOff; $('#ovDy').onchange = setOff; $('#ovRot').onchange = setOff;
  $('#ovReset').onclick = () => { $('#ovDx').value = 0; $('#ovDy').value = 0; $('#ovRot').value = 0; setOff(); };
  $('#ovAuto').onclick = async () => {
    if (!st.cl || !st.cr) return toast('左右に文書を読み込んでください');
    const [dx, dy, ang] = await withBusy('位置を合わせています…', async () => autoAlign(st.cl, st.cr));
    $('#ovDx').value = dx; $('#ovDy').value = dy; $('#ovRot').value = ang; setOff();
    toast(`右を X ${dx}px / Y ${dy}px${ang ? ` / 回転 ${ang}°` : ''} 補正しました`);
  };
  $('#ovRegPrev').onclick = () => gotoRegion(-1); $('#ovRegNext').onclick = () => gotoRegion(1);
  $('#ovScan').onclick = scan;
  const zs = $('#ovZoom');
  zs.onchange = () => { st.zoom = zs.value; update(); };
  const ZS = ['0.5', '0.75', '1', '1.5', '2'];
  $('#ovZIn').onclick = () => { const i = ZS.indexOf(st.zoom); st.zoom = i < 0 ? '1' : ZS[Math.min(ZS.length - 1, i + 1)]; zs.value = st.zoom; update(); };
  $('#ovZOut').onclick = () => { const i = ZS.indexOf(st.zoom); st.zoom = i < 0 ? '0.75' : ZS[Math.max(0, i - 1)]; zs.value = st.zoom; update(); };
  let rt = 0; window.addEventListener('resize', () => { if (App.tab === 'overlay' && st.zoom === 'fit') { clearTimeout(rt); rt = setTimeout(() => { $$('canvas', view).forEach(c => placeCanvas(c, st.mode === 'side')); }, 100); } });

  function activate() { if (st.dirty) update(); }
  function deactivate() { stopBlink(); }
  function invalidate() {
    st.l = 0; st.r = 0; st.cache.clear(); st.dirty = true; $('#ovScanRes').innerHTML = '';
    // ファイルが変わったら位置合わせ量を必ず0に戻す
    st.align.clear(); st.dx = 0; st.dy = 0; st.ang = 0; showOffset();
    // 「1px程度のずれを無視」はスキャン画像のときだけ既定でON（CADやWordから作ったPDFでは小さな変更を見落とさないようOFF）
    $('#ovTolPx').value = scanMode() ? 2 : 0; $('#ovTolVal').textContent = $('#ovTolPx').value;
    if (App.tab === 'overlay') update();
  }
  function onKey(e) {
    if (e.target.matches('input,select,textarea')) return false;
    if (e.key === 'ArrowRight' || e.key === 'PageDown') { step(0, 1); return true; }
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') { step(0, -1); return true; }
    if (e.key === 'n') { gotoRegion(1); return true; }
    return false;
  }
  return { activate, deactivate, invalidate, onKey, setPages: (l, r) => { st.l = l; st.r = r; } };
})();
