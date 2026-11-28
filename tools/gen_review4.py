#!/usr/bin/env python3
"""4回目の20人レビュー用のテストデータ（3回目とは別の業務・別の内容）。
出力：review4/<Rnn_所属_役割>/ に業務ファイルと「正解.md」（用意した変更点の一覧）、
      review4/_共通/ にレビュアー共通の進め方・ひな形・職種別の指示（briefs/Rnn.md）

使い方：python3 tools/gen_review4.py          … 20人分すべて
        python3 tools/gen_review4.py 3 7 12   … 番号を指定して作り直す

データの中身は、5人分ずつ4つのファイルに分けてある：
  tools/review4_a.py（R01〜R05：契約・薬事・設計・物流・人事）
  tools/review4_b.py（R06〜R10：経理・ローカライズ・運用・組込み・データ分析）
  tools/review4_c.py（R11〜R15：広報・印刷・保全・入札・証券）
  tools/review4_d.py（R16〜R20：店舗・キーボード操作・タブレット・大容量・異常系）
それぞれ SPEC = [(番号, 役割, 所属, 生成する関数, 指示)] を持つ。指示は {'who': 人物像, 'tasks': [課題…], 'note': 補足（省略可）}。
部品（Word・Excel・PDF・スキャン風の画像など）は tools/gen_review3.py のものを使う。"""
import os, sys, shutil, asyncio, subprocess, tempfile, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_samples as G
import gen_review3 as R3

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'review4')
R3.ROOT = ROOT; G.ROOT = ROOT
PARTS = {'review4_a': range(1, 6), 'review4_b': range(6, 11), 'review4_c': range(11, 16), 'review4_d': range(16, 21)}

GUIDE = """# ShibaDiff ユーザーレビューの進め方（レビュアー共通・4回目）

あなたは、実務で文書を比べる仕事をしている **ユーザー** として、文書比較ツール ShibaDiff（v1.5.14）を試し、
気づいたことを報告します。コードのレビューではありません。**画面を操作して、仕事に使えるかどうか**を見てください。

## ツール
- `/home/user/ShibaDiff/ShibaDiff.html`（1つの HTML。ブラウザで開いて使う。通信はしない）
- 機能：テキスト比較／ページ表示（左右に並べる・注釈）／重ね合わせ（画像としての差）／フォルダ比較。
  画面右上の［？］（`#btnHelp`）に使い方の説明があります。まずそれを読んでください。
- 仕様を確かめたいときは `docs/01_要件定義書.md` を見てもかまいません（「仕様どおり」か「不具合」かの判断のため。
  4.8・4.9 の「保留」「見送り」に書かれていることは、困っても要望です）。
  ただし、職種別の指示に「資料を読まない」と書かれている人は読まないでください。

## 操作のしかた（headless Chrome を Python から動かす）
- `tests/harness.py` の `Tool` を使います（先頭のコメントに、使い方と主なセレクタの一覧があります）。
- ひな形：`/home/user/ShibaDiff/review4/_共通/example.py`（コピーして使う。**自分の出力フォルダに置く**）
- 画面の見た目は、`t.shot('名前')` で PNG を保存し、**Read ツールでその PNG を開いて自分の目で見て**判断してください
  （文字の重なり・はみ出し・読みにくさ・分かりにくさは、見ないと分かりません）。
- 画面の部品の id は `src/body.html` を見ると分かります（id を調べる目的で読むのはかまいません）。
- できるだけ**ユーザーと同じ操作**（クリック・キー入力・ドロップ）で動かしてください。内部の関数を直接呼ぶのは、状態を調べるときだけにします。
- 1つの Python の実行は長くても数分に。重い処理（大きなファイル）は時間を測って報告してください。
- パスワード付き PDF は、読み込むとパスワードを尋ねるダイアログ（`#askPw`）が出ます。`t.load` は読み込み完了を待つので、
  その場合は `t.page.set_input_files('.slot[data-side="0"] input[type=file]', path)` のあと自分でダイアログを操作してください。
- 保存していない変更・注釈があると、別のファイルを読み込む前・閉じる前に確認のダイアログ（`#modal.on`）が出ます。
  `t.load` が待ったまま進まないときは、ダイアログが出ていないかを確かめてください（スクリーンショットで分かります）。

## 守ること
- **リポジトリのファイルを変更しない**（`src/`・`tests/`・`docs/`・`tools/`・`ShibaDiff.html`・`review4/R*` のデータ）。git の操作もしない。
- 書き込むのは **`/home/user/ShibaDiff/review4/_results/Rnn/`（自分の番号）の中だけ**（スクリプト・スクリーンショット・ダウンロードしたもの）。
- ほかのレビュアーも同じ機械で同時に作業しています。ブラウザは使い終わったら閉じ（`async with Tool(...)` を抜ける）、同時に何個も立ち上げないでください。
- 外部のサイトへはアクセスしません。

## 正解の扱い
- 自分のデータフォルダの `正解.md` に、用意した変更点が書いてあります。**まず自分でツールを使って変更点を調べ、そのあとで照らし合わせて**ください。
  ツールが見落とした変更、出てはいけない差、誤解を招く表示が、いちばん大事な発見です。
- 正解.md のほうが間違っているように見えるとき（書いてある変更がファイルに入っていない等）は、ファイルの中身を自分で確かめたうえで、
  「データの誤り」として報告に書いてください（ツールの不具合にはしない）。

## 不具合と要望の分け方
- **不具合**：結果が正しくない（違いを見落とす・ない違いを出す・数や表示が食い違う）／止まる・落ちる・固まる／操作に反応しない／
  表示が崩れる・重なる・読めない／案内や説明と実際の動きが違う／誤解させる言葉・表示／エラーの理由が分からない。
- **追加要望**：いまない機能がほしい、仕様を変えてほしい、もっとこうだと便利、というもの。要件定義書に「保留」「見送り」「制限」と書かれていることは、困っても要望です。
- 迷ったら不具合の側に書き、「仕様かもしれない」と添えてください。

## 思い込みで報告しない
- 不具合は**必ず2回再現**させてから書いてください。待ち時間が足りないだけ（処理中に次の操作をした、描画を待たずに撮った）ではないかを確かめます。
- headless ブラウザやこの操作方法に特有のこと（ファイル選択ダイアログが出ない、印刷のプレビューが見えない等）は不具合にしません。
- 再現手順は、**使ったファイル名と操作を、別の人がそのままなぞれる**ように書いてください（「〇〇を左、△△を右に読み込む → ［重ね合わせ］タブ → …」）。
  実際に取れた値（ステータス行の文字、件数、通知の文言）と、証拠のスクリーンショットのパスを添えます。

## 作業量の目安
- 職種別の指示にある課題を、上から順に。全部で 30〜50 回ほどのツール呼び出しを目安に、終わらない課題は「確認できなかったこと」に書いて切り上げてください。

## 報告（最後に必ず）
報告は**ファイルに保存せず、最後のメッセージとしてそのまま返して**ください（日本語、全体で 80 行以内を目安に簡潔に）。

```
# Rnn 職種名 のレビュー
## 総評（3行以内。仕事に使えるか）
## 不具合
### B1［重要度 高|中|低］見出し（1行）
- 手順：…
- 期待：…
- 実際：…（取れた値・文言）
- 証拠：スクリーンショット等のパス
- 再現：2/2 など
（B2, B3 …）
## 追加要望
- Q1 …（なぜ必要か、を一言）
## データの誤り（あれば）
- …
## 良かった点
- …
## 確認できなかったこと
- …
```
重要度の目安：高＝結果の誤り・見落とし・データが失われる・止まる／中＝操作できない・誤解を招く／低＝表示の乱れ・言葉。
"""

EXAMPLE = '''"""レビュー用のひな形。自分の出力フォルダ（review4/_results/Rnn/）にコピーして書き換えて使う。
実行：python3 review4/_results/Rnn/step1.py"""
import asyncio, os, sys, glob, time
sys.path.insert(0, '/home/user/ShibaDiff/tests')
from harness import Tool

NO = 'R00'                                                   # ← 自分の番号
D = glob.glob(f'/home/user/ShibaDiff/review4/{NO}_*/')[0]     # 自分のデータフォルダ
OUT = f'/home/user/ShibaDiff/review4/_results/{NO}'           # 出力先（スクリーンショットなど）


async def main():
    # 画面の大きさは Tool(out_dir=OUT, width=…, height=…) で変えられる。タッチ端末は mobile=True
    async with Tool(out_dir=OUT, width=1440, height=900) as t:
        p = t.page
        # 外部への通信を記録する（file:・data:・blob: 以外）
        reqs = []; p.on('request', lambda r: reqs.append(r.url) if not r.url.startswith(('file:', 'data:', 'blob:')) else None)

        # --- ウィンドウへのドロップ（ファイルでもフォルダでも。エクスプローラからドロップしたのと同じ経路）---
        cdp = await p.context.new_cdp_session(p)
        async def drop(paths, x, y=400):
            """x が画面の左半分なら左、右半分なら右に入る。paths は絶対パスのリスト"""
            data = {'items': [], 'files': paths, 'dragOperationsMask': 1}
            for typ in ('dragEnter', 'dragOver', 'drop'):
                await cdp.send('Input.dispatchDragEvent', {'type': typ, 'x': x, 'y': y, 'data': data})
            await p.wait_for_timeout(500); await t.wait_idle()

        # --- ファイルを左右に読み込む（ファイル選択と同じ）---
        files = sorted(glob.glob(D + '*'))
        print('\\n'.join(files))
        # sec = await t.load(D + '左のファイル', D + '右のファイル'); print('読み込み秒数', sec)
        # print('通知:', await t.toast()); print('ステータス:', await t.status())
        # print(await t.visible_rows(80))                 # 表示中の差分行（[c]変更 [d]左のみ [i]右のみ）
        # await t.shot('01_text')                          # → OUT/01_text.png（Read ツールで開いて見る）
        # await t.click('#tNext'); await t.shot('02_next') # 次の変更へ
        # await t.tab('page'); await t.shot('03_page')     # ページ表示
        # await t.tab('overlay'); print(await t.ov_stats()); await t.shot('04_overlay')   # 重ね合わせ
        # await t.tab('text'); rep = await t.download('#tReport'); print(rep)             # レポート（HTML）をダウンロード
        # await t.tab('folder'); await drop([左のフォルダ], 300); await drop([右のフォルダ], 1100)   # フォルダ比較（ドロップ）
        # st = await t.load_folders(左のフォルダ, 右のフォルダ)                            # フォルダ比較（「フォルダを選択」と同じ）
        # print(await t.js("document.querySelector('#fdStatus').textContent"))
        # キー操作：await t.key('Alt+ArrowDown')　　任意の JS：await t.js("document.title")
        print('エラー:', t.errors); print('外部通信:', reqs)

asyncio.run(main())
'''

COMMON = """## 共通で見ること（余裕があれば）
- 初めて開いたとき、何をすればよいかが画面から分かるか
- 処理中であることが分かるか、待ち時間は許せるか（秒数を測る）
- エラーや通知の言葉が、専門用語なしで分かるか
- 結果を人に渡す手段（レポート・印刷・書き出し）が、仕事にそのまま使えるか
"""


def load_spec(only=None):
    spec = []
    for mod, nums in PARTS.items():
        if only and not (set(nums) & only): continue
        spec += importlib.import_module(mod).SPEC
    return sorted(spec, key=lambda x: x[0])


def write_common(spec):
    c = os.path.join(ROOT, '_共通'); os.makedirs(os.path.join(c, 'briefs'), exist_ok=True); os.makedirs(os.path.join(ROOT, '_results'), exist_ok=True)
    open(os.path.join(c, 'レビューの進め方.md'), 'w', encoding='utf-8').write(GUIDE)
    open(os.path.join(c, 'example.py'), 'w', encoding='utf-8').write(EXAMPLE)
    for no, role, dept, gen, brief in spec:
        d = f'R{no:02d}_{dept}_{role}'
        s = f"# R{no:02d} レビュアーへの指示\n\n## あなた\n{brief['who']}\n\n## データ\n`/home/user/ShibaDiff/review4/{d}/`\n（`正解.md` は、自分で調べたあとに見る）\n\n" \
            f"## 出力先\n`/home/user/ShibaDiff/review4/_results/R{no:02d}/`（スクリプト・スクリーンショット。報告はファイルにせず、最後のメッセージで返す）\n\n" \
            "## 課題（上から順に）\n" + ''.join(f'{i + 1}. {x}\n' for i, x in enumerate(brief['tasks'])) + \
            (f"\n## 補足\n{brief['note']}\n" if brief.get('note') else '') + '\n' + COMMON
        open(os.path.join(c, 'briefs', f'R{no:02d}.md'), 'w', encoding='utf-8').write(s)


def main(only=None):
    spec = load_spec(only)
    if os.path.exists(ROOT):
        for n in os.listdir(ROOT):
            if n.startswith('R') and n[1:3].isdigit() and os.path.isdir(os.path.join(ROOT, n)) and (not only or int(n[1:3]) in only): shutil.rmtree(os.path.join(ROOT, n))
    done = []
    for no, role, dept, gen, brief in spec:
        if only and no not in only: continue
        gen(f'R{no:02d}_{dept}_{role}'); done.append((no, role, dept, gen, brief)); print('gen', no, role, flush=True)

    async def mk():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path=G.chrome_path(), args=['--no-sandbox']); pg = await b.new_page()
            for path, html, o in R3.PDFQ:
                await pg.set_content(html); await pg.wait_for_timeout(150)
                await pg.pdf(path=path, format=o.get('format', 'A4'), landscape=o.get('landscape', False), margin=o.get('margin'), print_background=True,
                             display_header_footer=o.get('display_header_footer', False), header_template=o.get('header_template', '<span></span>'), footer_template=o.get('footer_template', '<span></span>'),
                             width=o.get('width'), height=o.get('height'), prefer_css_page_size=o.get('prefer_css_page_size', False))
            await b.close()
    if R3.PDFQ: asyncio.run(mk())
    if R3.SOQ:
        prof = tempfile.mkdtemp()   # LibreOffice の設定の置き場所を実行ごとに分ける（同時に動かしても、ぶつからない）
        for src, dst, fmt in R3.SOQ:
            tmp = tempfile.mkdtemp()
            subprocess.run(['soffice', f'-env:UserInstallation=file://{prof}', '--headless', '--convert-to', fmt, '--outdir', tmp, src], check=True, capture_output=True, timeout=300)
            shutil.move(os.path.join(tmp, os.path.splitext(os.path.basename(src))[0] + '.' + fmt.split(':')[0]), dst); shutil.rmtree(tmp)
        shutil.rmtree(prof, ignore_errors=True)
    for f in R3.POST: f()
    for d, lines in R3.KEYS.items():
        open(G.P(f'{d}/正解.md'), 'w', encoding='utf-8').write('# 用意した変更点（レビュアーは、自分で確かめたあとに照らし合わせる）\n\n' + ''.join(f'- {x}\n' for x in lines))
    write_common(done)
    print('ok', len(R3.KEYS), ROOT)


if __name__ == '__main__':
    main(set(int(x) for x in sys.argv[1:]) or None)
