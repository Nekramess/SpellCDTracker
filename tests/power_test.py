"""Resource bar (Rogue energy, Warrior rage, Druid by form) and cost-aware ready icons (energy/rage abilities show their cost and
colour up when castable). UnitPower may be secret in combat in the live client (unconfirmed): the bar then gets the value unread;
affordability comes from C_Spell.IsSpellUsable, which the Forever docs do not mark secret."""
from mock_env import Client, Checker

t = Checker("power_test")
P = "SpellCDTrackerPowerFrame"
CD = "SpellCDTrackerCDFrame"

def bar(c):
    r = c.ev("""(function() local f = %s
      if not f then return {false, "", 0, 0} end
      return { f._shown and true or false, f.text._text or "", f.bar._value or -1, f.bar._max or -1 } end)()""" % P)
    return tuple(r.values())

def mk(cls="ROGUE", cur=100, mx=100, ptype=3):
    c = Client(cls).boot(["Sinister Strike", "Eviscerate"]); c.set_power(cur, mx, ptype); c.tick(0.3, 2); return c

for cls in ("PALADIN", "MAGE", "HUNTER", "PRIEST", "SHAMAN", "WARLOCK"):
    c = Client(cls).boot(["Some Spell"]); c.tick(0.3, 2)
    t.check(f"{cls}: no resource frame", c.ev(f"{P} == nil") is True)
    c.slash("debug"); t.check(f"{cls}: no power debug line", not any(p.strip().startswith("power:") for p in c.printed))

# visibility and values
c = mk("ROGUE", 80)
t.check("Rogue out of combat: bar hidden", bar(c)[0] is False)
c.combat(True, secrets=()); c.tick(0.3, 2)
t.check("in combat: shown with 80 / 100", bar(c) == (True, "80", 80, 100), bar(c))
c.set_power(35); c.tick(0.3, 2)
t.check("energy spent: 35", bar(c)[1:3] == ("35", 35), bar(c))
c.combat(False); c.tick(0.3, 2)
t.check("leaving combat hides it", bar(c)[0] is False)
c = mk("WARRIOR", 20, 100, 1); c.combat(True, secrets=()); c.tick(0.3, 2)
t.check("Warrior rage: shown with 20", bar(c) == (True, "20", 20, 100), bar(c))
c = mk("DRUID", 150, 300, 0); c.combat(True, secrets=()); c.tick(0.3, 2)
t.check("Druid in caster form: mana 150 / 300", bar(c) == (True, "150", 150, 300), bar(c))
t.check("no errors", c.errors() == [], c.errors())

# secret values
c = mk("ROGUE", 80); c.combat(True, secrets=("power",)); c.tick(0.3, 3)
t.check("secret energy: bar shown, no error", bar(c)[0] is True and c.errors() == [], c.errors())
t.check("... the secret was handed to the bar unread", c.ev(f"IsSecret({P}.bar._value)") is True)
c = Client("ROGUE").boot(["x"]); c.exe("UnitPower = nil; UnitPowerMax = nil; UnitPowerType = nil"); c.combat(True, secrets=()); c.tick(0.3, 3)
t.check("APIs missing: hidden, no error", bar(c)[0] is False and c.errors() == [], c.errors())

# profile switch, edit mode, reset, debug
c = mk("ROGUE", 80); c.combat(True, secrets=()); c.slash("spells")
t.check("Tracked spells shows 'Resource bar' for Rogue", c.ev("SpellCDTrackerSpells.powerToggle._shown") is True)
t.check("toggle off", c.click_check("Resource bar", False)); c.tick(0.3, 2)
t.check("switched off: hidden in combat; saved power=false", bar(c)[0] is False and c.db()["profiles"]["ROGUE"]["power"] is False)
c = mk("PALADIN"); c.slash("spells")
t.check("Paladin has no 'Resource bar' toggle", c.ev("SpellCDTrackerSpells.powerToggle._shown") is False)
c = mk("ROGUE")
t.check("default position CENTER 0,-135", c.pos(P)[3:5] == [0, -135], c.pos(P))
c.slash("unlock"); c.tick(0.3, 2)
t.check("edit mode: shown and draggable out of combat", bar(c)[0] is True and c.ev(f"{P}._mouse") is True)
c.exe("SpellCDTrackerDB.power.x = 70"); c.slash("reset")
t.check("/scdt reset restores it", c.db()["power"]["x"] == 0)
c = mk("ROGUE", 55); c.slash("debug")
t.check("debug prints power line", any(p.strip().startswith("power: type 3 | 55 / 100") for p in c.printed), c.printed)

# cost-aware ready icons
def ready_setup(cls="ROGUE", cur=100):
    c = Client(cls).boot(["Sinister Strike", "Eviscerate", "Sprint"])
    c.set_cost("Sinister Strike", 45); c.set_cost("Eviscerate", 35, need_combo=1)
    c.set_power(cur); c.slash("spells")
    c.click_row("Sinister Strike", "pin", True); c.click_row("Eviscerate", "pin", True)
    c.combat(True, secrets=()); c.tick(0.3, 3)
    return c

def by_tex(c, name):
    tex = c.spell_icon(name)
    for i in c.icons(CD):
        if i["tex"] == tex: return i

c = ready_setup(cur=100)
ss, ev = by_tex(c, "Sinister Strike"), by_tex(c, "Eviscerate")
t.check("pinned Sinister Strike with 100 energy: colour, full alpha, cost 45", ss and not ss["desat"] and ss["alpha"] == 1 and ss["text"] == "45", ss)
t.check("Eviscerate without a combo point: stays gray (cost shown)", ev and ev["desat"] and ev["alpha"] == 0.55 and ev["text"] == "35", ev)
c.set_combo(2); c.tick(0.3, 2)
t.check("with combo points Eviscerate lights up", not by_tex(c, "Eviscerate")["desat"])
c.set_power(30); c.tick(0.3, 2)
ss, ev = by_tex(c, "Sinister Strike"), by_tex(c, "Eviscerate")
t.check("30 energy: Sinister Strike gray with a red cost", ss["desat"] and ss["tcolor"][0] == 1 and ss["tcolor"][1] < 0.5 and ss["text"] == "45", ss)
t.check("30 energy: Eviscerate (35) gray too", ev["desat"] and ev["tcolor"][1] < 0.5, ev)
c.set_power(40); c.tick(0.3, 2)
t.check("40 energy: Eviscerate (35) castable again, Sinister Strike (45) not", not by_tex(c, "Eviscerate")["desat"] and by_tex(c, "Sinister Strike")["desat"])

# secret energy: affordability still works (IsSpellUsable), no error
c.set_power(100); c.combat(True, secrets=("power",)); c.tick(0.3, 3)
t.check("secret UnitPower: icons still coloured from IsSpellUsable, no error", not by_tex(c, "Sinister Strike")["desat"] and c.errors() == [], c.errors())
# no API: falls back to plain gray, no error
c = ready_setup(); c.exe("C_Spell.IsSpellUsable = nil"); c.tick(0.3, 3)
t.check("IsSpellUsable missing: gray with cost, no error", by_tex(c, "Sinister Strike")["desat"] and c.errors() == [], c.errors())
c = ready_setup(); c.exe("C_Spell.GetSpellPowerCost = nil"); c.tick(0.3, 3)
t.check("GetSpellPowerCost missing: plain gray ready icon, no cost text", by_tex(c, "Sinister Strike")["desat"] and by_tex(c, "Sinister Strike")["text"] == "" and c.errors() == [], c.errors())
# mana abilities keep the old gray look
c = Client("PALADIN").boot(["Judgement"]); c.set_cost("Judgement", 20, ptype=0); c.set_power(500, 500, 0)
c.combat(True, secrets=()); c.tick(0.3, 3)
j = by_tex(c, "Judgement")
t.check("Paladin Judgement (mana cost): still gray and no cost text", j and j["desat"] and j["alpha"] == 0.55 and j["text"] == "", j)

t.finish()
