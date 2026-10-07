"""Class/spec profile switching and pinned 'Show when ready' abilities.
Spec detection uses the global GetSpecialization. Forever's own UI only uses C_SpecializationInfo.GetSpecialization (the global is a
deprecated shim in the Standard game type only, behind CVar loadDeprecationFallbacks), so spec tests run in two worlds:
 - Forever-like: no global GetSpecialization (the default mock)
 - 'shim': global GetSpecialization present, to exercise the spec-profile code itself."""
from mock_env import Client, Checker

t = Checker("profile_test")
PALA = ["Judgement", "Holy Strike", "Consecration", "Holy Wrath", "Seal of Righteousness"]

def label(c): return c.ev("(function() local s = ''; return s end)()")

def debug_profile(c):
    c.slash("debug")
    for p in c.new_output():
        if p.strip().startswith("profile:"):
            return p.strip()

def shim(spec):
    c = Client("PALADIN", spec_api="global", spec=spec).boot(PALA)
    return c

# ---------------------------------------------------------------- Forever-like: class-wide only
c = Client("PALADIN").boot(PALA)
t.check("Forever-like: profile is class-wide ('PALADIN', 'Paladin - All specs')", "PALADIN (Paladin - All specs)" in debug_profile(c), debug_profile(c))
t.check("Forever-like: debug says the client has no GetSpecialization", "no GetSpecialization" in debug_profile(c))
t.check("class-wide profile exists with an ignore table", c.db()["profiles"]["PALADIN"] == {} or "ignore" in c.db()["profiles"]["PALADIN"])
t.check("no spec profile is created just by looking", set(c.db()["profiles"]) == {"PALADIN"}, c.db()["profiles"].keys())

# legacy global ignore list is copied into the first class profile
c = Client("PALADIN", saved={"ignore": {"consecration": True}}).boot(PALA)
t.check("legacy db.ignore is copied into the new class profile", c.db()["profiles"]["PALADIN"]["ignore"].get("consecration") is True, c.db()["profiles"])
c.cooldown("Consecration", 8, 8); c.cooldown("Holy Wrath", 8, 8); c.tick(0.2)
t.check("... and it is honoured (Consecration hidden, Holy Wrath shown)", c.icon_ids() == [c.spell_icon("Holy Wrath")], c.icons())

# a stale spec value never selects a spec profile that does not exist
for label_, spec in [("GetSpecialization returns 2 but no spec profile", 2)]:
    c = shim(spec)
    t.check(f"shim: {label_}: class-wide profile in use", "PALADIN (Paladin - All specs)" in debug_profile(c), debug_profile(c))

# ---------------------------------------------------------------- spec profiles (shim world)
def make_spec_profile(c, spec_tab_index, spell, state=False):
    c.slash("spells")
    c.exe(f"SpellCDTrackerSpells.tabs[{spec_tab_index}]._scripts.OnClick()")
    return c.click_row(spell, "check", state)

c = shim(2)
c.slash("spells")
t.check("shim: the window opens on the spec you are in (tab 2), uses All specs settings, says so",
        "Uses your All specs settings" in c.ev("SpellCDTrackerSpells.note._text") and c.ev("SpellCDTrackerSpells.resetBtn._shown") is False)
c.click_row("Consecration", "check", False)
d = c.db()["profiles"]
t.check("untracking a spell in the spec tab creates PALADIN:2 as a copy of the class-wide profile", "PALADIN:2" in d and d["PALADIN:2"]["ignore"].get("consecration") is True, list(d))
t.check("the class-wide profile is untouched", "consecration" not in d["PALADIN"]["ignore"], d["PALADIN"])
c.cooldown("Consecration", 8, 8); c.cooldown("Holy Wrath", 8, 8); c.tick(0.2)
t.check("spec 2 active: Consecration hidden, Holy Wrath shown", c.icon_ids() == [c.spell_icon("Holy Wrath")], c.icons())
t.check("the active profile label names the spec", "PALADIN:2 (Paladin - Protection)" in debug_profile(c), debug_profile(c))

c.set_spec(1); c.tick(0.2)
t.check("switch to spec 1 (no profile of its own): class-wide settings, Consecration is back",
        c.spell_icon("Consecration") in c.icon_ids() and "PALADIN (Paladin - All specs)" in debug_profile(c), c.icons())
c.set_spec(2); c.tick(0.2)
t.check("back to spec 2: its profile again, Consecration hidden", c.spell_icon("Consecration") not in c.icon_ids())
c.set_spec(3); c.tick(0.2)
t.check("spec 3: class-wide", c.spell_icon("Consecration") in c.icon_ids())

for label_, val in [("nil", None), ("0", 0), ("4 (out of range)", 4), ("a string", "'x'")]:
    c2 = shim(2)
    c2.slash("spells"); c2.click_row("Consecration", "check", False)
    c2.exe(f"SPEC = {val if val is not None else 'nil'}"); c2.cooldown("Consecration", 8, 8); c2.tick(0.2)
    t.check(f"GetSpecialization returns {label_}: class-wide profile, no error", c2.spell_icon("Consecration") in c2.icon_ids() and c2.errors() == [], c2.errors())
c2 = shim(2); c2.slash("spells"); c2.click_row("Consecration", "check", False)
c2.exe("function GetSpecialization() error('no talents') end"); c2.cooldown("Consecration", 8, 8); c2.tick(0.2)
t.check("GetSpecialization erroring: class-wide profile, no error", c2.spell_icon("Consecration") in c2.icon_ids() and c2.errors() == [], c2.errors())

# editing the class-wide settings does not leak into an existing spec profile, and the reset button drops a spec profile
c.set_spec(2); c.tick(0.2)
c.exe("SpellCDTrackerSpells.tabs[4]._scripts.OnClick()")     # All specs tab
c.click_row("Holy Wrath", "check", False)
d = c.db()["profiles"]
t.check("All specs tab edits the class-wide profile only", d["PALADIN"]["ignore"].get("holy wrath") is True and "holy wrath" not in d["PALADIN:2"]["ignore"], d)
c.exe("SpellCDTrackerSpells.tabs[2]._scripts.OnClick()")
t.check("the spec tab offers 'Use All specs settings'", c.ev("SpellCDTrackerSpells.resetBtn._shown") is True)
c.click_button("Use All specs settings"); c.tick(0.2)
t.check("pressing it deletes the spec profile", "PALADIN:2" not in c.db()["profiles"], list(c.db()["profiles"]))
c.cooldown("Holy Wrath", 8, 8); c.tick(0.2)
t.check("... Holy Wrath hidden by class-wide ignore", c.spell_icon("Holy Wrath") not in c.icon_ids(), c.icons())

# /scdt ignore edits whatever profile is active (class-wide when the spec has none)
c = shim(1); c.slash("ignore Consecration")
t.check("/scdt ignore with no spec profile edits the class-wide one", c.db()["profiles"]["PALADIN"]["ignore"].get("consecration") is True)
c = shim(2); c.slash("spells"); c.click_row("Holy Wrath", "check", False); c.tick(0.2); c.slash("ignore Consecration")
t.check("/scdt ignore with a spec profile active edits that spec profile", c.db()["profiles"]["PALADIN:2"]["ignore"].get("consecration") is True and "consecration" not in c.db()["profiles"]["PALADIN"]["ignore"])

# spec API only through C_SpecializationInfo (what Forever's UI uses): spec profiles still work
c = Client("PALADIN", saved={"profiles": {"PALADIN": {"ignore": {}}, "PALADIN:2": {"ignore": {"consecration": True}}}}, spec_api="c_only", spec=2).boot(PALA)
c.cooldown("Consecration", 8, 8); c.tick(0.2)
t.check("spec profile is selected when only C_SpecializationInfo.GetSpecialization exists (Forever UI source uses that)",
            "PALADIN:2" in (debug_profile(c) or ""), debug_profile(c))

# ---------------------------------------------------------------- profiles are per class: another class does not see Paladin settings
c = Client("MAGE", saved={"profiles": {"PALADIN": {"ignore": {"fireball": True}}}}).boot(["Fireball"])
c.cooldown("Fireball", 8, 8); c.tick(0.2)
t.check("a Mage ignores the Paladin profile", c.spell_icon("Fireball") in c.icon_ids() and "MAGE" in c.db()["profiles"])

# ---------------------------------------------------------------- tracked spells window: classes, snapshots
c = Client("PALADIN", saved={"spellCache": {"MAGE": [{"name": "Blink", "icon": 135736}, {"name": "Fireball", "icon": 135812}]}}).boot(PALA)
t.check("spell snapshot for the playing class is saved, sorted by name", [e["name"] for e in c.db()["spellCache"]["PALADIN"]] == sorted(PALA), c.db()["spellCache"]["PALADIN"])
c.slash("spells")
t.check("window opens on the player's own class", "Paladin" in c.ev("SpellCDTrackerSpells.header._text"))
t.check("Paladin-only indicator toggles are visible", all(c.ev(f"SpellCDTrackerSpells.toggles[{i}]._shown") is True for i in range(1, 5)))
c.exe("SpellCDTrackerSpells.classButtons.MAGE._scripts.OnClick()")
t.check("clicking another class shows its saved snapshot", c.ev("SpellCDTrackerSpells.rowSpell[1]") == "Blink" and c.ev("SpellCDTrackerSpells.rowSpell[2]") == "Fireball")
t.check("Paladin toggles hidden for the Mage", all(c.ev(f"SpellCDTrackerSpells.toggles[{i}]._shown") is False for i in range(1, 5)))
c.exe("SpellCDTrackerSpells.classButtons.WARRIOR._scripts.OnClick()")
t.check("a class never seen shows the 'log in once' note", "Log in once on a Warrior" in c.ev("SpellCDTrackerSpells.empty._text"))
c.exe("SpellCDTrackerSpells.classButtons.MAGE._scripts.OnClick()")
c.click_row("Fireball", "check", False)
t.check("editing another class creates that class's profile", c.db()["profiles"]["MAGE"]["ignore"].get("fireball") is True and "fireball" not in c.db()["profiles"]["PALADIN"]["ignore"])
c.click_button("Track none")
t.check("'Track none' ignores every listed spell", set(c.db()["profiles"]["MAGE"]["ignore"]) == {"fireball", "blink"})
c.click_button("Track all")
t.check("'Track all' clears the ignore list", c.db()["profiles"]["MAGE"]["ignore"] == {})
t.check("window raised no error", c.errors() == [], c.errors())
# paging
many = [f"Spell {i:02d}" for i in range(30)]
c = Client("PALADIN").boot(many); c.slash("spells")
t.check("30 spells: first page shows 12 rows, count '1-12 of 30'", c.ev("SpellCDTrackerSpells.count._text") == "1-12 of 30")
c.click_button(">"); t.check("'>' pages forward", c.ev("SpellCDTrackerSpells.count._text") == "13-24 of 30")
c.click_button(">"); c.click_button(">"); t.check("paging stops at the last page", c.ev("SpellCDTrackerSpells.count._text") == "19-30 of 30")
c.click_button("<"); c.click_button("<"); c.click_button("<"); t.check("paging stops at the first page", c.ev("SpellCDTrackerSpells.count._text") == "1-12 of 30")

# ---------------------------------------------------------------- pinned 'Show when ready'
c = Client("PALADIN").boot(PALA)
c.slash("spells")
t.check("Paladin default pins: Judgement and Holy Strike are ticked, Consecration is not",
        c.row_state("Judgement", "pin") is True and c.row_state("Holy Strike", "pin") is True and c.row_state("Consecration", "pin") is False)
c.tick(0.2)
t.check("out of combat nothing ready is shown (readyAlways is off)", c.icons() == [])
c.combat(True); c.tick(0.2)
t.check("in combat the two default pins are shown, grayed, alphabetical (Holy Strike, Judgement)",
        c.icon_ids() == [c.spell_icon("Holy Strike"), c.spell_icon("Judgement")] and all(i["desat"] for i in c.icons()), c.icons())
c.combat(False)
c.slash("")      # options window
c.click_check("Ready icons also out of combat", True); c.tick(0.2)
t.check("'Ready icons also out of combat' shows pins out of combat; saved", len(c.icons()) == 2 and c.db()["readyAlways"] is True)
c.click_check("Ready icons also out of combat", False); c.tick(0.2)
t.check("... and un-ticking hides them again", c.icons() == [])
c.click_row("Judgement", "pin", False)
t.check("unpinning Judgement stores an explicit pin list without it, keeping Holy Strike", c.db()["profiles"]["PALADIN"]["pin"] == {"holy strike": True}, c.db()["profiles"]["PALADIN"])
c.combat(True); c.tick(0.2)
t.check("in combat only Holy Strike stays", c.icon_ids() == [c.spell_icon("Holy Strike")], c.icons())
c.click_row("Consecration", "pin", True); c.tick(0.2)
t.check("pinning Consecration adds it", set(c.db()["profiles"]["PALADIN"]["pin"]) == {"holy strike", "consecration"} and len(c.icons()) == 2)
c.click_row("Holy Strike", "pin", False); c.click_row("Consecration", "pin", False); c.tick(0.2)
t.check("unpinning everything leaves NO pins (defaults do not come back)", c.db()["profiles"]["PALADIN"]["pin"] == {} and c.icons() == [], (c.db()["profiles"]["PALADIN"], c.icons()))

# pinned on cooldown: normal countdown; ordering with unpinned cooldowns
c = Client("PALADIN").boot(PALA)
c.cooldown("Judgement", 6, 10); c.cooldown("Consecration", 2, 8); c.cooldown("Holy Wrath", 30, 30); c.combat(True, secrets=()); c.tick(0.2)
ic = c.icons()
j = [i for i in ic if i["tex"] == c.spell_icon("Judgement")][0]
t.check("pinned spell on cooldown shows a countdown, in full colour", j["text"] != "" and j["desat"] is False and j["cdDur"] == 10, ic)
t.check("pinned icons first in name order (Holy Strike ready, Judgement on cooldown), then unpinned cooldowns soonest first (Consecration 2s, Holy Wrath 30s)",
        [i["tex"] for i in ic] == [c.spell_icon("Holy Strike"), c.spell_icon("Judgement"), c.spell_icon("Consecration"), c.spell_icon("Holy Wrath")], ic)
cons = [i for i in ic if i["tex"] == c.spell_icon("Consecration")][0]
t.check("a countdown under 3 seconds is drawn red, above that white", cons["tcolor"] == [1, 0.3, 0.3] and j["tcolor"] == [1, 1, 1], (cons, j))

# no default pins for other classes
c = Client("MAGE").boot(["Fireball", "Blink"]); c.combat(True); c.tick(0.2)
t.check("Mage: nothing pinned by default, nothing shown while ready in combat", c.icons() == [])
c.slash("spells")
c.click_row("Blink", "pin", True); c.tick(0.2)
t.check("Mage: pinning Blink shows it grayed in combat", c.icon_ids() == [c.spell_icon("Blink")] and c.icons()[0]["desat"], c.icons())
c.combat(False); c.tick(0.2)
t.check("... but not out of combat", c.icons() == [])
c.click_row("Blink", "check", False); c.combat(True); c.tick(0.2)
t.check("an ignored spell is never shown, even pinned", c.icons() == [], c.icons())

# pins are per profile: spec profile has its own
c = shim(2); c.slash("spells"); c.click_row("Judgement", "pin", False)
t.check("pin edit on a spec tab creates the spec profile; class-wide pins untouched",
        "PALADIN:2" in c.db()["profiles"] and "pin" not in c.db()["profiles"]["PALADIN"] and c.db()["profiles"]["PALADIN:2"]["pin"] == {"holy strike": True}, c.db()["profiles"])
c.combat(True); c.tick(0.2); in2 = c.icon_ids()
c.set_spec(1); c.tick(0.2); in1 = c.icon_ids()
t.check("spec 2 shows only Holy Strike while spec 1 (class-wide defaults) shows both", in2 == [c.spell_icon("Holy Strike")] and len(in1) == 2, (in2, in1))

t.finish()
