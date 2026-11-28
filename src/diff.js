/* 差分アルゴリズム（Myers + patience分割） */
const Diff = (() => {
  /* Myers O(ND). a,b: array-like of comparable values. returns array of 'e'|'d'|'i' or null if D > maxD */
  function myers(a, b, maxD, maxWork = Infinity) {
    const N = a.length, M = b.length, MAX = N + M; let work = 0;
    if (MAX === 0) return [];
    const off = MAX + 1;
    const V = new Int32Array(2 * MAX + 3);
    const trace = [];
    for (let d = 0; d <= MAX; d++) {
      if (d > maxD || (work += d) > maxWork) return null;
      trace.push(V.slice(off - d - 1, off + d + 2));
      for (let k = -d; k <= d; k += 2) {
        let x;
        if (k === -d || (k !== d && V[off + k - 1] < V[off + k + 1])) x = V[off + k + 1];
        else x = V[off + k - 1] + 1;
        let y = x - k;
        while (x < N && y < M && a[x] === b[y]) { x++; y++; work++; }
        V[off + k] = x;
        if (x >= N && y >= M) return backtrack(trace, d, N, M);
      }
    }
    return null;
  }
  function backtrack(trace, D, N, M) {
    const ops = []; let x = N, y = M;
    for (let d = D; d > 0; d--) {
      const V = trace[d], get = k => V[k + d + 1];
      const k = x - y;
      const prevK = (k === -d || (k !== d && get(k - 1) < get(k + 1))) ? k + 1 : k - 1;
      const prevX = get(prevK), prevY = prevX - prevK;
      while (x > prevX && y > prevY) { ops.push('e'); x--; y--; }
      if (x === prevX) { ops.push('i'); y--; } else { ops.push('d'); x--; }
    }
    while (x > 0 && y > 0) { ops.push('e'); x--; y--; }
    return ops.reverse();
  }

  /* unique common elements -> longest increasing subsequence (patience) */
  function anchors(a, a0, a1, b, b0, b1) {
    const cnt = new Map();
    for (let i = a0; i < a1; i++) { const v = a[i]; const c = cnt.get(v); if (c) { c.ca++; } else cnt.set(v, { ca: 1, cb: 0, ai: i, bi: -1 }); }
    for (let j = b0; j < b1; j++) { const c = cnt.get(b[j]); if (c) { c.cb++; c.bi = j; } }
    const cand = [];
    for (let i = a0; i < a1; i++) { const c = cnt.get(a[i]); if (c && c.ca === 1 && c.cb === 1) cand.push([i, c.bi]); }
    if (!cand.length) return [];
    // LIS on bi
    const tails = [], prev = new Int32Array(cand.length).fill(-1), tailIdx = [];
    for (let i = 0; i < cand.length; i++) {
      const v = cand[i][1];
      let lo = 0, hi = tails.length;
      while (lo < hi) { const mid = (lo + hi) >> 1; if (tails[mid] < v) lo = mid + 1; else hi = mid; }
      tails[lo] = v; tailIdx[lo] = i; prev[i] = lo > 0 ? tailIdx[lo - 1] : -1;
    }
    const res = []; let p = tailIdx[tails.length - 1];
    while (p >= 0) { res.push(cand[p]); p = prev[p]; }
    return res.reverse();
  }

  /* full sequence diff with prefix/suffix trimming and patience splitting */
  function seq(a, b) {
    const ops = [];
    const push = (c, n) => { for (let i = 0; i < n; i++) ops.push(c); };
    function solve(a0, a1, b0, b1, depth) {
      let pre = 0; while (a0 + pre < a1 && b0 + pre < b1 && a[a0 + pre] === b[b0 + pre]) pre++;
      let suf = 0; while (a1 - suf > a0 + pre && b1 - suf > b0 + pre && a[a1 - suf - 1] === b[b1 - suf - 1]) suf++;
      push('e', pre);
      const x0 = a0 + pre, x1 = a1 - suf, y0 = b0 + pre, y1 = b1 - suf;
      if (x0 === x1) push('i', y1 - y0);
      else if (y0 === y1) push('d', x1 - x0);
      else {
        let done = false;
        if ((x1 - x0) + (y1 - y0) > 1500 && depth < 200) {
          const an = anchors(a, x0, x1, b, y0, y1);
          if (an.length) {
            let pa = x0, pb = y0;
            for (const [ai, bi] of an) { solve(pa, ai, pb, bi, depth + 1); ops.push('e'); pa = ai + 1; pb = bi + 1; }
            solve(pa, x1, pb, y1, depth + 1);
            done = true;
          }
        }
        if (!done) {
          const sa = a.slice(x0, x1), sb = b.slice(y0, y1);
          const r = myers(sa, sb, 2500);
          if (r) for (const o of r) ops.push(o);
          else { push('d', x1 - x0); push('i', y1 - y0); }
        }
      }
      push('e', suf);
    }
    solve(0, a.length, 0, b.length, 0);
    return ops;
  }

  /* --- similarity for aligning lines inside a change block --- */
  function bigrams(s) {
    s = s.replace(/\s+/g, ' ').trim().slice(0, 400);
    const m = new Map();
    for (let i = 0; i < s.length - 1; i++) { const g = s.substr(i, 2); m.set(g, (m.get(g) || 0) + 1); }
    if (s.length === 1) m.set(s, 1);
    return m;
  }
  function dice(ma, mb) {
    let na = 0, nb = 0, inter = 0;
    for (const v of ma.values()) na += v;
    for (const v of mb.values()) nb += v;
    if (!na || !nb) return 0;
    for (const [g, v] of ma) { const w = mb.get(g); if (w) inter += Math.min(v, w); }
    return 2 * inter / (na + nb);
  }
  /* 変更のまとまりの中で、似た行どうしを組にする（順序は保つ）。返り値：[左の番号|-1, 右の番号|-1] の並び（dl・il の中の番号）。
     - 似ている度合いは 2文字の組（bigram）の重なり（Dice 係数）。SIM_MIN 未満は組にしない
     - 長い行ほど重く数える：短い見出しや空行がたまたま一致するより、長い本文が「ほぼ同じ」であることを優先する
     - 似ている度合いは2乗して数える：「ほぼ同じ」行どうしの組を、「そこそこ似た」行どうしの組より大きく優先する
       （番号だけが違う同じ規則の行が並ぶ設定ファイルで、1行削って番号を詰めたとき、同じ番号の別の規則と組にしないため）
       （請求項を1つ削って番号を繰り上げた文書で、【請求項２】どうしではなく、旧３の本文と新２の本文を組にするため）
     - 大きなまとまり（25万セル超）は、対角線の近く（帯）だけを調べる。さらに大きいものは上から順に
     same(i, j)：比較条件の上で同じ行かどうか（省略時は文字が同じかどうか） */
  const SIM_MIN = 0.3, FULL_CELLS = 250000, BAND = 80, ALIGN_MAX = 20000;
  function align(dl, il, A, B, same) {
    const n = dl.length, m = il.length;
    const idx = () => { const r = []; for (let i = 0; i < Math.max(n, m); i++) r.push([i < n ? i : -1, i < m ? i : -1]); return r; };
    if (!n || !m) return idx();
    if (n === 1 && m === 1) return [[0, 0]]; // 1行の置き換えは、似ていなくても左右に並べる
    if (n + m > ALIGN_MAX) return idx();
    const ga = dl.map(i => bigrams(A[i])), gb = il.map(j => bigrams(B[j]));
    const la = dl.map(i => A[i].trim().length), lb = il.map(j => B[j].trim().length);
    const sim = (i, j) => (same ? same(dl[i], il[j]) : A[dl[i]] === B[il[j]]) || (!la[i] && !lb[j]) ? 1 : dice(ga[i], gb[j]);
    const wt = (i, j) => 1 + Math.sqrt(Math.min(la[i], lb[j], 400));
    const band = n * m > FULL_CELLS ? Math.max(BAND, Math.abs(n - m) + BAND) : Infinity;
    const lo = new Int32Array(n + 1), hi = new Int32Array(n + 1), S = [];
    for (let i = 0; i <= n; i++) {
      const c = band === Infinity ? 0 : Math.round(i * m / n);
      lo[i] = band === Infinity ? 0 : Math.max(0, c - band); hi[i] = band === Infinity ? m : Math.min(m, c + band);
      S.push(new Float64Array(hi[i] - lo[i] + 1));
    }
    const NEG = -1e9, get = (i, j) => (j < lo[i] || j > hi[i]) ? NEG : S[i][j - lo[i]];
    for (let i = 1; i <= n; i++) for (let j = Math.max(1, lo[i]); j <= hi[i]; j++) {
      const s = sim(i - 1, j - 1), d = get(i - 1, j - 1);
      S[i][j - lo[i]] = Math.max(get(i - 1, j), get(i, j - 1), s >= SIM_MIN && d > NEG ? d + s * s * wt(i - 1, j - 1) : NEG);
    }
    const res = []; let i = n, j = m, matched = 0;
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0) {
        const s = sim(i - 1, j - 1), d = get(i - 1, j - 1);
        if (s >= SIM_MIN && d > NEG && Math.abs(get(i, j) - (d + s * s * wt(i - 1, j - 1))) < 1e-9) { res.push([i - 1, j - 1]); i--; j--; matched++; continue; }
      }
      if (i > 0 && (j === 0 || get(i, j) === get(i - 1, j) || get(i, j - 1) <= NEG)) { res.push([i - 1, -1]); i--; }
      else { res.push([-1, j - 1]); j--; }
    }
    // 似た組が1つもなく行数が同じなら、まるごとの書き換え：上から順に左右へ並べる
    if (!matched && n === m) return idx();
    res.reverse();
    // 組にならなかった行の連なり（組と組の間）：左右の行数が同じなら、上から順に左右へ並べる（1行ずつの書き換え）。
    // 違うなら、左のみ → 右のみ の順に出す（どの行がどの行に変わったとは言えない）
    const out = [];
    for (let k = 0; k < res.length;) {
      if (res[k][0] >= 0 && res[k][1] >= 0) { out.push(res[k++]); continue; }
      const L = [], R = [];
      while (k < res.length && (res[k][0] < 0 || res[k][1] < 0)) { if (res[k][0] >= 0) L.push(res[k][0]); else R.push(res[k][1]); k++; }
      if (L.length === R.length) for (let q = 0; q < L.length; q++) out.push([L[q], R[q]]);
      else { for (const x of L) out.push([x, -1]); for (const y of R) out.push([-1, y]); }
    }
    return out;
  }

  /*
   * rows: {a: lineIdx|-1, b: lineIdx|-1, t: 'e'|'c'|'d'|'i'|'w', blk: blockIdx|-1}
   * blocks: {r0, r1 (row range), a0, a1, b0, b1 (line ranges)}
   * opts.same(i, j)：比較条件の上で A[i] と B[j] が同じ行かどうか（省略時は文字が同じかどうか）
   *
   * 変更のまとまりが、弱い同一行（空行や短い見出しなど。合計 WEAK_CHARS 文字以下・WEAK_LINES 行以下）だけをはさんで続くときは、
   * それらを1つの領域として、似た行どうしで対応付けし直す。行の並びの比較（LCS）は「まったく同じ行」を優先して固定するので、
   * 段落を1つ足した・項目を1つ削って番号を繰り上げた、という文書では、空行や見出しだけが一致し、本文が1つずれた相手と組になるため
   */
  const WEAK_CHARS = 16, WEAK_LINES = 3;
  function buildRows(ops, A, B, opts = {}) {
    const rows = [], blocks = [];
    const same = opts.same || ((i, j) => A[i] === B[j]);
    let ai = 0, bi = 0, k = 0;
    const isBlank = s => /^\s*$/.test(s);
    while (k < ops.length) {
      if (ops[k] === 'e') { rows.push({ a: ai++, b: bi++, t: 'e', blk: -1 }); k++; continue; }
      const dl = [], il = [];
      let merged = false;
      for (;;) {
        while (k < ops.length && ops[k] !== 'e') { if (ops[k] === 'd') dl.push(ai++); else il.push(bi++); k++; }
        // この先が「弱い同一行 → また変更」なら、同じ領域に入れる
        let e = k, cnt = 0, chars = 0;
        while (e < ops.length && ops[e] === 'e' && cnt <= WEAK_LINES) { chars += A[ai + cnt].trim().length; cnt++; e++; }
        if (cnt >= 1 && cnt <= WEAK_LINES && chars <= WEAK_CHARS && e < ops.length && ops[e] !== 'e' && dl.length + il.length + cnt < ALIGN_MAX) {
          for (let q = 0; q < cnt; q++) { dl.push(ai++); il.push(bi++); }
          k = e; merged = true; continue;
        }
        break;
      }
      const ignorable = !merged && opts.ignoreBlank && dl.every(i => isBlank(A[i])) && il.every(j => isBlank(B[j]));
      if (ignorable) {
        for (let i = 0; i < Math.max(dl.length, il.length); i++) rows.push({ a: i < dl.length ? dl[i] : -1, b: i < il.length ? il[i] : -1, t: 'w', blk: -1 });
        continue;
      }
      // 領域の中を対応付ける。同じ行どうしの組は「同じ」（まとまりの外）、それ以外をまとまりにする
      let cur = null, ca = dl.length ? dl[0] : ai, cb = il.length ? il[0] : bi;
      const close = () => { if (cur) { cur.r1 = rows.length; cur.a1 = ca; cur.b1 = cb; blocks.push(cur); cur = null; } };
      for (const [x, y] of align(dl, il, A, B, same)) {
        const a = x >= 0 ? dl[x] : -1, b = y >= 0 ? il[y] : -1;
        if (a >= 0 && b >= 0 && same(a, b)) { close(); rows.push({ a, b, t: 'e', blk: -1 }); }
        else {
          if (!cur) cur = { r0: rows.length, r1: 0, a0: ca, a1: 0, b0: cb, b1: 0 };
          rows.push({ a, b, t: a >= 0 && b >= 0 ? 'c' : a >= 0 ? 'd' : 'i', blk: blocks.length });
        }
        if (a >= 0) ca = a + 1; if (b >= 0) cb = b + 1;
      }
      close();
    }
    return { rows, blocks };
  }

  /* character-level diff between two strings -> {a:[[s,e]], b:[[s,e]]} in code point indices */
  /* --- 行内（文字・単語）の差分 --- */
  // 単語の区切り：英数字のまとまり／ひらがな／カタカナ／漢字／全角英数／空白／その他1文字
  const TOKEN_RE = /[A-Za-z0-9_]+|[ぁ-ゟ]+|[゠-ヿㇰ-ㇿｦ-ﾟ]+|[一-鿿㐀-䶿豈-﫿々〆ヶ]+|[０-９Ａ-Ｚａ-ｚ]+|[ \t　]+|[\s\S]/gu;
  function tokenize(cps) { // cps: 文字（コードポイント）の配列 → {tok:[], len:[]}
    const tok = [], len = [];
    for (const m of cps.join('').matchAll(TOKEN_RE)) { tok.push(m[0]); len.push(Array.from(m[0]).length); }
    return { tok, len };
  }
  const wordish = s => { let a = 0, n = 0; for (const c of s) { if (c > ' ') n++; if (/[A-Za-z0-9_]/.test(c)) a++; } return n > 0 && a / n > 0.6; };
  const DIG = /[0-9０-９]/;
  // 数字のまとまり（3桁区切りのカンマは、後ろがちょうど3桁のときだけ数字の一部とみなす。CSVの区切りと区別するため）
  // 符号は、直前が英数字でないときだけ数字の一部とみなす（2026-11-26 や ABC-123 のハイフンを負号と誤認しない）
  const NUM_RE = /(?:(?<![0-9０-９A-Za-zＡ-Ｚａ-ｚ])[-+−])?(?:[0-9０-９]{1,3}(?:[,，][0-9０-９]{3})+(?![0-9０-９])|[0-9０-９]+)(?:[.．][0-9０-９]+)?/gu;
  // CSV では、カンマは区切りなので3桁区切りとみなさない（S12,300,156 を 12,300,156 と読まない）
  const NUM_RE_CSV = /(?:(?<![0-9０-９A-Za-zＡ-Ｚａ-ｚ])[-+−])?[0-9０-９]+(?:[.．][0-9０-９]+)?/gu;
  function numberSpans(arr, csv) {
    const s = arr.join(''), out = []; let cp = 0, last = 0;
    for (const m of s.matchAll(csv ? NUM_RE_CSV : NUM_RE)) {
      cp += Array.from(s.slice(last, m.index)).length; last = m.index;
      const len = Array.from(m[0]).length; out.push({ st: cp, en: cp + len, text: m[0] });
    }
    return out;
  }
  // 変わった範囲が数字にかかっていたら、数字全体（1,200 など）まで広げる
  function expandNumbers(arr, ranges, points, csv, numPts) {
    const nums = numberSpans(arr, csv), out = [];
    for (const [s0, e0] of ranges) {
      // 数字と数字の間に、数字でない文字（見えない文字など）が入った：両側の数字までを1つの変更として示す
      const mid = e0 > s0 && DIG.test(arr[s0 - 1] || '') && DIG.test(arr[e0] || ''), s = mid ? s0 - 1 : s0, e = mid ? e0 + 1 : e0;
      let a = s0, b = e0;
      for (const n of nums) if (n.st < e && n.en > s) { a = Math.min(a, n.st); b = Math.max(b, n.en); }
      out.push([a, b]);
    }
    const pts = [];
    for (const q of points) { // 数字の中や端で文字が消えた／増えた → その数字全体を変更扱いに
      // 数字の途中なら常に、数字の端なら、反対側で増えた／消えた文字が数字のとき（1,200→11,200 など）だけ、数字全体を変更扱いにする。
      // 数字のあとに「X」や見えない文字が足されただけなら、位置の印だけにする（左の数字全体に取り消し線を引くと、数字が消されたように見える）
      const n = nums.find(n => q >= n.st && q <= n.en && ((q > n.st && q < n.en) || (!numPts ? DIG.test(arr[q - 1] || '') || DIG.test(arr[q] || '') : (q === n.en && numPts.tail.has(q)) || (q === n.st && numPts.head.has(q)))));
      if (n) out.push([n.st, n.en]); else pts.push(q);
    }
    out.sort((x, y) => x[0] - y[0]);
    const merged = []; for (const r of out) addR(merged, r[0], r[1]);
    return { ranges: merged, points: pts.filter(q => !merged.some(([s, e]) => q > s && q < e)) };
  }
  /*
   * s1, s2 の違いを返す。unit: 'char' | 'word' | 'auto'
   * 戻り値 {a, b: 変わった範囲[[開始,終了]]（文字＝コードポイント単位）, pa, pb: 反対側で挿入・削除が起きた位置, A, B: 文字配列}
   */
  /* fold：比較条件（全角半角・大文字小文字・空白を無視）に合わせて比べるための関数。文字の配列を受け取り、
     { k: 比べるときの形の配列, idx: それぞれの元の位置（始まり）, end: 元の位置（終わり） } を返す。結果の範囲は、元の文字の位置に直して返す */
  function chars(s1, s2, unit = 'char', csv = false, fold = null) {
    const A0 = Array.from(s1), B0 = Array.from(s2);
    const fa = fold ? fold(A0) : null, fb = fold ? fold(B0) : null;
    const A = fa ? fa.k : A0, B = fb ? fb.k : B0;
    const backR = (ranges, f) => f ? ranges.map(([x, y]) => [f.idx[x], f.end[y - 1]]) : ranges;
    const backQ = (q, f, n) => !f ? q : q < f.idx.length ? f.idx[q] : f.end.length ? f.end[f.end.length - 1] : n;
    const backN = (np, f, n) => !f ? np : { head: new Set([...np.head].map(q => backQ(q, f, n))), tail: new Set([...np.tail].map(q => backQ(q, f, n))) };
    const u = unit === 'auto' ? (wordish(s1 + s2) ? 'word' : 'char') : unit;
    // 先頭・末尾の共通部分を先に除く（長い行でも違う部分だけを示せるように）
    let p = 0; while (p < A.length && p < B.length && A[p] === B[p]) p++;
    let s = 0; while (s < A.length - p && s < B.length - p && A[A.length - 1 - s] === B[B.length - 1 - s]) s++;
    if (u === 'word') { // 単語の途中で切れないよう、共通部分の端を単語の境界まで戻す
      const isW = c => c && /[A-Za-z0-9_]/.test(c);
      while (p > 0 && isW(A[p - 1]) && (isW(A[p]) || isW(B[p]))) p--;
      while (s > 0 && isW(A[A.length - s]) && (isW(A[A.length - s - 1]) || isW(B[B.length - s - 1]))) s--;
    }
    const ma = A.length - s - p, mb = B.length - s - p;
    const whole = () => ({ a: backR(ma ? [[p, A.length - s]] : [], fa), b: backR(mb ? [[p, B.length - s]] : [], fb), pa: (ma ? [] : [p]).map(q => backQ(q, fa, A0.length)), pb: (mb ? [] : [p]).map(q => backQ(q, fb, B0.length)), A: A0, B: B0, csv });
    const MA = A.slice(p, A.length - s), MB = B.slice(p, B.length - s);
    // 比較単位の列（1文字ずつ、または単語ずつ）とその長さ
    let ua, ub, la, lb;
    if (u === 'word') { const ta = tokenize(MA), tb = tokenize(MB); ua = ta.tok; la = ta.len; ub = tb.tok; lb = tb.len; }
    else { ua = MA; ub = MB; la = null; lb = null; }
    // 長い行（1行だけの JSON・minify したコードなど）でも、違いが少なければ変わった所だけを示す。
    // 違いが多すぎて手間がかかりすぎるときは、最初の違いから最後の違いまでをまとめて示す
    const big = ma > 6000 || mb > 6000;
    let ops = myers(ua, ub, 1500, big ? 2e7 : Infinity);
    if (!ops) { if (big) return whole(); ops = []; for (let i = 0; i < ua.length; i++) ops.push('d'); for (let j = 0; j < ub.length; j++) ops.push('i'); }
    // 連続する同じ種類の操作をまとめる（長さは文字数で数える）
    const runs = []; let ka = 0, kb = 0;
    for (const o of ops) {
      const l = runs[runs.length - 1];
      if (o === 'e') { const n = la ? la[ka] : 1; ka++; kb++; if (l && l.t === 'e') l.n += n; else runs.push({ t: 'e', n }); }
      else { let x = l; if (!x || x.t !== 'x') { x = { t: 'x', d: 0, i: 0 }; runs.push(x); } if (o === 'd') { x.d += la ? la[ka] : 1; ka++; } else { x.i += lb ? lb[kb] : 1; kb++; } }
    }
    // 反対側で増えた／消えた文字が、数字に続く形かどうか（tail：数字や小数点・桁区切りで始まる＝数字の後ろに続く。head：数字や符号で終わる＝数字の前に付く）
    const npa = { head: new Set(), tail: new Set() }, npb = { head: new Set(), tail: new Set() }, ra = [], rb = [], pa = [], pb = [];
    const isW = c => /[A-Za-z0-9_]/.test(c);
    const mark = (np, q, arr, x, y) => { if (/[0-9０-９.．,，]/.test(arr[x] || '')) np.tail.add(q); if (/[0-9０-９+\-−]/.test(arr[y - 1] || '')) np.head.add(q); };
    let ia = p, ib = p;
    for (let r = 0; r < runs.length; r++) {
      const run = runs[r];
      if (run.t === 'e') {
        // 変更にはさまれた1文字だけの一致は、変更に含めて読みやすくする
        if (r > 0 && r < runs.length - 1 && run.n <= 1) { addR(ra, ia, ia + run.n); addR(rb, ib, ib + run.n); }
        ia += run.n; ib += run.n;
      } else {
        let x = ia, y = ib, d = run.d, n = run.i;
        if (u === 'word' && d && n) {
          // 語の単位で比べたときの置き換え：日本語は「管理者」と「管理者及」のように漢字の連なりが1語になるので、
          // 先頭・末尾の同じ文字を除いて、変わった文字だけを示す（英数字の語は、語の途中では切らない）
          while (d && n && A[x] === B[y] && !isW(A[x])) { x++; y++; d--; n--; }
          while (d && n && A[x + d - 1] === B[y + n - 1] && !isW(A[x + d - 1])) { d--; n--; }
        }
        if (d) addR(ra, x, x + d); else if (n) { pa.push(x); mark(npa, x, B, y, y + n); } // 左には何もない → 右で挿入された位置
        if (n) addR(rb, y, y + n); else if (d) { pb.push(y); mark(npb, y, A, x, x + d); } // 右には何もない → 左で削除された位置
        ia += run.d; ib += run.i;
      }
    }
    const xa = expandNumbers(A0, backR(ra, fa), pa.map(q => backQ(q, fa, A0.length)), csv, backN(npa, fa, A0.length));
    const xb = expandNumbers(B0, backR(rb, fb), pb.map(q => backQ(q, fb, B0.length)), csv, backN(npb, fb, B0.length));
    return { a: xa.ranges, b: xb.ranges, pa: xa.points, pb: xb.points, A: A0, B: B0, csv };
  }

  /* 数字の変化（差額・増減率）。変わった範囲にかかる数字どうしを順に対応付ける */
  // 量ではない数字（日付・時刻・番号）には差を付けない。％の値は「ポイント」で示す
  const DATE_NEAR = /[年月日時分秒曜\/:：／]/;
  function kindOf(arr, n) {
    if (arr[0] === '=' && arr.slice(0, 5).join('') === '=====') return 'skip';           // 「===== ページ 3 =====」などの区切り
    const b = arr[n.st - 1] || '', b2 = arr[n.st - 2] || '', a = arr[n.en] || '', a2 = arr[n.en + 1] || '';
    // 「年1.475％」のように後ろが ％ なら、前に「年」があっても日付ではなく割合
    if (/[%％]/.test(a) && !/[\/:：／]/.test(b)) return 'pct';
    if (DATE_NEAR.test(b) || DATE_NEAR.test(a)) return 'skip';                          // 2026/11/27、4月1日、12:30
    // 量ではない番号には差を付けない（「+1 / +33.3%」と出しても意味がなく、読み違える）
    const pre = arr.slice(Math.max(0, n.st - 12), n.st).join(''), post = arr.slice(n.en, n.en + 6).join('');
    if (/[第【［\[]\s*$/.test(pre) || /^\s*[】］\]]/.test(post) || /(請求項|別表|様式|Rev\.?|Ver\.?|ver\.?|版)\s*$/.test(pre)) return 'skip';   // 第3条・第4版・【０００６】・請求項１・Rev.2
    if (/^\s*(条|項(?!目)|号|章|節|編|版)/.test(post)) return 'skip';                                         // 3条、2項、5号、4版（条文・版の番号）
    if ((b === '-' || b === '‐' || b === '－') && /[A-Za-zＡ-Ｚａ-ｚ]/.test(b2)) return 'skip';                // TW-21、IT-000123（型式・管理番号）
    if (b === '.' && /[A-Za-z]/.test(b2)) return 'skip';                                                      // Rev.2、v.3
    if ((b === '.' && /[0-9]/.test(b2) && /\./.test(n.text)) || (a === '.' && /[0-9]/.test(a2)) || /[0-9０-９]+[.．][0-9０-９]+[.．]$/.test(pre)) return 'skip';  // 2.4.0・10.10.200.41・2026.11.20（版番号・IP アドレス・日付）
    if (/^[A-Za-z]+[0-9]/.test(post)) return 'skip';                                                           // 24H2（数字・英字・数字と続く名前）
    if (/^(19|20)[0-9]{2}[.．](0[1-9]|1[0-2])$/.test(n.text)) return 'skip';                                    // 2024.06（年.月）
    if (/(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*$/.test(pre)) return 'skip';             // Nov 14
    if (/^\s*[\/／]\s*[0-9０-９]/.test(post) || /[0-9０-９]\s*[\/／]\s*$/.test(pre)) return 'skip';              // 7 / 10（ページ番号・分数）
    if (/^\s*[-－–]\s*$/.test(post) && /^\s*[-－–]\s*$/.test(arr.slice(0, n.st).join(''))) return 'skip';      // - 3 -（ページ番号だけの行）
    { let q = n.st - 1, url = false; for (let c = 0; q >= 0 && c < 300 && !/\s/.test(arr[q]); q--, c++) if (arr[q] === '/' && arr[q - 1] === '/' && arr[q - 2] === ':') { url = true; break; } if (url) return 'skip'; } // URL の中
    if ((b === '-' || b === '－') && /[0-9０-９]/.test(b2)) return 'skip';               // 2026-11-27 の 11・27
    if ((a === '-' || a === '－') && /[0-9０-９]/.test(a2)) return 'skip';
    if (/[A-Za-zＡ-Ｚａ-ｚ_#№]/.test(b) || /^No\.?$/i.test(arr.slice(Math.max(0, n.st - 3), n.st).join('').trim())) return 'skip'; // S12、G4、v3、#12、No.5（記号・番号）
    // 指数表記（1.5E-5 など）の仮数・指数は、それだけでは量にならないので差を付けない（1E-5→2E-5 を「+1」と出さない）
    // （e のあとに、符号と数字が続き、そのあとが英字でないもの。「20E-mail」のような並びは指数表記としない）
    if (/^[eEｅＥ][+\-−]?[0-9０-９]+(?![A-Za-zＡ-Ｚａ-ｚ])/.test(arr.slice(n.en, n.en + 8).join(''))) return 'skip';
    if (/[0-9０-９][eEｅＥ][+\-−]?$/.test(arr.slice(Math.max(0, n.st - 3), n.st).join(''))) return 'skip';               // 指数部（1.0e+22 の 22）
    if (/[%％]/.test(a)) return 'pct';
    return 'num';
  }
  function numbersIn(arr, ranges, csv) {
    return numberSpans(arr, csv).filter(n => ranges.some(([a, b]) => a < n.en && b > n.st)).map(n => {
      const t = n.text.normalize('NFKC').replace(/[,，]/g, '').replace('−', '-');
      return { st: n.st, en: n.en, v: parseFloat(t), t, dec: (t.split('.')[1] || '').length, kind: kindOf(arr, n) };
    }).filter(n => isFinite(n.v));
  }
  // 数の文字列（-1234.5）を、小数 dec 桁にそろえた整数（BigInt）にする。差を正確に出すため：
  // parseFloat は 15〜16 桁を超えると丸めるので、桁の多い数（9,007,199,254,740,993 など）の差がずれる
  function scaled(t, dec) {
    const neg = t[0] === '-', [i, f = ''] = t.replace(/^[+-]/, '').split('.');
    const b = BigInt((i || '0') + f.padEnd(dec, '0'));
    return neg ? -b : b;
  }
  function fmtScaled(b, dec) { // 絶対値を、3桁区切り・小数 dec 桁で
    const s = (b < 0n ? -b : b).toString().padStart(dec + 1, '0'), i = s.slice(0, s.length - dec);
    return i.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (dec ? '.' + s.slice(-dec) : '');
  }
  function numberDeltas(cd) {
    const na = numbersIn(cd.A, cd.a, cd.csv), nb = numbersIn(cd.B, cd.b, cd.csv);
    // 1行に数字の変更が多すぎるとき（1行だけのデータなど）は付けない：札で右だけ行が長くなり、左右の同じ場所が並ばなくなる
    if (!na.length || na.length !== nb.length || nb.length > 60) return [];
    const res = [];
    nb.forEach((n, k) => {
      const o = na[k];
      if (n.kind === 'skip' || o.kind === 'skip') return;
      const dec = Math.max(n.dec, o.dec), d = scaled(n.t, dec) - scaled(o.t, dec); if (d === 0n) return;
      const up = d > 0n;
      let t = (up ? '+' : '−') + fmtScaled(d, dec);
      if (n.kind === 'pct' && o.kind === 'pct') t += 'ポイント';
      // 増減率は、元の値が正のときだけ出す。元が 0 のときは計算できず、元が負のとき（−100 → 100 など）は
      // 「+200%」のような、増えたのか減ったのか読み違える数字になるので、差だけを出す
      else if (o.v > 0) {
        // 0.05% に満たない変化を「0.0%」と出すと、変わっていないように読めるので「0.1%未満」とする
        const r = Math.abs((n.v - o.v) / o.v * 100);
        t += ` / ${up ? '+' : '−'}${r < 0.05 ? '0.1%未満' : r.toFixed(1) + '%'}`;
      }
      res.push({ at: n.en, text: t });
    });
    return res;
  }
  function addR(arr, s, e) {
    if (e <= s) return;
    const last = arr[arr.length - 1];
    if (last && last[1] >= s) last[1] = Math.max(last[1], e); else arr.push([s, e]);
  }

  return { myers, seq, buildRows, chars, numberDeltas };
})();
