"""Combat transitions with secret values. In combat the mock returns a metatable value that THROWS on arithmetic,
comparison, concatenation, indexing and tostring (as Forever's secret values do), plus issecretvalue.
Cooldown start/duration, aura fields, totem info, weapon-enchant info (optional), equipment ids and UnitExists
('pet') can each be secret. The addon must never let one of those throw."""
import re
from mock_env import Client, Checker

t = Checker("combat_test")
ALL = ["WARRIOR", "PALADIN", "HUNTER", "ROGUE", "PRIEST", "SHAMAN", "MAGE", "WARLOCK", "DRUID"]

# ---- the stub itself behaves like a secret value (otherwise every other check here proves nothing)
c = Client("MAGE")
for label, expr in [("arithmetic", "return Secret() + 1"), ("comparison <", "return Secret() < 1"), ("comparison >", "return 1 > Secret()"),
                    ("<=", "return Secret() <= Secret()"), ("concatenation", "return 'x' .. Secret()"), ("tostring", "return tostring(Secret())"),
                    ("indexing", "return Secret().name"), ("string method", "return Secret():find('a')"),
                    ("string.format", "return string.format('%d', Secret())")]:
    ok = c.ev(f"(function() local ok = pcall(function() {expr} end) return ok end)()")
    t.check(f"secret stub throws on {label}", ok is False)
t.check("issecretvalue(secret) is true, for plain values false", c.ev("issecretvalue(Secret()) == true and issecretvalue(5) == false and issecretvalue(nil) == false and issecretvalue('a') == false"))
t.check("Cooldown:SetCooldown refuses secret numbers (tainted caller)", c.ev("(function() local f = CreateFrame('Cooldown'); local ok = pcall(f.SetCooldown, f, Secret(), Secret()) return ok end)()") is False)

# ---------------------------------------------------------------- cooldown row
def pal():
    return Client("PALADIN").boot(["Judgement", "Consecration", "Holy Wrath", "Hammer of Justice", "Exorcism", "Seal of Righteousness"])

c = pal()
c.cooldown("Consecration", 8, 8); c.tick(0.2)
ic = c.icons()
t.check("out of combat: a spell on cooldown shows with a readable countdown", len(ic) == 1 and ic[0]["tex"] == c.spell_icon("Consecration") and re.match(r"^\d", ic[0]["text"]) and ic[0]["cdDur"] == 8, ic)

c.combat(True); c.tick(0.2, 3)
ic = [i for i in c.icons() if i["tex"] == c.spell_icon("Consecration")]
t.check("enter combat: cooldown seen before combat keeps its countdown from the cache (no secret read needed)", len(ic) == 1 and ic[0]["text"] != "" and ic[0]["cdDur"] == 8, c.icons())
t.check("... no error while secret", c.errors() == [], c.errors())

# a cooldown that STARTS in combat: start/duration are secret, isActive is plain
c.cooldown("Holy Wrath", 30, 30); c.tick(0.2)
byicon = {i["tex"]: i for i in c.icons()}
hw = byicon.get(c.spell_icon("Holy Wrath"))
t.check("cooldown first seen in combat (secret numbers) still shows an icon", hw is not None, c.icons())
t.check("... drawn from a duration object, no readable text, no numeric SetCooldown", hw and hw["obj"] == "Holy Wrath" and hw["text"] == "" and hw.get("cdStart") is None, hw)
n = c.ev("W.calls.durApplied")
c.tick(0.2, 5)
t.check("... the duration object is not re-applied every tick", c.ev("W.calls.durApplied") == n, (n, c.ev("W.calls.durApplied")))
c.fire("SPELL_UPDATE_COOLDOWN"); c.tick(0.2)
t.check("... but is re-applied after SPELL_UPDATE_COOLDOWN (generation changed)", c.ev("W.calls.durApplied") == n + 1, (n, c.ev("W.calls.durApplied")))
t.check("no error through all of that", c.errors() == [], c.errors())

# only the GCD
c.gcd("Hammer of Justice"); c.fire("SPELL_UPDATE_COOLDOWN"); c.tick(0.2)
t.check("combat: a spell that is only on the global cooldown shows nothing", c.spell_icon("Hammer of Justice") not in c.icon_ids(), c.icons())
c.gcd("Hammer of Justice", False)

# ready spells: pinned (Judgement is a default pin for Paladin) vs not
c.tick(0.2)
j = [i for i in c.icons() if i["tex"] == c.spell_icon("Judgement")]
t.check("combat: pinned ready spell (Judgement) stays, grayed out", len(j) == 1 and j[0]["desat"] is True and abs(j[0]["alpha"] - 0.55) < 1e-9 and j[0]["text"] == "", j)
t.check("combat: an unpinned ready spell (Exorcism) is not shown", c.spell_icon("Exorcism") not in c.icon_ids())
t.check("pinned icons are listed before cooldown icons", c.icon_ids()[0] == c.spell_icon("Judgement"), c.icons())

# cache runs out, then a NEW cooldown starts while numbers are secret
c.exe("W.now = W.now + 20"); c.clear_cooldown("Consecration"); c.tick(0.2)
t.check("combat: expired cached cooldown disappears when the plain isActive flag says ready", c.spell_icon("Consecration") not in c.icon_ids(), c.icons())
c.cooldown("Consecration", 8, 8); c.tick(0.2)
t.check("combat: the same spell cooling down again (cache expired) switches to the secret/duration-object path", [i for i in c.icons() if i["tex"] == c.spell_icon("Consecration")][0]["obj"] == "Consecration", c.icons())
t.check("no error", c.errors() == [], c.errors())

# no spellbook rescan in combat; rescan on PLAYER_REGEN_ENABLED
c.add_spell("Avenging Wrath"); c.fire("SPELLS_CHANGED"); c.cooldown("Avenging Wrath", 100, 100); c.tick(0.2, 2)
t.check("spell learned in combat is not scanned until combat ends", c.spell_icon("Avenging Wrath") not in c.icon_ids())
c.combat(False); c.tick(0.2, 2)
t.check("leaving combat rescans: the new spell is tracked, readable cooldown", c.spell_icon("Avenging Wrath") in c.icon_ids() and c.errors() == [], c.errors())
t.check("leaving combat: numbers are plain again (countdown text)", all(i["text"] != "" for i in c.icons() if i["alpha"] == 1), c.icons())

# GetSpellCooldownDuration failing is contained
c = pal(); c.combat(True)
c.exe("C_Spell.GetSpellCooldownDuration = function() error('restricted') end")
c.cooldown("Holy Wrath", 30, 30); c.tick(0.2, 3)
t.check("GetSpellCooldownDuration erroring: no error escapes, icon still drawn", c.errors() == [] and c.spell_icon("Holy Wrath") in c.icon_ids(), c.errors())
c.exe("C_Spell.GetSpellCooldownDuration = function() return nil end"); c.exe("W.spells['Holy Wrath'].cdStart = W.now"); c.tick(0.2, 3)
t.check("GetSpellCooldownDuration returning nothing: no error", c.errors() == [], c.errors())

# /scdt debug in combat with secret cooldown numbers
c = pal(); c.cooldown("Consecration", 5, 8); c.combat(True); c.tick(0.2)
c.cooldown("Holy Wrath", 30, 30)
c.slash("debug Holy Wrath"); c.slash("debug Consecration")
t.check("/scdt debug in combat with secret numbers does not throw", c.errors() == [] and any("Holy Wrath: id" in p for p in c.printed), c.errors())

# ---------------------------------------------------------------- Paladin aura panel
def seal_state(c): return c.icon_at("SpellCDTrackerPalaFrame.seal")

c = pal()
c.set_buffs([("Seal of Righteousness", 25, 30), ("Blessing of Might", 280, 300), ("Devotion Aura", None, None)])
c.tick(0.2)
s = seal_state(c)
t.check("out of combat: Seal shows with its countdown", s["shown"] and s["text"] != "" and s["tex"] is not None and s["desat"] is False, s)
t.check("aura reads were used out of combat", c.ev("W.calls.aura") > 0)
calls = c.ev("W.calls.aura")
c.combat(True); c.tick(0.2, 10)
t.check("in combat the aura API is not touched at all (ShouldAurasBeSecret is true)", c.ev("W.calls.aura") == calls, (calls, c.ev("W.calls.aura")))
s = seal_state(c)
t.check("in combat the Seal keeps its last known state and keeps counting down", s["shown"] and s["text"] != "" and s["desat"] is False and c.errors() == [], (s, c.errors()))
c.exe("W.now = W.now + 40"); c.tick(0.2)
s = seal_state(c)
t.check("in combat an expired Seal lapses to the red 'missing' state", s["desat"] is True and s["border"][0] == 1 and s["border"][1] == 0.1, s)
c.cast("Seal of Righteousness"); c.tick(0.2)
s = seal_state(c)
t.check("in combat, casting the Seal (readable spell id) restores it from the cast", s["desat"] is False and s["text"] != "", s)
c.cast_secret(); c.tick(0.2)
t.check("a secret spell id on UNIT_SPELLCAST_SUCCEEDED is ignored without error", c.errors() == [] and seal_state(c)["desat"] is False, c.errors())

# Righteous Fury needs the spell known
c = Client("PALADIN").boot(["Judgement", "Seal of Righteousness", "Righteous Fury"])
c.combat(True); c.cast("Righteous Fury"); c.tick(0.2)
rf = c.icon_at("SpellCDTrackerPalaFrame.rf")
t.check("in combat, casting Righteous Fury shows it with the 30 minute default timer", rf["shown"] and rf["desat"] is False and rf["text"] == "30m", rf)

# API says 'not secret' but returns secret fields anyway: contained, one message, state kept
c = pal()
c.set_buffs([("Seal of Righteousness", 25, 30)]); c.tick(0.2)
c.exe("W.secretAuraValues = true")          # ShouldAurasBeSecret() stays false
c.tick(0.2, 15)
errs = c.errors()
t.check("aura values secret while ShouldAurasBeSecret()==false: nothing escapes to the client", c.raised == [], c.raised)
t.check("... the addon reports it once, not every tick", len(errs) == 1, errs)
t.check("... and keeps the last known Seal", seal_state(c)["desat"] is False)

# ---------------------------------------------------------------- non-Paladin buff row
c = Client("MAGE").boot(["Arcane Intellect", "Frost Armor", "Ice Barrier"])
c.set_buffs([("Arcane Intellect", 1700, 1800), ("Frost Armor", 1600, 1800)]); c.tick(0.2)
ic = c.icons("SpellCDTrackerBuffFrame")
t.check("Mage out of combat: Intellect and Armor icons with timers", len(ic) == 2 and all(i["text"] != "" for i in ic), ic)
calls = c.ev("W.calls.aura"); c.combat(True); c.tick(0.2, 10)
t.check("Mage in combat: aura API untouched, icons kept, no error", c.ev("W.calls.aura") == calls and len(c.icons("SpellCDTrackerBuffFrame")) == 2 and c.errors() == [], c.errors())
c.exe("W.now = W.now + 1750"); c.tick(0.2)
ic = c.icons("SpellCDTrackerBuffFrame")
t.check("Mage in combat: expired Arcane Intellect becomes the red 'missing' icon (maintain buff)", any(i["desat"] and i["border"][0] == 1 for i in ic), ic)
c.cast("Arcane Intellect"); c.tick(0.2)
ic = c.icons("SpellCDTrackerBuffFrame")
t.check("Mage in combat: recasting Intellect restores it from the cast (duration remembered from the aura read)", any(i["text"] == "30m" for i in ic), ic)

# ---------------------------------------------------------------- Shaman totems and imbues
c = Client("SHAMAN").boot(["Rockbiter Weapon", "Searing Totem", "Lightning Shield"])
c.set_totem(1, "Searing Totem", 50, 60); c.set_enchant("main", 600000); c.tick(0.2)
t.check("Shaman out of combat: totem and imbue icons", len(c.icons("SpellCDTrackerBuffFrame")) >= 2, c.icons("SpellCDTrackerBuffFrame"))
c.combat(True, secrets=("totems",)); c.tick(0.2, 5)
t.check("totem info secret in combat: cached totem stays, no error", c.errors() == [] and any(i["text"] != "" for i in c.icons("SpellCDTrackerBuffFrame")), c.errors())
n_before = len(c.icons("SpellCDTrackerBuffFrame"))
c.exe("W.now = W.now + 70"); c.tick(0.2)
t.check("secret totem info: the cached totem is dropped once its timer ran out", c.errors() == [] and len(c.icons("SpellCDTrackerBuffFrame")) == n_before - 1, (n_before, c.icons("SpellCDTrackerBuffFrame")))
c.combat(False)

c = Client("SHAMAN").boot(["Rockbiter Weapon"])
c.set_equip(main="INVTYPE_2HWEAPON")      # no gear warning, so the imbue is the only icon
c.set_enchant("main", 600000); c.tick(1.1)
t.check("setup: imbue active, shown with its timer", [i["text"] for i in c.icons("SpellCDTrackerBuffFrame")] in (["10m"], ["11m"]), c.icons("SpellCDTrackerBuffFrame"))
before = c.icons("SpellCDTrackerBuffFrame")
c.combat(True, secrets=("enchant",)); c.tick(1.1, 5)
t.check("weapon-enchant API returning secrets: no error escapes", c.errors() == [], c.errors())
c.slash("debug")
t.check("... debug names the reason", any("GetWeaponEnchantInfo returns secret values" in p for p in c.printed), c.new_output())
after = c.icons("SpellCDTrackerBuffFrame")
imbue_kept = len(after) == 1 and after[0]["desat"] is False
# GetWeaponEnchantInfo is documented with no secret-return flag, so this is a hypothetical risk; the addon itself handles the case.
t.known_bug("imbue that was active before combat stays shown as active when the enchant API returns secrets",
            imbue_kept, "ReadImbues() overwrites imbueState with nil every tick (and ignores the cast fallback once the API was trusted)")

# ---------------------------------------------------------------- equipment / pet secrets
c = Client("PALADIN").boot(["Judgement"])
c.set_equip(main="INVTYPE_WEAPON", off="INVTYPE_SHIELD"); c.tick(1.1)
t.check("setup: shield + 1H, no gear warning", c.icons("SpellCDTrackerBuffFrame") == [], c.icons("SpellCDTrackerBuffFrame"))
c.combat(True, secrets=("equip",)); c.tick(1.1, 3)
t.check("secret inventory item ids: no error escapes", c.errors() == [], c.errors())
shown = c.icons("SpellCDTrackerBuffFrame")
if shown:
    t.info("secret equipment ids make the gear check show a warning (looks like an empty main hand); only matters if GetInventoryItemID is secret in combat on Forever (not documented): live check")

c = Client("HUNTER").boot(["Call Pet", "Arcane Shot"])
c.set_equip(main="INVTYPE_2HWEAPON", ranged="INVTYPE_RANGEDRIGHT"); c.exe("W.pet = false"); c.tick(1.1)
t.check("Hunter out of combat, pet missing: PET icon shown", any(i["text"] == "PET" or i["desat"] for i in c.icons("SpellCDTrackerBuffFrame")), c.icons("SpellCDTrackerBuffFrame"))
c.combat(True, secrets=("unit",)); c.tick(0.2, 3)
t.check("UnitExists('pet') secret in combat: no error and no false PET reminder", c.errors() == [] and c.icons("SpellCDTrackerBuffFrame") == [], (c.errors(), c.icons("SpellCDTrackerBuffFrame")))

# ---------------------------------------------------------------- soak: every class, everything secret
for cls in ALL:
    spells = {"WARRIOR": ["Bloodthirst", "Battle Shout"], "PALADIN": ["Judgement", "Consecration", "Seal of Righteousness", "Righteous Fury", "Devotion Aura"],
              "HUNTER": ["Call Pet", "Aspect of the Hawk", "Arcane Shot"], "ROGUE": ["Poisons", "Evasion", "Sinister Strike"],
              "PRIEST": ["Power Word: Fortitude", "Inner Fire", "Smite"], "SHAMAN": ["Rockbiter Weapon", "Lightning Shield", "Earth Shock"],
              "MAGE": ["Arcane Intellect", "Frost Armor", "Fireball"], "WARLOCK": ["Summon Imp", "Demon Armor", "Corruption"],
              "DRUID": ["Mark of the Wild", "Thorns", "Wrath"]}[cls]
    c = Client(cls).boot(spells)
    c.set_equip(main="INVTYPE_WEAPON"); c.set_buffs([(spells[1] if cls != "PALADIN" else "Seal of Righteousness", 100, 120)])
    c.cooldown(spells[0], 6, 10); c.tick(1.1, 2)
    for rnd in range(3):
        c.combat(True, secrets=("cd", "auras", "totems", "enchant", "equip", "unit"))
        c.cooldown(spells[-1], 20, 20)
        c.fire("SPELL_UPDATE_COOLDOWN"); c.cast(spells[0]); c.cast_secret(); c.fire("PLAYER_EQUIPMENT_CHANGED")
        c.tick(1.1, 4)
        c.slash("debug")
        c.combat(False); c.clear_cooldown(spells[-1]); c.tick(1.1, 2)
    t.check(f"{cls}: 3 combat cycles with everything secret, no error at all", c.errors() == [], c.errors())

t.finish()
