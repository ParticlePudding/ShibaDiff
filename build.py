#!/usr/bin/env python3
"""Inline everything into a single HTML file."""
import base64, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
PDFJS = os.path.join(HERE, "node_modules", "pdfjs-dist")

def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

def check_script_safe(name, s):
    low = s.lower()
    for bad in ("</script", "<!--"):
        if bad in low:
            raise SystemExit(f"{name} contains {bad!r}; cannot inline safely")

# pdf.js main library: turn the trailing `export{a as b,...}` into a global
lib = read(os.path.join(PDFJS, "legacy", "build", "pdf.min.mjs"))
m = re.search(r"export\s*\{([^}]*)\}\s*;?\s*(//#.*)?\s*$", lib)
if not m:
    raise SystemExit("export clause not found in pdf.min.mjs")
pairs = []
for part in m.group(1).split(","):
    part = part.strip()
    if not part:
        continue
    if " as " in part:
        local, exported = [x.strip() for x in part.split(" as ")]
    else:
        local = exported = part
    pairs.append(f"{exported}:{local}")
lib = lib[: m.start()] + "globalThis.pdfjsLib={" + ",".join(pairs) + "};window.dispatchEvent(new Event('pdfjs-ready'));"
check_script_safe("pdf.min.mjs", lib)

worker = read(os.path.join(PDFJS, "legacy", "build", "pdf.worker.min.mjs"))
check_script_safe("pdf.worker.min.mjs", worker)

# Japanese CMaps only (keeps the file small)
cmap_dir = os.path.join(PDFJS, "cmaps")
pat = re.compile(r"^(UniJIS.*|Adobe-Japan1-.*|.*RKSJ.*|EUC-[HV]|H|V|Hankaku|Hiragana|Katakana|Roman|WP-Symbol|78-.*|83pv-.*|90.*|Add-.*|Ext-.*|NWP-.*|Identity-[HV])\.bcmap$")
cmaps = {}
for fn in sorted(os.listdir(cmap_dir)):
    if pat.match(fn):
        with open(os.path.join(cmap_dir, fn), "rb") as f:
            cmaps[fn[:-6]] = base64.b64encode(f.read()).decode()
cmaps_json = json.dumps(cmaps, separators=(",", ":"))

css = read(os.path.join(SRC, "style.css"))
body = read(os.path.join(SRC, "body.html"))
js_files = ["util.js", "settings.js", "encoding.js", "diff.js", "office.js", "pdf.js", "pages.js", "pagematch.js", "report.js", "notes.js",
            "textview.js", "pageview.js", "overlay.js", "folder.js", "main.js"]
import datetime
ver = json.load(open(os.path.join(HERE, "package.json")))["version"]
pdfjs_ver = json.load(open(os.path.join(PDFJS, "package.json")))["version"]
app_head = f"const APP = {{ version: {json.dumps(ver)}, build: {json.dumps(datetime.date.today().isoformat())}, pdfjs: {json.dumps(pdfjs_ver)} }};\n"
app = app_head + "\n".join(f"// ---- {n} ----\n" + read(os.path.join(SRC, n)) for n in js_files)

# アイコン（Lucide）：画面の HTML と JS の中の <i data-i="名前"></i> を、その SVG に置き換えて埋め込む。
# 使っているアイコンだけを入れる。名前の誤りはビルドを止める
LUCIDE = os.path.join(HERE, "node_modules", "lucide-static")
lucide_ver = json.load(open(os.path.join(LUCIDE, "package.json")))["version"]
ICON_RE = re.compile(r'<i data-i="([a-z0-9-]+)"></i>')
def icon_svg(name):
    path = os.path.join(LUCIDE, "icons", name + ".svg")
    if not os.path.exists(path): raise SystemExit(f"アイコンがありません: {name}")
    inner = re.search(r"<svg[^>]*>(.*)</svg>", read(path), re.S).group(1)
    inner = re.sub(r"\s*\n\s*", "", inner).replace(" />", "/>")
    return f'<svg class="ic" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{inner}</svg>'
used_icons = sorted(set(ICON_RE.findall(body)) | set(ICON_RE.findall(app)))
icons = {n: icon_svg(n) for n in used_icons}
body = ICON_RE.sub(lambda m: icons[m.group(1)], body)
app = ICON_RE.sub(lambda m: icons[m.group(1)], app)
app = app_head.replace("pdfjs:", f"lucide: {json.dumps(lucide_ver)}, pdfjs:") + app[len(app_head):]
check_script_safe("app", app)

# ライセンス表記（ShibaDiff 本体と、同梱する pdf.js・core-js）。設定の「このツールについて」から表示する
def notice(title, path):
    return f"==================== {title} ====================\n\n" + read(path).strip() + "\n"
licenses = "\n\n".join([
    notice("ShibaDiff (MIT License)", os.path.join(HERE, "LICENSE")),
    notice(f"pdf.js {pdfjs_ver} (Apache License 2.0) https://github.com/mozilla/pdf.js", os.path.join(PDFJS, "LICENSE")),
    notice("core-js 3.39.0 (MIT License, bundled in pdf.js legacy build) https://github.com/zloirock/core-js", os.path.join(HERE, "third_party", "core-js-LICENSE")),
    notice(f"Lucide icons {lucide_ver} (ISC License; some icons MIT License, Feather) https://lucide.dev", os.path.join(LUCIDE, "LICENSE")),
])
check_script_safe("licenses", licenses)

def icon_uri(n):
    import base64
    with open(os.path.join(HERE, "assets", f"icon-{n}.png"), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()
icon64, icon180 = icon_uri(64), icon_uri(180)
body = body.replace("__ICON64__", icon64)

html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' blob:; worker-src blob:; style-src 'unsafe-inline'; img-src data: blob:; font-src data: blob:; connect-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'">
<title>ShibaDiff</title>
<link rel="icon" type="image/png" sizes="64x64" href="{icon64}">
<link rel="apple-touch-icon" href="{icon180}">
<style>
{css}
</style>
</head>
<body>
{body}
<script type="text/plain" id="licenses">{licenses}</script>
<script type="application/json" id="cmaps">{cmaps_json}</script>
<script type="text/plain" id="pdfjs-worker">{worker}</script>
<script type="module">{lib}</script>
<script>
{app}
</script>
</body>
</html>
"""
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "ShibaDiff.html")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(out, f"{len(html.encode('utf-8'))/1024/1024:.2f} MB")
