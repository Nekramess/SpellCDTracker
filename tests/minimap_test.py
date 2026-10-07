"""Minimap button: shape logic (GetMinimapShape convention), the saved override, drag, visibility.
Forever has NO GetMinimapShape; a minimap addon may define it, so it is optional, may error, may return junk.
Expected offsets are worked out by hand for a 140x140 minimap (half size + 5 = 75)."""
import math
from mock_env import Client, Checker

t = Checker("minimap_test")
S2 = math.sqrt(2)

def at(c, angle):
    c.exe(f"SpellCDTrackerDB.minimapAngle = {angle}")
    c.exe("FIRE('PLAYER_ENTERING_WORLD')")     # the addon re-places the button on this event
    return c.mm_offset()

def near(p, q, eps=1e-6):
    return abs(p[0] - q[0]) < eps and abs(p[1] - q[1]) < eps

def new(shape_body=None, saved=None):
    c = Client("MAGE", saved=saved, minimap_shape=shape_body).boot(["Frost Armor"])
    return c

R = 75
SQ225 = (-67.92893218813452, -67.92893218813452)   # (sqrt(2)*75-10)*cos(45 deg), by hand
ring = lambda a: (R * math.cos(math.radians(a)), R * math.sin(math.radians(a)))
box = lambda a: (max(-R, min(R, math.cos(math.radians(a)) * (S2 * R - 10))), max(-R, min(R, math.sin(math.radians(a)) * (S2 * R - 10))))

# --- no GetMinimapShape at all (Forever default): round
c = new()
t.check("default (no GetMinimapShape, no saved shape): button sits on the circle", near(at(c, 200), ring(200)), at(c, 200))
t.check("button is parented to the Minimap and anchored CENTER to CENTER", c.ev("SpellCDTrackerMinimapButton._pt[1]") == "CENTER" and c.ev("SpellCDTrackerMinimapButton._pt[3]") == "CENTER")
t.check("default angle is 200", c.db()["minimapAngle"] == 200)

# --- saved override
c = new()
c.slash("minimap square")
t.check("/scdt minimap square: 200 deg rides the box edge (x clamped to -75)", near(at(c, 200), box(200)) and abs(at(c, 200)[0] + 75) < 1e-9, at(c, 200))
t.check("square: 225 deg is the diagonal point (-67.93,-67.93), inside the box corner (inset by 10)", near(at(c, 225), (-67.92893218813452, -67.92893218813452), 1e-6), at(c, 225))
t.check("square: 90 deg is the top edge (0,75)", near(at(c, 90), (0, 75)), at(c, 90))
c.slash("minimap round")
t.check("/scdt minimap round: back on the circle", near(at(c, 225), ring(225)), at(c, 225))
t.check("shape is saved", c.db()["minimapShape"] == "round")

# --- auto follows GetMinimapShape
cases = [
    ("SQUARE",             [(200, "box"), (45, "box")]),
    ("square",             [(225, "box")]),                       # lower case is accepted
    ("ROUND",              [(225, "ring")]),
    ("CORNER-TOPLEFT",     [(135, "ring"), (315, "box"), (225, "box"), (45, "box")]),
    ("CORNER-BOTTOMRIGHT", [(315, "ring"), (135, "box")]),
    ("CORNER-TOPRIGHT",    [(45, "ring"), (225, "box")]),
    ("CORNER-BOTTOMLEFT",  [(225, "ring"), (45, "box")]),
    ("SIDE-TOP",           [(90, "ring"), (270, "box")]),
    ("SIDE-LEFT",          [(180, "ring"), (0, "box")]),
    ("TRICORNER-TOPLEFT",  [(315, "box"), (135, "ring"), (225, "ring"), (45, "ring")]),
]
for name, pts in cases:
    c = new(f"return '{name}'")
    for ang, kind in pts:
        want = ring(ang) if kind == "ring" else box(ang)
        got = at(c, ang)
        t.check(f"auto + GetMinimapShape()='{name}': {ang} deg is on the {kind}", near(got, want, 1e-6), (got, want))

# --- GetMinimapShape misbehaves: round
for label, body in [("returns nil", "return nil"), ("errors", "error('boom')"), ("returns an unknown name", "return 'HEXAGON'"),
                    ("returns a number", "return 5"), ("returns a table", "return {}")]:
    c = new(body)
    t.check(f"GetMinimapShape {label}: round, and no error", near(at(c, 225), ring(225)) and c.errors() == [], (at(c, 225), c.errors()))

# --- override wins over the API; auto goes back to following it
c = new("return 'SQUARE'")
c.slash("minimap round")
t.check("saved 'round' beats GetMinimapShape()='SQUARE'", near(at(c, 225), ring(225)))
c.exe("function GetMinimapShape() return 'ROUND' end"); c.slash("minimap square")
t.check("saved 'square' beats GetMinimapShape()='ROUND'", near(at(c, 225), SQ225))
c.slash("minimap auto")
t.check("auto after an override: follows GetMinimapShape again (ROUND)", near(c.mm_offset(), ring(225)))
c.exe("function GetMinimapShape() return 'SQUARE' end"); c.slash("minimap auto")
t.check("auto picks up a changed GetMinimapShape on the next command", near(c.mm_offset(), SQ225))

# --- a minimap addon defining GetMinimapShape AFTER this addon loaded
c = new()
t.check("before the minimap addon loads: round", near(at(c, 225), ring(225)))
c.exe("function GetMinimapShape() return 'SQUARE' end")
c.fire("PLAYER_ENTERING_WORLD")
t.check("late GetMinimapShape: PLAYER_ENTERING_WORLD re-places the button on the square", near(c.mm_offset(), SQ225), c.mm_offset())
c.exe("function GetMinimapShape() return 'ROUND' end")
c.fire("PLAYER_LOGIN")
t.check("PLAYER_LOGIN re-places it too", near(c.mm_offset(), ring(225)))

# --- minimap size
c = new("return 'SQUARE'")
c.exe("Minimap._w, Minimap._h = 200, 100")
c.slash("minimap round")
c.exe("SpellCDTrackerDB.minimapAngle = 0"); c.fire("PLAYER_LOGIN")
t.check("non-square minimap (200x100) uses its own half width: 0 deg -> x = 105", near(c.mm_offset(), (105, 0)), c.mm_offset())
c.exe("SpellCDTrackerDB.minimapAngle = 90"); c.fire("PLAYER_LOGIN")
t.check("... and its own half height: 90 deg -> y = 55", near(c.mm_offset(), (0, 55)), c.mm_offset())
c.slash("minimap square")
c.exe("SpellCDTrackerDB.minimapAngle = 45"); c.fire("PLAYER_LOGIN")
dw, dh = S2 * 105 - 10, S2 * 55 - 10
t.check("square on 200x100 at 45 deg", near(c.mm_offset(), (math.cos(math.pi / 4) * dw, math.sin(math.pi / 4) * dh)), c.mm_offset())
c = new()
c.exe("Minimap._w, Minimap._h = nil, nil"); c.exe("SpellCDTrackerDB.minimapAngle = 0"); c.fire("PLAYER_LOGIN")
t.check("minimap size not available yet (nil): falls back to 140 and does not error", near(c.mm_offset(), (75, 0)) and c.errors() == [], (c.mm_offset(), c.errors()))

# --- dragging
c = new()
mm = c.mm()
c.exe("SpellCDTrackerMinimapButton._scripts.OnDragStart(SpellCDTrackerMinimapButton)")
t.check("drag start installs an OnUpdate", c.ev("SpellCDTrackerMinimapButton._scripts.OnUpdate ~= nil"))
c.exe("CURSOR = { 1000, 600 }"); c.tick(0.05)
t.check("dragging to straight above the centre saves angle 90 and moves the button", abs(c.db()["minimapAngle"] - 90) < 1e-6 and near(c.mm_offset(), ring(90)), (c.db()["minimapAngle"], c.mm_offset()))
c.exe("CURSOR = { 900, 500 }"); c.tick(0.05)
t.check("dragging to the left saves angle 180", abs(abs(c.db()["minimapAngle"]) - 180) < 1e-6)
c.exe("SpellCDTrackerMinimapButton._scripts.OnDragStop(SpellCDTrackerMinimapButton)")
t.check("drag stop removes the OnUpdate", c.ev("SpellCDTrackerMinimapButton._scripts.OnUpdate == nil"))
c.exe("CURSOR = { 1000, 400 }"); c.tick(0.05)
t.check("after drag stop the cursor no longer moves it", abs(abs(c.db()["minimapAngle"]) - 180) < 1e-6)
t.check("dragging raised no error", c.errors() == [], c.errors())

# --- click opens options; hide state
c = new()
c.exe("SpellCDTrackerMinimapButton._scripts.OnClick(SpellCDTrackerMinimapButton)")
t.check("clicking the button opens the options window", c.ev("SpellCDTrackerOptions._shown") is True)
t.check("the 'Hide minimap button' option hides it (and saves)", c.click_check("Hide minimap button", True) and c.ev("SpellCDTrackerMinimapButton._shown") is False and c.db()["minimapHide"] is True)
t.check("... and un-ticking shows it again", c.click_check("Hide minimap button", False) and c.ev("SpellCDTrackerMinimapButton._shown") is True)
c = new(saved={"minimapHide": True, "minimapShape": "square", "minimapAngle": 225})
t.check("saved hide/shape/angle are honoured at login", c.ev("SpellCDTrackerMinimapButton._shown") is False and near(c.mm_offset(), SQ225), c.mm_offset())

t.finish()
