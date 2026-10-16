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
    ("wand: start-recovery spells shown as cooldowns in combat again",
     'if active and not s.onGCD and not recovery then return "secret" end', 'if active and not s.onGCD then return "secret" end', ["wand_test.py"]),
    ("wand: Shoot is tracked like any other spell",
     'if not ignore[lname] and not NEVER_TRACK[lname] then', 'if not ignore[lname] then', ["wand_test.py"]),
    ("wand: any spell with start recovery ignored, even with a real cooldown category",
     "return info.timeUntilEndOfStartRecovery ~= nil and info.activeCategory == nil", "return info.timeUntilEndOfStartRecovery ~= nil", ["wand_test.py"]),
    ("food: tracking on by default",
     "trackFood = false,        -- optional food", "trackFood = true,        -- optional food", ["food_test.py"]),
    ("food: 'Well Fed XP Boost' also counts as fed",
     'local FOOD_AURAS = { ["Well Fed"] = true }', 'local FOOD_AURAS = { ["Well Fed"] = true, ["Well Fed XP Boost"] = true }', ["food_test.py"]),
    ("food: aura name matched as a substring instead of exactly",
     "if a.name and FOOD_AURAS[a.name] then", 'if a.name and a.name:find("Well Fed") then', ["food_test.py"]),
    ("food: missing state loses its red border",
     'ShowMissing(ic, db.lastFoodIcon or FOOD_FALLBACK_ICON, "FOOD")', "ic.icon:SetTexture(FOOD_FALLBACK_ICON); SetBorder(ic, 0, 0, 0)", ["food_test.py"]),
    ("food: cached state never lapses in combat",
     "and GetTime() > a.expires then foodState = nil end", "and false then foodState = nil end", ["food_test.py"]),
    ("food: auras read even while locked in combat",
     "if AurasLocked() then\n        local a = foodState", "if false then\n        local a = foodState", ["food_test.py"]),
    ("food: switching off keeps the stale state",
     "if db.trackFood then Guard(UpdateFood) else foodState = nil end", "if db.trackFood then Guard(UpdateFood) end", ["food_test.py"]),
    ("food: last food icon not remembered",
     "if found and found.icon then db.lastFoodIcon = found.icon end", "if false then db.lastFoodIcon = found.icon end", ["food_test.py"]),
    ("food: Paladin panel shows it even when switched off",
     "if db.trackFood then\n        place(palaFrame.food)", "if true then\n        place(palaFrame.food)", ["food_test.py"]),
    ("food: buff row shows it even when switched off",
     "if db.trackFood and not isPaladin then", "if not isPaladin then", ["food_test.py"]),
    ("food: Paladin gets a second food icon in the buff row",
     "if db.trackFood and not isPaladin then", "if db.trackFood then", ["food_test.py"]),
    ("food: options check box does not save",
     "function() return db.trackFood end, function(v) db.trackFood = v end, y)", "function() return db.trackFood end, function(v) end, y)", ["food_test.py"]),
    ("aura: default icon is the last known Aura instead of the first (Devotion)",
     "if known[an] then defaultAura = an break end", "if known[an] then defaultAura = an end", ["tracking_test.py"]),
    ("aura: the single icon keeps showing the default instead of the active Aura",
     "ic.icon:SetTexture(known[active].icon)", "ic.icon:SetTexture(known[defaultAura].icon)", ["tracking_test.py"]),
    ("aura: no Aura on no longer red",
     'ShowMissing(ic, known[defaultAura].icon, "AURA")', "ic.icon:SetTexture(known[defaultAura].icon); SetBorder(ic, 0, 0, 0)", ["tracking_test.py"]),
    ("aura: hidden when the profile switches Auras off is ignored",
     "local showAura = prof.auras ~= false and defaultAura ~= nil", "local showAura = defaultAura ~= nil", ["tracking_test.py"]),
    ("food: /scdt food (no argument) no longer toggles back off",
     "db.trackFood = not db.trackFood", "db.trackFood = true", ["food_test.py"]),
    ("combo: secret points compared (secret guard off)",
     "local secret = issecret(pts)", "local secret = false", ["combo_test.py"]),
    ("combo: Druid outside cat form still shows",
     "elseif prof.combo == false or max <= 0 or pts == nil then", "elseif prof.combo == false or pts == nil then", ["combo_test.py"]),
    ("combo: profile switch ignored",
     "elseif prof.combo == false or max <= 0 or pts == nil then", "elseif max <= 0 or pts == nil then", ["combo_test.py"]),
    ("combo: filled pips count off by one",
     "if i <= ptsShown then pip.fill", "if i < ptsShown then pip.fill", ["combo_test.py"]),
    ("combo: shown out of combat with 0 points",
     "show = fighting or ptsShown > 0", "show = true", ["combo_test.py"]),
    ("combo: reset positions in /scdt reset forgets it",
     "        db.combo = CopyTable(defaults.combo)\n        if comboFrame then ApplyPosition(comboFrame, \"combo\") end\n        db.power = CopyTable(defaults.power)\n        if powerFrame then ApplyPosition(powerFrame, \"power\") end\n        print(",
     "        db.power = CopyTable(defaults.power)\n        if powerFrame then ApplyPosition(powerFrame, \"power\") end\n        print(", ["combo_test.py"]),
    ("ApplyLock stops at the first missing frame (non-Paladin buff row not draggable)",
     "local f = _G[name]\n        if f then", "local f = _G[name]\n        if not f then break end\n        if f then", ["combo_test.py"]),
    ("power: only shown out of combat",
     "else show = fighting end\n    if not show then powerFrame:Hide()", "else show = not fighting end\n    if not show then powerFrame:Hide()", ["power_test.py"]),
    ("power: secret energy compared (guard off)",
     "local secret = issecret(cur) or issecret(max)", "local secret = false", ["power_test.py"]),
    ("power: profile switch ignored",
     "elseif prof.power == false or cur == nil or max == nil then show = false", "elseif cur == nil or max == nil then show = false", ["power_test.py"]),
    ("power: /scdt reset forgets the bar position",
     "        db.power = CopyTable(defaults.power)\n        if powerFrame then ApplyPosition(powerFrame, \"power\") end\n        print(", "        print(", ["power_test.py"]),
    ("cost icons: castable ability stays gray",
     "                    ic.icon:SetDesaturated(false)\n                    ic:SetAlpha(1)\n                    ic.text:SetTextColor(1, 1, 1)", "                    ic.text:SetTextColor(1, 1, 1)", ["power_test.py"]),
    ("cost icons: short on energy no longer red",
     "                    ic.text:SetTextColor(1, 0.3, 0.3)\n                else\n                    ic.text:SetTextColor(0.8, 0.8, 0.8)", "                    ic.text:SetTextColor(1, 1, 1)\n                else\n                    ic.text:SetTextColor(0.8, 0.8, 0.8)", ["power_test.py"]),
    ("cost icons: mana abilities also get the cost treatment",
     "(c.type == POWER_RAGE or c.type == POWER_ENERGY) and", "true and", ["power_test.py"]),
    ("cost icons: IsSpellUsable result ignored",
     "return usable and true or false, (not issecret(lacks))", "return true, (not issecret(lacks))", ["power_test.py"]),
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
