'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = s => s.replace(/[&<>"]/g, c => c === '&' ? '&amp;' : c === '<' ? '&lt;' : c === '>' ? '&gt;' : '&quot;');
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
  t.textContent = msg; t.className = 'on' + (isErr ? ' err' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.className = '', isErr ? Math.max(ms, 5000) : ms);
}
let busyCount = 0;
function busy(on, msg) {
  busyCount = Math.max(0, busyCount + (on ? 1 : -1));
  if (msg) $('#busyMsg').textContent = msg;
  $('#busy').classList.toggle('on', busyCount > 0);
}
async function withBusy(msg, fn) {
  busy(true, msg); await nextFrame(); await nextFrame();
  try { return await fn(); } finally { busy(false); }
}

/* modal: クリックしたボタンの value で解決する Promise を返す。
   キーボード操作に配慮：開いたらダイアログ内へフォーカスを移し、Tab はダイアログ内だけを巡回、閉じたら元の位置に戻す。
   ダイアログの要素（#modal）は1つを使い回す。開いている間に別のダイアログが開かれたら（設定の中の確認、
   ヘルプを開いたままファイルをドロップしたときのパスワード入力など）、下のダイアログの中身を、入力中の値や
   イベントごと退避して上に重ね、上を閉じたら元に戻す（下のダイアログの Promise とキー操作を置き去りにしない） */
const modalStack = [];
function modal({ title, html, buttons = [{ label: '閉じる', value: null }], onOpen, wide }) {
  return new Promise(resolve => {
    const m = $('#modal'), dlg = $('.dlg', m), h3 = $('h3', m), bodyEl = $('.body', m), foot = $('.foot', m);
    const prevFocus = document.activeElement;
    const under = modalStack[modalStack.length - 1];
    if (under) under.suspend();
    const head = () => { dlg.style.width = wide ? 'min(1100px,96vw)' : ''; h3.textContent = title; };
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
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(null); return; }
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
    if (onOpen) onOpen(m, close);
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
function normCJK(s) {
  return s.replace(/[\u2E80-\u2FDF\uF900-\uFAFF\u2027]/g, c => (c === '\u2027' ? '・' : RADICAL_MAP.get(c) || c.normalize('NFKC')));
}
function extOf(name) { const m = /\.([^.\\/]+)$/.exec(name || ''); return m ? m[1].toLowerCase() : ''; }
function baseName(name) { return (name || '').replace(/\.[^.\\/]+$/, ''); }

/* ツールバーのポップアップ（details.pop）は、外側をクリックするか Esc で閉じる */
document.addEventListener('click', e => { document.querySelectorAll('details.pop[open]').forEach(d => { if (!d.contains(e.target)) d.open = false; }); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') document.querySelectorAll('details.pop[open]').forEach(d => { d.open = false; d.querySelector('summary').focus(); }); });
// 狭い画面ではツールバーが横スクロールになり、その中に置いたポップアップは切り取られて見えない。
// そのときは画面に固定して（CSS で position:fixed）、開いたときに見出しのすぐ下・画面の中に収まる位置へ置く
document.addEventListener('toggle', e => {
  const d = e.target; if (!d.matches || !d.matches('details.pop') || !d.open) return;
  const body = d.querySelector('.pop-body'), r = d.querySelector('summary').getBoundingClientRect();
  if (getComputedStyle(body).position !== 'fixed') { body.style.left = body.style.top = ''; return; }
  body.style.top = (r.bottom + 4) + 'px';
  body.style.left = Math.max(6, Math.min(r.left, window.innerWidth - body.offsetWidth - 6)) + 'px';
}, true);
window.addEventListener('resize', () => document.querySelectorAll('details.pop[open]').forEach(d => { d.open = false; }));
