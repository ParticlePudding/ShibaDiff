"""パッチの適用、保存の確認、Office、レポート、フォルダ比較、壊れたファイル"""
import asyncio, sys, os, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool, SAMPLES as SM, FIXTURES as W, OUT as O


def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()[:300]


def apply_patch(tool, a, b, patch):
    """git apply と patch -p1 の両方で左のファイルに適用し、右のファイルとバイト単位で一致するかを返す"""
    ok = {}
    for how, cmd in [('git', 'git init -q && git apply "{p}"'), ('patch', 'patch -p1 -s < "{p}"')]:
        d = os.path.join(O, f'p_{how}_{a.split("_")[0]}')
        shutil.rmtree(d, ignore_errors=True); os.makedirs(d); shutil.copy(W + 'R07/' + a, os.path.join(d, a))
        rc, msg = sh(f'cd "{d}" && ' + cmd.format(p=patch))
        same = rc == 0 and open(os.path.join(d, a), 'rb').read() == open(W + 'R07/' + b, 'rb').read()
        tool.check(f'パッチ {a}：{how} で適用した結果が右のファイルと一致', same, '' if same else (msg or repr(open(os.path.join(d, a), 'rb').read()[:60])))


async def main():
    async with Tool(O, 1366, 768) as t:
        # --- パッチ（改行コード・末尾改行・Shift_JIS・改行のない最終行）
        for a, b in [('crlf_a.txt', 'crlf_b.txt'), ('noeol_a.txt', 'noeol_b.txt'), ('sjis_a.txt', 'sjis_b.txt'), ('eoladd_a.txt', 'eoladd_b.txt'),
                     ('noeolmid_a.txt', 'noeolmid_b.txt'), ('noeolmid2_a.txt', 'noeolmid2_b.txt'), ('toeol_a.txt', 'toeol_b.txt')]:
            await t.load(W + 'R07/' + a, W + 'R07/' + b)
            apply_patch(t, a, b, await t.download('#tPatch'))

        # --- 英数字だけのファイル：日本語が入っていなければ文字コードを聞かない／改行の混在は確認する
        await t.load(W + 'R08/ascii_l.ini', W + 'R08/mixed.ini')
        await t.click('#tAllToL'); await t.click('#modal.on .foot button.primary'); await t.click('.slot[data-side="0"] button[data-act=save]'); await t.page.wait_for_timeout(300)
        t.check('英数字のみの保存で文字コードを聞かない', not await t.js("$('#modal').classList.contains('on')"))
        await t.page.keyboard.press('Escape')
        await t.click('.slot[data-side="1"] button[data-act=save]'); await t.page.wait_for_timeout(300)
        h = await t.page.inner_text('#modal .dlg h3') if await t.js("$('#modal').classList.contains('on')") else ''
        t.check('改行が混在したファイルの保存で確認を出す', h == '改行コードの確認', h)
        await t.page.keyboard.press('Escape')

        # --- Excel の日付・数式
        await t.load(W + 'R04/見積_A社_v1.xlsx', W + 'R04/見積_A社_v2.xlsx')
        rows = await t.visible_rows(8)
        t.check('Excel の日付を日付として表示', '2027/02/28' in rows, rows[:200])
        t.check('Excel の数式を比較対象に含める', '‹=B2*C2›' in rows)

        # --- Office 文書の印刷（注釈付き）
        await t.load(SM + 'R12_経営企画部_経営企画部長/予算_部門集計_案.xlsx', SM + 'R12_経営企画部_経営企画部長/予算_部門集計_確定.xlsx')
        await t.tab('page')
        svg = t.page.locator('.pv-col[data-side="1"] svg').first; bb = await svg.bounding_box()
        await t.click('[data-tool=marker]'); await t.page.mouse.move(bb['x'] + bb['width'] * 0.6, bb['y'] + 80); await t.page.mouse.down()
        await t.page.mouse.move(bb['x'] + bb['width'] * 0.8, bb['y'] + 80, steps=4); await t.page.mouse.up()
        await t.click('[data-tool=rect]'); await t.page.mouse.move(bb['x'] + 40, bb['y'] + 50); await t.page.mouse.down()
        await t.page.mouse.move(bb['x'] + 250, bb['y'] + 110, steps=4); await t.page.mouse.up()
        t.check('注釈が2件付いた', await t.js("Object.values(PV.st.ann[1]).flat().length") == 2)
        await t.js("window.__printed = undefined")
        await t.click('#pvPrint'); await t.page.click('.dlg .foot button:has-text("右のみ")')
        await t.wait_for("window.__printed !== undefined", 30)
        n = await t.js("window.__printed")
        t.check('印刷用の画像を作った', n is not None and n >= 1, n)

        # --- HTMLレポート
        await t.tab('text'); rp = await t.download('#tReport'); html = open(rp, encoding='utf-8').read()
        t.check('レポート：印刷で色を残す', 'print-color-adjust' in html)
        t.check('レポート：SHA-256 を記載', 'SHA-256' in html)
        t.check('レポート：比較条件を記載', '比較条件' in html)
        t.check('レポート：CSP を付ける', 'Content-Security-Policy' in html)

        # --- フォルダ比較：ダブルクリックで開く
        await t.load_folders(SM + '00_共通サンプル（形式別）/17_フォルダ比較/旧版フォルダ', SM + '00_共通サンプル（形式別）/17_フォルダ比較/新版フォルダ')
        row = t.page.locator('#fdTable tbody tr', has_text='連絡文.txt'); await row.dblclick()
        await t.wait_for("App.tab === 'text' && !!S[0] && S[0].name === '連絡文.txt'", 20)
        t.check('フォルダ比較のダブルクリックでテキスト比較を開く', '差分' in await t.status())

        # --- 画像とテキスト、壊れたPDF
        await t.load(SM + 'R09_品質管理部_テストエンジニア/拡張子偽装_実はPNG.txt', SM + 'R09_品質管理部_テストエンジニア/BOMなし.txt')
        st = await t.status()
        t.check('拡張子を偽装した画像を「同一」と言わない', '⚠' in st and '同一' not in st, st[:60])
        await t.page.set_input_files('.slot[data-side="1"] input[type=file]', SM + 'R09_品質管理部_テストエンジニア/壊れたPDF.pdf')
        await t.page.wait_for_timeout(1500)
        msg = await t.toast()
        t.check('壊れたPDFは理由を表示し、前のファイルを残す', 'PDFファイルが壊れている' in msg and 'そのまま残っています' in msg, msg)
        t.check('壊れたPDFを読んでも右は前のファイルのまま', await t.js("S[1].name") == 'BOMなし.txt')

        # --- docx と、同じ版の PDF（康熙部首などの正規化）
        await t.load(SM + 'R01_法務部_契約審査担当/業務委託契約書_先方修正版.docx', SM + 'R01_法務部_契約審査担当/業務委託契約書_先方修正版.pdf')
        t.check('docx と PDF を比較できる', 'DOCX' in await t.status() and 'PDF' in await t.status())

        t.finish(allowed_errors=['InvalidPDFException'])

asyncio.run(main())
