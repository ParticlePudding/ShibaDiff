/* ページ表示用の「ページ」抽象。PDF以外（テキスト・Office・画像）もページとして扱う */
const Pages = (() => {
  const PW = 595, PH = 842, M = 40, LH = 13, FS = 10;
  const FONT = `${FS}px "BIZ UDGothic","MS Gothic","Noto Sans Mono CJK JP",monospace`;
  let mctx = null;
  function measure() { if (!mctx) { mctx = document.createElement('canvas').getContext('2d'); } mctx.font = FONT; return mctx; }

  function fromText(lines, title) {
    const ctx = measure(), maxW = PW - M * 2 - 6;
    const vis = []; // [lineNo|null, text]
    lines.forEach((ln, i) => {
      const t = ln.replace(/\t/g, '    ');
      if (!t) { vis.push([i + 1, '']); return; }
      if (t.length < 40 || ctx.measureText(t).width <= maxW) { vis.push([i + 1, t]); return; }
      let cur = '', first = true;
      for (const ch of t) {
        if (ctx.measureText(cur + ch).width > maxW && cur) { vis.push([first ? i + 1 : null, cur]); cur = ''; first = false; }
        cur += ch;
      }
      vis.push([first ? i + 1 : null, cur]);
    });
    const per = Math.floor((PH - M * 2) / LH);
    const pages = [];
    const total = Math.max(1, Math.ceil(vis.length / per));
    for (let p = 0; p < total; p++) {
      const chunk = vis.slice(p * per, (p + 1) * per);
      pages.push({
        w: PW, h: PH,
        async draw(canvas, scale) {
          canvas.width = Math.round(PW * scale); canvas.height = Math.round(PH * scale);
          const c = canvas.getContext('2d');
          c.setTransform(scale, 0, 0, scale, 0, 0);
          c.fillStyle = '#fff'; c.fillRect(0, 0, PW, PH);
          c.textBaseline = 'top';
          chunk.forEach(([no, t], i) => {
            const y = M + i * LH;
            if (no != null) { c.font = `7px sans-serif`; c.fillStyle = '#a0a8b2'; c.textAlign = 'right'; c.fillText(String(no), M - 6, y + 2); }
            c.font = FONT; c.fillStyle = '#111'; c.textAlign = 'left'; c.fillText(t, M, y);
          });
          c.font = '8px sans-serif'; c.fillStyle = '#9aa3ad'; c.textAlign = 'center'; void title; void total;
          c.fillText(`- ${p + 1} -`, PW / 2, PH - 24);
          c.setTransform(1, 0, 0, 1, 0, 0); // 後で注釈を重ねるときに拡大が残らないよう元に戻す
          return true;
        }
      });
    }
    return pages;
  }

  async function fromImage(bytes, mime) {
    const blob = new Blob([bytes], { type: mime || '' });
    const bmp = await createImageBitmap(blob);
    // treat 96dpi pixels as 72dpi points
    const s = 0.75;
    return [{
      w: bmp.width * s, h: bmp.height * s, bitmap: bmp,
      async draw(canvas, scale) {
        canvas.width = Math.max(1, Math.round(bmp.width * s * scale)); canvas.height = Math.max(1, Math.round(bmp.height * s * scale));
        const c = canvas.getContext('2d');
        c.fillStyle = '#fff'; c.fillRect(0, 0, canvas.width, canvas.height);
        c.imageSmoothingQuality = 'high';
        c.drawImage(bmp, 0, 0, canvas.width, canvas.height);
        return true;
      }
    }];
  }
  return { fromText, fromImage };
})();
