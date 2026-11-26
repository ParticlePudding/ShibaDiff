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
js_files = ["util.js", "settings.js", "encoding.js", "diff.js", "office.js", "pdf.js", "pages.js",
            "textview.js", "pageview.js", "overlay.js", "folder.js", "main.js"]
import datetime
ver = json.load(open(os.path.join(HERE, "package.json")))["version"]
pdfjs_ver = json.load(open(os.path.join(PDFJS, "package.json")))["version"]
app_head = f"const APP = {{ version: {json.dumps(ver)}, build: {json.dumps(datetime.date.today().isoformat())}, pdfjs: {json.dumps(pdfjs_ver)} }};\n"
app = app_head + "\n".join(f"// ---- {n} ----\n" + read(os.path.join(SRC, n)) for n in js_files)
check_script_safe("app", app)

html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' blob:; worker-src blob:; style-src 'unsafe-inline'; img-src data: blob:; font-src data: blob:; connect-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'">
<title>ShibaDiff</title>
<style>
{css}
</style>
</head>
<body>
{body}
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
