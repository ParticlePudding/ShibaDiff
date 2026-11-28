/* pdf.js 連携（ライブラリとワーカーはHTML内に埋め込み済み） */
const PDF = (() => {
  let libP = null, cmaps = null, classicUrl = null;
  function lib() {
    if (!libP) libP = new Promise((res, rej) => {
      const done = () => {
        try {
          const L = window.pdfjsLib;
          const src = document.getElementById('pdfjs-worker').textContent;
          const url = URL.createObjectURL(new Blob([src], { type: 'text/javascript' }));
          L.GlobalWorkerOptions.workerSrc = url;
          // ワーカーはこちらで作って渡す。pdf.js に任せると、file:// で開いたとき（オリジンが null）に
          // ワーカーの起動に失敗し、メインスレッドで処理する「fake worker」になって画面が固まるため。
          // オリジンが null だとモジュール形式のワーカーは起動できないので、末尾の export を外して通常のスクリプトにする
          // （ワーカー側は、ワーカー内で読み込まれると自動で待ち受けを始める）
          const classic = src.replace(/export\s*\{\s*([\w$]+)\s+as\s+WorkerMessageHandler\s*\}\s*;?\s*$/, 'self.pdfjsWorker = { WorkerMessageHandler: $1 };');
          // ワーカーは文書ごとに作る（左右の文書の読み込み・描画を並行して進められるように）。作れなければ pdf.js に任せる
          if (classic !== src) classicUrl = URL.createObjectURL(new Blob([classic], { type: 'text/javascript' }));
          res(L);
        } catch (e) { rej(e); }
      };
      if (window.pdfjsLib) done();
      else {
        window.addEventListener('pdfjs-ready', done, { once: true });
        setTimeout(() => { if (!window.pdfjsLib) rej(new Error('PDFライブラリを読み込めませんでした（ブラウザが古い可能性があります）')); }, 20000);
      }
    });
    return libP;
  }
  class CMapFactory {
    constructor() { }
    async fetch({ name }) {
      if (!cmaps) cmaps = JSON.parse(document.getElementById('cmaps').textContent);
      const b = cmaps[name];
      if (!b) throw new Error('CMap 未収録: ' + name);
      return { cMapData: b64ToBytes(b), isCompressed: true };
    }
  }
  async function open(bytes, password, name) {
    const L = await lib();
    // 文書ごとのワーカー（文書を閉じたら終了させる）
    let raw = null, worker = null;
    if (classicUrl) {
      try { raw = new Worker(classicUrl); worker = new L.PDFWorker({ port: raw }); }
      catch (e) { console.warn('PDFのワーカーを起動できません', e); if (raw) raw.terminate(); raw = worker = null; }
    }
    const stop = () => { try { if (worker) worker.destroy(); } catch (e) { } if (raw) raw.terminate(); raw = worker = null; };
    const task = L.getDocument({
      data: bytes.slice(), CMapReaderFactory: CMapFactory, cMapPacked: true, useWorkerFetch: false,
      isEvalSupported: false, password, disableFontFace: false, useSystemFonts: true, ...(worker ? { worker } : {})
    });
    task.onPassword = async (updatePw, reason) => {
      const nm = name ? `「${name}」` : 'このPDF';
      const pw = await askPassword(reason === 2 ? `${nm}のパスワードが違います。もう一度入力してください` : `${nm}はパスワードで保護されています`);
      if (pw == null) { task.destroy(); } else updatePw(pw);
    };
    let doc;
    try { doc = await task.promise; } catch (e) { stop(); throw e; }
    const destroy = doc.destroy.bind(doc);
    doc.destroy = async () => { try { await destroy(); } finally { stop(); } };
    return doc;
  }
  const SUP = { 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹', '+': '⁺', '-': '⁻', '−': '⁻', '(': '⁽', ')': '⁾', n: 'ⁿ', ' ': ' ' };
  const SUB = { 0: '₀', 1: '₁', 2: '₂', 3: '₃', 4: '₄', 5: '₅', 6: '₆', 7: '₇', 8: '₈', 9: '₉', '+': '₊', '-': '₋', '−': '₋', '(': '₍', ')': '₎', x: 'ₓ', ' ': ' ' };
  async function text(doc, onProgress) {
    const out = [];
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      /* disableNormalization: pdf.js は既定で、取り出した文字に NFKC をかける（µ U+00B5 → μ U+03BC、合字 ﬁ → fi、
         ノーブレークスペース → 空白 など）。比較ツールでは、元のファイルにある文字をそのまま見せないと、
         「µ を μ に直した」という改訂が差分に出ない（薬事・計測の文書では見落としになる）。そこで正規化を切る */
      const tc = await page.getTextContent({ disableNormalization: true });
      out.push(`===== ページ ${i} =====`);
      // 行の判定は、その行の基準（本文の大きさの文字の位置 baseY・高さ baseH）で行う。上付き・下付き（小さい文字が上下に少しずれる）は
      // 同じ行に入れる。前の文字との差だけで見ると、上付き文字のところで行が割れ、変わっていない文が別の行になって差分に出る
      let line = '', baseY = null, baseH = 0, lastX = null;
      const flush = () => { if (line.trim()) out.push(line.replace(/\s+$/, '')); line = ''; baseY = null; baseH = 0; lastX = null; };
      for (const it of tc.items) {
        if (typeof it.str !== 'string') continue;
        const y = it.transform[5], x = it.transform[4], h = Math.abs(it.transform[3]) || it.height || 10;
        if (baseY !== null && line && Math.abs(y - baseY) > Math.max(h, baseH) * 0.6) flush();
        else if (lastX !== null && line && x - lastX > h * 1.2 && !/\s$/.test(line) && it.str && !/^\s/.test(it.str)) line += ' ';
        let str = normCJK(it.str);
        if (baseY !== null && line && h < baseH * 0.85 && str.trim()) {
          // 本文より小さく、上か下にずれている：上付き（10⁵、Cu²⁺）・下付き（H₂O）。数字と符号だけなら、その文字に置き換える
          // （そのままだと 10⁵ が「105」になり、105→106 のような別の数に読める）
          const dy = y - baseY, map = dy > baseH * 0.18 ? SUP : dy < -baseH * 0.06 ? SUB : null;
          if (map && [...str].every(c => map[c] !== undefined)) str = [...str].map(c => map[c]).join('');
        }
        line += str;
        if (baseY === null || h >= baseH * 0.95) { baseY = y; baseH = h; }
        lastX = x + (it.width || 0);
        if (it.hasEOL) flush();
      }
      if (line.trim()) out.push(line.replace(/\s+$/, ''));
      page.cleanup();
      if (onProgress) onProgress(i, doc.numPages);
    }
    return out.join('\n');
  }
  async function pages(doc) {
    const res = [];
    const ready = new Set(); // 描画の命令と部品（フォント・画像）がそろっているページ（下の exact の説明を参照）
    for (let i = 1; i <= doc.numPages; i++) {
      const p = await doc.getPage(i);
      const vp = p.getViewport({ scale: 1 });
      const n = i;
      res.push({
        w: vp.width, h: vp.height,
        /* opt.exact：比較に使う描画。描きはじめたら、ブラウザに処理を返さずに最後まで描く。
           Chrome の canvas は、描画の途中で処理が一度ブラウザに戻ると、そのあとに描く図形の縁（アンチエイリアス）がわずかに変わる
           （切り抜き＝クリップの掛かり方が変わるため）。pdf.js は、長い描画では requestAnimationFrame を待ち、フォントや命令が
           届いていなければ届くまで待つので、同じページでも描くたびに画素が違うことがある。文字をパスで描く PDF（Chrome の印刷で
           作った PDF の Type3 フォントなど）で目立ち、重ね合わせで「変わっていない文字に枠が出る・件数が操作のたびに変わる」原因になる。
           そこで比較用の描画は、(1) 先にごく小さく1回描いて、そのページの命令と部品をそろえておき（初回だけ）、
           (2) requestAnimationFrame を待たずに描く（build.py が pdf.js の該当箇所を globalThis.__sdExact で切り替えられるようにしている）。
           画面に出すだけの描画（ページ表示）は、これまでどおり途中で処理を返す（大きなページでも操作が止まらないように） */
        async draw(canvas, scale, opt) {
          if (canvas._task) { try { canvas._task.cancel(); } catch (e) { } canvas._task = null; }
          const pg = await doc.getPage(n);
          if (opt && opt.exact && !ready.has(n)) {
            const v0 = pg.getViewport({ scale: 0.02 }), c0 = document.createElement('canvas');
            c0.width = Math.max(1, Math.round(v0.width)); c0.height = Math.max(1, Math.round(v0.height));
            try { await pg.render({ canvasContext: c0.getContext('2d'), viewport: v0 }).promise; ready.add(n); } catch (e) { /* 本番の描画で同じ失敗が出る */ }
          }
          const v = pg.getViewport({ scale });
          canvas.width = Math.max(1, Math.round(v.width)); canvas.height = Math.max(1, Math.round(v.height));
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height);
          let task;
          globalThis.__sdExact = !!(opt && opt.exact);
          try { task = pg.render({ canvasContext: ctx, viewport: v, background: 'white' }); } finally { globalThis.__sdExact = false; }
          canvas._task = task;
          try { await task.promise; } catch (e) { if (e && e.name === 'RenderingCancelledException') return false; throw e; }
          finally { if (canvas._task === task) canvas._task = null; }
          return true;
        }
      });
    }
    return res;
  }
  return { open, text, pages, lib };
})();
