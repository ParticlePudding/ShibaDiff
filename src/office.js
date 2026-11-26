/* Office (docx/xlsx/pptx) テキスト抽出。ZIPは自前で読み、展開はブラウザ標準の DecompressionStream を使用 */
const Zip = (() => {
  // 展開後の大きさの上限（ZIP爆弾対策）。ヘッダの値は偽装できるので、実際に展開したバイト数で判定する
  const LIMIT = { entry: 100 * 1024 * 1024, total: 300 * 1024 * 1024, ratio: 200, ratioFrom: 16 * 1024 * 1024 };
  const TOO_BIG = () => new Error('展開後のサイズが大きすぎるため読み込みを中止しました（ZIPの内容が異常に大きいか、細工されたファイルの可能性があります）');
  async function inflateRaw(data, budget) {
    if (typeof DecompressionStream === 'undefined') throw new Error('このブラウザはZIP展開に対応していません');
    const reader = new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader();
    const chunks = []; let n = 0;
    for (; ;) {
      const { done, value } = await reader.read();
      if (done) break;
      n += value.length;
      if (n > LIMIT.entry || n > budget.left || (n > LIMIT.ratioFrom && n > data.length * LIMIT.ratio)) {
        try { await reader.cancel(); } catch (e) { }
        throw TOO_BIG();
      }
      chunks.push(value);
    }
    budget.left -= n;
    const out = new Uint8Array(n); let o = 0;
    for (const c of chunks) { out.set(c, o); o += c.length; }
    return out;
  }
  function open(bytes) {
    const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let eocd = -1;
    for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 65557); i--) {
      if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('ZIP形式ではありません');
    const count = dv.getUint16(eocd + 10, true);
    let p = dv.getUint32(eocd + 16, true);
    const entries = new Map();
    const td = new TextDecoder('utf-8');
    for (let n = 0; n < count; n++) {
      if (p + 46 > bytes.length) throw new Error('ZIPの構造が壊れています');
      if (dv.getUint32(p, true) !== 0x02014b50) break;
      const method = dv.getUint16(p + 10, true);
      const csize = dv.getUint32(p + 20, true), usize = dv.getUint32(p + 24, true);
      const nameLen = dv.getUint16(p + 28, true), extraLen = dv.getUint16(p + 30, true), cmtLen = dv.getUint16(p + 32, true);
      const lho = dv.getUint32(p + 42, true);
      const name = td.decode(bytes.subarray(p + 46, p + 46 + nameLen));
      entries.set(name, { method, csize, usize, lho });
      p += 46 + nameLen + extraLen + cmtLen;
    }
    const budget = { left: LIMIT.total };
    return {
      names: () => Array.from(entries.keys()),
      has: n => entries.has(n),
      async read(name) {
        const e = entries.get(name); if (!e) return null;
        if (e.usize > LIMIT.entry || e.usize > budget.left) throw TOO_BIG();
        const l = e.lho;
        if (l + 30 > bytes.length || dv.getUint32(l, true) !== 0x04034b50) throw new Error('ZIPの構造が壊れています');
        const nl = dv.getUint16(l + 26, true), xl = dv.getUint16(l + 28, true);
        const start = l + 30 + nl + xl;
        const data = bytes.subarray(start, start + e.csize);
        if (e.method === 0) { budget.left -= data.length; return data; }
        if (e.method === 8) return inflateRaw(data, budget);
        throw new Error('未対応の圧縮形式: ' + e.method);
      },
      async text(name) { const d = await this.read(name); return d ? new TextDecoder('utf-8').decode(d) : null; }
    };
  }
  return { open };
})();

const Office = (() => {
  const parseXml = s => new DOMParser().parseFromString(s, 'application/xml');
  const kids = (el, ln) => Array.from(el.children).filter(c => c.localName === ln);
  const all = (el, ln) => Array.from(el.getElementsByTagNameNS('*', ln));

  function relsMap(xml) {
    const m = new Map(); if (!xml) return m;
    for (const r of all(parseXml(xml), 'Relationship')) m.set(r.getAttribute('Id'), r.getAttribute('Target'));
    return m;
  }
  function resolve(base, target) {
    if (target.startsWith('/')) return target.slice(1);
    const parts = base.split('/'); parts.pop();
    for (const seg of target.split('/')) { if (seg === '..') parts.pop(); else if (seg !== '.') parts.push(seg); }
    return parts.join('/');
  }

  /* ---- Word ---- */
  function wParaText(p) {
    let s = '';
    const walk = el => {
      for (const c of el.children) {
        const ln = c.localName;
        if (ln === 't') s += c.textContent;
        else if (ln === 'tab') s += '\t';
        else if (ln === 'br' || ln === 'cr') s += '\n';
        else if (ln === 'delText' || ln === 'instrText' || ln === 'del' || ln === 'rPr' || ln === 'pPr') continue;
        else if (ln === 'noBreakHyphen') s += '-';
        else walk(c);
      }
    };
    walk(p);
    return s;
  }
  function wListPrefix(p) {
    const ppr = kids(p, 'pPr')[0]; if (!ppr) return '';
    const num = kids(ppr, 'numPr')[0]; if (!num) return '';
    const lvl = kids(num, 'ilvl')[0];
    const n = lvl ? parseInt(lvl.getAttribute('w:val') || lvl.getAttributeNS(lvl.namespaceURI, 'val') || '0', 10) : 0;
    return '  '.repeat(n) + '・';
  }
  function wBlock(el, out) {
    for (const c of el.children) {
      if (c.localName === 'p') out.push(...(wListPrefix(c) + wParaText(c)).split('\n'));
      else if (c.localName === 'tbl') {
        out.push('┌─ 表 ─');
        for (const tr of kids(c, 'tr')) {
          const cells = kids(tr, 'tc').map(tc => { const o = []; wBlock(tc, o); return o.join(' / ').trim(); });
          out.push('│ ' + cells.join(' │ '));
        }
        out.push('└─');
      } else if (c.localName === 'sdt') { const ct = kids(c, 'sdtContent')[0]; if (ct) wBlock(ct, out); }
      else if (c.localName === 'customXml' || c.localName === 'ins' || c.localName === 'smartTag') wBlock(c, out);
    }
  }
  async function docx(zip) {
    const out = [];
    const xml = await zip.text('word/document.xml');
    if (!xml) throw new Error('word/document.xml が見つかりません');
    const body = all(parseXml(xml), 'body')[0];
    if (body) wBlock(body, out);
    for (const extra of [['word/footnotes.xml', '脚注'], ['word/endnotes.xml', '文末脚注'], ['word/comments.xml', 'コメント']]) {
      const x = await zip.text(extra[0]); if (!x) continue;
      const lines = []; for (const p of all(parseXml(x), 'p')) { const t = wParaText(p); if (t.trim()) lines.push(t); }
      if (lines.length) { out.push('', `===== ${extra[1]} =====`, ...lines); }
    }
    return out.join('\n');
  }

  /* ---- Excel ---- */
  function colIdx(ref) { let n = 0; for (const ch of ref) { const c = ch.charCodeAt(0); if (c < 65 || c > 90) break; n = n * 26 + (c - 64); } return n - 1; }
  async function xlsx(zip) {
    const ss = [];
    const ssx = await zip.text('xl/sharedStrings.xml');
    if (ssx) for (const si of all(parseXml(ssx), 'si')) ss.push(all(si, 't').filter(t => t.parentNode.localName !== 'rPh').map(t => t.textContent).join(''));
    // 日付の表示形式のセルを判定する（日付は内部では通し番号で保存されている）
    const dateStyle = [];
    const stx = await zip.text('xl/styles.xml');
    if (stx) {
      const sd = parseXml(stx), custom = new Map();
      for (const nf of all(sd, 'numFmt')) custom.set(+nf.getAttribute('numFmtId'), nf.getAttribute('formatCode') || '');
      const isDateFmt = id => {
        if ((id >= 14 && id <= 22) || (id >= 27 && id <= 36) || (id >= 45 && id <= 47) || (id >= 50 && id <= 58)) return true;
        const code = custom.get(id); if (!code) return false;
        const c = code.replace(/"[^"]*"|\[[^\]]*\]|\\./g, '');
        return /[ymdhs]/i.test(c) && !/^[#0.,%E+\-\s]*$/i.test(c);
      };
      const xfs = all(sd, 'cellXfs')[0];
      if (xfs) kids(xfs, 'xf').forEach((xf, i) => { dateStyle[i] = isDateFmt(+xf.getAttribute('numFmtId')); });
    }
    const serialToDate = v => {
      const n = parseFloat(v); if (!isFinite(n)) return v;
      const ms = Math.round((n - 25569) * 86400000), d = new Date(ms), p = x => String(x).padStart(2, '0');
      const date = `${d.getUTCFullYear()}/${p(d.getUTCMonth() + 1)}/${p(d.getUTCDate())}`;
      const frac = n - Math.floor(n);
      return frac > 1e-6 ? `${n >= 1 ? date + ' ' : ''}${p(d.getUTCHours())}:${p(d.getUTCMinutes())}` : date;
    };
    const wb = parseXml(await zip.text('xl/workbook.xml'));
    const rels = relsMap(await zip.text('xl/_rels/workbook.xml.rels'));
    const out = [];
    for (const sh of all(wb, 'sheet')) {
      const name = sh.getAttribute('name');
      const rid = sh.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships', 'id') || sh.getAttribute('r:id');
      const target = rels.get(rid); if (!target) continue;
      const path = resolve('xl/workbook.xml', target);
      const sx = await zip.text(path); if (!sx) continue;
      out.push(`===== シート: ${name} =====`);
      const doc = parseXml(sx);
      for (const row of all(doc, 'row')) {
        const cells = [];
        for (const c of kids(row, 'c')) {
          const r = c.getAttribute('r'); const ci = r ? colIdx(r) : cells.length;
          const t = c.getAttribute('t'); const v = kids(c, 'v')[0];
          let val = '';
          if (t === 's') val = v ? (ss[parseInt(v.textContent, 10)] ?? '') : '';
          else if (t === 'inlineStr') val = all(c, 't').map(x => x.textContent).join('');
          else if (t === 'b') val = v ? (v.textContent === '1' ? 'TRUE' : 'FALSE') : '';
          else if (t === 'str' || t === 'e') val = v ? v.textContent : '';
          else val = v ? (dateStyle[+(c.getAttribute('s') || 0)] ? serialToDate(v.textContent) : v.textContent) : '';
          // 数式は「値 ‹=数式›」の形で比較対象に含める（数式だけの変更も見落とさないように）
          const f = kids(c, 'f')[0];
          if (f && f.textContent) val = (val === '' ? '' : val + ' ') + '‹=' + f.textContent + '›';
          while (cells.length < ci) cells.push('');
          cells[ci] = val.replace(/\r?\n/g, '↵');
        }
        while (cells.length && cells[cells.length - 1] === '') cells.pop();
        if (cells.length) out.push(cells.join('\t'));
      }
      out.push('');
    }
    return out.join('\n');
  }

  /* ---- PowerPoint ---- */
  async function pptx(zip) {
    const pres = parseXml(await zip.text('ppt/presentation.xml'));
    const rels = relsMap(await zip.text('ppt/_rels/presentation.xml.rels'));
    let slides = all(pres, 'sldId').map(s => {
      const rid = s.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships', 'id') || s.getAttribute('r:id');
      return rels.get(rid) ? resolve('ppt/presentation.xml', rels.get(rid)) : null;
    }).filter(Boolean);
    if (!slides.length) slides = zip.names().filter(n => /^ppt\/slides\/slide\d+\.xml$/.test(n)).sort((a, b) => parseInt(a.match(/\d+/)[0]) - parseInt(b.match(/\d+/)[0]));
    const out = [];
    let n = 0;
    for (const path of slides) {
      n++;
      out.push(`===== スライド ${n} =====`);
      const x = await zip.text(path); if (!x) continue;
      for (const p of all(parseXml(x), 'p')) {
        if (p.namespaceURI && !/drawingml/.test(p.namespaceURI)) continue;
        const t = all(p, 't').map(e => e.textContent).join('');
        if (t.trim()) out.push(t);
      }
      const nrels = relsMap(await zip.text(path.replace(/slides\/(slide\d+\.xml)$/, 'slides/_rels/$1.rels')));
      for (const tgt of nrels.values()) {
        if (!/notesSlide/.test(tgt)) continue;
        const nx = await zip.text(resolve(path, tgt)); if (!nx) continue;
        const lines = all(parseXml(nx), 'p').map(p => all(p, 't').map(e => e.textContent).join('')).filter(s => s.trim() && !/^\d+$/.test(s.trim()));
        if (lines.length) out.push('〔ノート〕', ...lines);
      }
      out.push('');
    }
    return out.join('\n');
  }

  async function extract(kind, bytes) {
    const zip = Zip.open(bytes);
    if (kind === 'docx') return docx(zip);
    if (kind === 'xlsx') return xlsx(zip);
    if (kind === 'pptx') return pptx(zip);
    throw new Error('unknown office kind');
  }
  function kindOf(name, bytes) {
    const e = extOf(name);
    if (/^(docx|docm|dotx)$/.test(e)) return 'docx';
    if (/^(xlsx|xlsm|xltx)$/.test(e)) return 'xlsx';
    if (/^(pptx|pptm|potx)$/.test(e)) return 'pptx';
    try {
      const z = Zip.open(bytes);
      if (z.has('word/document.xml')) return 'docx';
      if (z.has('xl/workbook.xml')) return 'xlsx';
      if (z.has('ppt/presentation.xml')) return 'pptx';
    } catch (e) { }
    return null;
  }
  return { extract, kindOf };
})();
