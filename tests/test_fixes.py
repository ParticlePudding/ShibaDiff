import asyncio, sys, os, subprocess, shutil, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool
SM=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'samples') + '/'; W=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures') + '/'; O=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
def sh(c): r=subprocess.run(c,shell=True,capture_output=True,text=True); return (r.returncode, (r.stdout+r.stderr).strip()[:200])
async def main():
    async with Tool(O, 1366, 768) as t:
        # --- patches (R07)
        for a,b in [('crlf_a.txt','crlf_b.txt'),('noeol_a.txt','noeol_b.txt'),('sjis_a.txt','sjis_b.txt'),('eoladd_a.txt','eoladd_b.txt')]:
            await t.load(W+'R07/'+a, W+'R07/'+b)
            st = await t.status()
            p = await t.download('#tPatch')
            d=O+'p_'+a.split('_')[0]; shutil.rmtree(d,ignore_errors=True); os.makedirs(d); shutil.copy(W+'R07/'+a, d+'/'+a)
            r1=sh(f'cd {d} && git init -q && git apply --check "{p}"'); r2=sh(f'cd {d} && patch -p1 --dry-run < "{p}"')
            r3=sh(f'cd {d} && patch -p1 -s < "{p}" && cmp {a} {W}R07/t/{b} && echo SAME')
            print('PATCH',a,'| git',r1[0],'| patch',r2[0],'| result',r3[1][-4:], '|', st[:40])
        # --- R08 ascii save prompt & mixed
        await t.load(W+'R08/ascii_l.ini', W+'R08/mixed.ini')
        await t.click('#tAllToL'); await t.click('.slot[data-side="0"] button[data-act=save]')
        await t.page.wait_for_timeout(300); print('ASCII save dialog:', (await t.page.inner_text('#modal .dlg h3')) if await t.js("$('#modal').classList.contains('on')") else 'NONE')
        await t.page.keyboard.press('Escape')
        await t.click('.slot[data-side="1"] button[data-act=save]'); await t.page.wait_for_timeout(300)
        print('MIXED save dialog:', (await t.page.inner_text('#modal .dlg h3')) if await t.js("$('#modal').classList.contains('on')") else 'NONE'); await t.page.keyboard.press('Escape')
        # --- R04 excel dates
        await t.load(W+'R04/xl/見積_A社_v1.xlsx', W+'R04/xl/見積_A社_v2.xlsx'); print('XLSX rows:'); print(await t.visible_rows(8))
        # --- R12 print text-page annotations
        await t.load(SM+'R12_経営企画部_経営企画部長/予算_部門集計_案.xlsx', SM+'R12_経営企画部_経営企画部長/予算_部門集計_確定.xlsx')
        await t.js("Settings.set('stampName','山田')"); await t.tab('page'); svg=t.page.locator('.pv-col[data-side="1"] svg').first; bb=await svg.bounding_box()
        await t.click('[data-tool=stamp]'); await t.page.mouse.click(bb['x']+bb['width']*0.75, bb['y']+bb['height']*0.15)
        await t.click('[data-tool=rect]'); await t.page.mouse.move(bb['x']+40,bb['y']+50); await t.page.mouse.down(); await t.page.mouse.move(bb['x']+250,bb['y']+110,steps=4); await t.page.mouse.up()
        await t.click('#pvPrint'); await t.page.click('.dlg .foot button:has-text("右のみ")'); await t.page.wait_for_timeout(2500)
        await t.js("(()=>{const a=document.querySelector('#printArea');a.style.cssText='display:block;position:fixed;inset:0;z-index:99;background:#fff;overflow:auto';a.querySelector('img').style.width='700px'})()")
        await t.shot('print_xlsx'); await t.js("document.querySelector('#printArea').style.cssText=''")
        # --- report
        await t.tab('text'); rp = await t.download('#tReport'); html=open(rp,encoding='utf-8').read()
        print('REPORT print-color-adjust:', 'print-color-adjust' in html, '| SHA-256:', 'SHA-256' in html, '| 条件:', '比較条件' in html)
        # --- folder dblclick (real mouse)
        await t.load_folders(SM+'00_共通サンプル（形式別）/17_フォルダ比較/旧版フォルダ', SM+'00_共通サンプル（形式別）/17_フォルダ比較/新版フォルダ')
        row=t.page.locator('#fdTable tbody tr', has_text='連絡文.txt'); await row.dblclick(); await t.page.wait_for_timeout(1500)
        print('FOLDER dblclick -> tab:', await t.js('App.tab'), '|', (await t.status())[:50])
        # --- R09 image vs text, broken pdf
        await t.tab('text')
        await t.load(SM+'R09_品質管理部_テストエンジニア/拡張子偽装_実はPNG.txt', SM+'R09_品質管理部_テストエンジニア/BOMなし.txt'); print('IMG vs TEXT:', (await t.status())[:70])
        await t.page.set_input_files('.slot[data-side="1"] input[type=file]', SM+'R09_品質管理部_テストエンジニア/壊れたPDF.pdf'); await t.page.wait_for_timeout(1500); print('BROKEN:', await t.toast())
        # --- R13 docx & R01 docx-vs-pdf normalization
        await t.load(SM+'R01_法務部_契約審査担当/業務委託契約書_先方修正版.docx', SM+'R01_法務部_契約審査担当/業務委託契約書_先方修正版.pdf'); print('R01 docx vs pdf (same version):', await t.status())
        await t.shot('r01_docx_pdf')
        print('errors', t.errors)
asyncio.run(main())
