"""傾いたスキャン画像・スキャンPDFの自動位置合わせと変更箇所の数、一括チェック（サンプルは乱数の種を固定して作るので、数は毎回同じ）"""
import asyncio, sys, os, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool, SAMPLES as SM, OUT as O

CASES = [  # (左, 右, 名前, 期待する変更箇所の数)
    ('R06_設計部_機械設計エンジニア/DWG-2041_RevC.png', 'R06_設計部_機械設計エンジニア/DWG-2041_RevC_客先返却スキャン.jpg', 'r06', 1),
    ('R17_建設部_工事課_施工管理者/施工図_基礎伏図_第2回.jpg', 'R17_建設部_工事課_施工管理者/施工図_基礎伏図_第3回.jpg', 'r17', 3),
    ('00_共通サンプル（形式別）/14_画像_JPEG/図面_RevA_スキャン.jpg', '00_共通サンプル（形式別）/14_画像_JPEG/図面_RevB_スキャン.jpg', 'c14', 8),
    ('R15_市役所_総務課_文書管理担当（自治体）/支援金要綱_決裁前_スキャン.pdf', 'R15_市役所_総務課_文書管理担当（自治体）/支援金要綱_決裁後_スキャン.pdf', 'r15', 2),
]

async def main():
    async with Tool(O, 1366, 768) as t:
        for a, b, n, exp in CASES:
            t0 = time.time(); await t.load(SM + a, SM + b)
            t.check(f'{n}：スキャンなので重ね合わせ比較に切り替わる', await t.js('App.tab') == 'overlay')
            if await t.js('App.tab') != 'overlay': await t.tab('overlay')
            await t.wait_for("document.querySelector('#ovStats').textContent.includes('箇所')")
            s = await t.ov_stats(); sec = time.time() - t0
            t.check(f'{n}：変更箇所 {exp}', s.startswith(f'{exp} 箇所'), s[:40])
            t.check(f'{n}：自動で位置合わせした', '自動で位置合わせしました' in s)
            t.check(f'{n}：読み込みから10秒以内', sec < 10, f'{sec:.1f}s')
            await t.shot('rot_' + n)
        await t.click('#ovScan')
        await t.wait_for("document.querySelector('#ovScanRes').textContent.includes('変更ありのページ')", 60)
        r = (await t.page.inner_text('#ovScanRes')).replace('\n', ' ')
        t.check('r15 一括チェック：1ページ目だけ、件数は1ページ表示と一致（2箇所）', '変更ありのページ: 1 / 2' in r and re.search(r'\b1\s+2\b', r), r[:80])
        t.finish()

asyncio.run(main())
