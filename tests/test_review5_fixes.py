"""3回目の利用者レビュー（20人、2026-11-28）で見つかった不具合の修正（v1.5.14）"""
import asyncio, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
from harness import Tool, SAMPLES as SM, OUT as O
import gen_samples as G
import openpyxl
from PIL import Image, ImageDraw

D = os.path.join(O, 'r5')
C = SM + '00_共通サンプル（形式別）/'


def w(name, s, enc='utf-8', eol='\n'):
    p = os.path.join(D, name); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(s.replace('\n', eol).encode(enc)); return p


def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()[:300]


ROWS = "TV.st.rows.map(r => [r.a, r.b, r.t])"


async def main():
    shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
    async with Tool(D) as t:
        ck, p = t.check, t.page

        async def opt(sel, on):
            """比較条件のチェックを切り替える（吹き出しの中にあるので、値を入れて change を送る）"""
            await t.js(f"(() => {{ const e = document.querySelector('{sel}'); if (e.checked !== {str(on).lower()}) {{ e.checked = {str(on).lower()}; e.dispatchEvent(new Event('change', {{ bubbles: true }})); }} }})()")
            await p.wait_for_timeout(300)

        # ---- 行の対応付け：削除と番号の繰り上げ ----
        body = lambda k: f'本文{k}。' + f'この請求項{k}に固有の構成要素は、第{k}の部材と第{k}の制御部とを備える装置である。' * 3
        a = ['【請求項１】', body('甲'), '', '【請求項２】', body('乙'), '', '【請求項３】', body('丙'), '', '【請求項４】', body('丁')]
        b = ['【請求項１】', body('甲'), '', '【請求項２】', body('丙'), '', '【請求項３】', body('丁')]
        await t.load(w('claims_a.txt', '\n'.join(a) + '\n'), w('claims_b.txt', '\n'.join(b) + '\n'))
        rows = await t.js(ROWS)
        pair = {r[0]: (r[1], r[2]) for r in rows if r[0] >= 0}
        ck('請求項を1つ削って番号を繰り上げた文書：本文は、同じ本文どうしが並ぶ（1つずれた相手と「変更」にしない）',
           pair[7] == (4, 'e') and pair[10] == (7, 'e') and pair[4][0] == -1, [pair[4], pair[7], pair[10]])
        acl_a = ['ip access-list extended ACL-IN', ' 10 permit tcp 10.10.110.0 0.0.0.255 host 10.10.200.11 eq 443', ' 20 permit tcp 10.10.150.0 0.0.0.255 host 10.10.200.41 eq 3389',
                 ' 30 permit tcp 10.10.120.0 0.0.0.255 host 10.10.200.21 eq 1433', ' 40 permit udp 10.10.130.0 0.0.0.255 host 10.10.200.5 eq 53', ' 50 deny ip any any log']
        acl_b = [acl_a[0], acl_a[1], acl_a[3].replace(' 30 ', ' 20 '), acl_a[4].replace(' 40 ', ' 30 '), acl_a[5].replace(' 50 ', ' 40 ')]
        await t.load(w('acl_a.txt', '\n'.join(acl_a) + '\n'), w('acl_b.txt', '\n'.join(acl_b) + '\n'))
        rows = await t.js(ROWS)
        ck('1行の削除と番号のずれ：削除した行は「左のみ」、残りは同じ規則どうしを並べる', rows == [[0, 0, 'e'], [1, 1, 'e'], [2, -1, 'd'], [3, 2, 'c'], [4, 3, 'c'], [5, 4, 'c']], rows)

        # ---- 全角・半角を区別しない：幅の違いだけ ----
        r = await t.js("[foldWidth('ＡＢＣ　ｶﾞ１２３'), foldWidth('10³ ① ㈱ Ⅲ H₂O')]")
        ck('全角半角の正規化は、幅の違いだけをそろえる（上付き・丸数字・組文字・ローマ数字は変えない）', r == ['ABC ガ123', '10³ ① ㈱ Ⅲ H₂O'], r)
        await t.load(w('zen_a.txt', '粒径 10³ µm\nＡＢＣ商事　１００円\n型式 ＴＷ－２１\n'), w('zen_b.txt', '粒径 103 µm\nABC商事 200円\n型式 TW-21\n'))
        await opt('#oZen', True)
        rows = await t.js(ROWS)
        ck('全角半角を区別しない：10³ と 103 は違う行、全角と半角だけが違う行は同じ', rows == [[0, 0, 'c'], [1, 1, 'c'], [2, 2, 'e']], rows)
        cds = await t.js("[...document.querySelectorAll('#paneL .row.t-c .cd, #paneR .row.t-c .cd')].map(e => e.textContent)")
        ck('変更行の中の印も、比較の条件に合わせる（幅だけが違う「ＡＢＣ商事」には印を付けない）', sorted(cds) == sorted(['³', '103', '１００', '200']), cds)
        tags = await t.js("[document.querySelector('#paneL .row.t-c .cd').tagName, document.querySelector('#paneR .row.t-c .cd').tagName, document.querySelector('#paneL .row.t-c .mk').getAttribute('aria-label'), document.querySelector('#paneR .row.t-c .mk').getAttribute('aria-label'), document.querySelector('#paneL').getAttribute('aria-label')]")
        ck('変わった文字は del・ins の要素、行頭の印は読み上げ用の名前を持つ', tags == ['DEL', 'INS', '変更前', '変更後', '左の文書（比較結果）'], tags)
        await opt('#oZen', False)

        # ---- 数字の差の札：量ではない番号には付けない ----
        nd = lambda a, b: f"JSON.stringify(Diff.numberDeltas(Diff.chars({json.dumps(a, ensure_ascii=False)}, {json.dumps(b, ensure_ascii=False)})).map(d => d.text))"
        skip = [('第3条', '第4条'), ('型式 TW-21', '型式 TW-25'), ('host 192.168.1.10', 'host 192.168.1.20'), ('order-webapp v2.5.17', 'order-webapp v2.5.18'), ('【０００６】', '【０００７】'),
                ('Windows 11 24H2', 'Windows 11 25H2'), ('Rev.2', 'Rev.3'), ('第4版', '第5版'), ('- 3 -', '- 4 -'), ('請求項3に記載の', '請求項2に記載の')]
        bad = [(a, b, r) for a, b in skip if (r := await t.js(nd(a, b))) != '[]']
        ck('条・版・型式・IP アドレス・版番号・段落番号・ページ番号には、差の札を付けない', not bad, bad)
        r = [await t.js(nd('数量 100個', '数量 120個')), await t.js(nd('年1.475％', '年1.500％'))]
        ck('量の数字には今までどおり付ける（％はポイント）', '+20' in r[0] and 'ポイント' in r[1], r)
        r = await t.js("(() => { const cd = Diff.chars('数量 10', '数量 10個'); return [cd.a, cd.b.map(x => cd.B.slice(x[0], x[1]).join(''))]; })()")
        ck('数字の後ろに文字が足されただけのとき、左の数字を削除の表示にしない', r == [[], ['個']], r)

        # ---- 長い1行：違いが少なければ、変わった所だけ ----
        r = await t.js("""(() => { let s = ''; for (let i = 0; i < 9000; i++) s += `function f${i}(a,b){return a+b+${i * 7 % 1000}}`;
          const s2 = s.replace('function f777(a,b){return a+b+439}', 'function f777(a,b){return a+b+4242}').replace('f8000(', 'g8000(');
          const t0 = performance.now(), cd = Diff.chars(s, s2, 'auto'); return [s.length > 200000, s !== s2, cd.a.length, cd.a.reduce((n, x) => n + x[1] - x[0], 0), Math.round(performance.now() - t0)]; })()""")
        ck('20万文字を超える1行でも、変わった2か所だけに印を付ける（全体を塗らない）', r[0] and r[1] and r[2] == 2 and r[3] < 20 and r[4] < 5000, r)

        # ---- Excel：行を足して番号がずれただけの数式は、変更にしない ----
        def book(path, extra):
            wb = openpyxl.Workbook(); ws = wb.active; ws.title = '見積'
            ws.append(['No', '品名', '数量', '単価', '金額'])
            items = [('ボルト M8', 120, 45), ('ナット M8', 120, 12), ('ワッシャ', 240, 3), ('ブラケット', 16, 1850), ('カバー', 8, 4200), ('取付金具', 8, 960)]
            if extra: items.insert(2, ('スプリングワッシャ', 120, 5))
            for i, (nm, q, u) in enumerate(items):
                r_ = i + 2; ws.append(['=ROW()-1', nm, q, u, f'=C{r_}*D{r_}'])
            n = len(items) + 1; ws.append(['', '合計', '', '', f'=SUM(E2:E{n})'])
            wb.save(path); return path
        await t.load(book(os.path.join(D, '見積_前.xlsx'), False), book(os.path.join(D, '見積_後.xlsx'), True))
        st = await t.status(); rows = await t.js(ROWS)
        ck('Excel：行を1つ足しただけなら、足した行と、範囲の広がった合計の行だけが違いになる（以降の行は「数式の番号ずれ」）',
           sum(1 for x in rows if x[2] == 'i') == 1 and sum(1 for x in rows if x[2] == 'c') == 1 and '数式の番号ずれだけの 4 行' in st, (st, [x for x in rows if x[2] != 'e']))
        r = await t.js("[Office.relFormula('SUM(C5:C9)', 10, 3) === Office.relFormula('SUM(C6:C10)', 11, 3), Office.relFormula('SUM($C$5:C9)', 10, 3) === Office.relFormula('SUM($C$5:C9)', 11, 3), Office.relFormula('C5*D5', 5, 5) === Office.relFormula('C6*D7', 6, 5)]")
        ck('数式の相対的な形：ずれただけなら同じ、絶対参照・相手のずれが違えば別', r == [True, False, False], r)

        # ---- パッチ：日本語の名前は git の引用形式（Shift_JIS のファイルでも当たる） ----
        nm = '議事録 第3回.txt'
        pa = w('patch/a/' + nm, '第3回 定例会議 議事録\n出席：山田、鈴木\n決定事項：納期を11月末とする\n以上\n', 'shift_jis', '\r\n')
        pb = w('patch/b/' + nm, '第3回 定例会議 議事録\n出席：山田、鈴木、高橋\n決定事項：納期を12月10日とする\n以上\n', 'shift_jis', '\r\n')
        await t.load(pa, pb)
        pt = await t.download('#tPatch'); head = open(pt, 'rb').read().split(b'\n')[0].decode('ascii', 'replace')
        ck('パッチの見出し：日本語の名前は、UTF-8 のバイトを8進で書いた引用形式', head.startswith('diff --git "a/\\350\\255\\260') and head.endswith('.txt"'), head)
        for how, cmd in [('git', 'git init -q && git apply "{p}"'), ('patch', 'patch -p1 -s < "{p}"')]:
            d = os.path.join(D, 'apply_' + how); os.makedirs(d); shutil.copy(pa, os.path.join(d, nm))
            rc, msg = sh(f'cd "{d}" && ' + cmd.format(p=pt))
            ck(f'日本語の名前・Shift_JIS のパッチ：{how} で当てた結果が右のファイルと一致', rc == 0 and open(os.path.join(d, nm), 'rb').read() == open(pb, 'rb').read(), msg)
        await t.load(C + '07_Word/' + sorted(os.listdir(C + '07_Word'))[0], C + '07_Word/' + sorted(os.listdir(C + '07_Word'))[1])
        await t.download('#tPatch'); await p.wait_for_timeout(200)
        ck('Word の差分を出力したときは、元のファイルには当てられない旨を通知する', '当てられません' in await t.toast(), await t.toast())

        # ---- 文字コード ----
        u16 = list(('これは日本語のテキストです。\r\n改行もあります。数字 123 と ABC も入ります。\r\n' * 30).encode('utf-16-le'))
        r = await t.js(f"[Enc.detect(new Uint8Array({u16})), Enc.detect(new Uint8Array({u16}.map((v, i, a) => a[i ^ 1])))]")
        ck('BOM のない UTF-16（日本語が中心）を判定する', r == ['utf-16le', 'utf-16be'], r)
        sj = w('sjis.txt', '見積書\n品名：ボルト（ステンレス）\n数量：１２０個\n', 'shift_jis', '\r\n')
        await t.load(sj, sj)
        await t.open_slots('.slot[data-side="0"] select[data-act="enc"]')
        await p.select_option('.slot[data-side="0"] select[data-act="enc"]', 'utf-8'); await p.wait_for_timeout(500)
        ck('文字コードを選び直して文字化けしたら、読めない文字の数を通知する', '読めない文字' in await t.toast(), await t.toast())
        await t.open_slots('.slot[data-side="0"] [data-act="save"]')
        await p.click('.slot[data-side="0"] [data-act="save"]'); await p.wait_for_timeout(400)
        ck('文字化けしたまま保存しようとすると、確認を出す', await p.inner_text('#dlgTitle') == '文字化けの確認' and await p.is_visible('#modal.on'), await p.inner_text('#dlgTitle'))
        await p.keyboard.press('Escape'); await p.wait_for_timeout(200)

        # ---- 見えない制御文字 ----
        r = await t.js("[esc('請求書\\u202Etxt.exe'), esc('a\\u2066b<')]")
        ck('向きを変える制御文字（RLO など）は、見える形にして出す', r == ['請求書[U+202E]txt.exe', 'a[U+2066]b&lt;'], r)
        rlo = w('報告書‮txt.exe', 'テスト\n')
        await t.load(w('zw_a.txt', '注文番号 A-1001\n品名 ボルト\n'), w('zw_b.txt', '注文番号 A-​1001\n品名 ボルト\n'))
        r = await t.js("[TV.st.rows.filter(r => r.t === 'c').length, document.querySelectorAll('#paneR .row.t-c .cd .wzw').length, document.querySelectorAll('#paneR .row.t-e .wzw').length]")
        ck('幅のない文字（ゼロ幅スペース）だけが違う行：変わった文字の中に印を出す', r == [1, 1, 0], r)
        await t.load_one(0, rlo)
        r = await t.js("[document.querySelector('#hdrFiles .hf[data-side=\"0\"] .nm').textContent, document.querySelector('.slot[data-side=\"0\"] .fname').textContent]")
        ck('RLO を含むファイル名は、ヘッダとファイル欄に見える形で出す', all('[U+202E]' in x for x in r), r)

        # ---- 保存していないコメント：離れる前・閉じる前に確かめる ----
        await t.load(w('n_a.txt', '一行目\n二行目\n三行目\n'), w('n_b.txt', '一行目\n二行目（変更）\n三行目\n'))
        bu = "(() => { const e = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(e); return e.defaultPrevented; })()"
        r0 = await t.js(bu); await t.js("toast('')")
        await t.js("Notes.set(Notes.textIds(TV.st.blocks, S[0].lines, S[1].lines)[0], { st: 'ask', text: '要確認' })"); await p.wait_for_timeout(400)
        r1 = await t.js(bu); msg = await t.toast()
        ck('保存していないコメントがあると、ページを離れる前に確認が出る（ないときは出ない）', r0 is False and r1 is True, (r0, r1))
        ck('最初に書いたときに、保存されないことを一度知らせる', 'このブラウザには保存しません' in msg, msg)
        await t.open_slots('.slot[data-side="1"] [data-act="close"]')
        await p.click('.slot[data-side="1"] [data-act="close"]'); await p.wait_for_timeout(300)
        body = await p.inner_text('#modal .body') if await p.is_visible('#modal.on') else ''
        ck('保存していないコメントがある文書を閉じる前に、確認を出す', 'まだファイルに保存していません' in body, body)
        await p.click('#modal.on .foot button.primary'); await p.wait_for_timeout(300)
        await t.load_one(1, os.path.join(D, 'n_b.txt'))
        ck('閉じたら、その組のコメントは消える（開き直しても戻らない）', await t.js('Object.keys(Notes.all()).length') == 0)
        await t.js('Unsaved.clear()')

        # ---- テキストの入力：Ctrl+Enter で適用、Esc の前に確認 ----
        await t.open_slots('.slot[data-side="0"] [data-act="edit"]')
        await p.click('.slot[data-side="0"] [data-act="edit"]'); await p.wait_for_timeout(300)
        nm_ = await p.get_attribute('#edTa', 'aria-label')
        await p.fill('#edTa', '一行目\n書き換えた行\n三行目\n'); await p.keyboard.press('Escape'); await p.wait_for_timeout(300)
        t1 = await p.inner_text('#dlgTitle')
        await p.click('#modal.on .foot button:not(.primary)'); await p.wait_for_timeout(300)   # 入力に戻る
        back = await p.input_value('#edTa')
        await p.focus('#edTa'); await p.keyboard.press('Control+Enter'); await p.wait_for_timeout(500)
        ck('入力欄に名前があり、Esc では入力を捨てる前に確認し、戻ると入力が残っている', nm_ == '左のテキスト' and t1 == '入力の破棄' and '書き換えた行' in back, (nm_, t1))
        ck('Ctrl+Enter で適用する', not await p.is_visible('#modal.on') and await t.js("S[0].lines[1]") == '書き換えた行')
        await t.js("S[0].dirty = false; 0")   # 次の読み込みで「保存していない変更」の確認を出さない

        # ---- 読み上げ用の状態・名前 ----
        r = await t.js("""[...document.querySelectorAll('#toolGrp button, #ovModes button, #ovViewSw button')].every(b => b.getAttribute('aria-pressed') === String(b.classList.contains('on')))
          && [...document.querySelectorAll('#tabs button')].every(b => b.getAttribute('aria-selected') === String(b.classList.contains('on')))""")
        missing = await t.js("[...document.querySelectorAll('main input:not([type=file]):not([type=checkbox]), main select')].filter(e => !e.getAttribute('aria-label') && !e.title && !e.closest('label') && !e.placeholder).map(e => e.id || e.className)")
        ck('道具・表示方法・タブのボタンに状態があり、入力欄・選択欄に名前がある', r and not missing, missing)

        # ---- 重ね合わせ：同じ結果になる・画像ファイルの濃さの変化 ----
        await t.load(C + '10_PDF_テキスト/見積書_初回.pdf', C + '10_PDF_テキスト/見積書_再提出.pdf'); await t.tab('overlay')
        await t.wait_for("/箇所/.test(document.querySelector('#ovStats').textContent)", 60)
        got = []
        for _ in range(3):
            await t.js("OV.invalidate()"); await t.tab('text'); await t.tab('overlay')
            await t.wait_for("/箇所/.test(document.querySelector('#ovStats').textContent) && OV.st.cur && OV.st.cur.regions", 60)
            got.append(await t.js("JSON.stringify(OV.st.cur.regions.map(g => [g.x, g.y, g.w, g.h]))"))
        ck('同じ PDF の組は、何度比べても同じ変更箇所になる', len(set(got)) == 1 and got[0] != '[]', [len(json.loads(g)) for g in got])
        hashes = await t.js("""(async () => { const pg = (await S[0].getPages())[0], out = [];
          for (let k = 0; k < 4; k++) { const c = document.createElement('canvas'); await pg.draw(c, 1.6, { exact: true });
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let h = 0; for (let i = 0; i < d.length; i += 4) h = (Math.imul(h, 31) + d[i] + d[i + 1] * 3 + d[i + 2] * 7) | 0; out.push(h); if (k === 1) await new Promise(r => requestAnimationFrame(r)); }
          return out; })()""")
        ck('比較用の描画は、同じページなら何度描いても同じ画素になる', len(set(hashes)) == 1, hashes)

        def screen(path, label, btn, extra=False):
            im = Image.new('RGB', (1000, 600), 'white'); dr = ImageDraw.Draw(im); f = G.font(22)
            for i, nm2 in enumerate(['利用施設', '利用日', '利用時間', '利用人数']):
                dr.text((80, 70 + i * 100), nm2, fill=label, font=f); dr.rectangle([80, 104 + i * 100, 620, 144 + i * 100], outline=(190, 190, 190), width=2)
            dr.rectangle([80, 500, 260, 550], fill=btn); dr.text((120, 512), '申し込む', fill='white', font=f)
            if extra: dr.text((200, 70), '※必須', fill=(190, 30, 30), font=f)
            im.save(path); return path
        await t.load(screen(os.path.join(D, '画面_前.png'), (150, 150, 150), (90, 170, 230)), screen(os.path.join(D, '画面_後.png'), (70, 70, 70), (20, 90, 200), True))
        await t.wait_for("/箇所/.test(document.querySelector('#ovStats').textContent)", 60); await p.wait_for_timeout(400)
        s = await t.ov_stats(); n = await t.js('OV.st.cur.regions.length')
        ck('画面の取り込みどうし（ぴったり重なる PNG）：ラベルの文字を濃くした変更も拾う', n >= 5 and '色の濃さの違いも拾う' in s and 'スキャンの比較では' not in s, (n, s[:80]))
        await p.click('#ovScan'); await t.wait_for("document.querySelectorAll('#ovScanRes tr[data-k]').length > 0", 60)
        r = await t.js("(() => { const tr = document.querySelector('#ovScanRes tr[data-k]'); return [tr.tabIndex, (tr.querySelector('.pv') || {}).textContent || '', document.querySelector('#busyLive').textContent]; })()")
        ck('一括の結果：行は Tab で選べ、変化量を数値でも示し、読み上げにも伝える', r[0] == 0 and r[1].endswith('%') and '変更ありのページ 1 / 1' in r[2], r)
        await p.focus('#ovScanRes tr[data-k]'); await p.keyboard.press('Enter'); await p.wait_for_timeout(300)
        ck('一括の結果の行は、Enter で開ける', await t.js("OV.st.mode") == 'diff')

        # ---- ページ表示：変更箇所の番号札は、文字のない場所に置く ----
        lines = [f'{i + 1:02d} これは行の対応を確かめるための本文です。上の行にも下の行にも文字があります。' for i in range(30)]
        l2 = list(lines); l2[14] = l2[14].replace('本文です', '本文でした')
        await t.load(w('pv_a.txt', '\n'.join(lines) + '\n'), w('pv_b.txt', '\n'.join(l2) + '\n')); await t.tab('page')
        await t.wait_for("document.querySelectorAll('.pv-chg .cb').length >= 2", 60); await p.wait_for_timeout(800)
        r = await t.js("""(() => { const g = document.querySelector('.pv-chg .cb'), rs = g.querySelectorAll('rect'), b = rs[0], l = rs[1], n = k => +l.getAttribute(k), m = k => +b.getAttribute(k);
          const cv = g.closest('.pv-page, .page, div').parentNode.querySelector('canvas') || document.querySelector('.pv-pane canvas');
          const k = cv.width / (cv.getBoundingClientRect().width / (g.ownerSVGElement.getBoundingClientRect().width / g.ownerSVGElement.viewBox.baseVal.width)), d = cv.getContext('2d').getImageData(Math.round(n('x') * k), Math.round(n('y') * k), Math.max(1, Math.round(n('width') * k)), Math.max(1, Math.round(n('height') * k))).data;
          let ink = 0; for (let i = 0; i < d.length; i += 4) if (d[i] * 0.299 + d[i + 1] * 0.587 + d[i + 2] * 0.114 < 170) ink++;
          return [n('y') + n('height') <= m('y') + 0.01 && Math.abs(n('x') - m('x')) < 0.01, ink / (d.length / 4), l.getAttribute('fill')]; })()""")
        ck('番号札は、上の行の文字に重ならない場所に置く（文字の詰まったページでは、枠のすぐ上を避ける）。地の色は濃い橙', r[0] is False and r[1] < 0.02 and r[2] == '#b35f00', r)

        # ---- フォルダ比較：階層のずれの案内、相対パス ----
        for side, base in [('L', 'fd/L/order-webapp-2.3.0/order-webapp-2.3.0'), ('R', 'fd/R/order-webapp-2.4.0')]:
            w(base + '/src/main.ts', f"export const version = '{'2.3.0' if side == 'L' else '2.4.0'}';\n"); w(base + '/README.md', '# 受注管理\n')
        st = await t.load_folders(os.path.join(D, 'fd/L/order-webapp-2.3.0'), os.path.join(D, 'fd/R/order-webapp-2.4.0'))
        ck('外側のフォルダ（二重のフォルダ）を渡して1つも対応しないときは、階層のずれと中のフォルダの名前を案内する',
           '同じ場所・同じ名前のファイルが1つもありません' in st and '左は、中のフォルダ「order-webapp-2.3.0」' in st, st[-200:])
        st = await t.load_folders(os.path.join(D, 'fd/L/order-webapp-2.3.0/order-webapp-2.3.0'), os.path.join(D, 'fd/R/order-webapp-2.4.0'))
        ck('対応するファイルがあるときは、案内を出さない', '1つもありません' not in st, st)
        await p.locator('#fdTable tbody tr', has_text='main.ts').dblclick()
        await t.wait_for("App.mode === 'file' && S[0] && S[0].name === 'main.ts'", 20); await p.wait_for_timeout(400)
        foc = await t.js("document.activeElement && document.activeElement.id")
        ck('一覧から開いたファイルは、フォルダの中の場所（相対パス）を持ち、比較結果にフォーカスが移る', await t.js("S[0].rel") == 'src/main.ts' and foc in ('paneL', 'wrapView'), foc)
        pt = await t.download('#tPatch'); head = open(pt, encoding='utf-8').read().split('\n')[:3]
        ck('一覧から開いたファイルのパッチは、見出しが相対パス', head == ['diff --git a/src/main.ts b/src/main.ts', '--- a/src/main.ts', '+++ b/src/main.ts'], head)
        await p.click('#btnBackFolder'); await p.wait_for_timeout(300)
        ck('一覧に戻ると、一覧にフォーカスが戻る', await t.js("document.activeElement.classList.contains('fd-table-wrap')"))

        # ---- PDF：上付きの数字、部首の字体 ----
        r = await t.js("[normCJK('\\u2F3E\\u2FC8\\u2FCA'), normCJK('\\u2F00\\u2F08')]")
        ck('康熙部首は、国内の字体にする（戶・黃・黑 にしない）', r == ['戸黄黒', '一人'], r)
        pdf = os.path.join(D, 'sup.pdf')
        pg2 = await t.ctx.new_page(); await pg2.set_content(G.html_doc('<p style="font-size:14pt;line-height:2">粒子数は 10<sup>5</sup> 個、面積は 25 m<sup>2</sup>、水は H<sub>2</sub>O と書く。この行は上付きと下付きの文字を含むが、1つの行として取り出される。</p>')); await pg2.pdf(path=pdf, format='A4'); await pg2.close()
        await t.load(pdf, pdf)
        tx = await t.js("S[0].lines.join('\\n')")
        ck('PDF の上付き・下付きの数字は、その文字として取り出す（10⁵ を 105 にしない。行も分けない）', '10⁵' in tx and 'm²' in tx and 'H₂O' in tx and '105' not in tx, tx[:160])

        t.finish(allowed_errors=('DIALOG(beforeunload)',))

    # ---- 狭い画面：ツールバーの端の目印を押したら、下のボタンではなくツールバーを送る ----
    async with Tool(D, 700, 800) as t:
        ck, p = t.check, t.page
        await t.load(os.path.join(D, 'n_a.txt'), os.path.join(D, 'n_b.txt'))
        bar = "document.querySelector('#tab-text .toolbar')"
        box = await t.js(f"(() => {{ const b = {bar}, r = b.getBoundingClientRect(); return [b.classList.contains('more-r'), r.right, r.top + r.height / 2, b.scrollLeft]; }})()")
        st0 = await t.js("[document.querySelector('#oFold').checked, TV.st.unified, document.querySelector('#modal').classList.contains('on')]")
        await p.mouse.click(box[1] - 12, box[2]); await p.wait_for_timeout(700)
        sl = await t.js(f"{bar}.scrollLeft")
        st1 = await t.js("[document.querySelector('#oFold').checked, TV.st.unified, document.querySelector('#modal').classList.contains('on')]")
        ck('狭い画面：ツールバーの右端の目印を押すと、ツールバーが送られる（下のボタンは押されない）', box[0] and sl > box[3] + 50 and st0 == st1, (box, sl, st0, st1))
        await t.js(f"{bar}.scrollLeft = 0"); await p.wait_for_timeout(200)
        await p.mouse.move(box[1] - 200, box[2]); await p.mouse.wheel(0, 240); await p.wait_for_timeout(300)
        ck('狭い画面：ツールバーの上の縦ホイールでも送れる', await t.js(f"{bar}.scrollLeft") > 100, await t.js(f"{bar}.scrollLeft"))
        t.finish()


if __name__ == '__main__':
    asyncio.run(main())
