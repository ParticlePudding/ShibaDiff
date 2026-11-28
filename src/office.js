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
  const W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
  const R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
  // ページ番号のフィールド（ヘッダー・フッターで使う）。保存時の値（1 など）ではなく、印で出す
  const PAGE_FIELD = { PAGE: '‹ページ番号›', NUMPAGES: '‹総ページ数›', SECTIONPAGES: '‹総ページ数›' };
  const pageField = instr => PAGE_FIELD[((/^\s*([A-Za-z]+)/.exec(instr || '') || [])[1] || '').toUpperCase()] || '';
  // opt.pageFields：ページ番号のフィールドを印に置き換える（ヘッダー・フッター用）
  function wParaText(p, opt = {}) {
    let s = '', fld = null; // fld：読んでいる途中のフィールド { instr, mark, result }
    const walk = el => {
      for (const c of el.children) {
        const ln = c.localName;
        if (opt.pageFields) {
          if (ln === 'fldChar') {
            const t = c.getAttributeNS(W_NS, 'fldCharType') || c.getAttribute('w:fldCharType');
            if (t === 'begin') fld = { instr: '', mark: '', result: false };
            else if (t === 'separate' && fld) { fld.mark = pageField(fld.instr); fld.result = true; s += fld.mark; }
            else if (t === 'end') { if (fld && !fld.result) s += pageField(fld.instr); fld = null; }
            continue;
          }
          if (ln === 'instrText') { if (fld) fld.instr += c.textContent; continue; }
          if (ln === 'fldSimple') {
            const mark = pageField(c.getAttributeNS(W_NS, 'instr') || c.getAttribute('w:instr'));
            if (mark) { s += mark; continue; }
          }
          if (fld && fld.result && fld.mark && ln === 't') continue; // ページ番号の保存時の値は出さない
        }
        if (ln === 't') s += c.textContent;
        else if (ln === 'tab') s += '\t';
        else if (ln === 'br' || ln === 'cr') s += '\n';
        // 変更履歴は「すべて承諾した状態」にする：削除（del）と、移動する前の場所（moveFrom）は読まない
        else if (ln === 'delText' || ln === 'instrText' || ln === 'del' || ln === 'moveFrom' || ln === 'rPr' || ln === 'pPr') continue;
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
  function wBlock(el, out, opt) {
    for (const c of el.children) {
      if (c.localName === 'p') out.push(...(wListPrefix(c) + wParaText(c, opt)).split('\n'));
      else if (c.localName === 'tbl') {
        out.push('┌─ 表 ─');
        for (const tr of kids(c, 'tr')) {
          const cells = kids(tr, 'tc').map(tc => { const o = []; wBlock(tc, o, opt); return o.join(' / ').trim(); });
          out.push('│ ' + cells.join(' │ '));
        }
        out.push('└─');
      } else if (c.localName === 'sdt') { const ct = kids(c, 'sdtContent')[0]; if (ct) wBlock(ct, out, opt); }
      else if (c.localName === 'customXml' || c.localName === 'ins' || c.localName === 'moveTo' || c.localName === 'smartTag') wBlock(c, out, opt);
    }
  }
  async function docx(zip, info) {
    const out = [];
    const xml = await zip.text('word/document.xml');
    if (!xml) throw new Error('word/document.xml が見つかりません');
    const doc = parseXml(xml), body = all(doc, 'body')[0];
    if (body) wBlock(body, out);
    // 変更履歴（挿入・削除・移動）の数。比較は承諾した状態の文字で行うので、残っていることを読み込んだ側で知らせる
    const tracked = { ins: 0, del: 0 };
    const count = d => { tracked.ins += all(d, 'ins').length + all(d, 'moveTo').length; tracked.del += all(d, 'del').length + all(d, 'moveFrom').length; };
    count(doc);
    // ヘッダー・フッター（版数・文書番号・機密区分などが書かれることが多い）。本文の節（sectPr）が参照している順に読み、
    // どこからも参照されていないものは番号順に足す。同じ内容のもの（先頭ページ用・偶数ページ用など）は1回だけ出す
    const rels = relsMap(await zip.text('word/_rels/document.xml.rels'));
    for (const [ref, re, label] of [['headerReference', /^word\/header(\d+)\.xml$/, 'ヘッダー'], ['footerReference', /^word\/footer(\d+)\.xml$/, 'フッター']]) {
      const used = all(doc, ref).map(e => rels.get(e.getAttributeNS(R_NS, 'id') || e.getAttribute('r:id'))).filter(Boolean).map(t => resolve('word/document.xml', t));
      const rest = zip.names().filter(n => re.test(n)).sort((a, b) => +re.exec(a)[1] - +re.exec(b)[1]);
      const lines = [], seen = new Set();
      for (const name of new Set([...used, ...rest])) {
        const x = await zip.text(name); if (!x) continue;
        const d = parseXml(x), ls = []; count(d);
        wBlock(d.documentElement, ls, { pageFields: true });
        const t = ls.filter(l => l.trim()), key = t.join('\n');
        if (!t.length || seen.has(key)) continue;
        seen.add(key); lines.push(...t);
      }
      if (lines.length) out.push('', `===== ${label} =====`, ...lines);
    }
    for (const extra of [['word/footnotes.xml', '脚注'], ['word/endnotes.xml', '文末脚注'], ['word/comments.xml', 'コメント']]) {
      const x = await zip.text(extra[0]); if (!x) continue;
      const d = parseXml(x); if (extra[1] !== 'コメント') count(d);
      const lines = []; for (const p of all(d, 'p')) { const t = wParaText(p); if (t.trim()) lines.push(t); }
      if (lines.length) { out.push('', `===== ${extra[1]} =====`, ...lines); }
    }
    if (info && (tracked.ins || tracked.del)) info.tracked = tracked;
    return out.join('\n');
  }

  /* ---- Excel ---- */
  function colIdx(ref) { let n = 0; for (const ch of ref) { const c = ch.charCodeAt(0); if (c < 65 || c > 90) break; n = n * 26 + (c - 64); } return n - 1; }
  function colName(i) { let s = ''; for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + (n - 1) % 26) + s; return s; }
  // セル番地（A1・$B$2）→ 0 始まりの行・列
  function cellPos(ref) { const m = /^\$?([A-Z]{1,3})\$?(\d{1,7})$/.exec(ref || ''); return m ? { r: +m[2] - 1, c: colIdx(m[1]) } : null; }
  /* 共有数式：Excel は、下や右へコピーした数式を、先頭のセルにだけ本文を書き、残りのセルは <f t="shared" si="番号"/>（本文なし）で保存する。
     先頭のセルの数式の相対参照を、セルの位置の差（dr 行・dc 列）だけずらして、そのセルの数式を作り直す（Excel の数式バーに出るものと同じ）。
     $ の付いた行・列、文字列（"…"）、シート名（'…'）、構造化参照（[…]）、関数名・名前はそのままにする */
  const MAX_COL = 16384, MAX_ROW = 1048576, REF_END = '(?![A-Za-z0-9_.(!])';
  const RE_CELL = new RegExp('(\\$?)([A-Z]{1,3})(\\$?)([0-9]{1,7})' + REF_END, 'y');
  const RE_COLS = new RegExp('(\\$?)([A-Z]{1,3}):(\\$?)([A-Z]{1,3})' + REF_END, 'y');
  const RE_ROWS = new RegExp('(\\$?)([0-9]{1,7}):(\\$?)([0-9]{1,7})' + REF_END, 'y');
  function shiftFormula(f, dr, dc) {
    if (!dr && !dc) return f;
    const wrap = (v, max) => ((v % max) + max) % max; // 端を越えたら反対側へ回る（Excel と同じ）
    const okCol = name => colIdx(name) < MAX_COL, okRow = n => +n >= 1 && +n <= MAX_ROW;
    const col = (abs, name) => abs + (abs ? name : colName(wrap(colIdx(name) + dc, MAX_COL)));
    const row = (abs, n) => abs + (abs ? n : String(wrap(+n - 1 + dr, MAX_ROW) + 1));
    const n = f.length; let out = '', i = 0;
    const quoted = q => { // 引用符で囲まれた部分（中の引用符は2つ重ねて書かれる）
      let j = i + 1;
      while (j < n) { if (f[j] === q) { if (f[j + 1] === q) { j += 2; continue; } break; } j++; }
      out += f.slice(i, j + 1); i = j + 1;
    };
    while (i < n) {
      const ch = f[i];
      if (ch === '"' || ch === "'") { quoted(ch); continue; }
      if (ch === '[') { let d = 0, j = i; do { if (f[j] === '[') d++; else if (f[j] === ']') d--; j++; } while (j < n && d > 0); out += f.slice(i, j); i = j; continue; }
      // 参照は、名前や数の途中（英数字・_・.・$ の直後）からは始まらない
      if (!(i && /[A-Za-z0-9_.$]/.test(f[i - 1]))) {
        let m;
        RE_CELL.lastIndex = RE_COLS.lastIndex = RE_ROWS.lastIndex = i;
        if ((m = RE_CELL.exec(f)) && okCol(m[2]) && okRow(m[4])) { out += col(m[1], m[2]) + row(m[3], m[4]); i += m[0].length; continue; }
        if ((m = RE_COLS.exec(f)) && okCol(m[2]) && okCol(m[4])) { out += col(m[1], m[2]) + ':' + col(m[3], m[4]); i += m[0].length; continue; }
        if ((m = RE_ROWS.exec(f)) && okRow(m[2]) && okRow(m[4])) { out += row(m[1], m[2]) + ':' + row(m[3], m[4]); i += m[0].length; continue; }
      }
      out += ch; i++;
    }
    return out;
  }
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
      // 日付・時刻の書式か。'd'＝日付（日付と時刻の両方を含む）、't'＝時刻だけ、''＝日付ではない
      const TIME_IDS = new Set([18, 19, 20, 21, 32, 33, 45, 46, 47]);
      const dateFmt = id => {
        if ((id >= 14 && id <= 22) || (id >= 27 && id <= 36) || (id >= 45 && id <= 47) || (id >= 50 && id <= 58)) return TIME_IDS.has(id) ? 't' : 'd';
        const code = custom.get(id); if (!code) return '';
        const c = code.replace(/"[^"]*"|\[[^\]]*\]|\\./g, '');
        if (!(/[ymdhs]/i.test(c) && !/^[#0.,%E+\-\s]*$/i.test(c))) return '';
        // 年・日・元号があれば日付。なければ、時・秒か、経過時間（[h] [mm] [ss]）があれば時刻だけ（m だけなら月）
        return /[ydge]/i.test(c) ? 'd' : (/[hs]/i.test(c) || /\[(h+|m+|s+)\]/i.test(code)) ? 't' : 'd';
      };
      const xfs = all(sd, 'cellXfs')[0];
      if (xfs) kids(xfs, 'xf').forEach((xf, i) => { dateStyle[i] = dateFmt(+xf.getAttribute('numFmtId')); });
    }
    const serialToDate = (v, kind) => {
      const n = parseFloat(v); if (!isFinite(n)) return v;
      const ms = Math.round((n - 25569) * 86400000), d = new Date(ms), p = x => String(x).padStart(2, '0');
      const date = `${d.getUTCFullYear()}/${p(d.getUTCMonth() + 1)}/${p(d.getUTCDate())}`, time = `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
      // 時刻だけの書式で1日未満の値は、0（0:00）でも時刻として出す（日付にすると 1899/12/30 になってしまう）
      if (kind === 't' && n >= 0 && n < 1) return time;
      const frac = n - Math.floor(n);
      return frac > 1e-6 ? `${n >= 1 ? date + ' ' : ''}${time}` : date;
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
      // 非表示のシートも比較の対象にする。見えていないシートの内容だと分かるよう、見出しに書く
      const hidden = /hidden/i.test(sh.getAttribute('state') || '');
      out.push(`===== シート: ${name}${hidden ? '（非表示）' : ''} =====`);
      const doc = parseXml(sx);
      // 共有数式の先頭のセル（本文のあるもの）を先に集める
      const shared = new Map();
      for (const f of all(doc, 'f')) {
        if (f.getAttribute('t') !== 'shared' || !f.textContent) continue;
        const pos = cellPos(f.parentNode.getAttribute('r'));
        if (pos) shared.set(f.getAttribute('si'), { text: f.textContent, r: pos.r, c: pos.c });
      }
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
          else { const dk = dateStyle[+(c.getAttribute('s') || 0)]; val = v ? (dk ? serialToDate(v.textContent, dk) : v.textContent) : ''; }
          // 数式は「値 ‹=数式›」の形で比較対象に含める（数式だけの変更も見落とさないように）
          const f = kids(c, 'f')[0];
          let ftext = f ? f.textContent : '';
          if (f && !ftext && f.getAttribute('t') === 'shared') {
            // 共有数式の2つ目以降のセル：先頭のセルの数式を、位置の差だけずらして作る
            const mst = shared.get(f.getAttribute('si')), pos = cellPos(r);
            if (mst && pos) ftext = shiftFormula(mst.text, pos.r - mst.r, pos.c - mst.c);
          }
          if (ftext) val = (val === '' ? '' : val + ' ') + '‹=' + ftext + '›';
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

  // info を渡すと、読み込んだ文書について知らせること（Word の変更履歴の数 info.tracked）を入れて返す
  async function extract(kind, bytes, info) {
    const zip = Zip.open(bytes);
    if (kind === 'docx') return docx(zip, info);
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
  return { extract, kindOf, shiftFormula };
})();
