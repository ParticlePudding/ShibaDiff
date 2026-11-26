"""共通サンプル全形式の読み込み・比較、重ね合わせ、一括チェック、英数字ファイルの保存、レポートの印刷表示"""
import asyncio, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool, SAMPLES as SM, FIXTURES as W, OUT as O
C = SM + '00_共通サンプル（形式別）/'

# (左, 右, 期待する差分の箇所数 または 状態表示に含まれる文字, 開かれるタブ)
PAIRS = [
    ('01_テキスト_UTF-8/連絡文_旧.txt', '01_テキスト_UTF-8/連絡文_新.txt', 2, 'text'),
    ('02_テキスト_Shift_JIS_CRLF/連絡文_旧_SJIS.txt', '02_テキスト_Shift_JIS_CRLF/連絡文_新_SJIS.txt', 2, 'text'),
    ('03_テキスト_文字コード違い/連絡文_EUC-JP.txt', '03_テキスト_文字コード違い/連絡文_UTF-16LE.txt', '文字コードまたは改行コードが異なります', 'text'),
    ('04_CSV/在庫_1月.csv', '04_CSV/在庫_2月.csv', 2, 'text'),
    ('06_JSON/config_v2.3.json', '06_JSON/config_v2.4.json', 3, 'text'),
    ('07_Word/議事録_初版.docx', '07_Word/議事録_修正版.docx', 5, 'text'),
    ('08_Excel/予算_当初.xlsx', '08_Excel/予算_修正.xlsx', 3, 'text'),
    ('09_PowerPoint/提案書_v1.pptx', '09_PowerPoint/提案書_v2.pptx', 5, 'text'),
    ('10_PDF_テキスト/見積書_初回.pdf', '10_PDF_テキスト/見積書_再提出.pdf', 3, 'text'),
    ('11_PDF_非埋め込みフォント/お知らせ_旧.pdf', '11_PDF_非埋め込みフォント/お知らせ_新.pdf', 2, 'text'),
    ('16_バイナリ/data_v1.bin', '16_バイナリ/data_v2.bin', 2, 'text'),
    ('13_画像_PNG/図面_RevA.png', '13_画像_PNG/図面_RevB.png', '文字情報のない画像', 'overlay'),
]


def blocks(status):
    m = re.search(r'差分 \S+ / (\d+) 箇所', status)
    return int(m.group(1)) if m else None


async def main():
    async with Tool(O, 1440, 900) as t:
        for a, b, exp, tab in PAIRS:
            if await t.js('App.tab') != 'text': await t.tab('text')
            await t.load(C + a, C + b)
            st = await t.status(); name = a.split('/')[0]
            ok = blocks(st) == exp if isinstance(exp, int) else exp in st
            t.check(f'{name}：差分 {exp}', ok, st[:70])
            t.check(f'{name}：タブ {tab}', await t.js('App.tab') == tab)

        await t.tab('overlay')
        t.check('重ね合わせ（PNG）で変更箇所を検出', '箇所の変更を検出' in await t.ov_stats())
        await t.load(C + '10_PDF_テキスト/見積書_初回.pdf', C + '10_PDF_テキスト/見積書_再提出.pdf'); await t.page.wait_for_timeout(1500)
        s = await t.ov_stats()
        t.check('重ね合わせ（PDF）で3箇所を検出', s.startswith('3 箇所'), s[:40])
        for m in ['overlay', 'swipe', 'blink', 'side', 'diff']:
            await t.click(f'#ovModes button[data-mode={m}]'); await t.page.wait_for_timeout(300)
            t.check(f'表示方法 {m} に切り替わる', await t.js(f"document.querySelector('#ovModes button[data-mode={m}]').classList.contains('on')"))
        await t.click('#ovScan')
        await t.wait_for("document.querySelector('#ovScanRes').textContent.includes('変更ありのページ')", 60)
        r = (await t.page.inner_text('#ovScanRes')).replace('\n', ' ')
        t.check('一括チェック：1ページ目だけに変更、件数は1ページ表示と一致（3箇所）', '変更ありのページ: 1 / 2' in r and re.search(r'\b1\s+3\b', r), r[:80])

        await t.tab('page'); await t.shot('reg_page')
        await t.tab('text'); await t.click('#tLayout'); await t.shot('reg_unified'); await t.click('#tLayout')

        # 英数字だけのファイルに日本語を入れて保存 → 文字コードを聞き、Shift_JIS で保存できる
        await t.load(W + 'R08/ascii_l.ini', W + 'R08/ascii_l.ini')
        await t.click('.slot[data-side="0"] button[data-act=edit]'); await t.page.fill('#edTa', '[a]\nname=日本語\n'); await t.click('.dlg .foot button.primary')
        await t.click('.slot[data-side="0"] button[data-act=save]'); await t.page.wait_for_timeout(300)
        h = await t.page.inner_text('#modal .dlg h3') if await t.js("$('#modal').classList.contains('on')") else ''
        t.check('英数字のファイルに日本語を入れると、保存する文字コードを聞く', h == '保存する文字コード', h)
        p = await t.download('.dlg .foot button:has-text("Shift_JIS")')
        t.check('Shift_JIS・CRLF・末尾改行ありで保存', open(p, 'rb').read() == '[a]\r\nname=日本語\r\n'.encode('cp932'), open(p, 'rb').read())

        # レポートを印刷表示で開ける
        await t.load(C + '07_Word/議事録_初版.docx', C + '07_Word/議事録_修正版.docx'); rp = await t.download('#tReport')
        pg2 = await t.ctx.new_page(); await pg2.goto('file://' + rp); await pg2.emulate_media(media='print')
        await pg2.screenshot(path=os.path.join(O, 'report_print.png'))
        t.check('レポートに差分の行がある', await pg2.evaluate("document.querySelectorAll('td.t-c, td.t-d, td.t-i').length") == 10)
        await pg2.close()
        t.finish()

asyncio.run(main())
