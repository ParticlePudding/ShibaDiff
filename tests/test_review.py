"""コードレビューで直した点の確認"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Tool, OUT, FIXTURES
import zipfile

async def main():
    os.makedirs(OUT, exist_ok=True)
    async with Tool(OUT) as t:
        check = t.check

        # 日付・品番のハイフンを負号と誤認しない
        d = await t.js("JSON.stringify(Diff.numberDeltas(Diff.chars('納期 2026-11-26','納期 2026-11-27')))")
        # v1.4.1 から日付には差を付けない（2回目のレビューで12人が「日付の増減率は不要」と指摘）。負号と誤認しないことも確かめる
        check('日付のハイフンを負号と誤認せず、日付には差を付けない', d == '[]', d)
        d = await t.js("JSON.stringify(Diff.numberDeltas(Diff.chars('品番 ABC-120','品番 ABC-125')))")
        # v1.5.14 から、型式・管理番号（英字-数字）には差を付けない（量ではない番号。「+5 / +4.2%」と出しても意味がなく、読み違える）。負号とも誤認しない
        check('品番（ABC-120 → ABC-125）には差を付けない（ハイフンを負号と誤認しない）', d == '[]', d)
        d = await t.js("JSON.stringify(Diff.numberDeltas(Diff.chars('損益 -100','損益 -150')))")
        check('本物の負数は −50', '"−50' in d, d)

        # すべて削除で開いている間の設定も初期値に戻る
        await t.js("Settings.set('fontSize','l'); Settings.set('wrap', true)")
        await t.click('#btnSettings'); await t.click('#setData'); await t.page.wait_for_timeout(300)
        await t.page.click('#modal .foot button >> nth=1'); await t.page.wait_for_timeout(300)
        check('すべて削除は、アプリのダイアログで確かめる（ブラウザの confirm は使わない）', await t.page.inner_text('#modal h3') == 'すべて削除')
        await t.page.click('#modal .foot button.primary'); await t.page.wait_for_timeout(300)
        check('確かめたあとは、保存データの一覧に戻る', await t.page.inner_text('#modal h3') == '保存されているデータ' and await t.js("Object.keys(localStorage).filter(k => k.startsWith('doccmp:')).length") == 0)
        r = await t.js("[Settings.get('fontSize'), Settings.get('wrap') ? '' : '', document.documentElement.dataset.fs]")
        check('すべて削除で設定が初期化', r == ['m', '', 'm'], r)
        await t.page.keyboard.press('Escape'); await t.page.wait_for_timeout(200); await t.page.keyboard.press('Escape')

        # 編集で末尾の改行を消したら finalNL=false
        await t.js("S[0]=App.newTextSide(); S[0].lines=['a','b']; App.updateSlot(0)")
        await t.click('.slot[data-side="0"] [data-act=edit]')
        await t.page.fill('#edTa', 'a\nc'); await t.page.click('#modal .foot button.primary')
        check('末尾改行なしを保持', await t.js("S[0].finalNL") is False)
        await t.page.fill('#searchBox', '')
        await t.click('.slot[data-side="0"] [data-act=edit]')
        await t.page.fill('#edTa', 'a\nd\n'); await t.page.click('#modal .foot button.primary')
        check('末尾改行ありを保持', await t.js("S[0].finalNL") is True)

        # 折り返し表示で大きな差分を選んでも速い
        ms = await t.js("""(()=>{S[0]={...App.newTextSide(),lines:Array.from({length:30000},(_,i)=>'L'+i)};
          S[1]={...App.newTextSide(),lines:Array.from({length:30000},(_,i)=>i<5?'L'+i:'X'+i)};
          Settings.set('wrap',true); TV.compare(); const t0=performance.now(); TV.go(0); return performance.now()-t0;})()""")
        cur = await t.js("document.querySelectorAll('#wrapView .row.cur').length")
        check('大きな差分の選択が速い', ms < 1500 and cur == 59990, f'{ms:.0f}ms / 印 {cur} 行')
        await t.js("Settings.set('wrap',false)")

        await t.js("S[0]=null; S[1]=null; App.updateSlot(0); App.updateSlot(1)")
        await round2(t)
        t.finish(allowed_errors=['展開後のサイズが大きすぎる'])


def make_files():
    """4MB を超えるバイナリ（最後の1バイトだけ違う）と、ZIP爆弾の docx を作る"""
    big = os.urandom(5 * 1024 * 1024)
    open(os.path.join(OUT, 'big_a.bin'), 'wb').write(big)
    open(os.path.join(OUT, 'big_b.bin'), 'wb').write(big[:-1] + bytes([big[-1] ^ 0xFF]))
    open(os.path.join(OUT, 'big_c.bin'), 'wb').write(big)
    bomb = os.path.join(OUT, 'bomb.docx')
    if not os.path.exists(bomb):
        with zipfile.ZipFile(bomb, 'w', zipfile.ZIP_DEFLATED) as z:
            with z.open('word/document.xml', 'w', force_zip64=False) as f:
                f.write(b'<?xml version="1.0"?><w:document xmlns:w="w"><w:body>')
                chunk = b' ' * (1 << 20)
                for _ in range(400): f.write(chunk)  # 展開後 400MB
                f.write(b'</w:body></w:document>')
    # 展開後のサイズを小さく偽装したもの（ヘッダを信じず、実際に展開した量で止められるか）
    b = bytearray(open(bomb, 'rb').read())
    i = b.find(b'PK\x01\x02'); b[i + 24:i + 28] = (1000).to_bytes(4, 'little')
    j = b.find(b'PK\x03\x04'); b[j + 22:j + 26] = (1000).to_bytes(4, 'little')
    open(os.path.join(OUT, 'bomb_forged.docx'), 'wb').write(bytes(b))


async def round2(t):
    """シニアエンジニアのレビュー（2026-11-26）で直した点"""
    check = t.check
    make_files()
    # 1. 4MB を超えるバイナリ：後ろの方だけ違っても「同一」と言わない
    await t.load(os.path.join(OUT, 'big_a.bin'), os.path.join(OUT, 'big_b.bin'))
    st = await t.status()
    check('4MB超のバイナリの末尾の違いを「異なる」と表示', 'バイナリの内容が異なります' in st and '同一' not in st, st[:80])
    check('最初に違うバイトの位置を表示', f'オフセット 0x{5 * 1024 * 1024 - 1:X}（{5 * 1024 * 1024 - 1:,}）' in st, st[:120])
    await t.load(os.path.join(OUT, 'big_a.bin'), os.path.join(OUT, 'big_c.bin'))
    st = await t.status()
    check('同じバイナリは「完全に同一」', '完全に同一です' in st, st[:40])

    # 2. 編集画面で適用しても末尾の改行を保つ（CRLF）。元に戻すと末尾の改行の状態も戻る
    await t.load(FIXTURES + 'R07/crlf_a.txt', FIXTURES + 'R07/crlf_b.txt')
    await t.click('.slot[data-side="0"] [data-act=edit]')
    v = await t.page.input_value('#edTa')
    check('編集欄に末尾の改行も出す', v.endswith('\n'), repr(v[-6:]))
    await t.page.fill('#edTa', v.replace('y = 2', 'y = 9')); await t.page.click('#modal .foot button.primary')
    await t.click('.slot[data-side="0"] [data-act=save]'); await t.page.wait_for_timeout(300)
    if await t.js("$('#modal').classList.contains('on')"): await t.page.keyboard.press('Escape')
    p = await t.download('.slot[data-side="0"] [data-act=save]')
    check('編集して保存しても末尾の CRLF を保つ', open(p, 'rb').read() == b'x = 1\r\ny = 9\r\nz = 3\r\n', open(p, 'rb').read())
    await t.click('.slot[data-side="0"] [data-act=edit]')
    await t.page.fill('#edTa', 'x = 1\ny = 9\nz = 3'); await t.page.click('#modal .foot button.primary')
    check('利用者が末尾の改行を消したら、改行なしになる', await t.js("S[0].finalNL") is False)
    check('末尾の改行を消しただけでも「変更あり」になる', await t.js("S[0].dirty") is True)
    await t.key('Control+z')
    check('元に戻すと末尾の改行の状態も戻る', await t.js("S[0].finalNL") is True)
    await t.click('.slot[data-side="0"] [data-act=edit]')
    await t.page.fill('#edTa', 'x = 1\ny = 7\nz = 3\n'); await t.page.click('#modal .foot button.primary')

    # 5. 保存していない編集があるとき、別のファイルを読み込む前に確認する
    await t.page.set_input_files('.slot[data-side="0"] input[type=file]', FIXTURES + 'R07/noeol_a.txt')
    await t.page.wait_for_timeout(300)
    h = await t.page.inner_text('#modal .dlg h3') if await t.js("$('#modal').classList.contains('on')") else ''
    check('未保存の編集があると、読み込む前に確認する', h == '保存していない変更', h)
    await t.page.click('#modal .foot button:has-text("キャンセル")'); await t.page.wait_for_timeout(300)
    check('キャンセルすると編集はそのまま残る', await t.js("S[0].name === 'crlf_a.txt' && S[0].dirty"))
    await t.page.set_input_files('.slot[data-side="0"] input[type=file]', FIXTURES + 'R07/noeol_a.txt')
    await t.page.wait_for_timeout(300); await t.page.click('#modal .foot button:has-text("続ける")')
    await t.wait_for("S[0] && S[0].name === 'noeol_a.txt'", 20)
    check('続けると読み込む', True)

    # 4. ZIP爆弾：展開後が大きすぎるものは途中で止め、分かるメッセージを出す
    t0 = asyncio.get_event_loop().time()
    await t.page.set_input_files('.slot[data-side="1"] input[type=file]', os.path.join(OUT, 'bomb.docx'))
    await t.wait_for("!document.querySelector('#busy').classList.contains('on') && document.querySelector('#toast') && document.querySelector('#toast').textContent.includes('bomb.docx')", 60)
    sec = asyncio.get_event_loop().time() - t0
    msg = await t.toast()
    check('ZIP爆弾は展開を途中で止める', '展開後のサイズが大きすぎる' in msg, msg[:80])
    check('ZIP爆弾の判定が速い（5秒以内）', sec < 5, f'{sec:.1f}s')
    check('ZIP爆弾を読んでも前のファイルは残る', await t.js("S[1].name") == 'crlf_b.txt')
    await t.js("document.querySelector('#toast').textContent = ''")
    mem0 = await t.js("performance.memory ? performance.memory.usedJSHeapSize : 0")
    t0 = asyncio.get_event_loop().time()
    await t.page.set_input_files('.slot[data-side="1"] input[type=file]', os.path.join(OUT, 'bomb_forged.docx'))
    await t.wait_for("!document.querySelector('#busy').classList.contains('on') && document.querySelector('#toast').textContent.includes('bomb_forged.docx')", 60)
    sec = asyncio.get_event_loop().time() - t0; msg = await t.toast()
    check('サイズを偽装したZIP爆弾も、展開した量で止める', '展開後のサイズが大きすぎる' in msg, msg[:60])
    check('偽装したZIP爆弾の判定も速い（5秒以内）', sec < 5, f'{sec:.1f}s')
    mem = await t.js("performance.memory ? performance.memory.usedJSHeapSize : 0")
    check('偽装したZIP爆弾でもメモリの増加は 200MB 未満', mem - mem0 < 200 * 1024 * 1024, f'+{(mem - mem0) / 1048576:.0f}MB')
    # 通常の docx は今までどおり読める
    await t.load(t.samples('00_共通サンプル（形式別）/07_Word/議事録_初版.docx'), t.samples('00_共通サンプル（形式別）/07_Word/議事録_修正版.docx'))
    check('通常の docx は読める', 'DOCX' in await t.status())

    # 7. ライセンス全文を表示できる
    await t.click('#btnSettings'); await t.click('#setLicenses'); await t.page.wait_for_timeout(300)
    lic = await t.page.inner_text('#modal pre.licenses')
    check('ライセンス：本体の MIT と pdf.js・core-js の全文', all(x in lic for x in ['ShibaDiff (MIT License)', 'Copyright (c) 2026 ParticlePudding', 'Apache License', 'Version 2.0', 'Denis Pushkarev']), lic[:60])
    await t.page.keyboard.press('Escape'); await t.page.wait_for_timeout(300); await t.page.keyboard.press('Escape')


asyncio.run(main())
