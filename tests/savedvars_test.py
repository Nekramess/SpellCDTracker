"""Saved variables (SpellCDTrackerDB): defaults, migration, round trip through a simulated /reload, nothing odd stored."""
from mock_env import Client, Checker

t = Checker("savedvars_test")
SPELLS = ["Judgement", "Holy Strike", "Consecration", "Seal of Righteousness"]

DEFAULTS = {"cdSize": 40, "palaSize": 40, "textScale": 100, "minimapAngle": 200, "minimapHide": False, "readyAlways": False,
            "swingCombatOnly": True, "cd": {"point": "CENTER", "relPoint": "CENTER", "x": 0, "y": -150},
            "pala": {"point": "CENTER", "relPoint": "CENTER", "x": 0, "y": -215},
            "buff": {"point": "CENTER", "relPoint": "CENTER", "x": 0, "y": -215}, "pbuff": {"point": "CENTER", "relPoint": "CENTER", "x": 0, "y": -280}}

# ---------------------------------------------------------------- first run
c = Client("PALADIN").boot(SPELLS)
d = c.db()
for k, v in DEFAULTS.items():
    t.check(f"first run default: {k}", d.get(k) == v, d.get(k))
for k in ["ignore", "profiles", "spellCache", "lastSpec", "buffIcons", "durations"]:
    t.check(f"first run default: {k} is a table", isinstance(d.get(k), (dict, list)), d.get(k))
t.check("first run: no minimapShape saved (auto)", "minimapShape" not in d)
t.check("default tables are independent copies (cd vs pala vs buff)", c.ev("SpellCDTrackerDB.cd ~= SpellCDTrackerDB.pala and SpellCDTrackerDB.pala ~= SpellCDTrackerDB.buff and SpellCDTrackerDB.buff ~= SpellCDTrackerDB.pbuff"))
t.check("frames are placed from the defaults", c.pos("SpellCDTrackerCDFrame")[3:5] == [0, -150] and c.pos("SpellCDTrackerPalaFrame")[3:5] == [0, -215], c.pos("SpellCDTrackerCDFrame"))
c2 = Client("PALADIN").boot(SPELLS)
c.exe("SpellCDTrackerDB.cd.x = 99")
t.check("a second login's defaults are not contaminated by edits (copies, not shared)", c2.db()["cd"]["x"] == 0)

# ---------------------------------------------------------------- partial / older databases
c = Client("PALADIN", saved={"cdSize": 60, "minimapHide": True, "swingCombatOnly": False, "readyAlways": True}).boot(SPELLS)
d = c.db()
t.check("saved values win over defaults, including false", d["cdSize"] == 60 and d["minimapHide"] is True and d["swingCombatOnly"] is False and d["readyAlways"] is True, d)
t.check("missing keys are filled with defaults", d["palaSize"] == 40 and d["textScale"] == 100 and d["cd"]["y"] == -150 and d["pbuff"]["y"] == -280)
t.check("swing option saved as false is respected: bars left alone (alpha 1)", c.ev("SwingTimerMainHandFrame._alpha") == 1)

c = Client("MAGE", saved={"size": 50}).boot(["Fireball"])
d = c.db()
t.check("v0.1 'size' migrates to both icon sizes and is removed", d["cdSize"] == 50 and d["palaSize"] == 50 and "size" not in d, d)
c = Client("MAGE", saved={"size": 50, "cdSize": 30}).boot(["Fireball"])
t.check("migration keeps an existing cdSize", c.db()["cdSize"] == 30 and c.db()["palaSize"] == 50)

# ---------------------------------------------------------------- round trip: change things, 'reload', compare behaviour
c = Client("PALADIN").boot(SPELLS)
c.slash("size 56"); c.slash("minimap square"); c.slash("minimap off"); c.slash("swing")
c.slash("ignore Consecration")
c.slash("spells"); c.click_row("Judgement", "pin", False)
c.slash("")                                    # options
c.click_check("Ready icons also out of combat", True)
c.exe("SpellCDTrackerDB.minimapAngle = 123.5")
c.exe("SpellCDTrackerCDFrame._pt = { 'TOP', UIParent, 'TOP', 11, -22 }; SpellCDTrackerCDFrame._scripts.OnDragStop(SpellCDTrackerCDFrame)")
c.exe("SpellCDTrackerBuffFrame._pt = { 'LEFT', UIParent, 'LEFT', 5, 6 }; SpellCDTrackerBuffFrame._scripts.OnDragStop(SpellCDTrackerBuffFrame)")
before = c.db()
t.check("drag stop saves the frame position", before["cd"] == {"point": "TOP", "relPoint": "TOP", "x": 11, "y": -22}, before["cd"])
t.check("buff frame drag saves into 'pbuff' for a Paladin (not 'buff')", before["pbuff"]["x"] == 5 and before["buff"]["x"] == 0, (before["buff"], before["pbuff"]))

c2 = Client("PALADIN", saved=before).boot(SPELLS)
t.check("round trip: saved table comes back identical after login (nothing added or lost by loading)", c2.db() == before, {k: (before.get(k), c2.db().get(k)) for k in set(before) | set(c2.db()) if before.get(k) != c2.db().get(k)})
t.check("round trip: sizes", c2.db()["cdSize"] == 56 and c2.db()["palaSize"] == 56)
t.check("round trip: minimap hidden, square, angle", c2.ev("SpellCDTrackerMinimapButton._shown") is False and c2.db()["minimapShape"] == "square" and c2.db()["minimapAngle"] == 123.5)
t.check("round trip: swing option off -> bars untouched", c2.ev("SwingTimerMainHandFrame._alpha") == 1)
t.check("round trip: cd frame placed at the saved position", c2.pos("SpellCDTrackerCDFrame")[0:5][0] == "TOP" and c2.pos("SpellCDTrackerCDFrame")[3:5] == [11, -22], c2.pos("SpellCDTrackerCDFrame"))
c2.cooldown("Consecration", 8, 8); c2.cooldown("Holy Strike", 8, 8); c2.tick(0.2)
t.check("round trip: ignore list still hides Consecration", c2.spell_icon("Consecration") not in c2.icon_ids() and c2.spell_icon("Holy Strike") in c2.icon_ids())
c2.clear_cooldown("Holy Strike"); c2.tick(0.2)
t.check("round trip: pins (Judgement unpinned) and readyAlways persist: out of combat only Holy Strike shows, ready and grayed",
        c2.icon_ids() == [c2.spell_icon("Holy Strike")] and c2.icons()[0]["desat"] is True, c2.icons())
t.check("round trip: size is applied to the icons", c2.icons()[0]["i"] == 1 and c2.ev("SpellCDTrackerCDFrame._h") == 56)

# second round trip is a fixed point
c3 = Client("PALADIN", saved=c2.db()).boot(SPELLS)
t.check("a second round trip changes nothing (idempotent load)", c3.db() == c2.db())

# ---------------------------------------------------------------- reset positions button and sliders
c = Client("PALADIN", saved={"cd": {"point": "TOP", "relPoint": "TOP", "x": 300, "y": 300}}).boot(SPELLS)
c.slash(""); c.click_button("Reset positions")
t.check("options 'Reset positions' restores defaults and re-applies them", c.db()["cd"]["x"] == 0 and c.db()["cd"]["y"] == -150 and c.pos("SpellCDTrackerCDFrame")[3:5] == [0, -150])
sl = c.ev("(function() local n = 0 for _, f in ipairs(CREATED) do if f._kind == 'Slider' then n = n + 1 end end return n end)()")
t.check("options window has three sliders for a Paladin (cd size, pala size, text size)", sl == 3, sl)
c.exe("""(function() local k = 0 for _, f in ipairs(CREATED) do if f._kind == 'Slider' then k = k + 1
   if k == 1 then f._scripts.OnValueChanged(f, 47) elseif k == 2 then f._scripts.OnValueChanged(f, 31) elseif k == 3 then f._scripts.OnValueChanged(f, 133) end end end end)()""")
t.check("sliders round to their step (47->48 step 2, 31->32 step 2, 133->130 step 10) and save", (c.db()["cdSize"], c.db()["palaSize"], c.db()["textScale"]) == (48, 32, 130), (c.db()["cdSize"], c.db()["palaSize"], c.db()["textScale"]))
c = Client("MAGE").boot(["Fireball"]); c.slash("")
sl = c.ev("(function() local n = 0 for _, f in ipairs(CREATED) do if f._kind == 'Slider' then n = n + 1 end end return n end)()")
t.check("non-Paladin options window has two sliders (no Paladin size)", sl == 2, sl)

# ---------------------------------------------------------------- Tracked spells tab memory
c = Client("PALADIN").boot(SPELLS); c.slash("spells")
c.exe("SpellCDTrackerSpells.classButtons.MAGE._scripts.OnClick()")
c.exe("SpellCDTrackerSpells.tabs[3]._scripts.OnClick()")
t.check("viewing spec tab 3 of another class is remembered per class", c.db()["lastSpec"]["MAGE"] == 3, c.db()["lastSpec"])
c.exe("SpellCDTrackerSpells.tabs[4]._scripts.OnClick()")
t.check("All specs tab is saved as 0", c.db()["lastSpec"]["MAGE"] == 0)
c2 = Client("PALADIN", saved=c.db()).boot(SPELLS); c2.slash("spells")
c2.exe("SpellCDTrackerSpells.classButtons.MAGE._scripts.OnClick()")
t.check("after reload the other class opens on All specs (0 means none): no 'uses All specs' note", c2.ev("SpellCDTrackerSpells.note._text") == "" and c2.errors() == [], c2.ev("SpellCDTrackerSpells.note._text"))
d = c.db(); d["lastSpec"]["MAGE"] = 2
c3 = Client("PALADIN", saved=d).boot(SPELLS); c3.slash("spells")
c3.exe("SpellCDTrackerSpells.classButtons.MAGE._scripts.OnClick()")
t.check("lastSpec 2 reopens that class on spec tab 2 (spec without its own profile: note shown)", "Uses your All specs settings" in c3.ev("SpellCDTrackerSpells.note._text"))

# ---------------------------------------------------------------- the DB only holds plain data, never secret values or runtime state
def plain(c):
    return c.ev("""(function()
      local seen, bad = {}, nil
      local function walk(v, path)
        if bad then return end
        local ty = type(v)
        if IsSecret(v) then bad = path .. ' (secret)' return end
        if ty == 'function' or ty == 'userdata' or ty == 'thread' then bad = path .. ' (' .. ty .. ')' return end
        if ty == 'table' then
          if seen[v] then return end
          seen[v] = true
          for k, x in pairs(v) do
            local kt = type(k)
            if kt ~= 'string' and kt ~= 'number' then bad = path .. ' (key ' .. kt .. ')' return end
            walk(x, path .. '.' .. tostring(k))
          end
        end
      end
      walk(SpellCDTrackerDB, 'db')
      return bad or 'ok' end)()""")

for cls in ["PALADIN", "SHAMAN", "MAGE", "HUNTER", "ROGUE", "WARRIOR", "PRIEST", "WARLOCK", "DRUID"]:
    c = Client(cls).boot(["Spell A", "Seal of Righteousness", "Rockbiter Weapon", "Call Pet", "Poisons"])
    c.set_buffs([("Seal of Righteousness", 20, 30)]); c.tick(0.5, 2)
    c.combat(True, secrets=("cd", "auras", "totems", "enchant", "equip", "unit")); c.cooldown("Spell A", 10, 10)
    c.fire("SPELL_UPDATE_COOLDOWN"); c.cast("Seal of Righteousness"); c.cast_secret(); c.tick(1.1, 3); c.slash("debug")
    c.combat(False); c.tick(0.5, 2)
    t.check(f"{cls}: after a combat with secret values the DB holds only plain data (no secret, function or userdata)", plain(c) == "ok", plain(c))

t.finish()
