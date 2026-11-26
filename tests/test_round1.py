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
        # stamp: wareki + name kind
        await t.load(C+'10_PDF_テキスト/見積書_初回.pdf', C+'10_PDF_テキスト/見積書_再提出.pdf')
        await t.tab('page'); await t.click('[data-tool=stamp]'); await t.page.wait_for_timeout(400)
        t.check('初めて日付印を使うとき設定画面を開く', await t.js("$('#modal').classList.contains('on')"))
        await t.page.fill('[data-k=stampTop]','品質保証課長'); await t.page.fill('[data-k=stampName]','山本'); await t.page.select_option('[data-k=dateFmt]','wareki')
        await t.page.keyboard.press('Escape')
        svg=t.page.locator('.pv-col[data-side="1"] svg').first; bb=await svg.bounding_box()
        await t.page.mouse.click(bb['x']+bb['width']*0.8, bb['y']+60)
        await t.click('#btnSettings'); await t.page.select_option('[data-k=stampKind]','name'); await t.page.select_option('[data-k=stampSize]','l'); await t.page.keyboard.press('Escape')
        await t.click('[data-tool=stamp]'); await t.page.mouse.click(bb['x']+bb['width']*0.6, bb['y']+60)
        st = await t.js("JSON.stringify((PV.st.ann[1][0]||[]).filter(a=>a.t==='stamp').map(a=>[a.kind,a.date,a.name,a.top,a.r]))")
        t.check('日付印（和暦）と認印（大）を置ける', '"date","R' in st and '"name"' in st and '山本' in st and '品質保証課長' in st, st)
        await t.page.wait_for_timeout(400); await t.page.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'numdelta.png'), clip={'x':bb['x']+bb['width']*0.45,'y':bb['y'],'width':bb['width']*0.55,'height':140})
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
        await t.tab('text'); await t.page.focus('.slot[data-side="0"]')
        # ファイル選択ダイアログ自体は headless Chrome で不安定なため、input の click が呼ばれたかで確認する
        await t.js("(()=>{window._pick=0;const i=document.querySelector('.slot[data-side=\"0\"] input[type=file]');i.click=()=>{window._pick++;};})()")
        await t.page.keyboard.press('Enter')
        t.check('ファイル欄で Enter を押すとファイル選択を開く', await t.js("window._pick") == 1)
        t.finish()
asyncio.run(main())
