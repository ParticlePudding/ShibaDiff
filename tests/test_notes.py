"""変更点へのコメント（確認の状態とひとこと）と、注釈の使いやすさの改善（2回目のレビュー）"""
import asyncio, sys, os, json, csv, io
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
from harness import Tool, OUT as O
import gen_review2 as R2

D = os.path.join(O, 'r2n')


def make():
    R2.ROOT = D; R2.G.ROOT = D
    for f in (R2.r01, R2.r04, R2.r02): f(f.__name__.upper())
    async def pdfs():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path=os.environ.get('CHROME_PATH', '/usr/bin/google-chrome')); pg = await b.new_page()
            for path, html in R2.G.CHROME_PDFS: await pg.set_content(html); await pg.pdf(path=path, format='A4')
            await b.close()
    return pdfs()


async def dl(t, sel):
    async with t.page.expect_download() as d:
        await t.page.click(sel)
    x = await d.value; p = os.path.join(O, x.suggested_filename); await x.save_as(p); return p


async def main():
    R2.G.CHROME_PDFS.clear(); await make()
    async with Tool(O, 1366, 768) as t:
        ck = t.check
        await t.js("Settings.set('author', '山田')")
        # ---- テキスト比較：変更点一覧 ----
        await t.load(os.path.join(D, 'R01', '秘密保持契約書_当社ひな形.docx'), os.path.join(D, 'R01', '秘密保持契約書_先方赤入れ反映.docx'))
        await t.click('#tNotes'); await t.page.wait_for_timeout(300)
        n = await t.js("document.querySelectorAll('#tvNotes .nt-item').length")
        ck('変更点一覧に差分のまとまりが並ぶ', n == await t.js('TV.st.blocks.length') and n >= 4, n)
        await t.click('#tNext'); await t.page.wait_for_timeout(200)
        ck('選んだ差分に入力欄が出る', await t.js("!!document.querySelector('#tvNotes .nt-item.cur .nt-ed')"))
        await t.page.click('#tvNotes .nt-item.cur .nt-st button[data-st=ask]')
        await t.page.fill('#tvNotes .nt-item.cur textarea', '=再委託は認めない方針。削除を求める'); await t.page.wait_for_timeout(400)
        ck('比較欄の行に要確認の印', await t.js("document.querySelectorAll('#paneR .row.nt-ask').length") > 0)
        ck('一覧の行に状態とコメント', '要確認' in await t.page.inner_text('#tvNotes .nt-item[data-b="1"]'))
        ck('記入者と日時を残す', await t.js("Object.values(Notes.all())[0].by") == '山田')
        await t.page.click('#tvNotes .nt-item[data-b="0"]'); await t.page.wait_for_timeout(200)
        ck('一覧の行をクリックするとその差分へ', await t.js('TV.st.cur') == 0)
        await t.page.click('#tvNotes .nt-item.cur .nt-st button[data-st=ok]'); await t.page.wait_for_timeout(200)
        await t.page.focus('#tvNotes .nt-item.cur textarea'); await t.page.keyboard.press('n'); await t.page.keyboard.press('Delete')
        ck('入力欄でのキー操作は画面のショートカットにならない', await t.js('TV.st.cur') == 0)
        p = await dl(t, '#ntCsv'); rows = list(csv.reader(io.StringIO(open(p, encoding='utf-8-sig').read())))
        ck('CSV：番号・種類・行・変更前後・確認・コメント・記入者', rows[0][:8] == ['番号', '種類', '左の行', '右の行', '変更前（左）', '変更後（右）', '確認', 'コメント'] and rows[2][6] == '要確認', rows[2][:8] if len(rows) > 2 else rows)
        ck('CSV：コメントの数式注入を無害化', rows[2][7].startswith("'="), rows[2][7])
        h = open(await t.download('#tReport'), encoding='utf-8').read()
        ck('テキストのレポートに変更点の一覧（確認・コメント）', '変更点の一覧' in h and '再委託は認めない方針' in h and 'class="bn">#2<' in h and '確認済 1・要確認 1' in h)

        # ---- 重ね合わせ：変更箇所のコメント ----
        await t.load(os.path.join(D, 'R04', '注文書_控え_スキャン.pdf'), os.path.join(D, 'R04', '注文請書_返送スキャン.pdf'))
        if await t.js('App.tab') != 'overlay': await t.tab('overlay')
        await t.wait_for("OV.st.cur && OV.st.cur.noteIds && OV.st.cur.noteIds.length >= 2", 120)
        g = await t.js("(() => { const v = OV.st.cur, r = v.out.getBoundingClientRect(), k = r.width / v.out.width, g = v.regions[1]; return [r.left + (g.x + g.w / 2) * k, r.top + (g.y + g.h / 2) * k]; })()")
        await t.page.mouse.click(g[0], g[1]); await t.page.wait_for_timeout(300)
        ck('画像の枠をクリックすると、その変更箇所を選ぶ', await t.js('OV.st.cur.regIdx') == 1)
        await t.page.click('#ovNotes .nt-item.cur .nt-st button[data-st=ask]')
        await t.page.fill('#ovNotes .nt-item.cur textarea', '納期の相違。電話で確認中'); await t.page.wait_for_timeout(400)
        ck('変更箇所のコメントを覚える（ページの組と位置）', any(k.startswith('o:0:0:') for k in await t.js('Object.keys(Notes.all())')))
        await t.js("$('#ovThr').value = 95; $('#ovThr').dispatchEvent(new Event('input'))"); await t.page.wait_for_timeout(2500)
        ck('感度を変えても、同じ箇所のコメントを引き継ぐ', await t.js("OV.st.cur.noteIds.some(id => (Notes.get(id) || {}).text === '納期の相違。電話で確認中')"))
        await t.js("$('#ovThr').value = 105; $('#ovThr').dispatchEvent(new Event('input'))"); await t.page.wait_for_timeout(2500)
        await t.click('#ovReport'); p = await t.download('#modal .foot button:has-text("変更のあるページだけ")'); h = open(p, encoding='utf-8').read()
        ck('重ね合わせのレポートに確認・コメント', '納期の相違。電話で確認中' in h and '要確認' in h)
        await t.tab('overlay')
        cnt = []
        for v in (5, 160):
            await t.js(f"$('#ovThr').value = {v}; $('#ovThr').dispatchEvent(new Event('input'))"); await t.page.wait_for_timeout(2500)
            cnt.append(await t.js("OV.st.cur.regions.reduce((s, g) => s + g.w * g.h, 0)"))
        ck('差分の感度は右（大きい値）ほど多く検出する', cnt[1] > cnt[0], cnt)
        await t.js("$('#ovThr').value = 105; $('#ovThr').dispatchEvent(new Event('input'))"); await t.page.wait_for_timeout(2500)

        # ---- ページ表示：変更箇所の枠とコメント ----
        await t.tab('page'); await t.wait_for("document.querySelectorAll('.pv-chg .cb').length > 0", 60)
        ck('ページ表示に変更箇所の枠が出る（既定でオン）', await t.js("document.querySelectorAll('.pv-col[data-side=\"1\"] .pv-chg .cb').length") >= 2)
        ck('コメントのある枠は札にコメントを出す', '納期の相違' in await t.js("document.querySelector('.pv-col[data-side=\"1\"] .pv-chg').textContent"))
        lab = t.page.locator('.pv-col[data-side="1"] .pv-chg .cb-lab').first
        await lab.click(); await t.page.wait_for_timeout(300)
        ck('枠の番号をクリックすると、その場にコメントの入力欄', await t.page.is_visible('#pvNotePop textarea'))
        await t.page.click('#pvNotePop .nt-st button[data-st=ok]'); await t.page.wait_for_timeout(300)
        await t.page.keyboard.press('Escape')
        await t.click('#pvChanges'); await t.page.wait_for_timeout(200)
        ck('変更箇所の表示は切り替えられる', await t.js("document.querySelectorAll('.pv-chg .cb').length") == 0)
        await t.click('#pvChanges'); await t.page.wait_for_timeout(1500)

        # ---- 自由描画の注釈 ----
        await t.click('[data-tool=marker]')
        ck('マーカーの既定は黄色', await t.js('PV.st.color') == '#fdd835')
        await t.click('[data-tool=rect]')
        ck('枠の既定は青（印影の赤と見分ける）', await t.js('PV.st.color') == '#1e88e5')
        await t.click('[data-tool=note]')
        svg = t.page.locator('.pv-col[data-side="1"] .pv-page > svg:not(.pv-chg)').first; bb = await svg.bounding_box()
        await t.page.mouse.click(bb['x'] + 100, bb['y'] + 300); await t.page.wait_for_timeout(300)
        box = await t.page.locator('.pv-noteinput').bounding_box()
        ck('付箋の入力欄はクリックした位置に出る', box and abs(box['x'] - (bb['x'] + 100)) < 30 and abs(box['y'] - (bb['y'] + 300)) < 30, box)
        await t.page.fill('.pv-noteinput textarea', 'この欄の納期を、注文書の控えと照合してから取引先に連絡すること。'); await t.page.keyboard.press('Control+Enter'); await t.page.wait_for_timeout(300)
        notes = await t.js("(PV.st.ann[1][0] || []).filter(a => a.t === 'note')")
        ck('付箋が貼られ、1枚貼ると選択ツールに戻る', len(notes) == 1 and await t.js('PV.st.tool') == 'select')
        ck('長い付箋は折り返す', len(await t.js("Array.from(document.querySelectorAll('.pv-col[data-side=\"1\"] .pv-page > svg:not(.pv-chg)')[0].querySelectorAll('tspan'))")) >= 2)
        await t.page.keyboard.press('Control+z'); await t.page.wait_for_timeout(200)
        ck('Ctrl+Z で付箋を取り消せる', await t.js("(PV.st.ann[1][0] || []).filter(a => a.t === 'note').length") == 0)
        await t.page.keyboard.press('Control+y'); await t.page.wait_for_timeout(200)
        ck('Ctrl+Y でやり直せる', await t.js("(PV.st.ann[1][0] || []).filter(a => a.t === 'note').length") == 1)
        g = await t.page.locator('.pv-col[data-side="1"] .pv-page > svg:not(.pv-chg)').first.locator('g[data-i] rect').nth(1).bounding_box()
        await t.page.mouse.dblclick(g['x'] + 10, g['y'] + 10); await t.page.wait_for_timeout(400)
        ck('付箋のダブルクリックで、内容をその場で直せる', await t.page.is_visible('.pv-noteinput') and 'この欄の納期' in await t.page.input_value('.pv-noteinput textarea'))
        await t.page.fill('.pv-noteinput textarea', '直した付箋'); await t.page.click('.pv-noteinput .ok'); await t.page.wait_for_timeout(300)
        ck('直した内容になる', await t.js("PV.st.ann[1][0].find(a => a.t === 'note').text") == '直した付箋')

        # ---- 注釈ファイル：コメントも一緒に保存・読み込み ----
        p = await dl(t, '#annExport'); data = json.load(open(p, encoding='utf-8'))
        ck('注釈ファイルに変更点のコメント・記入者・SHA-256', len(data.get('notes', {})) >= 1 and data.get('author') == '山田' and all(len(f.get('sha256', '')) == 64 for f in data['files']))
        await t.js("Notes.clear(); PV.st.ann[1] = {}")
        await t.page.set_input_files('#annFile', p); await t.page.wait_for_timeout(800)
        ck('読み込むとコメントも戻る', any((v or {}).get('text') == '納期の相違。電話で確認中' for v in (await t.js('Notes.all()')).values()))
        ck('ブラウザには保存しない（既定）', await t.js("!Object.keys(localStorage).some(k => k.startsWith('doccmp:notes:') || k.startsWith('doccmp:ann:'))"))
        t.finish()

if __name__ == '__main__':
    asyncio.run(main())
