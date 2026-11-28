'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
/* 文字の並ぶ向きを変える制御文字（RLO・LRO・埋め込み・分離：U+202A〜202E、U+2066〜2069）は、目に見えないまま、後ろの文字を逆順に見せる
   （「報告書exe.txt」に見える名前が、実は「報告書txt.exe」など）。名前や本文が別物に見えないよう、画面・レポートに出すときは
   見える形（[U+202E]）に置き換える。ファイルの中身・保存するときの名前・パッチには手を付けない */
const BIDI_CTL = /[\u202A-\u202E\u2066-\u2069]/g;
const showCtl = s => String(s).replace(BIDI_CTL, c => `[U+${c.charCodeAt(0).toString(16).toUpperCase()}]`);
const esc = s => showCtl(s).replace(/[&<>"]/g, c => c === '&' ? '&amp;' : c === '<' ? '&lt;' : c === '>' ? '&gt;' : '&quot;');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const nextFrame = () => new Promise(r => requestAnimationFrame(() => r()));

function fmtSize(n) {
  if (n == null) return '';
  if (n < 1024) return n + ' B';
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
  return (n / 1024 / 1024).toFixed(1) + ' MB';
}
function fmtDate(t) {
  if (!t) return '';
  const d = new Date(t), p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}/${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function fmtNum(n) { return n.toLocaleString('ja-JP'); }

let toastTimer = 0;
function toast(msg, isErr = false, ms = 2600) {
  const t = $('#toast');
  if (!msg) { clearTimeout(toastTimer); t.className = ''; t.textContent = ''; return; } // 空なら、出ている通知を消す（閉じたファイルについての通知を残さない）
  t.setAttribute('aria-live', isErr ? 'assertive' : 'polite'); // 読み上げ：誤りはすぐに、ふつうの通知は区切りのよいところで
  t.textContent = showCtl(msg); t.className = 'on' + (isErr ? ' err' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.className = '', isErr ? Math.max(ms, 5000) : ms);
}
let busyCount = 0;
function busy(on, msg) {
  busyCount = Math.max(0, busyCount + (on ? 1 : -1));
  // 読み上げには、始まったときの文だけを伝える（#busyLive）。進み具合（n / m など）は #busyMsg に直接書かれ、読み上げない
  // （進み具合まで読み上げると、数千ファイルの読み込みで読み上げが止まらなくなる）
  if (msg) { $('#busyMsg').textContent = msg; if (on) $('#busyLive').textContent = msg; }
  $('#busy').classList.toggle('on', busyCount > 0);
}
// opt.onCancel を渡すと、「処理中」の表示に「中止」ボタンを出す（押すと onCancel を呼ぶ。止め方は呼び出し側で決める）。
// 中止できる処理が重なっているときは、ボタンはどれかが残っている間は出したままにし、押されたら残っている分をすべて中止する
const busyCancels = new Set();
async function withBusy(msg, fn, opt = {}) {
  const btn = $('#busyCancel');
  busy(true, msg);
  if (opt.onCancel) { busyCancels.add(opt.onCancel); btn.hidden = false; btn.onclick = () => Array.from(busyCancels).forEach(f => f()); }
  await nextFrame(); await nextFrame();
  try { return await fn(); } finally {
    if (opt.onCancel) { busyCancels.delete(opt.onCancel); if (!busyCancels.size) { btn.hidden = true; btn.onclick = null; } }
    busy(false);
  }
}

/* modal: クリックしたボタンの value で解決する Promise を返す。
   キーボード操作に配慮：開いたらダイアログ内へフォーカスを移し、Tab はダイアログ内だけを巡回、閉じたら元の位置に戻す。
   ダイアログの要素（#modal）は1つを使い回す。開いている間に別のダイアログが開かれたら（設定の中の確認、
   ヘルプを開いたままファイルをドロップしたときのパスワード入力など）、下のダイアログの中身を、入力中の値や
   イベントごと退避して上に重ね、上を閉じたら元に戻す（下のダイアログの Promise とキー操作を置き去りにしない） */
const modalStack = [];
function modal({ title, html, buttons = [{ label: '閉じる', value: null }], onOpen, wide, guard }) {
  return new Promise(resolve => {
    const m = $('#modal'), dlg = $('.dlg', m), h3 = $('h3', m), bodyEl = $('.body', m), foot = $('.foot', m);
    const prevFocus = document.activeElement;
    const under = modalStack[modalStack.length - 1];
    if (under) under.suspend();
    const head = () => { dlg.style.width = wide ? 'min(1100px,96vw)' : ''; h3.textContent = showCtl(title); };
    dlg.setAttribute('role', 'dialog'); dlg.setAttribute('aria-modal', 'true');
    h3.id = 'dlgTitle'; dlg.setAttribute('aria-labelledby', 'dlgTitle');
    head();
    bodyEl.innerHTML = html;
    foot.innerHTML = '';
    let closed = false, saved = null;
    const me = {
      // 上に別のダイアログが重なる間：中身の要素をそのまま持っておく（作り直さないので、入力中の値もイベントも残る）
      suspend() {
        saved = { body: Array.from(bodyEl.childNodes), foot: Array.from(foot.childNodes), top: bodyEl.scrollTop, focus: dlg.contains(document.activeElement) ? document.activeElement : null };
        document.removeEventListener('keydown', onKey, true);
      },
      resume() {
        head(); bodyEl.replaceChildren(...saved.body); foot.replaceChildren(...saved.foot); bodyEl.scrollTop = saved.top;
        document.addEventListener('keydown', onKey, true);
        const f = saved.focus || $('button.primary', foot) || focusables()[0]; saved = null;
        if (f && f.focus) f.focus();
      }
    };
    const close = v => {
      if (closed) return; closed = true;
      document.removeEventListener('keydown', onKey, true);
      const i = modalStack.indexOf(me), top = i === modalStack.length - 1;
      if (i >= 0) modalStack.splice(i, 1);
      if (top) {
        const below = modalStack[modalStack.length - 1];
        if (below) below.resume();
        else { m.classList.remove('on'); if (prevFocus && prevFocus.focus && document.contains(prevFocus)) prevFocus.focus(); }
      }
      resolve(v);
    };
    for (const b of buttons) {
      const el = document.createElement('button');
      el.type = 'button'; el.textContent = b.label; if (b.primary) el.className = 'primary';
      el.onclick = () => close(typeof b.value === 'function' ? b.value(m) : b.value);
      foot.appendChild(el);
    }
    const focusables = () => $$('button,input,select,textarea,a[href],[tabindex]:not([tabindex="-1"])', dlg).filter(e => !e.disabled && e.offsetParent !== null);
    const onKey = e => {
      if (e.key === 'Escape') {
        e.preventDefault(); e.stopPropagation();
        // guard：Esc で閉じてよいかを返す関数（入力した内容があるときに確かめる）。確かめている間は、上に確認のダイアログが重なる
        if (guard) Promise.resolve(guard(m)).then(ok => { if (ok) close(null); }); else close(null);
        return;
      }
      if (e.key === 'Tab') {
        const f = focusables(); if (!f.length) return;
        const i = f.indexOf(document.activeElement);
        if (e.shiftKey && (i <= 0)) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && (i === f.length - 1 || i < 0)) { e.preventDefault(); f[0].focus(); }
      }
    };
    document.addEventListener('keydown', onKey, true);
    modalStack.push(me);
    m.classList.add('on');
    // 中身の初期化で例外が出たら、開いたままにせず閉じる（閉じられないダイアログが modalStack に残らないように）
    try { if (onOpen) onOpen(m, close); } catch (e) { console.error(e); close(null); return; }
    if (!dlg.contains(document.activeElement)) {
      const first = $('textarea,input:not([type=checkbox]),select', bodyEl) || $('button.primary', foot) || focusables()[0];
      if (first) first.focus();
    }
  });
}
/* パスワードの入力：伏せ字の1行の入力欄。Enter で確定する。入力した値は返すだけで、どこにも保存しない */
function askPassword(title, label = 'パスワード') {
  return modal({
    title,
    html: `<label class="pw-row"><span>${esc(label)}</span><input type="password" id="askPw" autocomplete="off" autocapitalize="off" spellcheck="false"></label>` +
      `<label class="pw-show"><input type="checkbox" id="askPwShow">入力した文字を表示する</label>`,
    buttons: [{ label: 'キャンセル', value: null }, { label: 'OK', primary: true, value: m => $('#askPw', m).value }],
    onOpen: m => {
      const inp = $('#askPw', m);
      $('#askPwShow', m).onchange = e => { inp.type = e.target.checked ? 'text' : 'password'; };
      inp.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); $('.foot button.primary', m).click(); } });
      inp.focus();
    }
  }).then(v => { const el = $('#askPw'); if (el) el.value = ''; return v; }); // 閉じたあとの画面の中に、入力した値を残さない
}

function download(name, data, type = 'application/octet-stream') {
  const blob = data instanceof Blob ? data : new Blob([data], { type });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

const store = {
  get(k, def) { try { const v = localStorage.getItem('doccmp:' + k); return v == null ? def : JSON.parse(v); } catch (e) { return def; } },
  set(k, v) { try { localStorage.setItem('doccmp:' + k, JSON.stringify(v)); } catch (e) { /* quota or disabled */ } },
  del(k) { try { localStorage.removeItem('doccmp:' + k); } catch (e) { } }
};

function b64ToBytes(b64) {
  const s = atob(b64), u = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i);
  return u;
}
/* PDFの抽出文字に混ざる「見た目が同じ別の文字」（康熙部首・CJK部首補助・互換漢字など）を通常の文字にそろえる */
// CJK部首補助（U+2E80–2EFF）は NFKC では通常の漢字にならない（例：⻭ U+2EED → 歯、⻑ → 長）。
// Unicode の EquivalentUnifiedIdeograph.txt から作った対応表で置き換える
const RADICAL_SRC = '⺁⺂⺃⺄⺅⺆⺇⺈⺉⺊⺋⺌⺍⺎⺏⺐⺑⺒⺓⺔⺕⺖⺗⺘⺙⺛⺜⺝⺞⺟⺠⺡⺢⺣⺤⺥⺦⺧⺨⺩⺪⺫⺬⺭⺮⺯⺰⺱⺲⺳⺴⺵⺶⺷⺸⺹⺺⺻⺼⺽⺾⺿⻀⻁⻂⻃⻄⻅⻆⻇⻈⻉⻊⻋⻌⻍⻎⻏⻐⻑⻒⻓⻔⻕⻖⻗⻘⻙⻚⻛⻜⻝⻞⻟⻠⻡⻢⻣⻤⻥⻦⻧⻨⻩⻪⻫⻬⻭⻮⻯⻰⻱⻲⻳', RADICAL_DST = '厂乛乚乙亻冂𠘨刀刂卜㔾小小兀尣尢𡯂巳幺彑𫜹忄心扌攵旡日月歺母民氵氺灬爫爫丬牛犭王𤴔目示礻𥫗糹纟罓罒㓁冗𦉫羊𦍌𦍋耂肀聿肉𦥑艹艹艹虎衤覀西见角𧢲讠贝𧾷车辶辶辶邑钅長镸长门𨸏阝雨青韦页风飞食𩙿飠饣𩠐马骨鬼鱼鸟卤麦黄黾斉齐歯齿竜龙龜亀龟';
const RADICAL_MAP = (() => { const m = new Map(), a = Array.from(RADICAL_SRC), b = Array.from(RADICAL_DST); a.forEach((c, i) => m.set(c, b[i])); return m; })();
// 康熙部首（U+2F00–2FDF）は NFKC で漢字になるが、旧字体になるものがある（⼾ → 戶、⿊ → 黑）。日本語のフォントでは新字体の形で
// 描かれており、Chrome の印刷で作った PDF は「戸」「黒」の文字情報としてこの部首の符号を持つので、日本の字体に直す
const KANGXI_JP = { '\u2F3E': '戸', '\u2FC8': '黄', '\u2FCA': '黒', '\u2FD2': '歯', '\u2FAD': '青' };
function normCJK(s) {
  return s.replace(/[\u2E80-\u2FDF\uF900-\uFAFF\u2027]/g, c => (c === '\u2027' ? '・' : KANGXI_JP[c] || RADICAL_MAP.get(c) || c.normalize('NFKC')));
}
/* 「全角・半角を区別しない」：文字の幅の違いだけをそろえる（全角の英数字・記号 ↔ 半角、半角カナ ↔ 全角カナ、全角の空白 ↔ 半角の空白）。
   NFKC を文字列全体にかけると、上付き・下付き（³ ₂）、丸数字（①）、組文字（㎛ ㈱）、ローマ数字（Ⅲ）まで同じ文字になり、
   10³ と 103 のような値の違いを見落とすので、半角・全角形の範囲（U+FF00–FFEF）と全角の空白だけにかける */
function foldWidth(s) { return s.replace(/[\uFF00-\uFFEF\u3000]+/g, m => m.normalize('NFKC')); }
/* 注釈・コメントのうち、まだファイルに保存していない（ブラウザにも保存しない設定の）書き込みがあるかどうか。
   ページを閉じる・再読み込みするときの確認に使う。注釈ファイルへの保存・レポート・印刷で出力したら消す */
const Unsaved = {
  on: false, told: false,
  mark() {
    this.on = true;
    // 最初に書いたときに、保存されないことを一度だけ知らせる（ほかの通知が出ているときは、次の機会に回す）
    if (!this.told) setTimeout(() => {
      if (this.told || !this.on || $('#toast').classList.contains('on')) return;
      this.told = true;
      toast('注釈・コメントは、このブラウザには保存しません。残すときは、ページ表示の「注釈を保存」でファイルに保存してください（「設定」で、ブラウザに保存するようにもできます）', false, 8000);
    }, 60);
  },
  clear() { this.on = false; }
};
// 押した状態を色（.on）で示すボタン：読み上げ用の状態（aria-pressed）も合わせる
function setOn(b, on) { b.classList.toggle('on', on); b.setAttribute('aria-pressed', on); }
function extOf(name) { const m = /\.([^.\\/]+)$/.exec(name || ''); return m ? m[1].toLowerCase() : ''; }
function baseName(name) { return (name || '').replace(/\.[^.\\/]+$/, ''); }

/* ツールバーのポップアップ（details.pop）は、外側をクリックするか Esc で閉じる。Tab でフォーカスが外へ出たときも閉じる（開いたまま残さない） */
document.addEventListener('focusout', e => { const d = e.target.closest && e.target.closest('details.pop[open]'); if (d && e.relatedTarget && !d.contains(e.relatedTarget)) d.open = false; });
document.addEventListener('click', e => { document.querySelectorAll('details.pop[open]').forEach(d => { if (!d.contains(e.target)) d.open = false; }); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') document.querySelectorAll('details.pop[open]').forEach(d => { d.open = false; d.querySelector('summary').focus(); }); });
// 狭い画面ではツールバーが横スクロールになり、その中に置いたポップアップは切り取られて見えない。
// そのときは画面に固定して（CSS で position:fixed）、開いたときに見出しのすぐ下・画面の中に収まる位置へ置く
document.addEventListener('toggle', e => {
  const d = e.target; if (!d.matches || !d.matches('details.pop') || !d.open) return;
  const body = d.querySelector('.pop-body'), r = d.querySelector('summary').getBoundingClientRect();
  if (getComputedStyle(body).position !== 'fixed') {
    // 画面の右端からはみ出すときは、はみ出した分だけ左へ寄せる（幅 1024px などで右が切れ、ページに横スクロールができていた）
    body.style.left = body.style.top = '';
    const over = body.getBoundingClientRect().right - (window.innerWidth - 6);
    if (over > 0) body.style.left = -over + 'px';
    return;
  }
  body.style.top = (r.bottom + 4) + 'px';
  body.style.left = Math.max(6, Math.min(r.left, window.innerWidth - body.offsetWidth - 6)) + 'px';
}, true);
window.addEventListener('resize', () => document.querySelectorAll('details.pop[open]').forEach(d => { d.open = false; }));
