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
   キーボード操作に配慮：開いたらダイアログ内へフォーカスを移し、Tab はダイアログ内だけを巡回、閉じたら元の位置に戻す */
function modal({ title, html, buttons = [{ label: '閉じる', value: null }], onOpen, wide }) {
  return new Promise(resolve => {
    const m = $('#modal'), dlg = $('.dlg', m), h3 = $('h3', m);
    const prevFocus = document.activeElement;
    dlg.style.width = wide ? 'min(1100px,96vw)' : '';
    dlg.setAttribute('role', 'dialog'); dlg.setAttribute('aria-modal', 'true');
    h3.id = 'dlgTitle'; dlg.setAttribute('aria-labelledby', 'dlgTitle');
    h3.textContent = title;
    $('.body', m).innerHTML = html;
    const foot = $('.foot', m); foot.innerHTML = '';
    let closed = false;
    const close = v => {
      if (closed) return; closed = true;
      m.classList.remove('on'); document.removeEventListener('keydown', onKey, true);
      if (prevFocus && prevFocus.focus && document.contains(prevFocus)) prevFocus.focus();
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
    m.classList.add('on');
    if (onOpen) onOpen(m, close);
    if (!dlg.contains(document.activeElement)) {
      const first = $('textarea,input:not([type=checkbox]),select', $('.body', m)) || $('button.primary', foot) || focusables()[0];
      if (first) first.focus();
    }
  });
}
async function askText(title, value = '', { small = true, label = '' } = {}) {
  return modal({
    title,
    html: (label ? `<div style="margin-bottom:6px">${label}</div>` : '') + `<textarea class="${small ? 'small' : ''}" id="askTa"></textarea>`,
    buttons: [{ label: 'キャンセル', value: null }, { label: 'OK', primary: true, value: m => $('#askTa', m).value }],
    onOpen: m => { const ta = $('#askTa', m); ta.value = value; ta.focus(); ta.select(); }
  });
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
function normCJK(s) {
  return s.replace(/[\u2E80-\u2FDF\uF900-\uFAFF\u2027\u2F00-\u2FD5]/g, c => (c === '\u2027' ? '・' : c.normalize('NFKC')));
}
function extOf(name) { const m = /\.([^.\\/]+)$/.exec(name || ''); return m ? m[1].toLowerCase() : ''; }
function baseName(name) { return (name || '').replace(/\.[^.\\/]+$/, ''); }

/* ツールバーのポップアップ（details.pop）は、外側をクリックするか Esc で閉じる */
document.addEventListener('click', e => { document.querySelectorAll('details.pop[open]').forEach(d => { if (!d.contains(e.target)) d.open = false; }); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') document.querySelectorAll('details.pop[open]').forEach(d => { d.open = false; d.querySelector('summary').focus(); }); });
