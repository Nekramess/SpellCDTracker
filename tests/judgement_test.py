"""Judgement pulled in combat (Paladin, seen live 7 Nov 2026): the timer never started when the first cast happened in
combat. Out of combat the numbers are readable and it worked. In combat the numbers are secret and the addon decided
from the cached isOnGCD flag, which can stay true when no SPELL_UPDATE_COOLDOWN arrives after the GCD ends. The game's
own answer (duration object ignoring the GCD, IsZero) is a plain boolean and is now used first."""
from mock_env import Client, Checker

t = Checker("judgement_test")

def pal():
    return Client("PALADIN").boot(["Judgement", "Holy Strike", "Consecration", "Exorcism", "Hammer of Justice"])

def judge_icon(c):
    return [i for i in c.icons() if i["tex"] == c.spell_icon("Judgement")]

c = pal()
c.combat(True); c.tick(0.2, 3)
j = judge_icon(c)
t.check("combat, Judgement ready: grayed pinned icon", len(j) == 1 and j[0]["desat"] is True, c.icons())

# cast: GCD and a 10 s cooldown start together; the event sees the spell on the GCD
c.lua.globals().NAME = "Judgement"
c.exe("local s = W.spells[NAME]; s.cdStart = W.now; s.cdDur = 10; s.gcd = true")
c.fire("SPELL_UPDATE_COOLDOWN"); c.tick(0.2, 2)
# the GCD ends and the game sends no further SPELL_UPDATE_COOLDOWN
c.exe("W.now = W.now + 1.6; W.spells[NAME].gcd = false")
c.tick(0.2, 3)
j = judge_icon(c)
t.check("first cast in combat, stale GCD flag: the cooldown still starts (duration object, not grayed)",
        len(j) == 1 and j[0].get("obj") == "Judgement" and j[0]["desat"] is not True, j)
t.check("... no error", c.errors() == [], c.errors())

# a real cooldown is asked for without the GCD
t.check("the object is requested with ignoreGCD", c.ev("W.calls.lastIgnoreGCD") is True, c.ev("W.calls.lastIgnoreGCD"))

# GCD only (no cooldown): nothing
c2 = pal(); c2.combat(True); c2.tick(0.2, 2)
c2.gcd("Hammer of Justice"); c2.fire("SPELL_UPDATE_COOLDOWN"); c2.tick(0.2, 2)
t.check("combat, GCD only: no cooldown icon", c2.spell_icon("Hammer of Justice") not in c2.icon_ids(), c2.icons())

# answer hidden or missing: the old rules still apply
for flag in ("isZeroSecret", "noIsZero"):
    c3 = pal(); c3.exe(f"W.{flag} = true"); c3.combat(True); c3.tick(0.2, 2)
    c3.cooldown("Holy Strike", 10, 10); c3.tick(0.2, 3)
    h = [i for i in c3.icons() if i["tex"] == c3.spell_icon("Holy Strike")]
    t.check(f"{flag}: a plain cooldown still shows, no error", len(h) == 1 and h[0].get("obj") == "Holy Strike" and c3.errors() == [], (c3.icons(), c3.errors()))

t.finish()
