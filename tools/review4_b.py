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
]
