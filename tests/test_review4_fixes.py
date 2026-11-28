"""4回目のレビュー（設計・ロジック・セキュリティ・性能）で見つかった問題の修正"""
import asyncio, os, struct, sys, time, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
from harness import Tool, OUT as O
import gen_samples as G

D = os.path.join(O, 'r4')
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
DOC = f'<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body><w:p><w:r><w:t>正常な本文</w:t></w:r></w:p></w:body></w:document>'
TYPES = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'

# 以前の対応付け（全ますを Float32 と Uint8 で持つ方式）。新しい方式と結果が同じことを確かめるために使う
OLD_ALIGN = """function oldAlign(n, m, sim, T) {
  const band = Math.abs(n - m) + 30, W = m + 1, dp = new Float32Array((n + 1) * W), bt = new Uint8Array((n + 1) * W);
  for (let i = 0; i <= n; i++) for (let j = 0; j <= m; j++) {
    if (!i && !j) continue; let best = -Infinity, how = 0;
    if (i) { const v = dp[(i - 1) * W + j]; if (v > best) { best = v; how = 1; } }
    if (j) { const v = dp[i * W + j - 1]; if (v > best) { best = v; how = 2; } }
    if (i && j && Math.abs(i - j - (n - m) * i / Math.max(1, n)) <= band) { const g = sim(i - 1, j - 1) - T; if (g > 0) { const v = dp[(i - 1) * W + j - 1] + g; if (v > best) { best = v; how = 3; } } }
    dp[i * W + j] = best; bt[i * W + j] = how;
  }
  const raw = [];
  for (let i = n, j = m; i || j;) { const h = bt[i * W + j]; if (h === 3) { raw.push({ l: i - 1, r: j - 1 }); i--; j--; } else if (h === 1) { raw.push({ l: i - 1, r: -1 }); i--; } else { raw.push({ l: -1, r: j - 1 }); j--; } }
  raw.reverse(); const out = [];
  for (let k = 0; k < raw.length;) {
    if (raw[k].l >= 0 && raw[k].r >= 0) { out.push(raw[k++]); continue; }
    const L = [], R = []; while (k < raw.length && !(raw[k].l >= 0 && raw[k].r >= 0)) { if (raw[k].l >= 0) L.push(raw[k].l); else R.push(raw[k].r); k++; }
    if (L.length === R.length) for (let q = 0; q < L.length; q++) out.push({ l: L[q], r: R[q] }); else { L.forEach(l => out.push({ l, r: -1 })); R.forEach(r => out.push({ l: -1, r })); }
  }
  return out;
}"""


def zipto(path, files, method=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(path, 'w', method) as z:
        for name, data in files.items(): z.writestr(name, data)


def patch(src, dst, fn):
    b = bytearray(open(src, 'rb').read()); fn(b); open(dst, 'wb').write(bytes(b))


def central(b, name):
    """中央ディレクトリの中の、その名前の項目の位置"""
    k = 0
    while True:
        k = b.index(b'PK\x01\x02', k)
        n = struct.unpack_from('<H', b, k + 28)[0]
        if bytes(b[k + 46:k + 46 + n]) == name.encode(): return k
        k += 4


def make():
    os.makedirs(D, exist_ok=True)
    f = lambda n: os.path.join(D, n)
    files = {'[Content_Types].xml': TYPES, 'word/document.xml': DOC}
    zipto(f('正常_無圧縮.docx'), files, zipfile.ZIP_STORED)
    # 無圧縮の項目：一覧の「展開後の大きさ」だけを偽る
    def lie_usize(b): struct.pack_into('<I', b, central(b, 'word/document.xml') + 24, 5)
    patch(f('正常_無圧縮.docx'), f('壊_大きさ不一致.docx'), lie_usize)
    # 無圧縮の項目：データがファイルの終わりを越える
    def beyond(b): k = central(b, 'word/document.xml'); struct.pack_into('<II', b, k + 20, len(b) + 1000, len(b) + 1000)
    patch(f('正常_無圧縮.docx'), f('壊_終わりを越える.docx'), beyond)
    # 一覧は無圧縮、項目の先頭は deflate
    def method(b): struct.pack_into('<H', b, struct.unpack_from('<I', b, central(b, 'word/document.xml') + 42)[0] + 8, 8)
    patch(f('正常_無圧縮.docx'), f('壊_方式不一致.docx'), method)
    # 中央ディレクトリの2つ目の項目が、別のデータになっている
    def cd(b): k = central(b, 'word/document.xml'); b[k:k + 4] = b'XXXX'
    patch(f('正常_無圧縮.docx'), f('壊_一覧.docx'), cd)
    # XML として読めない（途中で切れている）
    zipto(f('壊_XML.docx'), {'[Content_Types].xml': TYPES, 'word/document.xml': DOC[:DOC.index('</w:t>')]})
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'; rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    zipto(f('壊_シート.xlsx'), {'[Content_Types].xml': TYPES,
        'xl/workbook.xml': f'<workbook {ns} xmlns:r="{rel}"><sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{rel}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': f'<worksheet {ns}><sheetData><row r="1"><c r="A1"><v>1</v></c></row><row r="2"><c r="A2"><v>2</v>'})
    open(f('ok.txt'), 'w', encoding='utf-8').write('前のファイル\n')
    for side in ('L', 'R'):
        os.makedirs(os.path.join(D, 'FD', side), exist_ok=True)
        for nm, text in (('a.txt', 'aaaa\n'), ('b.txt', 'bbbb\n' if side == 'L' else 'BBBB\n'), ('c.txt', 'cccc\n')):
            open(os.path.join(D, 'FD', side, nm), 'w').write(text)


async def main():
    make()
    f = lambda n: os.path.join(D, n)
    async with Tool(O, 1366, 768) as t:
        ck, p = t.check, t.page

        # ---- ページの対応付け：表のメモリを抑えても、結果は同じ ----
        r = await t.js("(async () => { " + OLD_ALIGN + """
          let seed = 12345, diff = 0, cases = 0; const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
          for (let k = 0; k < 600; k++) {
            const n = Math.floor(rnd() * 50), m = Math.floor(rnd() * 50), T = rnd() < 0.5 ? 0.3 : 0.55, lv = 2 + Math.floor(rnd() * 5), sh = Math.floor(rnd() * 9) - 4;
            const M = Array.from({ length: n }, (_, i) => Array.from({ length: m }, (_, j) => (j - i === sh && rnd() < 0.8) ? 1 : Math.floor(rnd() * lv) / (lv - 1)));
            const sim = (i, j) => M[i][j]; cases++;
            if (JSON.stringify(oldAlign(n, m, sim, T)) !== JSON.stringify(await PageMatch._align(n, m, sim, T))) diff++;
          }
          return [cases, diff]; })()""")
        ck('対応付け：以前の方式（全ますを持つ）と結果が同じ（同点の多い乱数 600 通り）', r == [600, 0], r)
        r = await t.js("""(async () => { const N = 6000, del = 1500, ins = 4500;
          const L = Array.from({ length: N }, (_, i) => i), R = L.filter(i => i !== del); R.splice(ins, 0, -1);
          const t0 = performance.now(); let yields = 0;
          const pairs = await PageMatch._align(N, N, (i, j) => L[i] === R[j] ? 1 : 0.1, 0.3, async () => { yields++; });
          return [pairs.filter(q => q.l < 0 || q.r < 0).map(q => [q.l, q.r]), Math.round(performance.now() - t0), yields]; })()""")
        ck('対応付け：6,000 ページどうしでも、削除・挿入されたページを見つける', r[0] == [[1500, -1], [-1, 4500]], r)
        ck('対応付け：6,000 ページどうしが 10 秒以内。途中で画面へ制御を返す', r[1] < 10000 and r[2] >= 3, r[1:])
        r = await t.js("(async () => { const q = await PageMatch._align(30000, 30000, () => 1, 0.3); return [q.length, q[7]]; })()")
        ck('対応付け：ページ数が多すぎるときは、表を作らずに同じページ番号どうしを組にする', r == [30000, {'l': 7, 'r': 7}], r)

        # ---- ZIP：無圧縮の項目も実際の大きさで確かめる。壊れた構造を、読めた分だけで進めない ----
        await t.load_one(0, f('ok.txt'))
        await t.load_one(1, f('正常_無圧縮.docx'))
        ck('ZIP：無圧縮の項目だけの Office 文書は、これまでどおり読める', await t.js('S[1].lines') == ['正常な本文'], await t.js('S[1].lines'))

        async def broken(name):
            await p.set_input_files('.slot[data-side="0"] input[type=file]', f(name)); await p.wait_for_timeout(700); await t.wait_idle(100)
            return await t.toast(), await t.js('S[0] && S[0].name')
        for name, what in (('壊_大きさ不一致.docx', '無圧縮の項目の大きさが一覧と合わない'), ('壊_終わりを越える.docx', 'データがファイルの終わりを越える'),
                           ('壊_方式不一致.docx', '一覧と項目の先頭で圧縮方式が違う'), ('壊_一覧.docx', '項目の一覧（中央ディレクトリ）が別のデータになっている')):
            toast, cur = await broken(name)
            ck(f'ZIP：{what} → 壊れているとして読み込まない（前のファイルは残る）', '読み込めませんでした' in toast and 'Office文書が壊れている' in toast and cur == 'ok.txt', toast)

        # ---- Office の XML：解析できないものを、空・途中までの文書として読み込まない ----
        toast, cur = await broken('壊_XML.docx')
        ck('Word：XML として読めないときは、壊れていると通知する（どのファイルかも示す）', 'Office文書の中身（word/document.xml）が壊れています' in toast and cur == 'ok.txt', toast)
        toast, cur = await broken('壊_シート.xlsx')
        ck('Excel：シートの XML が途中で切れているときも、読めた行だけで進めない', 'xl/worksheets/sheet1.xml' in toast and '壊れています' in toast and cur == 'ok.txt', toast)

        # ---- 数字の差：桁の多い数、負の値、指数表記 ----
        r = await t.js("""(() => { const f = (a, b) => Diff.numberDeltas(Diff.chars(a, b, 'char')).map(d => d.text);
          return [f('金額 9,007,199,254,740,993', '金額 9,007,199,254,740,995'), f('残高 12345678901234567890', '残高 12345678901234567891'), f('損益 -100', '損益 100'), f('損益 -100', '損益 -150'),
                  f('損益 100', '損益 -50'), f('損益 0', '損益 -30'), f('値 1E-5', '値 2E-5'), f('値 1.5e3', '値 1.5e4'), f('値 1.5', '値 1.25'), f('単価 1,200円', '単価 1,320円'), f('x 0.10', 'x 0.3')]; })()""")
        ck('数字の差：16 桁を超える数でも、差を正確に出す（+4 ではなく +2）', r[0] == ['+2 / +0.1%未満'] and r[1] == ['+1 / +0.1%未満'], r[:2])
        ck('数字の差：元の値が負のときは、増減率を出さない（−100→100 を「+200%」としない）', r[2] == ['+200'] and r[3] == ['−50'], r[2:4])
        ck('数字の差：元が正なら、負になっても増減率を出す。元が 0 なら差だけ', r[4] == ['−150 / −150.0%'] and r[5] == ['−30'], r[4:6])
        ck('数字の差：指数表記の仮数・指数には差を付けない（1E-5→2E-5 を「+1」としない）', r[6] == [] and r[7] == [], r[6:8])
        ck('数字の差：小数の桁をそろえる・3桁区切り（これまでどおり）', r[8] == ['−0.25 / −16.7%'] and r[9] == ['+120 / +10.0%'] and r[10] == ['+0.20 / +200.0%'], r[8:])

        # ---- 読み上げ：通知と処理中の表示 ----
        await t.js("toast('ふつうの通知')"); a = await t.js("[document.querySelector('#toast').getAttribute('role'), document.querySelector('#toast').getAttribute('aria-live')]")
        await t.js("toast('誤り', true)"); b = await t.js("document.querySelector('#toast').getAttribute('aria-live')")
        ck('通知を読み上げに伝える（誤りはすぐに）', a == ['status', 'polite'] and b == 'assertive' and await t.js("document.querySelector('#busyMsg').getAttribute('aria-live')") == 'polite', (a, b))

        # ---- フォルダ比較：読めなかったファイルを「相違」にしない ----
        await t.tab('folder'); await p.uncheck('#fdContent')
        await t.load_folders(os.path.join(D, 'FD', 'L'), os.path.join(D, 'FD', 'R')); await p.wait_for_timeout(500)
        # 読み込んだあとで、左の c.txt を書き換える（大きさは同じ）。ブラウザは、選んだあとに変わったファイルを読ませない
        time.sleep(1.1); open(os.path.join(D, 'FD', 'L', 'c.txt'), 'w').write('CCCC\n')
        await p.check('#fdContent'); await t.wait_for("FD.st.rows.length === 3 && !FD.st.running", 30); await p.wait_for_timeout(300)
        rows = await t.js("[...document.querySelectorAll('#fdTable tbody tr[data-i]')].map(r => r.querySelector('.path').textContent + '=' + r.querySelector('.st').textContent)")
        ck('フォルダ比較：読めなかったファイルは「読み取りエラー（未比較）」（「相違」にしない）', sorted(rows) == ['a.txt=同一', 'b.txt=相違', 'c.txt=読み取りエラー（未比較）'], rows)
        st = await t.js("document.querySelector('#fdStatus').textContent")
        ck('フォルダ比較：件数にも「読み取りエラー」を出す', '読み取りエラー 1' in st and '相違 1' in st, st)
        tip = await t.js("document.querySelector('#fdTable .st-error').title")
        ck('フォルダ比較：読めなかった理由を、状態の札に出す', tip.startswith('読めなかった理由：') and len(tip) > 10, tip)
        await p.uncheck('.fdFilter[value="diff"]'); await p.uncheck('.fdFilter[value="same"]'); await p.wait_for_timeout(300)
        rows = await t.js("[...document.querySelectorAll('#fdTable tbody tr[data-i]')].map(r => r.querySelector('.path').textContent)")
        ck('フォルダ比較：読み取りエラーは、絞り込みで隠れない', rows == ['c.txt'], rows)
        csv = open(await t.download('#fdCsv'), encoding='utf-8-sig').read()
        ck('フォルダ比較：CSV にも「読み取りエラー（未比較）」と出る', '"c.txt","読み取りエラー（未比較）"' in csv, csv[:200])
        h = open(await t.download('#fdReport'), encoding='utf-8').read()
        ck('フォルダ比較：レポートにも件数と状態が出る', '読み取りエラー（未比較）1' in h and 'tag error' in h)

        # ---- サンプル生成：Chrome の場所を環境変数で変えられる ----
        old = os.environ.get('CHROME_PATH')
        os.environ['CHROME_PATH'] = '/opt/somewhere/chrome'; a = G.chrome_path()
        if old is None: del os.environ['CHROME_PATH']
        else: os.environ['CHROME_PATH'] = old
        ck('サンプル生成（tools/gen_samples.py）も、CHROME_PATH で Chrome の場所を変えられる', a == '/opt/somewhere/chrome' and G.chrome_path() == (old or ('/usr/bin/google-chrome' if os.path.exists('/usr/bin/google-chrome') else None)))
        t.finish(allowed_errors=('ZIPの構造が壊れています', 'が壊れています', 'NotReadableError', 'NotFoundError'))  # 壊れたファイル・読めないファイルの記録（想定どおり）

if __name__ == '__main__':
    asyncio.run(main())
