"""Addon loads under the Forever-like mock with no Lua error, for every class; the Forever-absent APIs stay absent."""
import os
from mock_env import Client, Checker, ROOT

t = Checker("load_test")
CLASSES = ["WARRIOR", "PALADIN", "HUNTER", "ROGUE", "PRIEST", "SHAMAN", "MAGE", "WARLOCK", "DRUID"]

# mock integrity: these must NOT exist in the Forever-like client (Forever UI source 1.60.1)
c0 = Client("PALADIN")
for name in ["C_Console", "issecret", "GetMinimapShape", "GetSpellInfo", "GetSpellCooldown", "GetSpecialization", "OffhandHasWeapon", "UnitBuff"]:
    t.check(f"mock integrity: {name} is absent, like Forever", c0.ev(f"_G['{name}'] == nil"))
t.check("mock integrity: issecretvalue exists (and not issecret)", c0.ev("issecretvalue ~= nil"))

# toc list: files exist, in order
toc = [l.strip() for l in open(os.path.join(ROOT, "SpellCDTracker.toc")) if l.strip() and not l.startswith("#")]
t.check("toc lists SpellCDTracker.lua and every listed file exists", toc == ["SpellCDTracker.lua"] and all(os.path.exists(os.path.join(ROOT, f)) for f in toc), toc)
t.check("toc Interface is 16001", "## Interface: 16001" in open(os.path.join(ROOT, "SpellCDTracker.toc")).read())
t.check("toc declares SavedVariables: SpellCDTrackerDB", "## SavedVariables: SpellCDTrackerDB" in open(os.path.join(ROOT, "SpellCDTracker.toc")).read())

for cls in CLASSES:
    c = Client(cls)
    c.load()
    t.check(f"{cls}: file runs with no Lua error before ADDON_LOADED", c.raised == [], c.raised)
    t.check(f"{cls}: nothing is touched before ADDON_LOADED (db not created)", c.ev("SpellCDTrackerDB") is None)
    t.check(f"{cls}: slash command registered (/scdt -> SPELLCDTRACKER)", c.ev("SLASH_SPELLCDTRACKER1") == "/scdt" and c.ev("type(SlashCmdList.SPELLCDTRACKER)") == "function")
    c.fire("ADDON_LOADED", "Blizzard_SomethingElse")
    t.check(f"{cls}: another addon's ADDON_LOADED is ignored", c.ev("SpellCDTrackerDB") is None)
    c.add_spells("Some Spell")
    c.login()
    t.check(f"{cls}: login and first ticks raise no error", c.errors() == [], c.errors())
    t.check(f"{cls}: SpellCDTrackerDB created at ADDON_LOADED", c.ev("type(SpellCDTrackerDB)") == "table")
    t.check(f"{cls}: cooldown frame exists", c.ev("SpellCDTrackerCDFrame ~= nil"))
    t.check(f"{cls}: Paladin panel only for Paladin", c.ev("SpellCDTrackerPalaFrame ~= nil") == (cls == "PALADIN"))
    t.check(f"{cls}: buff frame exists for every class (all nine have buff groups)", c.ev("SpellCDTrackerBuffFrame ~= nil"))
    t.check(f"{cls}: minimap button exists", c.ev("SpellCDTrackerMinimapButton ~= nil"))
    c.tick(0.2, 30)
    t.check(f"{cls}: 6 seconds of ticks, no error", c.errors() == [], c.errors())
    c.slash("debug")
    t.check(f"{cls}: /scdt debug prints and does not error", c.errors() == [] and any("spells tracked" in p for p in c.printed), c.errors())

# Frame methods the addon calls that the mock does not model explicitly (harmless no-ops): informational
c = Client("PALADIN").boot(["Judgement"])
c.slash("")       # options window
c.slash("spells") # tracked spells window
c.tick(0.2, 3)
t.info("frame methods used but not explicitly mocked (no-ops): " + ", ".join(sorted(c.ev("(function() local o = {} for k in pairs(UNKNOWN_CALLS) do o[#o+1] = k end return table.concat(o, ', ') end)()").split(", "))))
t.check("options + tracked spells windows build with no error", c.errors() == [], c.errors())

# no GetWeaponEnchantInfo shim at all (CVar loadDeprecationFallbacks off): still loads, reports it
c = Client("SHAMAN", shims=()).boot(["Rockbiter Weapon"])
c.tick(0.2, 5)
c.slash("debug")
t.check("Shaman without the GetWeaponEnchantInfo shim: no error, debug says it is missing",
        c.errors() == [] and any("GetWeaponEnchantInfo missing" in p for p in c.printed), c.errors())

# UnitBuff is never needed when C_UnitAuras.GetAuraDataByIndex exists
c = Client("MAGE", shims=("UnitBuff",)).boot(["Arcane Intellect"])
c.exe("function UnitBuff() error('UnitBuff must not be used when C_UnitAuras exists') end")
c.tick(0.2, 5)
t.check("aura reads go through C_UnitAuras, not the deprecated UnitBuff shim", c.errors() == [] and c.ev("W.calls.aura") > 0, c.errors())

t.finish()
