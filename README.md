# ShibaDiff

WinMerge のテキスト比較と DocuWorks Viewer のページ表示・注釈を1つにまとめた、**単一HTMLファイル**の文書比較ツールです。
インストール不要で、ネットワークにつながらない環境でも動きます（外部との通信は Content-Security-Policy で禁止しています）。

## 使い方
`ShibaDiff.html` を Edge / Chrome で開き、比較したいファイルを左右にドロップします。
ダウンロードして手元で開いても、GitHub Pages で公開したページを開いても同じように動きます（どちらでもファイルは外部に送信されません）。

| 機能 | 内容 |
|---|---|
| テキスト比較 | 左右並列／一列表示、行内の文字・単語単位の差分、差分の移動・左右コピー、空白・大小文字・空行・全角半角の無視、検索、文字コード自動判定と保存、パッチ（git形式）・HTMLレポート出力 |
| ページ表示・注釈 | ページの並列表示・スクロール連動（挿入・削除されたページを飛ばして対応）・回転・拡大、ペン・マーカー・枠・付箋、注釈の保存・印刷／PDF・HTMLレポート |
| 重ね合わせ比較 | PDF・画像の画素差分（差分ハイライト／透かし／スワイプ／点滅／並べて）、位置と傾きの自動補正、挿入・削除されたページの自動対応付け、全ページ一括チェック、解像度の切り替え（A0 などの大きな図面向け）、HTMLレポート |
| フォルダ比較 | 同一／相違／左のみ／右のみの一覧、ダブルクリックで中身を比較、CSV・HTMLレポート出力 |

対応形式：テキスト（Shift_JIS / EUC-JP / JIS / UTF-8 / UTF-16）、PDF、Word (.docx)、Excel (.xlsx)、PowerPoint (.pptx)、PNG / JPEG / GIF / BMP / WebP

## ドキュメント
- [要件定義書](docs/01_要件定義書.md)
- [基本設計書](docs/02_基本設計書.md)
- [詳細設計書](docs/03_詳細設計書.md)

## ビルド
```
npm ci              # pdf.js と Lucide アイコンを取得
python3 build.py    # ShibaDiff.html を生成
```
ソースは `src/` にあり、`build.py` が CSS・JavaScript・pdf.js（ワーカー・日本語CMap込み）を1つのHTMLにまとめます。

## テスト
```
pip install -r requirements-dev.txt
python3 -m playwright install chromium   # Google Chrome があれば不要（CHROME_PATH で場所を指定できます）
npm run samples                          # samples/ にサンプルファイルを生成（乱数の種は固定）
npm test                                 # すべてのテストを headless Chrome で実行
```
各テストは画面を実際に操作し、結果を `OK` / `NG` で表示します。1つでも `NG` があれば終了コードが 1 になります。
スクリーンショットやダウンロードしたファイルは `tests/out/` に保存されます。

## ライセンス
ShibaDiff は [MIT License](LICENSE) で公開しています。

同梱しているライブラリとそのライセンスは次のとおりです。全文は、アプリの「設定」→「このツールについて」→「ライセンス全文を表示」で確認できます。
- [pdf.js](https://github.com/mozilla/pdf.js) 4.10.38（Apache License 2.0）
- [core-js](https://github.com/zloirock/core-js) 3.39.0（MIT License、pdf.js の legacy ビルドに同梱）
- [Lucide](https://lucide.dev) 1.81.0 のアイコン（ISC License。Feather 由来の一部は MIT License。使っているアイコンだけを SVG として埋め込み）

## 業務で使うときの注意
GitHub Pages 版は main ブランチの最新がそのまま反映されます。業務では、版を固定するために `ShibaDiff.html` をダウンロードして使うことをおすすめします。
