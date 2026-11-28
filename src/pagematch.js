/* ページの対応付け：途中でページが挿入・削除されても、似ているページどうしを組にする。
   ページ表示の連動、重ね合わせのページ送り、全ページ一括チェックで使う */
const PageMatch = (() => {
  // skipped：スキャンでページ数が同じため、調べずに1対1とみなした。visual：見た目で調べた結果（compute の visual 指定）
  // big：ページ数が多すぎて対応付けをしなかった（同じページ番号どうしを組にした）
  const st = { key: '', pairs: null, busy: null, info: '', skipped: false, visual: false, big: false };
  // 組の配列：{ l, r }（片側にしかないページは、反対側が -1）
  const enabled = () => Settings.get('pageMatch') !== false;
  const keyOf = () => (S[0] && S[1]) ? `${S[0].key}\u0001${S[1].key}\u0001${S[0].lines.length}\u0001${S[1].lines.length}` : '';

  /* ---- ページごとの特徴 ---- */
  // PDF の抽出文字（「===== ページ N =====」で区切られている）をページごとに分ける
  function pageTexts(s, n) {
    if (s.kind !== 'pdf' || s.noText || s.noTextLayer) return null; // スキャン（文字情報なし）は見た目で比べる
    const out = Array.from({ length: n }, () => []); let k = -1;
    for (const ln of s.lines) {
      const m = /^===== ページ (\d+) =====$/.exec(ln);
      if (m) { k = +m[1] - 1; continue; }
      if (k >= 0 && k < n) out[k].push(ln);
    }
    const feats = out.map(a => ({ lines: lineSet(a), grams: bigrams(a.join('\n')) }));
    // 文字がほとんどないページが半分を超えるなら、文字では比べられない（見た目で比べる）
    if (feats.filter(f => f.grams.total < 20).length * 2 > n) return null;
    return feats;
  }
  function bigrams(t) {
    const s = t.normalize('NFKC').replace(/\s+/g, ''), m = new Map();
    for (let i = 0; i < s.length - 1; i++) { const g = s.substr(i, 2); m.set(g, (m.get(g) || 0) + 1); }
    m.total = Math.max(0, s.length - 1); return m;
  }
  // 行の集まり（空白を詰めて正規化）。同じページなら、少し書き換えても多くの行が一致する
  function lineSet(lines) {
    const m = new Map(); let total = 0;
    for (const l of lines) { const k = l.normalize('NFKC').replace(/\s+/g, ''); if (!k) continue; m.set(k, (m.get(k) || 0) + 1); total++; }
    m.total = total; return m;
  }
  // ページの似ている度合い：行が3行以上あれば行の一致で、少なければ文字の並び（2文字の組）で比べる
  function textSim(a, b) {
    if (a.lines.total >= 3 && b.lines.total >= 3) return dice(a.lines, b.lines);
    return dice(a.grams, b.grams);
  }
  function dice(a, b) {
    if (!a.total && !b.total) return 1;
    if (!a.total || !b.total) return 0;
    let c = 0; const [x, y] = a.size < b.size ? [a, b] : [b, a];
    for (const [g, n] of x) { const k = y.get(g); if (k) c += Math.min(n, k); }
    return 2 * c / (a.total + b.total);
  }
  // 見た目の特徴：ページを 32×44 に縮小した濃さ（ぼかして、少しのずれ・傾きでは変わらないようにする）
  const TW = 48, TH = 66;
  async function thumb(pg) {
    const c = document.createElement('canvas'), scale = Math.min(1, 160 / Math.max(pg.w, pg.h));
    await pg.draw(c, scale);
    const t = document.createElement('canvas'); t.width = TW; t.height = TH;
    const x = t.getContext('2d', { willReadFrequently: true }); x.imageSmoothingQuality = 'high';
    x.fillStyle = '#fff'; x.fillRect(0, 0, TW, TH); x.drawImage(c, 0, 0, TW, TH);
    const d = x.getImageData(0, 0, TW, TH).data, v = new Float32Array(TW * TH);
    for (let i = 0; i < v.length; i++) v[i] = 255 - (77 * d[i * 4] + 150 * d[i * 4 + 1] + 29 * d[i * 4 + 2]) / 256;
    c.width = c.height = 0;
    return v;
  }
  function cosine(a, b) {
    let ab = 0, aa = 0, bb = 0;
    for (let i = 0; i < a.length; i++) { ab += a[i] * b[i]; aa += a[i] * a[i]; bb += b[i] * b[i]; }
    if (aa < 1e3 && bb < 1e3) return 1; // どちらもほぼ白紙
    if (aa < 1e3 || bb < 1e3) return 0;
    return ab / Math.sqrt(aa * bb);
  }

  /* ---- 並びをそろえる（ページの挿入・削除を許す動的計画法） ---- */
  // sim(i, j) が T を超える組だけを「同じページ」として組にし、合計が最大になる並びを選ぶ。
  // 組にならなかった左右のページが同じ数だけ並んでいる区間は、順に組にする（内容が大きく変わったページ）
  // 表のますの数の上限（たどり方の表が約100MB）。2万ページどうしに当たる。これを超えたら対応付けをせず、同じページ番号どうしを組にする
  const MAX_CELLS = 4e8;
  const tooBig = (n, m) => (n + 1) * (m + 1) > MAX_CELLS;
  const sameNumber = (n, m) => Array.from({ length: Math.max(n, m) }, (_, i) => ({ l: i < n ? i : -1, r: i < m ? i : -1 }));
  /* 表のメモリを抑える：点数は「直前の行」と「今の行」の2行だけを持ち、たどり方（1＝左だけ、2＝右だけ、3＝組）は1ますを2ビットに詰める。
     全ますを Float32 と Uint8 で持つと、5,000 ページどうしで約125MB、1万ページどうしで約500MB になる（詰めると約6MB、約25MB）。
     計算の順序と値は変えていないので、結果は全ますを持つ方式と同じ。
     tick を渡すと、ますの数が多いとき、途中で画面へ制御を返す（1万ページどうしで1億ます。止めたままにしない） */
  async function align(n, m, sim, T, tick) {
    if (tooBig(n, m)) return sameNumber(n, m);
    const band = Math.abs(n - m) + 30; // 対角線から離れすぎた組は調べない（ページ数が多いときの計算量を抑える）
    const W = m + 1, bt = new Uint8Array(Math.ceil((n + 1) * W / 4));
    const how = k => (bt[Math.floor(k / 4)] >> ((k % 4) * 2)) & 3;
    let prev = new Float32Array(W), cur = new Float32Array(W), since = 0;
    for (let i = 0; i <= n; i++) {
      for (let j = 0; j <= m; j++) {
        if (!i && !j) { cur[0] = 0; continue; }
        let best = -Infinity, h = 0;
        if (i) { const v = prev[j]; if (v > best) { best = v; h = 1; } }
        if (j) { const v = cur[j - 1]; if (v > best) { best = v; h = 2; } }
        if (i && j && Math.abs(i - j - (n - m) * i / Math.max(1, n)) <= band) {
          const g = sim(i - 1, j - 1) - T;
          if (g > 0) { const v = prev[j - 1] + g; if (v > best) { best = v; h = 3; } }
        }
        cur[j] = best;
        const k = i * W + j; bt[Math.floor(k / 4)] |= h << ((k % 4) * 2);
      }
      const t = prev; prev = cur; cur = t;
      if (tick && (since += W) > 4e6) { since = 0; await tick(); }
    }
    const raw = [];
    for (let i = n, j = m; i || j;) {
      const h = how(i * W + j);
      if (h === 3) { raw.push({ l: i - 1, r: j - 1 }); i--; j--; }
      else if (h === 1) { raw.push({ l: i - 1, r: -1 }); i--; }
      else { raw.push({ l: -1, r: j - 1 }); j--; }
    }
    raw.reverse();
    // 組にならなかった区間を整理する
    const out = [];
    for (let k = 0; k < raw.length;) {
      if (raw[k].l >= 0 && raw[k].r >= 0) { out.push(raw[k++]); continue; }
      const L = [], R = [];
      while (k < raw.length && !(raw[k].l >= 0 && raw[k].r >= 0)) { if (raw[k].l >= 0) L.push(raw[k].l); else R.push(raw[k].r); k++; }
      const c = Math.min(L.length, R.length);
      if (L.length === R.length) for (let q = 0; q < c; q++) out.push({ l: L[q], r: R[q] });
      else { L.forEach(l => out.push({ l, r: -1 })); R.forEach(r => out.push({ l: -1, r })); }
    }
    // 左右の番号順に並べ直す（左のみ・右のみが、前後の組の間に来るように）
    return out;
  }

  /* ---- 計算 ---- */
  // visual：文字のないスキャンでページ数が同じときも、見た目で調べる（既定では調べずに1対1とみなす。利用者が頼んだときだけ）
  async function compute(onProgress, visual = false) {
    const key = keyOf();
    if (!key) { st.key = ''; st.pairs = null; return null; }
    if (st.key === key && st.pairs && (!visual || !st.skipped)) return st.pairs;
    if (st.busy && st.busy.key === key && st.busy.visual === visual) return st.busy.p.then(r => r && r.pairs);
    const p = (async () => {
      const [pl, pr] = await Promise.all([S[0].getPages(), S[1].getPages()]);
      const n = pl.length, m = pr.length;
      let sim = null, skipped = false;
      const tl = pageTexts(S[0], n), tr = pageTexts(S[1], m);
      if (tl && tr) sim = (i, j) => textSim(tl[i], tr[j]);
      else if (n === m && !visual) skipped = true; // ページ数が同じなら1対1とみなす（全ページの縮小画像を作らない）
      else {
        // 文字がない（スキャン）ときは見た目で比べる
        const vl = [], vr = [], tot = n + m;
        for (let i = 0; i < n; i++) { vl.push(await thumb(pl[i])); if (onProgress) onProgress(i + 1, tot); if (keyOf() !== key) return null; }
        for (let j = 0; j < m; j++) { vr.push(await thumb(pr[j])); if (onProgress) onProgress(n + j + 1, tot); if (keyOf() !== key) return null; }
        sim = (i, j) => cosine(vl[i], vr[j]);
      }
      const big = !!sim && tooBig(n, m);
      const pairs = sim ? await align(n, m, sim, tl ? 0.3 : 0.55, () => sleep(0)) : sameNumber(n, m);
      if (keyOf() !== key) return null;
      return { pairs, skipped, visual: !!sim && !(tl && tr) && !big, big };
    })();
    const job = st.busy = { key, p, visual };
    const res = await p;
    if (st.busy === job) st.busy = null;
    if (res && keyOf() === key) { st.key = key; st.pairs = res.pairs; st.skipped = res.skipped; st.visual = res.visual; st.big = res.big; }
    return res && res.pairs;
  }
  function invalidate() { st.key = ''; st.pairs = null; st.busy = null; st.skipped = false; st.visual = false; st.big = false; }
  const ready = () => st.key === keyOf() && st.pairs && enabled() ? st.pairs : null;
  // 調べずに1対1とみなしたか（スキャンでページ数が同じ）。重ね合わせの画面で「見た目で調べ直す」を出すために使う
  const skipped = () => !!ready() && st.skipped;
  // 片側のページ i に対応する、反対側のページ番号（対応がなければ直前の対応から推定）
  function other(side, i, n) {
    const pairs = ready();
    if (!pairs) return Math.max(0, Math.min(i, n - 1));
    const me = side ? 'r' : 'l', ot = side ? 'l' : 'r';
    let last = 0;
    for (const p of pairs) {
      if (p[ot] >= 0) last = p[ot];
      if (p[me] === i) return Math.max(0, Math.min(p[ot] >= 0 ? p[ot] : last, n - 1));
    }
    return Math.max(0, Math.min(i, n - 1));
  }
  // 人が読める説明（追加・削除されたページ）
  function describe(pairs) {
    if (!pairs) return '';
    const add = pairs.filter(p => p.l < 0).map(p => p.r + 1), del = pairs.filter(p => p.r < 0).map(p => p.l + 1);
    const fmt = a => a.length > 6 ? a.slice(0, 6).join('・') + ` ほか ${a.length - 6}` : a.join('・');
    // 調べていないときは「ありません」とは言わない（スキャンでページ数が同じなら、同じページ番号どうしを組にしているだけ）
    if (skipped()) return 'ページ数が同じスキャンのため、同じページ番号どうしを組にしています（ページの入れ替え・差し替えは調べていません）';
    if (st.big) return 'ページ数が多すぎるため、ページの対応は調べず、同じページ番号どうしを組にしています';
    if (!add.length && !del.length) return 'ページの挿入・削除はありません' + (st.visual ? '（見た目で確認）' : '');
    return [add.length ? `右で追加されたページ：${fmt(add)}` : '', del.length ? `左から削除されたページ：${fmt(del)}` : ''].filter(Boolean).join('<br>');
  }
  return { compute, invalidate, ready, skipped, other, describe, enabled, _align: align };
})();
