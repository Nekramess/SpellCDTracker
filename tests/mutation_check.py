"""Mutation check: break SpellCDTracker.lua in a TEMPORARY COPY (the repo file is never touched), point the suite at the copy with
SCDT_LUA, and confirm at least one test file fails. Run from the repo root: python3 tests/mutation_check.py"""
import os
import subprocess
import sys
import tempfile

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
orig = open(os.path.join(root, "SpellCDTracker.lua"), encoding="utf-8").read()

MUTATIONS = [
    ("secret-value guard removed in ReadCooldown",
     "if not (issecret(start) or issecret(dur)) then", "if true then", ["combat_test.py"]),
    ("issecret alias always false (every secret guard off)",
     "local issecret = issecretvalue or function() return false end", "local issecret = function() return false end", ["combat_test.py"]),
    ("AurasLocked() never reports locked (aura API read in combat)",
     "if ok then return res and true or false end", "if ok then return false end", ["combat_test.py"]),
    ("totem secret guard removed",
     "if ok and not (issecret(have) or issecret(start) or issecret(dur) or issecret(name)) then", "if ok then", ["combat_test.py"]),
    ("minimap: saved 'square' ignored",
     'if mode == "square" then return "SQUARE" end', 'if mode == "square" then return "ROUND" end', ["minimap_test.py", "savedvars_test.py"]),
    ("minimap: round/square quadrant test inverted",
     "if quads[q] then return x * halfW, y * halfH end", "if not quads[q] then return x * halfW, y * halfH end", ["minimap_test.py"]),
    ("minimap: GetMinimapShape errors no longer contained",
     "local ok, name = pcall(fn)", "local ok, name = true, fn()", ["minimap_test.py"]),
    ("minimap auto no longer clears the override",
     "db.minimapShape = nil", 'db.minimapShape = "round"', ["slash_test.py", "minimap_test.py"]),
    ("gear: missing off hand no longer warns",
     'if not offId then gearWarn[#gearWarn + 1] = "offhand" end', 'if offId then gearWarn[#gearWarn + 1] = "offhand" end', ["gear_test.py"]),
    ("gear: Hunter rule removed",
     "HUNTER  = { ranged = true },", "HUNTER  = {},", ["gear_test.py"]),
    ("gear: PLAYER_EQUIPMENT_CHANGED no longer forces a re-check",
     "gearAt = 0\n    elseif", "elseif", ["gear_test.py"]),
    ("pins: ready icons shown out of combat without readyAlways",
     "local showReady = InCombat() or db.readyAlways", "local showReady = true", ["profile_test.py", "combat_test.py"]),
    ("saved defaults: swingCombatOnly default flipped",
     "swingCombatOnly = true,   --", "swingCombatOnly = false,   --", ["savedvars_test.py", "slash_test.py"]),
]

def run(files, lua):
    env = dict(os.environ, SCDT_LUA=lua)
    bad = []
    for f in files:
        p = subprocess.run([sys.executable, os.path.join(here, f)], cwd=root, env=env, capture_output=True, text=True)
        if p.returncode != 0:
            bad.append(f)
    return bad

survived = 0
with tempfile.TemporaryDirectory() as td:
    base = os.path.join(td, "SpellCDTracker.lua")
    open(base, "w", encoding="utf-8").write(orig)
    allfiles = sorted(f for f in os.listdir(here) if f.endswith("_test.py"))
    print("baseline (unmodified copy):", "all pass" if not run(allfiles, base) else "FAILURES")
    for label, old, new, files in MUTATIONS:
        if orig.count(old) != 1:
            print(f"ERROR mutation target not found exactly once: {label}")
            survived += 1
            continue
        path = os.path.join(td, "mut.lua")
        open(path, "w", encoding="utf-8").write(orig.replace(old, new))
        killed_by = run(files, path)
        if killed_by:
            print(f"KILLED   {label}  (failed: {', '.join(killed_by)})")
        else:
            print(f"SURVIVED {label}  (no test noticed)")
            survived += 1
print("mutations survived:", survived)
sys.exit(1 if survived else 0)
