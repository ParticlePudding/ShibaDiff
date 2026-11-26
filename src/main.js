/* アプリ本体：ファイル読み込み・ファイル欄・タブ・ドラッグ&ドロップ・キーボード */
let S = [null, null];

const App = (() => {
  const app = { tab: 'text' };
  const slots = $$('#slots .slot');

  function sniff(b) {
    const h = n => b.length > n ? b[n] : -1;
    if (h(0) === 0x25 && h(1) === 0x50 && h(2) === 0x44 && h(3) === 0x46) return 'pdf';
    if (h(0) === 0x89 && h(1) === 0x50 && h(2) === 0x4E && h(3) === 0x47) return 'image/png';
    if (h(0) === 0xFF && h(1) === 0xD8 && h(2) === 0xFF) return 'image/jpeg';
    if (h(0) === 0x47 && h(1) === 0x49 && h(2) === 0x46 && h(3) === 0x38) return 'image/gif';
    if (h(0) === 0x42 && h(1) === 0x4D && b.length > 26) return 'image/bmp';
    if (h(0) === 0x52 && h(1) === 0x49 && h(2) === 0x46 && h(3) === 0x46 && h(8) === 0x57 && h(9) === 0x45 && h(10) === 0x42 && h(11) === 0x50) return 'image/webp';
    if ((h(0) === 0x49 && h(1) === 0x49 && h(2) === 0x2A) || (h(0) === 0x4D && h(1) === 0x4D && h(3) === 0x2A)) return 'tiff';
    if (h(0) === 0x50 && h(1) === 0x4B && h(2) === 3 && h(3) === 4) return 'zip';
    if (h(0) === 0xD0 && h(1) === 0xCF && h(2) === 0x11 && h(3) === 0xE0) return 'ole';
    return null;
  }

  // 変更の有無の判定に使う内容（末尾の改行の有無も含める）
  const textSig = s => s.lines.join('\n') + (s.finalNL !== false && s.lines.length ? '\n' : '');
  function setText(s, text) {
    const sp = Enc.splitLines(text);
    s.lines = sp.lines; s.eol = sp.eol; s.mixed = sp.mixed; s.finalNL = sp.finalNL;
    s.orig = textSig(s);
  }

  async function prepare(s) {
    const b = s.bytes, ext = extOf(s.name), sn = sniff(b);
    s._pages = null;
    if (sn === 'pdf') {
      s.kind = 'pdf';
      s.pdf = await PDF.open(b);
      s.pageCount = s.pdf.numPages;
      setText(s, await PDF.text(s.pdf, (i, n) => { $('#busyMsg').textContent = `PDFのテキストを抽出中… ${i} / ${n}`; }));
      // 文字情報がない（スキャン画像だけの）PDFか
      s.noTextLayer = !s.lines.some(l => l.trim() && !/^===== ページ \d+ =====$/.test(l));
      s.getPages = async () => (s._pages || (s._pages = await PDF.pages(s.pdf)));
      return;
    }
    if (sn && sn.startsWith('image/')) {
      s.kind = 'image'; s.noText = true; s.mime = sn;
      s.lines = []; s.orig = ''; s.eol = '\r\n';
      s.getPages = async () => (s._pages || (s._pages = await Pages.fromImage(b, sn)));
      await s.getPages();
      return;
    }
    if (sn === 'zip') {
      const k = Office.kindOf(s.name, b);
      if (k) {
        s.kind = k; setText(s, await Office.extract(k, b));
        s.getPages = async () => (s._pages || (s._pages = Pages.fromText(s.lines, s.name)));
        return;
      }
    }
    if (sn === 'tiff') toast('TIFF画像はブラウザで表示できないため、バイナリとして比較します。PNG/JPEG/PDFに変換すると重ね合わせ比較ができます', true);
    else if (/^(xdw|xbd)$/.test(ext)) toast('DocuWorks文書(.xdw)は直接読めないため、バイナリとして比較します。DocuWorksでPDFに変換してから読み込んでください', true);
    else if (sn === 'ole' && /^(doc|xls|ppt)$/.test(ext)) toast(`旧形式の .${ext} はテキストを取り出せないため、バイナリとして比較します。.${ext}x 形式で保存し直すと中身を比較できます`, true);
    s.kind = 'text';
    s.enc = Enc.detect(b);
    s.asciiOnly = s.enc === 'utf-8' && b.every(x => x < 0x80);
    if (s.enc === 'binary') s.kind = 'binary';
    setText(s, Enc.decode(b, s.enc));
    s.getPages = async () => (s._pages || (s._pages = Pages.fromText(s.lines, s.name)));
  }

  function errMsg(e) {
    const n = e && e.name, m = (e && e.message) || String(e);
    if (n === 'InvalidPDFException' || /Invalid PDF/i.test(m)) return 'PDFファイルが壊れているか、PDF形式ではありません。';
    if (n === 'PasswordException') return 'パスワードが入力されませんでした。';
    if (/ZIPの構造|ZIP形式/.test(m)) return 'Office文書が壊れている可能性があります。';
    return m;
  }
  function disposeSide(s) { if (s && s.pdf) { try { s.pdf.destroy(); } catch (e) { } } }

  /* 保存していない変更がある側を置き換える前に確認する（置き換えると元に戻す履歴も消えるため） */
  async function confirmDiscard(sides, verb) {
    const d = sides.filter(i => S[i] && S[i].dirty);
    if (!d.length) return true;
    const names = d.map(i => `${i ? '右' : '左'}の「${esc(S[i].name)}」`).join('と');
    return !!await modal({ title: '保存していない変更', html: `${names}には保存していない変更があります。${verb}と変更は失われます。続けてもよろしいですか？`, buttons: [{ label: 'キャンセル', value: false }, { label: '続ける', primary: true, value: true }] });
  }
  async function loadFile(side, file) {
    if (!await confirmDiscard([side], '別のファイルを読み込む')) return;
    try {
      await withBusy(`${file.name} を読み込み中…`, async () => {
        const bytes = new Uint8Array(await file.arrayBuffer());
        const s = { name: file.name, size: file.size, mtime: file.lastModified, bytes, key: `${file.name}|${file.size}|${file.lastModified}`, file };
        await prepare(s);
        disposeSide(S[side]);
        S[side] = s;
      });
      changed([side]);
    } catch (e) {
      console.error(e);
      toast(`「${file.name}」を読み込めませんでした。${errMsg(e)}${S[side] ? '（前のファイルはそのまま残っています）' : ''}`, true);
    }
  }
  async function loadPair(files) {
    if (!await confirmDiscard([0, 1], '別のファイルを読み込む')) return false;
    for (let i = 0; i < 2; i++) {
      if (!files[i]) continue;
      try {
        await withBusy(`${files[i].name} を読み込み中…`, async () => {
          const f = files[i], bytes = new Uint8Array(await f.arrayBuffer());
          const s = { name: f.name, size: f.size, mtime: f.lastModified, bytes, key: `${f.name}|${f.size}|${f.lastModified}`, file: f };
          await prepare(s); disposeSide(S[i]); S[i] = s;
        });
      } catch (e) { toast(`「${files[i].name}」を読み込めませんでした。${errMsg(e)}`, true); }
    }
    for (let i = 0; i < 2; i++) if (!files[i]) { disposeSide(S[i]); S[i] = null; }
    if (app.tab === 'folder') setTab('text');
    changed([0, 1]);
    return true;
  }

  function changed(sides) {
    TV.resetHistory();
    sides.forEach(updateSlot);
    TV.invalidate();
    sides.forEach(s => PV.invalidate(s));
    OV.invalidate();
    autoTab();
  }
  const visualOnly = s => !!(s && (s.kind === 'image' || s.noTextLayer));
  /* 文字情報のない画像・スキャンPDFが含まれていたら、重ね合わせ比較へ自動で切り替える */
  function autoTab() {
    if (!S[0] || !S[1] || app.tab !== 'text') return;
    if (!(visualOnly(S[0]) || visualOnly(S[1]))) return;
    if (!S.every(s => s.kind === 'pdf' || s.kind === 'image')) return;
    setTab('overlay');
    toast('文字情報のない画像（スキャン）が含まれるため、「重ね合わせ比較」に切り替えました', false, 4500);
  }

  function newTextSide() {
    return { name: '(新規テキスト)', size: 0, mtime: Date.now(), bytes: null, key: 'new|' + Date.now() + Math.random(), kind: 'text', enc: 'utf-8', eol: '\r\n', finalNL: true, lines: [], orig: '', getPages() { return Promise.resolve(this._pages || (this._pages = Pages.fromText(this.lines, this.name))); } };
  }

  /* called after the model lines of a side changed */
  function afterEdit(side, quiet) {
    const s = S[side]; if (!s) return;
    s.dirty = textSig(s) !== s.orig;
    s._pages = s.kind === 'pdf' || s.kind === 'image' ? s._pages : null;
    updateSlot(side);
    if (s.kind !== 'pdf' && s.kind !== 'image') { PV.invalidate(side); OV.invalidate(); }
    void quiet;
  }

  /* ---------- file slot UI ---------- */
  const KIND = { pdf: 'PDF', docx: 'Word', xlsx: 'Excel', pptx: 'PowerPoint', image: '画像', binary: 'バイナリ', text: 'テキスト' };
  function updateSlot(side) {
    const el = slots[side], s = S[side];
    el.classList.toggle('loaded', !!s);
    $('.fname', el).innerHTML = s ? `${s.dirty ? '<span class="dirty" title="未保存の変更があります">● </span>' : ''}${esc(s.name)}` : 'ファイルをドロップ、またはクリックして選択';
    $('.fname', el).title = s ? s.name : '';
    const info = $('.slot-info', el);
    if (!s) { info.innerHTML = `<span class="meta"></span><button data-act="edit" title="テキストを直接入力・貼り付け">テキストを入力</button>`; return; }
    let meta = `${KIND[s.kind] || s.kind}`;
    if (s.size) meta += `・${fmtSize(s.size)}`;
    if (s.mtime && s.bytes) meta += `・${fmtDate(s.mtime)}`;
    if (s.kind === 'pdf') meta += `・${s.pageCount}ページ`;
    let html = '';
    if (s.asciiOnly) meta += '・英数字のみ';
    if (!s.lines.length || (s.lines.length === 1 && s.finalNL === false)) meta += '・改行なし';
    if (s.kind === 'text' || s.kind === 'binary') {
      html += `<select data-act="enc" title="文字コード（変更すると読み直します）">${Enc.LIST.map(e => `<option value="${e}"${e === s.enc ? ' selected' : ''}>${Enc.NAMES[e]}</option>`).join('')}</select>`;
      html += `<select data-act="eol" title="保存時の改行コード">${['\r\n', '\n', '\r'].map(e => `<option value="${encodeURIComponent(e)}"${e === s.eol ? ' selected' : ''}>${Enc.EOLNAME[e]}</option>`).join('')}</select>`;
    }
    html += `<span class="meta" title="${esc(meta)}">${esc(meta)}</span><span class="grow"></span>`;
    if (!s.noText) html += `<button data-act="edit" title="テキストを編集（行をダブルクリックでも開きます）">編集</button><button data-act="save" title="${s.kind === 'text' ? '保存' : 'テキストとして保存'}">保存</button>`;
    html += `<button data-act="close" title="閉じる">✕</button>`;
    info.innerHTML = html;
  }
  slots.forEach((el, side) => {
    const inp = $('input[type=file]', el);
    el.addEventListener('click', e => {
      if (e.target.closest('button,select,input')) return;
      inp.click();
    });
    el.addEventListener('keydown', e => {
      if (e.target !== el || (e.key !== 'Enter' && e.key !== ' ')) return;
      e.preventDefault(); inp.click();
    });
    inp.onchange = () => { if (inp.files[0]) loadFile(side, inp.files[0]); inp.value = ''; };
    el.addEventListener('change', e => {
      const act = e.target.dataset.act, s = S[side]; if (!s) return;
      if (act === 'enc') {
        const enc = e.target.value;
        if (s.dirty) { s.enc = enc; toast(`保存時の文字コードを ${Enc.NAMES[enc]} にしました`); return; }
        if (!s.bytes) { s.enc = enc; return; }
        s.enc = enc; s.kind = enc === 'binary' ? 'binary' : 'text';
        const eol = s.eol; setText(s, Enc.decode(s.bytes, enc)); if (s.bytes.length === 0) s.eol = eol;
        s._pages = null; changed([side]);
      } else if (act === 'eol') {
        s.eol = decodeURIComponent(e.target.value); s.dirty = true; updateSlot(side); TV.status();
      }
    });
    el.addEventListener('click', e => {
      const b = e.target.closest('button[data-act]'); if (!b) return;
      const act = b.dataset.act;
      if (act === 'edit') openEditor(side, null);
      else if (act === 'save') saveSide(side);
      else if (act === 'close') closeSide(side);
    });
    el.addEventListener('dragover', e => { e.preventDefault(); e.stopPropagation(); el.classList.add('drag'); $('#dropOverlay').classList.add('on'); });
    el.addEventListener('dragleave', () => el.classList.remove('drag'));
    el.addEventListener('drop', e => {
      e.preventDefault(); e.stopPropagation(); el.classList.remove('drag'); $('#dropOverlay').classList.remove('on'); dragDepth = 0;
      const fs = Array.from(e.dataTransfer.files);
      if (fs.length >= 2) loadPair([fs[0], fs[1]]); else if (fs[0]) loadFile(side, fs[0]);
    });
  });

  async function closeSide(side) {
    const s = S[side]; if (!s) return;
    if (s.dirty) {
      const ok = await modal({ title: '閉じる', html: `「${esc(s.name)}」には保存していない変更があります。閉じてもよろしいですか？`, buttons: [{ label: 'キャンセル', value: false }, { label: '閉じる', primary: true, value: true }] });
      if (!ok) return;
    }
    disposeSide(s); S[side] = null; changed([side]);
  }

  async function openEditor(side, line) {
    const s = S[side];
    if (s && s.noText) return toast('画像ファイルは編集できません');
    // 末尾の改行も編集欄に出す（出さないと、適用しただけで末尾の改行が消える）
    const txt = s ? s.lines.join('\n') + (s.finalNL !== false && s.lines.length ? '\n' : '') : '';
    const res = await modal({
      title: `${side ? '右' : '左'}のテキストを${s ? '編集' : '入力'}${s ? ' — ' + s.name : ''}`, wide: true,
      html: `<textarea id="edTa" spellcheck="false" wrap="off"></textarea><div class="muted" style="margin-top:6px">${s && s.kind !== 'text' ? '※ 抽出したテキストを編集します（元の文書は変更されません）。' : ''}「適用」で比較をやり直します。Tabキーでタブを入力できます。</div>`,
      buttons: [{ label: 'キャンセル', value: null }, { label: '適用', primary: true, value: m => $('#edTa', m).value }],
      onOpen: m => {
        const ta = $('#edTa', m); ta.value = txt; ta.focus();
        ta.addEventListener('keydown', e => {
          if (e.key === 'Tab' && !e.shiftKey && !e.ctrlKey) { e.preventDefault(); ta.setRangeText('\t', ta.selectionStart, ta.selectionEnd, 'end'); }
        });
        if (line != null) {
          let pos = 0; for (let i = 0; i < line && pos >= 0; i++) pos = txt.indexOf('\n', pos) + 1;
          ta.setSelectionRange(pos, pos);
          const lh = parseFloat(getComputedStyle(ta).lineHeight) || 18; ta.scrollTop = Math.max(0, line * lh - ta.clientHeight / 3);
        } else ta.setSelectionRange(0, 0);
      }
    });
    if (res == null || res === txt) return;
    TV.pushUndo();
    if (!S[side]) { S[side] = newTextSide(); }
    const ls = res === '' ? [] : res.split(/\r\n|\r|\n/);
    const endsNL = ls.length > 1 && ls[ls.length - 1] === '';
    if (endsNL) ls.pop();
    S[side].finalNL = endsNL || !ls.length;
    S[side].lines = ls;
    afterEdit(side);
    TV.compare(true);
  }

  async function saveSide(side) {
    const s = S[side]; if (!s) return;
    if (s.kind === 'binary') return toast('バイナリファイルは保存できません', true);
    const isText = s.kind === 'text';
    let enc = isText ? s.enc : 'utf-8';
    const body = s.lines.join(s.eol || '\r\n') + (s.finalNL && s.lines.length ? (s.eol || '\r\n') : '');
    if (!isText) {
      const ok = await modal({ title: '保存の確認', html: `「${esc(s.name)}」の文書そのものではなく、<b>取り出した文字だけ</b>をテキストファイル（UTF-8）として保存します。`, buttons: [{ label: 'キャンセル', value: false }, { label: 'テキストとして保存', primary: true, value: true }] });
      if (!ok) return;
    }
    // 元が英数字だけのファイルに日本語が入った → 文字コードを決めてもらう
    if (isText && s.asciiOnly && s.enc === 'utf-8' && /[^\x00-\x7F]/.test(body)) {
      const v = await modal({ title: '保存する文字コード', html: '元のファイルは英数字だけだったため、文字コードが決まっていません。<br>日本語を含めて保存する文字コードを選んでください。<br><span class="muted">Windows の設定ファイル（.ini / .bat など）は Shift_JIS が一般的です。</span>', buttons: [{ label: 'キャンセル', value: null }, { label: 'UTF-8', value: 'utf-8' }, { label: 'Shift_JIS', value: 'shift_jis' }] });
      if (!v) return;
      enc = v; s.enc = v;
    }
    if (isText && s.mixed && !s.mixedOk) {
      const ok = await modal({ title: '改行コードの確認', html: `このファイルは改行コードが混在していました（CRLF と LF など）。<br>保存すると、すべての行が <b>${Enc.EOLNAME[s.eol] || 'CRLF'}</b> に統一されます。<br><span class="muted">改行コードはファイル欄のプルダウンで変更できます。</span>`, buttons: [{ label: 'キャンセル', value: false }, { label: '統一して保存', primary: true, value: true }] });
      if (!ok) return;
      s.mixedOk = true;
    }
    let { bytes, unmapped } = Enc.encode(body, enc);
    if (unmapped) {
      const v = await modal({ title: '文字コードの確認', html: `${Enc.NAMES[enc]} で表せない文字が ${unmapped} 個あります（「?」に置き換わります）。<br>UTF-8 で保存しますか？`, buttons: [{ label: 'キャンセル', value: null }, { label: 'そのまま保存', value: 'keep' }, { label: 'UTF-8で保存', primary: true, value: 'utf8' }] });
      if (!v) return;
      if (v === 'utf8') { enc = 'utf-8'; bytes = Enc.encode(body, enc).bytes; }
    }
    const hadBom = s.bytes && s.bytes.length >= 2 && ((s.bytes[0] === 0xFF && s.bytes[1] === 0xFE) || (s.bytes[0] === 0xFE && s.bytes[1] === 0xFF));
    if (/^utf-16/.test(enc) && s.bytes && !hadBom) bytes = bytes.subarray(2); // 元にBOMがなければ付けない
    const name = isText ? (s.name === '(新規テキスト)' ? '新規テキスト.txt' : s.name) : baseName(s.name) + '_抽出テキスト.txt';
    const blob = new Blob([bytes], { type: 'application/octet-stream' });
    let saved = false;
    if (window.showSaveFilePicker) {
      try {
        const h = await window.showSaveFilePicker({ suggestedName: name });
        const w = await h.createWritable(); await w.write(blob); await w.close(); saved = true;
      } catch (e) { if (e && e.name === 'AbortError') return; }
    }
    if (!saved) download(name, blob);
    if (isText) { s.asciiOnly = s.asciiOnly && !/[^\x00-\x7F]/.test(body); s.orig = textSig(s); s.dirty = false; s.enc = enc; s.bytes = bytes; s.size = bytes.length; updateSlot(side); }
    toast(`保存しました（${Enc.NAMES[enc]}・${Enc.EOLNAME[s.eol] || 'CRLF'}）`);
  }

  /* ---------- tabs ---------- */
  function setTab(t) {
    if (app.tab === 'overlay' && t !== 'overlay') OV.deactivate();
    app.tab = t;
    $$('#tabs button').forEach(b => { const on = b.dataset.tab === t; b.classList.toggle('on', on); b.setAttribute('aria-selected', on); b.tabIndex = on ? 0 : -1; });
    $$('.tab').forEach(s => s.classList.toggle('on', s.id === 'tab-' + t));
    $('#slots').style.display = t === 'folder' ? 'none' : '';
    if (t === 'text') TV.activate();
    else if (t === 'page') PV.activate();
    else if (t === 'overlay') OV.activate();
  }
  $$('#tabs button').forEach(b => b.onclick = () => setTab(b.dataset.tab));
  // タブは矢印キーで切り替え
  $('#tabs').addEventListener('keydown', e => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const bs = $$('#tabs button'), i = bs.findIndex(b => b.dataset.tab === app.tab);
    const n = bs[(i + (e.key === 'ArrowRight' ? 1 : bs.length - 1)) % bs.length];
    e.preventDefault(); setTab(n.dataset.tab); n.focus();
  });
  $('#btnSettings').onclick = () => Settings.open();
  // 記号だけのボタンに、読み上げ用の名前を付ける
  $$('button[title]').forEach(b => { if (!b.hasAttribute('aria-label')) b.setAttribute('aria-label', b.title.replace(/\s*\(.*\)$/, '')); });

  $('#btnSwap').onclick = () => {
    S = [S[1], S[0]]; TV.resetHistory(); updateSlot(0); updateSlot(1);
    TV.invalidate(); PV.invalidate(0); PV.invalidate(1); OV.invalidate();
  };
  $('#btnClear').onclick = async () => {
    if (S.some(s => s && s.dirty)) {
      const ok = await modal({ title: 'すべて閉じる', html: '保存していない変更があります。閉じてもよろしいですか？', buttons: [{ label: 'キャンセル', value: false }, { label: '閉じる', primary: true, value: true }] });
      if (!ok) return;
    }
    S.forEach(disposeSide); S = [null, null]; changed([0, 1]);
  };

  /* ---------- global drag & drop ---------- */
  let dragDepth = 0;
  window.addEventListener('dragenter', e => { if (e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files')) { dragDepth++; $('#dropOverlay').classList.add('on'); } });
  window.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; $('#dropOverlay').classList.remove('on'); } });
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', async e => {
    e.preventDefault(); dragDepth = 0; $('#dropOverlay').classList.remove('on');
    const dt = e.dataTransfer; if (!dt) return;
    const ents = Array.from(dt.items || []).map(it => it.webkitGetAsEntry && it.webkitGetAsEntry()).filter(Boolean);
    if (ents.length && ents.every(en => en.isDirectory)) { setTab('folder'); return FD.dropFolders(dt); }
    const fs = Array.from(dt.files).filter((f, i) => !ents[i] || ents[i].isFile);
    if (!fs.length) return;
    if (app.tab === 'folder') setTab('text');
    if (fs.length >= 2) loadPair([fs[0], fs[1]]);
    else loadFile(!S[0] ? 0 : !S[1] ? 1 : 0, fs[0]);
  });

  /* ---------- keyboard ---------- */
  document.addEventListener('keydown', e => {
    if ($('#modal').classList.contains('on')) return;
    const inField = e.target.matches('input,select,textarea');
    if (app.tab === 'text') {
      if (e.altKey && e.key === 'ArrowDown') { e.preventDefault(); TV.next(); }
      else if (e.altKey && e.key === 'ArrowUp') { e.preventDefault(); TV.prev(); }
      else if (e.altKey && e.key === 'ArrowRight') { e.preventDefault(); TV.copyCur(0); }
      else if (e.altKey && e.key === 'ArrowLeft') { e.preventDefault(); TV.copyCur(1); }
      else if (e.key === 'F5') { e.preventDefault(); TV.compare(true); toast('再比較しました'); }
      else if (!inField && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); TV.undo(); }
      else if (!inField && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); TV.redo(); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') { e.preventDefault(); $('#searchBox').focus(); $('#searchBox').select(); }
      else if (e.key === 'F3') { e.preventDefault(); TV.find(); }
      else if (!inField && (e.key === 'n' || e.key === 'j')) TV.next();
      else if (!inField && (e.key === 'p' || e.key === 'k')) TV.prev();
    } else if (app.tab === 'page') {
      if (!inField && PV.onKey(e)) e.preventDefault();
    } else if (app.tab === 'overlay') {
      if (OV.onKey(e)) e.preventDefault();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'o') { e.preventDefault(); $('input[type=file]', slots[!S[0] ? 0 : !S[1] ? 1 : 0]).click(); }
  });
  window.addEventListener('beforeunload', e => { if (S.some(s => s && s.dirty)) { e.preventDefault(); e.returnValue = ''; } });

  /* ---------- help ---------- */
  $('#btnHelp').onclick = () => modal({
    title: 'ヘルプ', wide: true,
    html: `
<h4 style="margin-top:0">ファイルの読み込み</h4>
左右の欄にファイルをドロップ（2つまとめてドロップすると左右に入ります）。欄をクリックすると選択できます。<br>
対応形式: テキスト・ソースコード・CSV など（Shift_JIS / EUC-JP / JIS / UTF-8 / UTF-16 を自動判定）、PDF、Word(.docx)、Excel(.xlsx)、PowerPoint(.pptx)、画像（PNG / JPEG / GIF / BMP / WebP）。<br>
<span class="muted">DocuWorks文書(.xdw)・旧Office形式(.doc/.xls/.ppt)・TIFFは中身を読めないため、PDFや新しい形式に変換してから読み込んでください。</span>
<h4>テキスト比較（WinMerge相当）</h4>
<table>
<tr><td><kbd>Alt</kbd>+<kbd>↓</kbd> / <kbd>Alt</kbd>+<kbd>↑</kbd></td><td>次 / 前の差分へ（<kbd>N</kbd> / <kbd>P</kbd> でも可）</td></tr>
<tr><td><kbd>Alt</kbd>+<kbd>→</kbd> / <kbd>Alt</kbd>+<kbd>←</kbd></td><td>選択中の差分を右へ / 左へコピー</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Y</kbd></td><td>元に戻す / やり直し</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>F</kbd>、<kbd>F3</kbd></td><td>検索、次を検索</td></tr>
<tr><td><kbd>F5</kbd></td><td>再比較</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>O</kbd></td><td>ファイルを開く（左右のファイル欄は Tab で選んで Enter でも開けます）</td></tr>
<tr><td>行をダブルクリック</td><td>その行の位置で編集画面を開く</td></tr>
</table>
左端の細い帯は全体の差分位置です（クリック・ドラッグで移動）。<b style="color:#b3261e">赤</b>＝削除・変更前（行頭に −、文字に取り消し線）、<b style="color:#0550ae">青</b>＝追加・変更後（行頭に ＋、文字に下線）。紫の枠が選択中の差分です。縦線の印は、反対側で文字が追加・削除された位置です。数字が変わったときは差と増減率を表示します。<br>
行の折り返し・空白の記号表示・差分の単位（文字／単語）・文字の大きさは「設定」で変えられます。<br>
「保存」は元の文字コード・改行コードで保存します（欄のプルダウンで変更可）。PDF・Officeファイルは抽出テキストとして保存します。
<h4>ページ表示・注釈（DocuWorks Viewer相当）</h4>
左右の文書をページ単位で並べて表示します（スクロール連動）。ペン・蛍光マーカー・四角枠・付箋・日付印を書き込めます。<br>
選択ツールで注釈をクリック→ドラッグで移動、<kbd>Delete</kbd>で削除、付箋や日付印はダブルクリックで編集。注釈がないところをドラッグすると画面を動かせます。<kbd>Ctrl</kbd>+ホイールで拡大縮小。<br>
注釈はこのブラウザに自動保存されます（同じファイルを開くと復元）。保存しない設定や、保存データの確認・削除は「設定」からできます。他のPCへ持ち出すときは「注釈を保存」でファイルにしてください。日付印の種類・日付の書き方（和暦など）・大きさ・氏名は「設定」または「印設定」で変えられます。「印刷 / PDF」で注釈入りの印刷・PDF保存ができます。
<h4>重ね合わせ比較</h4>
PDF・画像のページを重ねて、変わった部分を色分けします（赤＝左にだけある、青＝右にだけある）。変更箇所はオレンジの枠と番号で示します。<br>
スキャン画像は開いたときに自動で位置と傾きを合わせます（「自動位置合わせ」で再実行）。細かなずれを差分にしたくないときは「ずれの許容」を増やしてください。「全ページの差分を調べる」で、どのページに変更があるか一覧できます。<kbd>←</kbd><kbd>→</kbd>でページ送り、<kbd>N</kbd>で次の変更箇所。
<h4>フォルダ比較</h4>
2つのフォルダを指定すると、同じ名前のファイルどうしを比べて「同一・相違・左のみ・右のみ」を一覧します。行をダブルクリックすると中身の比較に移ります。
<h4>プライバシー</h4>
<span class="muted">すべての処理はこのブラウザの中だけで行われ、ファイルが外部に送信されることはありません（ネットワーク接続なしで動作します）。</span>`
  });

  Object.assign(app, { resetDrag: () => { dragDepth = 0; }, loadFile, loadPair, newTextSide, afterEdit, openEditor, setTab, updateSlot, visualOnly });
  return app;
})();

/* init */
(function init() {
  App.updateSlot(0); App.updateSlot(1);
  TV.activate();
  // warm up pdf.js lazily
  setTimeout(() => PDF.lib().catch(() => { }), 500);
})();
