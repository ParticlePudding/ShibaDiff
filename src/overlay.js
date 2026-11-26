/* 重ね合わせ比較（画像差分） */
const OV = (() => {
  const view = $('#ovView');
  const st = {
    mode: 'diff', l: 0, r: 0, dx: 0, dy: 0, ang: 0, resF: 1, zoom: 'fit', regions: [], regIdx: -1, cache: new Map(),
    blink: 0, blinkOn: false, hand: false, dirty: true, out: null, base: null, cl: null, cr: null, scanning: false, gen: 0,
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
    // 描画結果は10件まで、かつ合計 6000万画素（約240MB）までに抑える（大きな図面でメモリを使いすぎないように）
    const px = () => { let n = 0; for (const c of st.cache.values()) n += c.width * c.height; return n; };
    while (st.cache.size > 10 || (st.cache.size > 2 && px() > 60e6)) {
      const k = st.cache.keys().next().value, c = st.cache.get(k); st.cache.delete(k); c.width = c.height = 0;
    }
    return cv;
  }
  // 描画の幅の上限（解像度の設定）。A0 などの大きな図面は上限で頭打ちになるので、軽量にすると速く、精細にすると細い線まで拾える
  const RES = { low: 1600, std: 2400, high: 4000 };
  function widthFor(pl, pr, max) {
    const w = Math.max(pl ? pl.w : 0, pr ? pr.w : 0);
    return Math.round(Math.max(Math.min(900, max), Math.min(max, w * 2)));
  }
  const renderWidth = (pl, pr) => widthFor(pl, pr, RES[Settings.get('ovRes')] || RES.std);
  // 「標準」で描いた場合に対する倍率。許容幅や変更箇所のます目をこの倍率で換算し、解像度を変えても同じ実寸で判定する
  // （A4 などの小さなページは解像度の上限に届かないので、どの設定でも 1）
  const resFactor = (pl, pr) => renderWidth(pl, pr) / widthFor(pl, pr, RES.std);

  function fillSelect(sel, n, v) {
    // 対応するページがない側（挿入・削除されたページ）は「—」にする
    sel.innerHTML = `<option value="-1" hidden>— / ${n}</option>` + Array.from({ length: n }, (_, i) => `<option value="${i}">${i + 1} / ${n}</option>`).join('');
    sel.value = String(v < 0 ? -1 : Math.min(v, Math.max(0, n - 1)));
  }
  /* ---- ページの対応（挿入・削除されたページ） ---- */
  // 対応付けを（まだなら）計算し、結果を表示する。連動中なら右のページを左に対応するページへ合わせる
  async function ensureMatch() {
    const info = $('#ovMatchInfo');
    if (!S[0] || !S[1] || !PageMatch.enabled()) { info.innerHTML = ''; return null; }
    if (PageMatch.ready()) { info.innerHTML = PageMatch.describe(PageMatch.ready()); return PageMatch.ready(); }
    info.textContent = 'ページの対応を調べています…';
    const pairs = await PageMatch.compute((k, n) => { info.textContent = `ページの対応を調べています… ${k} / ${n}`; });
    info.innerHTML = PageMatch.describe(PageMatch.ready());
    return pairs && PageMatch.ready();
  }
  // 今表示している組の位置（組の配列の何番目か）
  function pairIndex(pairs) {
    let k = pairs.findIndex(p => p.l === st.l && p.r === st.r);
    if (k < 0) k = pairs.findIndex(p => (st.l >= 0 && p.l === st.l) || (st.l < 0 && p.r === st.r));
    return Math.max(0, k);
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

  // 大きな図面でも画面が固まらないよう、段階ごと・一定の行ごとに画面へ制御を返す
  // o：位置合わせ量と解像度の倍率 {dx, dy, ang, resF}。途中で制御を返すので、共有の状態ではなく引数で受け取る
  async function diffImage(cl, cr, thr, faint, o) {
    const W = Math.max(cl.width, cr.width + Math.max(0, o.dx)), H = Math.max(cl.height, cr.height + Math.max(0, o.dy));
    const a = lumData(cl, W, H); await sleep(0);
    const b = lumData(cr, W, H, o.dx, o.dy, o.ang); await sleep(0);
    // ずれの許容（px）：スキャン画像は既定で2px、CADやWordから作ったPDFは0px（小さな変更を見落とさないため）
    // 許容幅は「標準（2400px）での px」として扱い、解像度に合わせて換算する（どの解像度でも同じ実寸の幅になるように）
    const tolSet = +$('#ovTolPx').value || 0, tol = tolSet > 0;
    const rad = tol ? Math.max(1, Math.round(tolSet * o.resF)) : 0;
    // スキャン画像は2段階のしきい値で比べる：片側に「はっきり濃い」画素（STRONG 未満）があり、
    // 反対側の近く（許容幅の中）に「薄くても」インク（WEAK 未満）が1つもないときだけ差分にする。
    // 縮小や回転で細い線が薄くなっても、消えたとは判定しない（大きな図面のスキャンで誤検出が多発するのを防ぐ）
    const scan = scanMode() && tol, STRONG = 170, WEAK = Math.min(250, STRONG + thr);
    const mf = async g => { let o = g; for (let k = 0; k < rad; k++) { o = minFilter(o, W, H); await sleep(0); } return o; };
    const aMin = tol ? await mf(a) : a, bMin = tol ? await mf(b) : b;
    const img = new ImageData(W, H), d = img.data, mask = new Uint8Array(W * H); // mask: 1=左だけ 2=右だけ
    // 変更箇所をまとめるます目も、標準での 16px を解像度に合わせて換算する（解像度で箇所の数が変わらないように）
    const CELL = Math.max(8, Math.round(16 * o.resF)), gw = Math.ceil(W / CELL), gh = Math.ceil(H / CELL), grid = new Uint16Array(gw * gh);
    let changed = 0, ink = 0;
    for (let y = 0, j = 0; y < H; y++) {
      if (y && !(y % 400)) await sleep(0);
      const gy = (y / CELL | 0) * gw;
      for (let x = 0; x < W; x++, j++) {
        const ga = a[j], gb = b[j], k = j * 4;
        if (ga < 200 || gb < 200) ink++;
        if (scan ? (ga < STRONG && bMin[j] >= WEAK) : (ga + thr < bMin[j])) { d[k] = 229; d[k + 1] = 50; d[k + 2] = 45; mask[j] = 1; changed++; grid[gy + (x / CELL | 0)]++; }
        else if (scan ? (gb < STRONG && aMin[j] >= WEAK) : (gb + thr < aMin[j])) { d[k] = 26; d[k + 1] = 115; d[k + 2] = 232; mask[j] = 2; changed++; grid[gy + (x / CELL | 0)]++; }
        else { const m = Math.min(ga, gb), v = faint ? 255 - ((255 - m) * 0.32 | 0) : m; d[k] = d[k + 1] = d[k + 2] = v; }
        d[k + 3] = 255;
      }
    }
    // regions: connected components of changed cells (with 1-cell dilation)
    const mark = new Uint8Array(gw * gh);
    // ます目の画素数の下限も解像度に合わせて換算する（軽量で小さな文字の変更を落とさないように）
    const cellMin = Math.max(2, Math.round(3 * o.resF)), regMin = Math.max(4, Math.round(8 * o.resF));
    for (let i = 0; i < grid.length; i++) if (grid[i] >= cellMin) mark[i] = 1;
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
      if (cnt < regMin) continue;
      regions.push({ x: x0 * CELL - 6, y: y0 * CELL - 6, w: (x1 - x0 + 1) * CELL + 12, h: (y1 - y0 + 1) * CELL + 12 });
    }
    regions.sort((p, q) => (Math.abs(p.y - q.y) < 30 ? p.x - q.x : p.y - q.y));
    return { img, mask, W, H, changed, ink, regions };
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
  async function autoAlign(cl, cr) {
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
    // 角度ごとに処理を区切って画面に制御を返す（大きな図面で画面が固まらないように）
    const search = async (f, angs, cx, cy, R, step) => {
      const A = ink(cl, f, 0); let best = { s: 1e18 };
      for (const ang of angs) {
        await sleep(0);
        const B = ink(cr, f, ang);
        for (let dy = cy - R; dy <= cy + R; dy++) {
          await sleep(0); // 1行ごとに区切る
          for (let dx = cx - R; dx <= cx + R; dx++) {
            const sc = score(A.g, B.g, A.w, A.h, dx, dy, step);
            if (sc < best.s) best = { s: sc, dx, dy, ang };
          }
        }
      }
      return best;
    };
    const range = (c, r, st) => { const o = []; for (let v = c - r; v <= c + r + 1e-9; v += st) o.push(Math.round(v * 100) / 100); return o; };
    // 粗い段階は、描画の幅によらず同じくらいの大きさ（幅 600〜800px）に縮小して探す。
    // 探す範囲は「標準（2400px）で ±56px」に相当する実寸にそろえる（精細で遅くならないように）
    const big = Math.max(1, W2 / 2400), f1 = Math.max(4, Math.round(W2 / 600)), f2 = Math.max(3, Math.round(W2 / 800));
    const R1 = Math.ceil(56 * big / f1);
    // 1) 縮小して平行移動だけを探す
    let b = await search(f1, [0], 0, 0, R1, 1);
    // 2) 回転 -1.2～1.2°（0.1°刻み）と平行移動 ±3 を探す
    b = await search(f2, range(0, 1.2, 0.1), Math.round(b.dx * f1 / f2), Math.round(b.dy * f1 / f2), 3, 2);
    // 3) 回転を 0.02° 刻みで詰める
    b = await search(f2, range(b.ang, 0.06, 0.02), b.dx, b.dy, 1, 2);
    // 4) 原寸で平行移動 ±3
    b = await search(1, [b.ang], b.dx * f2, b.dy * f2, 3, 3);
    return [b.dx, b.dy, Math.abs(b.ang) < 0.01 ? 0 : b.ang];
  }

  /* ---- drawing ---- */
  function stopBlink() { clearInterval(st.blink); st.blink = 0; }
  function startBlink() {
    stopBlink();
    if (st.mode === 'blink' && st.blinkFrame && !$('#ovBlinkManual').checked) st.blink = setInterval(st.blinkFrame, +$('#ovBlinkMs').value);
  }
  /* ---- 表示の大きさ：幅に合わせる（fit）／縦に合わせる（fith）／倍率 ---- */
  function cssWidth(cv, half) {
    const vw = view.clientWidth - 30, vh = view.clientHeight - 30;
    if (st.zoom === 'fit') return half ? Math.max(150, (view.clientWidth - 50) / 2) : Math.max(200, vw);
    if (st.zoom === 'fith') return Math.max(100, vh) * cv.width / cv.height;
    return cv.width * (+st.zoom) * (96 / 72) / (st.scale || 2);
  }
  function placeCanvas(cv, half = false) {
    cv.dataset.half = half ? '1' : '';
    const w = cssWidth(cv, half);
    cv.style.width = w + 'px'; cv.style.height = (cv.height / cv.width * w) + 'px';
  }
  // 今の表示倍率（幅・縦に合わせているときも数値にする）
  function effZoom() {
    const cv = $('canvas', view); if (!cv || !cv.width) return 1;
    return cv.getBoundingClientRect().width / (cv.width * (96 / 72) / (st.scale || 2));
  }
  function syncZoomSel() {
    const zs = $('#ovZoom'), custom = $('option[value=custom]', zs);
    if ([...zs.options].some(o => o.value === st.zoom && o.value !== 'custom')) { zs.value = st.zoom; custom.hidden = true; }
    else { custom.hidden = false; custom.textContent = Math.round(+st.zoom * 100) + '%'; zs.value = 'custom'; }
  }
  // 描き直さずに大きさだけ変える。ax, ay（表示領域の中の位置）を中心に拡大・縮小する
  function rezoom(z, ax, ay) {
    const cvs = $$('canvas', view);
    st.zoom = z; syncZoomSel();
    if (!cvs.length) return;
    if (ax == null) { ax = view.clientWidth / 2; ay = view.clientHeight / 2; }
    const before = cvs[0].getBoundingClientRect().width, px = view.scrollLeft + ax, py = view.scrollTop + ay;
    cvs.forEach(c => placeCanvas(c, c.dataset.half === '1'));
    const k = cvs[0].getBoundingClientRect().width / (before || 1);
    view.scrollLeft = px * k - ax; view.scrollTop = py * k - ay;
  }
  function zoomBy(f, ax, ay) {
    const z = Math.max(0.1, Math.min(8, effZoom() * f));
    rezoom(String(Math.round(z * 1000) / 1000), ax, ay);
  }
  function drawBoxesOn(c, regions, sel = st.regIdx) {
    regions.forEach((r, i) => {
      c.lineWidth = i === sel ? 6 : 3; c.strokeStyle = i === sel ? '#ff6d00' : 'rgba(255,152,0,.9)';
      c.strokeRect(r.x, r.y, r.w, r.h);
      c.fillStyle = i === sel ? '#ff6d00' : 'rgba(255,152,0,.95)'; c.font = 'bold 20px sans-serif';
      const label = String(i + 1), tw = c.measureText(label).width + 10;
      c.fillRect(r.x, r.y - 24, tw, 24); c.fillStyle = '#fff'; c.fillText(label, r.x + 5, r.y - 5);
    });
  }
  function drawBoxes() {
    if (st.mode === 'side') return drawSide();
    if (!st.out || st.mode !== 'diff') return;
    const c = st.out.getContext('2d');
    c.putImageData(st.base.img, 0, 0);
    if ($('#ovBoxes').checked) drawBoxesOn(c, st.regions);
  }
  // 色付け：濃い部分（線・文字）を指定の色にした画像（白はそのまま）
  const tintCache = new WeakMap();
  function tinted(cv, color) {
    let m = tintCache.get(cv); if (!m) tintCache.set(cv, m = new Map());
    if (m.has(color)) return m.get(color);
    if (m.size >= 2) m.clear();
    const t = document.createElement('canvas'); t.width = cv.width; t.height = cv.height;
    const c = t.getContext('2d'); c.drawImage(cv, 0, 0); c.globalCompositeOperation = 'lighten'; c.fillStyle = color; c.fillRect(0, 0, t.width, t.height);
    m.set(color, t); return t;
  }
  // 並べて表示：左はそのまま、右は位置合わせした状態で並べ、変更箇所に色と枠を付ける
  function drawSide() {
    const sd = st.side; if (!sd) return;
    const hl = $('#ovSideHl').checked && sd.res, boxes = $('#ovBoxes').checked && sd.res;
    sd.canvases.forEach((cv, k) => {
      const c = cv.getContext('2d');
      c.fillStyle = '#fff'; c.fillRect(0, 0, cv.width, cv.height);
      if (k === 0) c.drawImage(st.cl, 0, 0); else drawR(c, st.cr, st.dx, st.dy, st.ang);
      if (hl) {
        const im = c.getImageData(0, 0, cv.width, cv.height), d = im.data, m = sd.res.mask, want = k + 1;
        const col = k ? [26, 115, 232] : [229, 50, 45];
        for (let j = 0; j < m.length; j++) if (m[j] === want) { const q = j * 4; d[q] = col[0]; d[q + 1] = col[1]; d[q + 2] = col[2]; }
        c.putImageData(im, 0, 0);
      }
      if (boxes) drawBoxesOn(c, st.regions);
    });
  }
  function resultHtml(res, autoMsg) {
    const pct = res.ink ? res.changed / res.ink * 100 : 0;
    return (res.regions.length
      ? `<b style="color:#b42318">${res.regions.length} 箇所</b>の変更を検出<br><span class="muted">変化量: ${pct.toFixed(2)}%（文字・図の部分に対する割合）</span>`
      : (res.changed ? `<b>目立った変更はありません</b><br><span class="muted">わずかな差 ${pct.toFixed(3)}%（位置ずれや描画の違い）</span>` : '<b style="color:#21752f">✓ 差異は見つかりませんでした</b>')) + autoMsg;
  }

  async function update() {
    st.dirty = false; stopBlink();
    const gen = ++st.gen;
    const pl = await pages(0).catch(() => null), pr = await pages(1).catch(() => null);
    if (gen !== st.gen) return;
    fillSelect($('#ovLPage'), pl ? pl.length : 0, st.l); fillSelect($('#ovRPage'), pr ? pr.length : 0, st.r);
    if (!pl && !pr) { view.innerHTML = '<div class="pv-empty" style="color:#f2f4f6">左右にPDFまたは画像を読み込むと、ページを重ねて変更箇所を検出します<br><span style="font-size:12.5px">スキャン画像（PNG/JPEG）同士や、PDFとスキャン画像の比較にも使えます</span></div>'; $('#ovStats').textContent = '—'; return; }
    const pgL = pl && st.l >= 0 ? pl[st.l] : null, pgR = pr && st.r >= 0 ? pr[st.r] : null;
    const W = renderWidth(pgL, pgR); st.scale = W / Math.max(pgL ? pgL.w : 0, pgR ? pgR.w : 0); st.resF = resFactor(pgL, pgR);
    let cl, cr;
    try {
      [cl, cr] = await Promise.all([pgL ? renderAt(0, st.l, W) : null, pgR ? renderAt(1, st.r, W) : null]);
    } catch (e) { view.innerHTML = `<div class="pv-empty">描画に失敗しました: ${esc(e.message || '')}</div>`; return; }
    if (gen !== st.gen) return;
    st.cl = cl; st.cr = cr;
    // 位置合わせ：手動・自動で決めた量をページの組ごとに覚える。スキャンは初回に自動で合わせる
    let autoMsg = '';
    if (st.align.has(pairKey())) [st.dx, st.dy, st.ang] = st.align.get(pairKey());
    else if (cl && cr && scanMode()) {
      $('#ovStats').innerHTML = '<span class="muted">位置を合わせています…</span>';
      const off = await withBusy('スキャン画像の位置を合わせています…', () => autoAlign(cl, cr));
      if (gen !== st.gen) return;
      [st.dx, st.dy, st.ang] = off; st.align.set(pairKey(), [st.dx, st.dy, st.ang]); autoMsg = `<br><span class="muted">スキャン画像のため自動で位置合わせしました（X ${st.dx} / Y ${st.dy}px${st.ang ? ` / 回転 ${st.ang}°` : ''}）</span>`; }
    else { st.dx = 0; st.dy = 0; st.ang = 0; }
    showOffset();
    if (gen !== st.gen) return;
    // 差分画像は表示を消す前に計算する（計算中も前の結果を見られるように）
    let res = null;
    if (cl && cr && (st.mode === 'diff' || (st.mode === 'side' && ($('#ovSideHl').checked || $('#ovBoxes').checked)))) {
      res = await diffImage(cl, cr, +$('#ovThr').value, $('#ovFaint').checked, { dx: st.dx, dy: st.dy, ang: st.ang, resF: st.resF });
      if (gen !== st.gen) return;
    }
    view.innerHTML = ''; st.side = null;
    if (!cl || !cr) {
      const pair = document.createElement('div'); pair.className = 'pair';
      for (const c of [cl, cr]) if (c) { const d = document.createElement('canvas'); d.width = c.width; d.height = c.height; d.getContext('2d').drawImage(c, 0, 0); placeCanvas(d, false); pair.appendChild(d); }
      view.appendChild(pair);
      $('#ovStats').innerHTML = (pl && pr) ? (cl ? '<b>左だけにあるページです</b><br><span class="muted">右では削除されています</span>' : '<b>右だけにあるページです</b><br><span class="muted">右で追加されたページです</span>') : '片側のみ読み込まれています';
      return;
    }
    if (st.mode === 'side') {
      const W2 = Math.max(cl.width, cr.width + Math.max(0, st.dx)), H2 = Math.max(cl.height, cr.height + Math.max(0, st.dy));
      const pair = document.createElement('div'); pair.className = 'pair';
      const canvases = [0, 1].map(() => { const d = document.createElement('canvas'); d.width = W2; d.height = H2; placeCanvas(d, true); pair.appendChild(d); return d; });
      st.side = { canvases, res }; st.regions = res ? res.regions : []; st.regIdx = -1; st.out = canvases[0];
      drawSide();
      view.appendChild(pair);
      $('#ovStats').innerHTML = res ? resultHtml(res, autoMsg) : '並べて表示中';
      return;
    }
    const out = document.createElement('canvas');
    const W2 = Math.max(cl.width, cr.width + Math.max(0, st.dx)), H2 = Math.max(cl.height, cr.height + Math.max(0, st.dy));
    out.width = W2; out.height = H2;
    const c = out.getContext('2d');
    st.out = out;
    const tint = $('#ovTint').checked, colL = $('#ovColL').value, colR = $('#ovColR').value;
    if (st.mode === 'diff') {
      st.base = res; st.regions = res.regions; st.regIdx = -1;
      drawBoxes();
      $('#ovStats').innerHTML = resultHtml(res, autoMsg);
    } else if (st.mode === 'overlay') {
      // 色付け：左右の線をそれぞれの色にして乗算で重ねる（重なった線は濃く、片側だけの線はその色で見える）
      c.fillStyle = '#fff'; c.fillRect(0, 0, W2, H2); c.drawImage(tint ? tinted(cl, colL) : cl, 0, 0);
      c.globalAlpha = +$('#ovOpacity').value / 100; if (tint) c.globalCompositeOperation = 'multiply';
      drawR(c, tint ? tinted(cr, colR) : cr, st.dx, st.dy, st.ang);
      c.globalAlpha = 1; c.globalCompositeOperation = 'source-over';
      $('#ovStats').innerHTML = '左の上に右を半透明で重ねています' + (tint ? '<br><span class="muted">色：左＝左の色、右＝右の色、重なった線は濃く表示</span>' : '');
    } else if (st.mode === 'swipe') {
      const L = tint ? tinted(cl, colL) : cl, R = tint ? tinted(cr, colR) : cr;
      const drawSwipe = () => {
        const x = Math.round(W2 * +$('#ovSwipe').value / 100);
        c.fillStyle = '#fff'; c.fillRect(0, 0, W2, H2); c.drawImage(L, 0, 0);
        c.save(); c.beginPath(); c.rect(x, 0, W2 - x, H2); c.clip(); c.fillStyle = '#fff'; c.fillRect(x, 0, W2 - x, H2); drawR(c, R, st.dx, st.dy, st.ang); c.restore();
        c.fillStyle = '#1f6feb'; c.fillRect(x - 2, 0, 4, H2);
        c.font = 'bold 22px sans-serif'; c.fillStyle = 'rgba(192,80,77,.9)'; c.fillText('◀ 左', Math.max(8, x - 80), 30); c.fillStyle = 'rgba(58,143,74,.9)'; c.fillText('右 ▶', Math.min(W2 - 70, x + 12), 30);
      };
      drawSwipe(); st.drawSwipe = drawSwipe;
      const move = e => { const r = out.getBoundingClientRect(); $('#ovSwipe').value = Math.max(0, Math.min(100, (e.clientX - r.left) / r.width * 100)); drawSwipe(); };
      out.addEventListener('pointerdown', e => { if (st.hand || e.button !== 0) return; out.setPointerCapture(e.pointerId); move(e); });
      out.addEventListener('pointermove', e => { if (!st.hand && (e.buttons & 1)) move(e); });
      out.classList.add('swipe');
      $('#ovStats').innerHTML = '画像上をドラッグして境界を動かせます';
    } else if (st.mode === 'blink') {
      st.blinkFrame = () => {
        st.blinkOn = !st.blinkOn;
        c.fillStyle = '#fff'; c.fillRect(0, 0, W2, H2);
        if (st.blinkOn) drawR(c, cr, st.dx, st.dy, st.ang); else c.drawImage(cl, 0, 0);
        c.font = 'bold 26px sans-serif'; c.fillStyle = st.blinkOn ? 'rgba(58,143,74,.95)' : 'rgba(192,80,77,.95)';
        c.fillText(st.blinkOn ? '右' : '左', 14, 34);
      };
      st.blinkOn = true; st.blinkFrame(); startBlink();
      out.addEventListener('click', () => { if (!st.hand) st.blinkFrame(); });
      $('#ovStats').innerHTML = $('#ovBlinkManual').checked ? '画像をクリック（または Space）で左右を切り替えます' : '左右を交互に表示しています（変わった部分がちらつきます）。画像のクリックでも切り替えられます';
    }
    placeCanvas(out);
    view.appendChild(out);
  }

  /* ---- 手のひらツール・ホイール ---- */
  function setHand(on) {
    st.hand = on; view.classList.toggle('hand', on);
    $('#ovHand').classList.toggle('on', on); $('#ovHand').setAttribute('aria-pressed', on);
  }
  $('#ovHand').onclick = () => setHand(!st.hand);
  // 通常：ホイール＝縦スクロール、Shift＋ホイール＝横スクロール（ブラウザの標準）、Ctrl＋ホイール＝拡大・縮小
  // 手のひらツール：ホイール＝拡大・縮小。表示領域の上では、ブラウザの Ctrl＋ホイール（ページの拡大）より優先する
  view.addEventListener('wheel', e => {
    if (!e.ctrlKey && !e.metaKey && !st.hand) return;
    e.preventDefault();
    const r = view.getBoundingClientRect();
    zoomBy(Math.exp(-Math.max(-300, Math.min(300, e.deltaY)) * 0.0015), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  // ドラッグで表示位置を動かす（手のひらツール、または中ボタン）
  let pan = null;
  view.addEventListener('pointerdown', e => {
    if (!((st.hand && e.button === 0) || e.button === 1)) return;
    e.preventDefault(); view.setPointerCapture(e.pointerId);
    pan = { x: e.clientX, y: e.clientY, sl: view.scrollLeft, st: view.scrollTop, moved: false }; view.classList.add('panning');
  });
  view.addEventListener('pointermove', e => {
    if (!pan) return;
    if (Math.abs(e.clientX - pan.x) + Math.abs(e.clientY - pan.y) > 3) pan.moved = true;
    view.scrollLeft = pan.sl - (e.clientX - pan.x); view.scrollTop = pan.st - (e.clientY - pan.y);
  });
  const endPan = () => { pan = null; view.classList.remove('panning'); };
  view.addEventListener('pointerup', endPan); view.addEventListener('pointercancel', endPan);

  function gotoRegion(d) {
    if ((st.mode !== 'diff' && st.mode !== 'side') || !st.regions.length) return toast('変更箇所はありません');
    st.regIdx = (st.regIdx + d + st.regions.length) % st.regions.length;
    drawBoxes();
    const r = st.regions[st.regIdx], k = st.out.clientWidth / st.out.width;
    view.scrollTo({ top: st.out.offsetTop + r.y * k - view.clientHeight / 3, left: st.out.offsetLeft + r.x * k - view.clientWidth / 3, behavior: 'smooth' });
  }

  // 比べるページの組（対応付けが有効ならその結果、なければ同じページ番号どうし）
  async function pagePairs(pl, pr) {
    const pairs = PageMatch.enabled() ? await ensureMatch() : null;
    if (pairs) return pairs;
    return Array.from({ length: Math.max(pl.length, pr.length) }, (_, i) => ({ l: i < pl.length ? i : -1, r: i < pr.length ? i : -1 }));
  }
  // 1組を、1ページずつ表示したときと同じ解像度・位置合わせで調べる（件数をそろえるため）
  async function analyzePair(pl, pr, p, stop) {
    if (p.l < 0 || p.r < 0) return { ...p, kind: p.l < 0 ? 'add' : 'del', regs: 0, pct: 0 };
    const W = renderWidth(pl[p.l], pr[p.r]);
    const a = await renderAt(0, p.l, W), b = await renderAt(1, p.r, W);
    const key = `${p.l}:${p.r}`;
    let off = st.align.get(key);
    if (!off) { off = scanMode() ? await autoAlign(a, b) : [0, 0, 0]; if (stop()) return null; if (scanMode()) st.align.set(key, off); }
    const res = await diffImage(a, b, +$('#ovThr').value, $('#ovFaint').checked, { dx: off[0], dy: off[1], ang: off[2], resF: resFactor(pl[p.l], pr[p.r]) });
    return { ...p, kind: 'pair', regs: res.regions.length, pct: res.ink ? res.changed / res.ink * 100 : 0, res, off };
  }
  async function scan() {
    if (st.scanning) { st.scanning = false; return; }
    const pl = await pages(0).catch(() => null), pr = await pages(1).catch(() => null);
    if (!pl || !pr) return toast('左右に文書を読み込んでください');
    const res = $('#ovScanRes'), btn = $('#ovScan');
    st.scanning = true; btn.textContent = '中止'; res.innerHTML = '';
    const pairs = await pagePairs(pl, pr), rows = [];
    for (let k = 0; k < pairs.length && st.scanning; k++) {
      res.innerHTML = `<span class="muted">調べています… ${k + 1} / ${pairs.length}</span>`;
      const r = await analyzePair(pl, pr, pairs[k], () => !st.scanning);
      if (!r || !st.scanning) break;
      delete r.res; rows.push(r);
      await sleep(0);
    }
    const stopped = !st.scanning; st.scanning = false; btn.textContent = '全ページの差分を調べる';
    const mx = Math.max(1, ...rows.map(r => r.pct));
    const changedPages = rows.filter(r => r.regs > 0).length, adds = rows.filter(r => r.kind === 'add').length, dels = rows.filter(r => r.kind === 'del').length;
    const pg = v => v < 0 ? '<span class="muted">—</span>' : v + 1;
    res.innerHTML = `<div style="margin-bottom:4px">${stopped ? '（途中で中止）' : ''}変更ありのページ: <b>${changedPages}</b> / ${rows.filter(r => r.kind === 'pair').length}` +
      (adds ? `<br><span style="color:#1a5fb4">追加されたページ: <b>${adds}</b></span>` : '') + (dels ? `<br><span style="color:#b42318">削除されたページ: <b>${dels}</b></span>` : '') +
      (pl.length !== pr.length && !PageMatch.ready() ? `<br><span style="color:#b42318">ページ数が違います（左 ${pl.length} / 右 ${pr.length}）</span>` : '') + '</div>' +
      `<table class="scan-table"><tr><th>左</th><th>右</th><th>箇所</th><th style="width:45%">変化量</th></tr>` +
      rows.map((r, k) => `<tr data-k="${k}"><td>${pg(r.l)}</td><td>${pg(r.r)}</td><td>${r.kind === 'add' ? '<b style="color:#1a5fb4">追加</b>' : r.kind === 'del' ? '<b style="color:#b42318">削除</b>' : r.regs ? `<b style="color:#b42318">${r.regs}</b>` : '<span class="muted">0</span>'}</td><td>${r.kind === 'pair' ? `<div class="bar" style="width:${r.regs ? Math.max(3, r.pct / mx * 100) : 0}%"></div>` : ''}</td></tr>`).join('') + '</table>';
    $$('tr[data-k]', res).forEach(tr => tr.onclick = () => { const r = rows[+tr.dataset.k]; st.l = r.l; st.r = r.r; setMode('diff'); });
  }

  /* ---- レポート：全ページの差分画像（枠と番号付き）と変更箇所の一覧 ---- */
  async function exportReport() {
    const pl = await pages(0).catch(() => null), pr = await pages(1).catch(() => null);
    if (!pl || !pr) return toast('左右に文書を読み込んでください');
    const scope = await Report.ask('重ね合わせ比較のレポート', 'レポートに差分画像を載せるページを選んでください。<br><span class="muted">追加・削除されたページは、どちらを選んでも載せます。変更のないページは一覧にだけ載せます（「すべて」を選ぶと画像も載せます）。ページ数が多いと時間がかかります。</span>',
      [{ label: 'すべてのページ', value: 'all' }, { label: '変更のあるページだけ', value: 'changed', primary: true }]);
    if (!scope) return;
    let html;
    await withBusy('レポートを作成しています…', async () => {
      const pairs = await pagePairs(pl, pr), rows = [], secs = [];
      const pg = v => v < 0 ? '—' : v + 1;
      for (let k = 0; k < pairs.length; k++) {
        $('#busyMsg').textContent = `レポートを作成しています… ${k + 1} / ${pairs.length}`;
        const r = await analyzePair(pl, pr, pairs[k], () => false);
        rows.push(r);
        const title = `左 ${pg(r.l)} ページ ／ 右 ${pg(r.r)} ページ`;
        if (r.kind !== 'pair') {
          // 追加・削除されたページは、そのページだけを載せる
          const side = r.kind === 'add' ? 1 : 0, idx = side ? r.r : r.l, cv = await renderAt(side, idx, Math.min(1400, renderWidth(side ? null : pl[idx], side ? pr[idx] : null)));
          secs.push(`<h2 id="p${k}">${title}　<span class="tag ${r.kind}">${r.kind === 'add' ? '右で追加' : '左から削除'}</span></h2><figure><img src="${Report.jpeg(cv)}" alt=""><figcaption>${r.kind === 'add' ? '右だけにあるページ（追加されたページ）' : '左だけにあるページ（削除されたページ）'}</figcaption></figure>`);
        } else if (scope === 'all' || r.regs) {
          const res = r.res, cv = document.createElement('canvas'); cv.width = res.W; cv.height = res.H;
          const c = cv.getContext('2d'); c.putImageData(res.img, 0, 0); drawBoxesOn(c, res.regions, -1);
          const list = res.regions.map((g, i) => `<tr><td class="num">${i + 1}</td><td>横 ${Math.round(g.x / res.W * 100)}%・縦 ${Math.round(g.y / res.H * 100)}%</td><td>${Math.round(g.w / res.W * 100)}% × ${Math.round(g.h / res.H * 100)}%</td></tr>`).join('');
          secs.push(`<h2 id="p${k}">${title}　${r.regs ? `<span class="tag diff">${r.regs} 箇所</span>` : '<span class="tag same">変更なし</span>'}</h2>` +
            `<figure><img src="${Report.jpeg(cv)}" alt=""><figcaption>赤＝左にだけある（削除・変更前）、青＝右にだけある（追加・変更後）、橙の枠＝変更箇所。変化量 ${r.pct.toFixed(2)}%` +
            `${r.off && (r.off[0] || r.off[1] || r.off[2]) ? `。右の位置合わせ：X ${r.off[0]} / Y ${r.off[1]}px${r.off[2] ? ` / 回転 ${r.off[2]}°` : ''}` : ''}</figcaption></figure>` +
            (list ? `<table class="list"><thead><tr><th style="width:50px">番号</th><th>位置（ページの左上から）</th><th>大きさ（ページに対する割合）</th></tr></thead><tbody>${list}</tbody></table>` : ''));
          cv.width = cv.height = 0;
        }
        delete r.res;
        await sleep(0);
      }
      const nPair = rows.filter(r => r.kind === 'pair').length, nChg = rows.filter(r => r.regs).length;
      const nAdd = rows.filter(r => r.kind === 'add').length, nDel = rows.filter(r => r.kind === 'del').length;
      const summary = `<h2>ページの一覧</h2><table class="list"><thead><tr><th class="num">左</th><th class="num">右</th><th>結果</th><th class="num">変化量</th></tr></thead><tbody>` +
        rows.map((r, k) => `<tr><td class="num">${pg(r.l)}</td><td class="num">${pg(r.r)}</td><td>${r.kind === 'add' ? '<span class="tag add">右で追加</span>' : r.kind === 'del' ? '<span class="tag del">左から削除</span>' : r.regs ? `<span class="tag diff">${r.regs} 箇所</span>` : '<span class="tag same">変更なし</span>'}</td><td class="num">${r.kind === 'pair' ? r.pct.toFixed(2) + '%' : ''}</td></tr>`).join('') + '</tbody></table>';
      const cond = [`差分の感度 ${$('#ovThr').value}`, `ずれの許容 ${$('#ovTolPx').value}px`, `解像度 ${$('#ovRes').selectedOptions[0].textContent}`, PageMatch.enabled() ? 'ページの挿入・削除を自動で対応付け' : '同じページ番号どうしで比較'].join('、');
      html = Report.page({
        title: `重ね合わせレポート - ${S[0].name} / ${S[1].name}`, heading: '重ね合わせ比較レポート',
        meta: `<b>変更のあるページ ${nChg} / ${nPair}</b>${nAdd ? `　右で追加 ${nAdd} ページ` : ''}${nDel ? `　左から削除 ${nDel} ページ` : ''}<br>比較条件: ${esc(cond)}`,
        body: (await Report.bothInfo()) + summary + secs.join('')
      });
    });
    if (html) download(`重ね合わせレポート_${baseName(S[0].name)}.html`, html, 'text/html;charset=utf-8');
  }
  $('#ovReport').onclick = exportReport;

  // 右側のパネルには、そのモードで使う項目だけを出す
  function showPanelFor(m) { $$('.ov-side [data-modes]').forEach(el => { el.hidden = !el.dataset.modes.split(' ').includes(m); }); }
  function setMode(m) {
    st.mode = m;
    $$('#ovModes button').forEach(b => b.classList.toggle('on', b.dataset.mode === m));
    showPanelFor(m);
    update();
  }
  function step(side, d) {
    const lsel = $('#ovLPage'), rsel = $('#ovRPage');
    const nl = lsel.options.length - 1, nr = rsel.options.length - 1; // 先頭は「—」
    const pairs = $('#ovLink').checked && PageMatch.ready();
    if (pairs) {
      // 連動中で対応付けがあるときは、組の順にページを送る（挿入・削除されたページは片側だけを表示）
      const k = Math.max(0, Math.min(pairs.length - 1, pairIndex(pairs) + d));
      st.l = pairs[k].l; st.r = pairs[k].r;
    } else if ($('#ovLink').checked) { st.l = Math.max(0, Math.min(nl - 1, st.l + d)); st.r = Math.max(0, Math.min(nr - 1, st.r + d)); }
    else if (side === 0) st.l = Math.max(0, Math.min(nl - 1, st.l + d));
    else st.r = Math.max(0, Math.min(nr - 1, st.r + d));
    update();
  }

  $$('#ovModes button').forEach(b => b.onclick = () => setMode(b.dataset.mode));
  $('#ovLPrev').onclick = () => step(0, -1); $('#ovLNext').onclick = () => step(0, 1);
  $('#ovRPrev').onclick = () => step(1, -1); $('#ovRNext').onclick = () => step(1, 1);
  $('#ovLPage').onchange = e => {
    const v = +e.target.value, d = v - st.l, pairs = PageMatch.ready();
    if ($('#ovLink').checked) st.r = pairs ? pairs.find(p => p.l === v).r : Math.max(0, Math.min($('#ovRPage').options.length - 2, st.r + d));
    st.l = v; update();
  };
  $('#ovRPage').onchange = e => {
    const v = +e.target.value, pairs = PageMatch.ready();
    if ($('#ovLink').checked && pairs) st.l = pairs.find(p => p.r === v).l;
    st.r = v; update();
  };
  $('#ovMatch').checked = PageMatch.enabled();
  $('#ovMatch').onchange = async () => {
    Settings.set('pageMatch', $('#ovMatch').checked);
    $('#ovScanRes').innerHTML = '';
    if ($('#ovMatch').checked) await ensureMatch(); else { $('#ovMatchInfo').innerHTML = ''; if (st.l < 0 || st.r < 0) { st.l = Math.max(0, st.l); st.r = Math.max(0, st.r); } }
    update();
  };
  $('#ovOpacity').oninput = () => { if (st.mode === 'overlay') update(); };
  $('#ovSwipe').oninput = () => { if (st.mode === 'swipe' && st.drawSwipe) st.drawSwipe(); };
  let thrT = 0; $('#ovThr').oninput = () => { clearTimeout(thrT); thrT = setTimeout(() => { if (st.mode === 'diff') update(); }, 150); };
  $('#ovBoxes').onchange = () => { if (st.mode === 'side' && !st.side?.res) update(); else drawBoxes(); };
  $('#ovSideHl').onchange = () => { if (st.side && !st.side.res) update(); else drawSide(); };
  for (const id of ['#ovTint', '#ovColL', '#ovColR']) $(id).addEventListener('change', () => { if (st.mode === 'overlay' || st.mode === 'swipe') update(); });
  $('#ovBlinkMs').oninput = () => { $('#ovBlinkVal').textContent = (+$('#ovBlinkMs').value / 1000).toFixed(2); startBlink(); };
  $('#ovBlinkManual').onchange = () => { startBlink(); if (st.mode === 'blink') $('#ovStats').innerHTML = $('#ovBlinkManual').checked ? '画像をクリック（または Space）で左右を切り替えます' : '左右を交互に表示しています（変わった部分がちらつきます）。画像のクリックでも切り替えられます'; };
  $('#ovBlinkToggle').onclick = () => { if (st.blinkFrame) st.blinkFrame(); };
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
  const resSel = $('#ovRes'); resSel.value = Settings.get('ovRes');
  resSel.onchange = () => Settings.set('ovRes', resSel.value);
  Settings.on(k => {
    if (k !== 'ovRes') return;
    resSel.value = Settings.get('ovRes');
    // 解像度が変わると画素単位の位置合わせ量も変わるので、描画と位置合わせをやり直す。
    // 実行中の描画・位置合わせは世代番号を進めて捨てる（古い解像度の位置合わせ量を保存しないように）
    st.gen++; st.scanning = false;
    st.cache.clear(); st.align.clear(); $('#ovScanRes').innerHTML = ''; st.dirty = true;
    if (App.tab === 'overlay') update();
  });
  const zs = $('#ovZoom');
  zs.onchange = () => { if (zs.value !== 'custom') rezoom(zs.value); };
  // ＋／－は今の倍率から 1.25 倍ずつ（幅・縦に合わせているときも、その倍率から）
  $('#ovZIn').onclick = () => zoomBy(1.25);
  $('#ovZOut').onclick = () => zoomBy(1 / 1.25);
  let rt = 0; window.addEventListener('resize', () => { if (App.tab === 'overlay' && (st.zoom === 'fit' || st.zoom === 'fith')) { clearTimeout(rt); rt = setTimeout(() => { $$('canvas', view).forEach(c => placeCanvas(c, c.dataset.half === '1')); }, 100); } });

  showPanelFor(st.mode);
  // ページの対応付けを（必要なら裏で）調べ、終わったら、連動中なら右のページを左に対応するページへ合わせ直す
  async function refreshMatch() {
    const before = PageMatch.ready(), gen = st.gen;
    const pairs = await ensureMatch();
    if (pairs && !before && $('#ovLink').checked && App.tab === 'overlay' && gen === st.gen) {
      const p = pairs.find(q => q.l === st.l);
      if (p && p.r !== st.r) { st.r = p.r; update(); }
    }
  }
  async function activate() {
    if (st.dirty) update();
    refreshMatch();
  }
  function deactivate() { stopBlink(); }
  function invalidate() {
    st.gen++; st.scanning = false; // 実行中の描画・位置合わせ・一括チェックは捨てる（前のファイルの結果を残さないように）
    st.l = 0; st.r = 0; st.cache.clear(); st.dirty = true; $('#ovScanRes').innerHTML = '';
    // ファイルが変わったら位置合わせ量を必ず0に戻す
    st.align.clear(); st.dx = 0; st.dy = 0; st.ang = 0; showOffset();
    // 「1px程度のずれを無視」はスキャン画像のときだけ既定でON（CADやWordから作ったPDFでは小さな変更を見落とさないようOFF）
    $('#ovTolPx').value = scanMode() ? 2 : 0; $('#ovTolVal').textContent = $('#ovTolPx').value;
    $('#ovMatchInfo').innerHTML = ''; // 前のファイルの対応付けの結果を残さない
    if (App.tab === 'overlay') { update(); refreshMatch(); }
  }
  function onKey(e) {
    const typing = e.target.matches('textarea,input[type=text],input[type=number],input[type=search]');
    // PageUp／PageDown は、ページ番号の選択欄やスライダーにフォーカスがあってもページ送りにする
    if (!typing && e.key === 'PageDown') { step(0, 1); return true; }
    if (!typing && e.key === 'PageUp') { step(0, -1); return true; }
    if (e.target.matches('input,select,textarea') || e.ctrlKey || e.metaKey || e.altKey) return false;
    if (e.key === 'ArrowRight') { step(0, 1); return true; }
    if (e.key === 'ArrowLeft') { step(0, -1); return true; }
    if (e.key === 'n') { gotoRegion(1); return true; }
    if (e.key === 'h' || e.key === 'H') { setHand(!st.hand); return true; }
    if (e.key === ' ' && st.mode === 'blink' && st.blinkFrame) { st.blinkFrame(); return true; }
    return false;
  }
  return { activate, deactivate, invalidate, onKey, st, setPages: (l, r) => { st.l = l; st.r = r; } };
})();
