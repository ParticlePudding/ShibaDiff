#!/usr/bin/env python3
"""サンプルファイル生成（共通セット + レビュアー別セット）"""
import os, random, shutil, asyncio, json, io
import docx
from docx.shared import Pt
import openpyxl
from openpyxl.styles import Font, PatternFill
from pptx import Presentation
from pptx.util import Inches, Pt as PPt
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.pagesizes import A4

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'samples')
random.seed(42)
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
FONTB = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
CHROME_PDFS = []  # (path, html)
# Chrome の場所：環境変数 CHROME_PATH → /usr/bin/google-chrome → Playwright 同梱の Chromium（tests/harness.py と同じ決め方）
def chrome_path():
    return os.environ.get('CHROME_PATH') or ('/usr/bin/google-chrome' if os.path.exists('/usr/bin/google-chrome') else None)

def P(*a):
    p = os.path.join(ROOT, *a); os.makedirs(os.path.dirname(p), exist_ok=True); return p

def text(path, s, enc='utf-8', eol='\n', bom=False):
    b = s.replace('\r\n', '\n').replace('\n', eol).encode('cp932' if enc == 'shift_jis' else enc)
    if bom: b = b'\xef\xbb\xbf' + b
    open(P(path), 'wb').write(b)

def mkdocx(path, title, blocks):
    d = docx.Document()
    st = d.styles['Normal']; st.font.name = 'Yu Mincho'; st.font.size = Pt(10.5)
    d.add_heading(title, 1)
    for b in blocks:
        if isinstance(b, tuple) and b[0] == 'h': d.add_heading(b[1], 2)
        elif isinstance(b, tuple) and b[0] == 'table':
            rows = b[1]; t = d.add_table(rows=len(rows), cols=len(rows[0])); t.style = 'Table Grid'
            for i, r in enumerate(rows):
                for j, v in enumerate(r): t.cell(i, j).text = str(v)
        elif isinstance(b, tuple) and b[0] == 'li': d.add_paragraph(b[1], style='List Number')
        else: d.add_paragraph(b)
    d.save(P(path))

def mkxlsx(path, sheets):
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows: ws.append(r)
        for c in ws[1]: c.font = Font(bold=True); c.fill = PatternFill('solid', fgColor='DDEBF7')
        for col in ws.columns: ws.column_dimensions[col[0].column_letter].width = 14
    wb.save(P(path))

def mkpptx(path, slides, notes=None):
    pr = Presentation(); pr.slide_width = Inches(13.33); pr.slide_height = Inches(7.5)
    for i, (title, bullets) in enumerate(slides):
        s = pr.slides.add_slide(pr.slide_layouts[1])
        s.shapes.title.text = title
        tf = s.placeholders[1].text_frame; tf.text = bullets[0] if bullets else ''
        for b in bullets[1:]: tf.add_paragraph().text = b
        if notes and i < len(notes) and notes[i]: s.notes_slide.notes_text_frame.text = notes[i]
    pr.save(P(path))

def pdf_cid(path, pages, title=None, font='HeiseiKakuGo-W5'):
    """非埋め込みの日本語CIDフォントを使うPDF（CMap処理の確認用）"""
    c = rl_canvas.Canvas(P(path), pagesize=A4); W, H = A4
    for pi, lines in enumerate(pages):
        y = H - 60
        if title and pi == 0:
            c.setFont(font, 18); c.drawString(50, y, title); y -= 36
        c.setFont(font, 10.5)
        for ln in lines:
            if ln.startswith('## '): c.setFont(font, 13); c.drawString(50, y, ln[3:]); c.setFont(font, 10.5); y -= 22; continue
            c.drawString(50, y, ln); y -= 17
            if y < 60: break
        c.setFont(font, 8); c.drawCentredString(W / 2, 30, f'- {pi + 1} -')
        c.showPage()
    c.save()

def chrome_pdf(path, html):
    CHROME_PDFS.append((P(path), html))

def html_doc(body, css=''):
    return f"""<html><head><meta charset="utf-8"><style>body{{font-family:'Noto Sans CJK JP';font-size:11pt;margin:36px 44px;line-height:1.6}}
h1{{font-size:20pt;border-bottom:2px solid #333}}table{{border-collapse:collapse}}td,th{{border:1px solid #555;padding:4px 10px}}th{{background:#eee}}
.pb{{page-break-before:always}}{css}</style></head><body>{body}</body></html>"""

def font(sz, bold=False): return ImageFont.truetype(FONTB if bold else FONT, sz)

def drawing(path, rev, dims, extra=None, offset=(0, 0), rot=0.0, noise=0, size=(1654, 1169), fmt=None, scan=False):
    """機械図面風の画像"""
    W, H = size; im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im)
    ox, oy = offset
    d.rectangle([30 + ox, 30 + oy, W - 30 + ox, H - 30 + oy], outline='black', width=4)
    # title block
    tb = [W - 560 + ox, H - 230 + oy, W - 30 + ox, H - 30 + oy]
    d.rectangle(tb, outline='black', width=3)
    for k in range(1, 4): d.line([tb[0], tb[1] + k * 50, tb[2], tb[1] + k * 50], fill='black', width=2)
    d.text((tb[0] + 15, tb[1] + 8), f"図番 DWG-2041-{rev}", fill='black', font=font(28, True))
    d.text((tb[0] + 15, tb[1] + 58), "品名 ブラケット（取付金具）", fill='black', font=font(26))
    d.text((tb[0] + 15, tb[1] + 108), f"材質 {dims.get('mat', 'SS400')}　表面処理 {dims.get('surf', '黒染め')}", fill='black', font=font(24))
    d.text((tb[0] + 15, tb[1] + 158), f"改訂 {rev}　尺度 1:2　設計 山本", fill='black', font=font(24))
    # part outline
    x0, y0 = 250 + ox, 260 + oy; w = dims['w'] * 4; h = dims['h'] * 4
    d.rectangle([x0, y0, x0 + w, y0 + h], outline='black', width=5)
    for hx in dims['holes']:
        cx, cy = x0 + hx[0] * 4, y0 + hx[1] * 4; r = hx[2] * 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline='black', width=4)
        d.line([cx - r - 12, cy, cx + r + 12, cy], fill='black', width=1); d.line([cx, cy - r - 12, cx, cy + r + 12], fill='black', width=1)
    # dimension lines
    d.line([x0, y0 - 60, x0 + w, y0 - 60], fill='black', width=2)
    d.text((x0 + w / 2 - 40, y0 - 105), f"{dims['w']}", fill='black', font=font(34))
    d.line([x0 - 70, y0, x0 - 70, y0 + h], fill='black', width=2)
    d.text((x0 - 160, y0 + h / 2 - 20), f"{dims['h']}", fill='black', font=font(34))
    d.text((x0, y0 + h + 40), f"穴 {len(dims['holes'])}-φ{dims['holes'][0][2]}", fill='black', font=font(30))
    if extra: d.text((x0, y0 + h + 90), extra, fill='black', font=font(28))
    d.text((60 + ox, 50 + oy), "注記：指示なき角部はC0.5", fill='black', font=font(24))
    if rot: im = im.rotate(rot, resample=Image.BICUBIC, fillcolor='white')
    if scan:
        im = im.filter(ImageFilter.GaussianBlur(0.8))
        px = im.load()
        for _ in range(noise):
            x, y = random.randrange(W), random.randrange(H); v = random.randint(120, 200); px[x, y] = (v, v, v)
        im = im.convert('L').convert('RGB')
        im = Image.eval(im, lambda v: min(255, int(v * 0.97 + 10)))
    im.save(P(path), format=fmt)
    return im

def page_image(lines, title=None, size=(1240, 1754), offset=(0, 0), rot=0.0, scan=True, stamp=None):
    """スキャンした紙文書風の画像（A4 150dpi相当）"""
    W, H = size; im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im); ox, oy = offset
    y = 120 + oy
    if title: d.text((110 + ox, y), title, fill='black', font=font(46, True)); y += 110
    for ln in lines:
        if ln.startswith('## '): d.text((110 + ox, y), ln[3:], fill='black', font=font(32, True)); y += 62; continue
        d.text((110 + ox, y), ln, fill='black', font=font(27)); y += 50
    if stamp:
        cx, cy = W - 230 + ox, 170 + oy
        d.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], outline=(200, 30, 30), width=5)
        d.text((cx - 48, cy - 22), stamp, fill=(200, 30, 30), font=font(40, True))
    if rot: im = im.rotate(rot, resample=Image.BICUBIC, fillcolor='white')
    if scan:
        im = im.filter(ImageFilter.GaussianBlur(0.7)); px = im.load()
        for _ in range(2500):
            x, y2 = random.randrange(W), random.randrange(H); v = random.randint(150, 220); px[x, y2] = (v, v, v)
    return im

def scan_pdf(path, images):
    images[0].save(P(path), save_all=True, append_images=images[1:], resolution=150)

# =====================================================================================
# 共通セット（形式ごと）
# =====================================================================================
def common():
    base = '00_共通サンプル（形式別）'
    memo_a = """社内連絡
件名：年末年始の休業について
日付：2026年11月20日

各位
年末年始の休業期間を下記のとおりお知らせします。

休業期間：12月28日（月）～1月4日（月）
緊急連絡先：総務部 内線1234
休業前の最終出荷：12月25日（金）15時まで

以上
"""
    memo_b = memo_a.replace('1月4日（月）', '1月5日（火）').replace('15時まで', '12時まで').replace('内線1234', '内線1234（不在時は090-0000-0000）') + "\n追記：休業中のサーバー停止は12月29日に実施します。\n"
    text(f'{base}/01_テキスト_UTF-8/連絡文_旧.txt', memo_a)
    text(f'{base}/01_テキスト_UTF-8/連絡文_新.txt', memo_b)
    text(f'{base}/02_テキスト_Shift_JIS_CRLF/連絡文_旧_SJIS.txt', memo_a, 'shift_jis', '\r\n')
    text(f'{base}/02_テキスト_Shift_JIS_CRLF/連絡文_新_SJIS.txt', memo_b, 'shift_jis', '\r\n')
    text(f'{base}/03_テキスト_文字コード違い/連絡文_EUC-JP.txt', memo_a.replace('～', '〜'), 'euc-jp')
    text(f'{base}/03_テキスト_文字コード違い/連絡文_UTF-8_BOM付.txt', memo_a, 'utf-8', '\r\n', bom=True)
    text(f'{base}/03_テキスト_文字コード違い/連絡文_UTF-16LE.txt', '﻿' + memo_a, 'utf-16-le', '\r\n')
    csv_h = '商品コード,商品名,単価,在庫数,倉庫\n'
    rows = [(f'P{1000+i}', n, p, q, w) for i, (n, p, q, w) in enumerate([('ボールペン 黒', 120, 340, '東京'), ('ボールペン 赤', 120, 210, '東京'), ('ノート A4', 250, 95, '大阪'), ('付箋 75mm', 180, 500, '東京'), ('クリップ 大', 90, 1200, '福岡'), ('ホチキス', 980, 40, '大阪')])]
    ca = csv_h + ''.join(f'{a},{b},{c},{d},{e}\n' for a, b, c, d, e in rows)
    rows2 = [list(r) for r in rows]; rows2[2][3] = 60; rows2[4][2] = 95; del rows2[5]; rows2.append(['P1006', 'ファイル A4', 160, 300, '東京'])
    cb = csv_h + ''.join(f'{a},{b},{c},{d},{e}\n' for a, b, c, d, e in rows2)
    text(f'{base}/04_CSV/在庫_1月.csv', ca, 'shift_jis', '\r\n'); text(f'{base}/04_CSV/在庫_2月.csv', cb, 'shift_jis', '\r\n')
    md_a = "# 会議メモ\n\n## 決定事項\n- 次回リリースは12月10日\n- レビュー担当は佐藤さん\n\n## 宿題\n1. 仕様書の更新（田中）\n2. テスト計画の作成（鈴木）\n"
    md_b = "# 会議メモ\n\n## 決定事項\n- 次回リリースは12月17日（1週間延期）\n- レビュー担当は佐藤さん、高橋さん\n\n## 宿題\n1. 仕様書の更新（田中）\n2. テスト計画の作成（鈴木）\n3. 顧客への延期連絡（営業 中村）\n"
    text(f'{base}/05_Markdown/会議メモ_v1.md', md_a); text(f'{base}/05_Markdown/会議メモ_v2.md', md_b)
    ja = {"app": {"name": "業務システム", "version": "2.3.1", "port": 8080}, "db": {"host": "db01", "pool": 10, "timeout": 30}, "features": ["export", "audit"]}
    jb = json.loads(json.dumps(ja)); jb['app']['version'] = '2.4.0'; jb['db']['pool'] = 20; jb['features'].append('sso')
    text(f'{base}/06_JSON/config_v2.3.json', json.dumps(ja, ensure_ascii=False, indent=2)); text(f'{base}/06_JSON/config_v2.4.json', json.dumps(jb, ensure_ascii=False, indent=2))
    mkdocx(f'{base}/07_Word/議事録_初版.docx', '定例会議 議事録', ['日時：2026年11月18日 10:00～11:00', '出席者：山田、佐藤、田中、鈴木', ('h', '議題'), ('li', '前回宿題の確認'), ('li', '新システム導入スケジュール'), ('h', '決定事項'), '新システムは2027年4月に本稼働とする。', ('table', [['項目', '担当', '期限'], ['要件定義', '佐藤', '12月20日'], ['見積取得', '田中', '12月10日']])])
    mkdocx(f'{base}/07_Word/議事録_修正版.docx', '定例会議 議事録', ['日時：2026年11月18日 10:00～11:30', '出席者：山田、佐藤、田中、鈴木、高橋（オブザーバー）', ('h', '議題'), ('li', '前回宿題の確認'), ('li', '新システム導入スケジュール'), ('li', '予算の確認'), ('h', '決定事項'), '新システムは2027年5月に本稼働とする（移行期間を1か月延長）。', ('table', [['項目', '担当', '期限'], ['要件定義', '佐藤', '12月25日'], ['見積取得', '田中', '12月10日'], ['予算申請', '山田', '1月15日']])])
    mkxlsx(f'{base}/08_Excel/予算_当初.xlsx', {'部門別': [['部門', '人件費', '経費', '設備費', '合計'], ['営業', 5200, 800, 0, 6000], ['開発', 8400, 600, 1200, 10200], ['総務', 3100, 400, 100, 3600]], '前提': [['項目', '値'], ['為替(円/ドル)', 145], ['昇給率', '2.0%']]})
    mkxlsx(f'{base}/08_Excel/予算_修正.xlsx', {'部門別': [['部門', '人件費', '経費', '設備費', '合計'], ['営業', 5200, 950, 0, 6150], ['開発', 8900, 600, 1500, 11000], ['総務', 3100, 400, 100, 3600], ['品証', 2400, 200, 300, 2900]], '前提': [['項目', '値'], ['為替(円/ドル)', 150], ['昇給率', '2.5%']]})
    mkpptx(f'{base}/09_PowerPoint/提案書_v1.pptx', [('業務効率化のご提案', ['株式会社サンプル 御中', '2026年11月']), ('現状の課題', ['紙の回覧に平均3日かかる', '版管理が属人化している']), ('ご提案内容', ['文書管理システムの導入', '初期費用 300万円', '月額 5万円'])], notes=['', '課題はヒアリング結果より', ''])
    mkpptx(f'{base}/09_PowerPoint/提案書_v2.pptx', [('業務効率化のご提案', ['株式会社サンプル 御中', '2026年12月']), ('現状の課題', ['紙の回覧に平均3日かかる', '版管理が属人化している', '外出先から承認できない']), ('ご提案内容', ['文書管理システムの導入', '初期費用 250万円（キャンペーン適用）', '月額 5万円']), ('導入スケジュール', ['1月 要件確認', '2月 設定・移行', '3月 本稼働'])], notes=['', '課題はヒアリング結果より（12/1追記）', '値引きは部長承認済み', ''])
    est = lambda name, work, parts, due: html_doc(f"<h1>御見積書</h1><p>株式会社サンプル 御中</p><p>件名：{name}</p><table><tr><th>品目</th><th>金額</th></tr><tr><td>作業費</td><td>{work}円</td></tr><tr><td>部品代</td><td>{parts}円</td></tr></table><p>納期：{due}</p><p>有効期限：発行日より30日</p><div class='pb'><h2>特記事項</h2><p>本見積には出張費を含みません。</p></div>")
    chrome_pdf(f'{base}/10_PDF_テキスト/見積書_初回.pdf', est('サーバー保守', '100,000', '20,000', '2026年12月1日'))
    chrome_pdf(f'{base}/10_PDF_テキスト/見積書_再提出.pdf', est('サーバー保守（延長）', '120,000', '20,000', '2026年12月15日'))
    pdf_cid(f'{base}/11_PDF_非埋め込みフォント/お知らせ_旧.pdf', [['施設点検のお知らせ', '', '点検日：2026年12月5日（土）', '時間：9時～12時', '対象：本館 全フロア', '', '点検中はエレベーターが停止します。']], title='お知らせ')
    pdf_cid(f'{base}/11_PDF_非埋め込みフォント/お知らせ_新.pdf', [['施設点検のお知らせ', '', '点検日：2026年12月12日（土）', '時間：9時～15時', '対象：本館・別館 全フロア', '', '点検中はエレベーターが停止します。', '駐車場は通常どおり利用できます。']], title='お知らせ')
    la = ['## 1. 目的', '本書は備品の貸出手順を定める。', '## 2. 手順', '(1) 貸出簿に記入する。', '(2) 総務の確認印を受ける。', '(3) 返却時に状態を確認する。']
    lb = ['## 1. 目的', '本書は備品の貸出手順を定める。', '## 2. 手順', '(1) 貸出システムに登録する。', '(2) 総務の確認印を受ける。', '(3) 返却時に状態を確認し、写真を残す。']
    scan_pdf(f'{base}/12_PDF_スキャン画像/貸出手順_旧_スキャン.pdf', [page_image(la, '備品貸出手順', stamp='承認')])
    scan_pdf(f'{base}/12_PDF_スキャン画像/貸出手順_新_スキャン.pdf', [page_image(lb, '備品貸出手順', offset=(6, 9), rot=0.25, stamp='承認')])
    dims = {'w': 120, 'h': 80, 'holes': [(20, 20, 8), (100, 20, 8), (20, 60, 8), (100, 60, 8)]}
    drawing(f'{base}/13_画像_PNG/図面_RevA.png', 'A', dims)
    dims2 = dict(dims, w=130, holes=[(20, 20, 10), (110, 20, 10), (20, 60, 10), (110, 60, 10)])
    drawing(f'{base}/13_画像_PNG/図面_RevB.png', 'B', dims2, extra='※穴径変更（φ8→φ10）')
    drawing(f'{base}/14_画像_JPEG/図面_RevA_スキャン.jpg', 'A', dims, scan=True, noise=4000, fmt='JPEG')
    drawing(f'{base}/14_画像_JPEG/図面_RevB_スキャン.jpg', 'B', dims2, extra='※穴径変更（φ8→φ10）', offset=(7, -5), rot=0.3, scan=True, noise=4000, fmt='JPEG')
    src_a = '''def calc_price(qty, unit):
    """税込金額を計算する"""
    subtotal = qty * unit
    tax = int(subtotal * 0.08)
    return subtotal + tax


def is_member(user):
    return user.get("member") == True
'''
    src_b = '''def calc_price(qty, unit, rate=0.10):
    """税込金額を計算する（税率を引数化）"""
    if qty < 0:
        raise ValueError("数量が負です")
    subtotal = qty * unit
    tax = round(subtotal * rate)
    return subtotal + tax


def is_member(user):
    return bool(user.get("member"))
'''
    text(f'{base}/15_ソースコード/price_old.py', src_a); text(f'{base}/15_ソースコード/price_new.py', src_b)
    open(P(f'{base}/16_バイナリ/data_v1.bin'), 'wb').write(bytes(range(256)) * 4)
    bb = bytearray(bytes(range(256)) * 4); bb[100] = 0xFF; bb[700:704] = b'ABCD'; open(P(f'{base}/16_バイナリ/data_v2.bin'), 'wb').write(bytes(bb))
    for side, extra in (('旧版フォルダ', {}), ('新版フォルダ', {'追加資料.txt': '新しく追加したファイル\n'})):
        root = f'{base}/17_フォルダ比較/{side}'
        text(f'{root}/連絡文.txt', memo_a if side == '旧版フォルダ' else memo_b)
        text(f'{root}/共通/規程.txt', '変更のないファイル\n')
        if side == '旧版フォルダ': text(f'{root}/廃止予定.txt', '旧版にだけあるファイル\n')
        for k, v in extra.items(): text(f'{root}/{k}', v)
        shutil.copy(P(f'{base}/08_Excel/予算_当初.xlsx'), P(f'{root}/共通/予算.xlsx'))

# =====================================================================================
# レビュアー別セット
# =====================================================================================
REVIEWERS = []
def R(no, role, dept, years, focus, files_desc, gen):
    REVIEWERS.append(dict(no=no, role=role, dept=dept, years=years, focus=focus, files=files_desc, dir=f'R{no:02d}_{dept}_{role}'))
    gen(f'R{no:02d}_{dept}_{role}')

def r01(d):
    base = ['第1条（目的）', '甲は乙に対し、システム保守業務（以下「本業務」）を委託し、乙はこれを受託する。', '第2条（契約期間）', '本契約の期間は2027年4月1日から2028年3月31日までとする。',
            '第3条（委託料）', '甲は乙に対し、本業務の対価として月額500,000円（税別）を支払う。', '第4条（支払条件）', '甲は毎月末日締め、翌月末日までに乙の指定口座に振り込む。',
            '第5条（秘密保持）', '甲及び乙は、本業務により知り得た相手方の秘密を第三者に開示してはならない。', '第6条（損害賠償）', '乙の責に帰すべき事由により甲に損害が生じた場合、乙はその損害を賠償する。',
            '第7条（解除）', '甲又は乙は、相手方が本契約に違反した場合、催告の上、本契約を解除できる。', '第8条（協議）', '本契約に定めのない事項は、甲乙協議の上解決する。']
    rev = list(base)
    rev[5] = '甲は乙に対し、本業務の対価として月額550,000円（税別）を支払う。'
    rev[7] = '甲は毎月末日締め、翌々月10日までに乙の指定口座に振り込む。'
    rev[11] = '乙の責に帰すべき事由により甲に損害が生じた場合、乙は直近12か月の委託料総額を上限としてその損害を賠償する。'
    rev[13] = '甲又は乙は、相手方が本契約に違反し、30日以内に是正されない場合、本契約を解除できる。'
    rev[9] = rev[9] + 'ただし、法令に基づき開示が求められた場合はこの限りでない。'
    mkdocx(f'{d}/業務委託契約書_当社案.docx', '業務委託契約書', ['株式会社サンプル（以下「甲」）と株式会社テスト（以下「乙」）は、次のとおり契約を締結する。'] + base + ['（以下余白）'])
    mkdocx(f'{d}/業務委託契約書_先方修正版.docx', '業務委託契約書', ['株式会社サンプル（以下「甲」）と株式会社テスト（以下「乙」）は、次のとおり契約を締結する。'] + rev + ['第9条（反社会的勢力の排除）', '甲及び乙は、反社会的勢力に該当しないことを表明し保証する。', '（以下余白）'])
    chrome_pdf(f'{d}/業務委託契約書_先方修正版.pdf', html_doc('<h1>業務委託契約書</h1>' + ''.join(f'<p>{x}</p>' for x in rev)))
def r02(d):
    a = ['第10条（勤務時間）', '始業 9時00分　終業 17時45分　休憩 12時00分～13時00分', '第11条（休日）', '土曜日、日曜日、国民の祝日、年末年始（12月29日～1月3日）', '第12条（時間外労働）', '会社は業務の都合により時間外労働を命じることがある。', '第15条（年次有給休暇）', '入社6か月経過後に10日を付与する。']
    b = ['第10条（勤務時間）', '始業 9時00分　終業 17時30分　休憩 12時00分～12時45分', '第10条の2（フレックスタイム制）', '別に定める協定により、フレックスタイム制を適用することがある。', '第11条（休日）', '土曜日、日曜日、国民の祝日、年末年始（12月28日～1月4日）', '第12条（時間外労働）', '会社は業務の都合により、36協定の範囲内で時間外労働を命じることがある。', '第15条（年次有給休暇）', '入社日に5日、入社6か月経過後に5日を付与する。']
    mkdocx(f'{d}/就業規則_2025年版.docx', '就業規則（抜粋）', a + [('table', [['改定日', '内容'], ['2025/4/1', '制定']])])
    mkdocx(f'{d}/就業規則_2026年改定案.docx', '就業規則（抜粋）', b + [('table', [['改定日', '内容'], ['2025/4/1', '制定'], ['2026/4/1', '勤務時間・休暇の見直し']])])
    chrome_pdf(f'{d}/就業規則_2025年版.pdf', html_doc('<h1>就業規則（抜粋）</h1>' + ''.join(f'<p>{x}</p>' for x in a)))
    chrome_pdf(f'{d}/就業規則_2026年改定案.pdf', html_doc('<h1>就業規則（抜粋）</h1>' + ''.join(f'<p>{x}</p>' for x in b)))
    text(f'{d}/規程一覧_旧.txt', '就業規則\n賃金規程\n旅費規程\n慶弔見舞金規程\n', 'shift_jis', '\r\n')
    text(f'{d}/規程一覧_新.txt', '就業規則\n賃金規程\n旅費規程（国内・海外）\n慶弔見舞金規程\nテレワーク規程\n', 'shift_jis', '\r\n')
def r03(d):
    hdr = ['請求番号', '取引先', '請求日', '金額(税抜)', '消費税', '合計', '入金予定日']
    rows = [[f'INV-26{i:04d}', c, f'2026/10/{(i % 28) + 1:02d}', amt, int(amt * 0.1), int(amt * 1.1), f'2026/11/{(i % 28) + 1:02d}'] for i, (c, amt) in enumerate([('株式会社アルファ', 120000), ('ベータ商事', 85000), ('ガンマ工業', 430000), ('デルタ電機', 56000), ('イプシロン', 990000), ('ゼータ物流', 210000)])]
    rows2 = [list(r) for r in rows]; rows2[2][3] = 450000; rows2[2][4] = 45000; rows2[2][5] = 495000; rows2[4][6] = '2026/12/10'; rows2.append(['INV-260006', 'イータ建設', '2026/10/30', 150000, 15000, 165000, '2026/11/30'])
    mkxlsx(f'{d}/売掛金一覧_10月_締め前.xlsx', {'売掛金': [hdr] + rows, '集計': [['区分', '件数', '合計'], ['10月請求', len(rows), sum(r[5] for r in rows)]]})
    mkxlsx(f'{d}/売掛金一覧_10月_確定.xlsx', {'売掛金': [hdr] + rows2, '集計': [['区分', '件数', '合計'], ['10月請求', len(rows2), sum(r[5] for r in rows2)]]})
    inv = lambda amt, due: html_doc(f"<h1>請求書</h1><p>ガンマ工業 御中</p><p>請求番号：INV-260002</p><table><tr><th>内容</th><th>数量</th><th>単価</th><th>金額</th></tr><tr><td>部品加工</td><td>10</td><td>{amt // 10:,}</td><td>{amt:,}</td></tr></table><p>消費税（10%）：{amt // 10:,}円</p><p>合計：{amt * 11 // 10:,}円</p><p>お支払期限：{due}</p><p>振込先：○○銀行 本店 普通 0000000</p>")
    chrome_pdf(f'{d}/請求書_ガンマ工業_初版.pdf', inv(430000, '2026年11月30日')); chrome_pdf(f'{d}/請求書_ガンマ工業_訂正版.pdf', inv(450000, '2026年11月30日'))
    text(f'{d}/仕訳データ_会計ソフト出力.csv', '日付,借方科目,借方金額,貸方科目,貸方金額,摘要\n' + ''.join(f'2026/10/{i+1:02d},売掛金,{r[5]},売上高,{r[5]},{r[1]}\n' for i, r in enumerate(rows)), 'shift_jis', '\r\n')
    text(f'{d}/仕訳データ_修正後.csv', '日付,借方科目,借方金額,貸方科目,貸方金額,摘要\n' + ''.join(f'2026/10/{i+1:02d},売掛金,{r[5]},売上高,{r[5]},{r[1]}\n' for i, r in enumerate(rows2)), 'shift_jis', '\r\n')
def r04(d):
    def spec(v, rows, notes):
        body = f"<h1>購入仕様書（{v}）</h1><p>件名：工場内ネットワーク機器更新</p><h2>1. 調達品目</h2><table><tr><th>No</th><th>品名</th><th>仕様</th><th>数量</th></tr>" + ''.join(f'<tr><td>{i+1}</td><td>{a}</td><td>{b}</td><td>{c}</td></tr>' for i, (a, b, c) in enumerate(rows)) + "</table>"
        body += "<div class='pb'><h2>2. 納入条件</h2>" + ''.join(f'<p>{n}</p>' for n in notes) + "</div><div class='pb'><h2>3. 検収</h2><p>納入後10営業日以内に動作確認を行う。</p><p>不具合があった場合は無償で交換する。</p></div>"
        return html_doc(body)
    r1 = [('L2スイッチ', '24ポート 1Gbps PoE+', 12), ('L3スイッチ', '48ポート 10Gbps', 2), ('無線AP', 'Wi-Fi 6 屋内用', 30)]
    r2 = [('L2スイッチ', '24ポート 1Gbps PoE+', 14), ('L3スイッチ', '48ポート 10Gbps 冗長電源', 2), ('無線AP', 'Wi-Fi 6E 屋内用', 30), ('UPS', '1500VA ラックマウント', 4)]
    chrome_pdf(f'{d}/購入仕様書_第1版.pdf', spec('第1版', r1, ['納期：2027年2月末日', '納入場所：第2工場 サーバー室', '設置・初期設定を含む']))
    chrome_pdf(f'{d}/購入仕様書_第2版.pdf', spec('第2版', r2, ['納期：2027年3月15日', '納入場所：第2工場 サーバー室', '設置・初期設定を含む', '既存機器の撤去・廃棄を含む']))
    mkxlsx(f'{d}/相見積比較_A社B社.xlsx', {'比較': [['品名', 'A社単価', 'B社単価', '数量'], ['L2スイッチ', 68000, 65000, 12], ['L3スイッチ', 420000, 455000, 2], ['無線AP', 38000, 36500, 30]]})
    mkxlsx(f'{d}/相見積比較_A社B社_再見積後.xlsx', {'比較': [['品名', 'A社単価', 'B社単価', '数量'], ['L2スイッチ', 64000, 65000, 14], ['L3スイッチ', 410000, 430000, 2], ['無線AP', 41000, 39800, 30], ['UPS', 120000, 115000, 4]]})
def r05(d):
    steps = ['受入検査の手順', '1. 納品書と現品の品番・数量を照合する', '2. 外観を目視で確認する（キズ・汚れ・変形）', '3. 抜取検査を行う（AQL 1.0）', '4. 合否を検査記録表に記入する', '5. 不合格品は赤札を付け隔離棚へ移す']
    steps2 = ['受入検査の手順', '1. 納品書と現品の品番・数量・ロット番号を照合する', '2. 外観を目視で確認する（キズ・汚れ・変形・錆）', '3. 抜取検査を行う（AQL 0.65）', '4. 合否を検査システムに入力する', '5. 不合格品は赤札を付け隔離棚へ移し、品証課長へ報告する', '6. 月次で不合格率を集計する']
    mkdocx(f'{d}/QP-07_受入検査手順書_Rev3.docx', 'QP-07 受入検査手順書 Rev.3', steps + [('table', [['版', '日付', '内容', '承認'], ['3', '2025/6/1', '様式変更', '品証部長']])])
    mkdocx(f'{d}/QP-07_受入検査手順書_Rev4.docx', 'QP-07 受入検査手順書 Rev.4', steps2 + [('table', [['版', '日付', '内容', '承認'], ['3', '2025/6/1', '様式変更', '品証部長'], ['4', '2026/12/1', 'AQL見直し・システム化', '品証部長']])])
    ck = [['No', '検査項目', '基準', '測定器'], [1, '外径', 'φ20.0±0.05', 'マイクロメータ'], [2, '長さ', '50.0±0.1', 'ノギス'], [3, '硬度', 'HRC 40～45', '硬度計'], [4, '外観', 'キズなきこと', '目視']]
    ck2 = [list(r) for r in ck]; ck2[1][2] = 'φ20.0±0.03'; ck2[3][2] = 'HRC 42～46'; ck2.append([5, '表面粗さ', 'Ra 1.6以下', '粗さ計'])
    mkxlsx(f'{d}/検査チェックシート_旧.xlsx', {'チェックシート': ck}); mkxlsx(f'{d}/検査チェックシート_新.xlsx', {'チェックシート': ck2})
    scan_pdf(f'{d}/検査記録_押印済みスキャン_旧.pdf', [page_image(['## 検査記録表', 'ロット：L-2611-01', '外径：合格', '長さ：合格', '硬度：合格', '判定：合格'], '受入検査記録', stamp='検印')])
    scan_pdf(f'{d}/検査記録_押印済みスキャン_再検査.pdf', [page_image(['## 検査記録表', 'ロット：L-2611-01', '外径：合格', '長さ：不合格（50.15）', '硬度：合格', '判定：不合格'], '受入検査記録', offset=(-4, 6), rot=-0.3, stamp='検印')])
def r06(d):
    dims = {'w': 150, 'h': 90, 'holes': [(25, 25, 9), (125, 25, 9), (25, 65, 9), (125, 65, 9)], 'mat': 'SS400', 'surf': '黒染め'}
    dims2 = dict(dims, h=95, mat='SUS304', surf='なし', holes=[(25, 25, 9), (125, 25, 9), (25, 70, 9), (125, 70, 9)])
    drawing(f'{d}/DWG-2041_RevC.png', 'C', dims)
    drawing(f'{d}/DWG-2041_RevD.png', 'D', dims2, extra='※材質変更 SS400→SUS304')
    drawing(f'{d}/DWG-2041_RevC_客先返却スキャン.jpg', 'C', dims, extra='客先確認済', offset=(-10, 8), rot=-0.4, scan=True, noise=6000, fmt='JPEG')
    ima = drawing(f'{d}/_tmp_c.png', 'C', dims); imb = drawing(f'{d}/_tmp_d.png', 'D', dims2, extra='※材質変更 SS400→SUS304')
    ima.save(P(f'{d}/DWG-2041_RevC.pdf'), resolution=200); imb.save(P(f'{d}/DWG-2041_RevD.pdf'), resolution=200)
    os.remove(P(f'{d}/_tmp_c.png')); os.remove(P(f'{d}/_tmp_d.png'))
    mkxlsx(f'{d}/部品表BOM_RevC.xlsx', {'BOM': [['品番', '品名', '材質', '数量'], ['2041-01', 'ブラケット', 'SS400', 1], ['M8-20', '六角ボルト', 'SCM435', 4], ['W8', '平座金', 'SS400', 4]]})
    mkxlsx(f'{d}/部品表BOM_RevD.xlsx', {'BOM': [['品番', '品名', '材質', '数量'], ['2041-01', 'ブラケット', 'SUS304', 1], ['M8-20', '六角ボルト', 'SUS304', 4], ['W8', '平座金', 'SUS304', 4], ['SW8', 'ばね座金', 'SUS304', 4]]})
def r07(d):
    a = '''import { fetchUser } from "./api";

export async function loadProfile(id) {
\tconst user = await fetchUser(id);
\tif (!user) {
\t\treturn null;
\t}
\treturn {
\t\tname: user.name,
\t\temail: user.email,
\t\tage: user.age,
\t};
}

export function formatName(u) {
\treturn u.last + " " + u.first;
}
'''
    b = '''import { fetchUser } from "./api";
import { logger } from "./logger";

export async function loadProfile(id, { includeEmail = true } = {}) {
    const user = await fetchUser(id);
    if (!user) {
        logger.warn(`user not found: ${id}`);
        return null;
    }
    return {
        name: user.name,
        ...(includeEmail ? { email: user.email } : {}),
        age: user.age ?? null,
    };
}

export function formatName(u) {
    return `${u.last} ${u.first}`;
}
'''
    text(f'{d}/profile.js', a); text(f'{d}/profile_refactored.js', b)
    lines = [f'    def method_{i}(self, x):\n        return x * {i}\n' for i in range(400)]
    big = 'class Calc:\n' + '\n'.join(lines)
    lines2 = list(lines); lines2[57] = '    def method_57(self, x):\n        return x * 57 + 1  # bugfix\n'; lines2.insert(200, '    def method_new(self, x):\n        return -x\n'); del lines2[350]
    text(f'{d}/calc_large.py', big); text(f'{d}/calc_large_patched.py', 'class Calc:\n' + '\n'.join(lines2))
    text(f'{d}/package.json', json.dumps({'name': 'app', 'version': '1.4.2', 'dependencies': {'react': '^18.2.0', 'axios': '^1.6.0'}}, indent=2) + '\n')
    text(f'{d}/package_upgraded.json', json.dumps({'name': 'app', 'version': '1.5.0', 'dependencies': {'react': '^19.0.0', 'axios': '^1.7.2', 'zod': '^3.23.0'}}, indent=2) + '\n')
    text(f'{d}/minified_v1.js', 'var a=1;' + ''.join(f'function f{i}(x){{return x+{i}}}' for i in range(300)) + '\n')
    text(f'{d}/minified_v2.js', 'var a=1;' + ''.join(f'function f{i}(x){{return x+{i if i != 150 else 999}}}' for i in range(300)) + '\n')
def r08(d):
    ini = '[network]\r\nip=192.168.10.21\r\nmask=255.255.255.0\r\ngw=192.168.10.1\r\ndns=192.168.10.5\r\n\r\n[proxy]\r\nserver=proxy.local:8080\r\nbypass=*.local;10.*\r\n\r\n[backup]\r\npath=\\\\nas01\\backup\r\ntime=02:00\r\n'
    ini2 = ini.replace('dns=192.168.10.5', 'dns=192.168.10.5,192.168.10.6').replace('time=02:00', 'time=03:30').replace('bypass=*.local;10.*', 'bypass=*.local;10.*;172.16.*')
    open(P(f'{d}/端末設定_PC001_SJIS_CRLF.ini'), 'wb').write(ini.encode('cp932')); open(P(f'{d}/端末設定_PC002_UTF8_LF.ini'), 'wb').write(ini2.replace('\r\n', '\n').encode('utf-8'))
    log = ''.join(f'2026-11-20 0{h}:{m:02d}:00 INFO  backup job step {h*60+m} ok\n' for h in range(0, 3) for m in range(0, 60, 3))
    log2 = log.replace('step 75 ok', 'step 75 WARN retry').replace('step 120 ok', 'step 120 ERROR timeout')
    text(f'{d}/backup_1119.log', log); text(f'{d}/backup_1120.log', log2)
    for side, mod in (('本番サーバー設定', False), ('検証サーバー設定', True)):
        text(f'{d}/{side}/nginx/nginx.conf', 'worker_processes auto;\nevents { worker_connections 1024; }\nhttp {\n  server { listen 80; server_name app.local; }\n}\n' if not mod else 'worker_processes 4;\nevents { worker_connections 2048; }\nhttp {\n  server { listen 80; server_name app-stg.local; }\n}\n')
        text(f'{d}/{side}/nginx/mime.types', 'types { text/html html; }\n')
        text(f'{d}/{side}/app/settings.ini', '[db]\nhost=db-prod\n' if not mod else '[db]\nhost=db-stg\n')
        text(f'{d}/{side}/app/version.txt', '2.4.0\n')
        if mod: text(f'{d}/{side}/app/debug.ini', 'debug=true\n')
        else: text(f'{d}/{side}/cron/backup.cron', '0 2 * * * /opt/backup.sh\n')
def r09(d):
    text(f'{d}/空ファイル.txt', ''); text(f'{d}/1行だけ_改行なし.txt', 'abc')
    text(f'{d}/BOMあり.txt', 'テスト\n', bom=True); text(f'{d}/BOMなし.txt', 'テスト\n')
    text(f'{d}/改行CRLF.txt', 'a\nb\nc\n', eol='\r\n'); text(f'{d}/改行LF.txt', 'a\nb\nc\n')
    text(f'{d}/超長い1行.txt', 'x' * 20000 + 'Y' + 'x' * 20000 + '\n'); text(f'{d}/超長い1行_1文字違い.txt', 'x' * 20000 + 'Z' + 'x' * 20000 + '\n')
    rows = ['id,name,score,date'] + [f'{i},user{i},{random.randint(0, 100)},2026-11-{(i % 28) + 1:02d}' for i in range(1, 50001)]
    rows2 = list(rows)
    for _ in range(150):
        k = random.randrange(1, len(rows2)); rows2[k] = rows2[k].replace(',user', ',USER')
    del rows2[30000:30020]; rows2.insert(10000, '99999,inserted,0,2026-11-30')
    text(f'{d}/大容量_5万行.csv', '\n'.join(rows) + '\n'); text(f'{d}/大容量_5万行_改変.csv', '\n'.join(rows2) + '\n')
    text(f'{d}/全行入替_A.txt', '\n'.join(f'行{i}' for i in range(2000)) + '\n'); text(f'{d}/全行入替_B.txt', '\n'.join(f'別{i}' for i in range(2000)) + '\n')
    text(f'{d}/空白違い_A.txt', 'if (x == 1) {\n    return  true;\n}\n'); text(f'{d}/空白違い_B.txt', 'if (x==1) {\n\treturn true;   \n}\n\n\n')
    text(f'{d}/全角半角_A.txt', 'ＡＢＣ１２３ ｶﾀｶﾅ\n'); text(f'{d}/全角半角_B.txt', 'ABC123 カタカナ\n')
    text(f'{d}/絵文字_A.txt', '承認👍 済み\n𠮷野家\n'); text(f'{d}/絵文字_B.txt', '承認👌 済み\n吉野家\n')
    open(P(f'{d}/壊れたPDF.pdf'), 'wb').write(b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<<>>\n%%EOF')
    open(P(f'{d}/拡張子偽装_実はPNG.txt'), 'wb').write(open(P('00_共通サンプル（形式別）/13_画像_PNG/図面_RevA.png'), 'rb').read())
    open(P(f'{d}/旧形式Word.doc'), 'wb').write(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + bytes(500))
def r10(d):
    mkpptx(f'{d}/A社向け提案_初稿.pptx', [('クラウド移行のご提案', ['A社 情報システム部 御中', '2026年11月 営業第2課']), ('現状の課題', ['オンプレ機器の保守切れ（2027年3月）', '夜間バッチの遅延']), ('解決策', ['段階的なクラウド移行', 'バッチ処理の最適化']), ('費用', ['初期：1,200万円', '月額：80万円']), ('スケジュール', ['2027年1月 着手', '2027年9月 完了'])], notes=['', '保守切れは先方から聞いた情報', '', '値引きはまだ出さない', ''])
    mkpptx(f'{d}/A社向け提案_最終.pptx', [('クラウド移行のご提案', ['A社 情報システム部 御中', '2026年12月 営業第2課']), ('現状の課題', ['オンプレ機器の保守切れ（2027年3月）', '夜間バッチの遅延', 'BCP対策が未整備']), ('解決策', ['段階的なクラウド移行', 'バッチ処理の最適化', '東西リージョンでの冗長化']), ('費用', ['初期：1,050万円（早期契約割引）', '月額：85万円（冗長化含む）']), ('スケジュール', ['2027年1月 着手', '2027年8月 完了']), ('導入実績', ['製造業 12社', '流通業 8社'])], notes=['', '保守切れは先方から聞いた情報', 'BCPは部長の要望で追加', '割引は課長決裁済み', '', ''])
    chrome_pdf(f'{d}/A社向け提案_初稿.pdf', html_doc('<h1>クラウド移行のご提案</h1><p>初期：1,200万円　月額：80万円</p><p>2027年9月 完了予定</p>'))
    chrome_pdf(f'{d}/A社向け提案_最終.pdf', html_doc('<h1>クラウド移行のご提案</h1><p>初期：1,050万円（早期契約割引）　月額：85万円</p><p>2027年8月 完了予定</p>'))
def r11(d):
    names = ['青木 健', '石川 恵', '上田 翔', '江藤 舞', '大野 誠', '加藤 彩', '木村 拓', '工藤 遥']
    hdr = '社員番号,氏名,所属,役職,入社日\n'
    a = hdr + ''.join(f'E{100+i},{n},{["営業部","開発部","総務部"][i % 3]},{["一般","主任","課長"][i % 3]},20{15+i}/04/01\n' for i, n in enumerate(names))
    names2 = list(names); names2[3] = '江藤 舞（旧姓：佐々木）'
    b = hdr + ''.join(f'E{100+i},{n},{["営業部","開発部","総務部"][i % 3] if i != 4 else "人事部"},{["一般","主任","課長"][i % 3] if i != 1 else "係長"},20{15+i}/04/01\n' for i, n in enumerate(names2) if i != 6) + 'E108,佐藤 葵,開発部,一般,2026/10/01\n'
    text(f'{d}/社員名簿_10月_SJIS.csv', a, 'shift_jis', '\r\n'); text(f'{d}/社員名簿_11月_SJIS.csv', b, 'shift_jis', '\r\n')
    ev = [['評価項目', 'ウェイト', '本人評価', '上司評価', 'コメント'], ['業務成果', '40%', 'B', 'B', '目標どおり'], ['プロセス', '30%', 'A', 'B', ''], ['チームワーク', '20%', 'B', 'A', '後輩指導に貢献'], ['自己啓発', '10%', 'C', 'C', '']]
    ev2 = [list(r) for r in ev]; ev2[1][3] = 'A'; ev2[1][4] = '下期に大型案件を受注'; ev2[4][3] = 'B'; ev2[4][4] = '資格取得'
    mkxlsx(f'{d}/人事評価シート_一次評価.xlsx', {'評価': ev}); mkxlsx(f'{d}/人事評価シート_二次評価後.xlsx', {'評価': ev2})
def r12(d):
    mkpptx(f'{d}/中期経営計画_取締役会資料_案.pptx', [('中期経営計画 2027-2029', ['経営企画部']), ('数値目標', ['売上高 300億円', '営業利益率 8%', 'ROE 10%']), ('重点施策', ['海外売上比率 30%', 'DX投資 年20億円'])])
    mkpptx(f'{d}/中期経営計画_取締役会資料_確定.pptx', [('中期経営計画 2027-2029', ['経営企画部']), ('数値目標', ['売上高 320億円', '営業利益率 8.5%', 'ROE 10%']), ('重点施策', ['海外売上比率 35%', 'DX投資 年25億円', '人的資本投資の拡充'])])
    mkxlsx(f'{d}/予算_部門集計_案.xlsx', {'集計': [['部門', '売上', '営業利益'], ['第1事業部', 12000, 900], ['第2事業部', 9800, 700], ['海外事業部', 8200, 480]]})
    mkxlsx(f'{d}/予算_部門集計_確定.xlsx', {'集計': [['部門', '売上', '営業利益'], ['第1事業部', 12500, 950], ['第2事業部', 9800, 720], ['海外事業部', 9700, 610]]})
def r13(d):
    a = "# Installation Guide / インストールガイド\n\n## 1. 動作環境\n- Windows 10 / 11\n- メモリ 8GB 以上\n\n## 2. インストール手順\n1. `setup.exe` を実行します。\n2. 「次へ」をクリックします。\n3. インストール先を選択します。\n\n> 注意：管理者権限が必要です。\n"
    b = "# Installation Guide / インストールガイド\n\n## 1. 動作環境\n- Windows 11（Windows 10 はサポート終了）\n- メモリ 16GB 以上を推奨\n\n## 2. インストール手順\n1. `setup.exe` を右クリックし「管理者として実行」を選びます。\n2. 「次へ」をクリックします。\n3. インストール先を選択します。\n4. 「完了」をクリックします。\n\n> 注意：インストール中は他のアプリを終了してください。\n"
    text(f'{d}/install_guide_v1.md', a); text(f'{d}/install_guide_v2.md', b)
    ja = ['1. Click "Next".', '「次へ」をクリックします。', '2. Select the destination folder.', 'インストール先フォルダを選択します。', '3. Click "Install".', '「インストール」をクリックします。']
    jb = ['1. Click "Next".', '「次へ」をクリックしてください。', '2. Select the destination folder.', 'インストール先のフォルダーを選択してください。', '3. Click "Install".', '「インストール」をクリックしてください。']
    mkdocx(f'{d}/対訳マニュアル_翻訳初稿.docx', 'User Manual 対訳', ja); mkdocx(f'{d}/対訳マニュアル_校正後.docx', 'User Manual 対訳', jb)
    text(f'{d}/表記ゆれ_原稿.txt', 'サーバへ接続します。\nユーザはプリンタを選択します。\n１０件のデータ\n'); text(f'{d}/表記ゆれ_統一後.txt', 'サーバーへ接続します。\nユーザーはプリンターを選択します。\n10件のデータ\n')
def r14(d):
    text(f'{d}/xss_テスト_A.txt', '<script>alert("xss")</script>\n<img src=x onerror="alert(1)">\n普通の行\n')
    text(f'{d}/xss_テスト_B.txt', '<script>alert("xss2")</script>\n<img src=y onerror="alert(2)">\n普通の行（変更）\n"><svg onload=alert(3)>\n')
    mkdocx(f'{d}/悪意あるWord_A.docx', '<script>alert(1)</script>', ['<img src=x onerror=alert(document.domain)>', '通常の段落'])
    mkdocx(f'{d}/悪意あるWord_B.docx', '<script>alert(2)</script>', ['<iframe src="javascript:alert(1)"></iframe>', '通常の段落（改）'])
    mkxlsx(f'{d}/数式インジェクション_A.xlsx', {'S': [['A', 'B'], ['=HYPERLINK("http://evil.example","click")', '=1+1'], ['@SUM(1)', '+cmd']]})
    mkxlsx(f'{d}/数式インジェクション_B.xlsx', {'S': [['A', 'B'], ['=HYPERLINK("http://evil2.example","click")', '=1+2'], ['@SUM(2)', '-cmd']]})
    a = ['第3条（パスワード）', '8文字以上とし、90日ごとに変更する。', '第4条（持出し）', 'USBメモリの使用は許可制とする。']
    b = ['第3条（パスワード）', '12文字以上とし、多要素認証を必須とする。定期変更は求めない。', '第4条（持出し）', 'USBメモリの使用は原則禁止とする。', '第5条（生成AI）', '社外の生成AIサービスに機密情報を入力してはならない。']
    mkdocx(f'{d}/情報セキュリティ規程_旧.docx', '情報セキュリティ規程', a); mkdocx(f'{d}/情報セキュリティ規程_新.docx', '情報セキュリティ規程', b)
    text(f'{d}/ファイル名に<特殊>&文字.txt', 'a\n')
def r15(d):
    la = ['## 1. 申請要件', '市内に住所を有すること', '世帯の所得が基準額以下であること', '## 2. 支給額', '1世帯あたり 30,000円', '## 3. 申請期限', '令和8年12月25日（金）まで']
    lb = ['## 1. 申請要件', '市内に住所を有すること', '世帯の所得が基準額以下であること', '令和8年10月1日時点で住民登録があること', '## 2. 支給額', '1世帯あたり 50,000円', '## 3. 申請期限', '令和9年1月29日（金）まで']
    scan_pdf(f'{d}/支援金要綱_決裁前_スキャン.pdf', [page_image(la, '生活支援金 交付要綱', stamp='起案'), page_image(['## 4. 問い合わせ', '福祉課 生活支援係', '電話 000-000-0000'], None)])
    scan_pdf(f'{d}/支援金要綱_決裁後_スキャン.pdf', [page_image(lb, '生活支援金 交付要綱', offset=(9, -7), rot=0.5, stamp='決裁'), page_image(['## 4. 問い合わせ', '福祉課 生活支援係', '電話 000-000-0000'], None, offset=(9, -7), rot=0.5)])
    pdf_cid(f'{d}/通知文_様式第1号.pdf', [['様式第1号', '', '令和8年11月20日', '', '　様', '', '生活支援金 交付決定通知書', '', '申請のありました生活支援金について、下記のとおり交付することに決定しました。', '', '交付額　30,000円']], font='HeiseiMin-W3')
    pdf_cid(f'{d}/通知文_様式第1号_改正.pdf', [['様式第1号（第5条関係）', '', '令和8年11月20日', '', '　様', '', '生活支援金 交付決定通知書', '', '申請のありました生活支援金について、下記のとおり交付することに決定しました。', '', '交付額　50,000円', '交付予定日　令和9年2月中旬']], font='HeiseiMin-W3')
    open(P(f'{d}/DocuWorks文書_サンプル.xdw'), 'wb').write(b'XDWF' + bytes(random.randrange(256) for _ in range(3000)))
def r16(d):
    pg = lambda v, acc, n: html_doc(f"""<h1 style='font-family:serif'>Effect of Annealing Temperature on Thin-Film Conductivity</h1><p><i>Draft {v}</i></p>
<h2>Abstract</h2><p>We investigated the conductivity of ITO thin films annealed between 200 and 500 °C. The sheet resistance decreased by {acc} at the optimal temperature (n = {n}).</p>
<h2>1. Introduction</h2><p>Indium tin oxide (ITO) is widely used as a transparent conductor. 酸化インジウムスズは透明電極として広く利用されている。</p>
<h2>2. Methods</h2><p>Films were deposited by RF sputtering. Resistance was measured using a four-point probe. σ = 1/(ρ·t), where t is the thickness.</p>
<div class='pb'><h2>3. Results</h2><table><tr><th>T (°C)</th><th>R<sub>s</sub> (Ω/□)</th></tr><tr><td>200</td><td>48.2</td></tr><tr><td>300</td><td>31.5</td></tr><tr><td>400</td><td>{'22.1' if v == 'v1' else '20.7'}</td></tr><tr><td>500</td><td>25.9</td></tr></table>
<p>Figure 1 shows the dependence of R<sub>s</sub> on temperature.</p></div>""", 'body{font-family:serif}')
    chrome_pdf(f'{d}/paper_draft_v1.pdf', pg('v1', '54%', 12)); chrome_pdf(f'{d}/paper_draft_v2_共著者修正.pdf', pg('v2', '57%', 18))
    text(f'{d}/測定データ_run1.csv', 'T,Rs,err\n200,48.2,0.5\n300,31.5,0.4\n400,22.1,0.3\n500,25.9,0.4\n')
    text(f'{d}/測定データ_run2.csv', 'T,Rs,err\n200,48.0,0.4\n300,31.5,0.4\n400,20.7,0.2\n450,21.3,0.3\n500,25.9,0.4\n')
def r17(d):
    hdr = ['工種', '開始', '終了', '担当', '進捗']
    a = [hdr, ['仮設工事', '2026/11/01', '2026/11/15', '鈴木組', '100%'], ['基礎工事', '2026/11/16', '2026/12/20', '鈴木組', '40%'], ['鉄骨建方', '2027/01/10', '2027/02/10', '山田鉄工', '0%'], ['外装', '2027/02/11', '2027/03/31', '佐藤建装', '0%']]
    b = [list(r) for r in a]; b[2][2] = '2026/12/27'; b[2][4] = '55%'; b[3][1] = '2027/01/15'; b[3][2] = '2027/02/20'; b.insert(4, ['雨天予備', '2027/02/21', '2027/02/25', '-', '0%'])
    mkxlsx(f'{d}/工程表_11月第3週.xlsx', {'工程': a}); mkxlsx(f'{d}/工程表_11月第4週.xlsx', {'工程': b})
    for nm, rev, extra, off, rot in (('施工図_基礎伏図_第2回.jpg', '2', '', (0, 0), 0), ('施工図_基礎伏図_第3回.jpg', '3', '※基礎梁 FG2 幅 400→450', (5, 4), 0.2)):
        W, H = 1754, 1240; im = Image.new('RGB', (W, H), 'white'); dr = ImageDraw.Draw(im); ox, oy = off
        for i in range(6): dr.line([200 + i * 260 + ox, 150 + oy, 200 + i * 260 + ox, 1000 + oy], fill='black', width=3); dr.text((190 + i * 260 + ox, 100 + oy), f'X{i+1}', fill='black', font=font(30))
        for j in range(4): dr.line([200 + ox, 150 + j * 280 + oy, 1500 + ox, 150 + j * 280 + oy], fill='black', width=3); dr.text((130 + ox, 135 + j * 280 + oy), f'Y{j+1}', fill='black', font=font(30))
        for i in range(6):
            for j in range(4):
                s = 50 if not (rev == '3' and i == 2 and j == 1) else 64
                dr.rectangle([200 + i * 260 - s // 2 + ox, 150 + j * 280 - s // 2 + oy, 200 + i * 260 + s // 2 + ox, 150 + j * 280 + s // 2 + oy], outline='black', width=4)
        dr.text((200 + ox, 1060 + oy), f'基礎伏図　第{rev}回　S=1/100', fill='black', font=font(36, True))
        if extra: dr.text((900 + ox, 1060 + oy), extra, fill='black', font=font(32))
        if rot: im = im.rotate(rot, resample=Image.BICUBIC, fillcolor='white')
        im.save(P(f'{d}/{nm}'), quality=88)
    mkdocx(f'{d}/作業日報_1120.docx', '作業日報', ['日付：2026年11月20日　天候：晴れ', '作業内容：基礎配筋 X1～X3通り', '作業員：12名', '安全：KY活動実施、指摘なし'])
    mkdocx(f'{d}/作業日報_1121.docx', '作業日報', ['日付：2026年11月21日　天候：雨のち曇り', '作業内容：基礎配筋 X3～X5通り（雨天のため午後から）', '作業員：10名', '安全：KY活動実施、足元の滑りに注意喚起'])
def r18(d):
    def label(v, dose, warn, side):
        return html_doc(f"""<h1>医療用医薬品添付文書（サンプル・架空）</h1><p>販売名：サンプロキセン錠 100mg（架空の薬剤）</p><p>{v}</p>
<h2>【警告】</h2><p>{warn}</p><h2>【用法・用量】</h2><p>通常、成人には1回{dose}を1日2回、朝夕食後に経口投与する。なお、年齢、症状により適宜増減する。</p>
<h2>【副作用】</h2><table><tr><th>頻度</th><th>症状</th></tr><tr><td>1～5%未満</td><td>悪心、頭痛</td></tr><tr><td>1%未満</td><td>{side}</td></tr></table>
<div class='pb'><h2>【貯法】</h2><p>室温保存</p><h2>【有効期間】</h2><p>3年</p></div>""")
    chrome_pdf(f'{d}/添付文書_第3版.pdf', label('2025年4月改訂（第3版）', '100mg', '本剤の投与により重篤な肝機能障害があらわれることがある。', '発疹、めまい'))
    chrome_pdf(f'{d}/添付文書_第4版.pdf', label('2026年11月改訂（第4版）', '100mg（高齢者は50mg）', '本剤の投与により重篤な肝機能障害があらわれることがあるので、定期的に肝機能検査を行うこと。', '発疹、めまい、光線過敏症'))
    mkdocx(f'{d}/改訂のお知らせ_原稿.docx', '使用上の注意改訂のお知らせ', ['このたび、自主改訂により使用上の注意を改訂しましたのでお知らせします。', ('table', [['項目', '改訂後', '改訂前'], ['警告', '定期的に肝機能検査を行うこと', '（記載なし）'], ['用法・用量', '高齢者は50mg', '（記載なし）']])])
    mkdocx(f'{d}/改訂のお知らせ_薬事チェック後.docx', '使用上の注意改訂のお知らせ', ['このたび、自主改訂により「使用上の注意」を改訂いたしましたのでお知らせいたします。', ('table', [['項目', '改訂後', '改訂前'], ['警告', '定期的に肝機能検査を行うこと', '（記載なし）'], ['用法・用量', '高齢者には1回50mgから開始すること', '（記載なし）'], ['副作用', '光線過敏症を追記', '（記載なし）']])])
def r19(d):
    shutil.copy(P('00_共通サンプル（形式別）/07_Word/議事録_初版.docx'), P(f'{d}/議事録_初版.docx'))
    shutil.copy(P('00_共通サンプル（形式別）/07_Word/議事録_修正版.docx'), P(f'{d}/議事録_修正版.docx'))
    drawing(f'{d}/画面デザイン_案A.png', 'A', {'w': 100, 'h': 60, 'holes': [(20, 20, 6)]}, size=(1200, 800))
    drawing(f'{d}/画面デザイン_案B.png', 'B', {'w': 110, 'h': 60, 'holes': [(20, 20, 6), (90, 20, 6)]}, size=(1200, 800))
    text(f'{d}/ラベル文言_旧.txt', 'ログイン\nパスワードを忘れた方\n送信\nキャンセル\n'); text(f'{d}/ラベル文言_新.txt', 'サインイン\nパスワードをお忘れの方はこちら\n送信する\nキャンセル\n')
def r20(d):
    mkdocx(f'{d}/送別会のお知らせ_下書き.docx', '送別会のお知らせ', ['日時：12月18日（金）18時30分～', '場所：居酒屋さくら（駅前）', '会費：4,000円', '参加の方は12月11日までに田中までご連絡ください。'])
    mkdocx(f'{d}/送別会のお知らせ_課長修正.docx', '送別会のお知らせ', ['日時：12月18日（金）19時00分～', '場所：居酒屋さくら（駅前店）2階座敷', '会費：4,500円（当日集金）', '参加の方は12月10日までに田中（内線215）までご連絡ください。'])
    text(f'{d}/電話メモ_1.txt', '11/20 10:15\nABC商事 木下様より\n見積の件で折り返し希望\n電話番号 03-1234-5678\n', 'shift_jis', '\r\n')
    text(f'{d}/電話メモ_2.txt', '11/20 10:15\nABC商事 木下様より\n見積の件で至急折り返し希望（14時まで）\n電話番号 03-1234-5679\n', 'shift_jis', '\r\n')
    chrome_pdf(f'{d}/出張申請書_提出版.pdf', html_doc('<h1>出張申請書</h1><table><tr><th>出張先</th><td>大阪支店</td></tr><tr><th>期間</th><td>12月3日～12月4日</td></tr><tr><th>交通費</th><td>29,000円</td></tr><tr><th>宿泊費</th><td>9,800円</td></tr></table>'))
    chrome_pdf(f'{d}/出張申請書_差戻し後.pdf', html_doc('<h1>出張申請書</h1><table><tr><th>出張先</th><td>大阪支店</td></tr><tr><th>期間</th><td>12月3日～12月4日</td></tr><tr><th>交通費</th><td>28,340円</td></tr><tr><th>宿泊費</th><td>9,800円（規程上限内）</td></tr></table>'))

SPEC = [
 (1, '契約審査担当', '法務部', '経験12年', '契約書の条項変更を漏れなく正確に把握できるか。先方の修正点の見落としは致命的。Word と PDF が混在する。', r01),
 (2, '規程管理担当', '総務部', '経験8年', '社内規程の新旧対照。条文の追加・削除と、Word と PDF の両方での比較。', r02),
 (3, '経理主任', '経理部', '経験10年', '金額・日付の数字の違いを確実に拾えるか。Excel・請求書PDF・会計ソフトCSV（Shift_JIS）。', r03),
 (4, '調達担当', '購買部', '経験6年', '複数ページの仕様書PDFの版比較と、相見積Excelの比較。', r04),
 (5, '品質保証課長', '品質保証部', '経験18年', 'ISO文書の改訂管理。手順書・チェックシート・押印済みスキャンの比較。監査で説明できるか。', r05),
 (6, '機械設計エンジニア', '設計部', '経験9年', '図面のRev間比較（重ね合わせ）。客先から戻ってきたスキャン図面との位置合わせ。部品表。', r06),
 (7, 'ソフトウェアエンジニア', '開発部', '経験7年', 'ソースコード差分の読みやすさ（WinMerge・git diffとの比較）。インデント変更、大きめのファイル、minifyされたJS。', r07),
 (8, '社内SE（インフラ）', '情報システム部', '経験11年', '設定ファイル（文字コード・改行違い）、ログ、サーバー設定フォルダの比較。WinMergeの代替になるか。', r08),
 (9, 'テストエンジニア', '品質管理部', '経験5年', 'エッジケースと性能。空ファイル・BOM・改行・超長い行・5万行CSV・壊れたPDF・拡張子偽装・旧形式。', r09),
 (10, '営業課長', '営業部', '経験15年', '提案書PowerPointの版比較（スライド追加・金額変更・ノート）。忙しいので直感的に使えるか。', r10),
 (11, '人事労務担当', '人事部', '経験4年', '社員名簿CSV（Shift_JIS）の差分と評価シートExcel。個人情報を扱うので外部送信がないことも重要。', r11),
 (12, '経営企画部長', '経営企画部', '経験22年', '取締役会資料・予算の最終版チェック。管理職として「どこが変わったか」を素早く把握できるか、印刷して配れるか。', r12),
 (13, 'テクニカルライター（翻訳・校正）', 'ドキュメント課', '経験8年', 'マニュアル（Markdown・対訳Word）の校正差分。表記ゆれ、全角半角、語尾だけの細かい変更。', r13),
 (14, '情報セキュリティ担当', 'セキュリティ推進室', '経験9年', 'ツール自体の安全性。悪意あるファイル（XSS・数式インジェクション・特殊ファイル名）、オフライン動作、データの保存先。', r14),
 (15, '文書管理担当（自治体）', '市役所 総務課', '経験14年', 'DocuWorksを日常的に使う立場。スキャンした決裁文書の比較、日付印・付箋、印刷。.xdwの扱い。', r15),
 (16, '研究員', '研究開発センター', '経験6年', '英語論文PDFの共著者修正の確認（英日混在・記号・下付き文字）と測定データCSV。', r16),
 (17, '施工管理者', '建設部 工事課', '経験13年', '工程表Excel、施工図（JPEG、少しずれたスキャン）、作業日報。現場PCで使えるか。', r17),
 (18, '薬事担当', '薬事・品質部', '経験10年', '添付文書PDFの改訂確認。数値（用量）の1文字違いも見逃せない。改訂のお知らせWord。', r18),
 (19, 'UI/UXデザイナー（アクセシビリティ）', 'デザイン部', '経験7年', 'UIの分かりやすさ、色覚多様性への配慮、キーボード操作、狭い画面での表示。画面デザイン画像の比較。', r19),
 (20, '一般事務（新入社員）', '営業事務課', '経験半年', 'ITに詳しくない立場で、説明なしで使えるか。お知らせ文書・電話メモ・申請書PDF。', r20),
]

def main():
    if os.path.exists(ROOT): shutil.rmtree(ROOT)
    common()
    for no, role, dept, yrs, focus, gen in SPEC:
        safe = role.replace('/', '・')
        R(no, safe, dept.replace(' ', '_'), yrs, focus, None, gen)
    async def mk():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path=chrome_path(), args=['--no-sandbox'])
            pg = await b.new_page()
            for path, html in CHROME_PDFS:
                await pg.set_content(html); await pg.pdf(path=path, format='A4')
            await b.close()
    asyncio.run(mk())
    
    print('ok', len(REVIEWERS))

if __name__ == '__main__':
    main()
