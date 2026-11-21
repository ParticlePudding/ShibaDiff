import asyncio, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool
SM=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'samples') + '/'; C=SM+'00_共通サンプル（形式別）/'
async def main():
    async with Tool(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out'), 1440, 900) as t:
        pairs=[('01_テキスト_UTF-8/連絡文_旧.txt','01_テキスト_UTF-8/連絡文_新.txt'),('02_テキスト_Shift_JIS_CRLF/連絡文_旧_SJIS.txt','02_テキスト_Shift_JIS_CRLF/連絡文_新_SJIS.txt'),
               ('03_テキスト_文字コード違い/連絡文_EUC-JP.txt','03_テキスト_文字コード違い/連絡文_UTF-16LE.txt'),('04_CSV/在庫_1月.csv','04_CSV/在庫_2月.csv'),('06_JSON/config_v2.3.json','06_JSON/config_v2.4.json'),
               ('07_Word/議事録_初版.docx','07_Word/議事録_修正版.docx'),('08_Excel/予算_当初.xlsx','08_Excel/予算_修正.xlsx'),('09_PowerPoint/提案書_v1.pptx','09_PowerPoint/提案書_v2.pptx'),
               ('10_PDF_テキスト/見積書_初回.pdf','10_PDF_テキスト/見積書_再提出.pdf'),('11_PDF_非埋め込みフォント/お知らせ_旧.pdf','11_PDF_非埋め込みフォント/お知らせ_新.pdf'),
               ('16_バイナリ/data_v1.bin','16_バイナリ/data_v2.bin'),('13_画像_PNG/図面_RevA.png','13_画像_PNG/図面_RevB.png')]
        for a,b in pairs:
            if await t.js('App.tab')!='text': await t.tab('text')
            await t.load(C+a,C+b); print(a.split('/')[0], '|', (await t.status())[:60], '| tab', await t.js('App.tab'))
        await t.tab('overlay'); print('OV png:', await t.ov_stats())
        await t.load(C+'10_PDF_テキスト/見積書_初回.pdf', C+'10_PDF_テキスト/見積書_再提出.pdf'); await t.page.wait_for_timeout(1500); print('OV pdf:', await t.ov_stats())
        for m in ['overlay','swipe','blink','side','diff']: await t.click(f'#ovModes button[data-mode={m}]'); await t.page.wait_for_timeout(500)
        await t.click('#ovScan'); await t.page.wait_for_timeout(3000); print('scan:', (await t.page.inner_text('#ovScanRes')).replace('\n',' ')[:80])
        await t.tab('page'); await t.shot('reg_page')
        await t.tab('text'); await t.click('#tLayout'); await t.shot('reg_unified'); await t.click('#tLayout')
        # ascii -> japanese save prompt
        await t.load(os.path.join(os.path.dirname(os.path.abspath(__file__)),'fixtures','R08','')+'ascii_l.ini', os.path.join(os.path.dirname(os.path.abspath(__file__)),'fixtures','R08','')+'ascii_l.ini')
        await t.click('.slot[data-side="0"] button[data-act=edit]'); await t.page.fill('#edTa','[a]\nname=日本語\n'); await t.click('.dlg .foot button.primary')
        await t.click('.slot[data-side="0"] button[data-act=save]'); await t.page.wait_for_timeout(300)
        print('ASCII prompt:', await t.page.inner_text('#modal .dlg h3') if await t.js("$('#modal').classList.contains('on')") else 'NONE')
        p = await t.download('.dlg .foot button:has-text("Shift_JIS")'); print('saved bytes sjis ok:', open(p,'rb').read().decode('cp932').strip()[:20])
        # report print rendering
        await t.load(C+'07_Word/議事録_初版.docx', C+'07_Word/議事録_修正版.docx'); rp=await t.download('#tReport')
        pg2=await t.ctx.new_page(); await pg2.goto('file://'+rp); await pg2.emulate_media(media='print'); await pg2.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')); await pg2.close()
        print('errors', t.errors)
asyncio.run(main())
