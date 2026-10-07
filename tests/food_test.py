"""Optional food buff ("Well Fed", 0.13.0): off by default; when on it is always shown next to the buffs (Paladin panel after
Righteous Fury, buff row of every other class after gear warnings / imbues / pet), red while missing, countdown while up.
Aura names are matched exactly ("Well Fed"; "Well Fed XP Boost" is a different aura and does not count).
Simulated client only; the live Forever client has not been checked."""
from mock_env import Client, Checker

t = Checker("food_test")
BUFF = "SpellCDTrackerBuffFrame"
PALA = "SpellCDTrackerPalaFrame"
RED_MISSING = [1, 0.1, 0.1]
BLACK = [0, 0, 0]
FALLBACK = "Interface\\Icons\\INV_Misc_Food_01"
GEAR_OFFHAND = "Interface\\PaperDoll\\UI-PaperDoll-Slot-SecondaryHand"
CHECK = "Track food buff (Well Fed)"
WELL_FED = ("Well Fed", 800, 900)

PAL = ["Judgement", "Seal of Righteousness", "Righteous Fury", "Devotion Aura", "Retribution Aura"]
def pal(buffs=(), on=True):
    c = Client("PALADIN").boot(PAL)
    if on:
        c.slash("food on")
    c.set_buffs(list(buffs)); c.tick(1.1)
    return c
def food(c): return c.icon_at(f"{PALA}.food")
def x_of(c, expr): return c.ev(f"{expr}._pt[4]")

MAGE = ["Arcane Intellect", "Frost Armor", "Ice Barrier"]
def mage(buffs=(), on=True):
    c = Client("MAGE").boot(MAGE)
    if on:
        c.slash("food on")
    c.set_buffs(list(buffs)); c.tick(1.1)
    return c

def check_state(c, label):
    c.lua.globals().LBL = label
    return c.ev("""(function() for _, f in ipairs(CREATED) do
        if f._kind == "CheckButton" and f._fs and f._fs[1] and f._fs[1]._text == LBL then return f._checked end end return nil end)()""")

# ---------------------------------------------------------------- off by default
c = pal([WELL_FED], on=False)
t.check("default: trackFood is saved as false", c.db()["trackFood"] is False, c.db().get("trackFood"))
t.check("off: no food icon on the Paladin panel even with Well Fed up", food(c)["shown"] is False)
c = mage([WELL_FED], on=False)
t.check("off: Mage buff row is unchanged (only the two missing maintain buffs, no food icon)",
        len(c.icons(BUFF)) == 2 and 7001 not in c.icon_ids(BUFF), c.icons(BUFF))
t.check("off: nothing raised", c.errors() == [], c.errors())

# ---------------------------------------------------------------- Paladin panel
c = pal([])
f = food(c)
t.check("on, no Well Fed: icon is shown, dimmed, with the red 'missing' border and no countdown",
        f["shown"] and f["desat"] is True and f["border"] == RED_MISSING and f["text"] == "", f)
t.check("on, no Well Fed, never seen one: generic food icon", f["tex"] == FALLBACK, f)

c = pal([WELL_FED])
f = food(c)
t.check("Well Fed up: its own icon, a countdown, normal border, full colour",
        f["shown"] and f["tex"] == 7001 and f["text"] != "" and f["border"] == BLACK and f["desat"] is False and f["alpha"] == 1, f)
t.check("Well Fed up: the cooldown swirl uses the aura's duration", f["cdDur"] == 900, f)
t.check("the last seen food icon is saved", c.db()["lastFoodIcon"] == 7001, c.db())
c.set_buffs([]); c.tick(1.1)
f = food(c)
t.check("Well Fed falls off: red 'missing' again, now with the icon of the food you had",
        f["desat"] is True and f["border"] == RED_MISSING and f["tex"] == 7001, f)

c = pal([("Well Fed XP Boost", 800, 900)])
t.check("'Well Fed XP Boost' alone does not count as fed", food(c)["desat"] is True and food(c)["border"] == RED_MISSING, food(c))
c = pal([("Seal of Righteousness", 25, 30), ("Blessing of Might", 280, 300, "player")])
t.check("other buffs do not count as fed", food(c)["desat"] is True, food(c))
c = pal([("Well Fed XP Boost", 800, 900), ("Well Fed", 800, 900)])
t.check("with both auras up, the Well Fed aura (not the XP boost) drives the icon", food(c)["tex"] == 7002 and food(c)["desat"] is False, food(c))
c = pal([("Well Fed", 800, 900, "party1")])
t.check("Well Fed from another player's feast counts (no source check)", food(c)["desat"] is False and food(c)["text"] != "", food(c))
c = pal([("Well Fed", None, None)])
t.check("Well Fed with no timer: shown as active, no countdown", food(c)["desat"] is False and food(c)["text"] == "", food(c))

# position: after Righteous Fury, before the Auras; the Auras shift right by one icon only while it is on
c = pal([WELL_FED])
rf_x, fd_x, a1_x = x_of(c, f"{PALA}.rf"), x_of(c, f"{PALA}.food"), x_of(c, f"{PALA}.auraIcons[1]")
t.check("food sits right after Righteous Fury, and the first Aura right after the food", fd_x == rf_x + 44 and a1_x == fd_x + 44, (rf_x, fd_x, a1_x))
c2 = pal([WELL_FED], on=False)
t.check("food off: the first Aura is where it always was (right after Righteous Fury)", x_of(c2, f"{PALA}.auraIcons[1]") == rf_x + 44, x_of(c2, f"{PALA}.auraIcons[1]"))
t.check("the panel is one icon wider with the food icon", c.ev(f"{PALA}._w") == c2.ev(f"{PALA}._w") + 44, (c.ev(f"{PALA}._w"), c2.ev(f"{PALA}._w")))

# the Paladin buff row never carries the food icon (the panel does)
c = Client("PALADIN").boot(["Holy Shield", "Divine Shield"]); c.set_equip(main="INVTYPE_2HWEAPON"); c.slash("food on")
c.set_buffs([("Holy Shield", 8, 10), WELL_FED]); c.tick(1.1)
t.check("Paladin buff row: only Holy Shield, no second (food) icon", len(c.icons(BUFF)) == 1 and c.errors() == [], c.icons(BUFF))

# ---------------------------------------------------------------- combat (aura reads are secret)
c = pal([("Well Fed", 5, 900)])
c.combat(True); c.tick(1.0)
f = food(c)
t.check("combat: Well Fed keeps its last known state and keeps counting down", f["shown"] and f["desat"] is False and f["text"] != "", f)
c.tick(6.0)
f = food(c)
t.check("combat: once its own timer has run out it goes red", f["desat"] is True and f["border"] == RED_MISSING, f)
t.check("combat: no aura read, nothing raised", c.errors() == [], c.errors())
c.set_buffs([WELL_FED]); c.combat(False); c.tick(0.2)
t.check("leaving combat re-reads the auras: active again", food(c)["desat"] is False and food(c)["tex"] == 7001, food(c))

c = pal([WELL_FED])
c.combat(True)
c.slash("food off"); c.tick(0.2)
t.check("switched off in combat: icon hidden", food(c)["shown"] is False)
c.slash("food on"); c.tick(0.2)
t.check("switched back on in combat: starts from 'missing', never from stale state", food(c)["desat"] is True and food(c)["border"] == RED_MISSING, food(c))
t.check("... without errors", c.errors() == [], c.errors())

c = mage([("Arcane Intellect", 1700, 1800), WELL_FED])
c.combat(True); c.tick(1.1)
t.check("Mage in combat: food keeps its state, nothing raised", c.errors() == [] and any(i["tex"] == 7002 and i["desat"] is False for i in c.icons(BUFF)), (c.errors(), c.icons(BUFF)))

# ---------------------------------------------------------------- buff row (every other class)
c = mage([])
ic = c.icons(BUFF)
t.check("Mage: food missing -> first icon, dimmed, red border, generic food icon; maintain buffs follow",
        len(ic) == 3 and ic[0]["tex"] == FALLBACK and ic[0]["desat"] and ic[0]["border"] == RED_MISSING, ic)
c = mage([("Arcane Intellect", 1700, 1800), ("Frost Armor", 1700, 1800), WELL_FED])
ic = c.icons(BUFF)
t.check("Mage: all up -> food first (icon of the Well Fed aura, countdown), then the two buffs",
        len(ic) == 3 and ic[0]["tex"] == 7003 and ic[0]["text"] != "" and ic[0]["border"] == BLACK and ic[0]["desat"] is False, ic)

c = Client("WARRIOR").boot(["Battle Shout"]); c.set_equip(main="INVTYPE_WEAPON"); c.slash("food on"); c.tick(1.1)
ic = c.icons(BUFF)
t.check("Warrior: gear warning first, then food, then the buff groups",
        len(ic) == 3 and ic[0]["tex"] == GEAR_OFFHAND and ic[1]["tex"] == FALLBACK and ic[1]["border"] == RED_MISSING and ic[2]["desat"], ic)

c = Client("ROGUE").boot(["Poisons", "Evasion"]); c.set_equip(main="INVTYPE_WEAPON", off="INVTYPE_WEAPON"); c.slash("food on"); c.tick(1.1)
ic = c.icons(BUFF)
t.check("Rogue: poison reminders (one per hand) come before the food icon", len(ic) == 3 and ic[2]["tex"] == FALLBACK, ic)

# worst case for the 14-icon row: dual-wield Shaman, both imbues, four totems, all six buff groups, plus food
c = Client("SHAMAN").boot(["Rockbiter Weapon", "Flametongue Weapon", "Lightning Shield", "Searing Totem"])
c.set_equip(main="INVTYPE_WEAPON", off="INVTYPE_WEAPON"); c.slash("food on")
c.set_enchant("main", 1800000); c.set_enchant("off", 1800000)
for slot, n in enumerate(["Searing Totem", "Stoneskin Totem", "Mana Spring Totem", "Windfury Totem"], 1):
    c.set_totem(slot, n, 30, 60)
c.set_buffs([("Lightning Shield", 600, 600), ("Shamanistic Rage", 10, 15), ("Bloodlust", 30, 40), ("Ghost Wolf", None, None),
             ("Nature's Swiftness", None, None), ("Elemental Mastery", None, None), WELL_FED])
c.tick(1.1)
ic = c.icons(BUFF)
t.check("fully loaded Shaman row shows everything, including the last buff group and the food icon",
        len(ic) == 13 and 7006 in [i["tex"] for i in ic] and 7007 in [i["tex"] for i in ic] and c.errors() == [], (len(ic), c.errors()))

# ---------------------------------------------------------------- saved settings
c = Client("MAGE", saved={"trackFood": True}).boot(MAGE); c.tick(1.1)
t.check("a saved trackFood=true is honoured at login", len(c.icons(BUFF)) == 3 and c.icons(BUFF)[0]["tex"] == FALLBACK, c.icons(BUFF))
c = Client("MAGE", saved={"cdSize": 50}).boot(MAGE); c.tick(1.1)
t.check("an older saved database (no trackFood) gets the default: off", c.db()["trackFood"] is False and len(c.icons(BUFF)) == 2, c.db().get("trackFood"))

# ---------------------------------------------------------------- slash command and options window
c = mage([], on=False)
c.slash("food on")
t.check("/scdt food on", c.db()["trackFood"] is True and any("food buff tracking ON" in l for l in c.new_output()), c.new_output())
c.slash("food off")
t.check("/scdt food off", c.db()["trackFood"] is False and any("food buff tracking OFF" in l for l in c.new_output()), c.new_output())
c.slash("food")
t.check("/scdt food on its own toggles", c.db()["trackFood"] is True)
c.slash("food")
t.check("... and toggles back", c.db()["trackFood"] is False)
c.slash("food maybe")
t.check("/scdt food <garbage> prints the usage and changes nothing", c.db()["trackFood"] is False and any("/scdt food on | off" in l for l in c.new_output()), c.new_output())
c.slash("help")
t.check("the general usage line lists food", any("food [on|off]" in l for l in c.new_output()), c.new_output())

c = mage([], on=False)
c.slash("")
t.check("options window has the food check box, unchecked by default", check_state(c, CHECK) is False, check_state(c, CHECK))
t.check("clicking it switches the feature on", c.click_check(CHECK, True) and c.db()["trackFood"] is True)
c.tick(1.1)
t.check("... and the icon appears", len(c.icons(BUFF)) == 3 and c.icons(BUFF)[0]["tex"] == FALLBACK, c.icons(BUFF))
c.slash("food off")
t.check("/scdt food off while the options window is open updates the check box", check_state(c, CHECK) is False, check_state(c, CHECK))
c.click_check(CHECK, True); c.click_check(CHECK, False); c.tick(1.1)
t.check("unchecking hides it again", len(c.icons(BUFF)) == 2 and c.db()["trackFood"] is False, c.icons(BUFF))

# ---------------------------------------------------------------- /scdt debug
c = pal([WELL_FED])
c.slash("debug")
out = "\n".join(c.new_output())
t.check("/scdt debug reports food tracking and state", "food: tracking ON | active: Well Fed" in out, out)
c = pal([], on=False)
c.slash("debug")
out = "\n".join(c.new_output())
t.check("/scdt debug reports food tracking off", "food: tracking OFF | no Well Fed seen" in out, out)

t.finish()
