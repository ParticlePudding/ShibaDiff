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
    while (st.cache.size > 12 || (st.cache.size > 2 && px() > 60e6)) {
      const k = st.cache.keys().next().value, c = st.cache.get(k); st.cache.delete(k); // 表示中のページが使っていることがあるので、消さずに参照を外すだけにする
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
  // ずれの許容の倍率：解像度の倍率と、描画の細かさ（1pt あたり何画素か ÷ 2。A4 では 1）の小さい方。
  // A1 などの大きなページは標準でも 1pt が2画素未満になるので、許容（太らせる量）も細かくし、小さな数字の変更を見落とさないようにする
  const tolFactor = (pl, pr) => Math.min(resFactor(pl, pr), renderWidth(pl, pr) / Math.max(pl ? pl.w : 0, pr ? pr.w : 0) / 2);

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
  // 明るさの配列。rgb を渡すと、色の比較用に RGBA の画素もそこに入れる
  function lumData(cv, W, H, dx = 0, dy = 0, ang = 0, rgb = null) {
    const c = document.createElement('canvas'); c.width = W; c.height = H;
    const x = c.getContext('2d', { willReadFrequently: true });
    x.fillStyle = '#fff'; x.fillRect(0, 0, W, H); drawR(x, cv, dx, dy, ang);
    const d = x.getImageData(0, 0, W, H).data, g = new Uint8Array(W * H);
    for (let i = 0, j = 0; j < g.length; i += 4, j++) g[j] = (d[i] * 77 + d[i + 1] * 150 + d[i + 2] * 29) >> 8;
    if (rgb) rgb.d = d;
    return g;
  }
  // 色の違いを調べるか（パネルのチェック）。既定は、紙のスキャン（文字のないPDF）だけオフ
  const colorCheck = () => $('#ovColor').checked;

  // 大きな図面でも画面が固まらないよう、段階ごと・一定の行ごとに画面へ制御を返す
  // o：位置合わせ量と解像度の倍率 {dx, dy, ang, resF}。途中で制御を返すので、共有の状態ではなく引数で受け取る
  async function diffImage(cl, cr, thr, faint, o) {
    const W = Math.max(cl.width, cr.width + Math.max(0, o.dx)), H = Math.max(cl.height, cr.height + Math.max(0, o.dy));
    const col = o.color !== undefined ? o.color : colorCheck(), ca = {}, cb = {};
    const a = lumData(cl, W, H, 0, 0, 0, col ? ca : null); await sleep(0);
    const b = lumData(cr, W, H, o.dx, o.dy, o.ang, col ? cb : null); await sleep(0);
    // ずれの許容（px）：スキャン画像は既定で2px、CADやWordから作ったPDFは0px（小さな変更を見落とさないため）
    // 許容幅は「標準（2400px）での px」として扱い、解像度に合わせて換算する（どの解像度でも同じ実寸の幅になるように）
    const tolSet = +$('#ovTolPx').value || 0, tol = tolSet > 0;
    const rad = tol ? Math.max(1, Math.round(tolSet * (o.tolF || o.resF))) : 0;
    // スキャン画像は2段階のしきい値で比べる：片側に「はっきり濃い」画素（STRONG 未満）があり、
    // 反対側の近く（許容幅の中）に「薄くても」インク（WEAK 未満）が1つもないときだけ差分にする。
    // 縮小や回転で細い線が薄くなっても、消えたとは判定しない（大きな図面のスキャンで誤検出が多発するのを防ぐ）
    const scan = scanMode() && tol, STRONG = 170, WEAK = Math.min(250, STRONG + thr);
    const mf = async g => { let o = g; for (let k = 0; k < rad; k++) { o = minFilter(o, W, H); await sleep(0); } return o; };
    const aMin = tol ? await mf(a) : a, bMin = tol ? await mf(b) : b;
    const img = new ImageData(W, H), d = img.data, mask = new Uint8Array(W * H); // mask: 1=左だけ 2=右だけ 3=色が変わった
    // 色の変化：どちらかが白でなく、どちらかに色が付いている画素で、色の差（人の目の感じ方に寄せた重み付きの距離）が大きいもの。
    // 明るさが同じくらいの別の色（水色→青、赤→緑）への変更は、明るさだけの比較では見つからないため
    let cm = null;
    if (col) {
      cm = new Uint8Array(W * H);
      const da = ca.d, db = cb.d, T = Math.max(40, thr), T2 = T * T * 9;
      const cdist = (p, i, q, k) => { const dr = p[i] - q[k], dg = p[i + 1] - q[k + 1], dbb = p[i + 2] - q[k + 2]; return dr * dr * 2 + dg * dg * 4 + dbb * dbb * 3; };
      const near = (p, i, q, x, y) => {
        for (let yy = Math.max(0, y - rad); yy <= Math.min(H - 1, y + rad); yy++) for (let xx = Math.max(0, x - rad); xx <= Math.min(W - 1, x + rad); xx++) if (cdist(p, i, q, (yy * W + xx) * 4) <= T2) return true;
        return false;
      };
      for (let j = 0, i = 0; j < cm.length; j++, i += 4) {
        if (a[j] > 235 && b[j] > 235) continue;
        // 灰色どうし（白黒の文書・スキャン）は調べない。濃さの違いは明るさの比較（とスキャンの2段階のしきい値）に任せる
        const sa = Math.max(da[i], da[i + 1], da[i + 2]) - Math.min(da[i], da[i + 1], da[i + 2]), sb = Math.max(db[i], db[i + 1], db[i + 2]) - Math.min(db[i], db[i + 1], db[i + 2]);
        if (sa < 40 && sb < 40) continue;
        if (cdist(da, i, db, i) <= T2) continue;
        // ずれの許容：相手の近く（許容の半径の中）に同じような色があれば、ずれとみなして色の変化にしない（両方向で確かめる）
        if (rad) { const x = j % W, y = (j / W) | 0; if (near(da, i, db, x, y) && near(db, i, da, x, y)) continue; }
        cm[j] = 1;
      }
      await sleep(0);
      // 線の縁（1〜2px）のにじみ・わずかなずれで出る色の差は捨てる：上下左右も色が変わっている画素だけを残す
      const er = new Uint8Array(W * H);
      for (let y = 1; y < H - 1; y++) for (let x = 1, j = y * W + 1; x < W - 1; x++, j++) if (cm[j] && cm[j - 1] && cm[j + 1] && cm[j - W] && cm[j + W]) er[j] = 1;
      cm = er; await sleep(0);
    }
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
        else if (cm && cm[j]) { d[k] = 156; d[k + 1] = 54; d[k + 2] = 181; mask[j] = 3; changed++; grid[gy + (x / CELL | 0)]++; }
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
  // 表示中のページ（1ページ表示なら今のページ、全ページ表示なら描画済みのページ）
  const liveViews = () => st.slots ? st.slots.filter(s => s.v).map(s => s.v) : (st.cur ? [st.cur] : []);
  st.blinkFrame = () => { st.blinkOn = !st.blinkOn; liveViews().forEach(v => v.frame && v.frame(st.blinkOn)); };
  function stopBlink() { clearInterval(st.blink); st.blink = 0; }
  function startBlink() {
    stopBlink();
    if (st.mode === 'blink' && !$('#ovBlinkManual').checked) st.blink = setInterval(st.blinkFrame, +$('#ovBlinkMs').value);
  }
  /* ---- 表示の大きさ：幅に合わせる（fit）／縦に合わせる（fith）／倍率 ---- */
  // 描画の画素数（全ページ表示のまだ描いていないページは、仮の枠に入れた大きさ）
  const dims = el => el.tagName === 'CANVAS' ? [el.width, el.height] : [+el.dataset.w, +el.dataset.h];
  const scaleOf = el => +el.dataset.scale || st.scale || 2;
  function cssWidth(el, half) {
    const [w, h] = dims(el);
    const vw = view.clientWidth - 30, vh = view.clientHeight - 30 - (st.slots ? 24 : 0);
    if (st.zoom === 'fit') return half ? Math.max(150, (view.clientWidth - 50) / 2) : Math.max(200, vw);
    if (st.zoom === 'fith') return Math.max(100, vh) * w / h;
    return w * (+st.zoom) * (96 / 72) / scaleOf(el);
  }
  function placeCanvas(el, half = false) {
    el.dataset.half = half ? '1' : '';
    const [w, h] = dims(el), cw = cssWidth(el, half);
    el.style.width = cw + 'px'; el.style.height = (h / w * cw) + 'px';
  }
  const sized = () => $$('canvas, .ov-ph', view);
  function mkCanvas(w, h, scale) { const d = document.createElement('canvas'); d.width = w; d.height = h; d.dataset.scale = scale; return d; }
  // 今の表示倍率（幅・縦に合わせているときも数値にする）
  function effZoom() {
    const cv = sized()[0]; if (!cv || !dims(cv)[0]) return 1;
    return cv.getBoundingClientRect().width / (dims(cv)[0] * (96 / 72) / scaleOf(cv));
  }
  function syncZoomSel() {
    const zs = $('#ovZoom'), custom = $('option[value=custom]', zs);
    if ([...zs.options].some(o => o.value === st.zoom && o.value !== 'custom')) { zs.value = st.zoom; custom.hidden = true; }
    else { custom.hidden = false; custom.textContent = Math.round(+st.zoom * 100) + '%'; zs.value = 'custom'; }
  }
  // 描き直さずに大きさだけ変える。ax, ay（表示領域の中の位置）を中心に拡大・縮小する
  function rezoom(z, ax, ay) {
    const cvs = sized();
    st.zoom = z; syncZoomSel();
    if (!cvs.length) return;
    if (ax == null) { ax = view.clientWidth / 2; ay = view.clientHeight / 2; }
    // 全ページ表示では、指した位置のページを基準にする（ページの間のすき間は拡大しないため）
    const anchor = st.slots ? (cvs.find(c => { const r = c.getBoundingClientRect(), v = view.getBoundingClientRect(); return r.bottom >= v.top + ay; }) || cvs[0]) : cvs[0];
    const vr = view.getBoundingClientRect(), r0 = anchor.getBoundingClientRect();
    const fx = (vr.left + ax - r0.left) / (r0.width || 1), fy = (vr.top + ay - r0.top) / (r0.height || 1);
    cvs.forEach(c => placeCanvas(c, c.dataset.half === '1'));
    const r1 = anchor.getBoundingClientRect();
    view.scrollLeft += r1.left + fx * r1.width - (vr.left + ax);
    view.scrollTop += r1.top + fy * r1.height - (vr.top + ay);
  }
  function zoomBy(f, ax, ay) {
    const z = Math.max(0.1, Math.min(8, effZoom() * f));
    rezoom(String(Math.round(z * 1000) / 1000), ax, ay);
  }
  // 枠の色：確認済＝緑、要確認＝赤橙、それ以外＝橙。コメントがあれば番号に ✎ を付ける
  const NOTE_COL = { ok: ['#2f9e44', 'rgba(47,158,68,.9)'], ask: ['#d9480f', 'rgba(232,89,12,.95)'], '': ['#ff6d00', 'rgba(255,152,0,.9)'] };
  function drawBoxesOn(c, regions, sel = -1, ids = null) {
    regions.forEach((r, i) => {
      const nv = ids && ids[i] ? Notes.get(ids[i]) : null, col = NOTE_COL[nv ? nv.st : ''];
      c.lineWidth = i === sel ? 6 : 3; c.strokeStyle = i === sel ? col[0] : col[1];
      c.strokeRect(r.x, r.y, r.w, r.h);
      c.fillStyle = i === sel ? col[0] : col[1]; c.font = 'bold 20px sans-serif';
      const label = String(i + 1) + (nv && nv.st === 'ok' ? ' ✓' : nv && nv.st === 'ask' ? ' !' : '') + (nv && nv.text ? ' ✎' : ''), tw = c.measureText(label).width + 10;
      c.fillRect(r.x, r.y - 24, tw, 24); c.fillStyle = '#fff'; c.fillText(label, r.x + 5, r.y - 5);
    });
  }
  function drawBoxes(v) {
    if (!v) return liveViews().forEach(drawBoxes);
    if (v.side) return drawSide(v);
    if (!v.out || !v.base || st.mode !== 'diff') return;
    const c = v.out.getContext('2d');
    c.putImageData(v.base.img, 0, 0);
    if ($('#ovBoxes').checked) drawBoxesOn(c, v.regions, v.regIdx, v.noteIds);
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
  function drawSide(v) {
    if (!v) return liveViews().forEach(drawSide);
    const sd = v.side; if (!sd) return;
    const hl = $('#ovSideHl').checked && sd.res, boxes = $('#ovBoxes').checked && sd.res;
    sd.canvases.forEach((cv, k) => {
      const c = cv.getContext('2d');
      c.fillStyle = '#fff'; c.fillRect(0, 0, cv.width, cv.height);
      if (k === 0) c.drawImage(v.cl, 0, 0); else drawR(c, v.cr, v.dx, v.dy, v.ang);
      if (hl) {
        const im = c.getImageData(0, 0, cv.width, cv.height), d = im.data, m = sd.res.mask, want = k + 1;
        const col = k ? [26, 115, 232] : [229, 50, 45];
        for (let j = 0; j < m.length; j++) if (m[j] === want) { const q = j * 4; d[q] = col[0]; d[q + 1] = col[1]; d[q + 2] = col[2]; }
        else if (m[j] === 3) { const q = j * 4; d[q] = (d[q] + 156) >> 1; d[q + 1] = (d[q + 1] + 54) >> 1; d[q + 2] = (d[q + 2] + 181) >> 1; } // 色の変化：その色を残して紫を混ぜる
        c.putImageData(im, 0, 0);
      }
      if (boxes) drawBoxesOn(c, v.regions, v.regIdx, v.noteIds);
    });
  }
  function resultHtml(res, autoMsg) {
    const pct = res.ink ? res.changed / res.ink * 100 : 0;
    return (res.regions.length
      ? `<b style="color:#b42318">${res.regions.length} 箇所</b>の変更を検出<br><span class="muted">変化量: ${pct.toFixed(2)}%（文字・図の部分に対する割合）</span>`
      : (res.changed ? `<b>目立った変更はありません</b><br><span class="muted">わずかな差 ${pct.toFixed(3)}%（位置ずれや描画の違い）</span>` : '<b style="color:#21752f">✓ 差異は見つかりませんでした</b>')) + autoMsg;
  }

  /* ---- 1組のページを描く（1ページ表示・全ページ表示で共通） ---- */
  // 描画・位置合わせ・差分の計算。途中で状態が変わったら（世代番号が進んだら）null を返す
  // 左右のファイルの組（読み込みの途中で片側だけ入れ替わったら、その途中の結果は使わない）
  const fileKeys = () => `${S[0] ? S[0].key : ''}||${S[1] ? S[1].key : ''}`;
  async function prepare(pl, pr, l, r, gen) {
    const fk = fileKeys(), stale = () => gen !== st.gen || fk !== fileKeys();
    const pgL = pl && l >= 0 ? pl[l] : null, pgR = pr && r >= 0 ? pr[r] : null;
    const W = renderWidth(pgL, pgR), scale = W / Math.max(pgL ? pgL.w : 0, pgR ? pgR.w : 0), resF = resFactor(pgL, pgR), tolF = tolFactor(pgL, pgR);
    const [cl, cr] = await Promise.all([pgL ? renderAt(0, l, W) : null, pgR ? renderAt(1, r, W) : null]);
    if (stale()) return null;
    // 位置合わせ：手動・自動で決めた量をページの組ごとに覚える。スキャンは初回に自動で合わせる
    const key = `${l}:${r}`;
    let off = [0, 0, 0], autoMsg = '';
    if (st.align.has(key)) off = st.align.get(key);
    else if (cl && cr && scanMode()) {
      off = st.slots ? await autoAlign(cl, cr) : await withBusy('スキャン画像の位置を合わせています…', () => autoAlign(cl, cr));
      if (stale()) return null;
      st.align.set(key, off);
      autoMsg = `<br><span class="muted">スキャン画像のため自動で位置合わせしました（X ${off[0]} / Y ${off[1]}px${off[2] ? ` / 回転 ${off[2]}°` : ''}）</span>`;
    }
    const [dx, dy, ang] = off;
    let res = null;
    if (cl && cr && (st.mode === 'diff' || (st.mode === 'side' && ($('#ovSideHl').checked || $('#ovBoxes').checked)))) {
      res = await diffImage(cl, cr, +$('#ovThr').value, $('#ovFaint').checked, { dx, dy, ang, resF, tolF });
      if (stale()) return null;
    }
    return { l, r, cl, cr, dx, dy, ang, res, autoMsg, scale, resF, both: !!(pl && pr) };
  }
  // 表示用の要素を組み立てる（v.el）。差分の枠・点滅・スワイプはページごとの v に持たせる
  function compose(d) {
    const v = { ...d, regions: [], regIdx: -1, out: null, base: null, side: null, frame: null, drawSwipe: null, stats: '', noteIds: [] };
    const { cl, cr, dx, dy, ang } = d;
    if (!cl || !cr) {
      const pair = document.createElement('div'); pair.className = 'pair';
      for (const c of [cl, cr]) if (c) { const x = mkCanvas(c.width, c.height, d.scale); x.getContext('2d').drawImage(c, 0, 0); placeCanvas(x, false); pair.appendChild(x); }
      v.el = pair;
      v.stats = d.both ? (cl ? '<b>左だけにあるページです</b><br><span class="muted">右では削除されています</span>' : '<b>右だけにあるページです</b><br><span class="muted">右で追加されたページです</span>') : '片側のみ読み込まれています';
      return v;
    }
    const W2 = Math.max(cl.width, cr.width + Math.max(0, dx)), H2 = Math.max(cl.height, cr.height + Math.max(0, dy));
    if (st.mode === 'side') {
      const pair = document.createElement('div'); pair.className = 'pair';
      const canvases = [0, 1].map(() => { const x = mkCanvas(W2, H2, d.scale); placeCanvas(x, true); pair.appendChild(x); return x; });
      v.side = { canvases, res: d.res }; v.regions = d.res ? d.res.regions : []; v.out = canvases[0]; v.el = pair;
      v.noteIds = d.res ? v.regions.map(g => Notes.ovId(d.l, d.r, g, d.res.W, d.res.H)) : [];
      canvases.forEach(cv => cv.addEventListener('click', e => pickRegion(v, cv, e)));
      drawSide(v);
      v.stats = d.res ? resultHtml(d.res, d.autoMsg) : '並べて表示中';
      return v;
    }
    const out = mkCanvas(W2, H2, d.scale), c = out.getContext('2d');
    v.out = out; v.el = out;
    const tint = $('#ovTint').checked, colL = $('#ovColL').value, colR = $('#ovColR').value;
    if (st.mode === 'diff') {
      v.base = d.res; v.regions = d.res.regions;
      v.noteIds = v.regions.map(g => Notes.ovId(d.l, d.r, g, d.res.W, d.res.H));
      out.addEventListener('click', e => pickRegion(v, out, e));
      drawBoxes(v);
      v.stats = resultHtml(d.res, d.autoMsg);
    } else if (st.mode === 'overlay') {
      // 色付け：左右の線をそれぞれの色にして乗算で重ねる（重なった線は濃く、片側だけの線はその色で見える）
      c.fillStyle = '#fff'; c.fillRect(0, 0, W2, H2); c.drawImage(tint ? tinted(cl, colL) : cl, 0, 0);
      c.globalAlpha = +$('#ovOpacity').value / 100; if (tint) c.globalCompositeOperation = 'multiply';
      drawR(c, tint ? tinted(cr, colR) : cr, dx, dy, ang);
      c.globalAlpha = 1; c.globalCompositeOperation = 'source-over';
      v.stats = '左の上に右を半透明で重ねています' + (tint ? '<br><span class="muted">色：左＝左の色、右＝右の色、重なった線は濃く表示</span>' : '');
    } else if (st.mode === 'swipe') {
      const L = tint ? tinted(cl, colL) : cl, R = tint ? tinted(cr, colR) : cr;
      v.drawSwipe = () => {
        const x = Math.round(W2 * +$('#ovSwipe').value / 100);
        c.fillStyle = '#fff'; c.fillRect(0, 0, W2, H2); c.drawImage(L, 0, 0);
        c.save(); c.beginPath(); c.rect(x, 0, W2 - x, H2); c.clip(); c.fillStyle = '#fff'; c.fillRect(x, 0, W2 - x, H2); drawR(c, R, dx, dy, ang); c.restore();
        c.fillStyle = '#1f6feb'; c.fillRect(x - 2, 0, 4, H2);
        // 境界のつまみ（手のひらツールのときも、ここをドラッグすれば境界を動かせる）
        const kr = Math.max(14, Math.round(W2 * 0.012)), ky = Math.round(H2 / 2);
        c.beginPath(); c.arc(x, ky, kr, 0, Math.PI * 2); c.fill();
        c.strokeStyle = '#fff'; c.lineWidth = Math.max(2, kr / 6); c.beginPath();
        c.moveTo(x - kr * 0.25, ky - kr * 0.45); c.lineTo(x - kr * 0.6, ky); c.lineTo(x - kr * 0.25, ky + kr * 0.45);
        c.moveTo(x + kr * 0.25, ky - kr * 0.45); c.lineTo(x + kr * 0.6, ky); c.lineTo(x + kr * 0.25, ky + kr * 0.45); c.stroke();
        c.font = 'bold 22px sans-serif'; c.fillStyle = 'rgba(192,80,77,.9)'; c.fillText('◀ 左', Math.max(8, x - 80), 30); c.fillStyle = 'rgba(58,143,74,.9)'; c.fillText('右 ▶', Math.min(W2 - 70, x + 12), 30);
      };
      v.drawSwipe();
      // 境界は全ページ共通（どのページで動かしても、表示中のページすべてに反映）
      const move = e => { const rc = out.getBoundingClientRect(); $('#ovSwipe').value = Math.max(0, Math.min(100, (e.clientX - rc.left) / rc.width * 100)); drawSwipes(); };
      // 手のひらツールのときは、境界の線の近く（±16px）をつかんだときだけ境界を動かし、それ以外は表示位置を動かす
      const nearEdge = e => { const rc = out.getBoundingClientRect(); return Math.abs(e.clientX - (rc.left + rc.width * +$('#ovSwipe').value / 100)) <= 16; };
      let drag = false;
      out.addEventListener('pointerdown', e => {
        if (e.button !== 0 || (st.hand && !nearEdge(e))) return;
        e.preventDefault(); e.stopPropagation(); drag = true; out.setPointerCapture(e.pointerId); move(e);
      });
      out.addEventListener('pointermove', e => {
        if (drag && (e.buttons & 1)) move(e);
        else out.classList.toggle('edge', st.hand && nearEdge(e));
      });
      const end = () => { drag = false; };
      out.addEventListener('pointerup', end); out.addEventListener('pointercancel', end);
      out.classList.add('swipe');
      v.stats = '画像上をドラッグして境界を動かせます<br><span class="muted">手のひらツールのときは、境界の線（つまみ）をドラッグします</span>';
    } else if (st.mode === 'blink') {
      v.frame = on => {
        c.fillStyle = '#fff'; c.fillRect(0, 0, W2, H2);
        if (on) drawR(c, cr, dx, dy, ang); else c.drawImage(cl, 0, 0);
        c.font = 'bold 26px sans-serif'; c.fillStyle = on ? 'rgba(58,143,74,.95)' : 'rgba(192,80,77,.95)';
        c.fillText(on ? '右' : '左', 14, 34);
      };
      v.frame(st.blinkOn);
      out.addEventListener('click', () => { if (!st.hand) st.blinkFrame(); });
      v.stats = $('#ovBlinkManual').checked ? '画像をクリック（または Space）で左右を切り替えます' : '左右を交互に表示しています（変わった部分がちらつきます）。画像のクリックでも切り替えられます';
    }
    placeCanvas(out);
    return v;
  }
  const drawSwipes = () => liveViews().forEach(v => v.drawSwipe && v.drawSwipe());
  // 今のページ（右パネルの結果・位置合わせ・前後の変更の対象）を切り替える
  function setCurrent(v) {
    st.cur = v;
    st.l = v.l; st.r = v.r; st.dx = v.dx; st.dy = v.dy; st.ang = v.ang; st.scale = v.scale; st.resF = v.resF;
    st.cl = v.cl; st.cr = v.cr; st.out = v.out; st.base = v.base; st.side = v.side; st.regions = v.regions; st.regIdx = v.regIdx;
    showOffset();
    $('#ovStats').innerHTML = v.stats;
    renderOvNotes();
  }
  function selectPages(pl, pr) {
    fillSelect($('#ovLPage'), pl ? pl.length : 0, st.l); fillSelect($('#ovRPage'), pr ? pr.length : 0, st.r);
  }
  const EMPTY = '<div class="pv-empty" style="color:#f2f4f6">左右にPDFまたは画像を読み込むと、ページを重ねて変更箇所を検出します<br><span style="font-size:12.5px">スキャン画像（PNG/JPEG）同士や、PDFとスキャン画像の比較にも使えます</span></div>';

  async function update() {
    st.dirty = false; stopBlink();
    const gen = ++st.gen;
    const pl = await pages(0).catch(() => null), pr = await pages(1).catch(() => null);
    if (gen !== st.gen) return;
    selectPages(pl, pr);
    if (!pl && !pr) { dropSlots(); st.cur = null; view.innerHTML = EMPTY; $('#ovStats').textContent = '—'; return; }
    if (st.scroll) return buildScroll(pl, pr, gen);
    if (st.mode === 'blink') st.blinkOn = false; // 左から表示する
    let d;
    try { d = await prepare(pl, pr, st.l, st.r, gen); }
    catch (e) { if (gen === st.gen) { dropSlots(); view.innerHTML = `<div class="pv-empty">描画に失敗しました: ${esc(e.message || '')}</div>`; } return; }
    if (!d) return;
    // 差分画像は表示を消す前に計算する（計算中も前の結果を見られるように）
    const v = compose(d);
    dropSlots(); view.innerHTML = ''; view.appendChild(v.el);
    setCurrent(v);
    startBlink();
  }

  /* ---- 全ページ表示：全ページを縦に並べ、見えているページだけを描く ---- */
  let io = null;
  function dropSlots() { if (io) { io.disconnect(); io = null; } st.slots = null; st.curSlot = null; }
  const pairLabel = p => `左 ${p.l < 0 ? '—' : p.l + 1} ／ 右 ${p.r < 0 ? '—' : p.r + 1}`;
  async function buildScroll(pl, pr, gen) {
    const pairs = pl && pr ? await pagePairs(pl, pr) : (pl || pr).map((_, i) => ({ l: pl ? i : -1, r: pr ? i : -1 }));
    if (gen !== st.gen) return;
    if (st.mode === 'blink') st.blinkOn = false;
    // 今のページの、ページ内のどこを見ていたかを覚えておき、組み立て直した後も同じ位置を表示する
    const cs = st.slots && st.curSlot, keep = cs && cs.p.l === st.l && cs.p.r === st.r ? keepPos() : null;
    dropSlots();
    const list = document.createElement('div'); list.className = 'ov-scroll';
    const half = st.mode === 'side';
    st.slots = pairs.map((p, k) => {
      const el = document.createElement('div'); el.className = 'ov-page'; el.dataset.k = k;
      const head = document.createElement('div'); head.className = 'ov-pghead';
      head.innerHTML = `<span>${pairLabel(p)}</span>` + (p.l < 0 ? '<span class="tag add">右で追加</span>' : p.r < 0 ? '<span class="tag del">左から削除</span>' : '');
      const body = document.createElement('div'); body.className = 'pair';
      // まだ描いていないページは、ページの大きさの仮の枠で場所を取っておく
      const pgL = pl && p.l >= 0 ? pl[p.l] : null, pgR = pr && p.r >= 0 ? pr[p.r] : null, pg = pgL || pgR;
      const W = renderWidth(pgL, pgR), sc = W / Math.max(pgL ? pgL.w : 0, pgR ? pgR.w : 0);
      const n = (pgL && pgR) ? (half ? 2 : 1) : 1;
      for (let i = 0; i < n; i++) {
        const ph = document.createElement('div'); ph.className = 'ov-ph'; ph.textContent = '描画中…';
        ph.dataset.w = Math.round(pg.w * sc); ph.dataset.h = Math.round(pg.h * sc); ph.dataset.scale = sc;
        placeCanvas(ph, half && n === 2); body.appendChild(ph);
      }
      el.append(head, body); list.appendChild(el);
      return { k, p, el, head, body, v: null, near: false, busy: false };
    });
    view.innerHTML = ''; view.appendChild(list);
    // 開いたときは今のページへ
    let k0 = st.slots.findIndex(s => s.p.l === st.l && s.p.r === st.r);
    if (k0 < 0) k0 = Math.max(0, st.slots.findIndex(s => (st.l >= 0 && s.p.l === st.l) || (st.l < 0 && s.p.r === st.r)));
    st.curSlot = null;
    if (keep && st.slots[keep.k] && st.slots[keep.k].p.l === st.l && st.slots[keep.k].p.r === st.r) { restorePos(keep); markCurrent(st.slots[keep.k]); } else scrollToSlot(k0, false);
    io = new IntersectionObserver(ents => {
      for (const e of ents) { const s = st.slots && st.slots[+e.target.dataset.k]; if (s) { s.near = e.isIntersecting; if (!s.near) releaseSlot(s); } }
      pump(gen);
    }, { root: view, rootMargin: '120% 0px' });
    st.slots.forEach(s => io.observe(s.el));
    onScroll();
    startBlink();
  }
  function keepPos() {
    const s = st.curSlot || st.slots[0], vr = view.getBoundingClientRect(), r = s.el.getBoundingClientRect();
    return { k: s.k, f: (vr.top - r.top) / (r.height || 1) };
  }
  function restorePos(kp) {
    const s = st.slots[kp.k]; if (!s) return;
    const vr = view.getBoundingClientRect(), r = s.el.getBoundingClientRect();
    view.scrollTop += r.top - vr.top + kp.f * r.height;
  }
  function scrollToSlot(k, smooth = true) {
    const s = st.slots[k]; if (!s) return;
    const top = view.scrollTop + s.el.getBoundingClientRect().top - view.getBoundingClientRect().top - 6;
    if (smooth) view.scrollTo({ top, behavior: 'smooth' }); else view.scrollTop = top;
    markCurrent(s);
  }
  // 見えていないページの描画は捨てる（メモリを使いすぎないように）。仮の枠に戻す
  function releaseSlot(s) {
    if (!s.v) return;
    const els = [...s.body.children];
    const ph = els.map(el => { const x = document.createElement('div'); x.className = 'ov-ph'; x.textContent = '描画中…'; x.dataset.w = el.width || el.dataset.w; x.dataset.h = el.height || el.dataset.h; x.dataset.scale = el.dataset.scale; placeCanvas(x, el.dataset.half === '1'); return x; });
    s.body.replaceChildren(...ph); s.v = null;
  }
  // 近くにあるページを、今のページに近い順に1つずつ描く
  let pumping = false;
  async function pump(gen) {
    if (pumping) return; pumping = true;
    try {
      const pl = await pages(0).catch(() => null), pr = await pages(1).catch(() => null);
      while (st.slots && gen === st.gen) {
        const c = st.curSlot ? st.curSlot.k : 0;
        const todo = st.slots.filter(s => s.near && !s.v && !s.failed).sort((a, b) => Math.abs(a.k - c) - Math.abs(b.k - c))[0];
        if (!todo) break;
        let d;
        try { d = await prepare(pl, pr, todo.p.l, todo.p.r, gen); }
        catch (e) { todo.body.innerHTML = `<div class="pv-empty">描画に失敗しました: ${esc(e.message || '')}</div>`; todo.failed = true; continue; }
        if (!d || gen !== st.gen || !st.slots) break;
        if (!todo.near) continue;
        fillSlot(todo, compose(d));
        await sleep(0);
      }
    } finally { pumping = false; }
    // 描いている間に世代が変わっていたら、新しい一覧で描き直す
    if (st.slots && gen !== st.gen && io) pump(st.gen);
  }
  function fillSlot(s, v) {
    // 今見ている位置より上のページの大きさが変わっても、表示位置がずれないようにする
    const vr = view.getBoundingClientRect(), above = s.el.getBoundingClientRect().bottom <= vr.top + 1, h0 = s.el.offsetHeight;
    s.v = v; s.body.replaceChildren(...(v.el.classList && v.el.classList.contains('pair') ? [...v.el.children] : [v.el]));
    if (above) view.scrollTop += s.el.offsetHeight - h0;
    if (v.regions && v.regions.length && v.l >= 0 && v.r >= 0 && st.mode !== 'blink') {
      if (!$('.tag.diff', s.head)) s.head.insertAdjacentHTML('beforeend', `<span class="tag diff">${v.regions.length} 箇所</span>`);
    }
    if (st.curSlot === s) setCurrent(v);
  }
  // 表示領域の上から 1/3 の位置にあるページを「今のページ」にする
  function markCurrent(s) {
    if (st.curSlot === s) return;
    if (st.curSlot) st.curSlot.el.classList.remove('cur');
    st.curSlot = s; s.el.classList.add('cur');
    if (s.v) setCurrent(s.v);
    else {
      st.cur = null; st.l = s.p.l; st.r = s.p.r; st.cl = st.cr = st.out = st.base = st.side = null; st.regions = [];
      const off = st.align.get(`${s.p.l}:${s.p.r}`) || [0, 0, 0]; [st.dx, st.dy, st.ang] = off; showOffset();
      $('#ovStats').innerHTML = '<span class="muted">描画しています…</span>';
    }
    $('#ovLPage').value = String(st.l); $('#ovRPage').value = String(st.r);
  }
  function onScroll() {
    if (!st.slots) return;
    const vr = view.getBoundingClientRect(), y = vr.top + Math.min(vr.height / 3, 200);
    let s = st.slots.find(q => q.el.getBoundingClientRect().bottom > y) || st.slots[st.slots.length - 1];
    if (s) markCurrent(s);
  }
  view.addEventListener('scroll', () => { if (st.slots) onScroll(); }, { passive: true });
  // 1ページだけ描き直す（位置合わせを変えたとき）
  async function redrawSlot(s) {
    const gen = st.gen, pl = await pages(0).catch(() => null), pr = await pages(1).catch(() => null);
    const d = await prepare(pl, pr, s.p.l, s.p.r, gen);
    if (d && st.slots && gen === st.gen) { const t = $('.tag.diff', s.head); if (t) t.remove(); fillSlot(s, compose(d)); }
  }
  // 1ページ表示はそのページを描き直し、全ページ表示はそのページまでスクロールする
  function go() {
    if (!st.slots) return update();
    let k = st.slots.findIndex(s => s.p.l === st.l && s.p.r === st.r);
    if (k < 0) k = st.slots.findIndex(s => (st.l >= 0 && s.p.l === st.l) || (st.l < 0 && s.p.r === st.r));
    if (k >= 0) scrollToSlot(k);
  }
  function setScroll(on) {
    st.scroll = on; Settings.set('ovScroll', on);
    $$('#ovViewSw button').forEach(b => b.classList.toggle('on', (b.dataset.v === 'scroll') === on));
    update();
  }
  $$('#ovViewSw button').forEach(b => b.onclick = () => setScroll(b.dataset.v === 'scroll'));

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
  const endPan = () => { if (pan && pan.moved) st.panAt = Date.now(); pan = null; view.classList.remove('panning'); };
  view.addEventListener('pointerup', endPan); view.addEventListener('pointercancel', endPan);

  function gotoRegion(d) {
    const v = st.cur;
    if ((st.mode !== 'diff' && st.mode !== 'side') || !v || !v.regions.length) return toast('このページに変更箇所はありません');
    selectRegion(v, (v.regIdx + d + v.regions.length) % v.regions.length, true);
  }

  // 変更箇所を選ぶ（枠を太くし、右のパネルの入力欄をその箇所にする）。scroll なら表示位置も合わせる
  function selectRegion(v, i, scroll) {
    v.regIdx = i; if (v === st.cur) st.regIdx = i;
    drawBoxes(v);
    if (v !== st.cur && st.slots) { const s = st.slots.find(q => q.v === v); if (s) markCurrent(s); }
    renderOvNotes();
    if (!scroll) return;
    const r = v.regions[i], o = v.out.getBoundingClientRect(), vr = view.getBoundingClientRect(), k = o.width / v.out.width;
    view.scrollTo({ top: view.scrollTop + o.top - vr.top + r.y * k - view.clientHeight / 3, left: view.scrollLeft + o.left - vr.left + r.x * k - view.clientWidth / 3, behavior: 'smooth' });
  }
  // 画像のクリックで、その位置の変更箇所を選ぶ（手のひらツールのとき・ドラッグのあとは選ばない）
  function pickRegion(v, cv, e) {
    if (st.hand || Date.now() - (st.panAt || 0) < 300) return;
    const rc = cv.getBoundingClientRect(), k = cv.width / rc.width, x = (e.clientX - rc.left) * k, y = (e.clientY - rc.top) * k, m = 10 * k;
    const i = v.regions.findIndex(g => x >= g.x - m && x <= g.x + g.w + m && y >= g.y - 24 * k - m && y <= g.y + g.h + m);
    if (i >= 0) selectRegion(v, i, false);
  }
  /* ---- 変更箇所の一覧とコメント（右のパネル） ---- */
  function regionPos(g, res) { return `横 ${Math.round((g.x + g.w / 2) / res.W * 100)}%・縦 ${Math.round((g.y + g.h / 2) / res.H * 100)}%`; }
  function renderOvNotes() {
    const box = $('#ovNotes'); if (!box) return;
    const v = st.cur;
    if (!v || !v.noteIds || !v.noteIds.length || !(v.base || (v.side && v.side.res))) { box.innerHTML = ''; return; }
    const res = v.base || v.side.res;
    box.innerHTML = `<div class="ov-nt-h muted">変更箇所を選ぶと、確認の状態とひとことを付けられます（画像の枠のクリックでも選べます）</div>` +
      v.regions.map((g, i) => `<div class="nt-item${i === v.regIdx ? ' cur' : ''}${noteCls(v.noteIds[i])}" data-i="${i}"><div class="nt-h"><b>${i + 1}</b><span class="muted">${regionPos(g, res)}</span></div><div class="nt-sum">${Notes.chip(v.noteIds[i])}</div></div>`).join('');
    const cur = $(`.nt-item[data-i="${v.regIdx}"]`, box);
    if (cur) cur.appendChild(Notes.editor(v.noteIds[v.regIdx], `左 ${v.l + 1} ページ ／ 右 ${v.r + 1} ページ　変更箇所 ${v.regIdx + 1}（${regionPos(v.regions[v.regIdx], res)}）`));
    $$('.nt-item', box).forEach(el => el.addEventListener('click', e => { if (!e.target.closest('.nt-ed')) selectRegion(v, +el.dataset.i, true); }));
  }
  const noteCls = id => { const nv = Notes.get(id); return !nv ? '' : nv.st === 'ok' ? ' nt-ok' : nv.st === 'ask' ? ' nt-ask' : ' nt-c'; };
  Notes.on(id => {
    if (App.tab !== 'overlay') return;
    drawBoxes();
    const v = st.cur, box = $('#ovNotes');
    if (!v || !box) return;
    const i = id ? v.noteIds.indexOf(id) : -1;
    if (i >= 0) { const it = $(`.nt-item[data-i="${i}"]`, box); if (it) { it.className = `nt-item${i === v.regIdx ? ' cur' : ''}${noteCls(id)}`; $('.nt-sum', it).innerHTML = Notes.chip(id); } }
    else if (!id) renderOvNotes();
  });

  // 比べるページの組（対応付けが有効ならその結果、なければ同じページ番号どうし）
  async function pagePairs(pl, pr) {
    const pairs = PageMatch.enabled() ? await ensureMatch() : null;
    if (pairs) return pairs;
    return Array.from({ length: Math.max(pl.length, pr.length) }, (_, i) => ({ l: i < pl.length ? i : -1, r: i < pr.length ? i : -1 }));
  }
  // 1組を、1ページずつ表示したときと同じ解像度・位置合わせで調べる（件数をそろえるため）
  async function analyzePair(pl, pr, p, stop) {
    if (p.l < 0 || p.r < 0) return { ...p, kind: p.l < 0 ? 'add' : 'del', regs: 0, pct: 0 };
    const W = renderWidth(pl[p.l], pr[p.r]), fk = fileKeys();
    const a = await renderAt(0, p.l, W), b = await renderAt(1, p.r, W);
    const key = `${p.l}:${p.r}`;
    let off = st.align.get(key);
    if (!off) {
      off = scanMode() ? await autoAlign(a, b) : [0, 0, 0]; if (stop()) return null;
      if (fk !== fileKeys()) return null; // 途中でファイルが変わった：位置合わせの結果を、新しいファイルの組に残さない
      if (scanMode()) st.align.set(key, off);
    }
    const res = await diffImage(a, b, +$('#ovThr').value, $('#ovFaint').checked, { dx: off[0], dy: off[1], ang: off[2], resF: resFactor(pl[p.l], pr[p.r]), tolF: tolFactor(pl[p.l], pr[p.r]) });
    return { ...p, kind: 'pair', regs: res.regions.length, pct: res.ink ? res.changed / res.ink * 100 : 0, res, off };
  }
  /* ---- ページ表示・注釈タブ用：ページの組の変更箇所を、各ページの座標（pt）で返す ---- */
  // 結果は、ファイル・感度・許容・解像度が同じあいだ覚えておく。同じ組を同時に頼まれたら同じ計算を待つ
  const rcache = new Map();
  function regionsFor(l, r) {
    const key = `${st.gen0}:${l}:${r}:${$('#ovThr').value}:${$('#ovTolPx').value}:${Settings.get('ovRes')}:${colorCheck()}`;
    if (!rcache.has(key)) {
      if (rcache.size > 200) rcache.clear();
      rcache.set(key, (async () => {
        const pl = await pages(0), pr = await pages(1);
        if (!pl || !pr || !pl[l] || !pr[r]) return null;
        const a = await analyzePair(pl, pr, { l, r }, () => false);
        if (!a) return null;
        const res = a.res, off = a.off || [0, 0, 0], W = renderWidth(pl[l], pr[r]);
        const sL = W / pl[l].w, sR = W / pr[r].w, cw = W, ch = Math.round(pr[r].h * sR);
        const ids = res.regions.map(g => Notes.ovId(l, r, g, res.W, res.H));
        // 左：描画の画素 → pt。右：位置合わせ（回転→平行移動）を逆にたどってから pt
        const cos = Math.cos(-off[2] * Math.PI / 180), sin = Math.sin(-off[2] * Math.PI / 180);
        const back = (x, y) => { const px = x - off[0] - cw / 2, py = y - off[1] - ch / 2; return [cos * px - sin * py + cw / 2, sin * px + cos * py + ch / 2]; };
        const toPt = (side, g) => {
          if (!side) return { x: g.x / sL, y: g.y / sL, w: g.w / sL, h: g.h / sL };
          const c = [back(g.x, g.y), back(g.x + g.w, g.y), back(g.x, g.y + g.h), back(g.x + g.w, g.y + g.h)];
          const xs = c.map(q => q[0]), ys = c.map(q => q[1]), x0 = Math.min(...xs), y0 = Math.min(...ys);
          return { x: x0 / sR, y: y0 / sR, w: (Math.max(...xs) - x0) / sR, h: (Math.max(...ys) - y0) / sR };
        };
        const W2 = res.W, H2 = res.H;
        return { l, r, regions: res.regions.map(({ x, y, w, h }) => ({ x, y, w, h })), ids, toPt, pos: g => `横 ${Math.round((g.x + g.w / 2) / W2 * 100)}%・縦 ${Math.round((g.y + g.h / 2) / H2 * 100)}%` };
      })().catch(e => { console.warn('regionsFor', e); return null; }));
    }
    return rcache.get(key);
  }
  async function scan() {
    if (st.scanning) { st.scanning = false; return; }
    const pl = await pages(0).catch(() => null), pr = await pages(1).catch(() => null);
    if (!pl || !pr) return toast('左右に文書を読み込んでください');
    const res = $('#ovScanRes'), btn = $('#ovScan');
    st.scanning = true; $('.lbl', btn).textContent = '中止'; res.innerHTML = '';
    const pairs = await pagePairs(pl, pr), rows = [];
    for (let k = 0; k < pairs.length && st.scanning; k++) {
      res.innerHTML = `<span class="muted">調べています… ${k + 1} / ${pairs.length}</span>`;
      const r = await analyzePair(pl, pr, pairs[k], () => !st.scanning);
      if (!r || !st.scanning) break;
      delete r.res; rows.push(r);
      await sleep(0);
    }
    const stopped = !st.scanning; st.scanning = false; $('.lbl', btn).textContent = '全ページの差分を調べる';
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
  // 左右に並べるときの画像：左はそのまま、右は位置合わせした状態にし、変更箇所に色と枠を付ける
  function sideImages(a, b, off, res, ids) {
    const W2 = Math.max(a.width, b.width + Math.max(0, off[0])), H2 = Math.max(a.height, b.height + Math.max(0, off[1]));
    return [0, 1].map(k => {
      const cv = document.createElement('canvas'); cv.width = W2; cv.height = H2;
      const c = cv.getContext('2d'); c.fillStyle = '#fff'; c.fillRect(0, 0, W2, H2);
      if (k === 0) c.drawImage(a, 0, 0); else drawR(c, b, off[0], off[1], off[2]);
      if (res) {
        const im = c.getImageData(0, 0, W2, H2), d = im.data, m = res.mask, want = k + 1, col = k ? [26, 115, 232] : [229, 50, 45];
        for (let j = 0; j < m.length; j++) if (m[j] === want) { const q = j * 4; d[q] = col[0]; d[q + 1] = col[1]; d[q + 2] = col[2]; }
        else if (m[j] === 3) { const q = j * 4; d[q] = (d[q] + 156) >> 1; d[q + 1] = (d[q + 1] + 54) >> 1; d[q + 2] = (d[q + 2] + 181) >> 1; }
        c.putImageData(im, 0, 0); drawBoxesOn(c, res.regions, -1, ids);
      }
      return cv;
    });
  }
  async function exportReport() {
    const pl = await pages(0).catch(() => null), pr = await pages(1).catch(() => null);
    if (!pl || !pr) return toast('左右に文書を読み込んでください');
    const o = await Report.options('overlay', '重ね合わせ比較のレポート',
      '出力する内容を選び、下のボタンで載せるページを選んでください。<br><span class="muted">追加・削除されたページは、どちらを選んでも載せます。変更のないページは一覧にだけ載せます（「すべてのページ」を選ぶと画像も載せます）。ページ数が多いと時間がかかります。</span>',
      [{ k: 'layout', label: '画像の並べ方', type: 'radio', def: 'diff', choices: [['diff', '差分画像（重ねた画像）'], ['side', '左右に並べる'], ['both', '差分画像＋左右に並べる']] },
        Report.qualityField,
        { k: 'files', label: 'ファイル情報（SHA-256）', type: 'check', def: true },
        { k: 'cond', label: '比較条件', type: 'check', def: true },
        { k: 'summary', label: 'ページの一覧', type: 'check', def: true },
        { k: 'regions', label: '変更箇所の位置の表', type: 'check', def: true }],
      [{ label: 'すべてのページ', value: 'all' }, { label: '変更のあるページだけ', value: 'changed', primary: true }]);
    if (!o) return;
    const scope = o.scope, maxW = Report.width(o.quality), sideW = Math.round(maxW * 0.7);
    const nm = side => esc(S[side].name);
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
          // 追加・削除されたページは、そのページだけを載せる（左右に並べるときは、ない側を空けておく）
          const side = r.kind === 'add' ? 1 : 0, idx = side ? r.r : r.l, cv = await renderAt(side, idx, Math.min(maxW, renderWidth(side ? null : pl[idx], side ? pr[idx] : null)));
          const cap = r.kind === 'add' ? '右だけにあるページ（追加されたページ）' : '左だけにあるページ（削除されたページ）';
          const fig = `<figure><img src="${Report.jpeg(cv, o.layout === 'diff' ? maxW : sideW)}" alt=""><figcaption>${side ? '右' : '左'}：${nm(side)}　${idx + 1} ページ<br>${cap}</figcaption></figure>`;
          const body = o.layout === 'diff' ? fig : `<div class="pair">${side ? '<div class="none">（対応するページなし）</div>' + fig : fig + '<div class="none">（対応するページなし）</div>'}</div>`;
          secs.push(`<h2 id="p${k}">${title}　<span class="tag ${r.kind}">${r.kind === 'add' ? '右で追加' : '左から削除'}</span></h2>${body}`);
        } else if (scope === 'all' || r.regs) {
          const res = r.res, parts = [], ids = res.regions.map(g => Notes.ovId(r.l, r.r, g, res.W, res.H));
          const offTxt = r.off && (r.off[0] || r.off[1] || r.off[2]) ? `。右の位置合わせ：X ${r.off[0]} / Y ${r.off[1]}px${r.off[2] ? ` / 回転 ${r.off[2]}°` : ''}` : '';
          if (o.layout !== 'side') {
            const cv = document.createElement('canvas'); cv.width = res.W; cv.height = res.H;
            const c = cv.getContext('2d'); c.putImageData(res.img, 0, 0); drawBoxesOn(c, res.regions, -1, ids);
            parts.push(`<figure><img src="${Report.jpeg(cv, maxW)}" alt=""><figcaption>差分画像：赤＝左にだけある（削除・変更前）、青＝右にだけある（追加・変更後）、紫＝色が変わった、橙の枠＝変更箇所。変化量 ${r.pct.toFixed(2)}%${offTxt}</figcaption></figure>`);
            cv.width = cv.height = 0;
          }
          if (o.layout !== 'diff') {
            const W = renderWidth(pl[r.l], pr[r.r]);
            const [a, b] = await Promise.all([renderAt(0, r.l, W), renderAt(1, r.r, W)]);
            const [ca, cb] = sideImages(a, b, r.off || [0, 0, 0], res, ids);
            parts.push(`<div class="pair"><figure><img src="${Report.jpeg(ca, sideW)}" alt=""><figcaption>左：${nm(0)}　${r.l + 1} ページ（赤＝左にだけある部分）</figcaption></figure>` +
              `<figure><img src="${Report.jpeg(cb, sideW)}" alt=""><figcaption>右：${nm(1)}　${r.r + 1} ページ（青＝右にだけある部分）${o.layout === 'side' ? `。変化量 ${r.pct.toFixed(2)}%${offTxt}` : ''}</figcaption></figure></div>`);
            ca.width = ca.height = cb.width = cb.height = 0;
          }
          const nst = v => !v || !v.st ? '<span class="nst none">未確認</span>' : v.st === 'ok' ? '<span class="nst ok">確認済</span>' : '<span class="nst ask">要確認</span>';
          const list = o.regions ? res.regions.map((g, i) => { const v = Notes.get(ids[i]); return `<tr><td class="num">${i + 1}</td><td>横 ${Math.round(g.x / res.W * 100)}%・縦 ${Math.round(g.y / res.H * 100)}%</td><td>${Math.round(g.w / res.W * 100)}% × ${Math.round(g.h / res.H * 100)}%</td><td>${nst(v)}</td><td>${v && v.text ? esc(v.text).replace(/\n/g, '<br>') + (v.by || v.at ? `<div class="by">${esc(v.by)}${v.by ? '・' : ''}${v.at ? fmtDate(v.at) : ''}</div>` : '') : ''}</td></tr>`; }).join('') : '';
          r.nOk = ids.filter(id => (Notes.get(id) || {}).st === 'ok').length; r.nAsk = ids.filter(id => (Notes.get(id) || {}).st === 'ask').length;
          secs.push(`<h2 id="p${k}">${title}　${r.regs ? `<span class="tag diff">${r.regs} 箇所</span>` : '<span class="tag same">変更なし</span>'}</h2>` + parts.join('') +
            (list ? `<table class="list"><thead><tr><th style="width:50px">番号</th><th style="width:22%">位置（ページの左上から）</th><th style="width:18%">大きさ</th><th style="width:70px">確認</th><th>コメント</th></tr></thead><tbody>${list}</tbody></table>` : ''));
        }
        delete r.res;
        await sleep(0);
      }
      const nPair = rows.filter(r => r.kind === 'pair').length, nChg = rows.filter(r => r.regs).length;
      const nAdd = rows.filter(r => r.kind === 'add').length, nDel = rows.filter(r => r.kind === 'del').length;
      const summary = !o.summary ? '' : `<h2>ページの一覧</h2><table class="list"><thead><tr><th class="num">左</th><th class="num">右</th><th>結果</th><th class="num">変化量</th></tr></thead><tbody>` +
        rows.map((r, k) => `<tr><td class="num">${pg(r.l)}</td><td class="num">${pg(r.r)}</td><td>${r.kind === 'add' ? '<span class="tag add">右で追加</span>' : r.kind === 'del' ? '<span class="tag del">左から削除</span>' : r.regs ? `<span class="tag diff">${r.regs} 箇所</span>` : '<span class="tag same">変更なし</span>'}${r.nOk ? ` <span class="nst ok">確認済 ${r.nOk}</span>` : ''}${r.nAsk ? ` <span class="nst ask">要確認 ${r.nAsk}</span>` : ''}</td><td class="num">${r.kind === 'pair' ? r.pct.toFixed(2) + '%' : ''}</td></tr>`).join('') + '</tbody></table>';
      const cond = [`差分の感度 ${$('#ovThr').value}`, `ずれの許容 ${$('#ovTolPx').value}px`, colorCheck() ? '色の違いも検出' : '色の違いは検出しない', `解像度 ${$('#ovRes').selectedOptions[0].textContent}`, PageMatch.enabled() ? 'ページの挿入・削除を自動で対応付け' : '同じページ番号どうしで比較'].join('、');
      html = Report.page({
        title: `重ね合わせレポート - ${S[0].name} / ${S[1].name}`, heading: '重ね合わせ比較レポート',
        meta: `<b>変更のあるページ ${nChg} / ${nPair}</b>${nAdd ? `　右で追加 ${nAdd} ページ` : ''}${nDel ? `　左から削除 ${nDel} ページ` : ''}` + (o.cond ? `<br>比較条件: ${esc(cond)}` : '') +
          (o.files ? '' : `<br>左: ${nm(0)}　右: ${nm(1)}`),
        body: (o.files ? await Report.bothInfo() : '') + summary + secs.join(''),
        css: '.pair figure{margin:4px 0 14px}.none{border:1px dashed #bbb;color:#888;display:flex;align-items:center;justify-content:center;min-height:120px;margin:4px 0 14px}.nst{font-weight:700;font-size:11.5px}.nst.ok{color:#1b5e20}.nst.ask{color:#c2410c}.nst.none{color:#999;font-weight:400}.by{color:#777;font-size:10.5px}'
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
  // 連動中で対応付けを計算している途中なら、終わるのを待つ（待たずに送ると、挿入・削除されたページを飛ばせず組がずれる）
  const needMatch = () => $('#ovLink').checked && S[0] && S[1] && PageMatch.enabled() && !PageMatch.ready();
  let waiting = null;
  async function afterMatch(fn) {
    if (!needMatch()) return fn();
    const ticket = {}; waiting = ticket;
    toast('ページの対応を調べています。終わりしだい移動します…');
    await ensureMatch().catch(() => null);
    if (waiting === ticket) { waiting = null; fn(); } // 待っている間に別の操作が来たら、最後の操作だけを行う
  }
  function step(side, d) {
    if (needMatch()) return afterMatch(() => step(side, d));
    if (st.slots) { const c = st.curSlot ? st.curSlot.k : 0; return scrollToSlot(Math.max(0, Math.min(st.slots.length - 1, c + d))); }
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
    go();
  }

  $$('#ovModes button').forEach(b => b.onclick = () => setMode(b.dataset.mode));
  $('#ovLPrev').onclick = () => step(0, -1); $('#ovLNext').onclick = () => step(0, 1);
  $('#ovRPrev').onclick = () => step(1, -1); $('#ovRNext').onclick = () => step(1, 1);
  $('#ovLPage').onchange = e => {
    const v = +e.target.value;
    if (needMatch()) { e.target.value = String(st.l); return afterMatch(() => { $('#ovLPage').value = String(v); $('#ovLPage').dispatchEvent(new Event('change')); }); }
    const d = v - st.l, pairs = PageMatch.ready();
    if ($('#ovLink').checked) st.r = pairs ? pairs.find(p => p.l === v).r : Math.max(0, Math.min($('#ovRPage').options.length - 2, st.r + d));
    st.l = v; go();
  };
  $('#ovRPage').onchange = e => {
    const v = +e.target.value;
    if (needMatch()) { e.target.value = String(st.r); return afterMatch(() => { $('#ovRPage').value = String(v); $('#ovRPage').dispatchEvent(new Event('change')); }); }
    const pairs = PageMatch.ready();
    if ($('#ovLink').checked && pairs) st.l = pairs.find(p => p.r === v).l;
    st.r = v; go();
  };
  $('#ovMatch').checked = PageMatch.enabled();
  $('#ovMatch').onchange = async () => {
    Settings.set('pageMatch', $('#ovMatch').checked);
    $('#ovScanRes').innerHTML = '';
    if ($('#ovMatch').checked) await ensureMatch(); else { $('#ovMatchInfo').innerHTML = ''; if (st.l < 0 || st.r < 0) { st.l = Math.max(0, st.l); st.r = Math.max(0, st.r); } }
    update();
  };
  $('#ovOpacity').oninput = () => { if (st.mode === 'overlay') update(); };
  $('#ovSwipe').oninput = () => { if (st.mode === 'swipe') drawSwipes(); };
  let thrT = 0; $('#ovThr').oninput = () => { clearTimeout(thrT); thrT = setTimeout(() => { if (st.mode === 'diff') update(); }, 150); };
    // 並べて表示で差分を計算していなかったページがあれば計算し直す
  const sideNoRes = () => liveViews().some(v => v.side && !v.side.res);
  $('#ovBoxes').onchange = () => { if (st.mode === 'side' && sideNoRes()) update(); else drawBoxes(); };
  $('#ovSideHl').onchange = () => { if (sideNoRes()) update(); else drawSide(); };
  for (const id of ['#ovTint', '#ovColL', '#ovColR']) $(id).addEventListener('change', () => { if (st.mode === 'overlay' || st.mode === 'swipe') update(); });
  $('#ovBlinkMs').oninput = () => { $('#ovBlinkVal').textContent = (+$('#ovBlinkMs').value / 1000).toFixed(2); startBlink(); };
  $('#ovBlinkManual').onchange = () => { startBlink(); if (st.mode === 'blink') $('#ovStats').innerHTML = $('#ovBlinkManual').checked ? '画像をクリック（または Space）で左右を切り替えます' : '左右を交互に表示しています（変わった部分がちらつきます）。画像のクリックでも切り替えられます'; };
  $('#ovBlinkToggle').onclick = () => { if (st.blinkFrame) st.blinkFrame(); };
  $('#ovFaint').onchange = () => update();
  $('#ovColor').onchange = () => { st.cache && rcache.clear(); update(); };
  let tolT = 0;
  $('#ovTolPx').oninput = () => { $('#ovTolVal').textContent = $('#ovTolPx').value; clearTimeout(tolT); tolT = setTimeout(update, 150); };
  const setOff = () => {
    st.dx = Math.round(+$('#ovDx').value || 0); st.dy = Math.round(+$('#ovDy').value || 0);
    st.ang = Math.max(-10, Math.min(10, Math.round((+$('#ovRot').value || 0) * 100) / 100));
    st.align.set(pairKey(), [st.dx, st.dy, st.ang]);
    if (st.slots) { if (st.curSlot) redrawSlot(st.curSlot); } else update();
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
    st.cache.clear(); st.align.clear(); rcache.clear(); $('#ovScanRes').innerHTML = ''; st.dirty = true;
    if (App.tab === 'overlay') update();
  });
  const zs = $('#ovZoom');
  zs.onchange = () => { if (zs.value !== 'custom') rezoom(zs.value); };
  // ＋／－は今の倍率から 1.25 倍ずつ（幅・縦に合わせているときも、その倍率から）
  $('#ovZIn').onclick = () => zoomBy(1.25);
  $('#ovZOut').onclick = () => zoomBy(1 / 1.25);
  let rt = 0; window.addEventListener('resize', () => { if (App.tab === 'overlay' && (st.zoom === 'fit' || st.zoom === 'fith')) { clearTimeout(rt); rt = setTimeout(() => { sized().forEach(c => placeCanvas(c, c.dataset.half === '1')); }, 100); } });

  showPanelFor(st.mode);
  st.scroll = !!Settings.get('ovScroll');
  $$('#ovViewSw button').forEach(b => b.classList.toggle('on', (b.dataset.v === 'scroll') === st.scroll));
  // ページの対応付けを（必要なら裏で）調べ、終わったら、連動中なら右のページを左に対応するページへ合わせ直す
  async function refreshMatch() {
    const before = PageMatch.ready(), gen = st.gen;
    const pairs = await ensureMatch();
    if (pairs && !before && App.tab === 'overlay' && st.scroll) { update(); return; }
    // 計算が終わったら、今の組を確かめ直す（計算中に表示を描き直していても、左のページに対応する右のページへ直す）
    if (pairs && !before && $('#ovLink').checked && App.tab === 'overlay' && !waiting) {
      const p = st.l >= 0 ? pairs.find(q => q.l === st.l) : pairs.find(q => q.r === st.r);
      if (p && (p.r !== st.r || p.l !== st.l)) { st.l = p.l; st.r = p.r; update(); }
    }
  }
  async function activate() {
    if (st.dirty) update();
    refreshMatch();
  }
  function deactivate() { stopBlink(); }
  st.gen0 = 0;
  function invalidate() {
    dropSlots(); st.cur = null; st.gen0++; rcache.clear();
    st.gen++; st.scanning = false; // 実行中の描画・位置合わせ・一括チェックは捨てる（前のファイルの結果を残さないように）
    st.l = 0; st.r = 0; st.cache.clear(); st.dirty = true; $('#ovScanRes').innerHTML = '';
    // ファイルが変わったら位置合わせ量を必ず0に戻す
    st.align.clear(); st.dx = 0; st.dy = 0; st.ang = 0; showOffset();
    // 「1px程度のずれを無視」はスキャン画像のときだけ既定でON（CADやWordから作ったPDFでは小さな変更を見落とさないようOFF）
    $('#ovTolPx').value = scanMode() ? 2 : 0; $('#ovTolVal').textContent = $('#ovTolPx').value;
    // 紙のスキャン（文字のないPDF）は、紙の地色や印刷のムラを拾わないよう色の比較を既定でオフ。画像・文字のあるPDFはオン
    $('#ovColor').checked = ![0, 1].some(i => S[i] && S[i].noTextLayer);
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
  return { activate, deactivate, invalidate, onKey, st, regionsFor, setPages: (l, r) => { st.l = l; st.r = r; } };
})();
