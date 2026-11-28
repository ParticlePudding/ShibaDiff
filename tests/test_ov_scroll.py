"""重ね合わせ比較の全ページ表示（全ページを縦に並べてスクロール）と、Lucide アイコン"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool, OUT as O
from test_ui_feedback import make_docs

SLOTS = "OV.st.slots"


async def main():
    docs = make_docs()
    async with Tool(O, 1366, 768) as t:
        ck = t.check
        # ---- アイコン ----
        n = await t.js("document.querySelectorAll('button svg.ic').length")
        ck('ボタンに Lucide のアイコン（インラインSVG）が入っている', n > 40, n)
        ck('ビルド情報に Lucide の版がある', bool(await t.js("APP.lucide")))
        ck('ライセンスに Lucide を載せている', 'Lucide' in await t.js("document.getElementById('licenses').textContent"))
        ck('隠しているボタンはアイコンがあっても隠れたまま', not await t.page.is_visible('#btnExitFull') and not await t.page.is_visible('#btnBackFolder'))

        # ---- 全ページ表示（スキャン、3ページ目に挿入） ----
        await t.load(docs['v1s'], docs['v2s'])
        if await t.js('App.tab') != 'overlay': await t.tab('overlay')
        await t.wait_for("/追加|削除|ありません/.test(document.querySelector('#ovMatchInfo').textContent)", 120)
        await t.click('#ovViewSw button[data-v=scroll]')
        await t.wait_for(f"{SLOTS} && {SLOTS}.length === 6 && {SLOTS}[0].v", 120)
        ck('全ページ表示：対応付けた組の数だけページを並べる', await t.js(f"{SLOTS}.length") == 6)
        ck('挿入されたページに「右で追加」の印', '右で追加' in await t.page.inner_text('.ov-page[data-k="2"] .ov-pghead'))
        ck('見えていない遠いページはまだ描かない', await t.js(f"!{SLOTS}[5].v"))
        ck('設定に覚える', await t.js("Settings.get('ovScroll')") is True)
        await t.shot('ov_scroll_top')
        # スクロールすると「今のページ」が変わる
        await t.js("document.querySelector('#ovView').scrollTop = document.querySelector('.ov-page[data-k=\"3\"]').offsetTop")
        await t.wait_for(f"OV.st.curSlot && OV.st.curSlot.k === 3 && OV.st.curSlot.v", 120)
        ck('スクロールで今のページ（ページ番号の欄）が変わる', (await t.js("+$('#ovLPage').value"), await t.js("+$('#ovRPage').value")) == (2, 3))
        ck('右パネルの結果は今のページのもの', '箇所' in await t.page.inner_text('#ovStats') or '差異' in await t.page.inner_text('#ovStats') or '変更' in await t.page.inner_text('#ovStats'))
        ck('離れたページの描画は捨てる（メモリ）', await t.js(f"!{SLOTS}[0].v"))
        # PageUp／PageDown で前後のページへ
        await t.page.focus('#ovView'); await t.page.keyboard.press('PageUp'); await t.page.wait_for_timeout(900)
        ck('PageUp で前のページ（挿入ページ）へ', await t.js("OV.st.curSlot.k") == 2)
        await t.page.keyboard.press('PageDown'); await t.page.wait_for_timeout(900)
        ck('PageDown で次のページへ', await t.js("OV.st.curSlot.k") == 3)
        # ページ番号の欄で選ぶと、そのページまでスクロール
        await t.page.select_option('#ovLPage', '4')
        # 移動している間（滑らかなスクロールの途中）の「今のページ」を、30ms ごとに記録する
        await t.js("window.__ks = []; window.__kt = setInterval(() => window.__ks.push(OV.st.curSlot ? OV.st.curSlot.k : -1), 30); 0")
        await t.page.wait_for_timeout(1500)
        ks = await t.js("(clearInterval(window.__kt), window.__ks)")
        ck('ページ番号を選ぶとそのページへスクロール', await t.js("OV.st.curSlot.k") == 5)
        ck('移動の途中で通るページを「今のページ」にしない（ページ番号の欄が次々と変わらない）', len(ks) > 10 and set(ks) == {5}, sorted(set(ks)))
        off = await t.js("(() => { const v = document.querySelector('#ovView'), s = OV.st.curSlot.el; return Math.round(s.getBoundingClientRect().top - v.getBoundingClientRect().top); })()")
        ck('目的のページの先頭まで届く（途中で止まらない）', abs(off - 6) <= 3 or await t.js("(() => { const v = document.querySelector('#ovView'); return v.scrollTop >= v.scrollHeight - v.clientHeight - 2; })()"), off)
        # 表示方法ごとに描ける
        for m in ['side', 'blink', 'swipe', 'overlay', 'diff']:
            await t.click(f'#ovModes button[data-mode={m}]')
            await t.wait_for(f"OV.st.curSlot && OV.st.curSlot.v && document.querySelectorAll('#ovView canvas').length > 0", 120)
            cnt = await t.js(f"OV.st.curSlot.body.querySelectorAll('canvas').length")
            ck(f'全ページ表示で「{m}」も描ける', cnt == (2 if m == 'side' else 1), cnt)
            ck(f'「{m}」に切り替えても同じページのまま', await t.js("OV.st.curSlot.k") == 5)
            if m == 'swipe':
                await t.js("$('#ovSwipe').value = 20; $('#ovSwipe').dispatchEvent(new Event('input'))")
                ck('スワイプの境界は表示中のページすべてに反映', await t.js(f"{SLOTS}.filter(s => s.v && s.v.drawSwipe).length") >= 1)
        # 拡大しても全ページ並んだまま
        w0 = await t.js("OV.st.curSlot.body.querySelector('canvas').getBoundingClientRect().width")
        await t.click('#ovZIn'); await t.page.wait_for_timeout(300)
        w1 = await t.js("OV.st.curSlot.body.querySelector('canvas').getBoundingClientRect().width")
        ck('全ページ表示でも拡大できる（仮の枠も一緒に）', w1 > w0 * 1.2 and await t.js("[...document.querySelectorAll('.ov-ph')].every(e => parseFloat(e.style.width) > 0)"), (w0, w1))
        await t.click('#ovRegNext'); await t.page.wait_for_timeout(300)
        # 位置合わせを変えると今のページだけ描き直す
        other = await t.js(f"{SLOTS}.find(s => s.v && s !== OV.st.curSlot)?.k ?? -1")
        await t.page.fill('#ovDx', '5'); await t.page.dispatch_event('#ovDx', 'change'); await t.page.wait_for_timeout(1500)
        ck('位置合わせは今のページの組に効く', await t.js("OV.st.curSlot.v.dx") == 5 and await t.js("OV.st.align.get(OV.st.l + ':' + OV.st.r)[0]") == 5)
        if other >= 0: ck('ほかのページの位置合わせは変えない', await t.js(f"{SLOTS}[{other}].v ? {SLOTS}[{other}].v.dx !== 5 : true"))
        await t.shot('ov_scroll_zoom')
        # 1ページ表示に戻す
        await t.click('#ovViewSw button[data-v=single]'); await t.page.wait_for_timeout(1500)
        ck('1ページ表示に戻すと今のページを1枚だけ表示', await t.js("!OV.st.slots && OV.st.l === 4 && document.querySelectorAll('#ovView canvas').length === 1"), await t.js("[OV.st.l, document.querySelectorAll('#ovView canvas').length]"))
        # 全ページ表示のまま別のファイルを読み込んでも先頭から
        await t.click('#ovViewSw button[data-v=scroll]')
        await t.load(docs['v1'], docs['v2'])
        if await t.js('App.tab') != 'overlay': await t.tab('overlay')
        await t.wait_for(f"{SLOTS} && {SLOTS}.length === 6 && OV.st.curSlot && OV.st.curSlot.v", 120)
        ck('ファイルを読み込み直すと先頭のページから', await t.js("OV.st.curSlot.k") == 0)
        await t.click('#ovViewSw button[data-v=single]')
        t.finish()

asyncio.run(main())
