/* レポート（HTML）の共通部品：ファイル情報・SHA-256・印刷用のスタイル・CSP。
   テキスト比較・重ね合わせ比較・ページ表示・フォルダ比較のレポートで使う */
const Report = (() => {
  async function sha256(bytes) {
    try { if (!bytes || !crypto.subtle) return ''; const h = await crypto.subtle.digest('SHA-256', bytes); return Array.from(new Uint8Array(h), b => b.toString(16).padStart(2, '0')).join(''); }
    catch (e) { return ''; }
  }
  // 1つのファイルの情報（名前・大きさ・更新日時・文字コード・ページ数・SHA-256・未保存の編集）
  function fileInfo(s, hash) {
    if (!s) return '<span class="sub">（なし）</span>';
    const parts = [];
    if (s.size) parts.push(fmtSize(s.size));
    if (s.mtime) parts.push('更新 ' + fmtDate(s.mtime));
    if (s.kind === 'text') parts.push((Enc.NAMES[s.enc] || s.enc) + '・' + (Enc.EOLNAME[s.eol] || ''));
    if (s.kind === 'pdf') parts.push(`${s.pageCount}ページ${s.noTextLayer ? '・文字情報なし（スキャン）' : ''}`);
    return `${esc(s.name)}<br><span class="sub">${parts.join('・')}${hash ? `<br>SHA-256: ${hash}` : ''}` +
      `${s.dirty ? '<br><b style="color:#b42318">※ 未保存の編集を含む内容です（元のファイルとは異なります）</b>' : ''}</span>`;
  }
  async function bothInfo() {
    const [h0, h1] = await Promise.all([sha256(S[0] && S[0].bytes), sha256(S[1] && S[1].bytes)]);
    return `<table class="files"><tr><th>左</th><td>${fileInfo(S[0], h0)}</td></tr><tr><th>右</th><td>${fileInfo(S[1], h1)}</td></tr></table>`;
  }
  const BASE_CSS = `*{-webkit-print-color-adjust:exact;print-color-adjust:exact;box-sizing:border-box}
body{font-family:"BIZ UDPGothic","Meiryo",sans-serif;margin:20px;color:#222;font-size:13px}
h1{font-size:18px;margin:0 0 8px}h2{font-size:15px;margin:22px 0 8px;padding-bottom:4px;border-bottom:2px solid #d0d7de}
.meta{color:#444;font-size:12.5px;margin-bottom:12px;line-height:1.7}.meta b{color:#222}
.sub{font-weight:400;color:#666;font-size:11px;word-break:break-all}
table.files{border-collapse:collapse;margin:6px 0 12px;width:100%}table.files th{width:36px;background:#eee;padding:6px;text-align:center;vertical-align:top}table.files td{padding:6px 8px;border-bottom:1px solid #eee}
table.list{border-collapse:collapse;width:100%;font-size:12.5px}table.list th{background:#eee;padding:5px 8px;text-align:left;font-weight:600}table.list td{padding:4px 8px;border-bottom:1px solid #eee;vertical-align:top}
.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;border-radius:4px;padding:0 6px;font-size:11.5px;font-weight:700;color:#fff}
.tag.diff{background:#b42318}.tag.add,.tag.right{background:#1a5fb4}.tag.del,.tag.left{background:#9a3412}.tag.same{background:#2f7d3a}.tag.note{background:#8a6d00}
figure{margin:8px 0 18px;break-inside:avoid}figure img{max-width:100%;border:1px solid #ccd;display:block}figcaption{font-size:12px;color:#444;margin-top:4px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media print{body{margin:8mm}thead{display:table-header-group}tr{break-inside:avoid}h2{break-after:avoid}}`;
  // 完成した HTML（外部の読み込み・スクリプトを禁止する CSP 付き。画像は data URL で埋め込む）
  function page({ title, heading, meta = '', body, css = '' }) {
    return `<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:"><title>${esc(title)}</title><style>${BASE_CSS}${css}</style></head><body>
<h1>${esc(heading || title)}</h1>
<div class="meta">作成日時: ${fmtDate(Date.now())}　作成: ShibaDiff ${esc(APP.version)}${meta ? '<br>' + meta : ''}</div>
${body}</body></html>`;
  }
  // canvas を、幅を上限までに縮めた JPEG の data URL にする（レポートが大きくなりすぎないように）
  function jpeg(cv, maxW = 1400, q = 0.82) {
    let src = cv;
    if (cv.width > maxW) {
      src = document.createElement('canvas'); src.width = maxW; src.height = Math.round(cv.height * maxW / cv.width);
      const c = src.getContext('2d'); c.imageSmoothingQuality = 'high'; c.fillStyle = '#fff'; c.fillRect(0, 0, src.width, src.height); c.drawImage(cv, 0, 0, src.width, src.height);
    }
    const url = src.toDataURL('image/jpeg', q);
    if (src !== cv) src.width = src.height = 0;
    return url;
  }
  // どの範囲を出力するかを聞く（choices: [{label, value}]）
  async function ask(title, text, choices) {
    return modal({ title, html: text, buttons: [{ label: 'キャンセル', value: null }, ...choices] });
  }
  // 画像の幅（画質）：軽量・標準・高精細
  const QUALITY = { light: 900, std: 1400, high: 2200 };
  const qualityField = { k: 'quality', label: '画像の画質', type: 'radio', def: 'std', choices: [['light', '軽量（小さいファイル）'], ['std', '標準'], ['high', '高精細（細い線まで）']] };
  /* 出力の設定を聞くダイアログ。設定はレポートの種類ごとに覚える（doccmp:report:種類）。
     fields: [{k, label, type:'radio'|'check', def, choices:[[値, 表示]]}]、choices: 下のボタン（出力する範囲）[{label, value, primary}]
     戻り値：{scope: 押したボタンの値, …各項目の値}（キャンセルなら null） */
  async function options(kind, title, intro, fields, choices) {
    const saved = store.get('report:' + kind) || {};
    const val = f => (saved[f.k] !== undefined && (f.type === 'check' || f.choices.some(c => c[0] === saved[f.k]))) ? saved[f.k] : f.def;
    const radios = fields.filter(f => f.type === 'radio'), checks = fields.filter(f => f.type === 'check');
    const html = `<div class="rep-intro">${intro}</div><div class="rep-opts">` +
      radios.map(f => `<div class="rep-row" role="radiogroup" aria-label="${esc(f.label)}"><span class="rep-lbl">${esc(f.label)}</span>` +
        f.choices.map(([v, l]) => `<label><input type="radio" name="rep_${f.k}" data-k="${f.k}" value="${v}"${val(f) === v ? ' checked' : ''}>${esc(l)}</label>`).join('') + '</div>').join('') +
      (checks.length ? `<div class="rep-row"><span class="rep-lbl">載せる内容</span><span class="rep-chk">` +
        checks.map(f => `<label><input type="checkbox" data-k="${f.k}"${val(f) ? ' checked' : ''}>${esc(f.label)}</label>`).join('') + '</span></div>' : '') + '</div>';
    const read = m => {
      const o = {};
      for (const f of fields) {
        if (f.type === 'check') o[f.k] = $(`input[data-k="${f.k}"]`, m).checked;
        else { const r = $(`input[data-k="${f.k}"]:checked`, m); o[f.k] = r ? r.value : f.def; }
      }
      return o;
    };
    const res = await modal({ title, html, buttons: [{ label: 'キャンセル', value: null }, ...choices.map(c => ({ label: c.label, primary: c.primary, value: m => ({ ...read(m), scope: c.value }) }))] });
    if (res) { const o = { ...res }; delete o.scope; store.set('report:' + kind, o); }
    return res;
  }
  const width = q => QUALITY[q] || QUALITY.std;
  return { sha256, fileInfo, bothInfo, page, jpeg, ask, options, qualityField, width };
})();
