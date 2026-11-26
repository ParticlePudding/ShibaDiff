"""細工したファイル・注釈ファイルで、スクリプトが動かないこと、外部への通信がないこと、保存後も無害であること"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool, SAMPLES, FIXTURES, OUT
S = SAMPLES + 'R14_セキュリティ推進室_情報セキュリティ担当/'

async def main():
    async with Tool(OUT) as t:
        reqs = []
        t.page.on('request', lambda r: reqs.append(r.url) if not r.url.startswith(('file:', 'data:', 'blob:')) else None)
        # 罠：スクリプトが動いたら印が立つ
        await t.page.add_init_script("window.__pwned = 0; window.alert = () => { window.__pwned++; };")
        await t.page.reload()
        await t.load(S + 'xss_テスト_A.txt', S + 'xss_テスト_B.txt')
        t.check('ファイル内のスクリプトがテキスト比較で動かない', await t.js("window.__pwned") == 0)
        await t.tab('page')
        for f in ('evil_ann.json', 'evil_ann2.json'):
            await t.page.set_input_files('#annFile', FIXTURES + 'R14/' + f); await t.page.wait_for_timeout(1500)
            t.check(f'{f}：読み込んでもスクリプトが動かない', await t.js("window.__pwned") == 0, await t.toast())
        ann = await t.js("JSON.stringify(PV.st.ann)")
        t.check('不正な注釈（色・種類）は捨て、文字は文字のまま保持', '"t":"rect"' in ann and 'image href' not in ann and '"c":"#e53935"' in ann, ann[:200])
        t.check('付箋の文字はHTMLとして解釈されない', await t.js("document.querySelectorAll('.pv-col img[src=x]').length") == 0)
        await t.page.reload(); await t.page.wait_for_timeout(500)
        await t.load(S + 'xss_テスト_A.txt', S + 'xss_テスト_B.txt'); await t.tab('page'); await t.page.wait_for_timeout(1000)
        t.check('保存された注釈を読み戻してもスクリプトが動かない', await t.js("window.__pwned") == 0)
        await t.tab('text'); rp = await t.download('#tReport')
        pg2 = await t.ctx.new_page(); await pg2.add_init_script("window.__pwned = 0; window.alert = () => { window.__pwned++; };")
        await pg2.goto('file://' + rp); await pg2.wait_for_timeout(500)
        t.check('HTMLレポートでもスクリプトが動かない', await pg2.evaluate("window.__pwned") == 0)
        await pg2.close()
        t.check('外部への通信がない', not reqs, reqs)
        t.finish()

asyncio.run(main())
