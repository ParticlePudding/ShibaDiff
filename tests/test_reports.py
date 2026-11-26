"""レポートの出力設定（左右に並べる・載せる内容・画質・設定を覚える）と、手のひらツールでのスワイプ"""
import asyncio, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool, SAMPLES as SM, OUT as O
from test_ui_feedback import make_docs
C = SM + '00_共通サンプル（形式別）/'


async def report(t, opener, button, setup=None):
    """レポートのボタンを押し、出力設定を変えて（setup）、button の文字のボタンで出力した HTML を返す"""
    await t.click(opener); await t.page.wait_for_selector('#modal.on .rep-opts')
    if setup: await setup()
    async with t.page.expect_download() as d:
        await t.page.click(f'#modal.on .foot button:has-text("{button}")')
    dl = await d.value; p = os.path.join(O, dl.suggested_filename); await dl.save_as(p)
    return open(p, encoding='utf-8').read()


async def main():
    docs = make_docs()
    async with Tool(O, 1366, 768) as t:
        ck = t.check
        # ---- テキスト比較 ----
        await t.load(C + '01_テキスト_UTF-8/連絡文_旧.txt', C + '01_テキスト_UTF-8/連絡文_新.txt')
        h = await report(t, '#tReport', '出力', lambda: t.page.check('#modal input[data-k=layout][value=unified]'))
        ck('テキスト：一列のレポート', '<th>内容</th>' in h and '>＋<' in h and '>−<' in h)
        h = await report(t, '#tReport', '出力', lambda: t.page.check('#modal input[data-k=range][value=ctx]'))
        ck('出力設定を覚える（一列のまま）', '<th>内容</th>' in h)
        ck('差分と前後3行だけ（一致部分を省略）', '行省略' in h, h.count('行省略'))
        async def plain():
            await t.page.check('#modal input[data-k=layout][value=side]'); await t.page.uncheck('#modal input[data-k=files]'); await t.page.uncheck('#modal input[data-k=cond]')
        h = await report(t, '#tReport', '出力', plain)
        ck('ファイル情報・比較条件を外せる', 'SHA-256' not in h and '比較条件' not in h and '連絡文_旧.txt' in h)
        ck('出力設定をブラウザに覚える', await t.js("!!localStorage.getItem('doccmp:report:text')"))

        # ---- 重ね合わせ（挿入ページあり） ----
        await t.load(docs['v1'], docs['v2'])
        if await t.js('App.tab') != 'overlay': await t.tab('overlay')
        await t.wait_for("/追加|削除|ありません/.test(document.querySelector('#ovMatchInfo').textContent)", 120)
        h = await report(t, '#ovReport', 'すべてのページ', lambda: t.page.check('#modal input[data-k=layout][value=side]'))
        ck('重ね合わせ：左右に並べる（組ごとに2枚、追加ページは片側＋空き）', h.count('<img') == 11 and '対応するページなし' in h and h.count('class="pair"') == 6, h.count('<img'))
        h = await report(t, '#ovReport', 'すべてのページ', lambda: t.page.check('#modal input[data-k=layout][value=both]'))
        ck('差分画像＋左右', h.count('<img') == 16, h.count('<img'))
        async def light():
            await t.page.check('#modal input[data-k=layout][value=diff]'); await t.page.check('#modal input[data-k=quality][value=light]'); await t.page.uncheck('#modal input[data-k=summary]')
        h = await report(t, '#ovReport', 'すべてのページ', light)
        ck('ページの一覧を外せる', 'ページの一覧' not in h)
        sizes = [len(m) for m in re.findall(r'src="(data:image/jpeg[^"]+)"', h)]
        await t.page.wait_for_timeout(100)
        h2 = await report(t, '#ovReport', 'すべてのページ', lambda: t.page.check('#modal input[data-k=quality][value=high]'))
        sizes2 = [len(m) for m in re.findall(r'src="(data:image/jpeg[^"]+)"', h2)]
        ck('画質：軽量は高精細より小さい', sum(sizes) < sum(sizes2) * 0.7, (sum(sizes), sum(sizes2)))

        # ---- 手のひらツールでのスワイプ ----
        await t.click('#ovModes button[data-mode=swipe]'); await t.page.wait_for_timeout(800)
        await t.js("$('#ovSwipe').value = 50; $('#ovSwipe').dispatchEvent(new Event('input'))")
        if not await t.js("OV.st.hand"): await t.click('#ovHand')
        box = await t.js("(()=>{const r=document.querySelector('#ovView canvas').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
        x, y = box[0] + box[2] * 0.5, box[1] + min(box[3] * 0.5, 300)
        await t.page.mouse.move(x, y); await t.page.mouse.down(); await t.page.mouse.move(x - box[2] * 0.2, y, steps=5); await t.page.mouse.up()
        v = float(await t.js("$('#ovSwipe').value"))
        ck('手のひらツールでも、境界の線をドラッグすれば境界が動く', 25 < v < 35, v)
        st0 = await t.js("document.querySelector('#ovView').scrollLeft + ',' + document.querySelector('#ovView').scrollTop")
        await t.click('#ovZIn'); await t.click('#ovZIn')
        box = await t.js("(()=>{const r=document.querySelector('#ovView').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
        sl0 = await t.js("document.querySelector('#ovView').scrollTop")
        x, y = box[0] + box[2] * 0.85, box[1] + box[3] * 0.6
        v0 = float(await t.js("$('#ovSwipe').value"))
        await t.page.mouse.move(x, y); await t.page.mouse.down(); await t.page.mouse.move(x, y - 150, steps=5); await t.page.mouse.up()
        ck('境界から離れた所のドラッグは表示位置を動かす（境界は動かない）', float(await t.js("$('#ovSwipe').value")) == v0 and await t.js("document.querySelector('#ovView').scrollTop") > sl0, (v0, sl0))
        await t.click('#ovHand')

        # ---- 注釈（左右に並べる） ----
        await t.tab('page'); await t.page.wait_for_timeout(1200)
        await t.js("PV.st.ann[0][0]=[{t:'note',x:100,y:100,text:'左のメモ',bg:'#fff59d'}]; PV.st.ann[1][3]=[{t:'rect',c:'#e53935',lw:2,x:50,y:50,w:100,h:60}]")
        h = await report(t, '#pvReport', '注釈のあるページだけ', lambda: t.page.check('#modal input[data-k=layout][value=side]'))
        ck('注釈：左右の対応するページを並べる（右の4ページ目＝挿入ページの次は左の3ページ目と組）', h.count('class="pair"') == 2 and '左 3 ページ ／ 右 4 ページ' in h and '左のメモ' in h, re.findall(r'左 \S+ ページ ／ 右 \S+ ページ', h))
        h = await report(t, '#pvReport', '注釈のあるページだけ', lambda: t.page.check('#modal input[data-k=layout][value=single]'))
        ck('注釈：1ページずつ', 'class="pair"' not in h and h.count('<img') == 2)
        t.finish()

if __name__ == '__main__':
    asyncio.run(main())
