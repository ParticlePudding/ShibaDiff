"""2回目の20人レビューで見つかった重要度「高」の不具合の修正"""
import asyncio, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
from harness import Tool, OUT as O
import gen_review2 as R2

D = os.path.join(O, 'r2')


def make():
    """必要なレビュー用データだけをテストの出力先に作る"""
    R2.ROOT = D; R2.G.ROOT = D
    for f in (R2.r06, R2.r10, R2.r15, R2.r16, R2.r19): f(f.__name__.upper())
    d = os.path.join(D, 'FD')
    for side, ini in (('L', '[db]\nhost=db01\n'), ('R', '[db]\nhost=db02\n')):
        os.makedirs(os.path.join(d, side), exist_ok=True)
        open(os.path.join(d, side, 'setting.ini'), 'w').write(ini)
        open(os.path.join(d, side, 'same.txt'), 'w').write('abc\n')


async def main():
    make()
    async with Tool(O, 1366, 768) as t:
        ck = t.check
        # ---- ページ・注釈：ページ番号のずれ、次のページで先に進む ----
        await t.load(os.path.join(D, 'R15', '決裁文書_起案時_スキャン.pdf'), os.path.join(D, 'R15', '決裁文書_決裁後_スキャン.pdf'))
        await t.tab('page'); await t.page.wait_for_timeout(1500)
        nxt = '.pv-col[data-side="1"] .pvNext'; inp = '.pv-col[data-side="1"] .pvPage'
        seq = []
        for _ in range(3):
            await t.page.click(nxt); await t.page.wait_for_timeout(500); seq.append(await t.page.input_value(inp))
        ck('「次のページ」で 2→3→4 と進み、ページ番号の欄も合う', seq == ['2', '3', '4'], seq)
        await t.page.fill(inp, '2'); await t.page.press(inp, 'Enter'); await t.page.wait_for_timeout(500)
        ck('ページ番号を入れて移動すると、欄も同じ番号', await t.page.input_value(inp) == '2')

        # ---- CSV：カンマを3桁区切りと読まない ----
        await t.load(os.path.join(D, 'R16', 'measurements_run1.csv'), os.path.join(D, 'R16', 'measurements_run1_corrected.csv'))
        await t.tab('text'); await t.page.wait_for_timeout(500)
        nums = await t.js("[...document.querySelectorAll('.dnum')].map(e => e.textContent)")
        ck('CSV：厚さ 156→160 は「+4 / +2.6%」（12,300,156 と読まない）', '+4 / +2.6%' in nums and not any('0.0%' in x for x in nums), nums)
        # 数値でないもの・％
        r = await t.js("""(() => { const f = (a, b) => Diff.numberDeltas(Diff.chars(a, b, 'char')).map(d => d.text);
          return [f('令和9年4月1日', '令和9年7月1日'), f('2026-11-20', '2026-11-27'), f('透過率 92%', '透過率 94%'), f('等級 G4', '等級 G5'), f('1日最大10mg', '1日最大20mg'), f('===== スライド 4 =====', '===== スライド 5 =====')]; })()""")
        ck('日付・番号には差を付けず、％はポイント、量は従来どおり', r == [[], [], ['+2ポイント'], [], ['+10 / +100.0%'], []], r)

        # ---- 部首補助の文字 ----
        ck('PDFの「⻭」「⻑」を通常の漢字にする', await t.js("normCJK('⻭肉肥厚・上⻑印')") == '歯肉肥厚・上長印')

        # ---- すべてコピーは確認してから ----
        await t.load(os.path.join(D, 'R16', 'measurements_run1.csv'), os.path.join(D, 'R16', 'measurements_run1_corrected.csv'))
        await t.click('#tAllToR'); await t.page.wait_for_timeout(300)
        ck('「全て右へ」は確認を出す', await t.page.is_visible('#modal.on'))
        await t.click('#modal.on .foot button:has-text("キャンセル")'); await t.page.wait_for_timeout(300)
        ck('キャンセルすれば書き換えない', not await t.js('S[1].dirty'))
        await t.click('#tAllToR'); await t.click('#modal.on .foot button.primary'); await t.page.wait_for_timeout(500)
        st = await t.page.inner_text('#textStatus')
        ck('コピー後の「同一」には、編集後・未保存の内容だと添える', '編集後・未保存' in st, st[:80])
        await t.click('#tUndo'); await t.page.wait_for_timeout(300)
        ck('元に戻すで、未保存の編集がなくなる', not await t.js('S[1].dirty'))

        # ---- フォルダ：サイズだけの判定では「同一」としない ----
        await t.tab('folder'); await t.page.uncheck('#fdContent')
        await t.load_folders(os.path.join(D, 'FD', 'L'), os.path.join(D, 'FD', 'R')); await t.page.wait_for_timeout(800)
        rows = await t.js("[...document.querySelectorAll('#fdTable tbody tr')].map(r => r.innerText.replace(/\\s+/g, ' '))")
        ck('サイズが同じでも中身を見ていなければ「サイズ同じ（内容は未確認）」', any('setting.ini' in x and 'サイズ同じ' in x for x in rows) and not any('同一' in x for x in rows), rows)
        await t.page.check('#fdContent'); await t.page.wait_for_timeout(800)
        rows = await t.js("[...document.querySelectorAll('#fdTable tbody tr')].map(r => r.innerText.replace(/\\s+/g, ' '))")
        ck('内容まで比べれば「相違」「同一」', any('setting.ini' in x and '相違' in x for x in rows) and any('same.txt' in x and '同一' in x for x in rows), rows)
        await t.click('#modeSw button[data-mode=file]')

        # ---- A1 図面：標準の解像度でも寸法の変更を拾う ----
        await t.load(os.path.join(D, 'R06', 'PL-3307_RevC_A1.pdf'), os.path.join(D, 'R06', 'PL-3307_RevD_A1.pdf'))
        if await t.js('App.tab') != 'overlay': await t.tab('overlay')
        await t.wait_for("OV.st.cur && OV.st.cur.regions && !document.querySelector('#busy').classList.contains('on')", 120); await t.page.wait_for_timeout(1500)
        regs = await t.js("OV.st.cur.regions.map(r => [r.x, r.y])")
        ck('A1（標準）：寸法 1200→1250 の位置（右の部品の寸法）に枠が付く', any(1150 < x < 1300 and 220 < y < 520 for x, y in regs), regs)
        # ---- 色だけの変更（水色→濃い青のボタン） ----
        await t.load(os.path.join(D, 'R19', '登録画面_v1.png'), os.path.join(D, 'R19', '登録画面_v2.png'))
        if await t.js('App.tab') != 'overlay': await t.tab('overlay')
        await t.wait_for("OV.st.cur && OV.st.cur.regions && OV.st.cur.l === 0", 60); await t.page.wait_for_timeout(800)
        btn = lambda: t.js("OV.st.cur.regions.some(r => r.x < 120 && r.y > 480 && r.y < 600 && r.w > 150)")
        ck('画像：色の違いの検出は既定でオン', await t.js("$('#ovColor').checked"))
        ck('ボタンの色だけの変更に枠が付く（紫）', await btn() and await t.js("OV.st.cur.base.mask.includes(3)"))
        await t.click('#ovColor'); await t.page.wait_for_timeout(1500)
        ck('「色の違いも検出」を外すと、色だけの変更は拾わない', not await btn())
        await t.load(os.path.join(D, 'R15', '決裁文書_起案時_スキャン.pdf'), os.path.join(D, 'R15', '決裁文書_決裁後_スキャン.pdf'))
        await t.page.wait_for_timeout(500)
        ck('紙のスキャン（文字のないPDF）では、色の比較は既定でオフ', not await t.js("$('#ovColor').checked"))

        # ---- ヘッダのファイル名：左右の違う部分（v3／v4_提出版）が見える ----
        await t.load(os.path.join(D, 'R10', 'ノース様提案_v3.pptx'), os.path.join(D, 'R10', 'ノース様提案_v4_提出版.pptx'))
        names = lambda: t.js("[...document.querySelectorAll('#hdrFiles .nm')].map(e => e.textContent)")
        vis = lambda: t.js("[...document.querySelectorAll('#hdrFiles .nm')].every(e => e.scrollWidth <= e.clientWidth + 1)")
        for w, back in ((1366, False), (900, True), (800, True)):
            await t.page.set_viewport_size({'width': w, 'height': 700})
            await t.js(f"document.querySelector('#btnBackFolder').hidden = {str(not back).lower()}; window.dispatchEvent(new Event('resize'))"); await t.page.wait_for_timeout(400)
            n = await names()
            ck(f'ヘッダの名前に違う部分が見える（幅 {w}px{"・フォルダ一覧ボタンあり" if back else ""}）', 'v3' in n[0] and 'v4' in n[1] and await vis(), n)
        await t.js("document.querySelector('#btnBackFolder').hidden = true")
        await t.page.set_viewport_size({'width': 1366, 'height': 768})

        # ---- 390px 幅 ----
        await t.page.set_viewport_size({'width': 390, 'height': 800}); await t.page.wait_for_timeout(500)
        w = await t.js("Math.min(...[...document.querySelectorAll('#tabs button')].map(b => b.getBoundingClientRect().width))")
        ck('390px 幅でもタブを押せる大きさで出す', w >= 30, w)
        t.finish()

if __name__ == '__main__':
    asyncio.run(main())
