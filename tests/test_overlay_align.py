import asyncio, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool
SM=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'samples') + '/'
async def main():
    async with Tool(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out'), 1366, 768) as t:
        for a,b,n in [('R06_設計部_機械設計エンジニア/DWG-2041_RevC.png','R06_設計部_機械設計エンジニア/DWG-2041_RevC_客先返却スキャン.jpg','r06'),
                      ('R17_建設部_工事課_施工管理者/施工図_基礎伏図_第2回.jpg','R17_建設部_工事課_施工管理者/施工図_基礎伏図_第3回.jpg','r17'),
                      ('00_共通サンプル（形式別）/14_画像_JPEG/図面_RevA_スキャン.jpg','00_共通サンプル（形式別）/14_画像_JPEG/図面_RevB_スキャン.jpg','c14'),
                      ('R15_市役所_総務課_文書管理担当（自治体）/支援金要綱_決裁前_スキャン.pdf','R15_市役所_総務課_文書管理担当（自治体）/支援金要綱_決裁後_スキャン.pdf','r15')]:
            t0=time.time(); await t.load(SM+a, SM+b)
            if await t.js('App.tab') != 'overlay': await t.tab('overlay')
            await t.wait_for("document.querySelector('#ovStats').textContent.includes('箇所') || document.querySelector('#ovStats').textContent.includes('変更')")
            print(n, round(time.time()-t0,1),'s |', await t.ov_stats()); await t.shot('rot_'+n)
        await t.click('#ovScan'); await t.page.wait_for_timeout(9000); print('r15 scan:', (await t.page.inner_text('#ovScanRes')).replace('\n',' '))
        print('errors', t.errors)
asyncio.run(main())
