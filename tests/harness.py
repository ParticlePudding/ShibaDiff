"""レビュー用ヘルパー：headless Chrome でShibaDiff を操作する。

使い方（例）:
    import asyncio, sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from harness import Tool

    async def main():
        async with Tool(out_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out'), width=1440, height=900) as t:
            await t.load('/path/left.docx', '/path/right.docx')      # 左右に読み込む
            print(await t.status())                                 # テキスト比較のステータス行
            print(await t.visible_rows(40))                         # 表示中の差分行（テキスト）
            await t.shot('text')                                    # スクリーンショット → out_dir/text.png
            await t.tab('page'); await t.shot('page')               # タブ切替: text / page / overlay / folder
            await t.tab('overlay'); print(await t.ov_stats())
            await t.click('#tNext')                                 # 任意のセレクタをクリック
            await t.key('Alt+ArrowDown')                            # キー操作
            print(await t.js('TV.st.blocks.length'))               # 任意のJS評価
            print(t.errors)                                         # コンソールエラー・例外
    asyncio.run(main())

主なセレクタ:
  タブ: #tabs button[data-tab=text|page|overlay|folder]
  テキスト比較: #tFirst #tPrev #tNext #tLast #tToR #tToL #tAllToR #tAllToL #tUndo #tRedo
                #oWs(select) #oCase #oBlank #oZen #oFold(checkbox) #searchBox #tFind #tLayout #tPatch #tReport
                ステータス #textStatus、行 .pane .row（.t-c 変更 .t-d 左のみ .t-i 右のみ .cd 文字差分）
  ファイル欄: .slot[data-side="0|1"]  中のボタン button[data-act=edit|save|close] select[data-act=enc|eol]
  ページ表示: ツール [data-tool=select|pen|marker|rect|note|eraser]  #zSel #zIn #zOut #pvShow #pvSync
              #annExport #annImport #pvPrint  列 .pv-col[data-side] 内 svg（注釈レイヤー）
  重ね合わせ: #ovModes button[data-mode=diff|overlay|swipe|blink|side] #ovLPage #ovRPage #ovLNext ...
              #ovThr #ovTol #ovBoxes #ovFaint #ovDx #ovDy #ovAuto #ovScan #ovScanRes #ovStats #ovRegNext
  フォルダ: .fd-slot[data-side] input（webkitdirectory）→ t.load_folders(left_dir, right_dir)  #fdTable #fdStatus
  モーダル: #modal.on  .dlg .foot button.primary（OK/適用） #askPw #edTa
  ヘルプ: #btnHelp
"""
import asyncio, os, time
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = 'file://' + os.path.join(ROOT, 'ShibaDiff.html')
SAMPLES = os.path.join(ROOT, 'samples') + '/'
FIXTURES = os.path.join(ROOT, 'tests', 'fixtures') + '/'
OUT = os.path.join(ROOT, 'tests', 'out')
# Chrome の場所：環境変数 CHROME_PATH → /usr/bin/google-chrome → Playwright 同梱の Chromium
CHROME = os.environ.get('CHROME_PATH') or ('/usr/bin/google-chrome' if os.path.exists('/usr/bin/google-chrome') else None)


class Tool:
    def __init__(self, out_dir, width=1440, height=900, mobile=False):
        self.out_dir = out_dir; os.makedirs(out_dir, exist_ok=True)
        self.w, self.h, self.mobile = width, height, mobile
        self.errors = []
        self.results = []

    async def __aenter__(self):
        self._p = await async_playwright().start()
        self.browser = await self._p.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])
        self.ctx = await self.browser.new_context(viewport={'width': self.w, 'height': self.h}, accept_downloads=True,
                                                  device_scale_factor=1, has_touch=self.mobile, is_mobile=self.mobile)
        self.page = await self.ctx.new_page()
        self.page.on('console', lambda m: self.errors.append(f'console.{m.type}: {m.text}') if m.type in ('error',) else None)
        self.page.on('pageerror', lambda e: self.errors.append(f'pageerror: {e}'))
        self.page.on('dialog', lambda d: (self.errors.append(f'DIALOG({d.type}): {d.message}'), asyncio.ensure_future(d.dismiss())))
        await self.page.goto(TOOL)
        await self.page.evaluate("window.showSaveFilePicker = undefined; window.print = () => { window.__printed = document.querySelectorAll('#printArea img').length; }")
        return self

    async def __aexit__(self, *a):
        await self.browser.close(); await self._p.stop()

    # ---- 合否の判定 ----
    def check(self, name, cond, info=''):
        """条件を確かめて記録する。最後に finish() で、1つでも NG があれば終了コード 1 にする"""
        self.results.append((name, bool(cond)))
        print(('OK  ' if cond else 'NG  ') + name + (f'  [{info}]' if info != '' else ''), flush=True)
        return bool(cond)

    def finish(self, allowed_errors=()):
        """想定外のエラー（console.error・ページの例外・ネイティブのダイアログ）がないことも確かめる"""
        bad = [e for e in self.errors if not any(a in e for a in allowed_errors)]
        self.check('想定外のエラーがない', not bad, bad if bad else '')
        fails = [n for n, ok in self.results if not ok]
        print(f'== {len(self.results) - len(fails)} / {len(self.results)} OK' + (f'  NG: {", ".join(fails)}' if fails else ''), flush=True)
        if fails: raise SystemExit(1)

    async def wait_for(self, expr, timeout=120):
        """CSPで eval が禁止されているため、Python側でポーリングする"""
        t0 = time.time()
        while time.time() - t0 < timeout:
            if await self.page.evaluate(expr): return
            await asyncio.sleep(0.1)
        raise TimeoutError(expr)

    async def wait_idle(self, extra=300):
        await self.wait_for("!document.querySelector('#busy').classList.contains('on')")
        await self.page.wait_for_timeout(extra)

    async def load_one(self, side, path):
        t0 = time.time()
        await self.page.set_input_files(f'.slot[data-side="{side}"] input[type=file]', path)
        await self.wait_for(f"!!(S[{side}] && S[{side}].name === {os.path.basename(path)!r})")
        await self.wait_idle()
        return round(time.time() - t0, 2)

    async def load(self, left, right):
        """左右に読み込み、読み込み秒数を返す"""
        a = await self.load_one(0, left); b = await self.load_one(1, right)
        return a, b

    async def tab(self, name):
        if name == 'folder':  # フォルダ比較は「モード」の切り替え
            await self.page.click('#modeSw button[data-mode=folder]'); await self.page.wait_for_timeout(300); return
        if await self.page.evaluate("App.mode") != 'file':
            await self.page.click('#modeSw button[data-mode=file]'); await self.page.wait_for_timeout(300)
        await self.page.click(f'#tabs button[data-tab={name}]'); await self.page.wait_for_timeout(1200 if name != 'text' else 300)
        await self.wait_idle(200)

    async def status(self):
        return (await self.page.inner_text('#textStatus')).replace('\n', ' ')

    async def visible_rows(self, n=60, side=None):
        """表示中の行をテキストで返す。各行: [種別] 左行番号|左テキスト || 右行番号|右テキスト"""
        return await self.page.evaluate("""(n) => {
          const L = [...document.querySelectorAll('#paneL .row')].slice(0, n);
          const R = [...document.querySelectorAll('#paneR .row')].slice(0, n);
          const uni = document.querySelector('#diffwrap').classList.contains('unified');
          return L.map((r, i) => {
            const t = (r.className.match(/t-(\\w)/) || [, 'fold'])[1];
            const l = r.querySelector('.ln')?.textContent + '|' + (r.querySelector('.tx')?.textContent || '');
            if (uni) return `[${t}] ${l}`;
            const rr = R[i]; const rt = rr ? rr.querySelector('.ln')?.textContent + '|' + (rr.querySelector('.tx')?.textContent || '') : '';
            const cds = [...r.querySelectorAll('.cd'), ...(rr ? rr.querySelectorAll('.cd') : [])].map(x => x.textContent);
            return `[${t}] ${l} || ${rt}` + (cds.length ? `   (文字差分: ${cds.join(' / ')})` : '');
          }).join('\\n');
        }""", n)

    async def shot(self, name, full=False):
        p = os.path.join(self.out_dir, f'{name}.png'); await self.page.screenshot(path=p, full_page=full); return p

    async def open_slots(self, sel):
        """ファイル欄（両方読み込むと自動でたたまれる）の中のボタンを押す前に、ファイル欄を開く"""
        if '.slot' in sel: await self.page.evaluate("App.showSlots(true)")

    async def click(self, sel, **kw):
        await self.open_slots(sel)
        await self.page.click(sel, **kw); await self.page.wait_for_timeout(250)

    async def key(self, k):
        await self.page.keyboard.press(k); await self.page.wait_for_timeout(200)

    async def js(self, expr):
        return await self.page.evaluate(expr)

    async def ov_stats(self):
        return (await self.page.inner_text('#ovStats')).replace('\n', ' ')

    def samples(self, rel):
        return SAMPLES + rel

    async def toast(self):
        return await self.page.inner_text('#toast')

    async def load_folders(self, left_dir, right_dir):
        await self.tab('folder')
        await self.page.set_input_files('.fd-slot[data-side="0"] input', left_dir)
        await self.page.set_input_files('.fd-slot[data-side="1"] input', right_dir)
        await self.page.wait_for_timeout(1500)
        return (await self.page.inner_text('#fdStatus')).replace('\n', ' ')

    async def download(self, sel):
        """クリックでダウンロードされるファイルを out_dir に保存してパスを返す"""
        await self.open_slots(sel)
        async with self.page.expect_download() as d:
            await self.page.click(sel)
            # レポートの出力設定のダイアログが開いたら、そのまま出力する
            await self.page.wait_for_timeout(150)
            if await self.page.is_visible('#modal.on .rep-opts'):
                await self.page.click('#modal.on .foot button.primary')
        dl = await d.value; p = os.path.join(self.out_dir, dl.suggested_filename); await dl.save_as(p); return p
