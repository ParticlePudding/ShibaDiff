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
  async function open(bytes, password) {
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
      const pw = await askText(reason === 2 ? 'パスワードが違います。もう一度入力してください' : 'このPDFはパスワードで保護されています', '', { label: 'パスワード' });
      if (pw == null) { task.destroy(); } else updatePw(pw);
    };
    let doc;
    try { doc = await task.promise; } catch (e) { stop(); throw e; }
    const destroy = doc.destroy.bind(doc);
    doc.destroy = async () => { try { await destroy(); } finally { stop(); } };
    return doc;
  }
  async function text(doc, onProgress) {
    const out = [];
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const tc = await page.getTextContent({ disableNormalization: false });
      out.push(`===== ページ ${i} =====`);
      let line = '', lastY = null, lastX = null;
      for (const it of tc.items) {
        if (typeof it.str !== 'string') continue;
        const y = it.transform[5], x = it.transform[4], h = Math.abs(it.transform[3]) || it.height || 10;
        if (lastY !== null && line && Math.abs(y - lastY) > h * 0.6) { if (line.trim()) out.push(line.replace(/\s+$/, '')); line = ''; }
        else if (lastX !== null && line && x - lastX > h * 1.2 && !/\s$/.test(line) && it.str && !/^\s/.test(it.str)) line += ' ';
        line += normCJK(it.str);
        lastY = y; lastX = x + (it.width || 0);
        if (it.hasEOL) { if (line.trim()) out.push(line.replace(/\s+$/, '')); line = ''; lastY = null; lastX = null; }
      }
      if (line.trim()) out.push(line.replace(/\s+$/, ''));
      page.cleanup();
      if (onProgress) onProgress(i, doc.numPages);
    }
    return out.join('\n');
  }
  async function pages(doc) {
    const res = [];
    for (let i = 1; i <= doc.numPages; i++) {
      const p = await doc.getPage(i);
      const vp = p.getViewport({ scale: 1 });
      const n = i;
      res.push({
        w: vp.width, h: vp.height,
        async draw(canvas, scale) {
          if (canvas._task) { try { canvas._task.cancel(); } catch (e) { } canvas._task = null; }
          const pg = await doc.getPage(n);
          const v = pg.getViewport({ scale });
          canvas.width = Math.max(1, Math.round(v.width)); canvas.height = Math.max(1, Math.round(v.height));
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height);
          const task = pg.render({ canvasContext: ctx, viewport: v, background: 'white' });
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
