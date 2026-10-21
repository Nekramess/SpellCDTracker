"""Minimap button: registered through the embedded LibDBIcon-1.0 (the real library files run in the mock), because minimap
button managers flag any hand-built minimap button as "a custom button". Checks registration, placement (LibDBIcon follows
the GetMinimapShape convention), drag, click, visibility and the options checkbox.
Forever has NO GetMinimapShape; a minimap addon may define it, so it is optional, may error, may return junk.
Expected offsets are worked out by hand for a 140x140 minimap (half size + LibDBIcon's radius 5 = 75)."""
import math
from mock_env import Client, Checker

t = Checker("minimap_test")
S2 = math.sqrt(2)

def at(c, angle):
    c.exe(f"SpellCDTrackerDB.minimap.minimapPos = {angle}")
    c.exe("LibStub('LibDBIcon-1.0'):Refresh('SpellCDTracker')")      # what /scdt minimap on/off and the options checkbox do
    return c.mm_offset()

def near(p, q, eps=1e-6):
    return abs(p[0] - q[0]) < eps and abs(p[1] - q[1]) < eps

def new(shape_body=None, saved=None):
    return Client("MAGE", saved=saved, minimap_shape=shape_body).boot(["Frost Armor"])

R = 75
ring = lambda a: (R * math.cos(math.radians(a)), R * math.sin(math.radians(a)))
box = lambda a: (max(-R, min(R, math.cos(math.radians(a)) * (S2 * R - 10))), max(-R, min(R, math.sin(math.radians(a)) * (S2 * R - 10))))

# --- registration
c = new()
t.check("registered with LibDBIcon at login", c.ev("LibStub('LibDBIcon-1.0'):IsRegistered('SpellCDTracker')") is True)
obj = "LibStub('LibDataBroker-1.1'):GetDataObjectByName('SpellCDTracker')"
t.check("LibDataBroker launcher object with an icon", c.ev(obj + ".type") == "launcher" and bool(c.ev(obj + ".icon")))
t.check("the button is the one LibDBIcon built (LibDBIcon10_SpellCDTracker), parented to the Minimap", c.ev(c.MM + "._name") == "LibDBIcon10_SpellCDTracker" and c.ev(c.MM + "._parent == Minimap") is True)
t.check("button anchored CENTER to CENTER of the Minimap", c.ev(c.MM + "._pt[1]") == "CENTER" and c.ev(c.MM + "._pt[3]") == "CENTER" and c.ev(c.MM + "._pt[2] == Minimap") is True)
t.check("default angle is 200 (minimapPos), not hidden", c.db()["minimap"] == {"hide": False, "minimapPos": 200}, c.db()["minimap"])
t.check("old hand-built button frame does not exist", c.ev("SpellCDTrackerMinimapButton") is None)
custom = c.ev("(function() local o = {} for _, f in ipairs(CREATED) do if f._kind == 'Button' and f._parent == Minimap and not tostring(f._name):find('^LibDBIcon10_') then o[#o+1] = tostring(f._name) end end return table.concat(o, ',') end)()")
t.check(f"no hand-built minimap button: {custom!r}", custom == "")
lines = c.ev("(function() local o = {}; " + obj + ".OnTooltipShow({ AddLine = function(_, x) o[#o+1] = x end }); return table.concat(o, '|') end)()")
t.check("tooltip: title, click and drag lines", lines.startswith("Spell Cooldown Tracker|") and lines.count("|") >= 2, lines)
t.check("no error while loading", c.errors() == [], c.errors())

# --- no GetMinimapShape at all (Forever default): round
c = new()
t.check("default (no GetMinimapShape): button sits on the circle", near(at(c, 200), ring(200)), at(c, 200))

# --- follows GetMinimapShape
cases = [
    ("SQUARE",             [(200, "box"), (45, "box")]),
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
        t.check(f"GetMinimapShape()='{name}': {ang} deg is on the {kind}", near(got, want, 1e-6), (got, want))

# --- a minimap addon defining GetMinimapShape AFTER this addon loaded: picked up on the next placement
c = new()
t.check("before the minimap addon loads: round", near(at(c, 225), ring(225)))
c.exe("function GetMinimapShape() return 'SQUARE' end")
t.check("late GetMinimapShape: the next Refresh places the button on the square", near(at(c, 225), box(225)), c.mm_offset())

# --- minimap size
c = new("return 'SQUARE'")
c.exe("Minimap._w, Minimap._h = 200, 100")
c.exe("function GetMinimapShape() return 'ROUND' end")
t.check("non-square minimap (200x100) uses its own half width: 0 deg -> x = 105", near(at(c, 0), (105, 0)), c.mm_offset())
t.check("... and its own half height: 90 deg -> y = 55", near(at(c, 90), (0, 55)), c.mm_offset())

# --- dragging
c = new()
b = c.MM
c.exe(f"{b}._scripts.OnDragStart({b})")
t.check("drag start installs an OnUpdate", c.ev(f"{b}._scripts.OnUpdate ~= nil"))
c.exe("CURSOR = { 1000, 600 }"); c.exe(f"{b}._scripts.OnUpdate({b})")
t.check("dragging to straight above the centre saves minimapPos 90 and moves the button", abs(c.db()["minimap"]["minimapPos"] - 90) < 1e-6 and near(c.mm_offset(), ring(90)), (c.db()["minimap"], c.mm_offset()))
c.exe("CURSOR = { 900, 500 }"); c.exe(f"{b}._scripts.OnUpdate({b})")
t.check("dragging to the left saves 180", abs(c.db()["minimap"]["minimapPos"] - 180) < 1e-6)
c.exe(f"{b}._scripts.OnDragStop({b})")
t.check("drag stop removes the OnUpdate", c.ev(f"{b}._scripts.OnUpdate == nil"))
t.check("dragging raised no error", c.errors() == [], c.errors())

# --- click opens options; hide state
c = new()
c.exe(f"{c.MM}._scripts.OnClick({c.MM}, 'LeftButton')")
t.check("clicking the button opens the options window", c.ev("SpellCDTrackerOptions._shown") is True)
t.check("the 'Hide minimap button' option hides it (and saves)", c.click_check("Hide minimap button", True) and c.mm()["_shown"] is False and c.db()["minimap"]["hide"] is True)
t.check("... and un-ticking shows it again", c.click_check("Hide minimap button", False) and c.mm()["_shown"] is True and c.db()["minimap"]["hide"] is False)
c = new(saved={"minimap": {"hide": True, "minimapPos": 225}})
t.check("saved hide setting is honoured at login", c.mm()["_shown"] is False)
c.slash("minimap on")
t.check("saved angle is used for placement", near(c.mm_offset(), ring(225)), c.mm_offset())

# --- libraries missing (broken install): no errors, options and slash command still work
c = Client("MAGE", skip_libs=True).boot(["Frost Armor"])
t.check("without the libraries: login raises no error", c.errors() == [], c.errors())
t.check("without the libraries: no button is built", c.ev("LibStub") is None and c.ev("SpellCDTrackerMinimapButton") is None)
c.slash("minimap off")
t.check("without the libraries: /scdt minimap off still saves the setting, no error", c.db()["minimap"]["hide"] is True and c.errors() == [], c.errors())
c.slash("")
t.check("without the libraries: the options window opens and its hide checkbox works", c.ev("SpellCDTrackerOptions._shown") is True and c.click_check("Hide minimap button", False) and c.db()["minimap"]["hide"] is False and c.errors() == [], c.errors())

t.finish()
