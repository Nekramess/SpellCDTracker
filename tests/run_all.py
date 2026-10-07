"""Run every tests/*_test.py from the repo root and print per-file counts. Exit non-zero if any file has a FAIL."""
import glob
import os
import re
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
rows, bad = [], False
for path in sorted(glob.glob(os.path.join(here, "*_test.py"))):
    name = os.path.basename(path)
    p = subprocess.run([sys.executable, path], cwd=root, capture_output=True, text=True)
    out = p.stdout + p.stderr
    m = re.search(r"RESULT \S+: (\d+) passed, (\d+) failed, (\d+) xfail, (\d+) xpass", out)
    if not m or p.returncode != 0 and int(m.group(2)) == 0:
        rows.append((name, "CRASH", "", "", ""))
        bad = True
        print(out[-1500:])
        continue
    ps, fl, xf, xp = map(int, m.groups())
    rows.append((name, ps, fl, xf, xp))
    bad = bad or fl > 0
    for line in out.splitlines():
        if line.startswith(("FAIL", "XFAIL", "XPASS")):
            print(f"  [{name}] {line}")
print()
print(f"{'file':32} {'pass':>5} {'fail':>5} {'xfail':>6} {'xpass':>6}")
for r in rows:
    print(f"{r[0]:32} {r[1]!s:>5} {r[2]!s:>5} {r[3]!s:>6} {r[4]!s:>6}")
tot = [sum(r[i] for r in rows if isinstance(r[i], int)) for i in range(1, 5)]
print(f"{'TOTAL':32} {tot[0]:>5} {tot[1]:>5} {tot[2]:>6} {tot[3]:>6}")
sys.exit(1 if bad else 0)
