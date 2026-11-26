"""使用感のフィードバック（2026-11-26）で直した点：ヘッダ、フォルダ比較のモード、ドロップ先、全画面、
比較条件のポップアップ、重ね合わせの表示（縦に合わせる・手のひら・ホイール・色・点滅・並べて表示・パネル）、
ページの対応付け、ページ表示の連動、レポート（重ね合わせ・注釈・フォルダ）"""
import asyncio, sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool, SAMPLES as SM, OUT as O
C = SM + '00_共通サンプル（形式別）/'


def make_docs():
    """5ページの手順書と、3ページ目に1ページ挿入した6ページ版（文字のPDFと、画像だけのスキャン版）"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from PIL import Image, ImageDraw
    out = {}
    def page_img(n, inserted=False):
        random.seed(1000 + n if not inserted else 99)
        im = Image.new('L', (827, 1169), 255); d = ImageDraw.Draw(im)
        if inserted:
            for k in range(12): d.ellipse([100 + k * 50, 200 + k * 60, 160 + k * 50, 260 + k * 60], outline=0, width=4)
        else:
            d.rectangle([80 + n * 90, 120, 200 + n * 90, 220], outline=0, width=6)
            for k in range(25): d.line([80, 300 + k * 30, 80 + random.randint(200, 650), 300 + k * 30], fill=0, width=3)
        return im.convert('RGB')
    for name, seq in [('v1', [1, 2, 3, 4, 5]), ('v2', [1, 2, 'ins', 3, 4, 5])]:
        # 文字のPDF
        p = os.path.join(O, f'手順書_{name}.pdf'); c = canvas.Canvas(p, pagesize=A4)
        for n in seq:
            random.seed(2000 + (n if n != 'ins' else 99)); c.setFont('Helvetica', 16)
            c.drawString(60, 780, f'Chapter {n}' if n != 'ins' else 'Inserted: safety notes')
            c.setFont('Helvetica', 9)
            for k in range(40): c.drawString(60, 740 - k * 16, ' '.join(random.choice(['alpha', 'beta', 'gamma', 'delta', 'omega', 'sigma', 'kappa']) for _ in range(9)))
            c.showPage()
        c.save(); out[name] = p
        # スキャン版（画像だけ）
        p = os.path.join(O, f'手順書_{name}_スキャン.pdf'); c = canvas.Canvas(p, pagesize=A4)
        for n in seq:
            jp = os.path.join(O, f'pm_{name}_{n}.jpg'); page_img(n if n != 'ins' else 0, n == 'ins').save(jp, quality=85)
            c.drawImage(jp, 0, 0, *A4); c.showPage()
        c.save(); out[name + 's'] = p
    return out


async def main():
    docs = make_docs()
    async with Tool(O, 1366, 768) as t:
        ck = t.check
        # ---- ヘッダ ----
        ck('日付印のツールがない', await t.js("!document.querySelector('[data-tool=stamp]')"))
        ck('読み込む前はファイル欄が開いている', not await t.js("document.body.classList.contains('slots-closed')"))
        await t.load(C + '07_Word/議事録_初版.docx', C + '07_Word/議事録_修正版.docx')
        ck('左右を読み込むとファイル欄が自動でたたまれる', await t.js("document.body.classList.contains('slots-closed')"))
        ck('ヘッダにファイル名が出る', (await t.page.inner_text('#hdrFiles')).count('議事録') == 2)
        await t.page.click('#btnSlots')
        ck('▾ でファイル欄を開ける', not await t.js("document.body.classList.contains('slots-closed')"))
        await t.page.click('#btnSlots')
        await t.page.click('#oPop summary')
        ck('比較条件はポップアップにまとめた', await t.js("document.querySelector('#oPop').open") and await t.page.is_visible('#oCase'))
        await t.page.check('#oCase'); await t.page.wait_for_timeout(300)
        ck('変えた比較条件の数をボタンに出す', await t.page.inner_text('#oBadge') == '1')
        await t.page.mouse.click(700, 500)
        ck('外側をクリックするとポップアップが閉じる', not await t.js("document.querySelector('#oPop').open"))
        await t.page.uncheck('#oCase') if await t.page.is_visible('#oCase') else await t.js("document.querySelector('#oCase').checked=false; document.querySelector('#oCase').dispatchEvent(new Event('change'))")
        # 全画面
        await t.page.click('#btnFull'); await t.page.wait_for_timeout(300)
        ck('全画面でヘッダを隠す', await t.js("document.body.classList.contains('fullview') && getComputedStyle(document.querySelector('#top')).display === 'none'"))
        await t.page.keyboard.press('Escape'); await t.page.wait_for_timeout(300)
        ck('Esc で全画面を終える', not await t.js("document.body.classList.contains('fullview')"))
        # ドロップ先：左半分・右半分
        await t.js("""(()=>{window.__dt=new DataTransfer(); __dt.items.add(new File(['abc\\n'],'drop.txt',{type:'text/plain'}));
          window.__ev=(type,x)=>window.dispatchEvent(new DragEvent(type,{dataTransfer:__dt,clientX:x,clientY:300,bubbles:true,cancelable:true}));})()""")
        await t.js("__ev('dragenter', 1100); __ev('dragover', 1100)")
        ck('ドラッグ中は右半分に「右に読み込む」を強調', await t.js("document.querySelector('#dropOverlay').classList.contains('on') && document.querySelector('.dz[data-side=\"1\"]').classList.contains('hot') && !document.querySelector('.dz[data-side=\"0\"]').classList.contains('hot')"))
        await t.js("__ev('dragover', 200)")
        ck('左半分に動かすと「左に読み込む」を強調', await t.js("document.querySelector('.dz[data-side=\"0\"]').classList.contains('hot')"))
        await t.js("__ev('drop', 1100)"); await t.wait_for("S[1] && S[1].name === 'drop.txt'", 20)
        ck('右半分にドロップすると右に読み込む', await t.js("S[0].name") == '議事録_初版.docx')

        # ---- フォルダ比較はモード ----
        await t.load_folders(C + '17_フォルダ比較/旧版フォルダ', C + '17_フォルダ比較/新版フォルダ')
        ck('フォルダ比較ではファイル用のタブとファイル欄を出さない', await t.js("getComputedStyle(document.querySelector('#tabs')).display === 'none' && getComputedStyle(document.querySelector('#slots')).display === 'none'"))
        p = await t.download('#fdCsv'); csv = open(p, 'rb').read()
        ck('フォルダ比較の CSV（BOM 付き UTF-8・相違を含む）', csv.startswith(b'\xef\xbb\xbf') and '"連絡文.txt","相違"' in csv.decode('utf-8-sig'))
        p = await t.download('#fdReport'); h = open(p, encoding='utf-8').read()
        ck('フォルダ比較のレポート', 'フォルダ比較レポート' in h and '相違 1' in h and 'Content-Security-Policy' in h)
        await t.page.locator('#fdTable tbody tr', has_text='連絡文.txt').dblclick()
        await t.wait_for("App.mode === 'file' && S[0] && S[0].name === '連絡文.txt'", 20)
        ck('一覧から開くとファイル比較に移り、「フォルダ一覧」に戻るボタンが出る', await t.page.is_visible('#btnBackFolder'))
        await t.page.click('#btnBackFolder'); await t.page.wait_for_timeout(300)
        ck('「フォルダ一覧」で一覧に戻る', await t.js("App.mode") == 'folder' and await t.page.is_visible('#fdTable'))

        # ---- 重ね合わせの表示 ----
        await t.load(C + '13_画像_PNG/図面_RevA.png', C + '13_画像_PNG/図面_RevB.png')
        await t.wait_for("/箇所/.test(document.querySelector('#ovStats').textContent)", 60)
        vis = lambda: t.js("[...document.querySelectorAll('.ov-side [data-modes]')].filter(e=>!e.hidden).map(e=>e.querySelector('input,button')?.id||e.id).filter(Boolean)")
        ck('差分ハイライトのパネル：感度・枠・許容（濃さ・点滅は出さない）', (lambda v: 'ovThr' in v and 'ovTolPx' in v and 'ovOpacity' not in v and 'ovBlinkMs' not in v)(await vis()))
        await t.click('#ovModes button[data-mode=blink]'); await t.page.wait_for_timeout(500)
        v = await vis(); ck('点滅のパネル：間隔・手動だけ（感度は出さない）', 'ovBlinkMs' in v and 'ovThr' not in v, v)
        await t.page.check('#ovBlinkManual'); await t.page.wait_for_timeout(200)
        on0 = await t.js("OV.st.blinkOn"); await t.page.wait_for_timeout(1500)
        ck('手動のときは自動で切り替わらない', await t.js("OV.st.blinkOn") == on0)
        await t.page.click('#ovView canvas'); ck('画像のクリックで切り替わる', await t.js("OV.st.blinkOn") != on0)
        await t.page.uncheck('#ovBlinkManual')
        await t.click('#ovModes button[data-mode=overlay]'); await t.page.wait_for_timeout(500)
        px0 = await t.js("(()=>{const c=document.querySelector('#ovView canvas'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let r=0;for(let i=0;i<d.length;i+=4) if(d[i]>180&&d[i+1]<120) r++;return r})()")
        await t.page.check('#ovTint'); await t.page.wait_for_timeout(500)
        px1 = await t.js("(()=>{const c=document.querySelector('#ovView canvas'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let r=0;for(let i=0;i<d.length;i+=4) if(d[i]>180&&d[i+1]<120) r++;return r})()")
        ck('透かし重ねで色を付けられる（左の線が赤になる）', px1 > px0 + 1000, f'{px0} → {px1}')
        await t.click('#ovModes button[data-mode=side]'); await t.page.wait_for_timeout(800)
        ck('並べて表示でも変更箇所を数える', (await t.ov_stats()).startswith('9 箇所'), (await t.ov_stats())[:20])
        blue = "(()=>{const c=document.querySelectorAll('#ovView canvas')[1],d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let r=0;for(let i=0;i<d.length;i+=4) if(d[i]===26&&d[i+1]===115&&d[i+2]===232) r++;return r})()"
        b1 = await t.js(blue); await t.page.uncheck('#ovSideHl'); await t.page.wait_for_timeout(300); b0 = await t.js(blue)
        ck('並べて表示のハイライトを切り替えられる', b1 > 100 and b0 == 0, f'{b1} → {b0}')
        await t.click('#ovModes button[data-mode=diff]'); await t.page.wait_for_timeout(800)
        await t.page.select_option('#ovZoom', 'fith'); await t.page.wait_for_timeout(300)
        h, vh = await t.js("document.querySelector('#ovView canvas').getBoundingClientRect().height"), await t.js("$('#ovView').clientHeight")
        ck('縦に合わせる', abs(h - (vh - 30)) < 3, f'{h:.0f} / {vh}')
        w0 = await t.js("document.querySelector('#ovView canvas').getBoundingClientRect().width")
        await t.page.mouse.move(500, 400); await t.page.keyboard.down('Control'); await t.page.mouse.wheel(0, -300); await t.page.keyboard.up('Control'); await t.page.wait_for_timeout(300)
        w1 = await t.js("document.querySelector('#ovView canvas').getBoundingClientRect().width")
        ck('Ctrl＋ホイールで拡大（ブラウザの拡大より優先）', w1 > w0 * 1.3 and await t.js("window.devicePixelRatio") == 1, f'{w0:.0f} → {w1:.0f}')
        y0 = await t.js("$('#ovView').scrollTop"); await t.page.mouse.wheel(0, 200); await t.page.wait_for_timeout(300)
        ck('ホイールだけなら縦スクロール', await t.js("$('#ovView').scrollTop") > y0)
        await t.page.keyboard.press('h')
        s0 = await t.js("[$('#ovView').scrollLeft,$('#ovView').scrollTop]")
        await t.page.mouse.move(600, 400); await t.page.mouse.down(); await t.page.mouse.move(680, 470, steps=5); await t.page.mouse.up()
        s1 = await t.js("[$('#ovView').scrollLeft,$('#ovView').scrollTop]")
        ck('手のひらツールでドラッグすると表示位置が動く', s1[0] < s0[0] and s1[1] < s0[1], f'{s0} → {s1}')
        w1 = await t.js("document.querySelector('#ovView canvas').getBoundingClientRect().width"); await t.page.mouse.wheel(0, 300); await t.page.wait_for_timeout(300)
        ck('手のひらツールではホイールで縮小', await t.js("document.querySelector('#ovView canvas').getBoundingClientRect().width") < w1)
        await t.page.keyboard.press('h')

        # ---- ページの対応付け（文字のPDF・スキャン） ----
        for a, b, nm in [(docs['v1'], docs['v2'], '文字'), (docs['v1s'], docs['v2s'], 'スキャン')]:
            await t.load(a, b)
            if await t.js('App.tab') != 'overlay': await t.tab('overlay')
            await t.wait_for("/追加|削除|ありません/.test(document.querySelector('#ovMatchInfo').textContent)", 120)
            info = await t.page.inner_text('#ovMatchInfo')
            ck(f'{nm}：挿入された右の3ページ目を見つける', '右で追加されたページ：3' in info, info)
            seq = []
            for _ in range(4):
                await t.wait_for("!document.querySelector('#busy').classList.contains('on')", 60); await t.page.wait_for_timeout(300)
                seq.append((await t.js("+$('#ovLPage').value"), await t.js("+$('#ovRPage').value")))
                await t.page.focus('#ovLPage'); await t.page.keyboard.press('PageDown')
            ck(f'{nm}：PageDown（選択欄にフォーカスがあっても）で、挿入ページを挟んで組ごとに送る', seq == [(0, 0), (1, 1), (-1, 2), (2, 3)], seq)
            await t.click('#ovScan'); await t.wait_for("document.querySelector('#ovScanRes').textContent.includes('変更ありのページ')", 120)
            ck(f'{nm}：一括チェックは挿入ページを「追加」とし、以降を正しく組にする', '追加されたページ: 1' in await t.page.inner_text('#ovScanRes') and '変更ありのページ: 0 / 5' in await t.page.inner_text('#ovScanRes'), (await t.page.inner_text('#ovScanRes'))[:60])
        # 重ね合わせのレポート
        await t.click('#ovReport'); p = await t.download('#modal .foot button:has-text("すべてのページ")'); h = open(p, encoding='utf-8').read()
        ck('重ね合わせのレポート（追加ページ・全ページの画像・CSP）', '重ね合わせ比較レポート' in h and '右で追加' in h and h.count('<img') == 6 and "img-src data:" in h)

        # ---- ページ表示：連動のずれ・対応付け・レポート ----
        await t.tab('page'); await t.page.wait_for_timeout(1500)
        await t.js("document.querySelector('#pvSync').checked = true")
        r = await t.js("""(async()=>{const [L,R]=document.querySelectorAll('.pv-scroll'); const sl=[...L.querySelectorAll('.pv-slot')], sr=[...R.querySelectorAll('.pv-slot')];
          const cur=(sc,ss)=>{let b=0;for(let i=0;i<ss.length;i++) if(ss[i].offsetTop<=sc.scrollTop+8) b=i;return b};
          L.scrollTop = sl[3].offsetTop; await new Promise(r=>setTimeout(r,200)); const a=cur(R,sr);
          // 左を動かした直後（0.15秒以内）に右を動かしても、左が付いてくる
          L.scrollTop = sl[1].offsetTop; await new Promise(r=>setTimeout(r,30)); R.scrollTop = sr[4].offsetTop; await new Promise(r=>setTimeout(r,300));
          return [a, cur(L,sl)]; })()""")
        ck('ページ表示の連動：左の4ページ目に、右は挿入を飛ばして5ページ目が合う', r[0] == 4, r)
        ck('ページ表示の連動：左を動かした直後に右を動かしても、左が付いてくる（ずれない）', r[1] == 3, r)
        await t.js("document.querySelectorAll('.pv-scroll')[1].scrollTop = 0"); await t.page.wait_for_timeout(300)
        svg = t.page.locator('.pv-col[data-side="1"] svg').first; bb = await svg.bounding_box()
        await t.click('[data-tool=note]'); await t.page.mouse.click(bb['x'] + 80, bb['y'] + 80); await t.page.wait_for_timeout(300)
        await t.page.fill('#modal input, #modal textarea', '要確認<script>x</script>'); await t.page.click('#modal .foot button.primary'); await t.page.wait_for_timeout(300)
        await t.click('#pvReport'); p = await t.download('#modal .foot button:has-text("注釈のあるページだけ")'); h = open(p, encoding='utf-8').read()
        ck('注釈のレポート（付箋の内容・画像・文字はエスケープ）', '注釈レポート' in h and '要確認&lt;script&gt;' in h and h.count('<img') == 1)
        t.finish()

asyncio.run(main())
