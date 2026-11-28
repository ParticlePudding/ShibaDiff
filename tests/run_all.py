"""すべてのテストを順に実行し、1つでも失敗したら終了コード 1 を返す。
先に `npm ci`・`python3 build.py`・`python3 tools/gen_samples.py` を実行しておくこと。"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = ['test_regression.py', 'test_fixes.py', 'test_round1.py', 'test_review.py', 'test_overlay_align.py', 'test_security.py', 'test_ui_feedback.py', 'test_ov_scroll.py', 'test_reports.py', 'test_review2_fixes.py', 'test_notes.py', 'test_review3_fixes.py']

if not os.path.isdir(os.path.join(os.path.dirname(HERE), 'samples')):
    sys.exit('samples/ がありません。先に python3 tools/gen_samples.py を実行してください')
failed = []
for name in TESTS:
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(HERE, name)], capture_output=True, text=True)
    summary = next((l for l in reversed(r.stdout.splitlines()) if l.startswith('==')), '(結果なし)')
    ok = r.returncode == 0
    print(f"{'OK' if ok else 'NG'}  {name:24s} {time.time() - t0:5.1f}s  {summary}", flush=True)
    if not ok:
        failed.append(name)
        print('\n'.join('    ' + l for l in (r.stdout + r.stderr).splitlines() if l.startswith('NG') or 'Error' in l), flush=True)
print('すべて合格' if not failed else f'失敗: {", ".join(failed)}')
sys.exit(1 if failed else 0)
