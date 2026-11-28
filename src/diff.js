/* 差分アルゴリズム（Myers + patience分割） */
const Diff = (() => {
  /* Myers O(ND). a,b: array-like of comparable values. returns array of 'e'|'d'|'i' or null if D > maxD */
  function myers(a, b, maxD) {
    const N = a.length, M = b.length, MAX = N + M;
    if (MAX === 0) return [];
    const off = MAX + 1;
    const V = new Int32Array(2 * MAX + 3);
    const trace = [];
    for (let d = 0; d <= MAX; d++) {
      if (d > maxD) return null;
      trace.push(V.slice(off - d - 1, off + d + 2));
      for (let k = -d; k <= d; k += 2) {
        let x;
        if (k === -d || (k !== d && V[off + k - 1] < V[off + k + 1])) x = V[off + k + 1];
        else x = V[off + k - 1] + 1;
        let y = x - k;
        while (x < N && y < M && a[x] === b[y]) { x++; y++; }
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
  /* returns array of [ia|-1, ib|-1] in order */
  function align(dl, il, A, B) {
    const n = dl.length, m = il.length;
    const idx = () => { const r = []; for (let i = 0; i < Math.max(n, m); i++) r.push([i < n ? i : -1, i < m ? i : -1]); return r; };
    if (!n || !m || n === m || n * m > 3600) return idx();
    const ga = dl.map(i => bigrams(A[i])), gb = il.map(j => bigrams(B[j]));
    const sim = []; for (let i = 0; i < n; i++) { sim.push(new Float32Array(m)); for (let j = 0; j < m; j++) sim[i][j] = dice(ga[i], gb[j]); }
    const S = []; for (let i = 0; i <= n; i++) S.push(new Float32Array(m + 1));
    for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++) {
      const s = sim[i - 1][j - 1];
      S[i][j] = Math.max(S[i - 1][j], S[i][j - 1], s >= 0.3 ? S[i - 1][j - 1] + s : -1);
    }
    const res = []; let i = n, j = m;
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && sim[i - 1][j - 1] >= 0.3 && Math.abs(S[i][j] - (S[i - 1][j - 1] + sim[i - 1][j - 1])) < 1e-6) { res.push([i - 1, j - 1]); i--; j--; }
      else if (i > 0 && (j === 0 || S[i][j] === S[i - 1][j])) { res.push([i - 1, -1]); i--; }
      else { res.push([-1, j - 1]); j--; }
    }
    res.reverse();
    // merge adjacent single-sided entries into pairs ([x,-1],[-1,y]) -> [x,y] for compactness
    const out = [];
    for (let k = 0; k < res.length; k++) {
      const cur = res[k], nx = res[k + 1];
      if (nx && cur[1] === -1 && nx[0] === -1 && cur[0] >= 0 && nx[1] >= 0) { out.push([cur[0], nx[1]]); k++; }
      else out.push(cur);
    }
    return out;
  }

  /*
   * rows: {a: lineIdx|-1, b: lineIdx|-1, t: 'e'|'c'|'d'|'i'|'w', blk: blockIdx|-1}
   * blocks: {r0, r1 (row range), a0, a1, b0, b1 (line ranges)}
   */
  function buildRows(ops, A, B, opts = {}) {
    const rows = [], blocks = [];
    let ai = 0, bi = 0, k = 0;
    const isBlank = s => /^\s*$/.test(s);
    while (k < ops.length) {
      if (ops[k] === 'e') { rows.push({ a: ai++, b: bi++, t: 'e', blk: -1 }); k++; continue; }
      const dl = [], il = [];
      const a0 = ai, b0 = bi;
      while (k < ops.length && ops[k] !== 'e') { if (ops[k] === 'd') dl.push(ai++); else il.push(bi++); k++; }
      const ignorable = opts.ignoreBlank && dl.every(i => isBlank(A[i])) && il.every(j => isBlank(B[j]));
      const r0 = rows.length;
      const pairs = ignorable ? (() => { const r = []; for (let i = 0; i < Math.max(dl.length, il.length); i++) r.push([i < dl.length ? i : -1, i < il.length ? i : -1]); return r; })() : align(dl, il, A, B);
      const bIdx = ignorable ? -1 : blocks.length;
      for (const [x, y] of pairs) {
        const a = x >= 0 ? dl[x] : -1, b = y >= 0 ? il[y] : -1;
        rows.push({ a, b, t: ignorable ? 'w' : (a >= 0 && b >= 0 ? 'c' : a >= 0 ? 'd' : 'i'), blk: bIdx });
      }
      if (!ignorable) blocks.push({ r0, r1: rows.length, a0, a1: ai, b0, b1: bi });
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
  function expandNumbers(arr, ranges, points, csv) {
    const nums = numberSpans(arr, csv), out = [];
    for (const [s, e] of ranges) {
      let a = s, b = e;
      for (const n of nums) if (n.st < e && n.en > s) { a = Math.min(a, n.st); b = Math.max(b, n.en); }
      out.push([a, b]);
    }
    const pts = [];
    for (const q of points) { // 数字の中や端で文字が消えた／増えた → その数字全体を変更扱いに
      const n = nums.find(n => q >= n.st && q <= n.en && ((q > n.st && q < n.en) || DIG.test(arr[q - 1] || '') || DIG.test(arr[q] || '')));
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
  function chars(s1, s2, unit = 'char', csv = false) {
    const A = Array.from(s1), B = Array.from(s2);
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
    if (ma > 6000 || mb > 6000 || ma * mb > 6e6) return { a: ma ? [[p, A.length - s]] : [], b: mb ? [[p, B.length - s]] : [], pa: ma ? [] : [p], pb: mb ? [] : [p], A, B, csv };
    const MA = A.slice(p, A.length - s), MB = B.slice(p, B.length - s);
    // 比較単位の列（1文字ずつ、または単語ずつ）とその長さ
    let ua, ub, la, lb;
    if (u === 'word') { const ta = tokenize(MA), tb = tokenize(MB); ua = ta.tok; la = ta.len; ub = tb.tok; lb = tb.len; }
    else { ua = MA; ub = MB; la = null; lb = null; }
    let ops = myers(ua, ub, 1500);
    if (!ops) { ops = []; for (let i = 0; i < ua.length; i++) ops.push('d'); for (let j = 0; j < ub.length; j++) ops.push('i'); }
    // 連続する同じ種類の操作をまとめる（長さは文字数で数える）
    const runs = []; let ka = 0, kb = 0;
    for (const o of ops) {
      const l = runs[runs.length - 1];
      if (o === 'e') { const n = la ? la[ka] : 1; ka++; kb++; if (l && l.t === 'e') l.n += n; else runs.push({ t: 'e', n }); }
      else { let x = l; if (!x || x.t !== 'x') { x = { t: 'x', d: 0, i: 0 }; runs.push(x); } if (o === 'd') { x.d += la ? la[ka] : 1; ka++; } else { x.i += lb ? lb[kb] : 1; kb++; } }
    }
    const ra = [], rb = [], pa = [], pb = [];
    let ia = p, ib = p;
    for (let r = 0; r < runs.length; r++) {
      const run = runs[r];
      if (run.t === 'e') {
        // 変更にはさまれた1文字だけの一致は、変更に含めて読みやすくする
        if (r > 0 && r < runs.length - 1 && run.n <= 1) { addR(ra, ia, ia + run.n); addR(rb, ib, ib + run.n); }
        ia += run.n; ib += run.n;
      } else {
        if (run.d) addR(ra, ia, ia + run.d); else pa.push(ia); // 左には何もない → 右で挿入された位置
        if (run.i) addR(rb, ib, ib + run.i); else pb.push(ib); // 右には何もない → 左で削除された位置
        ia += run.d; ib += run.i;
      }
    }
    const xa = expandNumbers(A, ra, pa, csv), xb = expandNumbers(B, rb, pb, csv);
    return { a: xa.ranges, b: xb.ranges, pa: xa.points, pb: xb.points, A, B, csv };
  }

  /* 数字の変化（差額・増減率）。変わった範囲にかかる数字どうしを順に対応付ける */
  // 量ではない数字（日付・時刻・番号）には差を付けない。％の値は「ポイント」で示す
  const DATE_NEAR = /[年月日時分秒曜\/:：／]/;
  function kindOf(arr, n) {
    if (arr[0] === '=' && arr.slice(0, 5).join('') === '=====') return 'skip';           // 「===== ページ 3 =====」などの区切り
    const b = arr[n.st - 1] || '', b2 = arr[n.st - 2] || '', a = arr[n.en] || '', a2 = arr[n.en + 1] || '';
    if (DATE_NEAR.test(b) || DATE_NEAR.test(a)) return 'skip';                          // 2026/11/27、4月1日、12:30
    if ((b === '-' || b === '－') && /[0-9０-９]/.test(b2)) return 'skip';               // 2026-11-27 の 11・27
    if ((a === '-' || a === '－') && /[0-9０-９]/.test(a2)) return 'skip';
    if (/[A-Za-zＡ-Ｚａ-ｚ_#№]/.test(b) || /^No\.?$/i.test(arr.slice(Math.max(0, n.st - 3), n.st).join('').trim())) return 'skip'; // S12、G4、v3、#12、No.5（記号・番号）
    // 指数表記（1.5E-5 など）の仮数・指数は、それだけでは量にならないので差を付けない（1E-5→2E-5 を「+1」と出さない）
    // （e のあとに、符号と数字が続き、そのあとが英字でないもの。「20E-mail」のような並びは指数表記としない）
    if (/^[eEｅＥ][+\-−]?[0-9０-９]+(?![A-Za-zＡ-Ｚａ-ｚ])/.test(arr.slice(n.en, n.en + 8).join(''))) return 'skip';
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
    if (!na.length || na.length !== nb.length) return [];
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
