"""Shared simulated Forever client for the SpellCDTracker tests (Lua 5.1 via lupa). Not the live client.

Every mocked API was checked against the Forever 1.60.1 UI source
(wow-ui-source, branch forever, Interface/AddOns/Blizzard_APIDocumentationGenerated/*Documentation.lua);
forever_api_check_test.py re-verifies those names and signatures when the source is on disk.

What is deliberately ABSENT, because Forever does not have it (code that calls it must fail loudly):
  C_Console, issecret, GetMinimapShape (addons define it), GetSpellInfo, GetSpellCooldown (old global),
  GetSpecialization (only C_SpecializationInfo.GetSpecialization, plus a deprecated global shim
  in the Standard game type that is gated by the loadDeprecationFallbacks CVar), the global OffhandHasWeapon
  (only C_PaperDollInfo.OffhandHasWeapon), UnitBuff (only a deprecated shim, off by default here).

Run from the repo root:  python3 tests/<name>_test.py     (or: python3 tests/run_all.py)
Set SCDT_LUA=/path/to/other/SpellCDTracker.lua to test a different copy (used by mutation_check.py).
"""
import os
import sys
from lupa.lua51 import LuaRuntime, LuaError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = "SpellCDTracker"
ERR_MARK = "Spell Cooldown Tracker error:"

MOCK = r'''
W = {
  now = 1000, combat = false,
  -- what is secret right now (set by combat())
  secretCd = false, secretAurasFlag = false, secretAuraValues = false, secretTotems = false,
  secretEnchant = false, secretEquip = false, secretUnit = false,
  class = "PALADIN", className = "Paladin",
  spells = {}, book = {}, actions = {},
  buffs = {}, totems = {}, enchant = {}, equip = {}, items = {}, pet = true,
  calls = { aura = 0, durObj = 0, scan = 0, enchant = 0, totem = 0 },
  shims = { GetWeaponEnchantInfo = true },
  nextId = 1000,
}

-- ---------------------------------------------------------------- secret values
local SMT = {}
local function boom() error("attempt to use a secret value", 2) end
for _, k in ipairs({ "__add", "__sub", "__mul", "__div", "__mod", "__pow", "__unm", "__lt", "__le",
                     "__concat", "__len", "__call", "__index", "__newindex", "__tostring", "__eq" }) do SMT[k] = boom end
function Secret() return setmetatable({}, SMT) end
function issecretvalue(v) return getmetatable(v) == SMT end
function IsSecret(v) return getmetatable(v) == SMT end

-- ---------------------------------------------------------------- generic helpers Forever provides
function CopyTable(t, seen)
  seen = seen or {}
  if seen[t] then return seen[t] end
  local o = {}; seen[t] = o
  for k, v in pairs(t) do o[k] = (type(v) == "table") and CopyTable(v, seen) or v end
  return o
end
function wipe(t) for k in pairs(t) do t[k] = nil end return t end
function tinsert(t, v) table.insert(t, v) end
function GetTime() return W.now end
function InCombatLockdown() return W.combat end
function UnitAffectingCombat(u) return W.combat end
function UnitClass(u) return W.className, W.class, 1 end
function UnitIsUnit(a, b) return a == b end
function UnitExists(u)
  if W.secretUnit then return Secret() end
  if u == "pet" then return W.pet end
  return u == "player"
end
LOCALIZED_CLASS_NAMES_MALE = { PALADIN = "Paladin", WARRIOR = "Warrior", HUNTER = "Hunter", ROGUE = "Rogue", PRIEST = "Priest",
  SHAMAN = "Shaman", MAGE = "Mage", WARLOCK = "Warlock", DRUID = "Druid" }
RAID_CLASS_COLORS = { PALADIN = { r = 0.96, g = 0.55, b = 0.73 } }
CLASS_ICON_TCOORDS = {}
for k in pairs(LOCALIZED_CLASS_NAMES_MALE) do CLASS_ICON_TCOORDS[k] = { 0, 0.25, 0, 0.25 } end
C_Texture = { GetAtlasInfo = function() return nil end }
BackdropTemplateMixin = {}
INVSLOT_MAINHAND, INVSLOT_OFFHAND, INVSLOT_RANGED = 16, 17, 18
Enum = { SpellBookSpellBank = { Player = 0, Pet = 1 }, SpellBookItemType = { None = 0, Spell = 1, FutureSpell = 2, PetAction = 3, Flyout = 4 } }
SlashCmdList = {}
UISpecialFrames = {}

-- ---------------------------------------------------------------- frames
UNKNOWN_CALLS = {}
CREATED = {}
local COOLDOWN_ONLY = { SetCooldown = true, SetCooldownFromDurationObject = true, Clear = true,
                        SetHideCountdownNumbers = true, SetDrawEdge = true }
local M = {}
local function same(f) return f end
function M.SetScript(self, ev, fn) self._scripts[ev] = fn end
function M.GetScript(self, ev) return self._scripts[ev] end
function M.HookScript() end
function M.RegisterEvent(self, e) self._events[e] = true end
function M.RegisterUnitEvent(self, e, unit) self._events[e] = true end
function M.UnregisterEvent(self, e) self._events[e] = nil end
function M.Show(self)
  if self._shown then return end
  self._shown = true
  if self._scripts.OnShow then self._scripts.OnShow(self) end
end
function M.Hide(self)
  if not self._shown then return end
  self._shown = false
  if self._scripts.OnHide then self._scripts.OnHide(self) end
end
function M.SetShown(self, v) self._shown = v and true or false end
function M.IsShown(self) return self._shown end
function M.SetAlpha(self, a) self._alpha = a end
function M.GetAlpha(self) return self._alpha end
function M.SetText(self, t) self._text = t or "" end
function M.GetText(self) return self._text end
function M.SetTextColor(self, r, g, b) self._tcolor = { r, g, b } end
function M.SetPoint(self, ...) self._pts = self._pts or {}; table.insert(self._pts, { ... }); self._pt = { ... } end
function M.ClearAllPoints(self) self._pts = nil; self._pt = nil end
function M.GetPoint(self, i) local p = self._pt; if not p then return end; return p[1], p[2], p[3], p[4], p[5] end
function M.SetSize(self, w, h) self._w, self._h = w, h end
function M.GetWidth(self) return self._w end
function M.GetHeight(self) return self._h end
function M.GetFrameLevel() return 1 end
function M.GetEffectiveScale() return 1 end
function M.SetChecked(self, v) self._checked = v and true or false end
function M.GetChecked(self) return self._checked end
function M.SetTexture(self, t) self._tex = t; self._color = nil end
function M.SetColorTexture(self, r, g, b, a) self._color = { r, g, b }; self._tex = nil end
function M.SetDesaturated(self, v) self._desat = v and true or false end
function M.SetFont(self, ...) self._font = { ... } end
function M.EnableMouse(self, v) self._mouse = v and true or false end
function M.IsMouseEnabled(self) return self._mouse end
function M.GetThumbTexture(self) self._thumb = self._thumb or CreateFrame("Texture"); return self._thumb end
function M.CreateFontString(self) local fs = CreateFrame("FontString", nil, self); self._fs = self._fs or {}; table.insert(self._fs, fs); return fs end
function M.CreateTexture(self) return CreateFrame("Texture", nil, self) end
-- Cooldown widget (FrameAPICooldownDocumentation.lua): SetCooldown(start, duration, modRate),
-- SetCooldownFromDurationObject(duration, clearIfZero), Clear()
function M.SetCooldown(self, s, d)
  if IsSecret(s) or IsSecret(d) then error("Cooldown:SetCooldown called with secret values from tainted code", 2) end
  if type(s) ~= "number" or type(d) ~= "number" then error("bad argument to SetCooldown", 2) end
  self._cdStart, self._cdDur, self._cdObj = s, d, nil
end
function M.SetCooldownFromDurationObject(self, obj)
  if type(obj) ~= "table" or not obj.isDurationObject then error("SetCooldownFromDurationObject needs a LuaDurationObject", 2) end
  self._cdObj, self._cdStart, self._cdDur = obj, nil, nil
  W.calls.durApplied = (W.calls.durApplied or 0) + 1
end
function M.Clear(self) self._cdStart, self._cdDur, self._cdObj = nil, nil, nil end
function M.SetHideCountdownNumbers(self, v) self._hideNums = v end
function M.SetDrawEdge() end

local FMT = {}
FMT.__index = function(t, k)
  local m = M[k]
  if m then
    if COOLDOWN_ONLY[k] and rawget(t, "_kind") ~= "Cooldown" then return nil end
    return m
  end
  if type(k) == "string" and k:match("^[A-Z]") then
    if COOLDOWN_ONLY[k] then return nil end
    UNKNOWN_CALLS[k] = true
    return function() end
  end
  return nil
end
function CreateFrame(kind, name, parent, tmpl)
  local f = setmetatable({ _kind = kind, _name = name, _scripts = {}, _events = {}, _shown = true, _alpha = 1, _text = "", _template = tmpl }, FMT)
  if name then _G[name] = f end
  table.insert(CREATED, f)
  return f
end
UIParent = CreateFrame("Frame", "UIParent")
GameTooltip = CreateFrame("GameTooltip", "GameTooltip")
Minimap = CreateFrame("Frame", "Minimap")
Minimap._w, Minimap._h = 140, 140
function Minimap:GetCenter() return 1000, 500 end
CURSOR = { 1000, 500 }
function GetCursorPosition() return CURSOR[1], CURSOR[2] end
EditModeManagerFrame = CreateFrame("Frame", "EditModeManagerFrame"); EditModeManagerFrame._shown = false
SwingTimerMainHandFrame = CreateFrame("Frame", "SwingTimerMainHandFrame")
SwingTimerOffHandFrame = CreateFrame("Frame", "SwingTimerOffHandFrame")
SwingTimerRangedFrame = CreateFrame("Frame", "SwingTimerRangedFrame")

function FIRE(event, ...)
  for _, f in ipairs(CREATED) do
    local fn = f._scripts.OnEvent
    if fn and f._events[event] then fn(f, event, ...) end
  end
end
function TICK(dt)
  W.now = W.now + dt
  for _, f in ipairs(CREATED) do
    local fn = f._scripts.OnUpdate
    if fn and f._shown then fn(f, dt) end
  end
end

-- ---------------------------------------------------------------- spells (C_Spell, C_SpellBook)
local function lookup(x)
  if type(x) == "number" then
    for _, s in pairs(W.spells) do if s.id == x then return s end end
  else
    return W.spells[x]
  end
end
C_Spell = {}
function C_Spell.GetSpellName(x) local s = lookup(x); return s and s.name end
function C_Spell.GetSpellTexture(x) local s = lookup(x); return s and s.icon end
function C_Spell.GetSpellDescription(x) local s = lookup(x); return s and (s.desc or "") end
function C_Spell.GetSpellCooldown(x)
  local s = lookup(x)
  if not s then return nil end
  local active = (s.cdDur or 0) > 0 and (s.cdStart + s.cdDur) > W.now
  local info = { startTime = s.cdStart or 0, duration = s.cdDur or 0, isEnabled = true, isActive = active, modRate = 1, isOnGCD = s.gcd and true or false }
  if W.combat and W.secretCd then info.startTime, info.duration = Secret(), Secret() end
  return info
end
function C_Spell.GetSpellCooldownDuration(x, ignoreGCD)
  W.calls.durObj = W.calls.durObj + 1
  local s = lookup(x)
  if not s then return nil end
  return { isDurationObject = true, spell = s.name }
end
C_SpellBook = {}
function C_SpellBook.GetNumSpellBookSkillLines() return 1 end
function C_SpellBook.GetSpellBookSkillLineInfo(i)
  if i ~= 1 then return nil end
  return { name = "General", iconID = 1, itemIndexOffset = 0, numSpellBookItems = #W.book, isGuild = false, shouldHide = false }
end
function C_SpellBook.GetSpellBookItemInfo(slot, bank)
  if bank ~= Enum.SpellBookSpellBank.Player and bank ~= Enum.SpellBookSpellBank.Pet then error("bad spellBookItemSpellBank: " .. tostring(bank), 2) end
  local name = W.book[slot]
  if not name then return nil end
  local s = W.spells[name]
  return { actionID = s.id, spellID = s.id, itemType = Enum.SpellBookItemType.Spell, name = name, subName = "", iconID = s.icon,
           isPassive = s.passive and true or false, isOffSpec = s.offSpec and true or false }
end
function GetActionInfo(slot)
  local n = W.actions[slot]
  if not n then return nil end
  return "spell", W.spells[n].id
end

-- ---------------------------------------------------------------- auras (C_UnitAuras, C_Secrets)
C_Secrets = {}
function C_Secrets.ShouldAurasBeSecret() return W.secretAurasFlag end
C_UnitAuras = {}
function C_UnitAuras.GetAuraDataByIndex(unit, i, filter)
  W.calls.aura = W.calls.aura + 1
  local b = W.buffs[i]
  if not b then return nil end
  if W.secretAuraValues then
    return { name = Secret(), icon = Secret(), duration = Secret(), expirationTime = Secret(), sourceUnit = Secret() }
  end
  return { name = b.name, icon = b.icon, duration = b.duration or 0, expirationTime = b.expires or 0, sourceUnit = b.source }
end

-- ---------------------------------------------------------------- weapon enchants, totems, gear
-- Forever: C_Item.GetWeaponEnchantInfo(slot) returns a table; the global GetWeaponEnchantInfo is a deprecated shim
-- (Deprecated_12_1_0.lua, loaded only when CVar loadDeprecationFallbacks is on) returning 12 values:
-- hasEnchant, remainingTimeMs, charges, enchantID for main hand, off hand, ranged.
C_Item = {}
function C_Item.GetItemInfoInstant(id)
  local it = W.items[id]
  if not it then return nil end
  return id, "Weapon", "Sub", it.loc, 1, 2, 3
end
function C_Item.GetWeaponEnchantInfo(slot) return {} end
function GetInventoryItemID(unit, slot)
  if W.secretEquip then return Secret() end
  return W.equip[slot]
end
function GetWeaponEnchantInfo()
  W.calls.enchant = W.calls.enchant + 1
  local out = {}
  for i, k in ipairs({ "main", "off", "ranged" }) do
    local e = W.enchant[k]
    local o = (i - 1) * 4
    if e then
      out[o + 1], out[o + 2], out[o + 3], out[o + 4] = true, W.secretEnchant and Secret() or e.ms, 0, 1
    else
      out[o + 1] = false
    end
  end
  if W.secretEnchant then for i = 1, 12 do if out[i] ~= nil and i % 4 == 1 then out[i] = Secret() end end end
  return unpack(out, 1, 12)
end
function GetTotemInfo(slot)
  W.calls.totem = W.calls.totem + 1
  local t = W.totems[slot]
  if W.secretTotems then return Secret(), Secret(), Secret(), Secret(), Secret(), 1, Secret() end
  if not t then return false, "", 0, 0, 0, 1, 0 end
  return true, t.name, t.start, t.dur, t.icon, 1, 1
end
C_PaperDollInfo = { OffhandHasWeapon = function() return W.equip[17] ~= nil end }
function GetShapeshiftForm() return W.stance or 0 end
function GetShapeshiftFormInfo(i) return 5000 + i, i == W.stance, true, 1 end

function SETUP_SHIMS()
  if not W.shims.GetWeaponEnchantInfo then GetWeaponEnchantInfo = nil end
end
'''


def _to_py(v):
    """Convert a lupa table to plain Python (dict / list); leave scalars."""
    if hasattr(v, "items") and not isinstance(v, (str, bytes)):
        d = {k: _to_py(x) for k, x in v.items()}
        if d and all(isinstance(k, int) for k in d) and sorted(d) == list(range(1, len(d) + 1)):
            return [d[i] for i in range(1, len(d) + 1)]
        return d
    return v


class Client:
    """One simulated login. The class is fixed at load time (the addon reads UnitClass once)."""

    def __init__(self, cls="PALADIN", saved=None, lua_path=None, shims=("GetWeaponEnchantInfo",),
                 minimap_shape=None, spec=None, spec_api=None):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.printed = []
        self.raised = []
        g = self.lua.globals()
        g.print = lambda *a: self.printed.append(" ".join(str(x) for x in a))
        self.lua.execute(MOCK)
        self.cls = cls
        self.lua.execute(f'W.class = "{cls}"; W.className = "{cls.capitalize()}"')
        if "GetWeaponEnchantInfo" not in shims:
            self.lua.execute("W.shims.GetWeaponEnchantInfo = false; SETUP_SHIMS()")
        if "UnitBuff" in shims:
            self.lua.execute("function UnitBuff() return nil end")
        self.lua_path = lua_path or os.environ.get("SCDT_LUA") or os.path.join(ROOT, "SpellCDTracker.lua")
        self.saved = saved
        if saved is not None:
            self.set_saved(saved)
        if minimap_shape is not None:
            self.set_minimap_shape(minimap_shape)
        if spec_api is not None:
            self.set_spec_api(spec_api, spec)

    # ----------------------------------------------------------- environment control
    def exe(self, code):
        return self.lua.execute(code)

    def ev(self, expr):
        return self.lua.eval(expr)

    def set_saved(self, d):
        """Seed SpellCDTrackerDB from a Python dict (what the client does before ADDON_LOADED)."""
        self.lua.globals()["SpellCDTrackerDB"] = self.py_to_lua(d)

    def py_to_lua(self, v):
        if isinstance(v, dict):
            t = self.lua.table()
            for k, x in v.items():
                t[k] = self.py_to_lua(x)
            return t
        if isinstance(v, list):
            t = self.lua.table()
            for i, x in enumerate(v, 1):
                t[i] = self.py_to_lua(x)
            return t
        return v

    def set_minimap_shape(self, fn_body):
        """Define the optional global GetMinimapShape the way a minimap addon would. fn_body is Lua source of the body."""
        self.exe(f"function GetMinimapShape() {fn_body} end")

    def set_spec_api(self, kind, spec):
        if kind == "global":        # deprecated Standard-game-type shim: GetSpecialization = C_SpecializationInfo.GetSpecialization
            self.exe(f"SPEC = {spec if spec is not None else 'nil'}; function GetSpecialization() return SPEC end; "
                     "function GetSpecializationInfo(i) return i, ({'Holy','Protection','Retribution'})[i] end")
        elif kind == "c_only":      # what Forever's own UI uses
            self.exe(f"SPEC = {spec if spec is not None else 'nil'}; C_SpecializationInfo = {{ GetSpecialization = function() return SPEC end }}")

    def set_spec(self, n):
        self.exe(f"SPEC = {n if n is not None else 'nil'}")

    def add_spells(self, *names, passive=()):
        for n in names:
            self.add_spell(n, passive=(n in passive))

    def add_spell(self, name, passive=False, desc=None, book=True):
        self.lua.globals().NAME = name
        self.exe(f"""
          W.nextId = W.nextId + 1
          W.spells[NAME] = {{ name = NAME, id = W.nextId, icon = W.nextId + 50000, cdStart = 0, cdDur = 0,
                              passive = {str(passive).lower()}, desc = {('"%s"' % desc) if desc else 'nil'} }}
          if {str(book).lower()} then table.insert(W.book, NAME) end
        """)

    def cooldown(self, name, remaining, total):
        """Put a spell on cooldown with `remaining` seconds left of `total`."""
        self.lua.globals().NAME = name
        self.exe(f"local s = W.spells[NAME]; s.cdStart = W.now - ({total} - {remaining}); s.cdDur = {total}; s.gcd = false")

    def clear_cooldown(self, name):
        self.lua.globals().NAME = name
        self.exe("local s = W.spells[NAME]; s.cdStart, s.cdDur, s.gcd = 0, 0, false")

    def gcd(self, name, on=True):
        self.lua.globals().NAME = name
        if on:
            self.exe("local s = W.spells[NAME]; s.cdStart = W.now; s.cdDur = 1.5; s.gcd = true")
        else:
            self.clear_cooldown(name)

    def set_buffs(self, buffs):
        """buffs: list of (name, remaining_seconds_or_None, total_or_None[, source])"""
        self.exe("W.buffs = {}")
        for i, b in enumerate(buffs, 1):
            name, rem, total = b[0], b[1], b[2]
            src = b[3] if len(b) > 3 else "player"
            self.lua.globals().BN, self.lua.globals().BS = name, src
            exp = f"W.now + {rem}" if rem else "0"
            self.exe(f'W.buffs[{i}] = {{ name = BN, icon = 7000 + {i}, duration = {total or 0}, expires = {exp}, source = BS }}')

    def set_equip(self, main=None, off=None, ranged=None, unknown=()):
        """Each is an itemEquipLoc string (or None for an empty slot). `unknown` lists slots whose item data is not available."""
        self.exe("W.equip = {}")
        for slot, loc in ((16, main), (17, off), (18, ranged)):
            if loc is None:
                continue
            self.exe(f"W.equip[{slot}] = {9000 + slot}")
            if slot not in unknown:
                self.lua.globals().LOC = loc
                self.exe(f"W.items[{9000 + slot}] = {{ loc = LOC }}")
            else:
                self.exe(f"W.items[{9000 + slot}] = nil")

    def set_totem(self, slot, name, remaining, total):
        self.lua.globals().TN = name
        self.exe(f"W.totems[{slot}] = {{ name = TN, start = W.now - ({total} - {remaining}), dur = {total}, icon = 6000 + {slot} }}")

    def clear_totem(self, slot):
        self.exe(f"W.totems[{slot}] = nil")

    def set_enchant(self, hand, ms):
        self.exe(f'W.enchant["{hand}"] = {{ ms = {ms} }}' if ms is not None else f'W.enchant["{hand}"] = nil')

    def combat(self, on, secrets=("cd", "auras", "totems", "enchant")):
        """Enter/leave combat. While in combat the listed APIs return secret values (restricted)."""
        self.exe(f"W.combat = {str(on).lower()}")
        flags = {"cd": "secretCd", "totems": "secretTotems", "enchant": "secretEnchant", "equip": "secretEquip", "unit": "secretUnit"}
        for k, lua_name in flags.items():
            self.exe(f"W.{lua_name} = {str(bool(on and k in secrets)).lower()}")
        a = bool(on and "auras" in secrets)
        self.exe(f"W.secretAurasFlag = {str(a).lower()}; W.secretAuraValues = {str(a).lower()}")
        if not on:
            self.fire("PLAYER_REGEN_ENABLED")

    # ----------------------------------------------------------- driving the addon
    def _guard(self, fn, *a):
        try:
            return fn(*a)
        except LuaError as e:
            self.raised.append(str(e))

    def load(self):
        """Run the .toc file list in order (as the client does), with the addon name as `...`."""
        toc = os.path.join(ROOT, ADDON + ".toc")
        files = [ln.strip() for ln in open(toc, encoding="utf-8") if ln.strip() and not ln.startswith("#")]
        self.files = files
        mk = self.lua.eval("function(src, name) local f, e = loadstring(src, '=' .. name); if not f then error(e) end return f end")
        for fn in files:
            path = self.lua_path if fn == ADDON + ".lua" else os.path.join(ROOT, fn)
            src = open(path, encoding="utf-8").read()
            chunk = mk(src, fn)
            self._guard(chunk, ADDON, self.lua.table())

    def fire(self, event, *args):
        return self._guard(self.lua.globals().FIRE, event, *args)

    def tick(self, dt=0.2, n=1):
        for _ in range(n):
            self._guard(self.lua.globals().TICK, dt)

    def login(self):
        """ADDON_LOADED for another addon (must be ignored), then ours, then PLAYER_LOGIN / ENTERING_WORLD, then a tick."""
        self.fire("ADDON_LOADED", "Blizzard_SomethingElse")
        self.fire("ADDON_LOADED", ADDON)
        self.fire("PLAYER_LOGIN")
        self.fire("PLAYER_ENTERING_WORLD")
        self.tick(0.2)

    def boot(self, spells=(), **kw):
        self.load()
        for s in spells:
            self.add_spell(s)
        self.login()
        return self

    def slash(self, msg):
        self.printed_before = len(self.printed)
        return self._guard(self.lua.eval("function(m) SlashCmdList['SPELLCDTRACKER'](m) end"), msg)

    def new_output(self):
        return self.printed[getattr(self, "printed_before", 0):]

    def cast(self, name, unit="player"):
        self.lua.globals().NAME = name
        sid = self.ev("(W.spells[NAME] or {}).id")
        self.fire("UNIT_SPELLCAST_SUCCEEDED", unit, "castguid", sid)

    def cast_secret(self):
        self._guard(self.lua.eval("function() FIRE('UNIT_SPELLCAST_SUCCEEDED', 'player', 'guid', Secret()) end"))

    # ----------------------------------------------------------- inspection
    def errors(self):
        """Lua errors that escaped to the client plus the addon's own Guard() error prints."""
        return list(self.raised) + [p for p in self.printed if ERR_MARK in p]

    def db(self):
        return _to_py(self.ev("SpellCDTrackerDB"))

    def icons(self, frame="SpellCDTrackerCDFrame"):
        """Shown icons (in order) of a row frame: dicts with tex, desat, alpha, text, border, cdObj, cdStart, cdDur."""
        self.lua.globals().FN = frame
        res = self.ev("""(function()
          local f = _G[FN]; local out = {}
          for i, ic in ipairs(f.icons or {}) do
            if ic._shown then
              out[#out + 1] = { i = i, tex = ic.icon._tex, color = ic.icon._color, desat = ic.icon._desat or false, alpha = ic._alpha,
                                text = ic.text._text, tcolor = ic.text._tcolor, border = ic.border._color, obj = ic.cd._cdObj and ic.cd._cdObj.spell or nil,
                                cdStart = ic.cd._cdStart, cdDur = ic.cd._cdDur }
            end
          end
          return out end)()""")
        return _to_py(res) or []

    def icon_ids(self, frame="SpellCDTrackerCDFrame"):
        return [i["tex"] for i in self.icons(frame)]

    def icon_at(self, expr):
        """State of one icon frame addressed by a Lua expression, e.g. 'SpellCDTrackerPalaFrame.seal'."""
        self.lua.globals().EXPR = expr
        return _to_py(self.ev("""(function()
          local ic = loadstring('return ' .. EXPR)()
          return { shown = ic._shown, tex = ic.icon._tex, color = ic.icon._color, desat = ic.icon._desat or false, alpha = ic._alpha,
                   text = ic.text._text, border = ic.border._color, cdStart = ic.cd._cdStart, cdDur = ic.cd._cdDur } end)()"""))

    def click_check(self, label, state):
        """Click the options/spells-window check box whose label is `label` (sets its state, runs OnClick)."""
        self.lua.globals().LBL, self.lua.globals().ST = label, state
        ok = self.ev("""(function()
          for _, f in ipairs(CREATED) do
            if f._kind == "CheckButton" and f._fs and f._fs[1] and f._fs[1]._text == LBL then
              f._checked = ST; f._scripts.OnClick(f); return true
            end
          end
          return false end)()""")
        return ok

    def click_button(self, text):
        """Click the Button whose text is `text` (spells window / options)."""
        self.lua.globals().LBL = text
        return self.ev("""(function()
          for _, f in ipairs(CREATED) do
            if f._kind == "Button" and f._text == LBL and f._scripts.OnClick then f._scripts.OnClick(f); return true end
          end
          return false end)()""")

    def click_row(self, spell, which, state):
        """Tracked-spells window: tick `which` ('check' = track, 'pin' = show when ready) of the row for `spell`."""
        self.lua.globals().SP, self.lua.globals().WH, self.lua.globals().ST = spell, which, state
        return self.ev("""(function()
          local w = SpellCDTrackerSpells
          for i = 1, 12 do
            if w.rowSpell[i] == SP then
              local b = w.rows[i][WH]; b._checked = ST; b._scripts.OnClick(b); return true
            end
          end
          return false end)()""")

    def row_state(self, spell, which):
        self.lua.globals().SP, self.lua.globals().WH = spell, which
        return self.ev("""(function()
          local w = SpellCDTrackerSpells
          for i = 1, 12 do if w.rowSpell[i] == SP then return w.rows[i][WH]._checked end end
          return nil end)()""")

    def spell_icon(self, name):
        self.lua.globals().NAME = name
        return self.ev("W.spells[NAME].icon")

    def pos(self, frame_name):
        self.lua.globals().FN = frame_name
        return _to_py(self.ev("(function() local f = _G[FN]; local p = f._pt; return p end)()"))

    def mm(self):
        return self.ev("SpellCDTrackerMinimapButton")

    def mm_offset(self):
        p = self.ev("SpellCDTrackerMinimapButton._pt")
        return (p[4], p[5])


class Checker:
    def __init__(self, name):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.xfail = 0
        self.xpass = 0

    def check(self, label, cond, detail=""):
        if cond:
            self.passed += 1
            print("PASS " + label)
        else:
            self.failed += 1
            print("FAIL " + label + (("  [" + str(detail) + "]") if detail != "" else ""))

    def known_bug(self, label, desired_behaviour_holds, why):
        """A test of DESIRED behaviour that currently fails because of a bug in the addon. XFAIL does not fail the suite;
        if it starts passing it prints XPASS so the marker can be removed."""
        if desired_behaviour_holds:
            self.xpass += 1
            print("XPASS " + label + "  (bug appears fixed: turn this into a normal check)")
        else:
            self.xfail += 1
            print("XFAIL " + label + "  [known bug: " + why + "]")

    def info(self, text):
        print("INFO " + text)

    def finish(self):
        print(f"RESULT {self.name}: {self.passed} passed, {self.failed} failed, {self.xfail} xfail, {self.xpass} xpass")
        sys.exit(1 if self.failed else 0)
