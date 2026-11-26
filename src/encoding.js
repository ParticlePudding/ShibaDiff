/* 文字コード判定・デコード・エンコード */
const Enc = (() => {
  const NAMES = {
    'utf-8': 'UTF-8', 'utf-8-bom': 'UTF-8 (BOM付)', 'shift_jis': 'Shift_JIS', 'euc-jp': 'EUC-JP',
    'iso-2022-jp': 'JIS (ISO-2022-JP)', 'utf-16le': 'UTF-16LE', 'utf-16be': 'UTF-16BE', 'binary': 'バイナリ'
  };
  const LIST = ['utf-8', 'utf-8-bom', 'shift_jis', 'euc-jp', 'iso-2022-jp', 'utf-16le', 'utf-16be', 'binary'];

  function countBad(s) { let c = 0; for (let i = 0; i < s.length; i++) if (s.charCodeAt(i) === 0xFFFD) c++; return c; }
  function countHwKana(s) { let c = 0; for (let i = 0; i < s.length; i++) { const k = s.charCodeAt(i); if (k >= 0xFF61 && k <= 0xFF9F) c++; } return c; }

  function detect(bytes) {
    const L = bytes.length;
    if (L >= 3 && bytes[0] === 0xEF && bytes[1] === 0xBB && bytes[2] === 0xBF) return 'utf-8-bom';
    if (L >= 2 && bytes[0] === 0xFF && bytes[1] === 0xFE) return 'utf-16le';
    if (L >= 2 && bytes[0] === 0xFE && bytes[1] === 0xFF) return 'utf-16be';
    const n = Math.min(L, 65536);
    let nul = 0, ev = 0, od = 0;
    for (let i = 0; i < n; i++) if (bytes[i] === 0) { nul++; (i & 1) ? od++ : ev++; }
    if (nul > 0) {
      if (od > n * 0.25 && ev < n * 0.02) return 'utf-16le';
      if (ev > n * 0.25 && od < n * 0.02) return 'utf-16be';
      return 'binary';
    }
    let ctrl = 0;
    for (let i = 0; i < n; i++) { const b = bytes[i]; if (b < 9 || (b > 13 && b < 32 && b !== 27)) ctrl++; }
    if (ctrl > n * 0.1) return 'binary';
    for (let i = 0; i < n - 2; i++) if (bytes[i] === 0x1B && bytes[i + 1] === 0x24 && (bytes[i + 2] === 0x42 || bytes[i + 2] === 0x40)) return 'iso-2022-jp';
    let ascii = true; for (let i = 0; i < L; i++) if (bytes[i] >= 0x80) { ascii = false; break; }
    if (ascii) return 'utf-8';
    try { new TextDecoder('utf-8', { fatal: true }).decode(bytes); return 'utf-8'; } catch (e) { }
    const sample = bytes.subarray(0, Math.min(L, 262144));
    const sj = new TextDecoder('shift_jis').decode(sample), eu = new TextDecoder('euc-jp').decode(sample);
    const sjs = countBad(sj) * 20 + countHwKana(sj), eus = countBad(eu) * 20 + countHwKana(eu);
    return eus < sjs ? 'euc-jp' : 'shift_jis';
  }

  const DUMP_MAX = 4 * 1024 * 1024;
  function hexdump(bytes) {
    const MAX = DUMP_MAX;
    const n = Math.min(bytes.length, MAX), out = [];
    const hx = []; for (let i = 0; i < 256; i++) hx.push(i.toString(16).toUpperCase().padStart(2, '0'));
    for (let off = 0; off < n; off += 16) {
      let h = '', a = '';
      for (let j = 0; j < 16; j++) {
        if (off + j < n) { const b = bytes[off + j]; h += hx[b] + (j === 7 ? '  ' : ' '); a += (b >= 32 && b < 127) ? String.fromCharCode(b) : '.'; }
        else h += j === 7 ? '    ' : '   ';
      }
      out.push(off.toString(16).toUpperCase().padStart(8, '0') + '  ' + h + ' |' + a + '|');
    }
    if (bytes.length > MAX) out.push(`…（先頭 ${fmtSize(MAX)} のみ表示）`);
    return out.join('\n');
  }

  function decode(bytes, enc) {
    if (enc === 'binary') return hexdump(bytes);
    if (enc === 'utf-8-bom') {
      const b = (bytes[0] === 0xEF && bytes[1] === 0xBB && bytes[2] === 0xBF) ? bytes.subarray(3) : bytes;
      return new TextDecoder('utf-8').decode(b);
    }
    // TextDecoder strips a BOM automatically for utf-8/utf-16
    return new TextDecoder(enc).decode(bytes);
  }

  const tables = {};
  function table(enc) {
    if (tables[enc]) return tables[enc];
    const m = new Map(), buf = new Uint8Array(2), dec = new TextDecoder(enc === 'iso-2022-jp' ? 'euc-jp' : enc);
    const put = (cp, v) => { if (!m.has(cp)) m.set(cp, v); };
    if (enc === 'shift_jis') {
      for (let b = 0xA1; b <= 0xDF; b++) put(0xFF61 + b - 0xA1, b);
      const leads = []; for (let i = 0x81; i <= 0x9F; i++) leads.push(i); for (let i = 0xE0; i <= 0xFC; i++) leads.push(i);
      for (const l of leads) for (let t = 0x40; t <= 0xFC; t++) {
        if (t === 0x7F) continue;
        buf[0] = l; buf[1] = t; const s = dec.decode(buf);
        if (s.length === 1 && s !== '�') put(s.charCodeAt(0), (l << 8) | t);
      }
      put(0xA5, 0x5C); put(0x203E, 0x7E); put(0x2212, 0x817C);
    } else { // euc-jp (also used for iso-2022-jp)
      for (let b = 0xA1; b <= 0xDF; b++) put(0xFF61 + b - 0xA1, 0x8E00 | b);
      for (let l = 0xA1; l <= 0xFE; l++) for (let t = 0xA1; t <= 0xFE; t++) {
        buf[0] = l; buf[1] = t; const s = dec.decode(buf);
        if (s.length === 1 && s !== '�') put(s.charCodeAt(0), (l << 8) | t);
      }
      put(0xA5, 0x5C); put(0x203E, 0x7E); put(0x2212, 0xA1DD);
    }
    return (tables[enc] = m);
  }

  /* returns {bytes, unmapped} */
  function encode(str, enc) {
    if (enc === 'utf-8' || enc === 'binary') return { bytes: new TextEncoder().encode(str), unmapped: 0 };
    if (enc === 'utf-8-bom') {
      const b = new TextEncoder().encode(str), o = new Uint8Array(b.length + 3);
      o.set([0xEF, 0xBB, 0xBF]); o.set(b, 3); return { bytes: o, unmapped: 0 };
    }
    if (enc === 'utf-16le' || enc === 'utf-16be') {
      const o = new Uint8Array(2 + str.length * 2), le = enc === 'utf-16le';
      o[0] = le ? 0xFF : 0xFE; o[1] = le ? 0xFE : 0xFF;
      for (let i = 0; i < str.length; i++) {
        const c = str.charCodeAt(i);
        o[2 + i * 2] = le ? c & 0xFF : c >> 8; o[3 + i * 2] = le ? c >> 8 : c & 0xFF;
      }
      return { bytes: o, unmapped: 0 };
    }
    const t = table(enc), out = []; let unmapped = 0;
    if (enc === 'iso-2022-jp') {
      let mode = 0; // 0 ascii, 1 jis0208
      for (const ch of str) {
        const cp = ch.codePointAt(0);
        if (cp < 0x80) { if (mode) { out.push(0x1B, 0x28, 0x42); mode = 0; } out.push(cp); continue; }
        let v = t.get(cp);
        if (v === undefined && cp >= 0xFF61 && cp <= 0xFF9F) v = t.get(ch.normalize('NFKC').codePointAt(0));
        if (v === undefined || v < 0x100 || (v >> 8) === 0x8E) { // unmappable or halfwidth kana
          unmapped++; if (mode) { out.push(0x1B, 0x28, 0x42); mode = 0; } out.push(0x3F); continue;
        }
        if (!mode) { out.push(0x1B, 0x24, 0x42); mode = 1; }
        out.push((v >> 8) & 0x7F, v & 0x7F);
      }
      if (mode) out.push(0x1B, 0x28, 0x42);
      return { bytes: new Uint8Array(out), unmapped };
    }
    for (const ch of str) {
      const cp = ch.codePointAt(0);
      if (cp < 0x80) { out.push(cp); continue; }
      const v = t.get(cp);
      if (v === undefined) { unmapped++; out.push(0x3F); }
      else if (v > 0xFF) out.push(v >> 8, v & 0xFF);
      else out.push(v);
    }
    return { bytes: new Uint8Array(out), unmapped };
  }

  function splitLines(text) {
    let crlf = 0, lf = 0, cr = 0;
    for (let i = 0; i < text.length; i++) {
      const c = text.charCodeAt(i);
      if (c === 13) { if (text.charCodeAt(i + 1) === 10) { crlf++; i++; } else cr++; }
      else if (c === 10) lf++;
    }
    const eol = crlf >= lf && crlf >= cr ? (crlf ? '\r\n' : (lf ? '\n' : '\r\n')) : (lf >= cr ? '\n' : '\r');
    const mixed = [crlf, lf, cr].filter(x => x > 0).length > 1;
    const lines = text.split(/\r\n|\r|\n/);
    let finalNL = false;
    if (lines.length > 1 && lines[lines.length - 1] === '') { lines.pop(); finalNL = true; }
    if (lines.length === 1 && lines[0] === '' ) lines.length = 0;
    return { lines, eol, mixed, finalNL };
  }
  const EOLNAME = { '\r\n': 'CRLF', '\n': 'LF', '\r': 'CR' };

  return { detect, decode, encode, splitLines, NAMES, LIST, EOLNAME, DUMP_MAX };
})();
