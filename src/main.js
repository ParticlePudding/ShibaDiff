/* アプリ本体：ファイル読み込み・ファイル欄・タブ・ドラッグ&ドロップ・キーボード */
let S = [null, null];

const App = (() => {
  const app = { tab: 'text', mode: 'file' };
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
        const info = {};
        s.kind = k; setText(s, await Office.extract(k, b, info));
        s.getPages = async () => (s._pages || (s._pages = Pages.fromText(s.lines, s.name)));
        // Word の変更履歴が残っている：比較は「すべて承諾した状態」の文字で行うので、削除された文字は比較に出ない。見落とさないよう知らせる
        // （ファイル欄とテキスト比較の状態表示にも出す）
        if (info.tracked) {
          s.tracked = info.tracked;
          toast(`「${s.name}」には変更履歴が残っています（挿入 ${info.tracked.ins}・削除 ${info.tracked.del}）。変更をすべて承諾した状態の文字で比較します（削除された文字は比較に出ません）`, false, 7000);
        }
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
    // 先に各画面へ「文書が変わった」ことを知らせてから表示を切り替える（逆だと、古い比較結果を新しい文書で描こうとして失敗する）
    const fromFolder = app.mode === 'folder';
    if (fromFolder) app.tab = 'text';
    changed([0, 1]);
    if (fromFolder) { setMode('file'); $('#btnBackFolder').hidden = false; }
    requestAnimationFrame(fitHdrNames); // ヘッダのボタンが増減すると名前の欄の幅が変わる
    return true;
  }

  function changed(sides) {
    TV.resetHistory();
    sides.forEach(updateSlot);
    TV.invalidate();
    PageMatch.invalidate();
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

  /* ---------- ヘッダのファイル名：左右の違う部分が見えるように縮める ---------- */
  // 1) 左右の名前の共通の先頭が長ければ「…」にして、違う部分から出す（例：…v3.pptx ／ …v4_提出版.pptx）
  // 2) それでも入らなければ、真ん中を「…」にする（先頭と、拡張子の前の版番号などの末尾を残す）
  const cps = t => Array.from(t);
  function hdrLabel(name, other) {
    if (!other || name === other) return null;
    const a = cps(name), b = cps(other); let p = 0;
    while (p < a.length && p < b.length && a[p] === b[p]) p++;
    if (p < 6) return null;
    while (p > 0 && /[0-9A-Za-z]/.test(a[p - 1])) p--; // v3 と v4 なら「v」から、12 と 13 なら数字の頭から出す
    return a.slice(p).join('');
  }
  let measureCtx = null;
  function textWidth(t, el) { measureCtx = measureCtx || document.createElement('canvas').getContext('2d'); measureCtx.font = getComputedStyle(el).font; return measureCtx.measureText(t).width; }
  // 先頭 head 文字 ＋「…」＋末尾 tail 文字で、幅 w に入る最長のもの
  function squeeze(a, w, el, pre, tailMin) {
    let lo = 1, hi = a.length - 1, best = null;
    while (lo <= hi) {
      const n = (lo + hi) >> 1, tail = Math.max(tailMin, Math.ceil(n * 0.4)), head = n - tail;
      if (head < 0) { hi = n - 1; continue; }
      const c = pre + a.slice(0, head).join('') + '…' + a.slice(a.length - tail).join('');
      if (textWidth(c, el) <= w) { best = c; lo = n + 1; } else hi = n - 1;
    }
    return best || pre + '…' + a.slice(-tailMin).join('');
  }
  function fitName(name, other, el, w) {
    if (textWidth(name, el) <= w) return name;
    const diff = hdrLabel(name, other);
    const ext = (/\.[^.]{1,6}$/.exec(name) || [''])[0], extN = cps(ext).length;
    if (diff != null) {
      // 共通の先頭は「…」にして、違う部分から出す。入らなければ、違う部分の頭と拡張子を残す
      if (textWidth('…' + diff, el) <= w) return '…' + diff;
      const d = cps(diff), body = d.length - extN;
      // 違う部分の頭を2文字以上出せるなら拡張子も残す。出せないほど狭ければ拡張子は省き、違う部分の頭を出す
      for (let k = body; k >= 2; k--) { const c = '…' + d.slice(0, k).join('') + '…' + ext; if (textWidth(c, el) <= w) return c; }
      for (let k = body; k >= 1; k--) { const c = '…' + d.slice(0, k).join('') + '…'; if (textWidth(c, el) <= w) return c; }
      return '…' + d[0];
    }
    return squeeze(cps(name), w, el, '', Math.max(extN + 3, 4));
  }
  function fitHdrNames() {
    // 1) 左右とも全体を入れて、それぞれに割り当てられた幅を測る 2) その幅に収めた名前を入れる（片側ずつだと、もう片側の幅が変わるため）
    const items = [0, 1].map(side => {
      const hf = $(`#hdrFiles .hf[data-side="${side}"]`), nm = $('.nm', hf), s = S[side];
      const dirty = s && hf.dataset.dirty === '1' ? '<span class="dirty" title="未保存の変更があります">● </span>' : '';
      if (s) nm.innerHTML = dirty + esc(s.name); else nm.textContent = 'ファイルを選択';
      return { side, nm, s, dirty };
    });
    for (const it of items) { if (it.s) { it.over = it.nm.scrollWidth > it.nm.clientWidth + 1; it.w = it.nm.clientWidth - (it.dirty ? textWidth('● ', it.nm) : 0); } }
    for (const it of items) if (it.s && it.over) it.nm.innerHTML = it.dirty + esc(fitName(it.s.name, S[1 - it.side] && S[1 - it.side].name, it.nm, it.w - 2));
  }
  let hdrT = 0;
  window.addEventListener('resize', () => { clearTimeout(hdrT); hdrT = setTimeout(fitHdrNames, 120); });

  /* ---------- file slot UI ---------- */
  const KIND = { pdf: 'PDF', docx: 'Word', xlsx: 'Excel', pptx: 'PowerPoint', image: '画像', binary: 'バイナリ', text: 'テキスト' };
  function updateSlot(side) {
    const el = slots[side], s = S[side];
    // ヘッダのファイル名（1行表示）
    const hf = $(`#hdrFiles .hf[data-side="${side}"]`);
    hf.classList.toggle('empty', !s);
    hf.dataset.dirty = s && s.dirty ? '1' : '';
    hf.title = s ? `${side ? '右' : '左'}：${s.name}（クリックでファイル欄を開く／たたむ）` : `${side ? '右' : '左'}のファイルを選択`;
    autoSlots(); fitHdrNames();
    el.classList.toggle('loaded', !!s);
    $('.fname', el).innerHTML = s ? `${s.dirty ? '<span class="dirty" title="未保存の変更があります">● </span>' : ''}${esc(s.name)}` : 'ファイルをドロップ、またはクリックして選択';
    $('.fname', el).title = s ? s.name : '';
    const info = $('.slot-info', el);
    if (!s) { info.innerHTML = `<span class="meta"></span><button data-act="edit" title="テキストを直接入力・貼り付け"><i data-i="type"></i>テキストを入力</button>`; return; }
    let meta = `${KIND[s.kind] || s.kind}`;
    if (s.size) meta += `・${fmtSize(s.size)}`;
    if (s.mtime && s.bytes) meta += `・${fmtDate(s.mtime)}`;
    if (s.kind === 'pdf') meta += `・${s.pageCount}ページ`;
    let html = '';
    if (s.asciiOnly) meta += '・英数字のみ';
    if (s.tracked) meta += '・変更履歴あり';
    if (!s.lines.length || (s.lines.length === 1 && s.finalNL === false)) meta += '・改行なし';
    if (s.kind === 'text' || s.kind === 'binary') {
      html += `<select data-act="enc" title="文字コード（変更すると読み直します）">${Enc.LIST.map(e => `<option value="${e}"${e === s.enc ? ' selected' : ''}>${Enc.NAMES[e]}</option>`).join('')}</select>`;
      html += `<select data-act="eol" title="保存時の改行コード">${['\r\n', '\n', '\r'].map(e => `<option value="${encodeURIComponent(e)}"${e === s.eol ? ' selected' : ''}>${Enc.EOLNAME[e]}</option>`).join('')}</select>`;
    }
    html += `<span class="meta" title="${esc(meta)}">${esc(meta)}</span><span class="grow"></span>`;
    if (!s.noText) html += `<button data-act="edit" title="テキストを編集（行をダブルクリックでも開きます）"><i data-i="pencil"></i>編集</button><button data-act="save" title="${s.kind === 'text' ? '保存' : 'テキストとして保存'}"><i data-i="save"></i>保存</button>`;
    html += `<button data-act="close" title="閉じる"><i data-i="x"></i></button>`;
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
  /* ---------- ファイル比較／フォルダ比較の切り替え ---------- */
  function setMode(m) {
    if (m === app.mode) return;
    app.mode = m; document.body.dataset.mode = m;
    $$('#modeSw button').forEach(b => { const on = b.dataset.mode === m; b.classList.toggle('on', on); b.setAttribute('aria-pressed', on); });
    if (m === 'folder') {
      if (app.tab === 'overlay') OV.deactivate();
      $$('.tab').forEach(s => s.classList.toggle('on', s.id === 'tab-folder')); placeExitFull();
      $('#btnBackFolder').hidden = true;
    } else { setTab(app.tab); requestAnimationFrame(fitHdrNames); }
  }
  $$('#modeSw button').forEach(b => b.onclick = () => setMode(b.dataset.mode));
  $('#btnBackFolder').onclick = () => setMode('folder');

  /* ---------- ファイル欄の開閉（左右とも読み込んだら自動でたたむ。どちらかが空なら開く） ---------- */
  let bothBefore = false;
  function showSlots(open) {
    document.body.classList.toggle('slots-closed', !open);
    $('#btnSlots').setAttribute('aria-expanded', open);
  }
  function autoSlots() {
    const both = !!(S[0] && S[1]);
    if (both && !bothBefore) showSlots(false);
    if (!both) showSlots(true);
    bothBefore = both;
  }
  $('#btnSlots').onclick = () => showSlots(document.body.classList.contains('slots-closed'));
  $$('#hdrFiles .hf').forEach(b => b.onclick = () => {
    const side = +b.dataset.side;
    if (!S[side]) $('input[type=file]', slots[side]).click();
    else showSlots(document.body.classList.contains('slots-closed'));
  });

  /* ---------- 全画面表示（ヘッダとファイル欄を隠し、ブラウザも全画面にする） ---------- */
  // 「全画面を終える」は、今見ているタブ（フォルダ比較ではフォルダ比較）のツールバーの右端に入れる。
  // 画面の右上に浮かせると、ツールバーの右端のボタン（レポートなど）に重なって押せなくなるため
  function placeExitFull() {
    const btn = $('#btnExitFull');
    if (!document.body.classList.contains('fullview')) return;
    const sec = $('.tab.on'), bar = sec && $('.toolbar', sec);
    if (bar && btn.parentElement !== bar) bar.appendChild(btn);
  }
  function setFull(on) {
    document.body.classList.toggle('fullview', on);
    $('#btnExitFull').hidden = !on;
    placeExitFull();
    try {
      if (on && !document.fullscreenElement && document.documentElement.requestFullscreen) document.documentElement.requestFullscreen().catch(() => { });
      if (!on && document.fullscreenElement) document.exitFullscreen().catch(() => { });
    } catch (e) { }
    window.dispatchEvent(new Event('resize'));
  }
  $('#btnFull').onclick = () => setFull(true);
  $('#btnExitFull').onclick = () => setFull(false);
  // ブラウザの全画面を Esc で抜けたら、ヘッダも戻す
  document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && document.body.classList.contains('fullview')) setFull(false); });

  function setTab(t) {
    if (t === 'folder') return setMode('folder'); // 以前の呼び方との互換
    if (app.mode !== 'file') { app.tab = t; return setMode('file'); }
    if (app.tab === 'overlay' && t !== 'overlay') OV.deactivate();
    app.tab = t;
    $$('#tabs button').forEach(b => { const on = b.dataset.tab === t; b.classList.toggle('on', on); b.setAttribute('aria-selected', on); b.tabIndex = on ? 0 : -1; });
    $$('.tab').forEach(s => s.classList.toggle('on', s.id === 'tab-' + t)); placeExitFull();
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
  // 狭い画面（760px 未満）ではツールバーが横スクロールになる。続きがある側の端に目印（ぼかしと矢印）を出す。
  // スクロールバーは出していないので、目印がないと右に隠れたボタン（レポート・印刷など）に気づけない
  $$('.toolbar').forEach(bar => {
    const sync = () => {
      const max = bar.scrollWidth - bar.clientWidth;
      bar.classList.toggle('more-l', bar.scrollLeft > 2); bar.classList.toggle('more-r', max - bar.scrollLeft > 2);
    };
    bar.addEventListener('scroll', () => { sync(); $$('details.pop[open]', bar).forEach(d => { d.open = false; }); }, { passive: true });
    new ResizeObserver(sync).observe(bar);
  });
  // 記号だけのボタン（文字のないボタン）に、読み上げ用の名前を付ける。文字のあるボタンには付けない：
  // 見えている文字がそのまま名前になる。title の長い説明で上書きすると、見えている名前と読み上げの名前が食い違う（WCAG 2.5.3）
  $$('button[title]').forEach(b => { if (!b.hasAttribute('aria-label') && !b.textContent.trim()) b.setAttribute('aria-label', b.title.replace(/\s*\(.*\)$/, '')); });

  $('#btnSwap').onclick = () => {
    // 変更点のコメントは左右の組（左のキー||右のキー）に付く。入れ替えると別の組になり、付けたコメントは表示されなくなるので知らせる
    // （消えてはいない。もう一度入れ替えると戻る）
    const had = S[0] && S[1] ? Object.keys(Notes.all()).length : 0;
    S = [S[1], S[0]]; TV.resetHistory(); updateSlot(0); updateSlot(1);
    TV.invalidate(); PageMatch.invalidate(); PV.invalidate(0); PV.invalidate(1); OV.invalidate();
    if (had) toast(`左右を入れ替えました。変更点のコメント ${had} 件は、入れ替える前の左右の組に付いているため表示されません（もう一度入れ替えると戻ります）`, false, 7000);
  };
  $('#btnClear').onclick = async () => {
    if (S.some(s => s && s.dirty)) {
      const ok = await modal({ title: 'すべて閉じる', html: '保存していない変更があります。閉じてもよろしいですか？', buttons: [{ label: 'キャンセル', value: false }, { label: '閉じる', primary: true, value: true }] });
      if (!ok) return;
    }
    S.forEach(disposeSide); S = [null, null]; changed([0, 1]);
  };

  /* ---------- global drag & drop ---------- */
  // 画面の左半分・右半分を、それぞれ左・右の読み込み先として示す（2つ以上なら「左右に読み込む」）
  let dragDepth = 0, dropSide = 0;
  const dov = $('#dropOverlay');
  const isFileDrag = e => e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files');
  function hotZone(e) {
    const many = e.dataTransfer && e.dataTransfer.items && e.dataTransfer.items.length >= 2;
    dov.classList.toggle('both', !!many);
    dropSide = e.clientX < window.innerWidth / 2 ? 0 : 1;
    $$('.dz[data-side]', dov).forEach(z => z.classList.toggle('hot', +z.dataset.side === dropSide));
    $('.dz-both', dov).classList.toggle('hot', !!many);
  }
  window.addEventListener('dragenter', e => { if (isFileDrag(e)) { dragDepth++; dov.classList.add('on'); hotZone(e); } });
  window.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; dov.classList.remove('on'); } });
  window.addEventListener('dragover', e => { e.preventDefault(); if (isFileDrag(e)) hotZone(e); });
  window.addEventListener('drop', async e => {
    e.preventDefault(); dragDepth = 0; dov.classList.remove('on');
    const dt = e.dataTransfer; if (!dt) return;
    const side = e.clientX < window.innerWidth / 2 ? 0 : 1;
    const ents = Array.from(dt.items || []).map(it => it.webkitGetAsEntry && it.webkitGetAsEntry()).filter(Boolean);
    if (ents.length && ents.every(en => en.isDirectory)) { setMode('folder'); return FD.dropFolders(dt, side); }
    const fs = Array.from(dt.files).filter((f, i) => !ents[i] || ents[i].isFile);
    if (!fs.length) return;
    if (fs.length >= 2) return loadPair([fs[0], fs[1]]);
    if (app.mode === 'folder') { setMode('file'); }
    loadFile(side, fs[0]);
  });

  /* ---------- keyboard ---------- */
  document.addEventListener('keydown', e => {
    if ($('#modal').classList.contains('on')) return;
    const inField = e.target.matches('input,select,textarea');
    // 全画面表示は Esc で終える（ブラウザの全画面が使えなかったとき用）
    if (e.key === 'Escape' && document.body.classList.contains('fullview')) { e.preventDefault(); setFull(false); return; }
    if (app.mode === 'folder') return;
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
画面の左半分にドロップすると左、右半分にドロップすると右に入ります（ドラッグ中に、入る側を強調して示します。2つまとめてドロップすると左右に入ります）。上のファイル名をクリックしても選択できます。<br>
左右とも読み込むと、文字コード・保存・閉じるなどのファイル欄は自動でたたまれます（ヘッダ右のボタンで開く）。「全画面」でヘッダも隠せます（<kbd>Esc</kbd> で戻る）。<br>
対応形式: テキスト・ソースコード・CSV など（Shift_JIS / EUC-JP / JIS / UTF-8 / UTF-16 を自動判定）、PDF、Word(.docx)、Excel(.xlsx)、PowerPoint(.pptx)、画像（PNG / JPEG / GIF / BMP / WebP）。<br>
<span class="muted">DocuWorks文書(.xdw)・旧Office形式(.doc/.xls/.ppt)・TIFFは中身を読めないため、PDFや新しい形式に変換してから読み込んでください。</span><br>
Word はヘッダー・フッター・脚注・コメントも、Excel は数式（コピーした数式を含む）と非表示のシートも比較します。Word に変更履歴が残っているときは通知し、変更をすべて承諾した状態の文字で比較します。
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
<h4>変更点へのコメント（確認済・要確認・ひとこと）</h4>
見つけた変更点ごとに、確認の状態（未確認・確認済・要確認）と、ひとこと（理由・指示・確認結果）を付けられます。
テキスト比較ではツールバーの「変更点」で一覧を開き、差分を選んで書きます。重ね合わせでは右のパネルの一覧か、画像の枠のクリックで選びます。ページ表示・注釈では「変更箇所」で重ね合わせの枠を表示し、枠の番号をクリックして書きます。<br>
コメントは、各レポート・変更点一覧の CSV・「注釈を保存」のファイルに載ります。記入者名は「設定」で入れておけます。
<h4>ページ表示・注釈（DocuWorks Viewer相当）</h4>
左右の文書をページ単位で並べて表示します（スクロール連動）。ペン・蛍光マーカー・四角枠・付箋を書き込めます。<br>
「変更箇所」をオンにすると、重ね合わせで見つけた変更箇所が番号付きの枠で出ます（番号をクリックしてコメント）。<br>
付箋はクリックした位置に入力欄が出ます（<kbd>Ctrl</kbd>+<kbd>Enter</kbd> で貼る）。1枚貼ると選択ツールに戻ります。マーカーは黄色、枠は青が既定です（道具ごとに色を覚えます）。<br>
選択ツールで注釈をクリック→ドラッグで移動、<kbd>Delete</kbd>で削除、付箋はダブルクリックで編集。<kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Y</kbd> で注釈の取り消し・やり直し。注釈がないところをドラッグすると画面を動かせます。<kbd>Ctrl</kbd>+ホイールで拡大縮小。<br>
注釈とコメントは、既定ではこのブラウザに保存しません（ファイルを閉じると消えます）。残すときは「注釈を保存」でファイルにするか、「設定」で自動保存をオンにしてください。「レポート」で注釈・変更箇所・コメントを HTML に、「印刷 / PDF」で注釈入りの印刷・PDF保存ができます。
<h4>重ね合わせ比較</h4>
PDF・画像のページを重ねて、変わった部分を色分けします（赤＝左にだけある、青＝右にだけある、紫＝形は同じで色が変わった）。色の比較は「色の違いも検出」で切り替えられます（紙のスキャンでは最初はオフ）。変更箇所はオレンジの枠と番号で示します。右側のパネルには、選んだ表示方法で使う項目だけが出ます。<br>
スキャン画像は開いたときに自動で位置と傾きを合わせます（「自動位置合わせ」で再実行）。細かなずれを差分にしたくないときは「ずれの許容」を増やしてください。A1・A0 などの大きな図面は「解像度」で軽量／精細を選べます。<br>
途中でページが挿入・削除されていても、似ているページどうしを自動で組にします（ページ送り・一括チェック・ページ表示の連動に使います）。スキャンで左右のページ数が同じときは、同じページ番号どうしを組にします。ページの入れ替え・差し替えがあるときは、右のパネルの「見た目で対応を調べ直す」を押してください。「全ページの差分を調べる」で、どのページに変更があるか、追加・削除されたページを一覧できます。「レポート」で差分画像と一覧を HTML に出力できます。<br>
操作：ホイール＝縦スクロール、<kbd>Shift</kbd>+ホイール＝横スクロール、<kbd>Ctrl</kbd>+ホイール＝拡大・縮小。「移動」（<kbd>H</kbd>）ではドラッグで表示位置を動かし、ホイールで拡大・縮小します。<kbd>PageUp</kbd><kbd>PageDown</kbd>（<kbd>←</kbd><kbd>→</kbd>）でページ送り、<kbd>N</kbd>で次の変更箇所、点滅の手動切り替えは画像のクリックか <kbd>Space</kbd>。<br>表示方法：ツールバーの「1ページ」ボタンは1組ずつ、「全ページ」ボタンは全ページを縦に並べてスクロールで見られます（見えているページだけを描くので、ページ数が多くても軽く動きます。全ページ表示でも <kbd>PageUp</kbd><kbd>PageDown</kbd> で前後のページへ移動し、右のパネルの結果・位置合わせは画面の上のほうにあるページが対象です）。
<h4>フォルダ比較</h4>
ヘッダ左の「フォルダ比較」に切り替えて使います。2つのフォルダを指定すると、同じ名前のファイルどうしを比べて「同一・相違・左のみ・右のみ」を一覧します。行をダブルクリック（または <kbd>↑</kbd><kbd>↓</kbd> で選んで <kbd>Enter</kbd>）すると中身の比較に移り、「← フォルダ一覧」で一覧に戻れます。一覧は CSV・HTMLレポートに出力できます。
<h4>プライバシー</h4>
<span class="muted">すべての処理はこのブラウザの中だけで行われ、ファイルが外部に送信されることはありません（ネットワーク接続なしで動作します）。</span>`
  });

  Object.assign(app, { resetDrag: () => { dragDepth = 0; }, setMode, showSlots, setFull, loadFile, loadPair, newTextSide, afterEdit, openEditor, setTab, updateSlot, visualOnly });
  return app;
})();

/* init */
(function init() {
  App.updateSlot(0); App.updateSlot(1);
  TV.activate();
  // warm up pdf.js lazily
  setTimeout(() => PDF.lib().catch(() => { }), 500);
})();
