/* pdf.js 連携（ライブラリとワーカーはHTML内に埋め込み済み） */
const PDF = (() => {
  let libP = null, cmaps = null;
  function lib() {
    if (!libP) libP = new Promise((res, rej) => {
      const done = () => {
        try {
          const L = window.pdfjsLib;
          const src = document.getElementById('pdfjs-worker').textContent;
          L.GlobalWorkerOptions.workerSrc = URL.createObjectURL(new Blob([src], { type: 'text/javascript' }));
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
    const task = L.getDocument({
      data: bytes.slice(), CMapReaderFactory: CMapFactory, cMapPacked: true, useWorkerFetch: false,
      isEvalSupported: false, password, disableFontFace: false, useSystemFonts: true
    });
    task.onPassword = async (updatePw, reason) => {
      const pw = await askText(reason === 2 ? 'パスワードが違います。もう一度入力してください' : 'このPDFはパスワードで保護されています', '', { label: 'パスワード' });
      if (pw == null) { task.destroy(); } else updatePw(pw);
    };
    return task.promise;
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
