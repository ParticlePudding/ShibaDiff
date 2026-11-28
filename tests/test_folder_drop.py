"""フォルダのドロップ：HTML をファイルとして開いた状態（file://）で、ドロップしたフォルダを読めること。大きなフォルダで画面が止まらないこと。

テストは ShibaDiff.html を file:// で開く（ダウンロードして使うときと同じ）。フォルダのドロップは、Chrome の DevTools の
Input.dispatchDragEvent に本物のフォルダのパスを渡して行う（エクスプローラからドロップしたときと同じ経路でブラウザに届く）。"""
import asyncio, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness import Tool, OUT as O

D = os.path.join(O, 'fd_drop')


def make():
    """ZIP をエクスプローラで展開したときの形（外側のフォルダの中に、同じ名前のフォルダが入る）で作る。
    ファイルの組は毎回同じなので、前回の出力があれば上書きする"""
    def put(root, files):
        for rel, text in files.items():
            p = os.path.join(root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f: f.write(text)
    base = {'仕様書/01_概要.txt': '概要\n', '仕様書/02_詳細.txt': '詳細 第1版\n', '図面/部品A.txt': 'A\n', 'readme.txt': 'read me\n', '空のファイル.txt': ''}
    put(os.path.join(D, '納品_v1', '納品_v1'), {**base, '旧資料/廃止.txt': 'old\n'})
    put(os.path.join(D, '納品_v2', '納品_v2'), {**base, '仕様書/02_詳細.txt': '詳細 第2版\n', '追加/新規.txt': 'new\n'})
    for v in ('納品_v1', '納品_v2'): os.makedirs(os.path.join(D, v, v, '空のフォルダ', 'さらに空'), exist_ok=True)
    # 大きなフォルダ（3,000 ファイル。1つだけ中身が違う）
    for v, changed in (('大_v1', -1), ('大_v2', 7)):
        for i in range(3000):
            d = os.path.join(D, v, f'sub{i % 4}', f'd{(i // 4) % 7}'); os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f'file_{i:05d}.txt'), 'w') as f: f.write('changed\n' if i == changed else f'content {i}\n')


async def main():
    make()
    inner = lambda v: os.path.join(D, v, v)
    async with Tool(O, 1366, 768) as t:
        ck, p = t.check, t.page
        cdp = await p.context.new_cdp_session(p)

        async def drop(paths, x, y=400):
            data = {'items': [], 'files': paths, 'dragOperationsMask': 1}
            for typ in ('dragEnter', 'dragOver', 'drop'):
                await cdp.send('Input.dispatchDragEvent', {'type': typ, 'x': x, 'y': y, 'data': data})
        idle = "!document.querySelector('#busy').classList.contains('on')"
        nm = lambda side: p.inner_text(f'.fd-slot[data-side="{side}"] .nm')
        status = lambda: t.js("document.querySelector('#fdStatus').textContent")
        rows = lambda: t.js("[...document.querySelectorAll('#fdTable tbody tr[data-i]')].map(r => r.querySelector('.path').textContent + '=' + r.querySelector('.st').textContent)")
        ck('前提：ファイルとして開いている（file://）', await t.js("location.protocol") == 'file:')

        # ---- 左、右の順にドロップ ----
        await drop([inner('納品_v1')], 300)
        await t.wait_for(f"!!FD.st.files[0] && {idle}", 30)
        ck('ドロップしたフォルダを読める（フォルダ比較に切り替わり、左に入る）', await t.js('App.mode') == 'folder' and await nm(0) == '納品_v1（6 ファイル）', await nm(0))
        await drop([inner('納品_v2')], 1100)
        await t.wait_for(f"!!FD.st.files[1] && {idle} && !FD.st.running && FD.st.rows.length > 0", 30)
        ck('画面の右半分にドロップすると右に入る', await nm(1) == '納品_v2（6 ファイル）', await nm(1))
        r = await rows()
        ck('サブフォルダの中まで読み、同じ名前のファイルどうしを比べる', sorted(r) == sorted(['readme.txt=同一', '仕様書/01_概要.txt=同一', '仕様書/02_詳細.txt=相違', '図面/部品A.txt=同一', '空のファイル.txt=同一', '旧資料/廃止.txt=左のみ', '追加/新規.txt=右のみ']), r)
        ck('ドロップのあと、ドロップ先の表示と「処理中」の表示が残らない', not await t.js("document.querySelector('#dropOverlay').classList.contains('on') || document.querySelector('#busy').classList.contains('on')"))

        # ---- 2つまとめてドロップ ----
        await drop([inner('納品_v2'), inner('納品_v1')], 700)
        await t.wait_for(f"FD.st.names[0] === '納品_v2' && FD.st.names[1] === '納品_v1' && {idle} && !FD.st.running", 30)
        ck('2つのフォルダをまとめてドロップすると、左右に入る', '相違 1' in await status() and '左のみ 1' in await status() and '右のみ 1' in await status(), await status())

        # ---- 読めなかったときは、黙って止まらずに通知する（古い方式しか使えないブラウザを想定） ----
        await t.js("window.__h = DataTransferItem.prototype.getAsFileSystemHandle; DataTransferItem.prototype.getAsFileSystemHandle = undefined; 0")
        await drop([inner('納品_v1')], 300); await p.wait_for_timeout(1200)
        toast = await t.toast()
        ck('フォルダを読めなかったときは、理由と「フォルダを選択」の案内を通知する', 'フォルダを読み込めませんでした' in toast and 'フォルダを選択' in toast, toast)
        ck('読めなかったあとも、「処理中」の表示が残らず、前のフォルダはそのまま', await t.js(idle) and await t.js("FD.st.names[0]") == '納品_v2')
        await t.js("DataTransferItem.prototype.getAsFileSystemHandle = window.__h; 0")

        # ---- 中止：読み込みに時間がかかるときは、やめられる ----
        await t.js("window.__g = FileSystemFileHandle.prototype.getFile; FileSystemFileHandle.prototype.getFile = async function () { await new Promise(r => setTimeout(r, 150)); return window.__g.call(this); }; 0")
        await drop([os.path.join(D, '大_v1')], 300)
        await p.wait_for_selector('#busyCancel:not([hidden])', timeout=10000); await p.wait_for_timeout(700)
        msg = await p.inner_text('#busyMsg')
        ck('読み込み中は、読んだファイルの数を出す', 'ファイル）' in msg and '左' in msg, msg)
        await p.click('#busyCancel'); await p.wait_for_timeout(600)
        ck('「中止」で読み込みをやめ、画面を取り戻す', await t.js(idle) and '中止しました' in await t.toast() and await t.js("FD.st.names[0]") == '納品_v2', await t.toast())
        ck('中止のあと、「中止」ボタンは隠れる', await t.js("document.querySelector('#busyCancel').hidden"))
        # 左を読んでいる間に右をドロップしても、左の読み込みは止まらない
        await t.js("FileSystemFileHandle.prototype.getFile = async function () { await new Promise(r => setTimeout(r, 25)); return window.__g.call(this); }; 0")
        await t.js("document.querySelector('#toast').textContent = ''; 0")  # 前の確認（中止）の通知の文字を消しておく
        await drop([os.path.join(D, '大_v1')], 300)
        await p.wait_for_selector('#busyCancel:not([hidden])', timeout=10000); await p.wait_for_timeout(300)
        await drop([inner('納品_v1')], 1100)
        await t.wait_for("FD.st.names[1] === '納品_v1'", 30)
        ck('左の読み込み中に右をドロップしても、「中止」ボタンは左の分のために残る', await t.js("FD.st.names[0] !== '大_v1' && !document.querySelector('#busyCancel').hidden"))
        await t.wait_for(f"FD.st.names[0] === '大_v1' && {idle}", 60)
        ck('左の読み込み中に右をドロップしても、左右とも読み込まれる（左が中止されない）', await t.js("FD.st.files[0].size") == 3000 and await t.js("FD.st.files[1].size") == 6 and '中止' not in await t.toast(), await t.toast())
        await t.js("FileSystemFileHandle.prototype.getFile = window.__g; 0")
        # 開けないサブフォルダがあっても、そこだけ飛ばして残りを読む
        await t.js("window.__e = FileSystemDirectoryHandle.prototype.entries; FileSystemDirectoryHandle.prototype.entries = function () { if (this.name === '旧資料') throw new DOMException('denied', 'NotAllowedError'); return window.__e.call(this); }; 0")
        await drop([inner('納品_v1')], 300)
        await t.wait_for(f"FD.st.names[0] === '納品_v1' && {idle}", 30); await p.wait_for_timeout(300)
        toast = await t.toast()
        ck('開けないサブフォルダがあっても、残りのファイルは一覧に入り、飛ばしたものを通知する', await t.js("FD.st.files[0].size") == 5 and '読めないものが 1 個' in toast and '旧資料/' in toast, toast)
        await t.js("FileSystemDirectoryHandle.prototype.entries = window.__e; 0")

        # ---- 大きなフォルダ：比較の間、画面が止まらない ----
        await t.js("window.__lt = []; new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push(Math.round(e.duration)); }).observe({ entryTypes: ['longtask'] }); 0")
        t0 = time.time()
        await drop([os.path.join(D, '大_v1'), os.path.join(D, '大_v2')], 700)
        await t.wait_for(f"FD.st.names[0] === '大_v1' && FD.st.rows.length === 3000 && {idle} && !FD.st.running", 120)
        sec = time.time() - t0
        st = await status()
        ck('3,000 ファイルのフォルダを読み込んで比べられる', '全 3,000 ファイル' in st and '相違 1' in st and '同一 2999' in st, st)
        ck('3,000 ファイルの比較が 20 秒以内に終わる（表全体を描き直し続けない）', sec < 20, round(sec, 1))
        lt = await t.js('window.__lt')
        ck('比較の間、画面が1秒以上止まらない', max(lt or [0]) < 1000, lt)
        n = await t.js("document.querySelectorAll('#fdTable tbody tr[data-i]').length")
        more = await t.js("(document.querySelector('#fdTable tbody tr.more') || {}).textContent || ''")
        ck('表には先頭の 300 行だけを出し、残りの行数を示す', n == 300 and 'ほか 2,700 行' in more, (n, more))
        await t.js("const w = document.querySelector('.fd-table-wrap'); w.scrollTop = w.scrollHeight; 0"); await p.wait_for_timeout(400)
        ck('下までスクロールすると、続きの行を足す', await t.js("document.querySelectorAll('#fdTable tbody tr[data-i]').length") == 600)
        await p.uncheck('.fdFilter[value="same"]'); await p.wait_for_timeout(300)
        r = await rows()
        ck('絞り込みは全件が対象（表に出していない行の「相違」も出る）', r == ['sub3/d1/file_00007.txt=相違'], r[:3])
        await p.check('.fdFilter[value="same"]'); await p.wait_for_timeout(300)
        await p.focus('.fd-table-wrap')
        for _ in range(3): await p.keyboard.press('End'); await p.wait_for_timeout(150)
        sel = await t.js("(() => { const trs = [...document.querySelectorAll('#fdTable tbody tr[data-i]')]; return [trs.length, trs.findIndex(x => x.classList.contains('sel'))]; })()")
        ck('End キーは表に出している最後の行へ移り、そこで続きの行が足される（3回で 900 行目）', sel == [1200, 899], sel)
        await p.keyboard.press('ArrowDown'); await p.wait_for_timeout(150)
        ck('↓ キーで、続きの行へそのまま進める', await t.js("[...document.querySelectorAll('#fdTable tbody tr[data-i]')].findIndex(x => x.classList.contains('sel'))") == 900)
        # 上へ移動したとき、選んだ行が固定している見出しの行の下に隠れない
        clear = "(() => { const tr = document.querySelector('#fdTable tbody tr.sel'), th = document.querySelector('#fdTable thead th'); return Math.round(tr.getBoundingClientRect().top - th.getBoundingClientRect().bottom); })()"
        for _ in range(40): await p.keyboard.press('ArrowUp')
        await p.wait_for_timeout(200)
        gap = await t.js(clear)
        ck('↑ キーで上へ移動しても、選んだ行が見出しの行の下に隠れない', gap >= -1, gap)
        await p.keyboard.press('Home'); await p.wait_for_timeout(200)
        ck('Home キーでも、先頭の行が見出しの行の下に隠れない', await t.js(clear) >= -1 and await t.js("[...document.querySelectorAll('#fdTable tbody tr[data-i]')].findIndex(x => x.classList.contains('sel'))") == 0, await t.js(clear))
        p_csv = await t.download('#fdCsv')
        ck('CSV は、表に出している行数に関係なく全件', len(open(p_csv, encoding='utf-8-sig').read().strip().splitlines()) == 3001)
        t.finish(allowed_errors=('EncodingError',))  # 古い方式で読めなかったときの記録（想定どおり）

if __name__ == '__main__':
    asyncio.run(main())
