#!/usr/bin/env python3
"""4回目の20人レビュー用のテストデータ（担当 b：R06〜R10）。
tools/gen_review4.py から読み込まれる（単体では実行しない）。部品は tools/gen_review3.py のものを使う。
  R06 商社 購買・経理（見積 Excel、請求書 PDF、発注書↔請求書、支払予定 CSV、領収書の再スキャン）
  R07 ゲーム会社 ローカライズ（JSON・CSV・YAML・XLIFF、スクリーンショット、配布フォルダ）
  R08 Web サービス会社 SRE（マニフェストのフォルダ、tfstate、アクセスログ、kubectl diff、混在改行、PEM）
  R09 電機メーカー 組込みソフト（EUC-JP の C ソース、マップ、バイナリ・HEX・S レコード、レジスタ仕様書）
  R10 コンサルティング会社 データアナリスト（12万行 CSV、集計 Excel、ipynb、SQL、グラフ画像、parquet）
正解（key）に書く数は、生成のときに実際の中身から数え直している（assert）。"""
from gen_review3 import *
import csv, base64, hashlib, struct, math, zlib, difflib
from PIL import ImageChops


def _lines_of(path, enc='utf-8'):
    """書き出したファイルを読み直して、行のリストにする（行番号を正解に書くため。先頭が1行目）"""
    return open(P(path), 'rb').read().decode(enc).split('\n')


def _lineno(lines, needle, start=0):
    """needle を含む最初の行の番号（1始まり）。見つからなければ止める"""
    for i in range(start, len(lines)):
        if needle in lines[i]: return i + 1
    raise AssertionError(('not found', needle))


def _wd(n): return '月火水木金土日'[n.weekday()]


# ==========================================================================================
# R06 商社 購買・経理：見積書（Excel。初回と再提出）、請求書（PDF。初回と訂正版）、発注書↔請求書（様式が違う）、
#     支払予定一覧（CSV。負数の書き方が混在）、領収書（同じ1枚を2回スキャン）
# ==========================================================================================
R06_CAT = [
    ('TE-BR-6204ZZ', '深溝玉軸受 6204ZZ（内径20×外径47×幅14）', '個', 480), ('TE-BR-6205ZZ', '深溝玉軸受 6205ZZ（内径25×外径52×幅15）', '個', 560),
    ('TE-BR-6306DD', '深溝玉軸受 6306 両側接触ゴムシール', '個', 1280), ('TE-BU-P205', 'ピロー形軸受ユニット 軸径25', '個', 2450),
    ('TE-BU-F206', '角フランジ形軸受ユニット 軸径30', '個', 2980), ('TE-LB-20', 'リニアブッシュ 軸径20 標準形', '個', 890),
    ('TE-LG-25-640', 'リニアガイド 呼び25 レール長640mm ブロック2個付', '本', 38600), ('TE-BS-2005-500', 'ボールねじ 軸径20 リード5 全長500mm 両端加工済', '本', 46800),
    ('TE-CP-D40', 'カップリング ディスク形 外径40（穴径10×14）', '個', 6850), ('TE-TB-S5M450', 'タイミングベルト S5M 幅15 周長450', '本', 1120),
    ('TE-TP-S5M24', 'タイミングプーリ S5M 24歯 幅15用 A形', '個', 1960), ('TE-VB-A45', 'Vベルト A-45', '本', 640),
    ('TE-CH-RS40', 'ローラチェーン RS40 10フィート', '本', 5400), ('TE-SP-RS40-18', 'スプロケット RS40 18歯 B形', '個', 1750),
    ('TE-OS-304708', 'オイルシール TC 30×47×8', '個', 310), ('TE-OR-P24', 'Oリング P-24 NBR（100個入）', '袋', 1480),
    ('TE-GR-L2-400', 'グリース リチウム系 2号 400gカートリッジ', '本', 720), ('TE-LO-VG68', '潤滑油 ISO VG68 20L缶', '缶', 9800),
    ('TE-AC-T32-30', '薄形エアシリンダ φ32×30st 複動', '個', 5260), ('TE-AC-R25-100', '丸形エアシリンダ φ25×100st 複動', '個', 6120),
    ('TE-SV-5P24', '5ポート電磁弁 DC24V Rc1/4 シングル', '個', 7350), ('TE-FR-03', 'フィルタレギュレータ Rc3/8 圧力計付', '個', 6480),
    ('TE-SC-06-02', 'スピードコントローラ エルボ φ6-R1/4', '個', 820), ('TE-TU-0604', 'ウレタンチューブ φ6×4 20m巻 黒', '巻', 2380),
    ('TE-FJ-06-01', 'ワンタッチ継手 ストレート φ6-R1/8（10個入）', '袋', 2150), ('TE-PS-DR2M', '光電センサ 拡散反射形 NPN ケーブル2m', '個', 5980),
    ('TE-PX-M18-5', '近接センサ M18 検出距離5mm NPN', '個', 4720), ('TE-LS-S11', '安全リミットスイッチ 1NC/1NO ローラレバー', '個', 3860),
    ('TE-RY-2C-D24', 'ミニパワーリレー DC24V 2極 動作表示灯付', '個', 780), ('TE-RS-8P', 'リレーソケット 8ピン DINレール取付', '個', 420),
    ('TE-MC-03-200', '電磁接触器 AC200V 3極 補助1a', '個', 3240), ('TE-TH-0N-4', 'サーマルリレー 整定 2.8〜4.2A', '個', 2680),
    ('TE-BR-2P10', '配線用遮断器 2P 10A', '個', 3120), ('TE-PW-24-120', 'スイッチング電源 DC24V 5A 120W DINレール取付', '台', 8900),
    ('TE-TM-M8', 'ソリッドステートタイマ AC100-240V マルチレンジ', '個', 5340), ('TE-PB-22G', '押ボタンスイッチ φ22 緑 モメンタリ 1a', '個', 1260),
    ('TE-PL-22R', '表示灯 φ22 LED 赤 DC24V', '個', 1180), ('TE-ES-22', '非常停止スイッチ φ22 プッシュロック・ターンリセット', '個', 2940),
    ('TE-TB-15-10', '端子台 15A 10極 カバー付', '個', 690), ('TE-DR-AL1M', 'DINレール アルミ 1m', '本', 540),
    ('TE-WD-3050', '配線ダクト 30×50 2m グレー', '本', 980), ('TE-CB-VCTF-4C', 'ビニルキャブタイヤケーブル 0.75sq×4芯 100m', '巻', 14800),
    ('TE-CB-KIV125', '電気機器用ビニル絶縁電線 1.25sq 黒 300m', '巻', 9600), ('TE-CT-R125', '圧着端子 R1.25-3.5（100個入）', '箱', 620),
    ('TE-BT-M6-20', '六角穴付ボルト M6×20 SUS304（100本入）', '箱', 1850), ('TE-BT-M8-25', '六角穴付ボルト M8×25 SUS304（100本入）', '箱', 3280),
    ('TE-NT-M8', '六角ナット M8 SUS304（200個入）', '箱', 1640), ('TE-WS-M8', '平座金 M8 SUS304（500枚入）', '箱', 1320),
    ('TE-AF-3030-2K', 'アルミフレーム 30×30 L=2000 アルマイト', '本', 2760), ('TE-AB-30L', 'アルミフレーム用ブラケット 30シリーズ（10個入）', '袋', 1980)]


def r06(d):
    rnd = random.Random(4606)
    # ---------------------------------------------------------------- 見積書（Excel。仕入先の様式）
    qsel = {'個': [2, 4, 6, 8, 10, 12, 20, 24, 30, 40], '本': [2, 4, 5, 6, 10, 20]}
    rows0 = []
    for code, name, unit, price in R06_CAT:
        rows0.append([code, name, rnd.choice(qsel.get(unit, [1, 2, 3, 4, 5, 6])), unit, price, rnd.choice(['', '', '', '在庫品', '在庫品', '受注生産 約3週間', 'メーカー取寄せ 約2週間'])])
    assert len(rows0) == 50
    rows0[11][2] = 20; rows0[35][2] = 12      # あとで数量を変える行（No.12 Vベルト、No.36 押ボタン）の初回の数量
    rows1 = [list(r) for r in rows0]
    gone = rows1[28]                           # 初回 No.29 を削除
    rows1[6][4] = 39800; rows1[17][4] = 10400; rows1[41][4] = 15600      # 単価：No.7、No.18、No.42（再提出では No.41）
    rows1[11][2] = 30; rows1[35][2] = 16                                  # 数量：No.12、No.36（再提出では No.35）
    del rows1[28]
    add = [['TE-AF-CAP30', 'アルミフレーム用エンドキャップ 30シリーズ 黒（20個入）', 2, '袋', 1150, '追加ご依頼分'], ['TE-SV-MB6', 'マニホールドベース 6連 5ポート電磁弁用', 2, '個', 9450, '追加ご依頼分']]
    rows1 += [list(a) for a in add]
    assert len(rows1) == 51

    def remarks(n): return (f'1. 納期：ご注文後{n}日以内（受注生産品・メーカー取寄せ品は、明細の備考欄の日数によります）\n2. 受渡場所：貴社第2工場 渡し（運賃は弊社負担。ただし時間指定便・チャーター便を除きます）\n'
                            '3. 有効期限を過ぎた場合、及び数量に変更がある場合は、改めてお見積りいたします。\n4. 単価は消費税を含みません。消費税は合計欄に別途記載しております。\n5. メーカーの価格改定があった場合は、価格を見直しさせていただくことがあります。')

    def quote(path, rows, qno, qdate, expiry, disc, sum_end, nouki, own_from):
        """sum_end：小計の SUM の最後の行（Excel の行番号）。own_from：この番号（0始まり）以降の明細は、共有数式に入れない（あとから足した行）"""
        wb = xlsxwriter.Workbook(P(path)); ws = wb.add_worksheet('御見積書'); ws.set_paper(9); ws.fit_to_pages(1, 0); ws.set_margins(0.5, 0.5, 0.6, 0.6)
        for c, w in enumerate([5, 16, 48, 7, 5, 11, 13, 22]): ws.set_column(c, c, w)
        F = lambda **k: wb.add_format({'font_size': 10, 'valign': 'vcenter', **k})
        f_ttl = F(bold=True, font_size=18, align='center'); f_big = F(bold=True, font_size=13, bottom=1); f_n = F(); f_lbl = F(bold=True, bg_color='#EDEDED', border=1, align='center')
        f_date = F(num_format='[$-411]ggge"年"m"月"d"日"', align='left'); f_h = F(bold=True, bg_color='#D9E1F2', border=1, align='center'); f_c = F(border=1, align='center'); f_t = F(border=1); f_q = F(border=1, num_format='#,##0')
        f_y = F(border=1, num_format='"¥"#,##0;[Red]"▲¥"#,##0'); f_yb = F(border=1, bold=True, num_format='"¥"#,##0;[Red]"▲¥"#,##0'); f_amt = F(bold=True, font_size=16, num_format='"¥"#,##0"－"', border=2, align='center'); f_rm = F(text_wrap=True, valign='top', border=1, font_size=9)
        ws.merge_range('A1:H1', '御　見　積　書', f_ttl); ws.set_row(0, 30)
        ws.write('G2', '見積番号', f_n); ws.write('H2', qno, f_n); ws.write('G3', '見積日', f_n); ws.write_datetime('H3', qdate, f_date)
        ws.merge_range('A4:D4', '湊川商事株式会社　御中', f_big); ws.merge_range('F4:H4', '東栄機工株式会社', F(bold=True, font_size=12)); ws.set_row(3, 22)
        ws.merge_range('A5:D5', '購買部　ご担当　三好 様', f_n); ws.merge_range('F5:H5', '〒532-0003 大阪市淀川区宮原6丁目14番8号 東栄ビル', f_n)
        ws.merge_range('F6:H6', 'TEL 06-5555-0142　FAX 06-5555-0143', f_n); ws.merge_range('F7:H7', '登録番号 T8120001077415', f_n); ws.merge_range('F8:H8', '担当：営業2課　樋口 雅之　（印）', f_n)
        for r, (a, b) in enumerate([('件名', '第2工場 搬送ライン更新用 機械・制御部品一式'), ('納入場所', '貴社 第2工場（兵庫県尼崎市）'), ('支払条件', '月末締め 翌月末 銀行振込'), ('有効期限', expiry)]):
            ws.write(6 + r, 0, a, f_lbl); ws.merge_range(6 + r, 1, 6 + r, 3, b, f_t)
        n = len(rows); first = 16; last = first + n - 1; r_sub = last + 1; r_dis = last + 2; r_tax = last + 3; r_tot = last + 4      # いずれも Excel の行番号
        sub = sum(q * p for _, _, q, _, p, _ in rows[:sum_end - first + 1]); dis = -(sub * disc // 100); tax = (sub + dis) // 10; tot = sub + dis + tax
        assert math.floor(sub * (disc / 100)) == -dis and math.floor((sub + dis) * 0.1) == tax        # Excel の ROUNDDOWN と同じ値になること
        ws.merge_range('A12:B12', '御見積金額（税込）', f_lbl); ws.merge_range('C12:E12', '', f_amt); ws.write_formula('C12', f'=G{r_tot}', f_amt, tot); ws.set_row(11, 28)
        ws.merge_range('A13:H13', '平素は格別のお引き立てを賜り、厚く御礼申し上げます。下記のとおり御見積申し上げます。', f_n)
        ws.write_row('A15', ['No.', '品番', '品名・仕様', '数量', '単位', '単価', '金額', '備考'], f_h)
        for i, (code, name, q, unit, p, note) in enumerate(rows):
            r = first + i - 1
            ws.write_number(r, 0, i + 1, f_c); ws.write(r, 1, code, f_t); ws.write(r, 2, name, f_t); ws.write_number(r, 3, q, f_q); ws.write(r, 4, unit, f_c); ws.write_number(r, 5, p, f_y)
            ws.write_formula(r, 6, f'=D{r + 1}*F{r + 1}', f_y, q * p); ws.write(r, 7, note, f_t)
        ws.merge_range(r_sub - 1, 4, r_sub - 1, 5, '小計', f_lbl); ws.write_formula(r_sub - 1, 6, f'=SUM(G{first}:G{sum_end})', f_yb, sub)
        ws.merge_range(r_dis - 1, 4, r_dis - 1, 5, f'出精値引（{disc}%）', f_lbl); ws.write_formula(r_dis - 1, 6, f'=-ROUNDDOWN(G{r_sub}*{disc / 100:g},0)', f_y, dis)
        ws.merge_range(r_tax - 1, 4, r_tax - 1, 5, '消費税（10%）', f_lbl); ws.write_formula(r_tax - 1, 6, f'=ROUNDDOWN((G{r_sub}+G{r_dis})*0.1,0)', f_y, tax)
        ws.merge_range(r_tot - 1, 4, r_tot - 1, 5, '合計（税込）', f_lbl); ws.write_formula(r_tot - 1, 6, f'=SUM(G{r_sub}:G{r_tax})', f_yb, tot)
        ws.write(r_tot + 1, 0, '備考', F(bold=True)); ws.merge_range(r_tot + 2, 0, r_tot + 6, 7, remarks(nouki), f_rm)
        for r in range(r_tot + 2, r_tot + 7): ws.set_row(r, 15)
        ws.freeze_panes(15, 0); ws.print_area(0, 0, r_tot + 6, 7); wb.close()
        share_formulas(path, 1, 'G', first, first + own_from - 1)
        return dict(first=first, last=last, r_sub=r_sub, r_dis=r_dis, r_tax=r_tax, r_tot=r_tot, sub=sub, dis=dis, tax=tax, tot=tot, full=sum(q * p for _, _, q, _, p, _ in rows))
    q0n = '御見積書_東栄機工_QT-2611-0482_初回（11月10日受領）.xlsx'; q1n = '御見積書_東栄機工_QT-2611-0482-R1_再提出（11月24日受領）.xlsx'
    A = quote(f'{d}/{q0n}', rows0, 'QT-2611-0482', datetime.datetime(2026, 11, 10), '令和8年12月10日', 3, 65, 30, 50)
    B = quote(f'{d}/{q1n}', rows1, 'QT-2611-0482-R1', datetime.datetime(2026, 11, 24), '令和8年12月24日', 5, 64, 45, 49)
    assert (A['last'], B['last'], A['r_sub'], B['r_sub']) == (65, 66, 66, 67) and A['sub'] == A['full']
    miss = sum(a[2] * a[4] for a in add); assert B['full'] - B['sub'] == miss
    okdis = -(B['full'] * 5 // 100); oktax = (B['full'] + okdis) // 10; oktot = B['full'] + okdis + oktax
    key(d, f'■ 見積書（Excel）「{q0n}」→「{q1n}」。シートは「御見積書」1枚。明細は 16 行目から（初回 50 行＝16〜65 行目、再提出 51 行＝16〜66 行目）',
        f'行の削除 1：初回 No.29（44 行目）「{gone[0]} {gone[1]}」数量 {gone[2]}・単価 ¥{yen(gone[4])}。このため、初回 No.30〜50 は、再提出で No. が1つずつ繰り上がる（No.29〜49。A 列の番号だけが変わる）',
        f'行の追加 2：再提出の末尾に No.50（65 行目）「{add[0][0]} {add[0][1]}」{add[0][2]}{add[0][3]}×¥{yen(add[0][4])}＝¥{yen(add[0][2] * add[0][4])}、No.51（66 行目）「{add[1][0]} {add[1][1]}」{add[1][2]}{add[1][3]}×¥{yen(add[1][4])}＝¥{yen(add[1][2] * add[1][4])}。備考はどちらも「追加ご依頼分」',
        f'単価の変更 3：No.7 {rows0[6][0]} ¥38,600→¥39,800（金額 ¥{yen(rows0[6][2] * 38600)}→¥{yen(rows0[6][2] * 39800)}）、No.18 {rows0[17][0]} ¥9,800→¥10,400（金額 ¥{yen(rows0[17][2] * 9800)}→¥{yen(rows0[17][2] * 10400)}）、初回 No.42＝再提出 No.41 {rows0[41][0]} ¥14,800→¥15,600（金額 ¥{yen(rows0[41][2] * 14800)}→¥{yen(rows0[41][2] * 15600)}）',
        f'数量の変更 2：No.12 {rows0[11][0]} 20→30（金額 ¥{yen(20 * rows0[11][4])}→¥{yen(30 * rows0[11][4])}）、初回 No.36＝再提出 No.35 {rows0[35][0]} 12→16（金額 ¥{yen(12 * rows0[35][4])}→¥{yen(16 * rows0[35][4])}）',
        '値引率：「出精値引（3%）」→「出精値引（5%）」。式は =-ROUNDDOWN(G66*0.03,0) → =-ROUNDDOWN(G67*0.05,0)（参照の行が1つずれたうえで、率が 0.03→0.05）',
        f'【仕込んだ誤り】小計の式の範囲：初回 =SUM(G16:G65) → 再提出 =SUM(G16:G64)。再提出の明細は 16〜66 行目なので、末尾に足した2行（No.50・No.51、計 ¥{yen(miss)}）が小計に入っていない。'
        f'ファイルに入っている再提出の値は、小計 ¥{yen(B["sub"])}・値引 ▲¥{yen(-B["dis"])}・消費税 ¥{yen(B["tax"])}・合計 ¥{yen(B["tot"])}。2行を入れた正しい値は、小計 ¥{yen(B["full"])}・値引 ▲¥{yen(-okdis)}・消費税 ¥{yen(oktax)}・合計 ¥{yen(oktot)}（合計で ¥{yen(oktot - B["tot"])} の差）',
        f'初回の値：小計 ¥{yen(A["sub"])}・値引 ▲¥{yen(-A["dis"])}・消費税 ¥{yen(A["tax"])}・合計 ¥{yen(A["tot"])}。「御見積金額（税込）」（C12。結合セル、式 =G69 → =G70）も同じ合計の値に変わる',
        '消費税 =ROUNDDOWN((G66+G67)*0.1,0) → =ROUNDDOWN((G67+G68)*0.1,0)、合計 =SUM(G66:G68) → =SUM(G67:G69) は、行が1つ下がっただけ（中身の変更ではない）。明細の金額は「数量×単価」の式（共有数式。再提出の末尾2行だけは個別の式）',
        '備考欄（明細の下の結合セル。5項目を改行で区切った1つのセル）：1項目の「納期：ご注文後30日以内」→「ご注文後45日以内」。ほかの4項目は同じ',
        '日付など：見積番号 QT-2611-0482 → QT-2611-0482-R1（H2）、見積日 H3 は日付の値で表示形式が和暦（令和8年11月10日 → 令和8年11月24日。西暦では 2026/11/10 → 2026/11/24）、有効期限（文字のセル）令和8年12月10日 → 令和8年12月24日',
        '表示形式：金額は ¥#,##0（負は赤字の ▲¥）、御見積金額は「¥1,234,567－」の形。結合セルは表題・宛名・発行者・件名など・御見積金額・小計などの見出し・備考')

    # ---------------------------------------------------------------- 請求書（PDF。初回と訂正版。同じレイアウト）
    inv_items = [('11/02', 'D-118204', 'コピー用紙 A4 高白色 500枚×10冊', 20, '箱', 3480, 10), ('11/02', 'D-118204', 'コピー用紙 A3 高白色 500枚×5冊', 4, '箱', 3960, 10), ('11/02', 'D-118204', 'トナーカートリッジ 複合機用 ブラック（汎用品）', 3, '本', 12800, 10),
                 ('11/02', 'D-118204', 'トナーカートリッジ 複合機用 カラー3色セット（汎用品）', 1, '組', 36400, 10), ('11/05', 'D-118377', 'フラットファイル A4縦 青 10冊入', 15, 'パック', 420, 10), ('11/05', 'D-118377', 'クリアホルダー A4 透明 100枚入', 6, '箱', 1180, 10),
                 ('11/05', 'D-118377', '付箋 75×75mm 黄 10冊入', 12, 'パック', 680, 10), ('11/05', 'D-118377', '油性ボールペン 0.7mm 黒 10本入', 10, '箱', 760, 10), ('11/09', 'D-118652', 'ミネラルウォーター 500ml×24本', 12, 'ケース', 1680, 8),
                 ('11/09', 'D-118652', '緑茶 ペットボトル 525ml×24本', 10, 'ケース', 2160, 8), ('11/09', 'D-118652', 'ドリップコーヒー 個包装 100袋入', 4, '箱', 2980, 8), ('11/09', 'D-118652', '紙コップ 205ml 100個入', 20, '袋', 298, 10),
                 ('11/12', 'D-118930', '養生テープ 50mm×25m 緑 30巻入', 3, '箱', 6900, 10), ('11/12', 'D-118930', '梱包用OPPテープ 48mm×100m 50巻入', 2, '箱', 5400, 10), ('11/12', 'D-118930', '段ボール箱 120サイズ 20枚入', 8, '束', 3260, 10),
                 ('11/12', 'D-118930', 'エアー緩衝材 1200mm×42m', 5, '巻', 1980, 10), ('11/16', 'D-119215', '乾電池 単3形 アルカリ 40本入', 6, 'パック', 1580, 10), ('11/16', 'D-119215', 'ラベルシール A4 24面 100シート', 4, '箱', 3380, 10),
                 ('11/16', 'D-119215', 'ホワイトボードマーカー 4色セット', 10, '組', 520, 10), ('11/19', 'D-119480', 'スティックシュガー 3g×500本', 2, '箱', 940, 8), ('11/19', 'D-119480', '来客用 個包装菓子 詰合せ 60個入', 3, '箱', 2480, 8),
                 ('11/19', 'D-119480', 'ハンドソープ 詰替用 4L', 4, '本', 1860, 10), ('11/19', 'D-119480', 'トイレットペーパー ダブル 96ロール', 3, 'ケース', 4280, 10), ('11/19', 'D-119480', '配送料（小口・別送分）', 1, '式', 1100, 10)]

    def invoice(rev):
        items = [list(x) for x in inv_items]
        if rev: items[2][5] = 11800                 # 3行目の単価を訂正
        s10 = sum(q * p for _, _, _, q, _, p, r in items if r == 10); s8 = sum(q * p for _, _, _, q, _, p, r in items if r == 8); t10 = s10 // 10; t8 = s8 * 8 // 100; tot = s10 + s8 + t10 + t8
        reg = 'T5120001134306' if rev else 'T5120001184306'; acc = '3047857' if rev else '3041857'; due = datetime.date(2026, 12, 31)
        trs = ''.join(f'<tr><td class="c">{i + 1}</td><td class="c">{dt}</td><td class="c">{slip}</td><td>{esc(nm)}{" ※" if r == 8 else ""}</td><td class="r">{q}</td><td class="c">{u}</td><td class="r">{yen(p)}</td><td class="r">{yen(q * p)}</td></tr>' for i, (dt, slip, nm, q, u, p, r) in enumerate(items))
        notes = ['・振込手数料は、貴社にてご負担くださいますようお願いいたします。', '・※印は軽減税率（8%）の対象品目です。'] + (['・本書は、2026年11月20日付の請求書（請求番号 H26-11-04417）を訂正し、2026年11月27日に再発行したものです。先にお送りした請求書は破棄してください。'] if rev else [])
        body = ('<div class="wrap">' + ('<div class="rev">訂正版</div>' if rev else '') + '<h1>請　求　書</h1>'
                '<div class="top"><div class="to"><div class="nm">湊川商事株式会社　御中</div><div>購買部　御担当者様</div><div class="msg">毎度ありがとうございます。下記のとおりご請求申し上げます。</div>'
                f'<table class="amt"><tr><th>ご請求金額（税込）</th><td>¥{yen(tot)}－</td></tr></table><div>お支払期限：{due.year}年{due.month}月{due.day}日（{_wd(due)}）</div><div>対象期間：2026年11月1日〜11月20日 納品分</div></div>'
                '<div class="from"><table class="no"><tr><th>請求番号</th><td>H26-11-04417</td></tr><tr><th>発行日</th><td>2026年11月20日</td></tr><tr><th>お客様コード</th><td>C-203381</td></tr></table>'
                f'<div class="co">北斗オフィスサプライ株式会社</div><div>〒541-0056 大阪市中央区久太郎町2丁目7番15号</div><div>TEL 06-5555-0177　FAX 06-5555-0178</div><div>登録番号　{reg}</div><div class="seal">北斗オフィス<br>サプライ之印</div></div></div>'
                f'<table class="dt"><tr><th style="width:5%">No.</th><th style="width:8%">納品日</th><th style="width:11%">伝票番号</th><th>品名</th><th style="width:6%">数量</th><th style="width:8%">単位</th><th style="width:9%">単価</th><th style="width:10%">金額</th></tr>{trs}</table>'
                f'<table class="sm"><tr><th>10%対象 計（税抜）</th><td>{yen(s10)}</td><th>消費税（10%）</th><td>{yen(t10)}</td></tr><tr><th>8%対象 計（税抜）※</th><td>{yen(s8)}</td><th>消費税（8%）</th><td>{yen(t8)}</td></tr>'
                f'<tr><th>税抜合計</th><td>{yen(s10 + s8)}</td><th>消費税 計</th><td>{yen(t10 + t8)}</td></tr><tr><th colspan="3" class="tt">合計（税込）</th><td class="tt">¥{yen(tot)}</td></tr></table>'
                f'<div class="bank"><b>お振込先</b>　東都銀行 梅田支店　普通預金　{acc}　口座名義　ホクトオフイスサプライ（カ</div>'
                '<div class="note"><b>備考</b><br>' + '<br>'.join(notes) + '</div></div>')
        css = ('.wrap{position:relative}.rev{position:absolute;top:0;right:0;border:2.5px solid #c8102e;color:#c8102e;font-weight:bold;font-size:15pt;padding:1px 14px;letter-spacing:4px}h1{font-size:20pt;letter-spacing:6px;margin:0 0 10px}'
               '.top{display:flex;justify-content:space-between;margin-bottom:8px}.to{width:54%}.from{width:42%;position:relative;font-size:9pt;line-height:1.55}.nm{font-size:14pt;font-weight:bold;border-bottom:1.5px solid #000;margin-bottom:3px}.msg{margin:8px 0 6px;font-size:9pt}'
               '.amt{width:100%;margin:4px 0 6px}.amt th{width:42%;font-size:10pt;background:#e8e8e8}.amt td{font-size:15pt;font-weight:bold;text-align:right;padding:4px 10px}.no{width:72%;margin:0 0 6px}.no th{width:42%;font-weight:normal;background:#f0f0f0}.no td,.no th{font-size:9pt;padding:1px 6px}'
               '.co{font-size:12pt;font-weight:bold;margin-top:2px}.seal{position:absolute;right:0;top:0;width:19mm;height:19mm;border:1.6px solid #c8102e;color:#c8102e;font-size:7.5pt;line-height:1.3;display:flex;align-items:center;justify-content:center;text-align:center;opacity:.85}'
               '.dt td,.dt th{font-size:8.6pt;padding:1.5px 5px;line-height:1.3;white-space:nowrap}.sm{width:62%;margin-left:38%}.sm th{background:#f0f0f0;font-weight:normal;text-align:left;font-size:9pt}.sm td{text-align:right;font-size:9pt;width:20%}.sm .tt{font-weight:bold;font-size:11pt;text-align:right}'
               '.bank{border:1px solid #333;padding:4px 8px;margin:6px 0;font-size:9.5pt}.note{border:1px solid #333;padding:4px 8px;height:23mm;font-size:8.6pt;line-height:1.55}')
        return page(body, css, serif=False, size='9.5pt'), dict(s10=s10, s8=s8, t10=t10, t8=t8, tot=tot, line3=items[2][3] * items[2][5])
    m = {'top': '14mm', 'bottom': '14mm', 'left': '15mm', 'right': '15mm'}
    h0, I0 = invoice(False); h1, I1 = invoice(True)
    i0n = '請求書_北斗オフィスサプライ_2026年11月分.pdf'; i1n = '請求書_北斗オフィスサプライ_2026年11月分_訂正版.pdf'
    cpdf(f'{d}/{i0n}', h0, margin=m); cpdf(f'{d}/{i1n}', h1, margin=m)
    assert I0['s8'] == I1['s8'] and I0['t8'] == I1['t8']
    key(d, f'■ 請求書（PDF・A4・1ページ・文字あり。ブラウザの印刷で作ったもの）「{i0n}」→「{i1n}」。レイアウトは同じ',
        f'金額の訂正 1か所：明細 No.3「トナーカートリッジ 複合機用 ブラック（汎用品）」の単価 12,800→11,800（数量 3、金額 {yen(I0["line3"])}→{yen(I1["line3"])}）。'
        f'これに伴って、10%対象 計 {yen(I0["s10"])}→{yen(I1["s10"])}、消費税（10%）{yen(I0["t10"])}→{yen(I1["t10"])}、税抜合計 {yen(I0["s10"] + I0["s8"])}→{yen(I1["s10"] + I1["s8"])}、消費税 計 {yen(I0["t10"] + I0["t8"])}→{yen(I1["t10"] + I1["t8"])}、合計（税込）と上の「ご請求金額」¥{yen(I0["tot"])}→¥{yen(I1["tot"])}',
        '振込先の口座番号の1桁：普通預金 3041857 → 3047857（4桁目 1→7）', '登録番号の1桁：T5120001184306 → T5120001134306（10桁目の数字 8→3）',
        '「訂正」の表示の追加：右上に赤枠の「訂正版」、備考欄に3行目「・本書は、2026年11月20日付の請求書（請求番号 H26-11-04417）を訂正し、2026年11月27日に再発行したものです。…」を追加（備考欄の枠の大きさは同じ）',
        f'変わっていないもの：請求番号・発行日・お支払期限・ほかの 23 行の明細・8%対象（計 {yen(I0["s8"])}、税 {yen(I0["t8"])}）・角印')

    # ---------------------------------------------------------------- 発注書（自社の様式）と、それに対する請求書（仕入先の様式。レイアウトが違う）
    po = [('MS-4410-01', 'ベースプレート SS400 t12 300×450 黒染め', 4, '枚', 18600, '11/13'), ('MS-4410-02', 'サイドフレーム A5052 t10 120×600 白アルマイト', 8, '枚', 9400, '11/13'), ('MS-4410-03', 'シャフト S45C φ20×300 研磨 両端キー溝', 12, '本', 6850, '11/13'),
          ('MS-4410-04', 'ローラ STKM φ60×420 ウレタンライニング', 24, '本', 11200, '11/17'), ('MS-4410-05', 'ベアリングホルダ S45C φ62 内径47H7', 24, '個', 3980, '11/17'), ('MS-4410-06', 'スペーサ SUS304 φ30×t5', 40, '個', 620, '11/17'),
          ('MS-4410-07', 'ブラケット SPCC t3.2 曲げ 三価クロメート', 32, '個', 1850, '11/20'), ('MS-4410-08', 'カバー SUS304 t1.5 #400研磨 280×520', 6, '枚', 7600, '11/20'), ('MS-4410-09', 'ガイドレール SS400 FB9×50×1200', 8, '本', 5200, '11/20'),
          ('MS-4410-10', 'テンションボルト SCM435 M12×180 四三酸化鉄皮膜', 16, '本', 1480, '11/20'), ('MS-4410-11', 'モータベース SS400 t9 溶接組立 塗装', 2, '台', 28500, '11/25'), ('MS-4410-12', 'ストッパブロック MCナイロン 40×40×60', 12, '個', 1320, '11/25'),
          ('MS-4410-13', '調整ねじ S45C M16×P1.5 ローレット付', 8, '本', 2240, '11/25'), ('MS-4410-14', '銘板 アルミ t1 エッチング 60×120', 6, '枚', 1750, '11/25')]
    po_sub = sum(q * p for _, _, q, _, p, _ in po); po_tax = po_sub // 10
    po_tbl = ('<table class="it"><tr><th style="width:5%">No.</th><th style="width:13%">当社品番</th><th>品名・規格</th><th style="width:6%">数量</th><th style="width:6%">単位</th><th style="width:10%">単価（円）</th><th style="width:11%">金額（円）</th><th style="width:9%">希望納期</th></tr>'
              + ''.join(f'<tr><td class="c">{i + 1}</td><td class="c">{c_}</td><td>{esc(n)}</td><td class="r">{q}</td><td class="c">{u}</td><td class="r">{yen(p)}</td><td class="r">{yen(q * p)}</td><td class="c">{dl}</td></tr>' for i, (c_, n, q, u, p, dl) in enumerate(po))
              + f'<tr><td colspan="6" class="r">小計（税抜）</td><td class="r">{yen(po_sub)}</td><td></td></tr><tr><td colspan="6" class="r">消費税（10%）</td><td class="r">{yen(po_tax)}</td><td></td></tr><tr><td colspan="6" class="r"><b>合計（税込）</b></td><td class="r"><b>{yen(po_sub + po_tax)}</b></td><td></td></tr></table>')
    body = ('<h1>注　文　書</h1><div class="top"><div class="to"><div class="nm">関西精密工業株式会社　御中</div><div>営業部　御担当者様</div><p style="margin-top:8px">下記のとおり注文いたします。納期・数量に変更がある場合は、事前にご連絡ください。</p></div>'
            '<div class="from"><div>注文番号　PO-2611-0457</div><div>注文日　2026年11月4日</div><div class="co">湊川商事株式会社</div><div>〒660-0892 兵庫県尼崎市東難波町4丁目18番1号</div><div>購買部　三好 奈緒子　TEL 06-5555-0121</div><div>登録番号 T3140001052268</div></div></div>'
            + hb([('table', [['納入場所', '当社 第2工場 資材受入口（平日 9:00〜16:30）', '支払条件', '月末締め 翌月末 銀行振込'], ['案件名', '第2工場 搬送ライン更新（設備番号 CV-207）', '検収条件', '受入検査合格をもって検収とする']], 'nohead'),
                  ('raw', po_tbl),
                  '【特記事項】', '1. 図面は別途送付の最新版（図番 MS-4410 シリーズ、各 Rev.B）によること。', '2. 材料証明書（ミルシート）及び検査成績書を納品時に添付すること。', '3. 分納する場合は、納品書に注文番号と当社品番を記載すること。', '4. 本注文書の受領後、3営業日以内に注文請書を返送すること。'])
            + '<table class="ap"><tr><th>承認</th><th>審査</th><th>起票</th></tr><tr><td>西脇</td><td>岡部</td><td>三好</td></tr></table>')
    css = ('h1{letter-spacing:8px}.top{display:flex;justify-content:space-between;margin-bottom:8px}.to{width:52%}.from{width:44%;font-size:9.5pt;line-height:1.6}.nm{font-size:14pt;font-weight:bold;border-bottom:1.5px solid #000}.co{font-size:12pt;font-weight:bold;margin-top:4px}'
           '.it td,.it th{line-height:1.45;white-space:nowrap}.ap{width:42mm;margin:10px 0 0 auto}.ap td{height:14mm;text-align:center!important;vertical-align:middle;color:#b3261e;font-weight:bold}.ap th{font-weight:normal}')
    pon = '発注書_PO-2611-0457_関西精密工業宛.pdf'; kin = '請求書_関西精密工業_No.K2611-0871（PO-2611-0457分）.pdf'
    cpdf(f'{d}/{pon}', page(body, css), margin={'top': '16mm', 'bottom': '16mm', 'left': '16mm', 'right': '16mm'}, display_header_footer=True, header_template=hf('湊川商事株式会社 購買部　様式 P-03', ''), footer_template=hf('', '{p} / {n}'))
    # 請求書の側：納品日の順に並ぶ（発注書の No. の順ではない）。数量違い 1、単価違い 1、発注書にない行 1
    deliv = {'MS-4410-01': ('11/13', 'N-52011'), 'MS-4410-02': ('11/13', 'N-52011'), 'MS-4410-03': ('11/16', 'N-52047'), 'MS-4410-04': ('11/24', 'N-52160'), 'MS-4410-05': ('11/17', 'N-52063'), 'MS-4410-06': ('11/17', 'N-52063'), 'MS-4410-07': ('11/20', 'N-52118'),
             'MS-4410-08': ('11/20', 'N-52118'), 'MS-4410-09': ('11/19', 'N-52101'), 'MS-4410-10': ('11/20', 'N-52118'), 'MS-4410-11': ('11/18', 'N-52084'), 'MS-4410-12': ('11/25', 'N-52177'), 'MS-4410-13': ('11/25', 'N-52177'), 'MS-4410-14': ('11/25', 'N-52177')}
    bill = []
    for c, n, q, u, p, _ in po:
        if c == 'MS-4410-06': q = 36               # 発注 40 に対して 36（4個は未納）
        if c == 'MS-4410-07': p = 1950             # 発注単価 1,850 に対して 1,950
        bill.append([deliv[c][0], deliv[c][1], c, n, q, u, p])
    bill.sort(key=lambda x: (x[0], x[1], x[2]))
    bill.append(['11/24', 'N-52160', '―', '運賃（チャーター便・ローラ納入分）', 1, '式', 12000])
    b_sub = sum(x[4] * x[6] for x in bill); b_tax = b_sub // 10
    cv = rl_canvas.Canvas(P(f'{d}/{kin}'), pagesize=A4); W, H = A4
    def T(x, y, s, sz=9, right=False):
        cv.setFont('IPAG', sz); (cv.drawRightString if right else cv.drawString)(x, y, s)
    T(40, H - 50, '御　請　求　書', 20); cv.setLineWidth(1.2); cv.line(40, H - 58, 250, H - 58)
    T(380, H - 44, '請求書番号  K2611-0871', 10); T(380, H - 58, '発 行 日    2026年11月26日', 10); T(380, H - 72, '締    日    2026年11月25日', 10)
    T(40, H - 92, '〒660-0892 兵庫県尼崎市東難波町4丁目18番1号', 9); T(40, H - 110, '湊川商事株式会社　購買部　御中', 13); T(40, H - 128, '貴社注文番号：PO-2611-0457', 10)
    T(300, H - 100, '関西精密工業株式会社', 13); T(300, H - 115, '〒577-0011 大阪府東大阪市荒本北3丁目5番22号', 8.5); T(300, H - 127, 'TEL 06-5555-0163　FAX 06-5555-0164', 8.5); T(300, H - 139, '登録番号 T6122001043781', 8.5)
    cv.setStrokeColorRGB(0.78, 0.1, 0.1); cv.setLineWidth(1.4); cv.rect(512, H - 142, 44, 44); cv.setFillColorRGB(0.78, 0.1, 0.1); T(518, H - 117, '関西精密', 8); T(518, H - 129, '工業之印', 8); cv.setFillColorRGB(0, 0, 0); cv.setStrokeColorRGB(0, 0, 0)
    cv.setLineWidth(1.5); cv.rect(40, H - 178, 250, 30); T(48, H - 168, '今回御請求額（税込）', 10); T(282, H - 170, f'¥{yen(b_sub + b_tax)}', 15, right=True)
    T(40, H - 196, f'お支払期限：2026年12月31日（{_wd(datetime.date(2026, 12, 31))}）　毎度お引き立てを賜り、誠にありがとうございます。', 9)
    cols = [40, 78, 128, 196, 398, 432, 462, 508, 555]; heads = ['納品日', '納品書No.', '貴社品番', '品　名', '数量', '単位', '単価', '金額']; y = H - 222; rh = 17
    cv.setLineWidth(0.8); cv.setFillColorRGB(0.9, 0.9, 0.9); cv.rect(cols[0], y - 5, cols[-1] - cols[0], rh, fill=1); cv.setFillColorRGB(0, 0, 0)
    for j, hd in enumerate(heads): T(cols[j] + 4, y, hd, 8.5)
    for k, (dt, slip, code, nm, q, u, p) in enumerate(bill):
        yy = y - rh * (k + 1); cv.rect(cols[0], yy - 5, cols[-1] - cols[0], rh)
        T(cols[0] + 4, yy, dt, 8.5); T(cols[1] + 3, yy, slip, 8.5); T(cols[2] + 3, yy, code, 8.5); T(cols[3] + 3, yy, nm, 8); T(cols[5] - 4, yy, str(q), 8.5, right=True); T(cols[5] + 6, yy, u, 8.5); T(cols[7] - 4, yy, yen(p), 8.5, right=True); T(cols[8] - 4, yy, yen(q * p), 8.5, right=True)
    yb = y - rh * (len(bill) + 1)
    for x in cols[1:-1]: cv.line(x, y - 5 + rh, x, yb + rh - 5)
    for k, (lab, v) in enumerate([('税抜合計（10%対象）', b_sub), ('消費税（10%）', b_tax), ('御請求額（税込）', b_sub + b_tax)]):
        yy = yb - rh * k - 4; cv.rect(cols[4], yy - 5, cols[-1] - cols[4], rh); T(cols[4] + 4, yy, lab, 8.5); T(cols[8] - 4, yy, yen(v), 9, right=True)
    T(40, yb - 62, '※ MS-4410-06 スペーサは 36個を納入済み。残り 4個は 12月3日 納入予定（次回請求）。', 8.5); T(40, yb - 76, '※ ローラ（MS-4410-04）は、貴社ご指定の時間に合わせてチャーター便で納入しました。', 8.5); T(40, yb - 90, '※ 振込手数料は貴社にてご負担願います。', 8.5)
    cv.setLineWidth(0.8); cv.rect(40, yb - 136, 515, 30); T(48, yb - 118, '【お振込先】', 9); T(48, yb - 130, '浪速信用金庫 東大阪支店　当座預金 0218846　口座名義 カンサイセイミツコウギヨウ（カ', 9)
    T(W / 2 - 10, 30, '1 / 1', 8); cv.showPage(); cv.save()
    key(d, f'■ 発注書「{pon}」（自社の様式・明朝・表は発注の No. 順）と、それに対する請求書「{kin}」（仕入先の様式・ゴシック・表は納品日の順。別のソフトで作った PDF）。レイアウトも並び順も違う。どちらも A4・1ページ・文字あり',
        '品目は 14 件とも対応する（当社品番 MS-4410-01〜14 と品名は同じ文字）。食い違いは次の3つ',
        '① 数量：MS-4410-06 スペーサ　発注 40個（金額 24,800）／請求 36個（金額 22,320）。4個は未納（請求書の注記にあり）', '② 単価：MS-4410-07 ブラケット　発注 1,850（金額 59,200）／請求 1,950（金額 62,400）',
        '③ 発注書にない行：請求書の最後の行「運賃（チャーター便・ローラ納入分）」12,000',
        f'合計：発注書 小計 {yen(po_sub)}・消費税 {yen(po_tax)}・合計 {yen(po_sub + po_tax)}／請求書 税抜合計 {yen(b_sub)}・消費税 {yen(b_tax)}・御請求額 {yen(b_sub + b_tax)}（差 {yen(b_sub + b_tax - po_sub - po_tax)}）',
        '請求書の並び順（納品日順）：01, 02, 03, 05, 06, 11, 09, 07, 08, 10, 04, 12, 13, 14, 運賃。納品日は希望納期と違う行がある（03：11/13→11/16、04：11/17→11/24、09：11/20→11/19、11：11/25→11/18）')
    assert [x[2][-2:] for x in bill[:-1]] == ['01', '02', '03', '05', '06', '11', '09', '07', '08', '10', '04', '12', '13', '14']

    # ---------------------------------------------------------------- 支払予定一覧（CSV・UTF-8 BOM・CRLF。負数の書き方が担当者ごとに違う）
    pre = ['東栄', '北斗', '関西精密', '大和田', '三葉', '光陽', '日進', '富士見', '千代田', '浪速', '播磨', '淡路', '山城', '近江', '紀州', '丹波', '摂津', '若狭', '但馬', '吉野', '明石', '有馬', '生駒', '葛城', '伏見', '宇治', '堅田', '長浜', '彦根', '草津']
    suf = ['機工', '電機', '産業', '商会', '工業', '運輸', '化成', '精機', '金属', '物流', '製作所', '鋼材', '電設', '塗装', '梱包']
    vend = []
    for i in range(64):
        nm = pre[i % len(pre)] + suf[(i * 7 + i // len(pre)) % len(suf)]
        vend.append((f'V{10020 + i * 13}', (f'株式会社{nm}' if i % 3 else f'{nm}株式会社') if i % 11 else f'有限会社{nm}'))
    assert len(set(v[1] for v in vend)) == 64
    staff = [('三好', '-'), ('岡部', '△'), ('柴田', '()')]
    def neg(n, style):
        s = yen(n); return {'-': f'-{s}', '△': f'△{s}', '()': f'({s})'}[style]
    def pval(s):
        s = s.replace(',', '')
        if not s: return 0
        if s.startswith('△') or s.startswith('-'): return -int(s[1:])
        if s.startswith('('): return -int(s[1:-1])
        return int(s)
    recs = []
    for i in range(480):
        v = vend[rnd.randrange(64)]; st = staff[rnd.randrange(3)]; amt = rnd.randrange(12, 3800) * 550; day = rnd.randrange(21, 51)
        dt = datetime.date(2026, 10, 1) + datetime.timedelta(days=day - 1); off = 0
        if rnd.random() < 0.3: off = rnd.choice([330, 550, 880, 1000, 1100, 2200, 3300, 5500, 11000, 12500, 22000, 33000, 55000])
        if off >= amt: off = 0
        recs.append({'code': v[0], 'name': v[1], 'inv': f'{v[0][1:]}-{dt.month:02d}{dt.day:02d}-{1000 + i}', 'date': dt.strftime('%Y/%m/%d'), 'due': '2026/12/10', 'amt': amt, 'off': off, 'style': st[1], 'how': rnd.choice(['振込', '振込', '振込', '振込', 'でんさい', '手形']), 'who': st[0],
                     'memo': rnd.choice(['', '', '', '', '検収済', '検収済', '一部検収', '相殺通知書あり', '値引（数量違い）', '返品分を相殺']) if off else rnd.choice(['', '', '', '検収済', '検収済', '一部検収'])})
    recs.sort(key=lambda r: (r['code'], r['inv']))
    HD = ['支払先コード', '支払先名', '請求書番号', '請求日', '支払期日', '請求金額', '相殺・値引', '差引支払額', '支払方法', '担当', '備考']
    def row(r): return [r['code'], r['name'], r['inv'], r['date'], r['due'], yen(r['amt']), neg(r['off'], r['style']) if r['off'] else '0', yen(r['amt'] - r['off']), r['how'], r['who'], r['memo']]
    def tocsv(rs):
        b = io.StringIO(); w = csv.writer(b, lineterminator='\n'); w.writerow(HD)
        for r in rs: w.writerow(row(r))
        return b.getvalue()
    new = [dict(r) for r in recs]
    withoff = lambda st: [i for i, r in enumerate(recs) if r['off'] and r['style'] == st]
    m_, s_, k_ = withoff('-'), withoff('△'), withoff('()'); nooff = [i for i, r in enumerate(recs) if not r['off']]
    assert len(m_) > 20 and len(s_) > 12 and len(k_) > 20
    pick = lambda lst, ks: [lst[k] for k in ks]
    nota = pick(m_, [1, 6, 11, 15, 19]) + pick(k_, [2, 9, 14])                 # 書き方だけが変わる（金額は同じ）
    for i in nota[:5]: new[i]['style'] = '△'
    for i in nota[5:]: new[i]['style'] = '-'
    real_off = pick(s_, [1, 5, 8, 11])                                        # 相殺額そのものが変わる（書き方は同じ △）
    for i in real_off: new[i]['off'] = recs[i]['off'] + (1100 if recs[i]['off'] + 1100 < recs[i]['amt'] else -110)
    real_amt = pick(nooff, [30, 170])                                         # 請求金額が変わる
    for i in real_amt: new[i]['amt'] = recs[i]['amt'] + 5500
    both = pick(k_, [5, 17])                                                  # 書き方も金額も変わる
    for i in both: new[i]['style'] = '△'; new[i]['off'] = recs[i]['off'] + 300
    memo_i = nooff[77]; new[memo_i]['memo'] = '支払保留（検収未了）'
    dele = sorted(pick(nooff, [50, 210]), reverse=True); dele_inv = [recs[i]['inv'] for i in sorted(dele)]
    assert len(set(nota + real_off + real_amt + both + [memo_i] + dele)) == 8 + 4 + 2 + 2 + 1 + 2
    for i in dele: del new[i]
    adds = [{'code': vend[5][0], 'name': vend[5][1], 'inv': f'{vend[5][0][1:]}-1120-1481', 'date': '2026/11/20', 'due': '2026/12/10', 'amt': 184800, 'off': 0, 'style': '-', 'how': '振込', 'who': '三好', 'memo': '追加計上'},
            {'code': vend[22][0], 'name': vend[22][1], 'inv': f'{vend[22][0][1:]}-1118-1482', 'date': '2026/11/18', 'due': '2026/12/10', 'amt': 96800, 'off': 3300, 'style': '()', 'how': '振込', 'who': '柴田', 'memo': '追加計上・返品分を相殺'},
            {'code': vend[47][0], 'name': vend[47][1], 'inv': f'{vend[47][0][1:]}-1119-1483', 'date': '2026/11/19', 'due': '2026/12/10', 'amt': 412500, 'off': 0, 'style': '-', 'how': 'でんさい', 'who': '岡部', 'memo': '追加計上'}]
    new += adds; new.sort(key=lambda r: (r['code'], r['inv']))
    c0n = '支払予定一覧_2026年12月10日払_11月25日時点.csv'; c1n = '支払予定一覧_2026年12月10日払_11月27日時点.csv'
    text(f'{d}/{c0n}', tocsv(recs), eol='\r\n', bom=True); text(f'{d}/{c1n}', tocsv(new), eol='\r\n', bom=True)
    # 書き出した2つを読み直して、変更の数を数え直す
    rd = lambda n: list(csv.reader(io.StringIO(open(P(f'{d}/{n}'), 'rb').read().decode('utf-8-sig'), newline='')))
    L0, L1 = rd(c0n), rd(c1n); D0 = {r[2]: (i + 1, r) for i, r in enumerate(L0)}; D1 = {r[2]: (i + 1, r) for i, r in enumerate(L1)}
    assert len(L0) == 481 and len(L1) == 482 and len(D0) == 481
    v_nota, v_real, v_both, v_memo = [], [], [], []
    for k, (ln0, a) in D0.items():
        if k not in D1 or a == D1[k][1]: continue
        ln1, b = D1[k]; dc = [j for j in range(11) if a[j] != b[j]]
        if dc == [10]: v_memo.append((k, ln0, ln1, a, b))
        elif dc == [6] and pval(a[6]) == pval(b[6]): v_nota.append((k, ln0, ln1, a, b))
        elif a[6][0] not in '0123456789' and b[6][0] not in '0123456789' and a[6][0] != b[6][0]: assert pval(a[6]) != pval(b[6]); v_both.append((k, ln0, ln1, a, b))
        else: v_real.append((k, ln0, ln1, a, b))
    only0 = sorted(k for k in D0 if k not in D1); only1 = sorted(k for k in D1 if k not in D0)
    assert (len(v_nota), len(v_real), len(v_both), len(v_memo), len(only0), len(only1)) == (8, 6, 2, 1, 2, 3) and only0 == sorted(dele_inv)
    cnt = lambda L, pfx: sum(1 for r in L[1:] if r[6].startswith(pfx))
    fm = lambda t: f'{t[0]}（{t[1]}行目→{t[2]}行目）'
    key(d, f'■ 支払予定一覧（CSV・UTF-8 BOM 付き・CRLF・11列）「{c0n}」（見出し＋480行）→「{c1n}」（見出し＋481行）。並びは支払先コード・請求書番号の順。行番号は見出しを1行目とした番号',
        f'負数の書き方は担当者ごとに違う（三好＝-1,000、岡部＝△1,000、柴田＝(1,000)）。「相殺・値引」列で、11月25日時点は - が {cnt(L0, "-")} 行・△ が {cnt(L0, "△")} 行・( ) が {cnt(L0, "(")} 行、11月27日時点は - が {cnt(L1, "-")} 行・△ が {cnt(L1, "△")} 行・( ) が {cnt(L1, "(")} 行。桁区切りのカンマがある値は引用符で囲まれている',
        '書き方だけが違い、金額は同じ 8 行（文字としては違うが、金額の違いではない）：' + '、'.join(f'{fm(t)} {t[3][6]}→{t[4][6]}' for t in v_nota),
        '本当に金額が違う 6 行：' + '、'.join(f'{fm(t)} ' + '・'.join(f'{HD[j]} {t[3][j]}→{t[4][j]}' for j in (5, 6, 7) if t[3][j] != t[4][j]) for t in v_real),
        '書き方も金額も違う 2 行：' + '、'.join(f'{fm(t)} 相殺・値引 {t[3][6]}→{t[4][6]}・差引支払額 {t[3][7]}→{t[4][7]}' for t in v_both),
        '備考だけが違う 1 行：' + '、'.join(f'{fm(t)} 「{t[3][10]}」→「{t[4][10]}」' for t in v_memo),
        '削除 2 行（25日時点のみ）：' + '、'.join(f'{k}（{D0[k][0]}行目）' for k in only0) + '／追加 3 行（27日時点のみ）：' + '、'.join(f'{k}（{D1[k][0]}行目）' for k in only1))

    # ---------------------------------------------------------------- 領収書（同じ1枚を2回スキャンした JPEG。中身は同じ）
    rc = ('<div class="rc"><div class="hd"><span class="t">領　収　書</span><span class="no">No. 0038127<br>2026年11月18日</span></div><div class="to">湊川商事株式会社　様</div>'
          '<div class="amt">金額　<b>¥48,400－</b></div><div class="tx">但し　2026年11月分 事務所清掃用品代として<br>上記正に領収いたしました。</div>'
          '<div class="bt"><table><tr><th>税抜金額</th><td>¥44,000</td></tr><tr><th>消費税額（10%）</th><td>¥4,400</td></tr><tr><th>お支払方法</th><td>現金</td></tr></table>'
          '<div class="is">有限会社みどり美装<br>〒661-0012 兵庫県尼崎市南塚口町7丁目3番9号<br>TEL 06-5555-0198<br>登録番号 T2140002031954</div></div><div class="st">収入印紙<br><small>（5万円未満 非課税）</small></div></div>')
    css = ('.rc{border:2px solid #1c3f7a;padding:7mm 9mm;position:relative;height:122mm;box-sizing:border-box;color:#10254d;line-height:1.6}.hd{display:flex;justify-content:space-between;align-items:flex-start}.t{font-size:24pt;font-weight:bold;letter-spacing:8px}.no{text-align:right;font-size:10pt}'
           '.to{font-size:15pt;border-bottom:1.5px solid #1c3f7a;width:62%;margin:6mm 0 5mm}.amt{font-size:14pt;background:#e3ebf7;padding:3mm 6mm;width:70%}.amt b{font-size:22pt;margin-left:8mm}.tx{margin:5mm 0 4mm;font-size:11pt}'
           '.bt{display:flex;justify-content:space-between;align-items:flex-end}.bt table{width:44%;margin:0}.bt th{background:#e3ebf7;font-weight:normal}.bt td{text-align:right}.bt td,.bt th{border-color:#1c3f7a;font-size:9.5pt}.is{font-size:9.5pt;line-height:1.6;width:50%}'
           '.st{position:absolute;right:9mm;top:30mm;width:22mm;height:26mm;border:1px dashed #1c3f7a;font-size:8pt;text-align:center;padding-top:7mm;box-sizing:border-box;line-height:1.4}')
    cpdf(f'{d}/_tmp_領収書.pdf', page(rc, css, serif=True, size='10.5pt'), format='A5', landscape=True, margin={'top': '12mm', 'bottom': '12mm', 'left': '12mm', 'right': '12mm'})
    s1n = '領収書_みどり美装_スキャン1回目.jpg'; s2n = '領収書_みどり美装_スキャン2回目（取り直し）.jpg'
    def post():
        src = P(f'{d}/_tmp_領収書.pdf'); im = rasterize(src, dpi=200)[0]; stamp(im, 1445, 800, '美装', r=58)
        st = random.getstate(); random.seed(60606)        # scan_look は共通の乱数を使うので、ここだけ種を決めて、あとで元に戻す
        for nm, rot, off in ((s1n, 0.35, (5, -7)), (s2n, -0.45, (-8, 6))):
            scan_look(im.copy(), rot=rot, offset=off, noise=2500, blur=0.7).save(P(f'{d}/{nm}'), quality=84, dpi=(200, 200))
        random.setstate(st); os.remove(src)
    POST.append(post)
    key(d, f'■ 領収書のスキャン（JPEG・200dpi・A5 横）「{s1n}」と「{s2n}」：同じ1枚の領収書を2回スキャンしたもの。中身の違いは**ない**（金額 ¥48,400、2026年11月18日、No. 0038127、有限会社みどり美装、赤い丸印）',
        '違うのは、傾き（+0.35° と −0.45°）、位置のずれ（右5・上7 画素と、左8・下6 画素）、ごみの点の位置、JPEG の圧縮のにじみだけ。位置を合わせれば「変更箇所なし」になるのが正しい。文字情報はない（画像）ので、テキスト比較の対象ではない')


# <<<r07>>>
# ==========================================================================================
# R07 ゲーム会社 ローカライズ：文言 JSON（3,000行）、多言語 CSV（1,500行）、会話 YAML、XLIFF、スクリーンショット、配布フォルダ（各 約1,200 ファイル）
# ==========================================================================================
R07_PLACES = ['港町リベルタ', '風鳴りの森', '水晶の洞窟', '古城アルメリア', '砂塵の交易路', '霧の湿原', '星見の塔', '沈黙の神殿', '白銀の雪山', '灼熱の火口', '鏡の湖', '忘れられた遺跡', '王都セレスティア']
# 多言語の語（ja, en, zh-Hans, ko, ar, th）
R07_ADJ = [('古びた', 'Old', '古老的', '낡은', 'قديم', 'เก่า'), ('輝く', 'Shining', '闪耀的', '빛나는', 'لامع', 'ส่องแสง'), ('伝説の', 'Legendary', '传说的', '전설의', 'أسطوري', 'ในตำนาน'), ('呪われた', 'Cursed', '被诅咒的', '저주받은', 'ملعون', 'ต้องสาป'),
           ('聖なる', 'Holy', '神圣的', '신성한', 'مقدس', 'ศักดิ์สิทธิ์'), ('鉄の', 'Iron', '铁制', '철제', 'حديدي', 'เหล็ก'), ('銀の', 'Silver', '银制', '은제', 'فضي', 'เงิน'), ('黄金の', 'Golden', '黄金', '황금', 'ذهبي', 'ทองคำ'),
           ('炎の', 'Flame', '火焰', '화염의', 'ناري', 'เพลิง'), ('氷の', 'Frost', '寒冰', '얼음의', 'جليدي', 'น้ำแข็ง'), ('疾風の', 'Gale', '疾风', '질풍의', 'عاصف', 'วายุ'), ('大地の', 'Earth', '大地', '대지의', 'أرضي', 'ปฐพี')]
R07_NOUN = [('剣', 'Sword', '剑', '검', 'سيف', 'ดาบ'), ('盾', 'Shield', '盾', '방패', 'درع', 'โล่'), ('指輪', 'Ring', '戒指', '반지', 'خاتم', 'แหวน'), ('弓', 'Bow', '弓', '활', 'قوس', 'ธนู'), ('槍', 'Spear', '长枪', '창', 'رمح', 'หอก'),
            ('冠', 'Crown', '王冠', '왕관', 'تاج', 'มงกุฎ'), ('鍵', 'Key', '钥匙', '열쇠', 'مفتاح', 'กุญแจ'), ('書', 'Tome', '典籍', '서', 'كتاب', 'คัมภีร์'), ('短剣', 'Dagger', '短剑', '단검', 'خنجر', 'มีดสั้น'), ('靴', 'Boots', '靴子', '장화', 'حذاء', 'รองเท้า'),
            ('手袋', 'Gloves', '手套', '장갑', 'قفاز', 'ถุงมือ'), ('首飾り', 'Necklace', '项链', '목걸이', 'عقد', 'สร้อยคอ'), ('石', 'Stone', '宝石', '돌', 'حجر', 'หิน'), ('灯', 'Lantern', '提灯', '등불', 'مصباح', 'ตะเกียง'), ('外套', 'Cloak', '斗篷', '망토', 'معطف', 'เสื้อคลุม'),
            ('帯', 'Belt', '腰带', '허리띠', 'حزام', 'เข็มขัด'), ('兜', 'Helm', '头盔', '투구', 'خوذة', 'หมวกเกราะ'), ('杖', 'Staff', '法杖', '지팡이', 'عصا', 'คทา'), ('斧', 'Axe', '战斧', '도끼', 'فأس', 'ขวาน'), ('鎧', 'Armor', '铠甲', '갑옷', 'درع صدر', 'เกราะ')]
R07_DESC = [('攻撃力が{0}上がる。', 'Increases attack by {0}.', '攻击力提升{0}。', '공격력이 {0} 증가한다.', 'يزيد الهجوم بمقدار {0}.', 'เพิ่มพลังโจมตี {0}'), ('防御力が{0}上がる。', 'Increases defense by {0}.', '防御力提升{0}。', '방어력이 {0} 증가한다.', 'يزيد الدفاع بمقدار {0}.', 'เพิ่มพลังป้องกัน {0}'),
            ('HPを{0}回復する。', 'Restores {0} HP.', '恢复{0}点HP。', 'HP를 {0} 회복한다.', 'يستعيد {0} من نقاط الصحة.', 'ฟื้นฟู HP {0}'), ('{0}ゴールドで売却できる。', 'Can be sold for {0} gold.', '可以{0}金币出售。', '{0}골드에 판매할 수 있다.', 'يمكن بيعه مقابل {0} ذهب.', 'ขายได้ {0} โกลด์'),
            ('レベル{0}以上で装備できる。', 'Requires level {0}, or higher.', '需要等级{0}以上。', '레벨 {0} 이상 장착 가능.', 'يتطلب المستوى {0} أو أعلى.', 'ต้องการเลเวล {0} ขึ้นไป'), ('素早さが{0}上がる。', 'Increases speed by {0}.', '速度提升{0}。', '속도가 {0} 증가한다.', 'يزيد السرعة بمقدار {0}.', 'เพิ่มความเร็ว {0}')]
R07_NOSELL = ('売却できない。', 'Cannot be sold.', '无法出售。', '판매할 수 없다.', 'لا يمكن بيعه.', 'ขายไม่ได้')
R07_PLACE6 = [('森', 'Forest', '森林', '숲', 'الغابة', 'ป่า'), ('洞窟', 'Cave', '洞穴', '동굴', 'الكهف', 'ถ้ำ'), ('城', 'Castle', '城堡', '성', 'القلعة', 'ปราสาท'), ('村', 'Village', '村庄', '마을', 'القرية', 'หมู่บ้าน'), ('港', 'Harbor', '港口', '항구', 'الميناء', 'ท่าเรือ'), ('砂漠', 'Desert', '沙漠', '사막', 'الصحراء', 'ทะเลทราย'),
              ('塔', 'Tower', '高塔', '탑', 'البرج', 'หอคอย'), ('神殿', 'Temple', '神殿', '신전', 'المعبد', 'วิหาร'), ('雪山', 'Snow Mountain', '雪山', '설산', 'الجبل الثلجي', 'ภูเขาหิมะ'), ('火山', 'Volcano', '火山', '화산', 'البركان', 'ภูเขาไฟ'), ('湖', 'Lake', '湖泊', '호수', 'البحيرة', 'ทะเลสาบ'), ('遺跡', 'Ruins', '遗迹', '유적', 'الأطلال', 'ซากปรักหักพัง')]
R07_CREA = [('スライム', 'Slime', '史莱姆', '슬라임', 'سلايم', 'สไลม์'), ('ゴブリン', 'Goblin', '哥布林', '고블린', 'غوبلن', 'ก็อบลิน'), ('オオカミ', 'Wolf', '狼', '늑대', 'ذئب', 'หมาป่า'), ('ドラゴン', 'Dragon', '龙', '드래곤', 'تنين', 'มังกร'), ('骸骨兵', 'Skeleton', '骷髅兵', '해골병', 'هيكل عظمي', 'โครงกระดูก'),
            ('コウモリ', 'Bat', '蝙蝠', '박쥐', 'خفاش', 'ค้างคาว'), ('クモ', 'Spider', '蜘蛛', '거미', 'عنكبوت', 'แมงมุม'), ('ゴーレム', 'Golem', '魔像', '골렘', 'غولم', 'โกเลม'), ('幽霊', 'Ghost', '幽灵', '유령', 'شبح', 'ผี'), ('騎士', 'Knight', '骑士', '기사', 'فارس', 'อัศวิน')]
R07_ELEM = [('火', 'Fire', '火', '불', 'النار', 'ไฟ'), ('氷', 'Ice', '冰', '얼음', 'الجليد', 'น้ำแข็ง'), ('雷', 'Thunder', '雷', '번개', 'الرعد', 'สายฟ้า'), ('風', 'Wind', '风', '바람', 'الريح', 'ลม'), ('光', 'Light', '光', '빛', 'النور', 'แสง'), ('闇', 'Dark', '暗', '어둠', 'الظلام', 'ความมืด')]
R07_FORM = [('の矢', 'Arrow', '之箭', '의 화살', 'سهم', 'ศร'), ('の壁', 'Wall', '之墙', '의 벽', 'جدار', 'กำแพง'), ('の嵐', 'Storm', '风暴', '의 폭풍', 'عاصفة', 'พายุ'), ('の刃', 'Blade', '之刃', '의 칼날', 'نصل', 'ใบมีด'),
            ('の盾', 'Shield', '之盾', '의 방패', 'درع', 'โล่'), ('の鎖', 'Chain', '之锁', '의 사슬', 'سلسلة', 'โซ่'), ('の槌', 'Hammer', '之锤', '의 망치', 'مطرقة', 'ค้อน'), ('の印', 'Seal', '之印', '의 인장', 'ختم', 'ตรา')]
R07_UI = [('ui.yes', 'はい', 'Yes', '是', '예', 'نعم', 'ใช่'), ('ui.no', 'いいえ', 'No', '否', '아니오', 'لا', 'ไม่'), ('ui.ok', '決定', 'OK', '确定', '확인', 'موافق', 'ตกลง'), ('ui.cancel', 'キャンセル', 'Cancel', '取消', '취소', 'إلغاء', 'ยกเลิก'),
          ('ui.back', 'もどる', 'Back', '返回', '뒤로', 'رجوع', 'กลับ'), ('ui.next', 'つぎへ', 'Next', '下一步', '다음', 'التالي', 'ถัดไป'), ('ui.close', 'とじる', 'Close', '关闭', '닫기', 'إغلاق', 'ปิด'), ('ui.settings', '設定', 'Settings', '设置', '설정', 'الإعدادات', 'การตั้งค่า'),
          ('ui.save', 'セーブ', 'Save', '保存', '저장', 'حفظ', 'บันทึก'), ('ui.load', 'ロード', 'Load', '读取', '불러오기', 'تحميل', 'โหลด'), ('ui.new_game', 'はじめから', 'New Game', '新游戏', '새 게임', 'لعبة جديدة', 'เกมใหม่'), ('ui.continue', 'つづきから', 'Continue', '继续', '이어하기', 'متابعة', 'เล่นต่อ'),
          ('ui.quit', '終了', 'Quit', '退出', '종료', 'خروج', 'ออก'), ('ui.shop', 'ショップ', 'Shop', '商店', '상점', 'المتجر', 'ร้านค้า'), ('ui.items', 'もちもの', 'Items', '物品', '아이템', 'العناصر', 'ไอเทม'), ('ui.skills', 'スキル', 'Skills', '技能', '스킬', 'المهارات', 'สกิล'),
          ('ui.map', 'マップ', 'Map', '地图', '지도', 'الخريطة', 'แผนที่'), ('ui.quests', 'クエスト', 'Quests', '任务', '퀘스트', 'المهام', 'เควส'), ('ui.friends', 'フレンド', 'Friends', '好友', '친구', 'الأصدقاء', 'เพื่อน'), ('ui.mail', 'メール', 'Mail', '邮件', '우편', 'البريد', 'จดหมาย'),
          ('ui.level', 'レベル{0}', 'Level {0}', '等级{0}', '레벨 {0}', 'المستوى {0}', 'เลเวล {0}'), ('ui.gold', '{0}ゴールド', '{0} Gold', '{0}金币', '{0} 골드', '{0} ذهب', '{0} โกลด์'), ('ui.exp', '経験値{0}', '{0} EXP', '经验值{0}', '경험치 {0}', '{0} خبرة', 'ค่าประสบการณ์ {0}'),
          ('ui.loading', '読み込み中…', 'Loading…', '加载中…', '불러오는 중…', 'جارٍ التحميل…', 'กำลังโหลด…'), ('ui.saving', 'セーブ中…', 'Saving…', '保存中…', '저장 중…', 'جارٍ الحفظ…', 'กำลังบันทึก…'),
          ('ui.delete_confirm', '「{0}」を削除しますか？', 'Delete "{0}"?', '要删除“{0}”吗？', '"{0}"을(를) 삭제하시겠습니까?', 'هل تريد حذف "{0}"؟', 'ต้องการลบ "{0}" หรือไม่'),
          ('ui.rename_done', '名前を「{0}」に変更しました。', 'Renamed to "{0}".', '已改名为“{0}”。', '이름을 "{0}"(으)로 변경했습니다.', 'تمت إعادة التسمية إلى "{0}".', 'เปลี่ยนชื่อเป็น "{0}" แล้ว'),
          ('ui.buy_confirm', '{0}を{1}ゴールドで購入しますか？', 'Buy {0} for {1} gold?', '要花{1}金币购买{0}吗？', '{0}을(를) {1}골드에 구매하시겠습니까?', 'هل تريد شراء {0} مقابل {1} ذهب؟', 'ต้องการซื้อ {0} ในราคา {1} โกลด์หรือไม่'),
          ('ui.not_enough', 'ゴールドが足りません。', 'Not enough gold.', '金币不足。', '골드가 부족합니다.', 'لا يوجد ذهب كافٍ.', 'โกลด์ไม่พอ'), ('ui.bag_full', '持ち物がいっぱいです。', 'Your bag is full.', '背包已满。', '가방이 가득 찼습니다.', 'الحقيبة ممتلئة.', 'กระเป๋าเต็มแล้ว'),
          ('ui.connecting', 'サーバーに接続中…', 'Connecting to server…', '正在连接服务器…', '서버에 연결 중…', 'جارٍ الاتصال بالخادم…', 'กำลังเชื่อมต่อเซิร์ฟเวอร์…'), ('ui.conn_error', '通信エラーが発生しました。', 'A connection error occurred.', '发生通信错误。', '통신 오류가 발생했습니다.', 'حدث خطأ في الاتصال.', 'เกิดข้อผิดพลาดในการเชื่อมต่อ'),
          ('ui.retry', 'もう一度お試しください。', 'Please try again.', '请重试。', '다시 시도해 주세요.', 'يرجى المحاولة مرة أخرى.', 'โปรดลองอีกครั้ง'), ('ui.maintenance', 'メンテナンス中です。', 'Under maintenance.', '维护中。', '점검 중입니다.', 'تحت الصيانة.', 'อยู่ระหว่างปิดปรับปรุง'),
          ('ui.welcome', 'いらっしゃい！\n何をお探しで？', 'Welcome!\nWhat are you looking for?', '欢迎光临！\n您在找什么？', '어서 오세요!\n무엇을 찾으세요?', 'أهلًا بك!\nعمّ تبحث؟', 'ยินดีต้อนรับ!\nกำลังหาอะไรอยู่'),
          ('ui.thanks', 'まいどあり！', 'Thanks, come again!', '谢谢惠顾！', '감사합니다!', 'شكرًا لك!', 'ขอบคุณที่อุดหนุน!'), ('ui.language', '表示言語', 'Language', '显示语言', '표시 언어', 'اللغة', 'ภาษา'), ('ui.volume', '音量', 'Volume', '音量', '음량', 'مستوى الصوت', 'ระดับเสียง'),
          ('ui.brightness', '明るさ', 'Brightness', '亮度', '밝기', 'السطوع', 'ความสว่าง'), ('ui.terms', '利用規約', 'Terms of Service', '服务条款', '이용 약관', 'شروط الخدمة', 'ข้อกำหนดการใช้งาน')]
R07_TALK = [['やっと着いたな。', 'ここが港町リベルタか。'], ['潮の匂いがするわね。', '私、海を見るのは初めてなの。'], ['まずは宿を探そう。', '話はそれからだ。'], ['待って。あの船、帆に見覚えのある紋章が……。'], ['気のせいだろう。', '先を急ぐぞ。'], ['おや、旅の方かい。', 'この町は今、少しばかり物騒でね。'],
            ['物騒って、どういうことですか？'], ['夜になると、桟橋に妙な灯りがともるのさ。', '見に行った者は、誰も戻ってこない。'], ['……面白そうじゃないか。'], ['もう、すぐそうやって首を突っ込むんだから。'], ['船長、出航はいつになる？'], ['風が変わるまでは無理だ。', '早くても三日後だな。'],
            ['三日か。', 'それまでに用事を済ませておこう。'], ['老師、この文字が読めますか。'], ['ふむ……これは古い時代の航海日誌じゃな。', '「星の沈む場所に、扉は開く」とある。'], ['星の沈む場所……西の岬のことかしら。'], ['行ってみる価値はありそうだ。'], ['気をつけるんじゃぞ。', '好奇心は、時に身を滅ぼす。'],
            ['分かっています。', '無茶はしません。'], ['あなたの「無茶はしない」は信用できないのよ。'], ['見ろ、灯りだ。', '桟橋の先で揺れている。'], ['静かに。', '誰かいるわ。'], ['……人じゃない。', 'あれは、霧だ。霧が形を取っている。'], ['下がって！', '私が光で照らす！'],
            ['助かった。', 'おかげで正体が見えた。'], ['礼はあとにして。', 'まだ終わっていないわ。'], ['こいつ、斬っても手応えがない！'], ['核を狙うのじゃ。', '胸の奥で光っておるじゃろう。'], ['今だ、カイ！'], ['これで、終わりだ！'], ['……消えた、のか？'], ['ええ。', '霧も晴れていくわ。'],
            ['見事じゃった。', 'じゃが、これは始まりに過ぎん。'], ['どういう意味です、老師。'], ['霧の主は、何者かに呼び出されたのじゃ。', 'この町のどこかに、術者がおる。'], ['術者を探すなら、酒場で聞き込みね。'], ['酒場なら任せろ。', '情報集めは得意なんだ。'], ['飲みたいだけでしょう。'],
            ['いらっしゃい。', '見ない顔だね。'], ['最近、町で怪しい人物を見かけなかったか。'], ['怪しいと言えば、黒い外套の男が倉庫街に出入りしているよ。'], ['倉庫街か。', '行ってみよう。'], ['待ちな。', '情報料は、エール二杯だ。'], ['……やっぱり飲むことになるのね。'],
            ['鍵がかかっている。', '裏口を探そう。'], ['その必要はないわ。', 'この程度の錠なら、すぐ開く。'], ['いつの間にそんな技を覚えたんだ。'], ['旅をしていれば、いろいろあるのよ。']]


def _flat(o, pre=()):
    out = {}
    for k, v in o.items():
        if isinstance(v, dict): out.update(_flat(v, pre + (k,)))
        else: out[pre + (k,)] = v
    return out


def _jdump(obj):
    """json.dumps(indent=2, ensure_ascii=False) と同じ文字を作りながら、値ごとの行番号（1始まり）を記録する"""
    lines = []; where = {}
    def w(o, ind, path, k, last):
        pre = '  ' * ind + (json.dumps(k, ensure_ascii=False) + ': ' if k is not None else '')
        if isinstance(o, dict):
            lines.append(pre + '{'); it = list(o.items()); where[path] = len(lines)
            for i, (kk, v) in enumerate(it): w(v, ind + 1, path + (kk,), kk, i == len(it) - 1)
            lines.append('  ' * ind + '}' + ('' if last else ','))
        else: lines.append(pre + json.dumps(o, ensure_ascii=False) + ('' if last else ',')); where[path] = len(lines)
    w(obj, 0, (), None, True); s = '\n'.join(lines) + '\n'
    assert s == json.dumps(obj, indent=2, ensure_ascii=False) + '\n'
    return s, where


def _ins_after(dct, after, k, v):
    out = {}
    for kk, vv in dct.items():
        out[kk] = vv
        if kk == after: out[k] = v
    assert k in out; dct.clear(); dct.update(out)


def _cp(s): return '+'.join(f'U+{ord(c):04X}' for c in s)


def r07(d):
    rnd = random.Random(4707)
    # ---------------------------------------------------------------- strings_ja.json（旧版と、翻訳会社から戻った新版）
    WD, FT = '〜', '～'      # 波ダッシュ（U+301C）と全角チルダ（U+FF5E）
    ZW = '‍'; FAMILY = '👨' + ZW + '👩' + ZW + '👧' + ZW + '👦'
    def build():
        S = {'_meta': {'project': 'arcadia', 'language': 'ja', 'version': '1.8.0', 'exported': '2026-10-30T18:02:11+09:00'}}
        S['common'] = {'ok': 'OK', 'cancel': 'キャンセル', 'yes': 'はい', 'no': 'いいえ', 'back': 'もどる', 'next': 'つぎへ', 'close': 'とじる', 'loading': 'ロード中…', 'saving': 'セーブ中…', 'save_done': 'セーブしました。', 'no_save': 'セーブデータがありません。',
                       'hp_label': 'ＨＰ', 'mp_label': 'ＭＰ', 'level': 'レベル{0}', 'gold': '{0}ゴールド', 'exp': '経験値{0}', 'new': 'NEW', 'confirm': '確認', 'server_connecting': 'サーバーに接続中…', 'like': '👍 いいね！', 'family_plan': FAMILY + ' ファミリープラン（最大4人）',
                       'day_night': f'昼{WD}夜', 'play_time': 'プレイ時間 {0}:{1}', 'unit_count': '{0}個', 'unit_people': '{0}人', 'on': 'オン', 'off': 'オフ'}
        S['title'] = {'press_start': 'ボタンを押してスタート', 'copyright': '© 2026 Hoshizora Works', 'version': 'Ver {0}', 'legacy_notice': '旧バージョンのセーブデータは引き継げません。', 'new_game': 'はじめから', 'continue': 'つづきから',
                      'region_jp': '🇯🇵 日本', 'region_us': '🇺🇸 アメリカ', 'region_uk': '🇬🇧 イギリス', 'region_fr': '🇫🇷 フランス'}
        S['menu'] = {'continue': 'つづきから', 'new_game': 'はじめから', 'multiplayer': 'マルチプレイ', 'shop': 'ショップ', 'settings': '設定', 'quit': '終了', 'quit_confirm': 'ゲームを終了しますか？', 'old_gallery': 'ギャラリー（旧）', 'gallery': 'ギャラリー',
                     'records': '冒険の記録', 'news': 'お知らせ', 'friends': 'フレンド', 'mail': 'メール（{0}件）', 'present': 'プレゼント'}
        S['settings'] = {
            'graphics': {'quality_low': '低', 'quality_mid': '中', 'quality_high': '高', 'resolution': '解像度', 'fullscreen': 'フルスクリーン', 'vsync': '垂直同期', 'shadow': '影の品質', 'effect': 'エフェクトの量', 'brightness': '明るさ', 'gamma': 'ガンマ補正', 'motion_blur': 'モーションブラー', 'reset': '初期設定に戻す'},
            'audio': {'master': '全体の音量', 'bgm': 'BGM の音量', 'se': '効果音の音量', 'voice': 'ボイスの音量', 'mute': 'ミュート', 'output': '出力先', 'speaker': 'スピーカー', 'headphone': 'ヘッドホン', 'surround': 'サラウンド', 'voice_lang': 'ボイスの言語', 'subtitles': '字幕', 'test': 'テスト再生'},
            'controls': {'vibration': '振動（ＯＮ／ＯＦＦ）', 'sensitivity': 'カメラ感度', 'invert_y': '上下反転', 'invert_x': '左右反転', 'key_config': 'キーコンフィグ', 'dash': 'ダッシュ', 'jump': 'ジャンプ', 'attack': '攻撃', 'guard': 'ガード', 'skill': 'スキル', 'item': 'アイテム', 'map': 'マップ', 'auto_run': 'オートラン', 'reset': '初期設定に戻す'},
            'language': {'text': '表示言語', 'ja': '日本語', 'en': 'English', 'zh': '简体中文', 'ko': '한국어', 'ar': 'العربية', 'th': 'ไทย', 'restart_notice': '言語の変更は再起動後に反映されます。'},
            'account': {'user_name': 'ユーザー名', 'user_id': 'ユーザーID', 'link': 'アカウント連携', 'link_legacy': '旧アカウントの引き継ぎ', 'unlink': '連携を解除', 'delete': 'アカウント削除', 'delete_warning': 'アカウントを削除すると元に戻せません。よく確認して下さい。', 'terms': '利用規約', 'privacy': 'プライバシーポリシー', 'support': 'お問い合わせ'}}
        S['shop'] = {'title': 'ショップ', 'buy': '買う', 'sell': '売る', 'buy_confirm': '{0}を{1}ゴールドで購入しますか？', 'sold': '{0}を売却しました。', 'bought': '{0}を購入しました。', 'not_enough': 'ゴールドが足りません。', 'stock': '在庫：{0}', 'sold_out': '売り切れ',
                     'sale': '<color=#ffcc00>セール中</color> {0}%オフ', 'limited': '期間限定（{0}まで）', 'owned': '所持数：{0}', 'bag_full': '持ち物がいっぱいです。', 'thanks': 'まいどあり！', 'welcome': 'いらっしゃい！何をお探しで？'}
        pre = ['古びた', '輝く', '伝説の', '呪われた', '聖なる', '鉄の', '銀の', '黄金の', '炎の', '氷の', '疾風の', '大地の']; noun = ['剣', '盾', '指輪', '弓', '槍', '冠', '杖', '短剣', '兜', '鎧', '首飾り', '手袋', 'ブーツ', 'マント', '腕輪']
        dt = ['攻撃力が{0}上がる。', '防御力が{0}上がる。<color=#ffcc00>レア</color>', '装備すると素早さが{0}%上がる。', 'HPを{0}回復する。\n戦闘中は使えない。', '<color=#ff0000>呪い</color>：外すには教会で{0}ゴールドが必要。']
        who = ['騎士団長', '大魔導師', '盗賊王', '旅の商人', '名もなき兵士', '王女', '船乗り']
        S['items'] = {f'item_{i + 1:03d}': {'name': pre[i // 15] + noun[i % 15], 'desc': dt[i % 5], 'flavor': f'かつて{R07_PLACES[i % 13]}の{who[i % 7]}が使っていたと伝わる。'} for i in range(180)}
        el = ['火', '氷', '雷', '風', '土', '光', '闇', '水', '毒']; act = ['の矢', 'の壁', 'の嵐', 'の刃', 'の癒し', 'の鎖', 'の槌', 'の盾', 'の息吹', 'の印']
        sd = ['敵単体に{e}属性の{0}ダメージを与える。消費MP：{1}', '敵全体に{e}属性の{0}ダメージを与える。消費MP：{1}', '味方単体に{e}の加護を与え、{0}ターンの間、防御力を上げる。']
        S['skills'] = {f'skill_{i + 1:03d}': {'name': el[i // 10] + act[i % 10], 'desc': sd[i % 3].replace('{e}', el[i // 10])} for i in range(90)}
        qt = [('{p}の調査', '{p}で異変が起きているらしい。様子を見てきてほしい。', '{p}の奥まで進む（推奨レベル：{a}' + WD + '{b}）'), ('{p}の魔物退治', '{p}に魔物が住みついた。{0}体倒してほしい。', '魔物を{0}体倒す（推奨レベル：{a}' + WD + '{b}）'),
              ('{p}への届け物', '依頼人の荷物を{p}まで届けよう。', '荷物を持って{p}へ向かう'), ('{p}の落とし物', '{p}で大切な物を落としてしまった。探してきてほしい。', '{p}で落とし物を見つける'), ('{p}の護衛', '商人を{p}まで無事に送り届けよう。', '商人のHPが0にならないように{p}まで進む'),
              ('{p}の採集', '{p}でしか採れない素材を{0}個集めてほしい。', '素材を{0}個集める（推奨レベル：{a}' + WD + '{b}）'), ('{p}の主', '{p}の奥に強大な魔物がいる。<color=#ff0000>危険</color>な相手だ。', '{p}の主を倒す（推奨レベル：{a}' + WD + '{b}）'),
              ('{p}の噂', '{p}について、町の人から話を聞こう。', '町の人{0}人から話を聞く'), ('{p}の地図', '{p}の地図を完成させよう。', '{p}の全エリアを歩く'), ('{p}の試練', '{p}で己の力を試せ。制限時間は{0}分。', '制限時間内に試練を突破する（推奨レベル：{a}' + WD + '{b}）')]
        S['quests'] = {}
        for i in range(130):
            t = qt[i // 13]; a = 5 + (i * 3) % 60; f = lambda x: x.replace('{p}', R07_PLACES[i % 13]).replace('{a}', str(a)).replace('{b}', str(a + 5))
            S['quests'][f'q_{i + 1:03d}'] = {'title': f(t[0]), 'summary': f(t[1]), 'objective': f(t[2]), 'reward': '{0}ゴールド、経験値{1}'}
        cr = ['スライム', 'ゴブリン', 'オオカミ', 'ドラゴン', '骸骨兵', 'コウモリ', 'クモ', 'ゴーレム', '幽霊', '黒騎士']; rank = ['見習い', '一人前', '達人', '名人', '伝説']; cnt = [10, 50, 100, 500, 1000]
        A = [(f'{c}ハンター（{rank[j]}）', f'{c}を{cnt[j]}体倒した。') for c in cr for j in range(5)] + [(f'{p}の到達者', f'{p}に初めて到達した。') for p in R07_PLACES]
        A += [(f'レベル{n}到達', f'レベル{n}に到達した。') for n in range(10, 101, 10)] + [(f'大富豪 {n}万', f'所持ゴールドが{n}万を超えた。') for n in (1, 5, 10, 50, 100, 500, 1000, 5000)] + [(f'冒険の時間 {n}時間', f'プレイ時間が{n}時間を超えた。') for n in (1, 5, 10, 30, 50, 100, 300, 500)]
        A += [(f'鍛冶の心得 {n}', f'装備を{n}回強化した。') for n in (1, 10, 30, 50, 100, 200, 300, 500)] + [(f'お得意様 {n}', f'ショップで{n}回買い物をした。') for n in (1, 10, 50, 100, 300, 500, 1000, 3000)] + [('はじめの一歩', 'チュートリアルを完了した。'), ('友だちの輪', 'フレンドを10人登録した。'), ('完全制覇', 'すべてのクエストを達成した。'), ('無傷の勝利', 'ダメージを受けずにボスを倒した。'), ('夜ふかし', '午前3時にプレイした。')]
        assert len(A) == 110
        S['achievements'] = {f'a_{i + 1:03d}': {'name': n, 'desc': dsc} for i, (n, dsc) in enumerate(A)}
        eb = ['サーバーとの接続が切れました。', 'セーブデータの読み込みに失敗しました。', 'セーブデータが壊れています。', '通信エラーが発生しました。', 'メンテナンス中です。終了予定：{0}', 'アカウントの認証に失敗しました。', '空き容量が足りません。{0}MB以上の空きが必要です。',
              'このバージョンは古いため、アップデートが必要です。', '不正な操作が検出されました。', 'タイムアウトしました。\nもう一度お試しください。', 'フレンドの上限（{0}人）に達しています。', 'この名前は使用できません。']
        S['errors'] = {f'E{1001 + i}': eb[i % 12] + ('' if i < 12 else f'（詳細コード：{i // 12}-{i % 12}）') for i in range(60)}
        tb = ['左スティックで移動します。', 'Aボタンで決定、\nBボタンでキャンセルできます。', 'Xボタンで攻撃します。連続で押すとコンボになります。', 'Yボタンでスキルを使います。MPを消費します。', 'Rボタンを押している間、ダッシュできます。', '宝箱の前でAボタンを押すと開けられます。',
              'セーブポイントではHPとMPが全回復します。', 'マップはメニューからいつでも確認できます。', '装備を変えると見た目が変わります。', '敵の弱点属性を突くとダメージが増えます。']
        S['tutorial'] = {f'step_{i + 1:02d}': (tb[i % 10] if i < 10 else f'【おさらい{i // 10}】' + tb[i % 10]) for i in range(40)}
        S['events'] = {'summer2026': {'title': '真夏の海賊祭', 'period': f'7月20日{WD}8月17日', 'banner': '🏴‍☠️ 海賊祭 開催中！', 'mission_1': '海賊の宝箱を{0}個開ける', 'mission_2': '限定ボス「大海蛇」を倒す', 'reward': '限定衣装「船長の外套」'},
                       'halloween2026': {'title': '収穫祭の夜', 'period': f'10月16日{WD}11月2日', 'banner': '🎃 収穫祭の夜 開催中！', 'mission_1': 'かぼちゃランタンを{0}個集める', 'mission_2': '限定ボス「案山子の王」を倒す', 'reward': '限定衣装「魔女の帽子」'}}
        return S
    S0 = build(); S1 = build(); CH = []     # CH: (分類, パス, 旧, 新)
    def get(S, path):
        o = S
        for k in path[:-1]: o = o[k]
        return o, path[-1]
    def chg(cat, path, a, b):
        path = tuple(path.split('.')); o, k = get(S1, path); old = o[k]
        assert a in old, (path, a, old); o[k] = old.replace(a, b, 1); assert o[k] != old; CH.append((cat, path, old, o[k]))
    for path, a, b in [('common.ok', 'OK', '決定'), ('common.cancel', 'キャンセル', 'やめる'), ('common.loading', 'ロード中…', '読み込み中…'), ('menu.continue', 'つづきから', '続きから'), ('menu.quit_confirm', 'ゲームを終了しますか？', 'ゲームを終了してタイトルに戻りますか？'),
                       ('shop.buy_confirm', '購入しますか', '買いますか'), ('shop.not_enough', 'ゴールドが足りません。', 'ゴールドが{0}足りません。'), ('items.item_013.desc', '上がる', '上昇する'), ('items.item_027.name', '輝く', 'きらめく'), ('items.item_101.flavor', '伝わる', '言い伝えられている'),
                       ('skills.skill_013.desc', '敵単体', '敵1体'), ('skills.skill_045.name', '土', '大地'), ('quests.q_007.summary', '様子を見てきてほしい', '様子を確かめてきてほしい'), ('quests.q_033.objective', '荷物を持って', '荷物を持ったまま'), ('quests.q_090.reward', '経験値{1}', '経験値{1}、{2}'),
                       ('achievements.a_015.desc', '倒した', '討伐した'), ('errors.E1004', '発生しました。', '発生しました。電波の良い場所でお試しください。'), ('errors.E1020', 'アップデートが必要です', '更新が必要です'), ('tutorial.step_05', '押している間', '押しているあいだ'),
                       ('tutorial.step_18', 'いつでも確認できます', 'いつでも見られます'), ('settings.graphics.quality_high', '高', '高画質'), ('settings.account.delete_warning', '確認して下さい', '確認してください')]: chg('文言', path, a, b)
    chg('制御タグ', 'shop.sold', '{0}', '{O}'); chg('制御タグ', 'items.item_005.desc', '呪い</color>', '呪い')
    chg('エスケープ', 'tutorial.step_02', '\n', '\\n'); chg('エスケープ', 'errors.E1034', '\n', '\\n')
    chg('絵文字', 'title.press_start', 'ボタン', '🎮 ボタン'); chg('絵文字', 'title.region_uk', '🇬🇧', '🇺🇸'); chg('絵文字', 'common.like', '👍', '👍🏽'); chg('絵文字', 'common.family_plan', FAMILY, '👨👩👧👦')
    for path in ('quests.q_001.objective', 'quests.q_014.objective', 'quests.q_080.objective'): chg('波ダッシュ', path, WD, FT)
    chg('長音', 'settings.account.user_name', 'ユーザー', 'ユーザ―'); chg('長音', 'common.server_connecting', 'サーバー', 'サーバ－')
    chg('結合文字', 'common.no_save', 'が', 'が'); chg('結合文字', 'tutorial.step_10', 'が', 'が')
    chg('全角半角・空白', 'common.hp_label', 'ＨＰ', 'HP'); chg('全角半角・空白', 'shop.title', 'ショップ', 'ショップ '); chg('全角半角・空白', 'settings.controls.vibration', 'ＯＮ／ＯＦＦ', 'ON/OFF')
    assert len(CH) == 40 and len(set(c[1] for c in CH)) == 40
    S1['_meta']['version'] = '1.8.1'; S1['_meta']['exported'] = '2026-11-25T14:31:47+09:00'
    dels = ['title.legacy_notice', 'menu.old_gallery', 'settings.account.link_legacy', 'errors.E1007', 'tutorial.step_40']
    for p in dels: o, k = get(S1, tuple(p.split('.'))); del o[k]
    _ins_after(S1['common'], 'close', 'retry', 'もう一度'); _ins_after(S1['shop'], 'sale', 'bundle_label', 'おまとめ {0}個セット'); _ins_after(S1['settings']['graphics'], 'vsync', 'fps_limit', 'フレームレート上限'); S1['errors']['E1061'] = 'イベントの開催期間外です。'
    S1['events']['winter2026'] = {'title': '星降る冬の市', 'period': f'12月18日{WD}1月12日', 'banner': '❄️ 星降る冬の市 開催中！', 'mission_1': '雪の結晶を{0}個集める', 'mission_2': '限定ボス「氷晶の女王」を倒す', 'mission_3': 'フレンドに贈り物を{0}回贈る', 'reward': '限定衣装「星織りのマフラー」', 'notice': '<color=#ffcc00>期間中はショップが{0}%オフ</color>'}
    adds = ['common.retry', 'shop.bundle_label', 'settings.graphics.fps_limit', 'errors.E1061'] + [f'events.winter2026.{k}' for k in S1['events']['winter2026']]
    st = S1['settings']; au = st.pop('audio'); st['audio'] = au       # 「audio」のかたまりを、settings の2番目から最後へ移す（中身は同じ）
    j0n = 'strings_ja_1.8.0.json'; j1n = 'strings_ja_1.8.1_翻訳会社戻り.json'
    t0, w0 = _jdump(S0); t1, w1 = _jdump(S1); text(f'{d}/文言/{j0n}', t0); text(f'{d}/文言/{j1n}', t1)
    F0 = _flat(json.loads(open(P(f'{d}/文言/{j0n}'), encoding='utf-8').read())); F1 = _flat(json.loads(open(P(f'{d}/文言/{j1n}'), encoding='utf-8').read()))
    diff = sorted(k for k in F0 if k in F1 and F0[k] != F1[k]); assert set(diff) == set(c[1] for c in CH) | {('_meta', 'version'), ('_meta', 'exported')}
    assert sorted('.'.join(k) for k in F0 if k not in F1) == sorted(dels) and sorted('.'.join(k) for k in F1 if k not in F0) == sorted(adds) and len(adds) == 12
    assert all(F0[('settings', 'audio', k)] == F1[('settings', 'audio', k)] for k in au) and len(au) == 12
    n0, n1 = t0.count('\n'), t1.count('\n')
    def show(c):
        cat, path, a, b = c; p = '.'.join(path); ln = f'（旧 {w0[path]}行目／新 {w1[path]}行目）'
        if cat in ('波ダッシュ', '長音', '結合文字'):
            i = next(i for i in range(min(len(a), len(b))) if a[i] != b[i]); x, y = (a[i], b[i:i + 2]) if cat == '結合文字' else (a[i], b[i])
            return f'{p}{ln}「{a}」の「{x}」（{_cp(x)}）→「{y}」（{_cp(y)}）'
        if cat == '絵文字': return f'{p}{ln}「{a}」→「{b}」'
        return f'{p}{ln}' + json.dumps(a, ensure_ascii=False) + ' → ' + json.dumps(b, ensure_ascii=False)
    by = lambda cat: '／'.join(show(c) for c in CH if c[0] == cat)
    key(d, f'■ 文言 JSON「文言/{j0n}」（{n0:,}行）→「文言/{j1n}」（{n1:,}行）。UTF-8・LF・字下げ2つ。値（文字列）の数は 旧 {len(F0):,}・新 {len(F1):,}',
        '値の変更は 42 か所：_meta の2つ（version "1.8.0"→"1.8.1"、exported の日時）と、文言 40。文言 40 の内訳は次のとおり（JSON の中の書き方で示す。行番号はファイルの先頭を1行目とした番号）',
        '【ふつうの文言の変更 22】' + by('文言'),
        '【制御タグの破損 2】' + by('制御タグ') + '（{0} の数字のゼロが英大文字のオーに変わっている／<color=#ff0000> の閉じタグ </color> がなくなっている）',
        '【エスケープの違い 2】' + by('エスケープ') + '（旧は JSON の \\n＝改行そのもの、新は \\\\n＝「\\」と「n」の2文字。画面には「\\n」と出てしまう）',
        '【絵文字 4】' + by('絵文字') + '（順に：🎮 を追加／国旗 🇬🇧（U+1F1EC U+1F1E7）→ 🇺🇸（U+1F1FA U+1F1F8）／親指に肌色（U+1F3FD）を追加／家族の絵文字をつなぐ ZWJ（U+200D）3つがなくなり、4人が別々の絵文字になった）',
        '【波ダッシュ → 全角チルダ 3】' + by('波ダッシュ') + '（見た目はほぼ同じ別の文字）',
        '【長音 → 別の横線 2】' + by('長音'), '【結合文字 2】' + by('結合文字') + '（1文字の「が」を「か」＋濁点の2文字で書いたもの。見た目は同じ）',
        '【全角半角・空白 3】' + by('全角半角・空白') + '（shop.title は末尾に半角の空白が1つ付いた）',
        'キーの削除 5（旧のみ）：' + '、'.join(f'{p}（旧 {w0[tuple(p.split("."))]}行目）' for p in dels),
        'キーの追加 12（新のみ）：' + '、'.join(f'{p}（新 {w1[tuple(p.split("."))]}行目）' for p in adds[:4]) + f'、events.winter2026 の8つ（title・period・banner・mission_1〜3・reward・notice。新 {w1[("events", "winter2026")]}〜{w1[("events", "winter2026", "notice")] + 1}行目のかたまり）',
        f'順番の入れ替え：settings.audio のかたまり（12 のキー。中身は1文字も変わっていない）が、settings の2番目（旧 {w0[("settings", "audio")]}〜{w0[("settings", "audio", "test")] + 1}行目）から最後（新 {w1[("settings", "audio")]}〜{w1[("settings", "audio", "test")] + 1}行目）へ移った。'
        '移ったことで、かたまりの終わりの「},」が「}」に、直前の account の終わりの「}」が「},」に変わる（カンマだけ）',
        '変わっていない文字にも、絵文字（🏴‍☠️ 🎃 🇯🇵 🇺🇸 🇫🇷）、波ダッシュ（推奨レベル：5〜10 など多数）、アラビア文字・タイ文字・ハングル・簡体字（settings.language）、制御タグ（{0}、<color=#ffcc00>…</color>）が入っている')

    # ---------------------------------------------------------------- messages.csv（UTF-8 BOM。key, ja, en, zh-Hans, ko, ar, th。1,500行）
    LG = ['ja', 'en', 'zh-Hans', 'ko', 'ar', 'th']
    def nm(a, n): return (a[0] + n[0], f'{a[1]} {n[1]}', a[2] + n[2], f'{a[3]} {n[3]}', f'{n[4]} {a[4]}', n[5] + a[5])
    def fill(t, **kw):       # kw の値は6言語の組。{p} などを言語ごとに差し込む
        out = []
        for li in range(6):
            s = t[li]
            for k, v in kw.items(): s = s.replace('{' + k + '}', v[li] if isinstance(v, tuple) else str(v))
            out.append(s)
        return tuple(out)
    R = [(u[0],) + tuple(u[1:]) for u in R07_UI]; assert len(R) == 40
    for i in range(240):
        a, n = R07_ADJ[i // 20], R07_NOUN[i % 20]; R.append((f'item.{i + 1:03d}.name',) + nm(a, n))
        ds = R07_DESC[i % 6]
        if i % 7 == 0: ds = tuple(x + '\n' + y for x, y in zip(ds, R07_NOSELL))
        R.append((f'item.{i + 1:03d}.desc',) + ds)
    MD = ('{p}に生息する。弱点は{e}。', 'Lives in the {p}. Weak to {e}.', '栖息于{p}。弱点是{e}。', '{p}에 서식한다. 약점은 {e}.', 'يعيش في {p}. نقطة ضعفه {e}.', 'อาศัยอยู่ใน{p} จุดอ่อนคือ{e}')
    for i in range(120):
        R.append((f'monster.{i + 1:03d}.name',) + nm(R07_ADJ[i // 10], R07_CREA[i % 10])); R.append((f'monster.{i + 1:03d}.desc',) + fill(MD, p=R07_PLACE6[i % 12], e=R07_ELEM[i % 6]))
    Q1 = ('{p}の調査', 'Survey of the {p}', '调查{p}', '{p} 조사', 'استكشاف {p}', 'สำรวจ{p}'); Q2 = ('{p}の魔物を{k}体倒す', 'Defeat {k} monsters in the {p}', '在{p}击败{k}只怪物', '{p}에서 몬스터 {k}마리 처치', 'اهزم {k} وحوش في {p}', 'กำจัดมอนสเตอร์ {k} ตัวใน{p}')
    Q3 = ('{p}へ荷物を届ける', 'Deliver a package to the {p}', '把包裹送到{p}', '{p}에 짐을 배달하기', 'أوصل الطرد إلى {p}', 'ส่งพัสดุไปที่{p}'); Q4 = ('{p}で{n}を探す', 'Find the {n} in the {p}', '在{p}寻找{n}', '{p}에서 {n} 찾기', 'ابحث عن {n} في {p}', 'ค้นหา{n}ใน{p}')
    qn_ = 0
    def addq(t, **kw):
        nonlocal qn_; qn_ += 1; R.append((f'quest.{qn_:03d}.title',) + fill(t, **kw))
    for p in R07_PLACE6: addq(Q1, p=p)
    for p in R07_PLACE6:
        for k in (3, 5, 10, 20, 30): addq(Q2, p=p, k=k)
    for p in R07_PLACE6: addq(Q3, p=p)
    for p in R07_PLACE6:
        for n in R07_NOUN: addq(Q4, p=p, n=n)
    SDS = ('{e}属性のダメージを{0}与える。', 'Deals {0} {e} damage.', '造成{0}点{e}属性伤害。', '{e} 속성 피해를 {0} 준다.', 'يسبب {0} ضرر من عنصر {e}.', 'สร้างความเสียหายธาตุ{e} {0}')
    for i in range(48):
        e, f = R07_ELEM[i // 8], R07_FORM[i % 8]
        R.append((f'skill.{i + 1:02d}.name', e[0] + f[0], f'{e[1]} {f[1]}', e[2] + f[2], e[3] + f[3], f'{f[4]} {e[4]}', f[5] + e[5])); R.append((f'skill.{i + 1:02d}.desc',) + fill(SDS, e=e))
    AC = ('{c}を{k}体倒した', '{c} defeated: {k}', '击败了{k}只{c}', '{c} {k}마리 처치', 'هزمت {k} من {c}', 'กำจัด{c} {k} ตัว'); AP = ('{p}に初めて到達した', 'Reached the {p} for the first time', '首次到达{p}', '{p}에 처음 도착했다', 'وصلت إلى {p} لأول مرة', 'มาถึง{p}เป็นครั้งแรก')
    for i, c in enumerate(R07_CREA):
        for j, k in enumerate((10, 50, 100, 500, 1000)): R.append((f'achievement.hunt.{i + 1:02d}_{j + 1}',) + fill(AC, c=c, k=f'{k:,}' if k >= 1000 else k))
    for i, p in enumerate(R07_PLACE6): R.append((f'achievement.reach.{i + 1:02d}',) + fill(AP, p=p))
    NI = ('{n}を入手しました。', 'Obtained {n}.', '获得了{n}。', '{n}을(를) 획득했습니다.', 'حصلت على {n}.', 'ได้รับ{n}'); NP = ('{p}が解放されました。', 'The {p} has been unlocked.', '{p}已解锁。', '{p}이(가) 해금되었습니다.', 'تم فتح {p}.', 'ปลดล็อก{p}แล้ว')
    for i, n in enumerate(R07_NOUN): R.append((f'notify.item.{i + 1:02d}',) + fill(NI, n=n))
    for i, p in enumerate(R07_PLACE6): R.append((f'notify.place.{i + 1:02d}',) + fill(NP, p=p))
    TP = ('ヒント：{p}では{e}属性の装備が役に立つ。', 'Tip: {e} gear is useful in the {p}.', '提示：在{p}，{e}属性装备很有用。', '팁: {p}에서는 {e} 속성 장비가 유용하다.', 'تلميح: معدات {e} مفيدة في {p}.', 'เคล็ดลับ: อุปกรณ์ธาตุ{e}มีประโยชน์ใน{p}')
    for i in range(72): R.append((f'tips.{i + 1:02d}',) + fill(TP, p=R07_PLACE6[i // 6], e=R07_ELEM[i % 6]))
    SS = ('{n} ×{k} セット', '{n} x{k} Set', '{n} ×{k} 套装', '{n} ×{k} 세트', 'طقم {n} ×{k}', 'ชุด{n} ×{k}')
    for i, n in enumerate(R07_NOUN):
        for k in (3, 5, 10, 20, 50): R.append((f'shop.set.{i + 1:02d}_{k:02d}',) + fill(SS, n=n, k=k))
    NPC = [('npc.greet', ('ようこそ、{p}へ！', 'Welcome to the {p}!', '欢迎来到{p}！', '{p}에 오신 것을 환영합니다!', 'مرحبًا بك في {p}!', 'ยินดีต้อนรับสู่{p}!')), ('npc.farewell', ('{p}でまた会おう。', 'See you again in the {p}.', '在{p}再见。', '{p}에서 다시 만나요.', 'نراك مجددًا في {p}.', 'แล้วพบกันใหม่ที่{p}')),
           ('npc.closed', ('{p}への道は閉ざされている。', 'The road to the {p} is closed.', '通往{p}的道路已封闭。', '{p}(으)로 가는 길은 막혀 있다.', 'الطريق إلى {p} مغلق.', 'เส้นทางไป{p}ถูกปิดอยู่')), ('loading.place', ('{p}を読み込み中…', 'Loading the {p}…', '正在加载{p}…', '{p} 불러오는 중…', 'جارٍ تحميل {p}…', 'กำลังโหลด{p}…'))]
    for kx, t in NPC:
        for i, p in enumerate(R07_PLACE6): R.append((f'{kx}.{i + 1:02d}',) + fill(t, p=p))
    for i, e in enumerate(R07_ELEM): R.append((f'element.{i + 1}',) + e)
    assert len(R) == 1500 and len(set(r[0] for r in R)) == 1500
    R1 = [list(r) for r in R]; idx = {r[0]: i for i, r in enumerate(R1)}; CL = []      # CL: (分類, key, 言語, 旧, 新)
    def cc(cat, k, lang, a, b):
        r = R1[idx[k]]; j = 1 + LG.index(lang); old = r[j]; assert a in old, (k, lang, a, old); r[j] = old.replace(a, b, 1); CL.append((cat, k, lang, old, r[j]))
    for k, a, b in [('item.001.name', 'قديم', 'عتيق'), ('ui.settings', 'الإعدادات', 'الضبط'), ('quest.014.title', 'وحوش', 'من الوحوش'), ('notify.item.03', 'حصلت', 'لقد حصلت'), ('npc.greet.02', 'مرحبًا', 'أهلًا'), ('tips.07', '.', '.‏')]: cc('アラビア語', k, 'ar', a, b)
    for k, a, b in [('item.002.name', 'เก่า', 'เก่าแก่'), ('ui.cancel', 'ยกเลิก', 'ยกเลิกคำสั่ง'), ('item.003.desc', 'ฟื้นฟู HP {0}', 'ฟื้นฟู HP {0} หน่วย'), ('monster.005.desc', 'จุดอ่อนคือ', 'แพ้ทาง'), ('achievement.reach.03', 'เป็นครั้งแรก', 'ครั้งแรก'), ('shop.set.04_10', 'ชุด', 'เซ็ต')]: cc('タイ語', k, 'th', a, b)
    for k, a, b in [('ui.new_game', 'New Game', 'Start New Game'), ('item.005.desc', ', or higher', ' or higher'), ('item.021.name', 'Shining', 'Radiant'), ('monster.012.desc', 'Weak to', 'Weak against'), ('quest.090.title', 'Find the', 'Search for the'),
                    ('skill.09.desc', 'Deals {0}', 'Deals {O}'), ('achievement.hunt.03_5', '1,000', '1000'), ('npc.closed.05', 'is closed', 'is sealed')]: cc('英語', k, 'en', a, b)
    for k, a, b in [('ui.shop', '商店', '商城'), ('item.041.name', '传说的', '传奇'), ('notify.place.06', '已解锁', '已开放'), ('tips.20', '很有用', '非常有效')]: cc('中国語', k, 'zh-Hans', a, b)
    for k, a, b in [('ui.mail', '우편', '메일'), ('item.061.name', '저주받은', '저주의'), ('quest.005.title', '조사', '탐사'), ('loading.place.09', '불러오는 중', '로딩 중')]: cc('韓国語', k, 'ko', a, b)
    for k, a, b in [('ui.items', 'もちもの', '持ち物'), ('item.004.desc', '売却できる', '売れる'), ('monster.033.name', 'オオカミ', '狼'), ('quest.200.title', 'を探す', 'を探し出す'), ('npc.farewell.11', 'また会おう', 'また会いましょう')]: cc('日本語', k, 'ja', a, b)
    cc('セル内改行', 'item.008.desc', 'ja', '\n', ' '); cc('セル内改行', 'item.010.desc', 'en', 'gold.', 'gold.\nSell at any shop.')
    cc('引用符', 'ui.delete_confirm', 'en', '"{0}"', "'{0}'"); cc('引用符', 'ui.rename_done', 'ko', '"{0}"', '『{0}』')
    assert len(CL) == 37 and len(set(c[1] for c in CL)) == 37
    cdel = ['item.240.name', 'item.240.desc', 'shop.set.20_50', 'tips.72']; R1 = [r for r in R1 if r[0] not in cdel]
    EV = [('祭りの屋台', 'Festival Stall', '祭典摊位', '축제 노점', 'كشك المهرجان', 'ร้านในงานเทศกาล'), ('雪の結晶', 'Snowflake', '雪花', '눈 결정', 'ندفة ثلج', 'เกล็ดหิมะ'), ('冬の市が始まりました！', 'The Winter Fair has begun!', '冬季集市开始了！', '겨울 장터가 시작되었습니다!', 'بدأ سوق الشتاء!', 'ตลาดฤดูหนาวเริ่มแล้ว!'),
          ('雪の結晶を{0}個集める', 'Collect {0} snowflakes', '收集{0}片雪花', '눈 결정 {0}개 모으기', 'اجمع {0} ندفة ثلج', 'สะสมเกล็ดหิมะ {0} ชิ้น'), ('氷晶の女王', 'Queen of Frost Crystal', '冰晶女王', '빙정의 여왕', 'ملكة البلّور الجليدي', 'ราชินีผลึกน้ำแข็ง'), ('氷晶の女王を倒す', 'Defeat the Queen of Frost Crystal', '击败冰晶女王', '빙정의 여왕 처치', 'اهزم ملكة البلّور الجليدي', 'กำจัดราชินีผลึกน้ำแข็ง'),
          ('星織りのマフラー', 'Starwoven Scarf', '星织围巾', '별을 엮은 목도리', 'وشاح منسوج بالنجوم', 'ผ้าพันคอถักดาว'), ('フレンドに贈り物を贈る', 'Send a gift to a friend', '给好友送礼物', '친구에게 선물 보내기', 'أرسل هدية إلى صديق', 'ส่งของขวัญให้เพื่อน'),
          ('期間：12月18日〜1月12日', 'Period: Dec 18 – Jan 12', '期间：12月18日～1月12日', '기간: 12월 18일 ~ 1월 12일', 'الفترة: 18 ديسمبر – 12 يناير', 'ระยะเวลา: 18 ธ.ค. – 12 ม.ค.'), ('期間中はショップが{0}%オフ', '{0}% off in the shop during the event', '活动期间商店{0}%折扣', '기간 중 상점 {0}% 할인', 'خصم {0}% في المتجر خلال الحدث', 'ลด {0}% ในร้านค้าช่วงกิจกรรม'),
          ('イベントは終了しました。\nまたのご参加をお待ちしています。', 'The event has ended.\nWe look forward to seeing you again.', '活动已结束。\n期待您再次参加。', '이벤트가 종료되었습니다.\n다음에 또 참여해 주세요.', 'انتهى الحدث.\nنتطلع إلى مشاركتك مجددًا.', 'กิจกรรมสิ้นสุดแล้ว\nแล้วพบกันใหม่'), ('交換所', 'Exchange', '兑换所', '교환소', 'مركز التبادل', 'จุดแลกเปลี่ยน')]
    cadd = [f'event.winter.{i + 1:02d}' for i in range(12)]
    R1 += [[k] + list(v) for k, v in zip(cadd, EV)]
    def csvb(rows):
        """Excel が書き出す形：レコードの区切りは CRLF、セルの中の改行は LF。各レコードの先頭の行番号も返す"""
        b = io.StringIO(); w = csv.writer(b, lineterminator='\r\n'); w.writerow(['key'] + LG); at = {}
        for r in rows: at[r[0]] = b.getvalue().count('\n') + 1; w.writerow(r)
        return b'\xef\xbb\xbf' + b.getvalue().encode('utf-8'), at, b.getvalue().count('\n')
    m0n = 'messages_1.8.0.csv'; m1n = 'messages_1.8.1_翻訳会社戻り.csv'
    b0, at0, pl0 = csvb(R); b1, at1, pl1 = csvb(R1); wbytes(f'{d}/文言/{m0n}', b0); wbytes(f'{d}/文言/{m1n}', b1)
    rd = lambda n: list(csv.reader(io.StringIO(open(P(f'{d}/文言/{n}'), 'rb').read().decode('utf-8-sig'), newline='')))
    L0, L1 = rd(m0n), rd(m1n); D0 = {r[0]: r for r in L0[1:]}; D1 = {r[0]: r for r in L1[1:]}
    assert len(L0) == 1501 and len(L1) == 1501 - 4 + 12 and [tuple(r) for r in L0[1:]] == R
    dk = [k for k in D0 if k in D1 and D0[k] != D1[k]]; assert sorted(dk) == sorted(c[1] for c in CL)
    for cat, k, lang, a, b in CL: j = 1 + LG.index(lang); assert [i for i in range(7) if D0[k][i] != D1[k][i]] == [j] and (D0[k][j], D1[k][j]) == (a, b)
    assert sorted(k for k in D0 if k not in D1) == sorted(cdel) and sorted(k for k in D1 if k not in D0) == sorted(cadd)
    multi = lambda D: sum(1 for r in D.values() if any('\n' in c for c in r))
    def cshow(c):
        cat, k, lang, a, b = c; return f'{k}（旧 {at0[k]}行目／新 {at1[k]}行目）{lang}：' + json.dumps(a, ensure_ascii=False) + ' → ' + json.dumps(b, ensure_ascii=False)
    cby = lambda cat: '／'.join(cshow(c) for c in CL if c[0] == cat)
    key(d, f'■ 多言語 CSV「文言/{m0n}」（見出し＋1,500 レコード、ファイルの行数 {pl0:,}）→「文言/{m1n}」（見出し＋1,508 レコード、ファイルの行数 {pl1:,}）。UTF-8 BOM 付き。列は key, ja, en, zh-Hans, ko, ar, th',
        f'セルの中に改行（LF）を含むレコードが 旧 {multi(D0)}・新 {multi(D1)} あり、レコードの区切りは CRLF（Excel で書き出した形。1つのファイルに CRLF と LF が混ざる）。このため、ファイルの行番号とレコードの番号は一致しない。下の行番号は、そのレコードが始まるファイルの行',
        '中身が違うレコードは 37（どれも1つのセルだけが違う）。key は旧と新で同じ順。内訳：アラビア語 6・タイ語 6・英語 8・中国語 4・韓国語 4・日本語 5・セル内改行 2・引用符 2',
        '【アラビア語（右から左）6】' + cby('アラビア語') + '（最後の tips.07 は、文末に目に見えない文字 U+200F（右から左の印）が1つ付いただけ）', '【タイ語 6】' + cby('タイ語'),
        '【英語 8】' + cby('英語') + '（skill.09.desc は {0}→{O} の制御タグの破損。item.005.desc はカンマがなくなったので、新ではセルが引用符で囲まれなくなる。achievement.hunt.03_5 は桁区切りのカンマがなくなり、同じく引用符がなくなる）',
        '【中国語 4】' + cby('中国語'), '【韓国語 4】' + cby('韓国語'), '【日本語 5】' + cby('日本語'),
        '【セル内改行 2】' + cby('セル内改行') + '（1つ目は改行が空白になり、セルが1行になった。2つ目は改行と1文が増えた）', '【引用符 2】' + cby('引用符') + '（CSV の中では、" は "" と書かれている）',
        'レコードの削除 4（旧のみ）：' + '、'.join(f'{k}（旧 {at0[k]}行目）' for k in cdel) + f'／追加 12（新のみ・末尾）：event.winter.01〜12（新 {at1[cadd[0]]}行目から。event.winter.11 はセル内改行あり）')

    # ---------------------------------------------------------------- dialog.yaml（会話データ。字下げだけの変更のかたまり・本当の文言の変更・タブの混入）
    who_ = ['カイ', 'ミレイユ', 'ドルガン', '老師セト', '船長バルド', '酒場の主人']; face = ['normal', 'smile', 'serious', 'surprise', 'angry', 'sad']; loc = ['港町リベルタ・桟橋', '港町リベルタ・宿屋「かもめ亭」', '港町リベルタ・酒場', '港町リベルタ・倉庫街', '西の岬', '老師の庵']
    SC = []
    for k in range(36):
        ls = [{'sp': who_[(k * 5 + j * 3 + j // 2) % 6], 'face': face[(k + j * 2) % 6], 'text': list(R07_TALK[(k * 7 + j * 3) % len(R07_TALK)])} for j in range(6 + k % 5)]
        SC.append({'id': f'ch03_sc{k + 1:02d}', 'loc': loc[k % 6], 'bgm': ['bgm_harbor_day', 'bgm_harbor_night', 'bgm_tension', 'bgm_battle_01', 'bgm_calm'][k % 5], 'lines': ls})
    SC1 = json.loads(json.dumps(SC)); WIDE = range(11, 17); YC = []      # YC: (場面, 何番目のせりふ, 旧の行, 新の行)
    def yc(lo, hi, a, b):
        for k in range(lo, hi):
            for j, ln in enumerate(SC1[k]['lines']):
                for t, s in enumerate(ln['text']):
                    if a in s and not any(c[0] == k and c[1] == j for c in YC): ln['text'][t] = s.replace(a, b, 1); YC.append((k, j, s, ln['text'][t])); return
        raise AssertionError(('yaml phrase not found', a, lo, hi))
    for a, b in [('先を急ぐぞ', '先を急ごう'), ('早くても三日後だな', '早くても五日後だな'), ('無茶はしません', '無茶はしないと約束します')]: yc(11, 17, a, b)
    for a, b, lo, hi in [('ここが港町リベルタか', 'ここが、港町リベルタか', 0, 11), ('宿を探そう', '宿を取ろう', 0, 11), ('エール二杯', 'エール三杯', 0, 11), ('西の岬のことかしら', '西の岬のことじゃないかしら', 17, 36), ('斬っても手応えがない', '斬っても、まるで手応えがない', 17, 36), ('黒い外套の男', '黒い外套の女', 17, 36)]: yc(lo, hi, a, b)
    assert len(YC) == 9
    def ytext(scs, wide=()):
        L = ['# 会話データ 第3章「潮騒の街」', '# 文言を直すのは text: の中だけ。id・face・bgm は変えないこと。字下げは半角の空白（タブは使わない）', 'chapter: 3', 'title: 潮騒の街', 'scenes:']
        for si, sc in enumerate(scs):
            s = 4 if si in wide else 2; a = ' ' * (4 + s); b = ' ' * (6 + s); c = ' ' * (6 + 2 * s)
            L += [f'  - id: {sc["id"]}', f'    location: {sc["loc"]}', f'    bgm: {sc["bgm"]}', '    lines:']
            for ln in sc['lines']: L += [f'{a}- speaker: {ln["sp"]}', f'{b}face: {ln["face"]}', f'{b}text: |'] + [c + t for t in ln['text']]
        return L
    Y0 = ytext(SC); Y1 = ytext(SC1, WIDE); assert len(Y0) == len(Y1)
    tabln = _lineno(Y1, 'id: ch03_sc26'); tabln = next(i for i in range(tabln, len(Y1)) if Y1[i] == '        face: ' + SC1[25]['lines'][1]['face']) + 1
    fixed = '\n'.join(Y1) + '\n'; Y1[tabln - 1] = '\t' + Y1[tabln - 1][8:]
    y0n = 'dialog_ch03_1.8.0.yaml'; y1n = 'dialog_ch03_1.8.1_翻訳会社戻り.yaml'; text(f'{d}/文言/{y0n}', '\n'.join(Y0) + '\n'); text(f'{d}/文言/{y1n}', '\n'.join(Y1) + '\n')
    import yaml
    A_, B_ = _lines_of(f'{d}/文言/{y0n}'), _lines_of(f'{d}/文言/{y1n}')
    ind_only = [i + 1 for i in range(len(A_)) if A_[i] != B_[i] and A_[i].strip() == B_[i].strip() and '\t' not in B_[i]]; real = [i + 1 for i in range(len(A_)) if A_[i].strip() != B_[i].strip()]; tabs = [i + 1 for i in range(len(B_)) if '\t' in B_[i]]
    assert len(real) == 9 and tabs == [tabln] and {(A_[i - 1].strip(), B_[i - 1].strip()) for i in real} == {(c[2], c[3]) for c in YC}
    wl0, wl1 = _lineno(A_, 'id: ch03_sc12'), _lineno(A_, 'id: ch03_sc18') - 1; assert all(wl0 < i <= wl1 for i in ind_only) and sum(1 for i in real if wl0 < i <= wl1) == 3
    ok = True
    try: yaml.safe_load(open(P(f'{d}/文言/{y1n}'), encoding='utf-8').read())
    except yaml.YAMLError: ok = False
    assert not ok
    ya, yb = yaml.safe_load('\n'.join(A_)), yaml.safe_load(fixed); nd = sum(1 for x, y in zip(ya['scenes'], yb['scenes']) for p, q in zip(x['lines'], y['lines']) if p != q); assert nd == 9 and len(ya['scenes']) == 36
    key(d, f'■ 会話 YAML「文言/{y0n}」→「文言/{y1n}」（どちらも {len(A_) - 1:,}行・UTF-8・LF。36 場面。せりふは text: | の複数行）。行の数は同じで、同じ行番号どうしが対応する',
        f'字下げだけが変わった行 {len(ind_only)} 行：場面 ch03_sc12〜sc17（{wl0}〜{wl1}行目）の中の、speaker・face・text とせりふの行。字下げの幅が 2→4 になった（「- speaker」は空白 6→8、face・text は 8→10、せりふは 10→14）。'
        'id・location・bgm・lines の行は変わっていない。YAML として読んだ中身は同じ。「空白の量を無視」では、これらの行は差にならないのが正しい',
        '本当の文言の変更 9 行（うち 3 行は、字下げが変わったかたまりの中）：' + '／'.join(f'{i}行目「{A_[i - 1].strip()}」→「{B_[i - 1].strip()}」' + ('（字下げも変更）' if wl0 < i <= wl1 else '') for i in real),
        f'【仕込んだ誤り】タブの混入 1 か所：新の {tabln}行目（ch03_sc26 の2つ目のせりふの face の行）は、行頭の空白8つがタブ1つになっている。文字は同じだが、YAML では字下げにタブを使えないので、新のファイルはこのままでは読み込みエラーになる（空白の記号表示で見つけられること。空白を無視すると見えなくなる）')

    # ---------------------------------------------------------------- XLIFF（翻訳支援ツールの .xlf。ja → en）
    def xlf(v):
        units = []
        for i, r in enumerate(R[:300]):
            k, ja, en = r[0], r[1], r[2]; state = 'needs-review-translation' if i % 23 == 5 else 'translated'; note = 'ボタン。全角6文字以内' if k.startswith('ui.') and len(ja) <= 6 else ('{0} は数値に置き換わる' if '{0}' in ja else '')
            units.append({'id': k, 'src': ja, 'tgt': en, 'state': state, 'note': note, 'swap': False, 'rawph': False})
        log = []
        if v:
            U = {u['id']: u for u in units}
            for k, a, b in [('ui.new_game', 'New Game', 'Start New Game'), ('ui.thanks', 'Thanks, come again!', 'Thank you!'), ('ui.bag_full', 'Your bag is full.', 'Your inventory is full.'), ('item.005.desc', ', or higher', ' or higher'), ('item.021.name', 'Shining', 'Radiant'),
                            ('item.034.name', 'Lantern', 'Lamp'), ('item.049.desc', 'Increases', 'Raises'), ('item.100.name', 'Armor', 'Mail')]:
                assert a in U[k]['tgt']; old = U[k]['tgt']; U[k]['tgt'] = old.replace(a, b, 1); log.append(('訳文', k, old, U[k]['tgt']))
            rev = [u['id'] for u in units if u['state'] != 'translated'][:5]
            for k in rev: U[k]['state'] = 'translated'; log.append(('状態', k, 'needs-review-translation', 'translated'))
            for k in ('ui.gold', 'item.012.desc'): U[k]['swap'] = True; log.append(('属性の順', k, '', ''))
            U['item.003.desc']['rawph'] = True; log.append(('ph', 'item.003.desc', '', ''))
            gone_ = 'item.120.name'; units = [u for u in units if u['id'] != gone_]; log.append(('削除', gone_, '', ''))
            for k, ja, en in [('event.winter.01', '祭りの屋台', 'Festival Stall'), ('event.winter.02', '雪の結晶', 'Snowflake'), ('event.winter.04', '雪の結晶を{0}個集める', 'Collect {0} snowflakes')]:
                units.append({'id': k, 'src': ja, 'tgt': en, 'state': 'new', 'note': '1.8.1 で追加', 'swap': False, 'rawph': False}); log.append(('追加', k, '', ''))
        ph = lambda s, raw=False: esc(s) if raw else re.sub(r'\{(\d)\}', lambda m: f'<ph id="{int(m.group(1)) + 1}">{{{m.group(1)}}}</ph>', esc(s)).replace('\n', '<x id="lb"/>')
        L = ['<?xml version="1.0" encoding="UTF-8"?>', '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">',
             f'  <file original="messages.csv" source-language="ja" target-language="en" datatype="plaintext" tool-id="tm-bridge" date="{"2026-11-25T05:31:47Z" if v else "2026-10-30T09:02:11Z"}">',
             '    <header>', '      <tool tool-id="tm-bridge" tool-name="TM Bridge" tool-version="4.2.1"/>', f'      <note>arcadia {"1.8.1" if v else "1.8.0"} / ja → en</note>', '    </header>', '    <body>']; at = {}
        for u in units:
            at[u['id']] = len(L) + 1
            L.append(f'      <trans-unit resname="{u["id"]}" id="{u["id"]}" xml:space="preserve">' if u['swap'] else f'      <trans-unit id="{u["id"]}" resname="{u["id"]}" xml:space="preserve">')
            L += [f'        <source>{ph(u["src"])}</source>', f'        <target state="{u["state"]}">{ph(u["tgt"], u["rawph"])}</target>'] + ([f'        <note from="developer">{esc(u["note"])}</note>'] if u['note'] else []) + ['      </trans-unit>']
        L += ['    </body>', '  </file>', '</xliff>']
        return '\n'.join(L) + '\n', at, log, len(units)
    x0, xa0, _, nu0 = xlf(0); x1, xa1, xlog, nu1 = xlf(1); x0n = 'ui_ja-en_1.8.0.xlf'; x1n = 'ui_ja-en_1.8.1_翻訳会社戻り.xlf'; text(f'{d}/文言/{x0n}', x0); text(f'{d}/文言/{x1n}', x1)
    import xml.etree.ElementTree as ET
    ns = '{urn:oasis:names:tc:xliff:document:1.2}'
    def xparse(n):
        out = {}
        for tu in ET.parse(P(f'{d}/文言/{n}')).getroot().iter(ns + 'trans-unit'):
            t = tu.find(ns + 'target'); out[tu.get('id')] = (ET.tostring(tu.find(ns + 'source'), encoding='unicode'), ''.join(t.itertext()), t.get('state'), len(list(t)))
        return out
    X0, X1 = xparse(x0n), xparse(x1n); assert (len(X0), len(X1), nu0, nu1) == (300, 302, 300, 302)
    xd = {k for k in X0 if k in X1 and X0[k] != X1[k]}; assert xd == {c[1] for c in xlog if c[0] in ('訳文', '状態', 'ph')} and len(xd) == 14
    assert X0['item.003.desc'][3] == 1 and X1['item.003.desc'][3] == 0 and X0['item.003.desc'][1] == X1['item.003.desc'][1]
    xs = lambda cat, f: '、'.join(f(c) for c in xlog if c[0] == cat)
    key(d, f'■ XLIFF「文言/{x0n}」（trans-unit 300・{x0.count(chr(10)):,}行）→「文言/{x1n}」（trans-unit 302・{x1.count(chr(10)):,}行）。XML・UTF-8・LF。{{0}} は <ph id="1">{{0}}</ph>、改行は <x id="lb"/> で書かれている',
        '<file> の date 属性（3行目）と、<header> の <note>（6行目。1.8.0→1.8.1）が変わる',
        '訳文（target）の変更 8：' + xs('訳文', lambda c: f'{c[1]}（旧 {xa0[c[1]] + 2}行目／新 {xa1[c[1]] + 2}行目）「{c[2]}」→「{c[3]}」'),
        '状態だけの変更 5（target の state="needs-review-translation" → "translated"。訳文は同じ）：' + xs('状態', lambda c: f'{c[1]}（旧 {xa0[c[1]] + 2}行目）'),
        f'制御タグの破損 1：item.003.desc（旧 {xa0["item.003.desc"] + 2}行目／新 {xa1["item.003.desc"] + 2}行目）の target で、<ph id="1">{{0}}</ph> の囲みがなくなり、ただの {{0}} になった（見える文字「Restores {{0}} HP.」は同じ）',
        '属性の順番だけの変更 2（id と resname の並びが入れ替わっただけ。XML としては同じ）：' + xs('属性の順', lambda c: f'{c[1]}（旧 {xa0[c[1]]}行目／新 {xa1[c[1]]}行目）'),
        f'trans-unit の削除 1：item.120.name（旧 {xa0["item.120.name"]}行目から4行）／追加 3（末尾。state="new"）：' + xs('追加', lambda c: f'{c[1]}（新 {xa1[c[1]]}行目から）'))

    # ---------------------------------------------------------------- UI のスクリーンショット（1920×1080。暗い背景に明るい文字）
    def shot(v):
        W, H = 1920, 1080; im = Image.new('RGB', (W, H)); dr = ImageDraw.Draw(im); r = random.Random(77)
        for y in range(H): dr.line([0, y, W, y], fill=(10 + y * 14 // H, 14 + y * 10 // H, 38 + y * 30 // H))
        for _ in range(260):
            x, y, b = r.randrange(W), r.randrange(H * 2 // 3), r.randrange(110, 255); s = r.choice([1, 1, 1, 2]); dr.ellipse([x, y, x + s, y + s], fill=(b, b, min(255, b + 20)))
        dr.polygon([(0, 1080), (0, 820), (300, 700), (520, 790), (760, 640), (1040, 800), (1300, 690), (1620, 810), (1920, 720), (1920, 1080)], fill=(8, 10, 24))
        dr.text((150, 120), '星霜のアルカディア', fill=(245, 236, 200), font=font(104, True)); dr.text((158, 258), 'ARCADIA OF STARFROST', fill=(170, 190, 235), font=font(34)); dr.line([150, 312, 980, 312], fill=(170, 190, 235), width=2)
        boxes = {}
        for i, lab in enumerate(['ニューゲーム' if v else 'はじめから', 'つづきから', 'マルチプレイ', 'ショップ', '設定', '終了']):
            x0, y0 = 160 + (1 if v and i == 4 else 0), 392 + i * 92; sel = i == 1; box = [x0, y0, x0 + 460, y0 + 72]; boxes[i] = box
            dr.rounded_rectangle(box, radius=14, fill=((46, 118, 216) if v else (46, 111, 216)) if sel else (30, 44, 86), outline=(255, 226, 140) if sel else (110, 140, 220), width=3)
            dr.text((x0 + 44, y0 + 12), lab, fill=(255, 255, 255) if sel else (220, 228, 250), font=font(36, sel))
            if sel: dr.polygon([(x0 + 14, y0 + 24), (x0 + 30, y0 + 36), (x0 + 14, y0 + 48)], fill=(255, 226, 140))
        dr.rounded_rectangle([1240, 380, 1800, 640], radius=16, fill=(18, 26, 56), outline=(110, 140, 220), width=2); dr.text((1270, 398), 'プレイヤー', fill=(170, 190, 235), font=font(24)); dr.text((1270, 434), 'カイ　Lv.42', fill=(255, 255, 255), font=font(40, True))
        for j, (a, b) in enumerate([('プレイ時間', '63:27'), ('所持ゴールド', '128,450 G'), ('現在地', '港町リベルタ')]): dr.text((1270, 506 + j * 40), a, fill=(170, 190, 235), font=font(24)); dr.text((1500, 504 + j * 40), b, fill=(235, 240, 255), font=font(26))
        dr.rounded_rectangle([1240, 670, 1800, 900], radius=16, fill=(18, 26, 56), outline=(110, 140, 220), width=2); dr.text((1270, 688), 'お知らせ', fill=(255, 226, 140), font=font(26, True))
        for j, s in enumerate(['10/30　Ver 1.8.0 を配信しました', '10/16　「収穫祭の夜」が始まりました', '10/09　メンテナンスのお知らせ（10/16 2:00〜6:00）', '10/01　ログインボーナスを更新しました']): dr.text((1270, 736 + j * 38), s, fill=(225, 230, 245), font=font(22))
        dr.text((40, 1036), '© 2026 Hoshizora Works', fill=(150, 160, 190), font=font(20)); dr.text((1740, 1036), 'Ver 1.8.1' if v else 'Ver 1.8.0', fill=(150, 160, 190), font=font(20))
        if v: dr.text((700, 1036), '※ オートセーブ中は電源を切らないでください', fill=(150, 160, 190), font=font(20))
        return im, boxes
    im0, bx = shot(0); im1, _ = shot(1); p0n = 'screenshot_メニュー画面_1.8.0.png'; p1n = 'screenshot_メニュー画面_1.8.1.png'; im0.save(P(f'{d}/スクリーンショット/{p0n}')); im1.save(P(f'{d}/スクリーンショット/{p1n}'))
    regs = {'文言': [200, 398, 480, 458], '色': bx[1], '1px': [bx[4][0], bx[4][1], bx[4][2] + 2, bx[4][3] + 1], '注記': [690, 1030, 1160, 1070], '版': [1730, 1030, 1870, 1070]}
    dif = ImageChops.difference(Image.open(P(f'{d}/スクリーンショット/{p0n}')), Image.open(P(f'{d}/スクリーンショット/{p1n}'))).convert('L').point(lambda x: 255 if x else 0)
    rb = {}
    for k, (a, b, c_, e) in regs.items(): bb = dif.crop((a, b, c_ + 1, e + 1)).getbbox(); assert bb, k; rb[k] = (a + bb[0], b + bb[1], a + bb[2] - 1, b + bb[3] - 1)
    rest = dif.copy(); dr_ = ImageDraw.Draw(rest)
    for a, b, c_, e in regs.values(): dr_.rectangle([a, b, c_, e], fill=0)
    assert rest.getbbox() is None and im0.size == im1.size == (1920, 1080)
    key(d, f'■ スクリーンショット「スクリーンショット/{p0n}」→「…/{p1n}」（どちらも 1920×1080 の PNG。暗い背景に明るい文字）。違いは次の5か所だけ（座標は左上を 0,0 とした画素。実際に違う画素の範囲）',
        f'① ボタンの文言：1つ目のボタン「はじめから」→「ニューゲーム」（x {rb["文言"][0]}〜{rb["文言"][2]}、y {rb["文言"][1]}〜{rb["文言"][3]}）',
        f'② 色の変更（少しだけ）：選ばれているボタン「つづきから」の地の青 RGB(46,111,216) → (46,118,216)（x {rb["色"][0]}〜{rb["色"][2]}、y {rb["色"][1]}〜{rb["色"][3]}。形・文字は同じ）',
        f'③ 1px のずれ：5つ目のボタン「設定」が、枠も文字も右へ 1 画素ずれた（x {rb["1px"][0]}〜{rb["1px"][2]}、y {rb["1px"][1]}〜{rb["1px"][3]}）',
        f'④ 小さな注記の追加：下端の中央に「※ オートセーブ中は電源を切らないでください」（x {rb["注記"][0]}〜{rb["注記"][2]}、y {rb["注記"][1]}〜{rb["注記"][3]}。灰色の小さい文字）',
        f'⑤ 版の表示：右下「Ver 1.8.0」→「Ver 1.8.1」（x {rb["版"][0]}〜{rb["版"][2]}、y {rb["版"][1]}〜{rb["版"][3]}。最後の1文字だけ）', 'ほかの部分（星・題字・右の2つの枠・ほかのボタン）は、1画素も違わない')

    # ---------------------------------------------------------------- 配布用フォルダ build_1.8.0/ と build_1.8.1/
    def png(seed, size=32):
        r = random.Random(seed); im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); dr = ImageDraw.Draw(im); col = (r.randrange(256), r.randrange(256), r.randrange(256), 255)
        dr.rounded_rectangle([2, 2, size - 3, size - 3], radius=6, fill=col); dr.ellipse([size // 4, size // 4, size * 3 // 4, size * 3 // 4], fill=(255, 255, 255, 230)); dr.line([4, r.randrange(4, size - 4), size - 5, r.randrange(4, size - 4)], fill=(20, 20, 40, 255), width=2)
        b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()
    def ogg(seed, n=None):
        r = random.Random(f'ogg{seed}'); return b'OggS\x00\x02' + bytes(8) + r.randbytes(n or r.randrange(1500, 6000))
    J = lambda o: (json.dumps(o, ensure_ascii=False, indent=2) + '\n').encode('utf-8'); T8 = lambda s: s.encode('utf-8')
    FA = {}
    for i in range(40): FA[f'Assets/Audio/BGM/bgm_{i + 1:02d}.ogg'] = ogg(f'b{i}', 9000 + i * 37)
    for i in range(160): FA[f'Assets/Audio/SE/se_{i + 1:03d}.ogg'] = ogg(f's{i}')
    for i in range(240): FA[f'Assets/Audio/Voice/vc_ch{i // 40 + 1:02d}_{i % 40 + 1:03d}.ogg'] = ogg(f'v{i}')
    for i in range(160): FA[f'Assets/Textures/UI/ui_{["btn", "frame", "icon", "gauge"][i % 4]}_{i + 1:03d}.png'] = png(f'u{i}')
    for i in range(120): FA[f'Assets/Textures/Characters/chara_{i // 6 + 1:02d}_{["idle", "walk", "attack", "damage", "win", "face"][i % 6]}.png'] = png(f'c{i}', 64)
    for i in range(40): FA[f'Assets/Textures/Backgrounds/bg_{i + 1:02d}.png'] = png(f'g{i}', 96)
    for i in range(180): FA[f'Assets/Textures/Items/item_{i + 1:03d}.png'] = png(f'i{i}')
    for i in range(60): FA[f'Assets/Data/Master/master_{["item", "skill", "quest", "monster", "shop", "drop"][i % 6]}_{i // 6 + 1:02d}.json'] = J({'table': ["item", "skill", "quest", "monster", "shop", "drop"][i % 6], 'page': i // 6 + 1, 'rows': [{'id': i * 100 + k, 'value': (i * 37 + k * 11) % 500, 'rate': round(((i + k) % 17) / 16, 4)} for k in range(20)]})
    for li, lg in enumerate(['ja', 'en', 'zh-Hans', 'ko', 'ar', 'th', 'fr']):
        for ci, cat in enumerate(['common', 'title', 'menu', 'settings', 'shop', 'items', 'skills', 'quests', 'achievements', 'errors', 'tutorial', 'events']):
            src = {'.'.join(k): v for k, v in F0.items() if k[0] == cat} if lg == 'ja' else {r[0]: r[1 + min(li, 5)] for r in R[ci * 60:ci * 60 + 60]}
            FA[f'Assets/Data/Localization/{lg}_{cat}.json'] = J(src)
    for i in range(80): FA[f'Assets/Data/Scenario/sc_ch{i // 10 + 1:02d}_{i % 10 + 1:02d}.txt'] = T8(''.join(f'[{who_[(i + j) % 6]}]\n' + '\n'.join(R07_TALK[(i * 5 + j * 3) % len(R07_TALK)]) + '\n\n' for j in range(8)))
    for i in range(18): FA[f'Config/{["graphics", "audio", "input", "network", "region", "debug"][i % 6]}_{["default", "low", "high"][i // 6]}.{"json" if i % 2 == 0 else "txt"}'] = J({'profile': ["default", "low", "high"][i // 6], 'level': i, 'enabled': i % 3 != 0}) if i % 2 == 0 else T8(f'# {["graphics", "audio", "input", "network", "region", "debug"][i % 6]}\nprofile={["default", "low", "high"][i // 6]}\nlevel={i}\n')
    for i in range(14): FA[f'Licenses/license_{["font", "audio", "engine", "plugin", "codec", "tool", "lib"][i % 7]}_{i // 7 + 1}.txt'] = T8(f'License notice #{i + 1}\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this component ({["font", "audio", "engine", "plugin", "codec", "tool", "lib"][i % 7]} #{i // 7 + 1}) ...\n')
    FA['version.txt'] = T8('1.8.0\nbuild 4412\n2026-10-30\n'); FA['README.txt'] = T8('星霜のアルカディア 配布用ビルド\n\nこのフォルダを、そのまま配信サーバへアップロードしてください。\nファイル名の大文字・小文字は変えないでください（サーバは区別します）。\n')
    FA['Config/app_settings.json'] = J({'api_base': 'https://api.arcadia.example.jp/v1', 'cdn_base': 'https://cdn.arcadia.example.jp/1.8.0', 'timeout_sec': 15, 'max_friends': 100, 'maintenance': False}); FA['Config/override.txt'] = b''
    FA['Assets/Audio/Voice/vc_placeholder.ogg'] = b''; FA['Assets/Data/Cache/.gitkeep'] = b''; FA['Assets/Textures/UI/Thumbs.db'] = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + random.Random('thumbs').randbytes(7000)
    FA['Assets/Textures/UI/Icon_Shop.png'] = png('shopicon'); FA['Assets/Data/Master/ItemTable.json'] = J({'table': 'item', 'columns': ['id', 'name', 'price'], 'count': 180})
    def manifest(F, ver): return J({'version': ver, 'files': [{'path': k, 'size': len(v), 'sha1': hashlib.sha1(v).hexdigest()} for k, v in sorted(F.items()) if not os.path.basename(k).startswith('.') and k != 'manifest.json' and not k.endswith('Thumbs.db')]})
    FB = dict(FA); changed = []
    def mod(k, v): assert k in FA and FA[k] != v, k; FB[k] = v; changed.append(k)
    mod('version.txt', T8('1.8.1\nbuild 4467\n2026-11-25\n')); mod('Config/override.txt', T8('# 1.8.1 の緊急設定\nmax_friends=150\n')); mod('Config/app_settings.json', FA['Config/app_settings.json'].replace(b'/1.8.0', b'/1.8.1').replace(b'"max_friends": 100', b'"max_friends": 150'))
    for k in ['Assets/Data/Master/master_item_01.json', 'Assets/Data/Master/master_shop_03.json', 'Assets/Data/Master/master_drop_07.json', 'Assets/Data/Master/master_quest_10.json', 'Assets/Data/Master/master_monster_05.json']:
        o = json.loads(FA[k]); o['rows'][7]['value'] += 25; o['rows'][12]['rate'] = round(o['rows'][12]['rate'] + 0.0625, 4); mod(k, J(o))
    for lg, cat in [('ja', 'common'), ('ja', 'shop'), ('ja', 'tutorial'), ('en', 'title'), ('en', 'items'), ('zh-Hans', 'menu')]:
        k = f'Assets/Data/Localization/{lg}_{cat}.json'
        if lg == 'ja': mod(k, J({'.'.join(p): v for p, v in F1.items() if p[0] == cat}))
        else: o = json.loads(FA[k]); kk = sorted(o)[3]; o[kk] = o[kk] + ('!' if lg == 'en' else '！'); mod(k, J(o))
    for k in ['Assets/Data/Scenario/sc_ch02_04.txt', 'Assets/Data/Scenario/sc_ch05_09.txt', 'Assets/Data/Scenario/sc_ch08_01.txt']: mod(k, FA[k].replace('。'.encode('utf-8'), '！'.encode('utf-8'), 1))
    for k, sd_ in [('Assets/Textures/UI/ui_btn_001.png', 'new1'), ('Assets/Textures/UI/ui_icon_043.png', 'new2'), ('Assets/Textures/Characters/chara_07_face.png', 'new3'), ('Assets/Textures/Items/item_101.png', 'new4')]: mod(k, png(sd_, Image.open(io.BytesIO(FA[k])).size[0]))
    for k in ['Assets/Audio/BGM/bgm_12.ogg', 'Assets/Audio/Voice/vc_ch03_017.ogg', 'Assets/Audio/Voice/vc_ch05_002.ogg']: mod(k, ogg('re' + k))
    lonly = [f'Assets/Textures/UI/ui_old_banner_{i}.png' for i in (1, 2, 3, 4)] + [f'Assets/Audio/SE/se_legacy_{i}.ogg' for i in (1, 2, 3)] + ['Assets/Data/Scenario/sc_draft_a.txt', 'Assets/Data/Scenario/sc_draft_b.txt', 'Licenses/old_font_license.txt']
    for k in lonly: FA[k] = png('L' + k) if k.endswith('.png') else ogg('L' + k) if k.endswith('.ogg') else T8('（下書き）この場面は 1.8.1 で削除する。\n' if 'draft' in k else 'Old font license (no longer bundled).\n')
    ronly = [f'Assets/Textures/UI/ui_winter_banner_{i}.png' for i in (1, 2, 3)] + ['Assets/Audio/BGM/bgm_winter_festival.ogg', 'Assets/Data/Master/event_winter2026.json', 'Assets/Data/Localization/ja_event_winter.json', 'Assets/Data/Localization/en_event_winter.json', 'Licenses/new_font_license.txt']
    for k in ronly: FB[k] = png('R' + k) if k.endswith('.png') else ogg('R' + k, 12000) if k.endswith('.ogg') else J({'event': 'winter2026', 'file': os.path.basename(k), 'keys': cadd}) if k.endswith('.json') else T8('New font license (bundled from 1.8.1).\n')
    case = [('Assets/Textures/UI/Icon_Shop.png', 'Assets/Textures/UI/icon_shop.png'), ('Assets/Data/Master/ItemTable.json', 'Assets/Data/Master/itemtable.json')]
    for a, b in case: FB[b] = FB.pop(a)
    ds = ['.DS_Store', 'Assets/Textures/Characters/.DS_Store', 'Assets/Data/Localization/.DS_Store']
    for k in ds: FB[k] = b'\x00\x00\x00\x01Bud1' + random.Random(k).randbytes(6140)
    FA['manifest.json'] = manifest(FA, '1.8.0'); FB['manifest.json'] = manifest(FB, '1.8.1'); changed.append('manifest.json')
    same = sorted(k for k in FA if k in FB and FA[k] == FB[k]); touched = [k for k in same if k.endswith(('.png', '.json', '.txt')) and not os.path.basename(k).startswith('.')][5::17][:40]
    t_old = datetime.datetime(2026, 10, 30, 18, 0).timestamp(); t_new = datetime.datetime(2026, 11, 25, 14, 30).timestamp()
    for k, v in FA.items(): wbytes(f'{d}/build_1.8.0/{k}', v); os.utime(P(f'{d}/build_1.8.0/{k}'), (t_old, t_old))
    for k, v in FB.items(): wbytes(f'{d}/build_1.8.1/{k}', v); tt = t_old if (k in same and k not in touched) else t_new; os.utime(P(f'{d}/build_1.8.1/{k}'), (tt, tt))
    # 書き出したフォルダを読み直して数える
    def scan(root):
        out = {}
        for dp, _, fs in os.walk(root):
            for f in fs: p = os.path.join(dp, f); out[os.path.relpath(p, root).replace(os.sep, '/')] = (open(p, 'rb').read(), int(os.path.getmtime(p)))
        return out
    GA, GB = scan(P(f'{d}/build_1.8.0/x')[:-2]), scan(P(f'{d}/build_1.8.1/x')[:-2])
    g_diff = sorted(k for k in GA if k in GB and GA[k][0] != GB[k][0]); g_same = [k for k in GA if k in GB and GA[k][0] == GB[k][0]]; g_l = sorted(k for k in GA if k not in GB); g_r = sorted(k for k in GB if k not in GA)
    g_time = [k for k in g_same if GA[k][1] != GB[k][1]]; zero = sorted(k for k in g_same if len(GA[k][0]) == 0)
    assert len(g_diff) == 25 and g_diff == sorted(changed) and sorted(g_l) == sorted(lonly + [a for a, _ in case]) and sorted(g_r) == sorted(ronly + [b for _, b in case] + ds) and len(g_time) == 40 and len(touched) == 40
    assert len(GA) == len(g_same) + 25 + 12 and len(GB) == len(g_same) + 25 + 13 and zero == ['Assets/Audio/Voice/vc_placeholder.ogg', 'Assets/Data/Cache/.gitkeep']
    dep = max(k.count('/') for k in GA); assert dep == 3
    key(d, f'■ 配布用フォルダ「build_1.8.0/」（{len(GA):,} ファイル）と「build_1.8.1/」（{len(GB):,} ファイル）。json・png・ogg（中身は音声ではない適当なバイト列）・txt。サブフォルダは3階層まで（Assets/Audio/BGM/ など 11 フォルダ＋Config・Licenses）',
        f'内容が同じファイル：{len(g_same):,}（うち 40 は、内容は同じで更新日時だけが新しい＝1.8.1 側が 2026-11-25 14:30。ほかは左右とも 2026-10-30 18:00。0 バイトのファイルが2つ：{zero[0]}、{zero[1]}）',
        '内容が違うファイル 25：' + '、'.join(g_diff) + '（Config/override.txt は左が 0 バイト・右は2行。manifest.json は全ファイルの大きさとハッシュの一覧なので、ほかの変更がすべて映る）',
        '左のみ 10：' + '、'.join(sorted(lonly)), '右のみ 8：' + '、'.join(sorted(ronly)),
        '名前の大文字・小文字だけが違う 2 組（内容は同じ）：' + '、'.join(f'{a} ↔ {os.path.basename(b)}' for a, b in case) + '。別のファイルとして扱うと、左のみ・右のみが 2 つずつ増える（左のみ 12、右のみ 10）',
        '隠しファイル：.DS_Store が右（1.8.1）だけに 3 つ（' + '、'.join(ds) + '）。これを数えると右のみは 8＋2＋3＝13。Assets/Textures/UI/Thumbs.db と Assets/Data/Cache/.gitkeep（0 バイト）は左右にあって同じ',
        f'まとめ（隠しファイルも大文字小文字の違いも、そのまま数えた場合）：同一 {len(g_same):,}・相違 25・左のみ 12・右のみ 13')


# <<<end r07>>>
# <<<r08>>>
# ==========================================================================================
# R08 Web サービス会社 SRE：マニフェストのフォルダ（約90ファイル・4階層）、tfstate（4万行）、nginx のログ（3万行×2）、kubectl diff の出力、
#     CRLF と LF が混ざったシェルスクリプト、証明書（PEM）、crontab、Dockerfile
# ==========================================================================================
R08_SVC = [('api-gateway', 8080, '2.14.3', '2.15.0'), ('auth', 8081, '4.1.0', None), ('catalog', 8082, '7.3.2', None), ('cart', 8083, '3.9.4', None), ('order', 8084, '5.8.1', '5.9.0'),
           ('payment', 8085, '3.2.7', '3.2.8'), ('search', 8086, '1.12.0', None), ('notification', 8087, '2.0.5', None), ('web-front', 3000, '11.4.0', '11.5.2'), ('batch-report', 8089, '0.9.3', None)]


def _r08_deploy(svc, port, tag, env=(), gen=None):
    e = ''.join(f'            - name: {k}\n              value: {v}\n' for k, v in (('TZ', 'Asia/Tokyo'), ('LOG_LEVEL', 'info')) + tuple(env))
    return (f"apiVersion: apps/v1\nkind: Deployment\nmetadata:\n" + (f"  generation: {gen}\n" if gen else '') + f"  name: {svc}\n  namespace: shop\n  labels:\n    app.kubernetes.io/name: {svc}\n    app.kubernetes.io/part-of: shop\nspec:\n  replicas: 2\n  revisionHistoryLimit: 5\n  selector:\n    matchLabels:\n      app.kubernetes.io/name: {svc}\n"
            f"  strategy:\n    type: RollingUpdate\n    rollingUpdate:\n      maxSurge: 25%\n      maxUnavailable: 0\n  template:\n    metadata:\n      labels:\n        app.kubernetes.io/name: {svc}\n        app.kubernetes.io/part-of: shop\n      annotations:\n        prometheus.io/scrape: \"true\"\n        prometheus.io/port: \"9102\"\n"
            f"    spec:\n      serviceAccountName: {svc}\n      terminationGracePeriodSeconds: 45\n      containers:\n        - name: {svc}\n          image: registry.shop.example.co.jp/shop/{svc}:{tag}\n          imagePullPolicy: IfNotPresent\n          ports:\n            - name: http\n              containerPort: {port}\n            - name: metrics\n              containerPort: 9102\n"
            f"          envFrom:\n            - configMapRef:\n                name: {svc}-config\n          env:\n{e}          resources:\n            requests:\n              cpu: 200m\n              memory: 256Mi\n            limits:\n              cpu: \"1\"\n              memory: 512Mi\n"
            f"          readinessProbe:\n            httpGet:\n              path: /healthz\n              port: http\n            initialDelaySeconds: 5\n            periodSeconds: 10\n          livenessProbe:\n            httpGet:\n              path: /livez\n              port: http\n            initialDelaySeconds: 20\n            periodSeconds: 15\n            failureThreshold: 3\n"
            f"          securityContext:\n            runAsNonRoot: true\n            readOnlyRootFilesystem: true\n            allowPrivilegeEscalation: false\n      topologySpreadConstraints:\n        - maxSkew: 1\n          topologyKey: topology.kubernetes.io/zone\n          whenUnsatisfiable: ScheduleAnyway\n          labelSelector:\n            matchLabels:\n              app.kubernetes.io/name: {svc}\n")


def _r08_service(svc, port, style=0):
    if style == 1:   # キーの順番だけが違う
        return f"kind: Service\napiVersion: v1\nmetadata:\n  namespace: shop\n  name: {svc}\n  labels:\n    app.kubernetes.io/part-of: shop\n    app.kubernetes.io/name: {svc}\nspec:\n  selector:\n    app.kubernetes.io/name: {svc}\n  type: ClusterIP\n  ports:\n    - port: 80\n      name: http\n      protocol: TCP\n      targetPort: {port}\n    - port: 9102\n      name: metrics\n      protocol: TCP\n      targetPort: 9102\n"
    s = f"apiVersion: v1\nkind: Service\nmetadata:\n  name: {svc}\n  namespace: shop\n  labels:\n    app.kubernetes.io/name: {svc}\n    app.kubernetes.io/part-of: shop\nspec:\n  type: ClusterIP\n  selector:\n    app.kubernetes.io/name: {svc}\n  ports:\n    - name: http\n      port: 80\n      targetPort: {port}\n      protocol: TCP\n    - name: metrics\n      port: 9102\n      targetPort: 9102\n      protocol: TCP\n"
    if style == 2: s = s.replace('\n    - name', '\n  - name').replace('\n      port', '\n    port').replace('\n      targetPort', '\n    targetPort').replace('\n      protocol', '\n    protocol')     # 字下げだけが違う（リストを下げない書き方）
    return s


def _r08_hpa(svc, mn, mx, alt=False):
    if alt: return f"apiVersion: autoscaling/v2\nkind: HorizontalPodAutoscaler\nmetadata:\n  namespace: shop\n  name: {svc}\nspec:\n  maxReplicas: {mx}\n  minReplicas: {mn}\n  scaleTargetRef:\n    kind: Deployment\n    name: {svc}\n    apiVersion: apps/v1\n  metrics:\n    - resource:\n        target:\n          averageUtilization: 70\n          type: Utilization\n        name: cpu\n      type: Resource\n"
    return f"apiVersion: autoscaling/v2\nkind: HorizontalPodAutoscaler\nmetadata:\n  name: {svc}\n  namespace: shop\nspec:\n  scaleTargetRef:\n    apiVersion: apps/v1\n    kind: Deployment\n    name: {svc}\n  minReplicas: {mn}\n  maxReplicas: {mx}\n  metrics:\n    - type: Resource\n      resource:\n        name: cpu\n        target:\n          type: Utilization\n          averageUtilization: 70\n"


def r08(d):
    rnd = random.Random(4808); import yaml
    T8 = lambda s: s.encode('utf-8')
    # ---------------------------------------------------------------- マニフェストのフォルダ
    def tree(v):
        F = {}
        F['README.md'] = (f"# shop-manifests\n\nEC サイト「shop」の Kubernetes マニフェスト（kustomize）。\n\n## 構成\n\n- `base/` … 全環境で共通の定義（アプリごとに Deployment・Service・HPA・ConfigMap）\n- `overlays/production/` … 本番（replicas、環境変数）\n- `overlays/staging/` … 検証\n- `scripts/` … 反映・切り戻しのスクリプト\n\n"
                          f"## 反映の手順\n\n1. `kubectl diff -k overlays/production` で差分を確かめる\n2. 2人以上でレビューする（このフォルダと前回のフォルダを比べる）\n3. `scripts/deploy.sh production` を実行する\n4. 問題があれば `scripts/rollback.sh production` で切り戻す\n\n## 今回の反映\n\n| 項目 | 内容 |\n|---|---|\n| 反映日 | {'2026-11-27（金）22:00' if v else '2026-11-20（金）22:00'} |\n| 担当 | {'大西・古賀' if v else '大西・宮本'} |\n"
                          + ('| 主な変更 | api-gateway 2.15.0、order 5.9.0、payment 3.2.8、web-front 11.5.2、recommend の追加 |\n' if v else '| 主な変更 | catalog 7.3.2、cart の replicas 見直し |\n'))
        F['.gitignore'] = "# 秘密情報は置かない\n.env\n*.key\n*.pem\noverlays/*/secrets/*\n!overlays/*/secrets/.gitkeep\n\n# 作業ファイル\n*.swp\n.DS_Store\n" + ("rendered/\n" if v else '')
        F['.env.example'] = "# scripts/deploy.sh が読む設定の例（実際の値は .env に書く。.env はコミットしない）\nKUBE_CONTEXT=shop-prod-tokyo\nKUBE_NAMESPACE=shop\nSLACK_CHANNEL=#shop-deploy\nDEPLOY_TIMEOUT_SEC=" + ('600' if v else '300') + "\n" + ("DRY_RUN=false\n" if v else '')
        F['.yamllint'] = "extends: default\nrules:\n  line-length:\n    max: 160\n  indentation:\n    spaces: 2\n    indent-sequences: whatever\n  document-start: disable\n"
        F['.github/workflows/deploy.yml'] = ("name: deploy\non:\n  workflow_dispatch:\n    inputs:\n      environment:\n        description: 反映先（production / staging）\n        required: true\n        default: staging\njobs:\n  diff:\n    runs-on: ubuntu-24.04\n    steps:\n      - uses: actions/checkout@v4\n      - name: kubeconform\n        run: kustomize build overlays/${{ inputs.environment }} | kubeconform -strict -summary\n"
                                             "      - name: kubectl diff\n        run: kubectl diff -k overlays/${{ inputs.environment }} || true\n  deploy:\n    needs: diff\n    runs-on: ubuntu-24.04\n    environment: ${{ inputs.environment }}\n    steps:\n      - uses: actions/checkout@v4\n      - name: deploy\n        run: ./scripts/deploy.sh ${{ inputs.environment }}\n        timeout-minutes: " + ('20' if v else '10') + "\n")
        F['scripts/deploy.sh'] = ("#!/usr/bin/env bash\n# マニフェストを反映する。使い方：scripts/deploy.sh <production|staging>\nset -euo pipefail\n\ncd \"$(dirname \"$0\")/..\"\nsource scripts/lib/common.sh\n\nENVIRONMENT=\"${1:?反映先を指定してください（production / staging）}\"\nOVERLAY=\"overlays/${ENVIRONMENT}\"\n\nrequire_cmd kubectl\nrequire_cmd kustomize\nload_env\n\n"
                                  "log \"差分を確認します：${OVERLAY}\"\nkubectl --context \"${KUBE_CONTEXT}\" diff -k \"${OVERLAY}\" || true\n\nconfirm \"${ENVIRONMENT} に反映しますか？\"\n\nlog \"反映します\"\nkubectl --context \"${KUBE_CONTEXT}\" apply -k \"${OVERLAY}\"\n\nfor deploy in $(kubectl --context \"${KUBE_CONTEXT}\" -n \"${KUBE_NAMESPACE}\" get deploy -o name); do\n"
                                  "  kubectl --context \"${KUBE_CONTEXT}\" -n \"${KUBE_NAMESPACE}\" rollout status \"${deploy}\" --timeout=" + ('600s' if v else '300s') + "\ndone\n\nnotify \"${ENVIRONMENT} への反映が終わりました\"\n")
        F['scripts/rollback.sh'] = "#!/usr/bin/env bash\n# 1つ前のリビジョンへ切り戻す。使い方：scripts/rollback.sh <production|staging> [deployment]\nset -euo pipefail\n\ncd \"$(dirname \"$0\")/..\"\nsource scripts/lib/common.sh\n\nENVIRONMENT=\"${1:?反映先を指定してください}\"\nTARGET=\"${2:-}\"\nload_env\n\nif [[ -n \"${TARGET}\" ]]; then\n  kubectl --context \"${KUBE_CONTEXT}\" -n \"${KUBE_NAMESPACE}\" rollout undo \"deploy/${TARGET}\"\nelse\n  for deploy in $(kubectl --context \"${KUBE_CONTEXT}\" -n \"${KUBE_NAMESPACE}\" get deploy -o name); do\n    kubectl --context \"${KUBE_CONTEXT}\" -n \"${KUBE_NAMESPACE}\" rollout undo \"${deploy}\"\n  done\nfi\n\nnotify \"${ENVIRONMENT} を切り戻しました\"\n"
        F['scripts/lib/common.sh'] = ("#!/usr/bin/env bash\n# 共通の関数\n\n" + ("# ログを標準エラーに出す（時刻つき）\n" if v else "# ログを出す\n") + "log() {\n  echo \"[$(date '+%Y-%m-%d %H:%M:%S')] $*\" >&2\n}\n\n# コマンドがなければ止める\nrequire_cmd() {\n  command -v \"$1\" >/dev/null 2>&1 || { log \"$1 が見つかりません\"; exit 1; }\n}\n\n# .env を読む\nload_env() {\n  if [[ -f .env ]]; then\n    set -a; source .env; set +a\n  fi\n  : \"${KUBE_CONTEXT:?KUBE_CONTEXT が未設定です}\"\n  : \"${KUBE_NAMESPACE:=shop}\"\n}\n\n"
                                      "# y と答えたときだけ進む\nconfirm() {\n  read -r -p \"$1 [y/N] \" answer\n  [[ \"${answer}\" == \"y\" ]] || { log \"中止しました\"; exit 1; }\n}\n\n" + ("# Slack に知らせる（SLACK_WEBHOOK_URL がなければ何もしない）\n" if v else "# Slack に知らせる\n") + "notify() {\n  [[ -n \"${SLACK_WEBHOOK_URL:-}\" ]] || return 0\n  curl -fsS -X POST -H 'Content-Type: application/json' --data \"{\\\"channel\\\":\\\"${SLACK_CHANNEL}\\\",\\\"text\\\":\\\"$1\\\"}\" \"${SLACK_WEBHOOK_URL}\" >/dev/null\n}\n")
        if not v: F['scripts/migrate_2026-10.sh'] = "#!/usr/bin/env bash\n# 2026年10月の名前空間の移行（shop-v1 → shop）。移行が終わったので、次回の反映で削除する。\nset -euo pipefail\n\nfor kind in deploy svc hpa cm; do\n  kubectl -n shop-v1 get \"${kind}\" -o yaml | sed 's/namespace: shop-v1/namespace: shop/' | kubectl apply -f -\ndone\n"
        else: F['scripts/lib/hooks.sh'] = ''
        apps = [s[0] for s in R08_SVC] + (['recommend'] if v else [])
        F['base/kustomization.yaml'] = "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nnamespace: shop\nresources:\n  - namespace.yaml\n" + ''.join(f'  - apps/{a}\n' for a in apps) + "  - ingress/ingress.yaml\n  - ingress/certificate.yaml\n  - monitoring/servicemonitor.yaml\n  - monitoring/" + ('alert-rules.yaml' if v else 'alerts.yaml') + "\n"
        F['base/namespace.yaml'] = ("# shop の名前空間。\n" + ("# Pod Security Standards は restricted（2026-10 から）\n" if v else '') + "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: shop\n  labels:\n    pod-security.kubernetes.io/enforce: restricted\n    istio-injection: disabled\n")
        for svc, port, t0, t1 in R08_SVC + ([('recommend', 8090, '0.4.0', None)] if v else []):
            env = ()
            if v and svc == 'order': env = (('ORDER_OUTBOX_ENABLED', '"true"'),)
            if v and svc == 'search': env = (('SEARCH_SYNONYM_DICT', 'v20261125'),)
            b = f'base/apps/{svc}'; F[f'{b}/deployment.yaml'] = _r08_deploy(svc, port, t1 if (v and t1) else t0, env)
            F[f'{b}/service.yaml'] = _r08_service(svc, port, (1 if svc == 'auth' else 2 if svc == 'cart' else 0) if v else 0)
            F[f'{b}/hpa.yaml'] = _r08_hpa(svc, 2, 10 if svc in ('api-gateway', 'web-front') else 6, alt=bool(v and svc == 'notification'))
            cm = {'APP_ENV': 'production', 'HTTP_PORT': str(port), 'DB_HOST': f'{svc.replace("-", "")}-db.shop.internal', 'DB_POOL_SIZE': '20', 'CACHE_TTL_SEC': '300', 'REQUEST_TIMEOUT_MS': '3000'}
            if svc == 'api-gateway': cm['RATE_LIMIT_RPS'] = '300' if v else '200'; cm['UPSTREAM_KEEPALIVE'] = '64'
            cmt = {'payment': ('# 決済代行の接続先は Secret（payment-secret）にある。ここには置かない。\n', '# 決済代行会社の接続先・鍵は Secret（payment-secret）で管理する。この ConfigMap には書かないこと。\n')}.get(svc, ('', ''))[1 if v else 0]
            F[f'{b}/configmap.yaml'] = cmt + f"apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: {svc}-config\n  namespace: shop\ndata:\n" + ''.join(f'  {k}: "{x}"\n' for k, x in cm.items())
            F[f'{b}/kustomization.yaml'] = "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n  - deployment.yaml\n  - service.yaml\n  - hpa.yaml\n  - configmap.yaml\n"
        F['base/apps/web-front/nginx/default.conf'] = "server {\n    listen 3000;\n    server_name _;\n    root /usr/share/nginx/html;\n\n    include /etc/nginx/conf.d/security-headers.conf;\n\n    location / {\n        try_files $uri $uri/ /index.html;\n    }\n\n    location /api/ {\n        proxy_pass http://api-gateway.shop.svc.cluster.local;\n        proxy_set_header X-Request-Id $request_id;\n        proxy_read_timeout 30s;\n    }\n\n    location = /healthz {\n        access_log off;\n        return 200 'ok';\n    }\n}\n"
        F['base/apps/web-front/nginx/security-headers.conf'] = "add_header X-Content-Type-Options nosniff always;\nadd_header X-Frame-Options DENY always;\nadd_header Referrer-Policy strict-origin-when-cross-origin always;\nadd_header Strict-Transport-Security \"max-age=31536000; includeSubDomains\" always;\n"
        ing = ("apiVersion: networking.k8s.io/v1\nkind: Ingress\nmetadata:\n  name: shop\n  namespace: shop\n  annotations:\n    nginx.ingress.kubernetes.io/proxy-body-size: 8m\n    nginx.ingress.kubernetes.io/ssl-redirect: \"true\"\nspec:\n  ingressClassName: nginx\n  tls:\n    - hosts:\n        - shop.example.co.jp\n        - api.shop.example.co.jp\n      secretName: shop-tls\n  rules:\n    - host: shop.example.co.jp\n      http:\n        paths:\n          - path: /\n            pathType: Prefix\n            backend:\n              service:\n                name: web-front\n                port:\n                  number: 80\n"
               "    - host: api.shop.example.co.jp\n      http:\n        paths:\n          - path: /\n            pathType: Prefix\n            backend:\n              service:\n                name: api-gateway\n                port:\n                  number: 80\n")
        if v:      # 字下げだけが違う（全体を 2 → 4 つの空白で下げ直した）
            o_, st_ = [], []
            for l in ing.splitlines(True):
                n = len(l) - len(l.lstrip(' '))
                while st_ and n <= st_[-1][0]: st_.pop()
                nn = st_[-1][1] + 2 + 2 * (n - st_[-1][0] - 2) if st_ else 2 * n
                if l.lstrip(' ').startswith('- '): st_.append((n, nn))
                o_.append(' ' * nn + l.lstrip(' '))
            ing = ''.join(o_)
        F['base/ingress/ingress.yaml'] = ing
        F['base/ingress/certificate.yaml'] = "apiVersion: cert-manager.io/v1\nkind: Certificate\nmetadata:\n  name: shop-tls\n  namespace: shop\nspec:\n  secretName: shop-tls\n  issuerRef:\n    name: letsencrypt-prod\n    kind: ClusterIssuer\n  dnsNames:\n    - shop.example.co.jp\n    - api.shop.example.co.jp\n  renewBefore: 720h\n"
        F['base/monitoring/servicemonitor.yaml'] = "apiVersion: monitoring.coreos.com/v1\nkind: ServiceMonitor\nmetadata:\n  name: shop\n  namespace: shop\nspec:\n  selector:\n    matchLabels:\n      app.kubernetes.io/part-of: shop\n  endpoints:\n    - port: metrics\n      interval: 30s\n      path: /metrics\n"
        F['base/monitoring/' + ('alert-rules.yaml' if v else 'alerts.yaml')] = ("apiVersion: monitoring.coreos.com/v1\nkind: PrometheusRule\nmetadata:\n  name: shop-alerts\n  namespace: shop\nspec:\n  groups:\n    - name: shop.rules\n      rules:\n" + ''.join(
            f"        - alert: {n}\n          expr: {e}\n          for: {f}\n          labels:\n            severity: {sv}\n          annotations:\n            summary: {sm}\n" for n, e, f, sv, sm in [
                ('HighErrorRate', 'sum(rate(http_requests_total{namespace="shop",code=~"5.."}[5m])) / sum(rate(http_requests_total{namespace="shop"}[5m])) > 0.02', '5m', 'critical', '5xx の割合が 2% を超えています'),
                ('HighLatencyP99', 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{namespace="shop"}[5m])) by (le, service)) > 1.5', '10m', 'warning', 'p99 の応答時間が 1.5 秒を超えています'),
                ('PodCrashLooping', 'increase(kube_pod_container_status_restarts_total{namespace="shop"}[15m]) > 3', '5m', 'critical', 'Pod が再起動を繰り返しています'),
                ('HpaMaxedOut', 'kube_horizontalpodautoscaler_status_current_replicas{namespace="shop"} == kube_horizontalpodautoscaler_spec_max_replicas{namespace="shop"}', '15m', 'warning', 'HPA が上限に張り付いています'),
                ('CertificateExpiringSoon', 'certmanager_certificate_expiration_timestamp_seconds{namespace="shop"} - time() < 14 * 24 * 3600', '1h', 'warning', '証明書の期限が 14 日以内です')]))
        prod = {'api-gateway': 6, 'auth': 4, 'catalog': 5 if v else 3, 'cart': 6 if v else 4, 'order': 6, 'payment': 4, 'search': 3, 'notification': 2, 'web-front': 8, 'batch-report': 1}
        if v: prod['recommend'] = 2
        for envn, reps in (('production', prod), ('staging', {k: 1 for k in prod})):
            for svc, n in reps.items(): F[f'overlays/{envn}/patches/{svc}-replicas.yaml'] = f"apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {svc}\n  namespace: shop\nspec:\n  replicas: {n}\n"
            extra = ['patches/debug-toolbox.yaml'] if (envn == 'staging' and not v) else []
            F[f'overlays/{envn}/kustomization.yaml'] = ("apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nnamespace: shop\nresources:\n  - ../../base\n" + ("  - configmap-env.yaml\n" if envn == 'production' else '') + "patches:\n" + ''.join(f'  - path: patches/{svc}-replicas.yaml\n' for svc in reps) + ''.join(f'  - path: {x}\n' for x in extra)
                                                        + f"commonLabels:\n  environment: {envn}\n")
        F['overlays/production/configmap-env.yaml'] = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: shop-env\n  namespace: shop\ndata:\n  FEATURE_POINT_CAMPAIGN: \"" + ('true' if v else 'false') + "\"\n  FEATURE_NEW_CHECKOUT: \"true\"\n  MAINTENANCE_MODE: \"false\"\n  CDN_BASE_URL: \"https://cdn.shop.example.co.jp\"\n"
        F['overlays/production/secrets/.gitkeep'] = ''
        if not v: F['overlays/staging/patches/debug-toolbox.yaml'] = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: debug-toolbox\n  namespace: shop\nspec:\n  replicas: 1\n  selector:\n    matchLabels:\n      app: debug-toolbox\n  template:\n    metadata:\n      labels:\n        app: debug-toolbox\n    spec:\n      containers:\n        - name: toolbox\n          image: registry.shop.example.co.jp/tools/toolbox:1.3.0\n          command: [\"sleep\", \"infinity\"]\n"
        return {k: T8(x) for k, x in F.items()}
    TA, TB = tree(0), tree(1); dn0, dn1 = 'deploy_2026-11-20', 'deploy_2026-11-27'
    for nm_, T in ((dn0, TA), (dn1, TB)):
        for k, b in T.items(): wbytes(f'{d}/{nm_}/{k}', b)
    def scan(root):
        out = {}
        for dp, _, fs in os.walk(root):
            for f in fs: p = os.path.join(dp, f); out[os.path.relpath(p, root).replace(os.sep, '/')] = open(p, 'rb').read()
        return out
    GA, GB = scan(P(f'{d}/{dn0}/x')[:-2]), scan(P(f'{d}/{dn1}/x')[:-2]); assert GA == TA and GB == TB
    for G_ in (GA, GB):
        for k, b in G_.items():
            if k.endswith(('.yaml', '.yml')) and b: yaml.safe_load(b.decode('utf-8'))
    g_diff = sorted(k for k in GA if k in GB and GA[k] != GB[k]); g_same = sorted(k for k in GA if k in GB and GA[k] == GB[k]); g_l = sorted(k for k in GA if k not in GB); g_r = sorted(k for k in GB if k not in GA)
    sem = [k for k in g_diff if k.endswith(('.yaml', '.yml')) and yaml.safe_load(GA[k].decode()) == yaml.safe_load(GB[k].decode())]      # 読んだ中身は同じ（順番・字下げ・コメントだけの違い）
    k_order = ['base/apps/auth/service.yaml', 'base/apps/notification/hpa.yaml']; k_ind = ['base/apps/cart/service.yaml', 'base/ingress/ingress.yaml']; k_cmt = ['base/apps/payment/configmap.yaml', 'base/namespace.yaml', 'scripts/lib/common.sh']
    k_real = ['.env.example', '.github/workflows/deploy.yml', '.gitignore', 'README.md', 'base/apps/api-gateway/configmap.yaml', 'base/apps/api-gateway/deployment.yaml', 'base/apps/order/deployment.yaml', 'base/apps/payment/deployment.yaml', 'base/apps/search/deployment.yaml', 'base/apps/web-front/deployment.yaml',
              'base/kustomization.yaml', 'overlays/production/configmap-env.yaml', 'overlays/production/kustomization.yaml', 'overlays/production/patches/cart-replicas.yaml', 'overlays/production/patches/catalog-replicas.yaml', 'overlays/staging/kustomization.yaml', 'scripts/deploy.sh']
    assert sorted(sem) == sorted(k_order + k_ind + k_cmt[:2]) and g_diff == sorted(k_real + k_order + k_ind + k_cmt), sorted(set(g_diff) ^ set(k_real + k_order + k_ind + k_cmt))
    strip_c = lambda b: [l for l in b.decode().splitlines() if not l.lstrip().startswith('#')]
    assert all(strip_c(GA[k]) == strip_c(GB[k]) for k in k_cmt) and all([l.strip() for l in GA[k].decode().splitlines()] == [l.strip() for l in GB[k].decode().splitlines()] for k in k_ind)
    nch = lambda k: sum(1 for x, y in zip(GA[k].decode().splitlines(), GB[k].decode().splitlines()) if x != y)
    assert GA['base/monitoring/alerts.yaml'] == GB['base/monitoring/alert-rules.yaml'] and g_l == ['base/monitoring/alerts.yaml', 'overlays/staging/patches/debug-toolbox.yaml', 'scripts/migrate_2026-10.sh'] and len(g_r) == 9 and (len(GA), len(GB)) == (92, 98)
    dots = sorted(k for k in GB if any(p.startswith('.') for p in k.split('/'))); empt = sorted(k for k in GB if not GB[k]); assert max(k.count('/') for k in GB) == 4
    def ld(k):
        a, b = GA[k].decode().splitlines(), GB[k].decode().splitlines(); sm = difflib.SequenceMatcher(None, a, b, autojunk=False); o = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != 'equal': o.append((f'{i1 + 1}行目 ' if i2 > i1 else f'{j1 + 1}行目に追加 ') + ' / '.join(x.strip() for x in a[i1:i2]) + (' → ' if i2 > i1 and j2 > j1 else '') + ' / '.join(x.strip() for x in b[j1:j2]))
        return '；'.join(o)
    key(d, f'■ マニフェストのフォルダ「{dn0}/」（{len(GA)} ファイル）と「{dn1}/」（{len(GB)} ファイル）。フォルダは4階層まで（base/apps/web-front/nginx/）。すべて UTF-8・LF',
        f'内容が同じ {len(g_same)}・内容（バイト）が違う {len(g_diff)}・左のみ {len(g_l)}・右のみ {len(g_r)}。内容が違う {len(g_diff)} のうち、設定として意味のある変更は 17、残り 7 は「順番・字下げ・コメントだけ」の違い',
        '【image のタグ 4】' + '　／　'.join(f'{k}：{ld(k)}' for k in ['base/apps/api-gateway/deployment.yaml', 'base/apps/payment/deployment.yaml', 'base/apps/web-front/deployment.yaml']) + '　／　base/apps/order/deployment.yaml（5.8.1→5.9.0。次の env の追加と同じファイル）',
        '【env の追加 2】base/apps/order/deployment.yaml：' + ld('base/apps/order/deployment.yaml') + '　／　base/apps/search/deployment.yaml：' + ld('base/apps/search/deployment.yaml'),
        '【replicas 2】' + '　／　'.join(f'{k}：{ld(k)}' for k in ['overlays/production/patches/cart-replicas.yaml', 'overlays/production/patches/catalog-replicas.yaml']),
        '【そのほかの意味のある変更 10】' + '　／　'.join(f'{k}：{ld(k)}' for k in ['base/apps/api-gateway/configmap.yaml', 'overlays/production/configmap-env.yaml', 'base/kustomization.yaml', 'overlays/production/kustomization.yaml', 'overlays/staging/kustomization.yaml', '.env.example', '.gitignore', '.github/workflows/deploy.yml', 'scripts/deploy.sh'])
        + '　／　README.md：' + ld('README.md'),
        '【キーの順番だけが違う 2】' + '、'.join(k_order) + '（キーを書く順番を入れ替えただけ。YAML として読んだ中身は同じ。テキストとしては多くの行が違って見える）',
        f'【字下げだけが違う 2】base/apps/cart/service.yaml（ports のリストを下げない書き方に変えた。{nch("base/apps/cart/service.yaml")} 行）、base/ingress/ingress.yaml（全体の字下げの幅を 2→4 に変えた。{nch("base/ingress/ingress.yaml")} 行）。行の数は同じで、行頭の空白の数だけが違う。YAML として読んだ中身は同じ',
        '【コメントだけが違う 3】' + '　／　'.join(f'{k}：{ld(k)}' for k in k_cmt),
        '【ファイル名の変更 1】base/monitoring/alerts.yaml（左のみ）→ base/monitoring/alert-rules.yaml（右のみ）。中身は1バイトも違わない。base/kustomization.yaml の参照も書き換わっている',
        '【左のみ 3】' + '、'.join(g_l) + '（うち alerts.yaml は名前の変更）', '【右のみ 9】' + '、'.join(g_r) + '（recommend の追加で 7、名前の変更で 1、空のファイル scripts/lib/hooks.sh）',
        '【空のファイル（0 バイト）】' + '、'.join(empt) + '（.gitkeep は左右にあって同じ。hooks.sh は右のみ）',
        f'【ドットで始まるファイル・フォルダ {len(dots)}】' + '、'.join(dots) + '（.yamllint と .gitkeep は左右で同じ。.env.example・.gitignore・.github/workflows/deploy.yml は内容が違う）。フォルダ比較の一覧に、これらが出ること')

    # ---------------------------------------------------------------- terraform.tfstate（JSON・字下げ2・約4万行）
    PROV = 'provider["registry.terraform.io/hashicorp/aws"]'; ACCT = '482915730164'; REG = 'ap-northeast-1'
    def tf(v):
        RS = []
        def hx(r, n): return ''.join(r.choice('0123456789abcdef') for _ in range(n))
        def tags(name, role): return {'CostCenter': 'CC-1042', 'Environment': 'production', 'ManagedBy': 'terraform', 'Name': name, 'Role': role, 'Service': 'shop'}
        def res(typ, name, attrs, deps=(), sv=0):
            RS.append({'mode': 'managed', 'type': typ, 'name': name, 'provider': PROV, 'instances': [{'schema_version': sv, 'attributes': attrs, 'sensitive_attributes': [], 'private': base64.b64encode(json.dumps({'schema_version': str(sv)}).encode()).decode(), 'dependencies': sorted(deps)}]})
        def rule(r, desc, port, cidr): return {'cidr_blocks': [cidr], 'description': desc, 'from_port': port, 'ipv6_cidr_blocks': [], 'prefix_list_ids': [], 'protocol': 'tcp', 'security_groups': [], 'self': False, 'to_port': port}
        def sg(name, role, nrules):
            r = random.Random(f'sg.{name}'); i = 'sg-0' + hx(r, 16); t = tags(f'shop-prod-{name.replace("_", "-")}', role)
            ing = [rule(r, f'{role} from {["alb", "bastion", "monitor", "vpn", "batch", "office", "peer-vpc", "nat"][k % 8]} #{k + 1}', r.choice([22, 80, 443, 3306, 5432, 6379, 8080, 8443, 9100, 9102]), f'10.{r.randrange(20, 28)}.{r.randrange(0, 255)}.0/24') for k in range(nrules)]
            res('aws_security_group', name, {'arn': f'arn:aws:ec2:{REG}:{ACCT}:security-group/{i}', 'description': f'shop production {role}', 'egress': [{'cidr_blocks': ['0.0.0.0/0'], 'description': 'all outbound', 'from_port': 0, 'ipv6_cidr_blocks': [], 'prefix_list_ids': [], 'protocol': '-1', 'security_groups': [], 'self': False, 'to_port': 0}],
                                              'id': i, 'ingress': ing, 'name': f'shop-prod-{name.replace("_", "-")}', 'name_prefix': '', 'owner_id': ACCT, 'revoke_rules_on_delete': False, 'tags': t, 'tags_all': t, 'timeouts': None, 'vpc_id': 'vpc-0c41d7e2a95b3f608'}, ['aws_vpc.main'], 1)
        res('aws_vpc', 'main', {'arn': f'arn:aws:ec2:{REG}:{ACCT}:vpc/vpc-0c41d7e2a95b3f608', 'assign_generated_ipv6_cidr_block': False, 'cidr_block': '10.20.0.0/16', 'default_network_acl_id': 'acl-07be3d15a0c9e4412', 'default_route_table_id': 'rtb-0a6f2e81d4b7c3905', 'default_security_group_id': 'sg-04d1b8a7e63f2c590', 'dhcp_options_id': 'dopt-0e2c9a4b71f6d3508',
                                'enable_dns_hostnames': True, 'enable_dns_support': True, 'enable_network_address_usage_metrics': False, 'id': 'vpc-0c41d7e2a95b3f608', 'instance_tenancy': 'default', 'ipv4_ipam_pool_id': None, 'ipv4_netmask_length': None, 'ipv6_association_id': '', 'ipv6_cidr_block': '', 'main_route_table_id': 'rtb-0a6f2e81d4b7c3905', 'owner_id': ACCT, 'tags': tags('shop-prod-vpc', 'network'), 'tags_all': tags('shop-prod-vpc', 'network')}, sv=1)
        subn = []
        for ti, tier in enumerate(['public', 'private', 'db', 'cache']):
            for ai, az in enumerate('acd'):
                for k in (1, 2):
                    n = f'{tier}_{az}{k}'; r = random.Random(f'sn.{n}'); i = 'subnet-0' + hx(r, 16); subn.append((n, i, az)); t = tags(f'shop-prod-{tier}-{az}{k}', 'network')
                    res('aws_subnet', n, {'arn': f'arn:aws:ec2:{REG}:{ACCT}:subnet/{i}', 'assign_ipv6_address_on_creation': False, 'availability_zone': f'{REG}{az}', 'availability_zone_id': f'apne1-az{ai + 1}', 'cidr_block': f'10.20.{ti * 48 + ai * 8 + k * 2}.0/23', 'customer_owned_ipv4_pool': '', 'enable_dns64': False,
                                          'enable_resource_name_dns_a_record_on_launch': False, 'enable_resource_name_dns_aaaa_record_on_launch': False, 'id': i, 'ipv6_cidr_block': '', 'ipv6_cidr_block_association_id': '', 'ipv6_native': False, 'map_customer_owned_ip_on_launch': False, 'map_public_ip_on_launch': tier == 'public', 'outpost_arn': '', 'owner_id': ACCT,
                                          'private_dns_hostname_type_on_launch': 'ip-name', 'tags': t, 'tags_all': t, 'timeouts': None, 'vpc_id': 'vpc-0c41d7e2a95b3f608'}, ['aws_vpc.main'], 1)
        groups = [('web', 20, 'm6i.large'), ('api', 16, 'c6i.xlarge'), ('worker', 12, 'm6i.xlarge'), ('batch', 8, 'r6i.large'), ('monitor', 4, 't3.large'), ('bastion', 2, 't3.small')]
        for g, n, _ in groups + [('alb', 1, ''), ('db', 1, ''), ('cache', 1, ''), ('search', 1, ''), ('office_vpn', 1, ''), ('ci_runner', 1, ''), ('internal_tools', 1, ''), ('mail_relay', 1, ''), ('log_collector', 1, ''), ('nat', 1, ''), ('peer_analytics', 1, ''), ('peer_backoffice', 1, '')]:
            sg(g, g, 4 + len(g) % 5)
        for g, n, ityp in groups + ([('recommend', 3, 'c6i.large')] if v else []):
            multi = []; sgk = 'api' if g == 'recommend' else g
            for k in range(n):
                nm_ = f'{g}_{k + 1:02d}'; r = random.Random(f'i.{nm_}'); i = 'i-0' + hx(r, 16); sn = subn[(k * 5 + len(g)) % len(subn)]; ip = f'10.20.{r.randrange(2, 190)}.{r.randrange(4, 250)}'; t = tags(f'shop-prod-{g}-{k + 1:02d}', g); vol = 'vol-0' + hx(r, 16); eni = 'eni-0' + hx(r, 16)
                it = {'web': 'm6i.xlarge', 'api': 'c6i.2xlarge'}[g] if (v and g in ('web', 'api') and k < 10) else ityp
                attrs = ({'ami': 'ami-0a1b2c3d4e5f60718', 'arn': f'arn:aws:ec2:{REG}:{ACCT}:instance/{i}', 'associate_public_ip_address': g == 'bastion', 'availability_zone': f'{REG}{sn[2]}', 'capacity_reservation_specification': [{'capacity_reservation_preference': 'open', 'capacity_reservation_target': []}],
                                          'cpu_core_count': 2, 'cpu_options': [{'amd_sev_snp': '', 'core_count': 2, 'threads_per_core': 2}], 'cpu_threads_per_core': 2, 'credit_specification': [], 'disable_api_stop': False, 'disable_api_termination': g in ('web', 'api'), 'ebs_block_device': [], 'ebs_optimized': True,
                                          'enclave_options': [{'enabled': False}], 'ephemeral_block_device': [], 'get_password_data': False, 'hibernation': False, 'host_id': '', 'host_resource_group_arn': None, 'iam_instance_profile': f'shop-prod-{g}', 'id': i, 'instance_initiated_shutdown_behavior': 'stop', 'instance_lifecycle': '', 'instance_market_options': [],
                                          'instance_state': 'running', 'instance_type': it, 'ipv6_address_count': 0, 'ipv6_addresses': [], 'key_name': 'shop-prod-2026', 'launch_template': [], 'maintenance_options': [{'auto_recovery': 'default'}],
                                          'metadata_options': [{'http_endpoint': 'enabled', 'http_protocol_ipv6': 'disabled', 'http_put_response_hop_limit': 1, 'http_tokens': 'required', 'instance_metadata_tags': 'disabled'}], 'monitoring': True, 'network_interface': [], 'outpost_arn': '', 'password_data': '', 'placement_group': '', 'placement_partition_number': 0,
                                          'primary_network_interface_id': eni, 'private_dns': f'ip-{ip.replace(".", "-")}.{REG}.compute.internal', 'private_dns_name_options': [{'enable_resource_name_dns_a_record': False, 'enable_resource_name_dns_aaaa_record': False, 'hostname_type': 'ip-name'}], 'private_ip': ip, 'public_dns': '', 'public_ip': '',
                                          'root_block_device': [{'delete_on_termination': True, 'device_name': '/dev/xvda', 'encrypted': True, 'iops': 3000, 'kms_key_id': f'arn:aws:kms:{REG}:{ACCT}:key/3f6a1c2e-84d7-4b0e-9a15-7c2d8e4f0b61', 'tags': {}, 'tags_all': {}, 'throughput': 125, 'volume_id': vol, 'volume_size': 50 if g != 'batch' else 200, 'volume_type': 'gp3'}],
                                          'secondary_private_ips': [], 'security_groups': [], 'source_dest_check': True, 'spot_instance_request_id': '', 'subnet_id': sn[1], 'tags': t, 'tags_all': t, 'tenancy': 'default', 'timeouts': None, 'user_data': hashlib.sha1(f'ud-{g}'.encode()).hexdigest(), 'user_data_base64': base64.b64encode((f'#!/bin/bash\nset -eu\nhostnamectl set-hostname shop-prod-{g}-{k + 1:02d}\n' + ''.join(f'echo "{x}=$(/opt/shop/bin/param get /shop/prod/{g}/{x})" >> /etc/shop/env\n' for x in ('DB_HOST', 'DB_USER', 'CACHE_HOST', 'QUEUE_URL', 'LOG_BUCKET', 'API_TOKEN_PATH', 'SENTRY_DSN_PATH', 'FEATURE_FLAGS')) + f'systemctl enable --now shop-{g}.service\n').encode()).decode(), 'user_data_replace_on_change': False,
                                          'volume_tags': None, 'vpc_security_group_ids': ['sg-0' + hx(random.Random(f'sg.{sgk}'), 16)]}); deps = [f'aws_security_group.{sgk}', f'aws_subnet.{sn[0]}', 'aws_vpc.main']
                if g == 'recommend': multi.append({'index_key': k, 'schema_version': 1, 'attributes': attrs, 'sensitive_attributes': [], 'private': base64.b64encode(json.dumps({'schema_version': '1'}).encode()).decode(), 'dependencies': sorted(deps)}); continue
                res('aws_instance', nm_, attrs, deps, 1)
                for dv in ('data',) if g in ('batch', 'monitor', 'worker') else ():
                    r2 = random.Random(f'v.{nm_}'); vi = 'vol-0' + hx(r2, 16)
                    res('aws_ebs_volume', f'{nm_}_{dv}', {'arn': f'arn:aws:ec2:{REG}:{ACCT}:volume/{vi}', 'availability_zone': f'{REG}{sn[2]}', 'encrypted': True, 'final_snapshot': False, 'id': vi, 'iops': 3000, 'kms_key_id': f'arn:aws:kms:{REG}:{ACCT}:key/3f6a1c2e-84d7-4b0e-9a15-7c2d8e4f0b61', 'multi_attach_enabled': False, 'outpost_arn': '', 'size': 500, 'snapshot_id': '',
                                                          'tags': tags(f'shop-prod-{g}-{k + 1:02d}-{dv}', g), 'tags_all': tags(f'shop-prod-{g}-{k + 1:02d}-{dv}', g), 'throughput': 250, 'timeouts': None, 'type': 'gp3'}, [f'aws_instance.{nm_}'])
        RS.append({'mode': 'managed', 'type': 'aws_instance', 'name': 'recommend', 'provider': PROV, 'instances': multi}) if v else None
        hosts = ['www', 'api', 'img', 'static', 'admin', 'batch', 'grafana', 'kibana', 'mail', 'vpn'] + [f'web{k:02d}' for k in range(1, 21)] + [f'api{k:02d}' for k in range(1, 17)] + [f'worker{k:02d}' for k in range(1, 13)] + [f'{x}-{y}' for x in ('db', 'cache', 'search', 'queue') for y in ('primary', 'replica1', 'replica2', 'reader')]
        for k, h in enumerate(hosts):
            for z, zid in (('shop.example.co.jp', 'Z08412973KQ2M5XB7D1TA'), ('shop.internal', 'Z03391582JH7P4WN6C8RE')):
                r = random.Random(f'r53.{h}.{z}')
                res('aws_route53_record', f'{h.replace("-", "_")}_{"public" if "example" in z else "internal"}', {'alias': [], 'allow_overwrite': None, 'cidr_routing_policy': [], 'failover_routing_policy': [], 'fqdn': f'{h}.{z}', 'geolocation_routing_policy': [], 'geoproximity_routing_policy': [], 'health_check_id': '', 'id': f'{zid}_{h}.{z}_A',
                                                    'latency_routing_policy': [], 'multivalue_answer_routing_policy': None, 'name': f'{h}.{z}', 'records': [f'10.20.{r.randrange(2, 190)}.{r.randrange(4, 250)}'], 'set_identifier': '', 'ttl': 60 if k < 10 else 300, 'type': 'A', 'weighted_routing_policy': [], 'zone_id': zid}, [], 2)
        for k, b in enumerate(['assets', 'images', 'logs-alb', 'logs-app', 'logs-audit', 'backup-db', 'backup-files', 'export', 'import', 'reports', 'invoices', 'tfstate', 'artifacts', 'static-web', 'mail-archive', 'analytics-raw', 'analytics-mart', 'tmp-upload', 'thumbnails', 'cdn-origin']):
            n = f'shop-prod-{b}-{ACCT[-4:]}'; t = tags(n, 'storage')
            res('aws_s3_bucket', b.replace('-', '_'), {'acceleration_status': '', 'acl': None, 'arn': f'arn:aws:s3:::{n}', 'bucket': n, 'bucket_domain_name': f'{n}.s3.amazonaws.com', 'bucket_prefix': '', 'bucket_regional_domain_name': f'{n}.s3.{REG}.amazonaws.com', 'cors_rule': [], 'force_destroy': False,
                                                       'grant': [{'id': hashlib.sha256(b'owner').hexdigest(), 'permissions': ['FULL_CONTROL'], 'type': 'CanonicalUser', 'uri': ''}], 'hosted_zone_id': 'Z2M4EHUR26P7ZW', 'id': n,
                                                       'lifecycle_rule': [{'abort_incomplete_multipart_upload_days': 7, 'enabled': True, 'expiration': [{'date': '', 'days': 90 + k * 30, 'expired_object_delete_marker': False}], 'id': 'expire-old', 'noncurrent_version_expiration': [{'days': 30}], 'noncurrent_version_transition': [], 'prefix': '', 'tags': {}, 'transition': [{'date': '', 'days': 30, 'storage_class': 'STANDARD_IA'}]}],
                                                       'logging': [], 'object_lock_configuration': [], 'object_lock_enabled': False, 'policy': '', 'region': REG, 'replication_configuration': [], 'request_payer': 'BucketOwner',
                                                       'server_side_encryption_configuration': [{'rule': [{'apply_server_side_encryption_by_default': [{'kms_master_key_id': '', 'sse_algorithm': 'AES256'}], 'bucket_key_enabled': True}]}], 'tags': t, 'tags_all': t, 'timeouts': None, 'versioning': [{'enabled': k % 3 != 0, 'mfa_delete': False}], 'website': [], 'website_domain': None, 'website_endpoint': None}, [])
        for g in [x[0] for x in groups] + ['lambda_thumbnail', 'lambda_mail', 'lambda_export', 'ecs_task', 'ecs_exec', 'ci_deploy', 'backup', 'flow_logs', 'rds_monitoring', 'eks_node', 'eks_cluster', 'firehose', 'glue', 'athena']:
            r = random.Random(f'iam.{g}'); n = f'shop-prod-{g.replace("_", "-")}'; t = tags(n, 'iam')
            pol = json.dumps({'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Principal': {'Service': 'ec2.amazonaws.com' if g in [x[0] for x in groups] else g.split('_')[0] + '.amazonaws.com'}, 'Action': 'sts:AssumeRole'}]}, separators=(',', ':'))
            res('aws_iam_role', g, {'arn': f'arn:aws:iam::{ACCT}:role/{n}', 'assume_role_policy': pol, 'create_date': f'2025-{r.randrange(1, 13):02d}-{r.randrange(1, 29):02d}T0{r.randrange(1, 9)}:{r.randrange(10, 59)}:{r.randrange(10, 59)}Z', 'description': f'shop production {g}', 'force_detach_policies': False, 'id': n, 'inline_policy': [], 'managed_policy_arns': [], 'max_session_duration': 3600, 'name': n, 'name_prefix': '', 'path': '/', 'permissions_boundary': '', 'tags': t, 'tags_all': t, 'unique_id': 'AROA' + hx(r, 17).upper()}, [])
            for pa in ['AmazonSSMManagedInstanceCore', 'CloudWatchAgentServerPolicy', 'AmazonS3ReadOnlyAccess'][:2 + len(g) % 2]:
                res('aws_iam_role_policy_attachment', f'{g}_{pa}', {'id': f'{n}-{hx(r, 26)}', 'policy_arn': f'arn:aws:iam::aws:policy/{pa}', 'role': n}, [f'aws_iam_role.{g}'])
        metrics = [('CPUUtilization', 80, 'AWS/EC2'), ('StatusCheckFailed', 1, 'AWS/EC2'), ('mem_used_percent', 85, 'CWAgent'), ('disk_used_percent', 80, 'CWAgent'), ('NetworkOut', 900000000, 'AWS/EC2')]
        for g, n, _ in groups:
            for k in range(n):
                for m, th, nsp in metrics:
                    nm_ = f'{g}_{k + 1:02d}_{m.lower()}'; an = f'shop-prod-{g}-{k + 1:02d}-{m}'
                    res('aws_cloudwatch_metric_alarm', nm_, {'actions_enabled': True, 'alarm_actions': [f'arn:aws:sns:{REG}:{ACCT}:shop-prod-alert'], 'alarm_description': f'{g}-{k + 1:02d} の {m} が {th} を超えた', 'alarm_name': an, 'arn': f'arn:aws:cloudwatch:{REG}:{ACCT}:alarm:{an}', 'comparison_operator': 'GreaterThanOrEqualToThreshold', 'datapoints_to_alarm': 3,
                                                             'dimensions': {'InstanceId': 'i-0' + hx(random.Random(f'i.{g}_{k + 1:02d}'), 16)}, 'evaluate_low_sample_count_percentiles': '', 'evaluation_periods': 3, 'extended_statistic': '', 'id': an, 'insufficient_data_actions': [], 'metric_name': m, 'metric_query': [], 'namespace': nsp, 'ok_actions': [f'arn:aws:sns:{REG}:{ACCT}:shop-prod-alert'],
                                                             'period': 300, 'statistic': 'Average', 'tags': {}, 'tags_all': {'ManagedBy': 'terraform', 'Service': 'shop'}, 'threshold': th, 'threshold_metric_id': '', 'treat_missing_data': 'breaching' if m == 'StatusCheckFailed' else 'missing', 'unit': ''}, [f'aws_instance.{g}_{k + 1:02d}'], 1)
        for k, tg in enumerate(['web', 'api', 'admin', 'img', 'static', 'grafana', 'kibana', 'batch_api', 'internal_api', 'webhook'] * 3):
            n = f'shop-prod-{tg.replace("_", "-")}-{"abc"[k // 10]}'; r = random.Random(f'tg.{n}'); arn = f'arn:aws:elasticloadbalancing:{REG}:{ACCT}:targetgroup/{n}/{hx(r, 16)}'; t = tags(n, 'lb')
            res('aws_lb_target_group', f'{tg}_{"abc"[k // 10]}', {'arn': arn, 'arn_suffix': arn.split(':')[-1], 'connection_termination': None, 'deregistration_delay': '60', 'health_check': [{'enabled': True, 'healthy_threshold': 3, 'interval': 10, 'matcher': '200', 'path': '/healthz', 'port': 'traffic-port', 'protocol': 'HTTP', 'timeout': 5, 'unhealthy_threshold': 2}], 'id': arn, 'ip_address_type': 'ipv4',
                                                                  'lambda_multi_value_headers_enabled': False, 'load_balancer_arns': [f'arn:aws:elasticloadbalancing:{REG}:{ACCT}:loadbalancer/app/shop-prod-alb/5d2f8a1c9e47b360'], 'load_balancing_algorithm_type': 'least_outstanding_requests', 'load_balancing_anomaly_mitigation': 'off', 'load_balancing_cross_zone_enabled': 'use_load_balancer_configuration', 'name': n, 'name_prefix': '',
                                                                  'port': 8080 + k % 10, 'preserve_client_ip': None, 'protocol': 'HTTP', 'protocol_version': 'HTTP1', 'proxy_protocol_v2': False, 'slow_start': 30, 'stickiness': [{'cookie_duration': 86400, 'cookie_name': '', 'enabled': False, 'type': 'lb_cookie'}], 'tags': t, 'tags_all': t,
                                                                  'target_failover': [{'on_deregistration': None, 'on_unhealthy': None}], 'target_health_state': [{'enable_unhealthy_connection_termination': None}], 'target_type': 'instance', 'vpc_id': 'vpc-0c41d7e2a95b3f608'}, ['aws_vpc.main'])
        for k, db in enumerate(['order_primary', 'order_replica1', 'order_replica2', 'catalog_primary', 'catalog_replica1', 'auth_primary', 'auth_replica1', 'report_primary']):
            n = f'shop-prod-{db.replace("_", "-")}'; r = random.Random(f'db.{db}'); t = tags(n, 'db'); ep = f'{n}.c{hx(r, 11)}.{REG}.rds.amazonaws.com'
            res('aws_db_instance', db, {'address': ep, 'allocated_storage': 500, 'allow_major_version_upgrade': None, 'apply_immediately': False, 'arn': f'arn:aws:rds:{REG}:{ACCT}:db:{n}', 'auto_minor_version_upgrade': False, 'availability_zone': f'{REG}{"acd"[k % 3]}', 'backup_retention_period': 14 if 'primary' in db else 0, 'backup_target': 'region', 'backup_window': '17:10-17:40',
                                        'blue_green_update': [], 'ca_cert_identifier': 'rds-ca-rsa2048-g1', 'character_set_name': '', 'copy_tags_to_snapshot': True, 'custom_iam_instance_profile': '', 'customer_owned_ip_enabled': False, 'db_name': db.split('_')[0], 'db_subnet_group_name': 'shop-prod-db', 'delete_automated_backups': True, 'deletion_protection': True, 'domain': '', 'domain_iam_role_name': '',
                                        'enabled_cloudwatch_logs_exports': ['postgresql', 'upgrade'], 'endpoint': f'{ep}:5432', 'engine': 'postgres', 'engine_version': '16.4', 'engine_version_actual': '16.4', 'final_snapshot_identifier': None, 'hosted_zone_id': 'Z24O6O9L7SGTNB', 'iam_database_authentication_enabled': True, 'id': 'db-' + hx(r, 26).upper(), 'identifier': n, 'identifier_prefix': '',
                                        'instance_class': 'db.r6g.2xlarge' if 'primary' in db else 'db.r6g.xlarge', 'iops': 12000, 'kms_key_id': f'arn:aws:kms:{REG}:{ACCT}:key/3f6a1c2e-84d7-4b0e-9a15-7c2d8e4f0b61', 'latest_restorable_time': '', 'license_model': 'postgresql-license', 'listener_endpoint': [], 'maintenance_window': 'sun:18:00-sun:18:30', 'manage_master_user_password': None,
                                        'master_user_secret': [], 'max_allocated_storage': 2000, 'monitoring_interval': 60, 'monitoring_role_arn': f'arn:aws:iam::{ACCT}:role/shop-prod-rds-monitoring', 'multi_az': 'primary' in db, 'nchar_character_set_name': '', 'network_type': 'IPV4', 'option_group_name': 'default:postgres-16', 'parameter_group_name': 'shop-prod-pg16', 'password': None,
                                        'performance_insights_enabled': True, 'performance_insights_retention_period': 7, 'port': 5432, 'publicly_accessible': False, 'replica_mode': '', 'replicas': [], 'replicate_source_db': '' if 'primary' in db else f'shop-prod-{db.split("_")[0]}-primary', 'resource_id': 'db-' + hx(r, 26).upper(), 'restore_to_point_in_time': [], 's3_import': [], 'skip_final_snapshot': False,
                                        'snapshot_identifier': None, 'status': 'available', 'storage_encrypted': True, 'storage_throughput': 500, 'storage_type': 'gp3', 'tags': t, 'tags_all': t, 'timeouts': None, 'timezone': '', 'username': 'shop_admin', 'vpc_security_group_ids': ['sg-0' + hx(random.Random('sg.db'), 16)]}, ['aws_security_group.db', 'aws_iam_role.rds_monitoring'], 2)
        RS.sort(key=lambda x: (x['type'], x['name']))
        return {'version': 4, 'terraform_version': '1.9.8', 'serial': 413 if v else 412, 'lineage': '7c2f4e18-3b9a-4d60-a1f5-92e8c04b6d37', 'outputs': {'alb_dns_name': {'value': 'shop-prod-alb-1482915730.ap-northeast-1.elb.amazonaws.com', 'type': 'string'}, 'vpc_id': {'value': 'vpc-0c41d7e2a95b3f608', 'type': 'string'},
                'web_instance_count': {'value': 20, 'type': 'number'}}, 'resources': RS, 'check_results': None}
    s0, s1 = tf(0), tf(1); j0 = json.dumps(s0, indent=2, ensure_ascii=False) + '\n'; j1 = json.dumps(s1, indent=2, ensure_ascii=False) + '\n'
    text(f'{d}/tfstate/terraform.tfstate.backup', j0); text(f'{d}/tfstate/terraform.tfstate', j1)
    a_, b_ = _lines_of(f'{d}/tfstate/terraform.tfstate.backup'), _lines_of(f'{d}/tfstate/terraform.tfstate'); la, lb = len(a_) - 1, len(b_) - 1
    ins0 = _lineno(b_, '"name": "recommend",') - 4; ins_n = lb - la      # 挿入が始まる行（0始まり。リソースの「{」の行）と、その行数
    assert b_[ins0 + ins_n:] != [] and [x for x in a_[ins0:]] != [] and b_[ins0].strip() == '{' and b_[ins0 + ins_n - 1].strip() == '},' and '"recommend"' in b_[ins0 + 3]
    b_wo = b_[:ins0] + b_[ins0 + ins_n:]; dl = [i for i in range(len(a_)) if a_[i] != b_wo[i]]; assert len(dl) == 21 and 'serial' in a_[dl[0]] and all('"instance_type": ' in a_[i] and '"instance_type": ' in b_wo[i] for i in dl[1:]) and sum(1 for i in dl[1:] if i < ins0) == 10
    r0 = {(x['type'], x['name']): x for x in s0['resources']}; r1 = {(x['type'], x['name']): x for x in s1['resources']}; assert set(r1) - set(r0) == {('aws_instance', 'recommend')} and not set(r0) - set(r1) and sum(1 for k in r0 if r0[k] != r1[k]) == 20
    itl = [(i + 1, i + 1 + (ins_n if i >= ins0 else 0)) for i in dl[1:]]; sz0, sz1 = len(j0.encode()), len(j1.encode())
    key(d, f'■ 状態ファイル「tfstate/terraform.tfstate.backup」（反映前。{la:,}行・{sz0 / 1e6:.2f} MB・リソース {len(r0)}）→「tfstate/terraform.tfstate」（反映後。{lb:,}行・{sz1 / 1e6:.2f} MB・リソース {len(r1)}）。JSON・字下げ2・UTF-8・LF。拡張子は .backup と .tfstate',
        '違いは3種類だけ：① serial（4行目）412 → 413',
        f'② リソース1つの追加：aws_instance.recommend（count = 3 のリソース。instances が3つ）。新の {ins0 + 1:,}〜{ins0 + ins_n:,}行目の {ins_n} 行がまるごと挿入（旧の {ins0:,}行目と {ins0 + 1:,}行目の間。aws_instance.monitor_04 と web_01 の間）。挿入より後ろの {la - ins0:,} 行は、中身が同じで行番号が {ins_n} ずれるだけ',
        '③ instance_type の変更が 20 か所（挿入の前に 10、後ろに 10）：aws_instance.api_01〜api_10 の "c6i.xlarge" → "c6i.2xlarge"（挿入より前。旧と新で同じ行番号）：' + '、'.join(f'{a:,}' for a, b in itl[:10])
        + f'　／　aws_instance.web_01〜web_10 の "m6i.large" → "m6i.xlarge"（挿入より後ろ。旧の行番号（新の行番号＝旧＋{ins_n}））：' + '、'.join(f'{a:,}（{b:,}）' for a, b in itl[10:]) + '。api_11〜16・web_11〜20 は変わっていない',
        '上の ①〜③ 以外の行は、1文字も違わない（1行が長い行：assume_role_policy は JSON を1行に詰めた文字列）')

    # ---------------------------------------------------------------- nginx のアクセスログ（同じ1時間を2台で取ったもの。ほとんどの行が違う）
    def alog(server):
        r = random.Random(f'log{server}'); L = []; health = 0
        paths = ['/', '/items', '/items/{n}', '/items/{n}/reviews', '/cart', '/cart/add', '/checkout', '/checkout/confirm', '/api/v2/items?page={p}', '/api/v2/items/{n}', '/api/v2/cart', '/api/v2/orders/{n}', '/api/v2/search?q=%E3%82%B9%E3%83%8B%E3%83%BC%E3%82%AB%E3%83%BC&page={p}', '/api/v2/recommend?item={n}', '/static/js/app.{h}.js', '/static/css/app.{h}.css', '/img/items/{n}_l.webp', '/img/items/{n}_s.webp', '/favicon.ico', '/login', '/mypage', '/mypage/orders']
        uas = ['Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36', 'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
               'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15', 'ShopApp/5.12.0 (iOS 18.1; iPhone16,2)', 'ShopApp/5.12.0 (Android 15; SM-S928)', 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)']
        for s in range(3600):
            ts = f'27/Nov/2026:02:{s // 60:02d}:{s % 60:02d} +0900'
            if s % 10 == 0: L.append(f'10.20.0.10 - - [{ts}] "GET /healthz HTTP/1.1" 200 2 "-" "ELB-HealthChecker/2.0" rt=0.000 urt=- rid=-'); health += 1
            for _ in range(8 + (1 if s % 30 < 7 else 0)):
                p = r.choice(paths).replace('{n}', str(r.randrange(100000, 999999))).replace('{p}', str(r.randrange(1, 40))).replace('{h}', '3f9c2a71'); m = 'POST' if p in ('/cart/add', '/checkout/confirm', '/login') else 'GET'
                st = r.choices([200, 200, 200, 200, 304, 302, 404, 499, 500, 502], weights=[60, 10, 10, 5, 6, 3, 3, 1, 1, 1])[0]; rt = r.expovariate(9) + 0.002
                L.append(f'{r.randrange(11, 223)}.{r.randrange(0, 255)}.{r.randrange(0, 255)}.{r.randrange(1, 254)} - - [{ts}] "{m} {p} HTTP/{"2.0" if r.random() < 0.8 else "1.1"}" {st} {0 if st == 304 else r.randrange(180, 96000)} "{"https://shop.example.co.jp/" if r.random() < 0.6 else "-"}" "{r.choice(uas)}" rt={rt:.3f} urt={rt * 0.9:.3f} rid={server}-{r.getrandbits(48):012x}')
        return L, health
    (l1, h1), (l2, h2) = alog('web01'), alog('web02'); g1n = 'access_web01_2026-11-27_02時台.log'; g2n = 'access_web02_2026-11-27_02時台.log'; text(f'{d}/logs/{g1n}', '\n'.join(l1) + '\n'); text(f'{d}/logs/{g2n}', '\n'.join(l2) + '\n')
    a_, b_ = _lines_of(f'{d}/logs/{g1n}')[:-1], _lines_of(f'{d}/logs/{g2n}')[:-1]; common = set(a_) & set(b_); assert len(a_) == len(b_) == 30000 and len(common) == 360 == h1 == h2 and all('/healthz' in x for x in common) and len(set(a_)) == 30000
    key(d, f'■ アクセスログ「logs/{g1n}」と「logs/{g2n}」（各 30,000行・{len(open(P(f"{d}/logs/{g1n}"), "rb").read()) / 1e6:.1f} MB と {len(open(P(f"{d}/logs/{g2n}"), "rb").read()) / 1e6:.1f} MB・UTF-8・LF）。同じ1時間（02:00:00〜02:59:59）を2台のサーバで取ったもの',
        '2つで文字まで同じ行は、ロードバランサのヘルスチェック（GET /healthz、10秒おき）の 360 行だけ。残りの 29,640 行ずつは、別々のリクエスト（IP・パス・応答時間・rid がすべて違う）。「ほぼ全行が違う」のが正しい結果（1行ごとに似た行を探して「変更」として並べる意味はない）',
        '時刻の並びは同じ（各秒に 8〜9 行＋10秒ごとにヘルスチェック1行）なので、同じ行番号どうしは同じ秒の行になる。1行は 170〜330 文字ほど')

    # ---------------------------------------------------------------- kubectl diff の出力を保存したテキスト（unified diff 形式そのもの）
    def kdiff(v):
        tmp_l, tmp_m, ts = (('LIVE-2841907365', 'MERGED-1193847520', '2026-11-27 16:42:1') if v else ('LIVE-3716250948', 'MERGED-860419273', '2026-11-26 11:08:3')); out = []
        def blk(kind, name, live, merged, k):
            a = live.splitlines(True); b = merged.splitlines(True); fn = f'{kind}.shop.{name}'
            out.append(f'diff -u -N /tmp/{tmp_l}/{fn} /tmp/{tmp_m}/{fn}\n')
            out.extend(difflib.unified_diff(a, b, f'/tmp/{tmp_l}/{fn}', f'/tmp/{tmp_m}/{fn}', f'{ts}{k}.{(k * 37 + 104729) % 1000000000:09d} +0900', f'{ts}{k}.{(k * 91 + 350377) % 1000000000:09d} +0900', n=3))
        S = {s[0]: s for s in R08_SVC}
        def dep(svc, tag0, tag1, env=(), gen=30, rep=None):
            live = _r08_deploy(svc, S[svc][1], tag0, gen=gen); merged = _r08_deploy(svc, S[svc][1], tag1, env, gen=gen + 1)
            if rep: live = live.replace('replicas: 2', f'replicas: {rep[0]}'); merged = merged.replace('replicas: 2', f'replicas: {rep[1]}')
            return live, merged
        blk('apps.v1.Deployment', 'api-gateway', *dep('api-gateway', '2.14.3', '2.15.0', gen=41), 1); blk('apps.v1.Deployment', 'cart', *dep('cart', '3.9.4', '3.9.4', gen=27, rep=(4, 6 if v else 5)), 2); blk('apps.v1.Deployment', 'catalog', *dep('catalog', '7.3.2', '7.3.2', gen=33, rep=(3, 5)), 3)
        blk('apps.v1.Deployment', 'order', *dep('order', '5.8.1', '5.9.0', (('ORDER_OUTBOX_ENABLED', '"true"'),) if v else (), gen=58), 4); blk('apps.v1.Deployment', 'payment', *dep('payment', '3.2.7', '3.2.8', gen=22), 5)
        if v:
            blk('apps.v1.Deployment', 'recommend', '', _r08_deploy('recommend', 8090, '0.4.0', gen=1), 6); blk('apps.v1.Deployment', 'search', *dep('search', '1.12.0', '1.12.0', (('SEARCH_SYNONYM_DICT', 'v20261125'),), gen=19), 7)
        blk('apps.v1.Deployment', 'web-front', *dep('web-front', '11.4.0', '11.5.2', gen=73), 8)
        cm = lambda n: f'apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: api-gateway-config\n  namespace: shop\ndata:\n  APP_ENV: "production"\n  HTTP_PORT: "8080"\n  DB_HOST: "apigateway-db.shop.internal"\n  DB_POOL_SIZE: "20"\n  CACHE_TTL_SEC: "300"\n  REQUEST_TIMEOUT_MS: "3000"\n  RATE_LIMIT_RPS: "{n}"\n  UPSTREAM_KEEPALIVE: "64"\n'
        blk('v1.ConfigMap', 'api-gateway-config', cm(200), cm(300), 9)
        if v: blk('v1.Service', 'recommend', '', _r08_service('recommend', 8090), 10)
        return ''.join(out)
    k0, k1 = kdiff(0), kdiff(1); k0n = 'kubectl-diff_production_2026-11-26_事前確認.txt'; k1n = 'kubectl-diff_production_2026-11-27_反映直前.txt'; text(f'{d}/kubectl-diff/{k0n}', k0); text(f'{d}/kubectl-diff/{k1n}', k1)
    a_, b_ = _lines_of(f'{d}/kubectl-diff/{k0n}')[:-1], _lines_of(f'{d}/kubectl-diff/{k1n}')[:-1]; hd = lambda L: sum(1 for x in L if x.startswith('diff -u -N '))
    sm = difflib.SequenceMatcher(None, a_, b_, autojunk=False); ops = [o for o in sm.get_opcodes() if o[0] != 'equal']; assert hd(a_) == 7 and hd(b_) == 10
    f1 = lambda L, s, st=0: _lineno(L, s, st)
    cart0 = f1(a_, '+  replicas: 5'); cart1 = f1(b_, '+  replicas: 6'); ord0 = f1(a_, 'apps.v1.Deployment.shop.order'); ord1 = f1(b_, 'apps.v1.Deployment.shop.order'); pay1 = f1(b_, 'diff -u -N', ord1); rec1 = f1(b_, 'apps.v1.Deployment.shop.recommend'); sea1 = f1(b_, 'apps.v1.Deployment.shop.search'); web1 = f1(b_, 'apps.v1.Deployment.shop.web-front'); svc1 = f1(b_, 'v1.Service.shop.recommend')
    assert a_[cart0 - 1] == '+  replicas: 5' and b_[cart1 - 1] == '+  replicas: 6' and cart0 == cart1
    key(d, f'■ kubectl diff の出力「kubectl-diff/{k0n}」（{len(a_)}行・リソース 7）→「kubectl-diff/{k1n}」（{len(b_)}行・リソース 10）。ファイルの中身そのものが unified diff 形式（行頭が +・-・空白・@@・diff・---・+++）',
        '各リソースの先頭3行（diff -u -N …、--- …、+++ …）は、一時フォルダの名前（LIVE-3716250948→LIVE-2841907365、MERGED-860419273→MERGED-1193847520）と日時が違うので、共通の 7 リソース分の 21 行がすべて違う',
        f'cart：{cart0}行目「+  replicas: 5」→「+  replicas: 6」（行頭の + は diff の記号。数字だけが違う）',
        f'order（旧 {ord0}行目から／新 {ord1}〜{pay1 - 1}行目）：新では env の追加（「+            - name: ORDER_OUTBOX_ENABLED」「+              value: "true"」の2行）が増え、その @@ の行の行数も変わる',
        f'新にだけあるリソース 3：recommend の Deployment（新 {rec1}〜{sea1 - 1}行目。全行が + の新規作成）、search の Deployment（新 {sea1}〜{web1 - 1}行目。env の追加）、recommend の Service（新 {svc1}〜{len(b_)}行目。全行が +）',
        'api-gateway・catalog・payment・web-front・ConfigMap の中身（先頭3行以外）は同じ。このファイルを比べると、「- で始まる行」が比較結果の「削除」と紛らわしくないか、行頭の記号と元の +/- が区別できるかを見る')

    # ---------------------------------------------------------------- 単体のファイル：混在改行のシェルスクリプト、証明書（PEM）、Secret、crontab、Dockerfile
    sh = ['#!/usr/bin/env bash', '# shop の DB を S3 へバックアップする（毎日 03:10 に cron から実行）', 'set -euo pipefail', '', 'readonly BACKUP_BUCKET="s3://shop-prod-backup-db-0164"', 'readonly DB_HOST="order-db.shop.internal"', 'readonly DB_NAME="shop_order"', 'readonly RETENTION_DAYS=14', 'readonly WORK_DIR="/var/tmp/backup_db"',
          'readonly LOG_FILE="/var/log/shop/backup_db.log"', '', 'log() {', '  echo "[$(date \'+%Y-%m-%d %H:%M:%S\')] $*" | tee -a "${LOG_FILE}"', '}', '', 'fail() {', '  log "ERROR: $*"', '  /usr/local/bin/notify-slack "#shop-alert" "backup_db: $*" || true', '  exit 1', '}', '',
          'cleanup() {', '  rm -rf "${WORK_DIR:?}/dump"', '}', 'trap cleanup EXIT', '', 'check_space() {', '  local need_kb=$1', '  local free_kb', '  free_kb=$(df --output=avail -k "${WORK_DIR}" | tail -n 1)', '  if (( free_kb < need_kb )); then', '    fail "空き容量が足りません（必要 ${need_kb} KB、空き ${free_kb} KB）"', '  fi', '}', '',
          'dump_db() {', '  local out="$1"', '  log "dump を開始します：${DB_NAME}"', '  mkdir -p "$(dirname "${out}")"', '  PGPASSFILE=/etc/shop/pgpass pg_dump \\', '    --host="${DB_HOST}" \\', '    --username=backup \\', '    --format=custom \\', '    --compress=6 \\', '    --jobs=1 \\', '    --file="${out}" \\', '    "${DB_NAME}"', '  log "dump が終わりました：$(du -h "${out}" | cut -f1)"', '}', '',
          'upload() {', '  local src="$1"', '  local key="daily/$(date +%Y/%m)/$(basename "${src}")"', '  aws s3 cp "${src}" "${BACKUP_BUCKET}/${key}" --storage-class STANDARD_IA --only-show-errors', '  aws s3api head-object --bucket "${BACKUP_BUCKET#s3://}" --key "${key}" >/dev/null || fail "アップロードを確認できません：${key}"', '  log "アップロードしました：${key}"', '}', '',
          'prune() {', '  local cutoff', '  cutoff=$(date -d "${RETENTION_DAYS} days ago" +%Y-%m-%d)', '  log "${cutoff} より古いバックアップを削除します"', '  aws s3 ls "${BACKUP_BUCKET}/daily/" --recursive | while read -r day _time _size path; do', '    if [[ "${day}" < "${cutoff}" ]]; then', '      aws s3 rm "${BACKUP_BUCKET}/${path}" --only-show-errors', '    fi', '  done', '}', '',
          'main() {', '  local stamp', '  stamp=$(date +%Y%m%d_%H%M%S)', '  local out="${WORK_DIR}/dump/${DB_NAME}_${stamp}.dump"', '  check_space $((20 * 1024 * 1024))', '  dump_db "${out}"', '  upload "${out}"', '  prune', '  log "完了しました"', '}', '', 'main "$@"']
    sh1 = list(sh); ci = sh1.index('readonly RETENTION_DAYS=14'); sh1[ci] = 'readonly RETENTION_DAYS=30'
    crlf = range(sh.index('dump_db() {'), sh.index('prune() {'))      # Windows のエディタで開いて保存し直した範囲（行末が CRLF になった）
    assert ci not in crlf
    mixed = ''.join(l + ('\r\n' if i in crlf else '\n') for i, l in enumerate(sh1)).encode('utf-8'); d0, d1 = '単体ファイル_反映前', '単体ファイル_反映後'
    wbytes(f'{d}/{d0}/backup_db.sh', ('\n'.join(sh) + '\n').encode('utf-8')); wbytes(f'{d}/{d1}/backup_db.sh', mixed)
    rb_ = open(P(f'{d}/{d1}/backup_db.sh'), 'rb').read(); n_crlf = rb_.count(b'\r\n'); n_lf = rb_.count(b'\n') - n_crlf; assert n_crlf == len(crlf) and n_crlf + n_lf == len(sh) and b'\r' not in open(P(f'{d}/{d0}/backup_db.sh'), 'rb').read()
    def pem(seed, n=1380):
        b = b'\x30\x82' + struct.pack('>H', n - 4) + random.Random(seed).randbytes(n - 4); s = base64.b64encode(b).decode()
        return '-----BEGIN CERTIFICATE-----\n' + '\n'.join(s[i:i + 64] for i in range(0, len(s), 64)) + '\n-----END CERTIFICATE-----\n'
    inter = pem('intermediate-r11', 1290); p_old = pem('leaf-2025') + inter; p_new = pem('leaf-2026') + inter
    text(f'{d}/{d0}/shop.example.co.jp.pem', p_old); text(f'{d}/{d1}/shop.example.co.jp.pem', p_new)
    sec = lambda p: ('apiVersion: v1\nkind: Secret\nmetadata:\n  name: shop-tls-chain\n  namespace: shop\n  annotations:\n    cert-manager.io/issuer-name: letsencrypt-prod\ntype: Opaque\ndata:\n  tls.crt: ' + base64.b64encode(p.encode()).decode() + '\n  ca.crt: ' + base64.b64encode(inter.encode()).decode() + '\n')
    text(f'{d}/{d0}/tls-secret.yaml', sec(p_old)); text(f'{d}/{d1}/tls-secret.yaml', sec(p_new))
    pl0, pl1 = p_old.split('\n'), p_new.split('\n'); nleaf = pl0.index('-----END CERTIFICATE-----') + 1; assert pl0[nleaf:] == pl1[nleaf:] and all(pl0[i] != pl1[i] for i in range(1, nleaf - 1)) and pl0[0] == pl1[0]
    s0_, s1_ = sec(p_old).split('\n'), sec(p_new).split('\n'); assert [i + 1 for i in range(len(s0_)) if s0_[i] != s1_[i]] == [10]
    cron = lambda v: ('# shop 本番 web01 の crontab（root）。変更したら、このファイルも更新すること\nSHELL=/bin/bash\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin\nMAILTO=infra-alert@shop.example.co.jp\n\n# 分 時 日 月 曜日 コマンド\n'
                      + ('30 2 * * * /opt/shop/bin/backup_db.sh >> /var/log/shop/cron.log 2>&1\n' if v else '10 3 * * * /opt/shop/bin/backup_db.sh >> /var/log/shop/cron.log 2>&1\n') + '*/5 * * * * /opt/shop/bin/healthcheck.sh\n0 4 * * 0 /opt/shop/bin/rotate_logs.sh --keep 8\n'
                      + ('#15 1 * * * /opt/shop/bin/sync_images.sh --dest s3://shop-prod-images-0164\n' if v else '15 1 * * * /opt/shop/bin/sync_images.sh --dest s3://shop-prod-images-0164\n') + '0 9 1 * * /opt/shop/bin/report_monthly.sh\n*/10 * * * * /opt/shop/bin/queue_monitor.sh --warn 500 --crit ' + ('3000' if v else '2000') + '\n'
                      + ('45 23 * * 1-5 /opt/shop/bin/export_orders.sh --format csv\n' if v else '') + '@reboot /opt/shop/bin/warmup_cache.sh\n')
    text(f'{d}/{d0}/crontab', cron(0)); text(f'{d}/{d1}/crontab', cron(1))
    dock = lambda v: ('# syntax=docker/dockerfile:1\nFROM ' + ('node:22.11-bookworm-slim' if v else 'node:20.18-bookworm-slim') + ' AS build\nWORKDIR /app\nCOPY package.json package-lock.json ./\nRUN npm ci\nCOPY . .\nRUN npm run build\n\nFROM nginx:1.27-alpine\nLABEL org.opencontainers.image.title="shop web-front"\nLABEL org.opencontainers.image.version="' + ('11.5.2' if v else '11.4.0') + '"\n'
                      'ENV TZ=Asia/Tokyo\n' + ('ENV NGINX_ENTRYPOINT_QUIET_LOGS=1\n' if v else '') + 'RUN apk add --no-cache tzdata curl \\\n    && rm -rf /var/cache/apk/*\nCOPY --from=build /app/dist /usr/share/nginx/html\nCOPY nginx/default.conf /etc/nginx/conf.d/default.conf\nCOPY nginx/security-headers.conf /etc/nginx/conf.d/security-headers.conf\n'
                      'EXPOSE 3000\nHEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD curl -fsS http://127.0.0.1:3000/healthz || exit 1\nUSER ' + ('101' if v else 'nginx') + '\nCMD ["nginx", "-g", "daemon off;"]\n')
    text(f'{d}/{d0}/Dockerfile', dock(0)); text(f'{d}/{d1}/Dockerfile', dock(1))
    key(d, f'■ 単体のファイル「{d0}/」と「{d1}/」（同じ名前の5ファイルずつ：backup_db.sh・shop.example.co.jp.pem・tls-secret.yaml・crontab・Dockerfile。crontab と Dockerfile は拡張子がない）',
        f'backup_db.sh（{len(sh)}行）：反映前は全行 LF。反映後は **CRLF と LF が混在**（{crlf.start + 1}〜{crlf.stop}行目の {n_crlf} 行が CRLF、残りの {n_lf} 行が LF。Windows で一部を編集して保存したため）。中身の変更は 1 行だけ：{ci + 1}行目 RETENTION_DAYS=14 → RETENTION_DAYS=30（この行は LF のまま）。'
        '改行の違いを無視すれば差は1行、区別すれば CRLF の行もすべて違う。改行が混在していることを知らせること',
        f'shop.example.co.jp.pem（証明書2つの連結。base64 が1行 64 文字）：1つ目（サーバ証明書）は中身がすべて違う（2〜{nleaf - 1}行目の {nleaf - 2} 行。-----BEGIN/END----- の行は同じ）。2つ目（中間証明書。{nleaf + 1}行目以降）は同じ',
        f'tls-secret.yaml（{len(s0_) - 1}行）：10行目 tls.crt の値（base64 を1行に詰めたもの。{len(s0_[9]):,} 文字）だけが違う。11行目 ca.crt（{len(s0_[10]):,} 文字）は同じ。1行が長いときの見え方を確かめる',
        'crontab：バックアップの時刻「10 3 * * *」→「30 2 * * *」、sync_images.sh の行が行頭に # を付けてコメントアウト、queue_monitor.sh の --crit 2000 → 3000、export_orders.sh の行（45 23 * * 1-5）を追加',
        'Dockerfile：ビルド用のイメージ node:20.18-bookworm-slim → node:22.11-bookworm-slim、LABEL の version 11.4.0 → 11.5.2、ENV NGINX_ENTRYPOINT_QUIET_LOGS=1 の行を追加、USER nginx → USER 101')


# <<<end r08>>>
SPEC = [
    (6, '購買・経理担当', '商社', r06, {
        'who': 'あなたは、商社（湊川商事）の購買部で、発注と支払の事務を7年担当しています。仕入先から届く見積書・請求書の「再提出版」「訂正版」を前の版と比べ、金額・数量・振込先が変わっていないかを確かめるのが日課です。'
               '上司（課長）に「どこが変わったか」を紙かファイルで渡して承認をもらいます。パソコンは Excel とメールが中心で、IT の言葉（文字コード、パッチ、差分など）には詳しくありません。振込先や金額の見落としは事故になるので、1桁の違いをいちばん気にします。',
        'tasks': [
            '見積書（Excel）の「…_初回（11月10日受領）.xlsx」と「…-R1_再提出（11月24日受領）.xlsx」をテキスト比較で比べ、どの明細が増え・減り・変わったか、単価・数量・値引・合計がどう変わったか、備考や日付に変更がないかを洗い出す。合計の計算が正しいか（式の範囲）も確かめる。和暦の日付・¥ の表示・結合セルが、Excel で見たとおりに読めるかも見る。',
            '請求書（PDF）の「請求書_北斗オフィスサプライ_2026年11月分.pdf」と「…_訂正版.pdf」を、①テキスト比較、②重ね合わせ、③ページ表示（変更箇所の枠・付箋）の3つで比べる。金額・振込先の口座番号・登録番号の1桁の違い、「訂正」の表示を、それぞれの画面で見つけられるか。見つけた箇所に付箋やコメントを付ける。',
            '「発注書_PO-2611-0457_関西精密工業宛.pdf」（自社の様式）と「請求書_関西精密工業_No.K2611-0871（PO-2611-0457分）.pdf」（仕入先の様式）は、レイアウトも並び順も違う。発注どおりに請求されているか（品番ごとの数量・単価・金額、発注にない請求）を、このツールでどこまで確かめられるかを試す（テキスト比較・検索・ページ表示を並べる、など）。',
            '支払予定一覧（CSV）の「…_11月25日時点.csv」と「…_11月27日時点.csv」を比べる。負数の書き方（-1,000／△1,000／(1,000)）が混ざっているので、「書き方が違うだけの行」と「本当に金額が違う行」を見分けられるか。行の追加・削除も確かめる。数字の差の札が、負数の書き方にどう付くかも見る。',
            '領収書のスキャン2枚（「…スキャン1回目.jpg」と「…スキャン2回目（取り直し）.jpg」）を重ね合わせで比べる。同じ領収書を2回取り込んだだけなので、「違いなし」と分かる結果になるか（位置合わせ、枠の数、表示される言葉）。テキスト比較のタブではどう案内されるか。',
            '課題1と課題2の結果を、上司に渡す形にする（レポートの出力、印刷 / PDF、変更点の一覧）。Excel の比較結果と PDF の重ね合わせの結果のそれぞれで、「何が・どこで・どう変わったか」が、ツールを知らない上司に伝わるかを見る。'],
        'note': '要件定義書などの資料は読まず、画面と［？］の説明だけで進めてください（IT に詳しくない利用者の役です）。金額や番号は、1桁ずつ自分の目でも確かめてください。'}),
    # <<<spec r07>>>
    (7, 'ローカライズ担当', 'ゲーム会社', r07, {
        'who': 'あなたは、ゲーム会社でローカライズのリードを5年務めています。翻訳会社から戻ってきた文言ファイル（JSON・CSV・YAML・XLIFF）を前の版と比べ、頼んでいない変更や、壊れた制御タグ（{0}、<color=…>、\\n）を出荷前に見つけるのが仕事です。'
               '日本語のほかに英語・中国語・韓国語・アラビア語・タイ語と絵文字を扱うので、文字が正しく表示されるか、見た目が同じ別の文字（波ダッシュと全角チルダ、濁点の付け方）を見分けられるかを気にします。配布前には、ビルドのフォルダどうしも比べます。',
        'tasks': [
            '「文言/strings_ja_1.8.0.json」と「文言/strings_ja_1.8.1_翻訳会社戻り.json」をテキスト比較で比べる。①ひとかたまりのキーの順番の入れ替えと、本当の変更・追加・削除を見分けられるか、②制御タグの破損（{0}、<color=…> の閉じ忘れ、\\n のエスケープ）を見つけられるか、③絵文字（国旗・肌色・家族）や、見た目が同じ別の文字（波ダッシュ／全角チルダ、長音／横線、1文字の「が」／「か＋濁点」）の違いを、どう示すか（どの文字がどう違うかが分かるか）。',
            '「文言/messages_1.8.0.csv」と「文言/messages_1.8.1_翻訳会社戻り.csv」を比べる。アラビア語（右から左）・タイ語・ハングル・簡体字のセルが正しく表示されるか、変わった箇所の印が文字の並びとずれないか、セルの中の改行や引用符のあるレコードの対応が崩れないか、目に見えない文字の違いに気づけるか。検索（アラビア語・タイ語の語）も試す。',
            '「文言/dialog_ch03_1.8.0.yaml」と「文言/dialog_ch03_1.8.1_翻訳会社戻り.yaml」を比べる。字下げだけが変わったかたまりと、本当の文言の変更が混ざっている。比較の条件（空白：比較する／量を無視／すべて無視）を切り替えて、本当の変更だけを残せるか。タブの混入を、空白の記号表示で見つけられるか。',
            '「文言/ui_ja-en_1.8.0.xlf」と「文言/ui_ja-en_1.8.1_翻訳会社戻り.xlf」（XLIFF）を比べる。訳文の変更・状態（state）だけの変更・タグの破損・属性の順番だけの違いを見分けられるか。変更点の一覧やレポートが、翻訳会社へ差し戻す資料として使えるか。',
            '「スクリーンショット/screenshot_メニュー画面_1.8.0.png」と「…_1.8.1.png」を重ね合わせで比べる。ボタンの文言、1画素のずれ、わずかな色の変更、小さな注記の追加を、どの表示方法（差分ハイライト・点滅・スワイプなど）と感度で見つけられるか。暗い背景でも色分けが見えるか。',
            '「build_1.8.0」と「build_1.8.1」をフォルダ比較で比べる。「フォルダを選択」と、ウィンドウへのドロップの両方で読み込み、結果（件数）が同じになるかを確かめる。同一・相違・左のみ・右のみの件数、状態での絞り込み、並べ替え、行を開いて比較して一覧に戻る操作、CSV・レポートの出力を試す。名前の大文字小文字だけが違うファイル、隠しファイル（.DS_Store・Thumbs.db・.gitkeep）、0 バイトのファイル、内容が同じで更新日時だけが違うファイル、バイナリ（png・ogg）がどう扱われるかを見る。',
            '課題1〜4で見つけた「頼んでいない変更」を、翻訳会社へ差し戻すための資料にする（変更点へのコメント、CSV・レポートの出力）。多言語と絵文字が、出力したファイルでも崩れないかを確かめる。'],
        'note': 'CSV は、Excel で書き出した形（レコードの区切りは CRLF、セルの中の改行は LF）です。フォルダは各 約1,200 ファイルあります。読み込みと比較にかかる時間を測ってください。'}),
    # <<<endspec r07>>>
    # <<<spec r08>>>
    (8, 'SRE', 'Webサービス会社', r08, {
        'who': 'あなたは、EC サイトを運営する会社でインフラ運用（SRE）を8年担当しています。本番への反映の前に、設定ファイル（Kubernetes の YAML・Terraform）のフォルダを前回の反映時のものと比べて、意図しない変更が混ざっていないかをレビューします。'
               '障害の調査では、ログや Terraform の状態ファイルも比べます。ふだんは diff・git diff・vimdiff を使っていて、キーボードだけで操作したい人です。行末の空白、改行コード、ドットで始まるファイルの扱いには、特にうるさいです。',
        'tasks': [
            '「deploy_2026-11-20」と「deploy_2026-11-27」をフォルダ比較で比べる。「フォルダを選択」とウィンドウへのドロップの両方で読み込み、件数（同一・相違・左のみ・右のみ）が同じになるか、ドットで始まるファイル・フォルダ（.gitignore、.env.example、.yamllint、.github/、.gitkeep）と空のファイルが一覧に出るかを確かめる。並べ替え・状態での絞り込み・相対パスの表示も見る。',
            '課題1の一覧から、相違のファイルを順に開いて中身を比べ、一覧に戻る操作を繰り返す。image のタグ・replicas・env の追加といった「意味のある変更」と、キーの順番だけ・字下げだけ・コメントだけの違いを見分けられるか（比較の条件を変えて試す）。名前が変わっただけのファイル（中身は同じ）に気づけるか。できるだけキーボードだけで操作する。',
            '課題2で開いたファイルのうち2〜3個について、パッチを出力し、反映前のフォルダのコピー（自分の出力フォルダに作る）に `git apply` または `patch -p1` で当てて、反映後と同じ内容になるかを確かめる。パッチの見出しのパス（相対パス）も見る。',
            '「tfstate/terraform.tfstate.backup」と「tfstate/terraform.tfstate」（各 約4万行・2MB）を比べる。読み込みと比較にかかる時間を測る。数百行の挿入の前後で行の対応が保たれるか、散らばった 20 か所の値の変更を次々にたどれるか、拡張子（.backup・.tfstate）のせいで読み込みに困らないか。',
            '「logs/access_web01_…log」と「logs/access_web02_…log」（各3万行。ほぼ全行が違う）を比べる。かかる時間、画面の反応、結果の見え方（件数・位置マップ・「差分のある所だけ」）を確かめる。途中で止まったように見えないか、中止できるか。',
            '「単体ファイル_反映前」と「単体ファイル_反映後」の5組を比べる。backup_db.sh は改行コードが混在している。混在していることが分かるか、中身の変更（1行）だけを取り出せるか、保存・パッチ出力で改行がどうなるか。証明書（PEM）と tls-secret.yaml（1行が数千文字の base64）の見え方、拡張子のない crontab・Dockerfile の読み込みも確かめる。',
            '「kubectl-diff/…_事前確認.txt」と「…_反映直前.txt」は、ファイルの中身そのものが diff 形式（行頭が + や -）。これを比べたとき、元の +/- と、このツールが付ける記号・色が紛らわしくないか。レポートやパッチにしたときに読めるか。'],
        'note': 'キーボードでの操作（Tab・矢印・Enter・ショートカット）を、マウスと同じだけ試してください。tfstate とログは大きいので、読み込みと比較の秒数を測って報告してください。'}),
    # <<<endspec r08>>>
]
