# 文書比較ツール

WinMerge のテキスト比較と DocuWorks Viewer のページ表示・注釈を1つにまとめた、**単一HTMLファイル**の文書比較ツールです。
インストール不要で、ネットワークにつながらない環境でも動きます（外部との通信は Content-Security-Policy で禁止しています）。

## 使い方
`dist/文書比較ツール.html` を Edge / Chrome で開き、比較したいファイルを左右にドロップします。

| 機能 | 内容 |
|---|---|
| テキスト比較 | 左右並列／一列表示、行内の文字・単語単位の差分、差分の移動・左右コピー、空白・大小文字・空行・全角半角の無視、検索、文字コード自動判定と保存、パッチ（git形式）・HTMLレポート出力 |
| ページ表示・注釈 | ページの並列表示・スクロール連動・回転・拡大、ペン・マーカー・枠・付箋・日付印、注釈の保存・印刷／PDF |
| 重ね合わせ比較 | PDF・画像の画素差分（差分ハイライト／透かし／スワイプ／点滅／並べて）、位置と傾きの自動補正、全ページ一括チェック |
| フォルダ比較 | 同一／相違／左のみ／右のみの一覧、ダブルクリックで中身を比較 |

対応形式：テキスト（Shift_JIS / EUC-JP / JIS / UTF-8 / UTF-16）、PDF、Word (.docx)、Excel (.xlsx)、PowerPoint (.pptx)、PNG / JPEG / GIF / BMP / WebP

## ドキュメント
- [要件定義書](docs/01_要件定義書.md)
- [基本設計書](docs/02_基本設計書.md)
- [詳細設計書](docs/03_詳細設計書.md)

## ビルド
```
npm ci              # pdf.js を取得
python3 build.py    # dist/文書比較ツール.html を生成
```
ソースは `src/` にあり、`build.py` が CSS・JavaScript・pdf.js（ワーカー・日本語CMap込み）を1つのHTMLにまとめます。

## テスト
```
pip install playwright python-docx openpyxl python-pptx pillow reportlab
python3 tools/gen_samples.py        # samples/ にサンプルファイルを生成
python3 tests/test_regression.py    # 各テストは headless Chrome で実際に操作して確認します
```

## 同梱ライブラリ
- pdf.js（Apache License 2.0）
- core-js（MIT License、pdf.js に同梱）
