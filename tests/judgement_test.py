"""Judgement pulled in combat (Paladin, seen live 7 Nov 2026, /scdt debug in combat after the cast): isActive true,
isOnGCD nil, activeCategory nil, timeUntilEndOfStartRecovery SECRET, duration SECRET, and the cooldown-ignoring-GCD IsZero
answer is secret too. The addon took that for a wand pause (start recovery, no category) and showed no timer. Now a cast we
saw (spell ID readable) of a spell whose cooldown length we learned while the numbers were readable is timed from the cast."""
from mock_env import Client, Checker

t = Checker("judgement_test")
SP = ["Judgement", "Holy Strike", "Consecration", "Exorcism", "Fear"]

def pal():
    return Client("PALADIN").boot(SP)

def cast(c, name, secs, secret_id=False):
    """The game's view of a cast in combat: start recovery set (secret), no category, long hidden cooldown."""
    c.lua.globals().NAME = name
    c.exe(f"local s = W.spells[NAME]; s.cdStart = W.now; s.cdDur = {secs}; s.gcd = false; s.recovery = true; s.cat = nil")
    if secret_id:
        c.exe("FIRE('UNIT_SPELLCAST_SUCCEEDED', 'player', 'guid', Secret())")
    else:
        c.exe("FIRE('UNIT_SPELLCAST_SUCCEEDED', 'player', 'guid', W.spells[NAME].id)")
    c.fire("SPELL_UPDATE_COOLDOWN")

def icon(c, name):
    return [i for i in c.icons() if i["tex"] == c.spell_icon(name)]

def learn(c, name, secs):
    c.cooldown(name, secs, secs); c.tick(0.2, 2)       # readable numbers, out of combat
    c.clear_cooldown(name); c.tick(0.2, 2)

# 1. learned out of combat, pulled with Judgement
c = pal()
learn(c, "Judgement", 10)
c.combat(True); c.tick(0.2, 3)
j = icon(c, "Judgement")
t.check("combat, Judgement ready: grayed pinned icon", len(j) == 1 and j[0]["desat"] is True, c.icons())
cast(c, "Judgement", 10); c.tick(0.2, 3)
j = icon(c, "Judgement")
t.check("cast in combat (start recovery, no category, secret numbers): the timer starts",
        len(j) == 1 and j[0]["text"] != "" and j[0]["cdDur"] == 10 and j[0]["desat"] is not True, c.icons())
t.check("... no error", c.errors() == [], c.errors())
c.tick(1.0, 4); j = icon(c, "Judgement")
t.check("... and it keeps counting down", len(j) == 1 and j[0]["text"] != "", c.icons())
c.exe("W.now = W.now + 20; W.spells['Judgement'].cdDur = 0; W.spells['Judgement'].recovery = false"); c.tick(0.2, 3)
j = icon(c, "Judgement")
t.check("cooldown over: back to the grayed ready icon", len(j) == 1 and j[0]["desat"] is True and j[0]["text"] == "", c.icons())

# 2. never seen out of combat: nothing known about its length, so the old (wand) rule applies
c = pal(); c.combat(True); c.tick(0.2, 2)
cast(c, "Judgement", 10); c.tick(0.2, 3)
j = icon(c, "Judgement")
t.check("cooldown length never learned: no made-up timer", len(j) == 1 and j[0]["desat"] is True and j[0]["text"] == "", c.icons())

# 3. wand pause: every spell in start recovery, no cast of ours: still nothing, even for spells with a learned cooldown
c = Client("WARLOCK").boot(["Shadow Bolt", "Corruption", "Fear"])
learn(c, "Fear", 30)
c.combat(True); c.tick(0.2, 2)
for n in ("Shadow Bolt", "Corruption", "Fear"):
    c.lua.globals().NAME = n
    c.exe("local s = W.spells[NAME]; s.cdStart = W.now; s.cdDur = 1.8; s.gcd = false; s.recovery = true")
c.tick(0.2, 3)
t.check("wand pause, Fear has a learned cooldown but was not cast: no icon", len(c.icons()) == 0, c.icons())

# 4. spell ID hidden in combat: cannot tell which spell was cast, so the old rule stays (and nothing breaks)
c = pal(); learn(c, "Judgement", 10); c.combat(True); c.tick(0.2, 2)
cast(c, "Judgement", 10, secret_id=True); c.tick(0.2, 3)
j = icon(c, "Judgement")
t.check("secret spell ID: no error, no guessed timer", c.errors() == [] and len(j) == 1 and j[0]["text"] == "", (c.icons(), c.errors()))

# 5. the cooldown length is kept in the saved variables
c = pal(); learn(c, "Holy Strike", 9)
t.check("learned length stored in the saved variables", c.ev("SpellCDTrackerDB.cdLearned['Holy Strike']") == 9, c.ev("SpellCDTrackerDB.cdLearned"))
t.finish()
