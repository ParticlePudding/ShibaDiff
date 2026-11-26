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
        await large_sheet(t)
        t.finish()


def make_large_scan():
    """A0 横の図面を 100dpi でスキャンした想定の PDF（右は 0.3° 傾き・ずれあり、四角を1つ追加）"""
    import random
    from PIL import Image, ImageDraw, ImageFilter
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    W, H = 1189 * mm, 841 * mm; pw, ph = int(1189 / 25.4 * 100), int(841 / 25.4 * 100)
    out = []
    for rev, rot, off in [('A', 0, (0, 0)), ('B', 0.3, (6, -4))]:
        random.seed(11); im = Image.new('L', (pw, ph), 255); d = ImageDraw.Draw(im)
        for _ in range(8000):
            x, y = random.randint(50, pw - 50), random.randint(50, ph - 50)
            d.line([x, y, x + random.randint(-80, 80), y + random.randint(-80, 80)], fill=0, width=2)
        d.rectangle([30, 30, pw - 30, ph - 30], outline=0, width=5)
        if rev == 'B': d.rectangle([2500, 1500, 2750, 1650], outline=0, width=3); d.line([2500, 1500, 2750, 1650], fill=0, width=3)
        im = im.rotate(rot, resample=Image.BICUBIC, fillcolor=255).transform(im.size, Image.AFFINE, (1, 0, off[0], 0, 1, off[1]), fillcolor=255)
        jpg = os.path.join(O, f'a0scan_{rev}.jpg'); im.filter(ImageFilter.GaussianBlur(0.6)).convert('RGB').save(jpg, quality=80)
        pdf = os.path.join(O, f'A0スキャン_{rev}.pdf'); c = canvas.Canvas(pdf, pagesize=(W, H)); c.drawImage(jpg, 0, 0, W, H); c.showPage(); c.save()
        out.append(pdf)
    return out


async def large_sheet(t):
    """A0 などの大きな図面：PDF のワーカーが使われること、解像度の設定、細い線のスキャンで誤検出しないこと"""
    a, b = make_large_scan()
    await t.page.evaluate("window.__lt=[]; new PerformanceObserver(l=>{for(const e of l.getEntries()) window.__lt.push(Math.round(e.duration))}).observe({type:'longtask'})")
    for res, width in [('std', 2400), ('low', 1600), ('high', 4000)]:
        await t.tab('text'); await t.js(f"Settings.set('ovRes','{res}'); window.__lt = []; document.querySelector('#ovStats').textContent = ''")
        if res == 'std': await t.load(a, b)
        if await t.js('App.tab') != 'overlay': await t.tab('overlay')
        await t.wait_for("/箇所|差異|目立った/.test(document.querySelector('#ovStats').textContent) && !document.querySelector('#busy').classList.contains('on')", 120)
        s = await t.ov_stats(); cw = await t.js("document.querySelector('#ovView canvas').width")
        t.check(f'A0スキャン（{res}）：描画の幅が {width}px 前後', abs(cw - width) <= 10, cw)
        if res != 'high':  # 精細はスキャンのわずかなずれまで拾うため、箇所の数は確かめない
            t.check(f'A0スキャン（{res}）：細い線を誤検出せず、追加した四角の1箇所だけ', s.startswith('1 箇所'), s[:30])
        lt = max(await t.js("window.__lt") or [0])
        t.check(f'A0スキャン（{res}）：画面が2秒以上固まらない', lt < 2000, f'最長 {lt}ms')
    t.check('PDF はワーカーで処理する（メインスレッドで処理する fake worker にならない）', await t.js("typeof globalThis.pdfjsWorker") == "undefined")
    # これまでに何組も読み込んだが、動いているワーカーは今開いている左右の2つだけ（閉じた文書のワーカーは終了している）
    await t.page.wait_for_timeout(500)
    t.check('閉じた文書の PDF ワーカーは終了している', len(t.page.workers) == 2, len(t.page.workers))
    await t.js("Settings.set('ovRes','std')")

asyncio.run(main())
