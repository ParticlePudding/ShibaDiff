"""コードレビューで直した点の確認"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')

async def main():
    os.makedirs(OUT, exist_ok=True)
    async with Tool(OUT) as t:
        ok = True
        def check(name, cond, info=''):
            nonlocal ok; ok &= bool(cond); print(('OK  ' if cond else 'NG  ') + name, info)

        # 日付・品番のハイフンを負号と誤認しない
        d = await t.js("JSON.stringify(Diff.numberDeltas(Diff.chars('納期 2026-11-26','納期 2026-11-27')))")
        check('日付の差は +1', '"+1' in d, d)
        d = await t.js("JSON.stringify(Diff.numberDeltas(Diff.chars('品番 ABC-120','品番 ABC-125')))")
        check('品番の差は +5', '"+5' in d, d)
        d = await t.js("JSON.stringify(Diff.numberDeltas(Diff.chars('損益 -100','損益 -150')))")
        check('本物の負数は −50', '"−50' in d, d)

        # すべて削除で開いている間の設定も初期値に戻る
        await t.js("Settings.set('fontSize','l'); Settings.set('stampName','山田')")
        await t.click('#btnSettings'); await t.click('#setData'); await t.page.wait_for_timeout(300)
        await t.js("window.confirm=()=>true")
        await t.page.click('#modal .foot button >> nth=1'); await t.page.wait_for_timeout(300)
        r = await t.js("[Settings.get('fontSize'), Settings.get('stampName'), document.documentElement.dataset.fs]")
        check('すべて削除で設定が初期化', r == ['m', '', 'm'], r)
        await t.page.keyboard.press('Escape'); await t.page.wait_for_timeout(200); await t.page.keyboard.press('Escape')

        # 編集で末尾の改行を消したら finalNL=false
        await t.js("S[0]=App.newTextSide(); S[0].lines=['a','b']; App.updateSlot(0)")
        await t.click('.slot[data-side="0"] [data-act=edit]')
        await t.page.fill('#edTa', 'a\nc'); await t.page.click('#modal .foot button.primary')
        check('末尾改行なしを保持', await t.js("S[0].finalNL") is False)
        await t.page.fill('#searchBox', '')
        await t.click('.slot[data-side="0"] [data-act=edit]')
        await t.page.fill('#edTa', 'a\nd\n'); await t.page.click('#modal .foot button.primary')
        check('末尾改行ありを保持', await t.js("S[0].finalNL") is True)

        # 折り返し表示で大きな差分を選んでも速い
        ms = await t.js("""(()=>{S[0]={...App.newTextSide(),lines:Array.from({length:30000},(_,i)=>'L'+i)};
          S[1]={...App.newTextSide(),lines:Array.from({length:30000},(_,i)=>i<5?'L'+i:'X'+i)};
          Settings.set('wrap',true); TV.compare(); const t0=performance.now(); TV.go(0); return performance.now()-t0;})()""")
        cur = await t.js("document.querySelectorAll('#wrapView .row.cur').length")
        check('大きな差分の選択が速い', ms < 1500 and cur == 59990, f'{ms:.0f}ms / 印 {cur} 行')
        await t.js("Settings.set('wrap',false)")

        print('errors', t.errors)
        print('ALL OK' if ok and not t.errors else 'FAILED')

asyncio.run(main())
