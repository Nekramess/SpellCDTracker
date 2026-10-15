"""Wand shots in combat. Seen live (Warlock, 15 Oct 2026): while shooting a wand in combat every spell looked like it
was on cooldown for the wand's attack timer. The game reported, for Shadow Bolt: isActive true, isOnGCD nil,
timeUntilEndOfStartRecovery SET (secret), activeCategory nil. Out of combat the same pause is <= 2 s and was ignored; in combat
the numbers are secret so it was treated as a real cooldown. A spell in start recovery with no cooldown category is not a cooldown."""
from mock_env import Client, Checker

t = Checker("wand_test")
SPELLS = ["Shadow Bolt", "Corruption", "Immolate", "Fear", "Curse of Agony"]

def lock(c):
    return Client("WARLOCK").boot(SPELLS)

def start_recovery(c, names, secs=1.8):
    for n in names:
        c.lua.globals().NAME = n
        c.exe(f"local s = W.spells[NAME]; s.cdStart = W.now; s.cdDur = {secs}; s.gcd = false; s.recovery = true")

def shown(c):
    return [i for i in c.icons() if i["tex"] != c.spell_icon("None")]

c = lock(None)
c.combat(True); c.tick(0.2, 2)
start_recovery(c, SPELLS); c.tick(0.2, 3)
t.check("combat, wand shot pause on every spell (start recovery, no category, secret numbers): no icons", len(c.icons()) == 0, c.icons())
t.check("... no error", c.errors() == [], c.errors())

# the pause repeats with every shot
for _ in range(4):
    c.tick(1.9, 1); start_recovery(c, SPELLS); c.fire("SPELL_UPDATE_COOLDOWN"); c.tick(0.2, 2)
t.check("repeated wand shots: still no icons", len(c.icons()) == 0, c.icons())

# a real cooldown (has a category) is still shown, also while the pause is running
c.lua.globals().NAME = "Fear"
c.exe("local s = W.spells[NAME]; s.cdStart = W.now; s.cdDur = 30; s.gcd = false; s.recovery = true; s.cat = 133")
c.tick(0.2, 3)
fear = [i for i in c.icons() if i["tex"] == c.spell_icon("Fear")]
t.check("a real cooldown (category set) started in combat is still shown with its duration object", len(fear) == 1 and fear[0]["obj"] == "Fear", c.icons())
t.check("... and only that one", len(c.icons()) == 1, c.icons())

# spell without start recovery field (old behaviour for real cooldowns) unchanged
c2 = lock(None)
c2.combat(True); c2.tick(0.2, 2)
c2.lua.globals().NAME = "Immolate"
c2.exe("local s = W.spells[NAME]; s.cdStart = W.now; s.cdDur = 20; s.gcd = false")
c2.tick(0.2, 3)
t.check("combat: a plain cooldown without the recovery field still shows", len(c2.icons()) == 1, c2.icons())

# out of combat with readable numbers is unchanged (short pause ignored, long cooldown shown)
c3 = lock(None)
start_recovery(c3, SPELLS); c3.tick(0.2, 2)
t.check("out of combat: wand pause (1.8 s) ignored", len(c3.icons()) == 0, c3.icons())
c3.cooldown("Fear", 20, 30); c3.tick(0.2, 2)
t.check("out of combat: a real cooldown shows", len(c3.icons()) == 1, c3.icons())

# the wand spell itself: its own cooldown is the wand's attack timer and is never shown
c4 = Client("WARLOCK").boot(["Shadow Bolt", "Shoot", "Fear"])
c4.combat(True); c4.tick(0.2, 2)
c4.lua.globals().NAME = "Shoot"
c4.exe("local s = W.spells[NAME]; s.cdStart = W.now; s.cdDur = 1.8; s.gcd = false; s.cat = 133")
c4.tick(0.2, 3)
t.check("combat: the wand spell (Shoot) with its own attack-timer cooldown shows no icon", len(c4.icons()) == 0, c4.icons())
c4.cooldown("Fear", 20, 30); c4.tick(0.2, 3)
t.check("... other cooldowns still show next to it", len(c4.icons()) == 1 and c4.icons()[0]["tex"] == c4.spell_icon("Fear"), c4.icons())
c4.combat(False); c4.tick(0.2, 2)
c4.lua.globals().NAME = "Shoot"
c4.exe("local s = W.spells[NAME]; s.cdStart = W.now; s.cdDur = 3.0; s.gcd = false")
c4.tick(0.2, 2)
t.check("out of combat: a slow wand (3 s timer, readable) shows no icon either", all(i["tex"] != c4.spell_icon("Shoot") for i in c4.icons()), c4.icons())

t.finish()
