import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool, OUT
SM=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'samples') + '/'; C=SM+'00_共通サンプル（形式別）/'
async def main():
    async with Tool(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out'), 1440, 860) as t:
        await t.load(SM+'R01_法務部_契約審査担当/業務委託契約書_当社案.docx', SM+'R01_法務部_契約審査担当/業務委託契約書_先方修正版.docx')
        await t.shot('1_colors')
        await t.click('#tLayout'); await t.shot('2_unified'); await t.click('#tLayout')
        # settings: wrap + ws + word unit
        await t.click('#btnSettings'); await t.shot('3_settings')
        await t.page.check('[data-k=wrap]'); await t.page.check('[data-k=showWs]')
        await t.page.keyboard.press('Escape'); await t.page.wait_for_timeout(400)
        await t.shot('4_wrap_ws')
        await t.key('Alt+ArrowDown'); await t.key('Alt+ArrowDown'); await t.page.wait_for_timeout(300); await t.shot('5_wrap_nav')
        st = await t.status()
        t.check('折り返し表示で差分を移動できる（1→3）', '差分 3 / 6' in st, st[:40])
        t.check('折り返し表示で選択中の差分に印', await t.js("document.querySelectorAll('#wrapView .row.cur').length") > 0)
        await t.click('#btnSettings'); await t.page.uncheck('[data-k=wrap]'); await t.page.uncheck('[data-k=showWs]'); await t.page.keyboard.press('Escape')
        # code with word unit
        await t.load(SM+'R07_開発部_ソフトウェアエンジニア/profile.js', SM+'R07_開発部_ソフトウェアエンジニア/profile_refactored.js'); await t.shot('6_code_auto')
        await t.click('#btnSettings'); await t.page.check('[data-k=showWs]'); await t.page.keyboard.press('Escape'); await t.page.wait_for_timeout(300); await t.shot('7_code_ws')
        await t.click('#btnSettings'); await t.page.uncheck('[data-k=showWs]'); await t.page.select_option('[data-k=fontSize]','l'); await t.page.keyboard.press('Escape'); await t.page.wait_for_timeout(300)
        # numbers
        await t.load(SM+'R03_経理部_経理主任/仕訳データ_会計ソフト出力.csv', SM+'R03_経理部_経理主任/仕訳データ_修正後.csv'); await t.shot('8_numbers_large')
        t.check('数字の差の札が出る', await t.js("document.querySelectorAll('.dnum').length") > 0)
        t.check('文字の大きさ（大）が反映される', await t.js("document.documentElement.dataset.fs") == 'l')
        await t.click('#btnSettings'); await t.page.select_option('[data-k=fontSize]','m'); await t.page.keyboard.press('Escape')
        # 注釈（日付印は廃止。付箋と枠を付けて保存データに出ることを確認する）
        # 注釈のブラウザ保存は既定でオフ（2回目のレビューで変更）。保存データの画面を確かめるためにオンにする
        t.check('注釈のブラウザ保存は既定でオフ', await t.js("Settings.get('persist') === false"))
        await t.js("Settings.set('persist', true)")
        await t.load(C+'10_PDF_テキスト/見積書_初回.pdf', C+'10_PDF_テキスト/見積書_再提出.pdf')
        await t.tab('page')
        t.check('日付印のツールがない', await t.js("!document.querySelector('[data-tool=stamp]') && !document.querySelector('#stampCfg')"))
        svg=t.page.locator('.pv-col[data-side="1"] svg').first; bb=await svg.bounding_box()
        await t.click('[data-tool=rect]'); await t.page.mouse.move(bb['x']+60, bb['y']+60); await t.page.mouse.down()
        await t.page.mouse.move(bb['x']+200, bb['y']+120, steps=4); await t.page.mouse.up()
        t.check('枠を付けられる', await t.js("(PV.st.ann[1][0]||[]).some(a=>a.t==='rect')"))
        # 古い注釈ファイルに日付印が入っていても、読み込まずに捨てる
        t.check('古い日付印の注釈は読み込まない', await t.js("PV.cleanAnnot({t:'stamp',x:10,y:10,name:'a'}) === null"))
        # data manager
        await t.click('#btnSettings'); await t.click('#setData'); await t.page.wait_for_timeout(400); await t.shot('10_data')
        n = await t.js("document.querySelectorAll('#dList [data-key]').length")
        t.check('保存データの一覧に設定・注釈が出る', n >= 3, n)
        await t.page.keyboard.press('Escape'); await t.page.wait_for_timeout(300); await t.page.keyboard.press('Escape')
        # overlay tolerance
        await t.tab('overlay')
        t.check('文字のあるPDFではずれの許容は0', await t.js("$('#ovTolPx').value") == '0')
        t.check('文字のあるPDFの重ね合わせで3箇所', (await t.ov_stats()).startswith('3 箇所'))
        # a11y: focus trap in help
        await t.click('#btnHelp'); 
        for _ in range(6): await t.page.keyboard.press('Tab')
        t.check('Tab でもフォーカスがダイアログの外に出ない', await t.js("document.querySelector('.dlg').contains(document.activeElement)"))
        await t.page.keyboard.press('Escape')
        t.check('閉じたらフォーカスが元のボタンに戻る', await t.js("document.activeElement.id") == 'btnHelp')
        # slot keyboard
        await t.tab('text'); await t.js("App.showSlots(true)"); await t.page.focus('.slot[data-side="0"]')
        # ファイル選択ダイアログ自体は headless Chrome で不安定なため、input の click が呼ばれたかで確認する
        await t.js("(()=>{window._pick=0;const i=document.querySelector('.slot[data-side=\"0\"] input[type=file]');i.click=()=>{window._pick++;};})()")
        await t.page.keyboard.press('Enter')
        t.check('ファイル欄で Enter を押すとファイル選択を開く', await t.js("window._pick") == 1)
        t.finish()
asyncio.run(main())
