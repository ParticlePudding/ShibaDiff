"""3回目のレビュー（仕様・UI・実装）で見つかった不具合と抜けの修正"""
import asyncio, json, os, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
from harness import Tool, OUT as O
import gen_samples as G
from reportlab.pdfgen import canvas

D = os.path.join(O, 'r3')
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def zipto(path, files):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items(): z.writestr(name, data)


def make_docx(path):
    """ヘッダー・フッター（ページ番号のフィールド）と変更履歴（挿入・削除・移動）のある Word 文書"""
    run = lambda t: f'<w:r><w:t xml:space="preserve">{t}</w:t></w:r>'
    doc = f'''<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body>
<w:p>{run("第1条 目的")}</w:p>
<w:p>{run("契約金額は")}<w:del w:id="1" w:author="A"><w:r><w:delText>100</w:delText></w:r></w:del><w:ins w:id="2" w:author="A">{run("120")}</w:ins>{run("万円とする。")}</w:p>
<w:p><w:moveFrom w:id="3" w:author="A">{run("この文は移動した。")}</w:moveFrom></w:p>
<w:p>{run("第2条 期間")}</w:p>
<w:p><w:moveTo w:id="4" w:author="A">{run("この文は移動した。")}</w:moveTo></w:p>
<w:sectPr><w:headerReference w:type="default" r:id="rId1"/><w:footerReference w:type="default" r:id="rId2"/></w:sectPr>
</w:body></w:document>'''
    hdr = f'<?xml version="1.0" encoding="UTF-8"?><w:hdr {W}><w:p>{run("文書番号 QA-001　第3版　社外秘")}</w:p></w:hdr>'
    fld = lambda t: f'<w:r><w:fldChar w:fldCharType="{t}"/></w:r>'
    ftr = (f'<?xml version="1.0" encoding="UTF-8"?><w:ftr {W}><w:p>{run("- ")}{fld("begin")}<w:r><w:instrText> PAGE </w:instrText></w:r>{fld("separate")}{run("1")}{fld("end")}'
           f'{run(" / ")}<w:fldSimple w:instr=" NUMPAGES ">{run("5")}</w:fldSimple>{run(" -")}</w:p></w:ftr>')
    rels = (f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{REL}/header" Target="header1.xml"/><Relationship Id="rId2" Type="{REL}/footer" Target="footer1.xml"/></Relationships>')
    # header2.xml は先頭ページ用などの「同じ内容のヘッダー」。1回だけ出ること
    zipto(path, {'[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
                 'word/document.xml': doc, 'word/_rels/document.xml.rels': rels, 'word/header1.xml': hdr, 'word/header2.xml': hdr, 'word/footer1.xml': ftr})


def make_xlsx(path):
    """共有数式（下へ・右へコピーした数式）、時刻だけの書式の 0、非表示のシートのある Excel ブック"""
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    wb = (f'<?xml version="1.0" encoding="UTF-8"?><workbook {ns} xmlns:r="{REL}"><sheets>'
          f'<sheet name="見積" sheetId="1" r:id="rId1"/><sheet name="原価" sheetId="2" state="hidden" r:id="rId2"/></sheets></workbook>')
    rels = (f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{REL}/worksheet" Target="worksheets/sheet2.xml"/></Relationships>')
    styles = (f'<?xml version="1.0" encoding="UTF-8"?><styleSheet {ns}><numFmts count="1"><numFmt numFmtId="164" formatCode="[h]:mm"/></numFmts>'
              f'<cellXfs count="4"><xf numFmtId="0"/><xf numFmtId="20"/><xf numFmtId="14"/><xf numFmtId="164"/></cellXfs></styleSheet>')
    n = lambda ref, v, extra='': f'<c r="{ref}"{extra}><v>{v}</v></c>'
    s1 = f'''<?xml version="1.0" encoding="UTF-8"?><worksheet {ns}><sheetData>
<row r="1">{n("A1", 1)}{n("B1", 2)}{n("C1", 3)}{n("D1", 0, ' s="1"')}{n("E1", 0.5, ' s="1"')}{n("F1", 45000, ' s="2"')}{n("G1", 0, ' s="3"')}</row>
<row r="2">{n("A2", 2)}{n("B2", 3)}<c r="C2"><f t="shared" ref="C2:C4" si="0">A2*B2*$A$1</f><v>6</v></c></row>
<row r="3">{n("A3", 3)}{n("B3", 4)}<c r="C3"><f t="shared" si="0"/><v>12</v></c></row>
<row r="4">{n("A4", 4)}{n("B4", 5)}<c r="C4"><f t="shared" si="0"/><v>20</v></c></row>
<row r="5">{n("A5", 9)}<c r="B5"><f t="shared" ref="B5:C5" si="1">SUM(B$2:B4)</f><v>12</v></c><c r="C5"><f t="shared" si="1"/><v>38</v></c></row>
</sheetData></worksheet>'''
    s2 = f'<?xml version="1.0" encoding="UTF-8"?><worksheet {ns}><sheetData><row r="1">{n("A1", 777)}</row></sheetData></worksheet>'
    zipto(path, {'[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
                 'xl/workbook.xml': wb, 'xl/_rels/workbook.xml.rels': rels, 'xl/styles.xml': styles, 'xl/worksheets/sheet1.xml': s1, 'xl/worksheets/sheet2.xml': s2})


def make():
    os.makedirs(D, exist_ok=True)
    make_docx(os.path.join(D, '契約書_履歴あり.docx')); make_xlsx(os.path.join(D, '見積_共有数式.xlsx'))
    c = canvas.Canvas(os.path.join(D, 'pw.pdf'), encrypt='secret'); c.drawString(72, 720, 'Hello password protected'); c.showPage(); c.save()
    for name, lines in (('a.txt', 'alpha\nbeta\ngamma\n'), ('b.txt', 'alpha\nBETA\ngamma\n'), ('c.txt', 'one\ntwo\n'), ('d.txt', 'one\n2\n')):
        open(os.path.join(D, name), 'w', encoding='utf-8', newline='').write(lines)
    for side in ('L', 'R'):
        os.makedirs(os.path.join(D, 'FD', side), exist_ok=True)
        for i, nm in enumerate(('1_a.txt', '2_b.txt', '3_c.txt')):
            open(os.path.join(D, 'FD', side, nm), 'w').write(f'{nm} {side if i == 1 else ""}\n')
    # ページ数が同じスキャン：2ページ目を削除し、6ページ目に別紙を挿入（どちらも8ページ）
    G.ROOT = D
    body = lambda k: [f'## 第{k}章 {"概要 手順 検査 記録 保管 改訂 付則 様式".split()[k % 8]}'] + [f'{k}-{i} ' + ('手順書の内容を確認し、記録を残すこと。' if (i + k) % 3 else '担当者は責任者の承認を得てから作業を始める。') * (1 + (i * k) % 3) for i in range(1, 6 + k * 2 % 7)]
    a = [body(k) for k in range(1, 9)]
    x = ['## 追加 別紙', '別紙1 点検表', '項目 判定 備考', '外観 良 なし', '寸法 良 なし', '動作 否 再検査']
    b = [a[0], a[2], a[3], a[4], a[5], x, a[6], a[7]]
    G.scan_pdf('scan_a.pdf', [G.page_image(p, '手順書') for p in a])
    G.scan_pdf('scan_b.pdf', [G.page_image(p, '手順書', offset=(6, -4), rot=0.3) for p in b])


async def dl(t, sel):
    async with t.page.expect_download() as d: await t.page.click(sel)
    v = await d.value; p = os.path.join(t.out_dir, v.suggested_filename); await v.save_as(p); return p


async def reload(t):
    await t.page.reload()
    await t.page.evaluate("window.showSaveFilePicker = undefined")
    await t.page.wait_for_timeout(300)


async def main():
    make()
    f = lambda n: os.path.join(D, n)
    async with Tool(O, 1366, 768) as t:
        ck, p = t.check, t.page
        title = lambda: p.inner_text('#modal h3')

        # ---- 比較条件のバッジ：前回の条件を戻した直後（起動時）から出す ----
        await t.js("localStorage.setItem('doccmp:textopts', JSON.stringify({ ws: 'all', ignoreCase: true, blank: false, zen: false, fold: false }))")
        await reload(t)
        ck('起動時：戻した比較条件の数をバッジに出す', await p.is_visible('#oBadge') and await p.inner_text('#oBadge') == '2', await p.inner_text('#oBadge'))
        ck('起動時：比較条件そのものも戻っている', await t.js("[document.querySelector('#oWs').value, document.querySelector('#oCase').checked]") == ['all', True])
        await t.js("localStorage.removeItem('doccmp:textopts')"); await reload(t)
        ck('条件を変えていなければバッジは出ない', not await p.is_visible('#oBadge'))

        # ---- 自動保存をオフにするとき：注釈だけでなく、変更点のコメント・回転も削除の対象にする（ブラウザの confirm は使わない） ----
        seed = ("localStorage.setItem('doccmp:settings', JSON.stringify({ persist: true }));"
                "localStorage.setItem('doccmp:ann:a.pdf|1|2', '{\"0\":[]}'); localStorage.setItem('doccmp:notes:a.pdf|1|2||b.pdf|3|4', '{\"t:abc:0\":{\"st\":\"ok\",\"text\":\"社外秘のメモ\"}}'); localStorage.setItem('doccmp:rot:a.pdf|1|2', '90')")
        keys = "Object.keys(localStorage).filter(k => /^doccmp:(ann|notes|rot):/.test(k)).length"
        await t.js(seed); await reload(t)
        await t.click('#btnSettings'); await p.click('#modal [data-k="persist"]'); await p.wait_for_timeout(300)
        body = await p.inner_text('#modal .body')
        ck('オフにすると、保存済みのデータを残すか聞く（アプリのダイアログ）', await title() == '保存済みのデータ' and '変更点のコメント 1 件' in body and '注釈 1 件' in body and 'ページの回転 1 件' in body, body[:80])
        await p.click('#modal .foot button:has-text("残す")'); await p.wait_for_timeout(300)
        ck('「残す」：データは残り、設定のダイアログに戻る', await t.js(keys) == 3 and await title() == '設定' and await t.js("Settings.get('persist')") is False)
        ck('戻った設定のダイアログは、操作した状態のまま（チェックが外れている）', await t.js("document.querySelector('#modal [data-k=\"persist\"]').checked") is False)
        await p.click('#modal [data-k="persist"]'); await p.wait_for_timeout(200)   # オンに戻す
        await p.click('#modal [data-k="persist"]'); await p.wait_for_timeout(300)   # もう一度オフ
        await p.click('#modal .foot button:has-text("削除する")'); await p.wait_for_timeout(300)
        ck('「削除する」：注釈・変更点のコメント・回転をすべて消す', await t.js(keys) == 0 and await t.js("!!localStorage.getItem('doccmp:settings')"))
        await p.keyboard.press('Escape'); await p.wait_for_timeout(200)
        ck('設定を閉じると、ダイアログは残らない', not await p.is_visible('#modal.on') and await t.js('modalStack.length') == 0)

        # ---- ダイアログの重なり：開いている間に別のダイアログが開いても、下のダイアログを置き去りにしない ----
        await t.click('#btnHelp')
        await t.js("window.__m2 = modal({ title: '重ねたダイアログ', html: '<input type=\"text\" id=\"m2in\">', buttons: [{ label: 'OK', primary: true, value: 'ok' }] }); 0")
        await p.wait_for_timeout(200)
        ck('上に重ねたダイアログが出る', await title() == '重ねたダイアログ' and await t.js('modalStack.length') == 2)
        await p.keyboard.press('Escape'); await p.wait_for_timeout(200)
        ck('Esc は上のダイアログだけを閉じ、下のダイアログ（ヘルプ）に戻る', await title() == 'ヘルプ' and await p.is_visible('#modal.on') and 'ファイルの読み込み' in await p.inner_text('#modal .body'))
        await p.keyboard.press('Escape'); await p.wait_for_timeout(200)
        ck('もう一度 Esc で下のダイアログも閉じる', not await p.is_visible('#modal.on') and await t.js('modalStack.length') == 0)

        # ---- パスワード付きPDF：伏せ字の入力欄、Enter で確定、「処理中」の幕に隠れない ----
        await p.set_input_files('.slot[data-side="0"] input[type=file]', f('pw.pdf'))
        await p.wait_for_selector('#modal.on #askPw', timeout=20000)
        ck('パスワードは伏せ字の1行の入力欄（textarea ではない）', await t.js("document.querySelector('#askPw').type") == 'password' and await t.js("document.activeElement.id") == 'askPw')
        hit = await t.js("(() => { const r = document.querySelector('#askPw').getBoundingClientRect(); return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2).id; })()")
        ck('入力欄は「処理中」の幕に隠れず、クリックできる', hit == 'askPw', hit)
        await p.click('#askPw'); await p.keyboard.type('wrong'); await p.keyboard.press('Enter'); await p.wait_for_timeout(1500)
        ck('Enter で確定。違うときは聞き直し、前の入力は残さない', 'パスワードが違います' in await title() and await p.input_value('#askPw') == '')
        await p.check('#askPwShow')
        ck('「入力した文字を表示する」で確かめられる', await t.js("document.querySelector('#askPw').type") == 'text')
        await p.fill('#askPw', 'secret'); await p.keyboard.press('Enter')
        await t.wait_for("!!(S[0] && S[0].name === 'pw.pdf')"); await t.wait_idle()
        ck('正しいパスワードで開ける', 'Hello password protected' in await t.js("S[0].lines.join(' ')") and not await p.is_visible('#modal.on'))
        ck('閉じたあとの画面に、入力したパスワードを残さない', await t.js("!document.querySelector('#askPw') || document.querySelector('#askPw').value === ''"))
        await p.set_input_files('.slot[data-side="1"] input[type=file]', f('pw.pdf'))
        await p.wait_for_selector('#modal.on #askPw', timeout=20000)
        await p.click('#modal .foot button:has-text("キャンセル")'); await p.wait_for_timeout(1200)
        ck('キャンセルすれば読み込まず、理由を通知する', await t.js('S[1] === null') and 'パスワードが入力されませんでした' in await t.toast(), await t.toast())
        await t.js("document.querySelector('#btnClear').click()"); await p.wait_for_timeout(300)

        # ---- Word：ヘッダー・フッター、変更履歴の通知 ----
        await t.load_one(0, f('契約書_履歴あり.docx'))
        toast = await t.toast()
        L = await t.js('S[0].lines')
        ck('Word：ヘッダーを取り出す（同じ内容のヘッダーは1回だけ）', '===== ヘッダー =====' in L and L.count('文書番号 QA-001　第3版　社外秘') == 1, L)
        ck('Word：フッターを取り出し、ページ番号のフィールドは印にする', '===== フッター =====' in L and '- ‹ページ番号› / ‹総ページ数› -' in L, L)
        ck('Word：変更履歴は承諾した状態（削除と、移動する前の文は読まない）', '契約金額は120万円とする。' in L and L.count('この文は移動した。') == 1, L)
        ck('Word：変更履歴が残っていることを通知する', '変更履歴が残っています' in toast and '挿入 2・削除 2' in toast, toast)
        meta = await p.inner_text('.slot[data-side="0"] .slot-info .meta')
        ck('Word：ファイル欄にも「変更履歴あり」', '変更履歴あり' in meta, meta)
        await t.load_one(1, f('契約書_履歴あり.docx'))
        ck('Word：状態表示にも「変更履歴あり」', '変更履歴あり（承諾した状態で比較）' in await t.status())

        # ---- Excel：共有数式、時刻 0:00、非表示のシート ----
        await t.load_one(0, f('見積_共有数式.xlsx'))
        L = await t.js('S[0].lines')
        ck('Excel：共有数式の先頭のセルはそのまま', L[2].split('\t')[2] == '6 ‹=A2*B2*$A$1›', L[2])
        ck('Excel：共有数式の2つ目以降は、行をずらした数式を付ける（$ の付いた参照は動かさない）', L[3].split('\t')[2] == '12 ‹=A3*B3*$A$1›' and L[4].split('\t')[2] == '20 ‹=A4*B4*$A$1›', L[3:5])
        ck('Excel：右へコピーした共有数式は、列をずらす', L[5].split('\t')[1:] == ['12 ‹=SUM(B$2:B4)›', '38 ‹=SUM(C$2:C4)›'], L[5])
        c1 = L[1].split('\t')
        ck('Excel：時刻だけの書式の 0 は 00:00（1899/12/30 にしない）', c1[3] == '00:00' and c1[4] == '12:00' and c1[6] == '00:00', c1)
        ck('Excel：日付の書式はこれまでどおり日付', c1[5] == '2023/03/15', c1)
        ck('Excel：非表示のシートは、見出しに（非表示）と書く', '===== シート: 原価（非表示） =====' in L and '===== シート: 見積 =====' in L, [x for x in L if x.startswith('=====')])
        r = await t.js("[Office.shiftFormula('VLOOKUP(A2,Sheet2!A:C,3,FALSE)&\"A1\"', 1, 1), Office.shiftFormula(\"'Sheet A1'!B2+LOG10(C2)+AB1!C3\", 2, 0)]")
        ck('Excel：数式のずらし方（列の範囲・文字列・シート名・関数名）', r == ['VLOOKUP(B3,Sheet2!B:D,3,FALSE)&"A1"', "'Sheet A1'!B4+LOG10(C4)+AB1!C5"], r)

        # ---- 検索：CJK部首補助の文字もそろえる ----
        await t.js("document.querySelector('#btnClear').click()"); await p.wait_for_timeout(300)
        await t.js("S[0] = App.newTextSide(); S[0].lines = ['歯科検診の結果', '上⻑印']; S[1] = App.newTextSide(); S[1].lines = ['歯科検診の結果', '上⻑印']; App.updateSlot(0); App.updateSlot(1); TV.compare()")
        await p.fill('#searchBox', '⻭科'); await p.click('#tFind'); await p.wait_for_timeout(200)
        ck('検索：部首補助の「⻭」で「歯」が見つかる', await t.js('TV.st.hit') == 0 and '1 / 1 件' in await t.toast(), await t.toast())
        await p.fill('#searchBox', '上長'); await p.click('#tFind'); await p.wait_for_timeout(200)
        ck('検索：「長」で部首補助の「⻑」が見つかる', await t.js('TV.st.hit') == 1, await t.toast())
        await p.fill('#searchBox', '')

        # ---- ISO-2022-JP：濁点付きの半角カナ ----
        r = await t.js("(() => { const r = Enc.encode('ｶﾞｷﾞ ﾊﾟ ｳﾞ ｱﾞ ｱｲｳ', 'iso-2022-jp'); return [r.unmapped, new TextDecoder('iso-2022-jp').decode(r.bytes)]; })()")
        ck('JIS で保存：濁点・半濁点付きの半角カナを1文字の全角にする（? にしない）', r == [0, 'ガギ パ ヴ ア゛ アイウ'], r)

        # ---- 読み上げ用の名前：文字のあるボタンは見えている文字のまま ----
        r = await t.js("['#ovHand', '#tPrev', '#btnSettings', '#tFirst', '#btnSwap'].map(s => document.querySelector(s).getAttribute('aria-label'))")
        ck('文字のあるボタンには aria-label を付けない（見えている名前と食い違わせない）', r[:3] == [None, None, None], r)
        ck('記号だけのボタンには aria-label を付ける', r[3] == '最初の差分' and r[4] == '左右を入れ替え', r)

        # ---- 注釈ファイルの変更点のコメント：別の文書には、確かめてから読み込む ----
        await t.load(f('a.txt'), f('b.txt'))
        await t.js("Notes.set(TV.st.noteIds[0], { st: 'ask', text: '大文字に変わった理由を確認' })")
        await t.tab('page')
        ann = await dl(t, '#annExport')
        await t.tab('text'); await t.load(f('c.txt'), f('d.txt')); await t.tab('page')
        await p.set_input_files('#annFile', ann); await p.wait_for_timeout(500)
        body = await p.inner_text('#modal .body') if await p.is_visible('#modal.on') else ''
        ck('別の文書を開いているときは、コメントを読み込む前に確かめる', await title() == '変更点のコメントの読み込み' and 'a.txt' in body and 'c.txt' in body, body[:90])
        await p.click('#modal .foot button:has-text("読み込まない")'); await p.wait_for_timeout(400)
        ck('「読み込まない」：別の文書の組にコメントを足さない', await t.js('Object.keys(Notes.all()).length') == 0, await t.toast())
        await p.set_input_files('#annFile', ann); await p.wait_for_timeout(500)
        await p.click('#modal .foot button.primary'); await p.wait_for_timeout(400)
        ck('「読み込む」を選べば足す', await t.js('Object.keys(Notes.all()).length') == 1)
        await t.js('Notes.clear()')
        await t.tab('text'); await t.load(f('a.txt'), f('b.txt')); await t.js('Notes.clear()'); await t.tab('page')
        await p.set_input_files('#annFile', ann); await p.wait_for_timeout(600)
        ck('同じ文書の組なら、確かめずに読み込む', not await p.is_visible('#modal.on') and await t.js("Object.values(Notes.all()).map(v => v.text)") == ['大文字に変わった理由を確認'], await t.toast())

        # ---- 左右の入れ替え：コメントが見えなくなることを知らせる ----
        await t.tab('text'); await t.js('App.showSlots(true)')
        await p.click('#btnSwap'); await p.wait_for_timeout(300)
        ck('入れ替えると、コメントが別の組に付いていることを通知する', '変更点のコメント 1 件' in await t.toast() and await t.js('Object.keys(Notes.all()).length') == 0, await t.toast())
        await p.click('#btnSwap'); await p.wait_for_timeout(300)
        ck('もう一度入れ替えると、コメントは戻る', await t.js('Object.keys(Notes.all()).length') == 1)
        await t.js('Notes.clear()')

        # ---- ページ表示の変更箇所：調べている間の印、位置合わせを変えたら求め直す ----
        await t.load(f('scan_a.pdf'), f('scan_b.pdf'))
        await t.wait_for("App.tab === 'overlay'"); await p.wait_for_timeout(2500); await t.wait_idle()
        info = await p.inner_text('#ovMatchInfo')
        ck('ページ数が同じスキャン：調べていないのに「挿入・削除はありません」とは言わない', 'ページ数が同じスキャン' in info and 'ありません' not in info, info)
        await t.js("window.__busy = false; new MutationObserver(() => { if (document.querySelector('#pvChanges').classList.contains('busy')) window.__busy = true; }).observe(document.querySelector('#pvChanges'), { attributes: true }); 0")
        await t.tab('page'); await t.wait_for("document.querySelector('#pvChanges').getAttribute('aria-busy') === 'false' && document.querySelectorAll('.pv-chg .cb').length > 0", 120)
        ck('ページ表示：変更箇所を調べている間、ボタンに印を出し、終わったら消す', await t.js('window.__busy') is True and not await t.js("document.querySelector('#pvChanges').classList.contains('busy')"))
        await t.tab('overlay'); await p.wait_for_timeout(500)
        await t.js("window.__r1 = OV.regionsFor(0, 0); 0")
        await p.fill('#ovDx', '12'); await p.dispatch_event('#ovDx', 'change'); await p.wait_for_timeout(1500); await t.wait_idle()
        ck('位置合わせを変えたら、ページ表示用の変更箇所を求め直す（覚えた結果を捨てる）', await t.js('OV.regionsFor(0, 0) !== window.__r1'))
        # 見た目での対応付け（ページ数が同じでも、頼めば調べる）
        await p.click('#ovRematch'); await t.wait_for('!PageMatch.skipped()', 90); await p.wait_for_timeout(1500); await t.wait_idle()
        pairs = await t.js('PageMatch.ready().map(q => [q.l, q.r])')
        ck('見た目で対応を調べ直すと、削除されたページと挿入されたページを見つける', pairs == [[0, 0], [1, -1], [2, 1], [3, 2], [4, 3], [5, 4], [-1, 5], [6, 6], [7, 7]], pairs)
        info = await p.inner_text('#ovMatchInfo')
        ck('結果を右のパネルに示し、ボタンは消える', '右で追加されたページ：6' in info and '左から削除されたページ：2' in info and not await p.is_visible('#ovRematch'), info)

        # ---- フォルダ比較：↑↓ で行を選び、Enter で開く ----
        await t.load_folders(os.path.join(D, 'FD', 'L'), os.path.join(D, 'FD', 'R'))
        sel = "(() => { const tr = document.querySelector('#fdTable tbody tr.sel'); return tr ? [tr.querySelector('.path').textContent, tr.getAttribute('aria-selected')] : null; })()"
        await p.keyboard.press('ArrowDown'); await p.wait_for_timeout(100)
        ck('フォルダ比較：↓ で最初の行を選ぶ', await t.js(sel) == ['1_a.txt', 'true'], await t.js(sel))
        await p.keyboard.press('ArrowDown'); await p.keyboard.press('ArrowDown'); await p.keyboard.press('ArrowDown'); await p.wait_for_timeout(100)
        ck('フォルダ比較：↓ で次の行へ（最後の行で止まる）', (await t.js(sel))[0] == '3_c.txt', await t.js(sel))
        await p.keyboard.press('ArrowUp'); await p.wait_for_timeout(100)
        ck('フォルダ比較：↑ で前の行へ', (await t.js(sel))[0] == '2_b.txt', await t.js(sel))
        await p.keyboard.press('Home'); r1 = (await t.js(sel))[0]; await p.keyboard.press('End'); r2 = (await t.js(sel))[0]
        ck('フォルダ比較：Home・End で先頭・末尾の行へ', [r1, r2] == ['1_a.txt', '3_c.txt'], [r1, r2])
        await p.keyboard.press('ArrowUp'); await p.keyboard.press('Enter')
        await t.wait_for("App.mode === 'file' && !!S[0] && S[0].name === '2_b.txt'"); await t.wait_idle()
        ck('フォルダ比較：キーボードだけで選んだ行を Enter で開ける', await t.js("S[1].name") == '2_b.txt' and '差分' in await t.status(), await t.status())
        t.finish(allowed_errors=('PasswordException',))  # パスワードの入力をキャンセルしたときの記録（想定どおり）
        n1 = len(t.results)

    # ---- 狭い画面：ツールバーの続きの目印、比較条件のポップアップ ----
    async with Tool(O, 700, 800) as t:
        ck, p = t.check, t.page
        bar = "document.querySelector('#tab-text .toolbar')"
        ck('狭い画面：ツールバーの右に続きがあることを示す', await t.js(bar + ".classList.contains('more-r') && !" + bar + ".classList.contains('more-l')"))
        await t.js(bar + ".scrollLeft = 300"); await p.wait_for_timeout(300)
        ck('狭い画面：スクロールすると、左にも続きがあることを示す', await t.js(bar + ".classList.contains('more-l') && " + bar + ".classList.contains('more-r')"))
        await p.click('#oPop summary'); await p.wait_for_timeout(300)
        r = await t.js("(() => { const b = document.querySelector('#oPop .pop-body').getBoundingClientRect(); const el = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return [b.left >= 0 && b.right <= innerWidth && b.height > 80, !!el.closest('#oPop .pop-body')]; })()")
        ck('狭い画面：比較条件のポップアップが、切り取られずに画面の中に出る', r == [True, True], r)
        await p.check('#oCase'); await p.wait_for_timeout(200)
        ck('狭い画面：ポップアップの中の条件を変えられる', await p.inner_text('#oBadge') == '1')
        await t.js(bar + ".scrollLeft = 99999"); await p.wait_for_timeout(300)
        ck('狭い画面：右端までスクロールすると右の目印が消え、ポップアップは閉じる', await t.js("!" + bar + ".classList.contains('more-r') && !document.querySelector('#oPop').open"))
        t.finish()
        print(f'== {n1 + len(t.results)} / {n1 + len(t.results)} OK', flush=True)  # 2つの画面幅の合計（run_all.py は最後の == の行を表示する）

if __name__ == '__main__':
    asyncio.run(main())
