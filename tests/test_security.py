import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool
S=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'samples') + '/R14_セキュリティ推進室_情報セキュリティ担当/'
async def main():
    async with Tool(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')) as t:
        reqs=[]
        t.page.on('request', lambda r: reqs.append(r.url) if not r.url.startswith(('file:','data:','blob:')) else None)
        await t.load(S+'xss_テスト_A.txt', S+'xss_テスト_B.txt')
        await t.tab('page')
        for f in ('evil_ann.json','evil_ann2.json'):
            await t.page.set_input_files('#annFile',os.path.join(os.path.dirname(os.path.abspath(__file__)),'fixtures','R14',f)); await t.page.wait_for_timeout(1500)
            print(f, 'toast:', await t.toast())
        await t.page.reload(); await t.page.wait_for_timeout(500)
        await t.load(S+'xss_テスト_A.txt', S+'xss_テスト_B.txt'); await t.tab('page'); await t.page.wait_for_timeout(1000)
        print('annots now', await t.js("JSON.stringify(PV.st.ann).slice(0,300)"))
        print('errors', t.errors); print('requests', reqs)
asyncio.run(main())
