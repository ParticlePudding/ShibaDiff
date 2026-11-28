/* 設定（頻繁には切り替えない項目）とブラウザ保存データの管理 */
const Settings = (() => {
  const DEF = {
    wrap: false, showWs: false, unit: 'auto', numDelta: true, fontSize: 'm', persist: false, author: '', ovRes: 'std', pageMatch: true, ovScroll: false
  };
  const cur = Object.assign({}, DEF, store.get('settings', {}));
  const subs = [];
  const get = k => cur[k];
  function set(k, v) {
    if (cur[k] === v) return;
    cur[k] = v; store.set('settings', cur); applyFont();
    subs.forEach(f => { try { f(k, v); } catch (e) { console.error(e); } });
  }
  const on = f => subs.push(f);
  function applyFont() { document.documentElement.dataset.fs = cur.fontSize; }
  applyFont();

  const sel = (k, opts) => `<select data-k="${k}">${opts.map(([v, l]) => `<option value="${v}"${cur[k] === v ? ' selected' : ''}>${l}</option>`).join('')}</select>`;
  const chk = (k, label) => `<label class="setrow"><input type="checkbox" data-k="${k}"${cur[k] ? ' checked' : ''}> ${label}</label>`;
  const txt = (k, label, ph) => `<label class="setrow">${label} <input type="text" data-k="${k}" value="${esc(cur[k] || '')}" placeholder="${ph}" style="width:200px"></label>`;

  async function open(section) {
    await modal({
      title: '設定', wide: false,
      html: `<div class="settings">
<h4 id="set-view">表示</h4>
${chk('wrap', '長い行を折り返して表示する')}
${chk('showWs', '空白・タブ・改行を記号で表示する（半角空白 ・／全角空白 □／タブ →／改行 ↵＝CRLF・↓＝LF）')}
<label class="setrow">行の中の違いの単位 ${sel('unit', [['auto', '自動（英文は単語、和文は文字）'], ['char', '1文字ずつ'], ['word', '単語ずつ']])}</label>
${chk('numDelta', '数字が変わったとき、差と増減率を表示する（例：+50,000 / +10.0%）')}
<label class="setrow">文字の大きさ ${sel('fontSize', [['s', '小'], ['m', '標準'], ['l', '大']])}</label>
<label class="setrow">重ね合わせの解像度 ${sel('ovRes', [['low', '軽量（〜1600px）'], ['std', '標準（〜2400px）'], ['high', '精細（〜4000px）']])}</label>
<div class="muted" style="margin:2px 0 6px 0">A1・A0 などの大きな図面で効きます。重いときは「軽量」、細い線の違いを見落とすときは「精細」にしてください。</div>
<h4 id="set-data">このブラウザに保存するデータ</h4>
${chk('persist', '注釈・変更点のコメント・ページの回転を、このブラウザに自動で保存する')}
<div class="muted" style="margin:2px 0 6px 22px">既定はオフです（共用のPCに個人情報や社外秘のメモが残らないように）。オフのときは、ファイルを閉じると注釈とコメントは消えます。残すときは「注釈を保存」でファイルにしてください。</div>
${txt('author', 'コメントの記入者名', '例：山田（空欄なら記録しません）')}
<button type="button" id="setData"><i data-i="database"></i>保存されているデータを確認・削除…</button>
<h4 id="set-about">このツールについて</h4>
<table class="about">
<tr><td>版</td><td>${esc(APP.version)}（${esc(APP.build)}）</td></tr>
<tr><td>ライセンス</td><td>MIT License</td></tr>
<tr><td>同梱ライブラリ</td><td>pdf.js ${esc(APP.pdfjs)}（Apache License 2.0）<br>core-js（MIT License。pdf.js に同梱）<br>Lucide アイコン ${esc(APP.lucide || '')}（ISC License）</td></tr>
<tr><td></td><td><button type="button" id="setLicenses"><i data-i="scale"></i>ライセンス全文を表示…</button></td></tr>
<tr><td>通信</td><td>外部との通信は行いません（Content-Security-Policy で禁止しています）</td></tr>
</table></div>`,
      buttons: [{ label: '閉じる', primary: true, value: null }],
      onOpen: (m, close) => {
        $$('[data-k]', m).forEach(el => {
          const k = el.dataset.k;
          el.addEventListener(el.type === 'text' ? 'input' : 'change', async () => {
            const v = el.type === 'checkbox' ? el.checked : el.value;
            if (k === 'persist' && !v) {
              // 自動保存をやめるとき：それまでに保存した注釈・変更点のコメント・ページの回転を、残すか削除するかを確かめる
              // （共用のPCに付箋やコメントの文字を残さないため。どれか1種類でも残っていれば聞く）
              const ks = savedDataKeys();
              if (ks.length) {
                const cnt = kind => ks.filter(x => x.startsWith(`doccmp:${kind}:`)).length;
                const parts = [['ann', '注釈'], ['notes', '変更点のコメント'], ['rot', 'ページの回転']].map(([kind, t]) => [cnt(kind), t]).filter(x => x[0]).map(([n, t]) => `${t} ${n} 件`).join('・');
                const del = await modal({
                  title: '保存済みのデータ',
                  html: `このブラウザには、これまでに自動で保存したデータが残っています（${parts}）。<br>これらも削除しますか？<br><span class="muted">残した場合も、「保存されているデータを確認・削除…」からあとで削除できます。開いている文書の注釈とコメントは、閉じるまで画面に残ります。</span>`,
                  buttons: [{ label: '削除する', value: true }, { label: '残す', primary: true, value: false }]
                });
                if (del) savedDataKeys().forEach(key => { try { localStorage.removeItem(key); } catch (e) { } });
              }
            }
            set(k, v);
          });
        });
        $('#setData', m).onclick = () => { close(null); setTimeout(() => openData().then(() => open('data')), 0); };
        $('#setLicenses', m).onclick = () => { close(null); setTimeout(() => openLicenses().then(() => open('about')), 0); };
        if (section) { const h = $('#set-' + section, m); if (h) h.scrollIntoView(); }
      }
    });
  }

  function allKeys() { const r = []; try { for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (k && k.startsWith('doccmp:')) r.push(k); } } catch (e) { } return r.sort(); }
  // 自動保存（persist）で残るデータ：注釈・変更点のコメント・ページの回転
  const savedDataKeys = () => allKeys().filter(k => /^doccmp:(ann|notes|rot):/.test(k));
  function describe(k) {
    const raw = (() => { try { return localStorage.getItem(k) || ''; } catch (e) { return ''; } })();
    if (k.startsWith('doccmp:ann:')) {
      const [name, size, mt] = k.slice(11).split('|');
      let n = 0; try { const o = JSON.parse(raw); for (const v of Object.values(o)) if (Array.isArray(v)) n += v.length; } catch (e) { }
      return { kind: '注釈', name, detail: `${n} 件（文書 ${fmtSize(+size)}・文書の更新日時 ${fmtDate(+mt)}）`, bytes: raw.length };
    }
    if (k.startsWith('doccmp:notes:')) {
      const [l, r] = k.slice(13).split('||').map(x => (x || '').split('|')[0]);
      let n = 0; try { n = Object.keys(JSON.parse(raw)).length; } catch (e) { }
      return { kind: '変更点のコメント', name: `${l} ／ ${r}`, detail: `${n} 件`, bytes: raw.length };
    }
    if (k.startsWith('doccmp:rot:')) { const [name] = k.slice(11).split('|'); return { kind: 'ページの回転', name, detail: raw + '°', bytes: raw.length }; }
    const names = { 'doccmp:settings': '設定', 'doccmp:textopts': 'テキスト比較の比較条件', 'doccmp:tvLayout': '左右表示／一列表示', 'doccmp:pv:color': '注釈の色（旧形式）', 'doccmp:pv:toolColor': '注釈の道具ごとの色', 'doccmp:pv:width': '注釈の線の太さ', 'doccmp:pv:zoom': 'ページ表示の倍率', 'doccmp:pv:stamp': '日付印（旧形式・使っていません）', 'doccmp:pvChanges': 'ページ表示で変更箇所を表示するか', 'doccmp:tvNotes': 'テキスト比較の変更点一覧を開くか' };
    const rep = { text: 'テキスト比較', overlay: '重ね合わせ比較', page: 'ページ表示・注釈', folder: 'フォルダ比較' };
    const m = /^doccmp:report:(\w+)$/.exec(k);
    if (m) return { kind: '設定', name: `レポートの出力設定（${rep[m[1]] || m[1]}）`, detail: '', bytes: raw.length };
    return { kind: '設定', name: names[k] || k.slice(7), detail: '', bytes: raw.length };
  }
  /* 保存データをすべて削除したとき、開いている間の設定も初期値に戻す（保存はしない） */
  function resetAll() {
    for (const k of Object.keys(DEF)) {
      const v = DEF[k];
      if (cur[k] === v) continue;
      cur[k] = v; subs.forEach(f => { try { f(k, v); } catch (e) { console.error(e); } });
    }
    applyFont();
  }
  function openLicenses() {
    const t = ($('#licenses') || {}).textContent || '';
    return modal({ title: 'ライセンス', wide: true, html: `<pre class="licenses">${esc(t)}</pre>`, buttons: [{ label: '閉じる', primary: true, value: null }] });
  }
  function openData() {
    const rows = () => allKeys().map(k => ({ k, ...describe(k) }));
    const table = list => list.length ? `<table class="datatbl"><thead><tr><th><input type="checkbox" id="dAll" aria-label="すべて選択"></th><th>種類</th><th>内容</th><th>詳細</th><th class="num">保存の大きさ</th></tr></thead><tbody>` +
      list.map(r => `<tr><td><input type="checkbox" data-key="${esc(r.k)}" aria-label="${esc(r.name)} を選択"></td><td>${r.kind}</td><td class="nm">${esc(r.name)}</td><td class="muted">${esc(r.detail)}</td><td class="num">${fmtSize(r.bytes * 2)}</td></tr>`).join('') + '</tbody></table>'
      : '<p class="muted">このブラウザに保存されているデータはありません。</p>';
    return modal({
      title: '保存されているデータ', wide: true,
      html: `<p>このツールがブラウザ（localStorage）に保存しているデータの一覧です。ファイルの中身そのものは保存していません。<br>注釈には付箋の文字が、変更点のコメントにはひとことと記入者名が含まれます。共用のPCでは、使い終わったら削除してください（注釈・コメントの自動保存は、設定で既定はオフです）。<br><span class="muted">「保存の大きさ」は、このブラウザに保存しているデータの大きさです（文書のファイルの大きさではありません）。</span></p><div id="dList"></div>`,
      buttons: [{ label: '選択したものを削除', value: 'sel' }, { label: 'すべて削除', value: 'all' }, { label: '閉じる', primary: true, value: null }],
      onOpen: m => {
        const draw = () => {
          $('#dList', m).innerHTML = table(rows());
          const all = $('#dAll', m); if (all) all.onchange = () => $$('[data-key]', m).forEach(c => c.checked = all.checked);
        };
        draw();
        // 「削除」ボタンはダイアログを閉じずに処理する
        const btns = $$('.foot button', m);
        const keep = (b, fn) => { const nb = b.cloneNode(true); b.replaceWith(nb); nb.onclick = fn; };
        keep(btns[0], () => { const ks = $$('[data-key]:checked', m).map(c => c.dataset.key); if (!ks.length) return toast('削除するものを選んでください'); ks.forEach(k => localStorage.removeItem(k)); toast(`${ks.length} 件を削除しました`); draw(); });
        keep(btns[1], async () => {
          if (!allKeys().length) return toast('保存されているデータはありません');
          // 確認はこのダイアログの上に重ねて出し、閉じたら一覧に戻る
          const ok = await modal({ title: 'すべて削除', html: 'このツールがブラウザに保存しているデータをすべて削除しますか？<br>設定も初期状態に戻ります。', buttons: [{ label: 'キャンセル', value: false }, { label: 'すべて削除する', primary: true, value: true }] });
          if (!ok) return;
          allKeys().forEach(k => localStorage.removeItem(k)); resetAll(); toast('すべて削除しました'); draw();
        });
      }
    });
  }
  return { get, set, on, open, openData };
})();
