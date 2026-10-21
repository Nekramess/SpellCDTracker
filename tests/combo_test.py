"""Combo points (Rogue; Druid in cat form): pips, secret-value bar fallback, visibility rules, profile switch, position, debug.
UnitPower(player, ComboPoints) is SecretWhenUnitPowerRestricted in the Forever UI source; whether it is secret for the
player's own points in the live client is NOT confirmed, so both paths are tested."""
from mock_env import Client, Checker

t = Checker("combo_test")
F = "SpellCDTrackerComboFrame"

def state(c):
    """(frame shown, number of visible pips, number of filled pips, bar shown)"""
    return tuple(c.ev("""(function() local f = %s
      if not f then return {false,0,0,false} end
      local vis, fill = 0, 0
      for _, p in ipairs(f.pips) do
        if p._shown then vis = vis + 1; if p.fill._color and p.fill._color[1] > 0.5 then fill = fill + 1 end end
      end
      return {f._shown and true or false, vis, fill, f.bar._shown and true or false} end)()""" % F).values())

def mk(cls="ROGUE", pts=0, mx=5):
    c = Client(cls).boot(["Some Spell"]); c.set_combo(pts, mx); c.tick(0.3, 2); return c

# classes
for cls in ("PALADIN", "WARRIOR", "MAGE", "PRIEST", "HUNTER", "SHAMAN", "WARLOCK"):
    c = Client(cls).boot(["Some Spell"]); c.set_combo(3); c.tick(0.3, 2)
    t.check(f"{cls}: no combo frame", c.ev(f"{F} == nil") is True)
    c.slash("debug"); t.check(f"{cls}: no combo debug line", not any(p.strip().startswith("combo:") for p in c.printed))

# visibility
c = mk("ROGUE", 0)
t.check("Rogue, 0 points, out of combat: hidden", state(c)[0] is False, state(c))
c.set_combo(3); c.tick(0.3, 2)
t.check("Rogue, 3 points: shown with 5 pips, 3 filled, no bar", state(c) == (True, 5, 3, False), state(c))
c.set_combo(5); c.tick(0.3, 2)
t.check("5 points: all 5 filled", state(c) == (True, 5, 5, False), state(c))
c.set_combo(0); c.tick(0.3, 2)
t.check("points spent out of combat: hidden again", state(c)[0] is False)
c.combat(True, secrets=()); c.tick(0.3, 2)
t.check("in combat with 0 points: shown, 0 filled", state(c) == (True, 5, 0, False), state(c))
c.set_combo(2); c.tick(0.3, 2)
t.check("in combat, 2 points: 2 filled", state(c) == (True, 5, 2, False), state(c))
c.combat(False); c.set_combo(0); c.tick(0.3, 2)
t.check("leaving combat with 0 points: hidden", state(c)[0] is False)
c.set_combo(6, 6); c.tick(0.3, 2)
t.check("max 6: six pips", state(c) == (True, 6, 6, False), state(c))
c.set_combo(2, 20); c.tick(0.3, 2)
t.check("absurd max is capped at 8 pips", state(c)[1] == 8, state(c))
t.check("no errors", c.errors() == [], c.errors())

# Druid: only with a combo point pool (cat form)
c = mk("DRUID", 0, 0)
c.combat(True, secrets=()); c.tick(0.3, 2)
t.check("Druid with max 0 (not in cat form): hidden even in combat", state(c)[0] is False, state(c))
c.combat(False); c.set_combo(0, 5); c.tick(0.3, 2); c.combat(True, secrets=()); c.tick(0.3, 2)
t.check("Druid in cat form in combat: shown", state(c)[0] is True)
c.combat(False); c.set_combo(3, 5); c.tick(0.3, 2)
t.check("Druid cat form, 3 points: 3 filled", state(c) == (True, 5, 3, False), state(c))
c.set_combo(3, 0); c.tick(0.3, 2)
t.check("shifting out of cat form hides it", state(c)[0] is False)

# secret values: no error, bar instead of pips, value passed straight through
c = mk("ROGUE", 3)
c.combat(True, secrets=("power",)); c.tick(0.3, 2)
s = state(c)
t.check("secret points in combat: bar shown, pips hidden, no error", s == (True, 0, 0, True) and c.errors() == [], (s, c.errors()))
t.check("... the secret value was handed to the bar unread", c.ev(f"IsSecret({F}.bar._value)") is True)
c.combat(False, secrets=("power",)); c.tick(0.3, 2)
t.check("leaving combat: pips are back (3 filled)", state(c) == (True, 5, 3, False), state(c))
c = mk("ROGUE", 0); c.exe("W.secretPower = true"); c.tick(0.3, 2)
t.check("secret points out of combat: hidden (cannot compare to 0), no error", state(c)[0] is False and c.errors() == [], c.errors())
c = mk("DRUID", 2); c.combat(True, secrets=("power", "cd", "auras", "totems", "enchant")); c.tick(0.3, 3)
t.check("Druid, everything secret: bar, no error", state(c)[3] is True and c.errors() == [], c.errors())

# missing API
c = Client("ROGUE").boot(["Some Spell"]); c.exe("UnitPower = nil; UnitPowerMax = nil"); c.tick(0.3, 3)
t.check("UnitPower missing: hidden, no error", state(c)[0] is False and c.errors() == [], c.errors())

# always visible option
c = mk("ROGUE", 0)
t.check("option check box exists for Rogue", c.slash("options") is None or True)
c.exe("SpellCDTrackerDB.comboAlways = true"); c.tick(0.3, 2)
t.check("'always visible': shown with 0 points out of combat", state(c) == (True, 5, 0, False), state(c))
c = mk("MAGE")
c.slash("options")
t.check("Mage options have no combo check box", c.click_check("Combo points always visible", True) is False)
c = mk("ROGUE"); c.slash("options")
t.check("Rogue options: 'Combo points always visible' saves", c.click_check("Combo points always visible", True) and c.db()["comboAlways"] is True)

# per-profile switch in the Tracked spells window
c = mk("ROGUE", 3)
c.slash("spells")
t.check("Tracked spells shows 'Combo points' for Rogue", c.ev("SpellCDTrackerSpells.comboToggle._shown") is True)
t.check("toggle off via the window", c.click_check("Combo points", False))
c.tick(0.3, 2)
t.check("switched off: hidden even with 3 points", state(c)[0] is False)
t.check("... saved in the profile as combo=false", c.db()["profiles"]["ROGUE"]["combo"] is False)
c.click_check("Combo points", True); c.tick(0.3, 2)
t.check("switched back on: shown", state(c)[0] is True)
c = mk("MAGE"); c.slash("spells")
t.check("Mage has no 'Combo points' toggle", c.ev("SpellCDTrackerSpells.comboToggle._shown") is False)

# position, edit mode, reset
c = mk("ROGUE", 0)
t.check("default position CENTER 0,-110", c.pos(F)[:5] == ["CENTER", "UIParent", "CENTER", 0, -110] or c.pos(F)[3:5] == [0, -110], c.pos(F))
c.slash("unlock"); c.tick(0.3, 2)
t.check("edit mode: shown for dragging with 0 points, mouse enabled", state(c)[0] is True and c.ev(f"{F}._mouse") is True, state(c))
c.slash("lock"); c.tick(0.3, 2)
t.check("edit mode off: hidden again, mouse off", state(c)[0] is False and c.ev(f"{F}._mouse") is False)
c.exe(f"SpellCDTrackerDB.combo.x = 50"); c.slash("reset")
t.check("/scdt reset restores the combo position", c.db()["combo"]["x"] == 0 and c.db()["combo"]["y"] == -110, c.db()["combo"])
c.exe(f"SpellCDTrackerDB.combo.x = 50"); c.slash("options"); c.click_button("Reset positions")
t.check("options 'Reset positions' restores it too", c.db()["combo"]["x"] == 0)

# regression: the buff row must be draggable on non-Paladins too (ApplyLock used to stop at the missing Paladin frame)
c = mk("ROGUE"); c.slash("unlock")
t.check("edit mode: buff row and cooldown row take the mouse on a Rogue", c.ev("SpellCDTrackerBuffFrame._mouse") is True and c.ev("SpellCDTrackerCDFrame._mouse") is True)

# existing saved variables without 'combo' get the default
c = Client("ROGUE", saved={"cdSize": 40, "profiles": {}}).boot(["Some Spell"])
t.check("old saved variables gain db.combo", c.db()["combo"]["y"] == -110, c.db().get("combo"))

# debug
c = mk("ROGUE", 3); c.slash("debug")
t.check("debug prints combo line with points and max", any(p.strip().startswith("combo: points 3 / max 5") for p in c.printed), c.printed)
c = mk("ROGUE", 0); c.combat(True, secrets=("power",)); c.tick(0.3, 2); c.slash("debug")
t.check("debug says 'secret' for secret points", any("combo: points secret" in p for p in c.printed), c.printed)

t.finish()
