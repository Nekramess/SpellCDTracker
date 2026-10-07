"""Gear warnings: missing off hand (Paladin/Warrior/Shaman/Rogue) and missing ranged weapon (Hunter).
Warning icons are drawn first in the buff row, dimmed, with a red border."""
from mock_env import Client, Checker

t = Checker("gear_test")
BUFF = "SpellCDTrackerBuffFrame"
TEX = {"main": "Interface\\PaperDoll\\UI-PaperDoll-Slot-MainHand", "offhand": "Interface\\PaperDoll\\UI-PaperDoll-Slot-SecondaryHand",
       "ranged": "Interface\\PaperDoll\\UI-PaperDoll-Slot-Ranged"}

def warn(c):
    """Gear warnings currently on screen, by key."""
    inv = {v: k for k, v in TEX.items()}
    return [inv[i["tex"]] for i in c.icons(BUFF) if i["tex"] in inv]

def setup(cls, **gear):
    c = Client(cls).boot(["Some Spell"])
    c.set_equip(**gear)
    c.tick(1.1)
    return c

OFFHAND = ["PALADIN", "WARRIOR", "SHAMAN", "ROGUE"]
for cls in OFFHAND:
    c = setup(cls, main="INVTYPE_WEAPON")
    t.check(f"{cls}: one-hander and nothing in the off hand -> 'offhand' warning", warn(c) == ["offhand"], c.icons(BUFF))
    i = c.icons(BUFF)[0]
    t.check(f"{cls}: the warning icon is dimmed with a red border", i["desat"] is True and abs(i["alpha"] - 0.55) < 1e-9 and i["border"] == [1, 0.1, 0.1], i)
    for off in ["INVTYPE_SHIELD", "INVTYPE_WEAPON", "INVTYPE_WEAPONOFFHAND", "INVTYPE_HOLDABLE"]:
        c = setup(cls, main="INVTYPE_WEAPON", off=off)
        t.check(f"{cls}: 1H + {off} -> no warning", warn(c) == [], c.icons(BUFF))
    c = setup(cls, main="INVTYPE_2HWEAPON")
    t.check(f"{cls}: two-hander -> no warning", warn(c) == [], c.icons(BUFF))
    c = setup(cls)
    t.check(f"{cls}: empty main hand -> 'main' warning", warn(c) == ["main"], c.icons(BUFF))
    c = setup(cls, main="INVTYPE_WEAPON", unknown=(16,))
    t.check(f"{cls}: main hand item whose data is not loaded yet -> no warning (unknown counts as fine)", warn(c) == [], c.icons(BUFF))
    c = setup(cls, main="INVTYPE_WEAPON", off="INVTYPE_SHIELD", unknown=(17,))
    t.check(f"{cls}: off hand item with unknown data counts as filled", warn(c) == [], c.icons(BUFF))
    c = setup(cls, main="INVTYPE_RANGEDRIGHT")
    t.check(f"{cls}: a bow in the main hand needs no off hand", warn(c) == [], c.icons(BUFF))

# Hunter: ranged
for loc in ["INVTYPE_RANGED", "INVTYPE_RANGEDRIGHT", "INVTYPE_THROWN"]:
    c = setup("HUNTER", main="INVTYPE_2HWEAPON", ranged=loc)
    t.check(f"HUNTER: {loc} in the ranged slot -> no warning", warn(c) == [], c.icons(BUFF))
c = setup("HUNTER", main="INVTYPE_2HWEAPON")
t.check("HUNTER: no ranged weapon -> 'ranged' warning", warn(c) == ["ranged"], c.icons(BUFF))
c = setup("HUNTER")
t.check("HUNTER: nothing equipped -> 'ranged' warning (the Hunter rule is only about ranged)", warn(c) == ["ranged"], c.icons(BUFF))
c = setup("HUNTER", main="INVTYPE_RANGEDRIGHT")
t.check("HUNTER: ranged weapon sitting in the main hand counts", warn(c) == [], c.icons(BUFF))
c = setup("HUNTER", main="INVTYPE_2HWEAPON", ranged="INVTYPE_RANGEDRIGHT", unknown=(18,))
t.check("HUNTER: ranged item with unknown data counts as filled", warn(c) == [], c.icons(BUFF))
c = setup("HUNTER", main="INVTYPE_2HWEAPON", ranged="INVTYPE_RELIC")
t.check("HUNTER: a non-ranged item in the ranged slot still warns", warn(c) == ["ranged"], c.icons(BUFF))

# Classes with no rule never warn
for cls in ["MAGE", "PRIEST", "WARLOCK", "DRUID"]:
    c = setup(cls)
    t.check(f"{cls}: no gear rule -> never warns, even with nothing equipped", warn(c) == [], c.icons(BUFF))
    c.slash("debug")
    t.check(f"{cls}: debug has no gear line", not any(p.strip().startswith("gear:") for p in c.printed))

# no equipment API / no item-info API
c = Client("PALADIN").boot(["Some Spell"]); c.exe("GetInventoryItemID = nil"); c.tick(1.1, 3)
t.check("GetInventoryItemID missing: no warning, no error", warn(c) == [] and c.errors() == [], c.errors())
c.slash("debug")
t.check("... debug says the equipment API is missing", any("equipment API missing" in p for p in c.printed))
c = Client("PALADIN").boot(["Some Spell"]); c.set_equip(main="INVTYPE_WEAPON"); c.exe("C_Item.GetItemInfoInstant = nil"); c.tick(1.1, 3)
t.check("C_Item.GetItemInfoInstant missing: ids present count as filled (no false warning), no error", warn(c) == [] and c.errors() == [], c.errors())

# timing: re-check at most once a second, immediately on PLAYER_EQUIPMENT_CHANGED
c = setup("PALADIN", main="INVTYPE_WEAPON")
t.check("setup: warning shown", warn(c) == ["offhand"])
c.set_equip(main="INVTYPE_WEAPON", off="INVTYPE_SHIELD"); c.tick(0.2)
t.check("equipping a shield is not noticed within the 1 s throttle", warn(c) == ["offhand"])
c.fire("PLAYER_EQUIPMENT_CHANGED"); c.tick(0.2)
t.check("PLAYER_EQUIPMENT_CHANGED forces a re-check on the next tick: warning clears", warn(c) == [], c.icons(BUFF))
c.set_equip(main="INVTYPE_WEAPON"); c.tick(0.2); still = warn(c)
c.tick(1.1)
t.check("without the event the change is still picked up after a second", still == [] and warn(c) == ["offhand"])

# in combat the warning is still there; combat does not clear it
c.combat(True); c.tick(1.1, 2)
t.check("warning persists in combat", warn(c) == ["offhand"] and c.errors() == [])

# order: gear warnings first, before buff icons
c = Client("PALADIN").boot(["Holy Shield"]); c.set_equip(main="INVTYPE_WEAPON"); c.set_buffs([("Holy Shield", 8, 10)]); c.tick(1.1)
ic = c.icons(BUFF)
t.check("gear warning is drawn before the buff icons", len(ic) == 2 and ic[0]["tex"] == TEX["offhand"] and ic[1]["tex"] != TEX["offhand"], ic)

# per-profile switch through the Tracked spells window
c = setup("PALADIN", main="INVTYPE_WEAPON")
c.slash("spells")
t.check("Tracked spells shows the 'Gear warning' toggle for Paladin", c.ev("SpellCDTrackerSpells.gearToggle._shown") is True)
t.check("toggle off via the window", c.click_check("Gear warning", False))
c.tick(1.1)
t.check("gear warning switched off: icon gone", warn(c) == [], c.icons(BUFF))
t.check("... and saved in the profile as gear=false", c.db()["profiles"]["PALADIN"]["gear"] is False)
c.click_check("Gear warning", True); c.tick(1.1)
t.check("switched back on: warning returns", warn(c) == ["offhand"])
c = setup("MAGE")
c.slash("spells")
t.check("Mage has no 'Gear warning' toggle", c.ev("SpellCDTrackerSpells.gearToggle._shown") is False)

# debug line
c = setup("WARRIOR", main="INVTYPE_WEAPON"); c.slash("debug")
t.check("debug prints 'gear: WARNING offhand' with the slot data", any("gear: WARNING offhand" in p and "main=INVTYPE_WEAPON" in p for p in c.printed), c.printed)
c = setup("WARRIOR", main="INVTYPE_2HWEAPON"); c.slash("debug")
t.check("debug prints 'gear: ok' when fine", any(p.strip().startswith("gear: ok") for p in c.printed))

t.finish()
