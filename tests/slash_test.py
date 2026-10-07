"""/scdt and its subcommands, driven through SlashCmdList like the chat box does."""
from mock_env import Client, Checker

t = Checker("slash_test")

def fresh(cls="PALADIN", spells=("Judgement", "Consecration", "Seal of Righteousness")):
    return Client(cls).boot(list(spells))

# --- options window
c = fresh()
c.slash("")
t.check("/scdt opens the options window", c.ev("SpellCDTrackerOptions._shown") is True and c.errors() == [], c.errors())
c.slash("")
t.check("/scdt again closes it (toggle)", c.ev("SpellCDTrackerOptions._shown") is False)
c.slash("options"); t.check("/scdt options opens it", c.ev("SpellCDTrackerOptions._shown") is True)
c.slash("config"); t.check("/scdt config closes it", c.ev("SpellCDTrackerOptions._shown") is False)
t.check("options window is registered for Escape (UISpecialFrames)", c.ev("(function() for _, n in ipairs(UISpecialFrames) do if n == 'SpellCDTrackerOptions' then return true end end end)()") is True)

# --- edit mode
c = fresh()
t.check("edit mode starts OFF: frames click-through", c.ev("SpellCDTrackerCDFrame._mouse") is False)
c.slash("edit")
t.check("/scdt edit turns edit mode ON (mouse on, green box shown)", c.ev("SpellCDTrackerCDFrame._mouse") is True and c.ev("SpellCDTrackerCDFrame.bg._shown") is True)
t.check("edit mode applies to the Paladin and buff frames too", c.ev("SpellCDTrackerPalaFrame._mouse and SpellCDTrackerBuffFrame._mouse") is True)
t.check("edit prints ON message", any("edit mode ON" in p for p in c.new_output()))
c.slash("EDIT")
t.check("/scdt EDIT (upper case) toggles back OFF", c.ev("SpellCDTrackerCDFrame._mouse") is False and any("edit mode OFF" in p for p in c.new_output()))
c.slash("unlock"); t.check("/scdt unlock -> ON", c.ev("SpellCDTrackerCDFrame._mouse") is True)
c.slash("lock"); t.check("/scdt lock -> OFF", c.ev("SpellCDTrackerCDFrame._mouse") is False)
c.slash("unlock")
t.check("edit mode is never saved", "editMode" not in c.db() and not any("edit" in str(k).lower() for k in c.db()))

# --- swing timer toggle and its effect on Forever's bars
c = fresh()
c.tick(0.2, 2)
t.check("swing timer bars hidden (alpha 0) out of combat by default", c.ev("SwingTimerMainHandFrame._alpha") == 0)
c.combat(True); c.tick(0.2, 2)
t.check("swing timer bars visible in combat", c.ev("SwingTimerMainHandFrame._alpha") == 1)
c.combat(False); c.tick(0.2, 2)
t.check("hidden again after combat", c.ev("SwingTimerRangedFrame._alpha") == 0)
c.slash("swing"); c.tick(0.2, 2)
t.check("/scdt swing turns the option off and gives the bars back (alpha 1)", c.db()["swingCombatOnly"] is False and c.ev("SwingTimerOffHandFrame._alpha") == 1)
t.check("swing prints the new state", any("always visible" in p for p in c.new_output()))
c.slash("swing")
t.check("/scdt swing again -> on", c.db()["swingCombatOnly"] is True)

# --- size
c = fresh()
c.slash("size 60"); t.check("/scdt size 60 sets both icon sizes", c.db()["cdSize"] == 60 and c.db()["palaSize"] == 60)
c.tick(0.2)
t.check("size change is applied to drawn icons", c.ev("SpellCDTrackerCDFrame._h") == 60)
c.slash("size 5"); t.check("size clamps to 16 minimum", c.db()["cdSize"] == 16)
c.slash("size 500"); t.check("size clamps to 96 maximum", c.db()["cdSize"] == 96)
c.slash("size abc")
t.check("size with a non-number prints usage and changes nothing", c.db()["cdSize"] == 96 and any("/scdt (options)" in p for p in c.new_output()))

# --- ignore / unignore
c = fresh()
c.cooldown("Consecration", 8, 8); c.tick(0.2)
t.check("setup: Consecration on cooldown shows an icon", len(c.icons()) == 1)
c.slash("ignore Consecration")
t.check("/scdt ignore stores it lower-case in the active profile", c.db()["profiles"]["PALADIN"]["ignore"].get("consecration") is True)
c.tick(0.2)
t.check("ignored spell no longer shows", c.icons() == [])
c.slash("unignore CONSECRATION"); c.tick(0.2)
t.check("/scdt unignore (any case) tracks it again", len(c.icons()) == 1 and "consecration" not in c.db()["profiles"]["PALADIN"]["ignore"])
c.slash("ignore")
t.check("/scdt ignore with no spell prints usage", any("/scdt (options)" in p for p in c.new_output()))

# --- spells window
c = fresh()
c.slash("spells"); t.check("/scdt spells opens Tracked spells", c.ev("SpellCDTrackerSpells._shown") is True and c.errors() == [], c.errors())
c.slash("track"); t.check("/scdt track closes it", c.ev("SpellCDTrackerSpells._shown") is False)

# --- reset
c = fresh()
c.exe("SpellCDTrackerDB.cd.x = 500; SpellCDTrackerDB.pala.y = 9; SpellCDTrackerDB.buff.x = 77; SpellCDTrackerDB.pbuff.x = 78")
c.slash("reset")
d = c.db()
t.check("/scdt reset restores default positions", d["cd"] == {"point": "CENTER", "relPoint": "CENTER", "x": 0, "y": -150} and d["pala"]["y"] == -215
        and d["buff"]["x"] == 0 and d["pbuff"] == {"point": "CENTER", "relPoint": "CENTER", "x": 0, "y": -280}, d["cd"])
t.check("reset re-applies the frame position", c.ev("SpellCDTrackerCDFrame._pt[5]") == -150)
t.check("reset prints", any("positions reset" in p for p in c.new_output()))

# --- minimap subcommands (geometry is in minimap_test.py)
c = fresh()
c.slash("minimap off")
t.check("minimap off hides the button and saves it", c.ev("SpellCDTrackerMinimapButton._shown") is False and c.db()["minimapHide"] is True)
c.slash("minimap on")
t.check("minimap on shows it", c.ev("SpellCDTrackerMinimapButton._shown") is True and c.db()["minimapHide"] is False)
c.slash("minimap hide"); t.check("minimap hide alias", c.db()["minimapHide"] is True)
c.slash("minimap show"); t.check("minimap show alias", c.db()["minimapHide"] is False)
c.slash("minimap square"); t.check("minimap square saves shape", c.db()["minimapShape"] == "square")
c.slash("minimap round"); t.check("minimap round saves shape", c.db()["minimapShape"] == "round")
c.slash("minimap auto"); t.check("minimap auto clears the override", "minimapShape" not in c.db())
c.slash("Minimap SQUARE"); t.check("subcommand and argument are case-insensitive", c.db()["minimapShape"] == "square")
t.check("minimap message reports hidden/shown and shape", any("minimap button shown, shape square" in p for p in c.new_output()))
before = dict(c.db())
c.slash("minimap banana")
t.check("minimap with a bad argument prints usage and changes nothing",
        any("on | off | square | round | auto" in p for p in c.new_output()) and c.db()["minimapShape"] == "square" and c.db()["minimapHide"] == before["minimapHide"])
c.slash("minimap")
t.check("bare /scdt minimap prints usage", any("on | off | square | round | auto" in p for p in c.new_output()))

# --- unknown command and debug
c = fresh()
c.slash("frobnicate")
out = " ".join(c.new_output())
t.check("unknown subcommand prints the full usage", all(w in out for w in ["spells", "edit", "swing", "size", "ignore", "unignore", "minimap", "reset", "debug"]), out)
c.slash("debug Judgement")
t.check("/scdt debug <spell> reports that spell", any("Judgement: id" in p for p in c.new_output()))
c.slash("debug Nonexistent")
t.check("/scdt debug on an unknown spell says not found", any("Nonexistent: not found in spell list" in p for p in c.new_output()))

# --- every subcommand on every class: no error
for cls in ["WARRIOR", "PALADIN", "HUNTER", "ROGUE", "PRIEST", "SHAMAN", "MAGE", "WARLOCK", "DRUID"]:
    c = fresh(cls)
    for m in ["", "", "edit", "edit", "swing", "swing", "size 30", "spells", "spells", "reset", "minimap off", "minimap on", "minimap square", "minimap auto", "debug", "frobnicate"]:
        c.slash(m); c.tick(0.2)
    t.check(f"{cls}: all subcommands run without an error", c.errors() == [], c.errors())

t.finish()
