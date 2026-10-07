"""Buff / totem / imbue / pet / Paladin-panel basics, out of combat (combat paths are in combat_test.py)."""
from mock_env import Client, Checker

t = Checker("tracking_test")
BUFF = "SpellCDTrackerBuffFrame"
RED_MISSING = [1, 0.1, 0.1]
RED_WARN = [1, 0.2, 0.2]
BLACK = [0, 0, 0]

# ---------------------------------------------------------------- Paladin panel
PAL = ["Judgement", "Seal of Righteousness", "Seal of Command", "Blessing of Might", "Righteous Fury", "Devotion Aura", "Retribution Aura"]
def pal(buffs=()):
    c = Client("PALADIN").boot(PAL)
    c.set_buffs(list(buffs)); c.tick(0.2)
    return c
def pic(c, which): return c.icon_at(f"SpellCDTrackerPalaFrame.{which}")

c = pal([("Seal of Righteousness", 25, 30), ("Blessing of Might", 280, 300, "player"), ("Righteous Fury", 1700, 1800, "player"), ("Devotion Aura", None, None, "player")])
s, b, rf = pic(c, "seal"), pic(c, "blessing"), pic(c, "rf")
t.check("Seal active: its icon, a countdown, normal border", s["tex"] == 7001 and s["text"] != "" and s["border"] == BLACK and s["desat"] is False, s)
t.check("Blessing (mine) active with countdown", b["tex"] == 7002 and b["text"] != "", b)
t.check("Righteous Fury active (known + active)", rf["tex"] == 7003 and rf["text"] != "" and rf["border"] == BLACK, rf)
au = c.icon_at("SpellCDTrackerPalaFrame.aura")
t.check("Auras are ONE icon: with Devotion Aura on it shows Devotion's icon, full colour, normal border",
        au["shown"] and au["tex"] == c.spell_icon("Devotion Aura") and au["alpha"] == 1 and au["desat"] is False and au["border"] == BLACK, au)
c2 = pal([("Retribution Aura", None, None, "player")])
au = c2.icon_at("SpellCDTrackerPalaFrame.aura")
t.check("with Retribution Aura on, the same icon shows Retribution's icon (always the active Aura)",
        au["tex"] == c2.spell_icon("Retribution Aura") and au["desat"] is False and au["border"] == BLACK, au)
t.check("no 'NO AURA' warning while an Aura is up", c.ev("SpellCDTrackerPalaFrame.warn._text") == "")
db = c.db()
t.check("last seen Seal/Blessing/RF icons and durations are saved for combat",
        db["lastSealIcon"] == 7001 and db["lastBlessIcon"] == 7002 and db["lastRFIcon"] == 7003
        and db["durations"]["Seal of Righteousness"] == 30 and db["durations"]["Blessing of Might"] == 300, db)

c = pal([("Seal of Righteousness", 4, 30)])
t.check("Seal under 5 s left: red warning border", pic(c, "seal")["border"] == RED_WARN, pic(c, "seal"))
c = pal([("Seal of Righteousness", 10, 30)])
t.check("Seal at 10 s left: still normal border", pic(c, "seal")["border"] == BLACK)

c = pal([])
s, b, rf = pic(c, "seal"), pic(c, "blessing"), pic(c, "rf")
t.check("Seal missing: dimmed icon (a Seal you know) with red border, no countdown", s["desat"] is True and s["border"] == RED_MISSING and s["text"] == "" and s["tex"] is not None, s)
t.check("Blessing missing: same", b["desat"] is True and b["border"] == RED_MISSING, b)
t.check("Righteous Fury missing (known): shown as missing", rf["shown"] and rf["desat"] is True and rf["border"] == RED_MISSING, rf)
t.check("no Aura active: 'NO AURA' warning", c.ev("SpellCDTrackerPalaFrame.warn._text") == "NO AURA")
au = c.icon_at("SpellCDTrackerPalaFrame.aura")
t.check("no Aura active: the one Aura icon is Devotion Aura (the default), dimmed, with the red 'missing' border",
        au["shown"] and au["tex"] == c.spell_icon("Devotion Aura") and au["desat"] is True and au["border"] == RED_MISSING, au)
c3 = Client("PALADIN").boot(["Judgement", "Seal of Righteousness", "Retribution Aura"]); c3.tick(0.2)
t.check("Devotion Aura not known: the default icon is the first Aura you do know",
        c3.icon_at("SpellCDTrackerPalaFrame.aura")["tex"] == c3.spell_icon("Retribution Aura") and c3.icon_at("SpellCDTrackerPalaFrame.aura")["border"] == RED_MISSING)

c = pal([("Blessing of Might", 280, 300, "party1"), ("Devotion Aura", None, None, "party1")])
t.check("someone else's Blessing does not count as mine", pic(c, "blessing")["desat"] is True)
t.check("someone else's Aura does not count either (NO AURA)", c.ev("SpellCDTrackerPalaFrame.warn._text") == "NO AURA")
c = pal([("Righteous Fury", 1700, 1800, "party1")])
t.check("someone else's Righteous Fury does not count", pic(c, "rf")["desat"] is True)

c = Client("PALADIN").boot(["Judgement"]); c.tick(0.2)
t.check("no Seal spells known and none cached: dark tile with the word SEAL", pic(c, "seal")["color"] is not None and pic(c, "seal")["text"] == "SEAL", pic(c, "seal"))
t.check("Righteous Fury not known: hidden", pic(c, "rf")["shown"] is False)
t.check("no Auras known: no icons and no NO AURA warning", c.ev("SpellCDTrackerPalaFrame.warn._text") == "")

c = pal([("Seal of Righteousness", 25, 30)])
c.slash("spells")
for label, key, frame in [("Seal", "seal", "seal"), ("Blessing", "blessing", "blessing"), ("Righteous Fury", "rf", "rf")]:
    c.click_check(label, False); c.tick(0.2)
    t.check(f"profile toggle '{label}' off hides that icon and saves {key}=false", pic(c, frame)["shown"] is False and c.db()["profiles"]["PALADIN"][key] is False)
c.click_check("Auras", False); c.tick(0.2)
t.check("profile toggle 'Auras' off hides the Aura icon and the warning", c.icon_at("SpellCDTrackerPalaFrame.aura")["shown"] is False and c.ev("SpellCDTrackerPalaFrame.warn._text") == "")

# Paladin buff row (pbuff): shows only while active
c = Client("PALADIN").boot(["Holy Shield", "Divine Shield"]); c.set_equip(main="INVTYPE_2HWEAPON")
c.set_buffs([("Holy Shield", 8, 10)]); c.tick(1.1)
t.check("Paladin buff row: Holy Shield shows while active, Divine Shield (not up) does not", len(c.icons(BUFF)) == 1)
t.check("Paladin buff row lives in 'pbuff' (own saved position)", c.ev("SpellCDTrackerBuffFrame._pt[5]") == -280)

# ---------------------------------------------------------------- Mage / buff row
MAGE = ["Arcane Intellect", "Frost Armor", "Ice Barrier", "Fireball"]
def mage(buffs=(), known=MAGE):
    c = Client("MAGE").boot(list(known)); c.set_buffs(list(buffs)); c.tick(0.2)
    return c

c = mage()
ic = c.icons(BUFF)
t.check("maintain groups (Intellect, Armor) show as red 'missing' icons when you know the spell", len(ic) == 2 and all(i["desat"] and i["border"] == RED_MISSING for i in ic), ic)
t.check("non-maintain group (Ice Barrier) shows nothing while not active", all(i["tex"] != c.spell_icon("Ice Barrier") for i in ic))
c = mage(known=["Fireball"])
t.check("a maintain buff you have not learned never shows as missing", c.icons(BUFF) == [])

c = mage([("Arcane Intellect", 1700, 1800), ("Frost Armor", 8, 1800), ("Ice Barrier", 40, 60)])
ic = {i["tex"]: i for i in c.icons(BUFF)}
t.check("active buffs: three icons with countdowns", len(ic) == 3 and all(i["text"] != "" for i in ic.values()), ic)
t.check("maintain buff under 10 s: red warn border; others normal", ic[7002]["border"] == RED_WARN and ic[7001]["border"] == BLACK, ic)
t.check("non-maintain buff never gets the red warning", ic[7003]["border"] == BLACK)
t.check("icon cache saved per group", c.db()["buffIcons"]["armor"] == 7002 and c.db()["buffIcons"]["int"] == 7001, c.db()["buffIcons"])
c.set_buffs([]); c.tick(0.2)
ic = c.icons(BUFF)
t.check("buff falls off: maintain buffs go to 'missing' with the last seen icon, Ice Barrier disappears",
        len(ic) == 2 and {i["tex"] for i in ic} == {7001, 7002} and all(i["desat"] for i in ic), ic)

c = mage([("Arcane Brilliance", 1700, 1800)], known=["Arcane Intellect"])
t.check("a group matches any of its spell names (Arcane Brilliance satisfies the Intellect group): one icon, active", len(c.icons(BUFF)) == 1 and c.icons(BUFF)[0]["desat"] is False)
c = mage([("Arcane Intellect", 1700, 1800), ("Arcane Brilliance", 1700, 1800)], known=["Arcane Intellect"])
t.check("two buffs of one group: one icon only", len(c.icons(BUFF)) == 1)
c = mage([("Ice Barrier", 40, 60)]); c.slash("ignore Ice Barrier"); c.tick(0.2)
t.check("/scdt ignore hides an active tracked buff (only the two 'missing' maintain icons remain)", len(c.icons(BUFF)) == 2 and all(i["desat"] for i in c.icons(BUFF)), c.icons(BUFF))
c = mage(); c.slash("ignore Frost Armor"); c.slash("ignore Arcane Intellect"); c.tick(0.2)
t.check("/scdt ignore hides a missing maintain buff", c.icons(BUFF) == [])
c = mage([("Frost Armor", None, None)])
armor = [i for i in c.icons(BUFF) if i["tex"] == 7001]
t.check("a buff with no duration (permanent) shows active with no countdown", len(armor) == 1 and armor[0]["desat"] is False and armor[0]["text"] == "", c.icons(BUFF))

# ---------------------------------------------------------------- Priest / Druid / Warlock / Warrior group basics
c = Client("PRIEST").boot(["Power Word: Fortitude", "Inner Fire", "Renew"]); c.set_buffs([("Prayer of Fortitude", 1700, 1800)]); c.tick(0.2)
ic = c.icons(BUFF)
t.check("Priest: Fortitude (Prayer of Fortitude counts) active, Inner Fire missing, Renew absent", len(ic) == 2 and sorted(i["desat"] for i in ic) == [False, True], ic)
c = Client("DRUID").boot(["Mark of the Wild"]); c.tick(0.2)
t.check("Druid: missing Mark of the Wild shows", len(c.icons(BUFF)) == 1 and c.icons(BUFF)[0]["border"] == RED_MISSING)
c = Client("WARLOCK").boot(["Demon Armor"]); c.tick(0.2)
t.check("Warlock: missing armor shows", len(c.icons(BUFF)) == 1)

c = Client("WARRIOR").boot(["Battle Shout"]); c.set_equip(main="INVTYPE_2HWEAPON"); c.exe("W.stance = 2"); c.set_buffs([("Battle Shout", 100, 120)]); c.tick(1.1)
ic = c.icons(BUFF)
t.check("Warrior: stance icon first (neutral), then Battle Shout", len(ic) == 2 and ic[0]["tex"] == 5002 and ic[0]["border"] == BLACK, ic)
c.slash("ignore Stance"); c.tick(1.1)
t.check("/scdt ignore Stance hides the stance icon", [i["tex"] for i in c.icons(BUFF)] == [7001])
c.exe("W.stance = 0"); c.slash("unignore Stance"); c.tick(1.1)
t.check("no stance (form 0): no stance icon", [i["tex"] for i in c.icons(BUFF)] == [7001])

# ---------------------------------------------------------------- Shaman totems
SH = ["Rockbiter Weapon", "Flametongue Weapon", "Lightning Shield", "Searing Totem"]
def shaman(**kw):
    c = Client("SHAMAN", **kw).boot(SH); c.set_equip(main="INVTYPE_2HWEAPON"); return c
c = shaman(); c.set_enchant("main", 1800000); c.set_buffs([("Lightning Shield", 600, 600)])
c.set_totem(1, "Searing Totem", 30, 60); c.set_totem(3, "Mana Spring Totem", 8, 60); c.tick(1.1)
ic = c.icons(BUFF)
t.check("Shaman: imbue, totems (slot order), and Lightning Shield are drawn", len(ic) == 4, ic)
tot = {i["tex"]: i for i in ic}
t.check("totem icons show a timer; a totem under 10 s gets the red warn border", tot[6001]["text"] != "" and tot[6001]["border"] == BLACK and tot[6003]["border"] == RED_WARN, tot)
t.check("totem order follows slot order (1 before 3)", [i["tex"] for i in ic if i["tex"] in (6001, 6003)] == [6001, 6003])
c.clear_totem(1); c.tick(1.1)
t.check("a totem that is gone disappears", 6001 not in [i["tex"] for i in c.icons(BUFF)])
c.slash("ignore Mana Spring Totem"); c.tick(1.1)
t.check("an ignored totem is hidden", 6003 not in [i["tex"] for i in c.icons(BUFF)])

# imbues
c = shaman(); c.tick(1.1)
ic = c.icons(BUFF)
t.check("Shaman with imbue spells known and no imbue: IMBUE reminder (dimmed, red border)", any(i["desat"] and i["border"] == RED_MISSING for i in ic) and any(i["text"] == "" for i in ic), ic)
c.set_enchant("main", 1800000); c.tick(1.1)
imb = [i for i in c.icons(BUFF) if i["tex"] not in (7001,)]
t.check("imbue applied (API): icon with a 30m countdown", any(i["text"] in ("30m", "31m") and i["desat"] is False for i in imb), imb)
c.set_enchant("main", 90000); c.tick(1.1)
t.check("imbue under 2 minutes: red warn border", any(i["border"] == RED_WARN for i in c.icons(BUFF)), c.icons(BUFF))
c.set_enchant("main", None); c.tick(1.1)
t.check("imbue falls off: reminder is back", any(i["desat"] and i["border"] == RED_MISSING for i in c.icons(BUFF)))

c = shaman(); c.set_buffs([("Flametongue Weapon", 1500, 1800)]); c.tick(1.1)
t.check("imbue seen as a normal aura (no weapon-enchant data): counts as applied", c.errors() == [] and any(i["desat"] is False and i["text"] != "" for i in c.icons(BUFF)), c.icons(BUFF))

c = Client("SHAMAN").boot(["Lightning Shield"]); c.set_equip(main="INVTYPE_2HWEAPON"); c.tick(1.1)
t.check("no imbue spells known and no enchant: no imbue reminder", [i for i in c.icons(BUFF)] == [i for i in c.icons(BUFF) if i["tex"] == c.spell_icon("Lightning Shield")])

# cast fallback when the API reports nothing (shim off)
c = Client("SHAMAN", shims=()).boot(SH); c.set_equip(main="INVTYPE_2HWEAPON")
c.add_spell("Windfury Weapon", desc="Imbue your weapon for 30 min."); c.fire("SPELLS_CHANGED"); c.tick(1.1)
c.cast("Windfury Weapon"); c.tick(1.1)
t.check("no GetWeaponEnchantInfo: casting an imbue shows it with the tooltip duration", any(i["desat"] is False and i["text"] != "" for i in c.icons(BUFF)) and c.errors() == [], c.icons(BUFF))
c.exe("W.now = W.now + 1801"); c.tick(1.1)
t.check("... and it lapses back to the reminder after that duration", any(i["desat"] and i["border"] == RED_MISSING for i in c.icons(BUFF)))

# off-hand imbue: needs OffhandHasWeapon. Forever has only C_PaperDollInfo.OffhandHasWeapon (no global)
c = shaman(); c.set_equip(main="INVTYPE_WEAPON", off="INVTYPE_WEAPON"); c.set_enchant("main", 1800000); c.set_enchant("off", 1800000); c.tick(1.1)
imb = [i for i in c.icons(BUFF) if i["text"] in ("30m", "31m")]
t.check("dual-wield Shaman with both weapons enchanted shows TWO imbue icons (one per hand)", len(imb) == 2, c.icons(BUFF))
c = shaman(); c.set_equip(main="INVTYPE_WEAPON", off="INVTYPE_WEAPON"); c.exe("OffhandHasWeapon = function() return C_PaperDollInfo.OffhandHasWeapon() end")
c.set_enchant("main", 1800000); c.set_enchant("off", 1800000); c.tick(1.1)
t.check("a client that only has the old global OffhandHasWeapon still gets both imbue slots", len([i for i in c.icons(BUFF) if i["text"] in ("30m", "31m")]) == 2, c.icons(BUFF))
c = shaman(); c.set_equip(main="INVTYPE_2HWEAPON"); c.set_enchant("main", 1800000); c.tick(1.1)
t.check("two-hander: only one imbue icon (no off-hand slot)", len([i for i in c.icons(BUFF) if i["text"] in ("30m", "31m")]) == 1, c.icons(BUFF))

# ---------------------------------------------------------------- Rogue poisons
c = Client("ROGUE").boot(["Poisons", "Evasion"]); c.set_equip(main="INVTYPE_WEAPON", off="INVTYPE_WEAPON"); c.tick(1.1)
ic = c.icons(BUFF)
t.check("Rogue (dual-wield): one POISON reminder per hand with the poison icon when no poison is applied", len(ic) == 2 and all(i["tex"] == "Interface\\Icons\\Ability_Poisons" and i["border"] == RED_MISSING for i in ic), ic)
c.set_enchant("main", 3600000); c.tick(1.1)
ic = c.icons(BUFF)
t.check("Rogue: poison on the main hand -> 1h countdown there, off hand still shows the reminder", len(ic) == 2 and ic[0]["desat"] is False and ic[0]["text"] in ("1h", "60m") and ic[1]["desat"] is True and ic[1]["border"] == RED_MISSING, ic)
c = Client("ROGUE").boot(["Evasion"]); c.set_equip(main="INVTYPE_WEAPON", off="INVTYPE_WEAPON"); c.tick(1.1)
t.check("Rogue without the Poisons spell: no reminder", c.icons(BUFF) == [])

# ---------------------------------------------------------------- pets
for cls, spell in [("HUNTER", "Call Pet"), ("WARLOCK", "Summon Imp")]:
    c = Client(cls).boot([spell]); c.set_equip(main="INVTYPE_2HWEAPON", ranged="INVTYPE_RANGEDRIGHT"); c.exe("W.pet = false"); c.tick(1.1)
    ic = [i for i in c.icons(BUFF) if i["tex"] == c.spell_icon(spell)]
    t.check(f"{cls}: pet missing -> dimmed {spell} icon with red border", len(ic) == 1 and ic[0]["desat"] and ic[0]["border"] == RED_MISSING, c.icons(BUFF))
    c.exe("W.pet = true"); c.tick(1.1)
    t.check(f"{cls}: pet present -> no reminder", [i for i in c.icons(BUFF) if i["tex"] == c.spell_icon(spell)] == [])
    c.exe("W.pet = false"); c.slash(f"ignore {spell}"); c.tick(1.1)
    t.check(f"{cls}: ignoring {spell} turns the reminder off", [i for i in c.icons(BUFF) if i["tex"] == c.spell_icon(spell)] == [])
c = Client("HUNTER").boot(["Arcane Shot"]); c.set_equip(main="INVTYPE_2HWEAPON", ranged="INVTYPE_RANGEDRIGHT"); c.exe("W.pet = false"); c.tick(1.1)
t.check("Hunter without Call Pet: no pet reminder", c.icons(BUFF) == [])
c = Client("WARLOCK").boot(["Summon Imp", "Summon Voidwalker"]); c.exe("W.pet = false"); c.cast("Summon Voidwalker"); c.tick(1.1)
t.check("casting a pet spell remembers its icon for the reminder", c.db()["buffIcons"]["pet"] == c.spell_icon("Summon Voidwalker") and c.icons(BUFF)[0]["tex"] == c.spell_icon("Summon Voidwalker"), c.db()["buffIcons"])

t.finish()
