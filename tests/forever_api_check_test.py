"""Checks the mocks (and the addon's API use) against the Forever UI source: names, namespaces, argument and return names,
secret flags, and the things Forever does NOT have. Needs the source (git clone --depth 1 --branch forever
https://github.com/Gethe/wow-ui-source). Set FOREVER_UI to its path; default /tmp/claude-0/forever-ui/wow-ui-source.
Without the source this file prints SKIP and exits 0 (it can not confirm anything)."""
import os
import re
import sys
from mock_env import Client, Checker, ROOT

t = Checker("forever_api_check_test")
SRC = os.environ.get("FOREVER_UI", "/tmp/claude-0/forever-ui/wow-ui-source")
DOCS = os.path.join(SRC, "Interface", "AddOns", "Blizzard_APIDocumentationGenerated")
if not os.path.isdir(DOCS):
    print(f"SKIP Forever UI source not found at {SRC}; nothing was verified against it")
    print("RESULT forever_api_check_test: 0 passed, 0 failed, 0 xfail, 0 xpass (skipped)")
    sys.exit(0)

print("INFO Forever UI source version:", open(os.path.join(SRC, "version.txt")).read().strip() if os.path.exists(os.path.join(SRC, "version.txt")) else "unknown")

texts = {}
for fn in os.listdir(DOCS):
    if fn.endswith("Documentation.lua"):
        texts[fn] = open(os.path.join(DOCS, fn), encoding="utf-8", errors="replace").read()

def namespace(text):
    m = re.search(r'Namespace = "([^"]+)"', text)
    return m.group(1) if m else None

# (namespace or None) -> {function name: (block text)}
FUNCS = {}
for fn, text in texts.items():
    ns = namespace(text)
    for m in re.finditer(r'\n\t\t\{\n\t\t\tName = "(\w+)",\n\t\t\tType = "Function",', text):
        nxt = text.find("\n\t\t{\n\t\t\tName =", m.end())
        block = text[m.start(): nxt if nxt != -1 else len(text)]
        FUNCS.setdefault((ns, m.group(1)), (fn, block))

def names_in(section):
    return re.findall(r'Name = "(\w+)"', section)

def sig(ns, name):
    fn, block = FUNCS[(ns, name)]
    a = block.find("\n\t\t\tArguments =")
    r = block.find("\n\t\t\tReturns =")
    args = names_in(block[a:r if r > a else len(block)]) if a != -1 else []
    rets = names_in(block[r:]) if r != -1 else []
    return fn, args, rets, block

EXPECT = [
    # ns, name, args, first returns, flags that must appear in the block
    ("C_Spell", "GetSpellCooldown", ["spellIdentifier"], ["spellCooldownInfo"], ["SecretWhenCooldownsRestricted"]),
    ("C_Spell", "GetSpellCooldownDuration", ["spellIdentifier", "ignoreGCD"], ["duration"], []),
    ("C_Spell", "GetSpellName", ["spellIdentifier"], ["name"], []),
    ("C_Spell", "GetSpellTexture", ["spellIdentifier"], None, []),
    ("C_Spell", "GetSpellDescription", ["spellIdentifier"], ["description"], []),
    ("C_SpellBook", "GetNumSpellBookSkillLines", [], None, []),
    ("C_SpellBook", "GetSpellBookSkillLineInfo", None, ["skillLineInfo"], []),
    ("C_SpellBook", "GetSpellBookItemInfo", ["spellBookItemSlotIndex", "spellBookItemSpellBank"], ["spellBookItemInfo"], []),
    ("C_UnitAuras", "GetAuraDataByIndex", ["unit", "index", "filter"], ["aura"], ["SecretWhenUnitAuraRestricted"]),
    ("C_Secrets", "ShouldAurasBeSecret", [], ["hasSecretAuras"], []),
    ("C_Item", "GetItemInfoInstant", ["itemInfo"], ["itemID", "itemType", "itemSubType", "itemEquipLoc"], []),
    ("C_Item", "GetWeaponEnchantInfo", ["weaponSlot"], ["enchants"], []),
    (None, "GetTotemInfo", ["slot"], ["haveTotem", "totemName", "startTime", "duration", "icon"], ["SecretWhenTotemSlotSecret"]),
    (None, "issecretvalue", ["value"], None, []),
    ("C_PaperDollInfo", "OffhandHasWeapon", [], None, []),
    ("C_SpecializationInfo", "GetSpecialization", ["isInspect", "isPet", "specGroupIndex"], ["specializationIndex"], []),
    (None, "UnitExists", None, None, []),
    (None, "UnitIsUnit", None, None, []),
    (None, "UnitAffectingCombat", None, None, []),
    (None, "UnitClass", None, ["className", "classFilename", "classID"], []),
]
for ns, name, args, rets, flags in EXPECT:
    label = f"{ns + '.' if ns else ''}{name}"
    if (ns, name) not in FUNCS:
        t.check(f"Forever documents {label}", False, "not found")
        continue
    fn, a, r, block = sig(ns, name)
    t.check(f"Forever documents {label} ({fn})", True)
    if args is not None:
        t.check(f"{label} arguments are {args}", a == args, a)
    if rets is not None:
        t.check(f"{label} returns start with {rets}", r[:len(rets)] == rets, r)
    for f in flags:
        t.check(f"{label} carries {f}", f in block)

# Cooldown widget methods (not a namespace: widget API docs)
cd = texts["FrameAPICooldownDocumentation.lua"]
for meth, argn in [("SetCooldown", ["start", "duration", "modRate"]), ("SetCooldownFromDurationObject", ["duration", "clearIfZero"]), ("Clear", []),
                   ("SetHideCountdownNumbers", None), ("SetDrawEdge", None)]:
    m = re.search(r'Name = "%s",\n\t\t\tType = "Function",' % meth, cd)
    t.check(f"Cooldown:{meth} exists", m is not None)
    if m and argn is not None:
        nxt = cd.find("\n\t\t{\n\t\t\tName =", m.end())
        blk = cd[m.start(): nxt if nxt != -1 else len(cd)]
        a = blk.find("\n\t\t\tArguments =")
        got = names_in(blk[a:]) if a != -1 else []
        t.check(f"Cooldown:{meth} arguments are {argn}", got == argn, got)

# structures and enums the mock returns
shared = texts["SpellSharedDocumentation.lua"]
m = re.search(r'Name = "SpellCooldownInfo",.*?\n\t\t\},\n', shared, re.S)
fields = names_in(m.group(0)) if m else []
t.check("SpellCooldownInfo has startTime, duration, isEnabled, isActive, modRate, isOnGCD (what the mock returns)",
        all(f in fields for f in ["startTime", "duration", "isEnabled", "isActive", "modRate", "isOnGCD"]), fields)
for f in ["isActive", "isOnGCD", "isEnabled"]:
    line = [l for l in shared.splitlines() if f'Name = "{f}"' in l and "NeverSecret" in l]
    t.check(f"SpellCooldownInfo.{f} is NeverSecret (the mock keeps it plain in combat)", len(line) > 0)
for f in ["startTime", "duration"]:
    line = [l for l in shared.splitlines() if f'Name = "{f}",' in l and "Seconds" not in l and "Type = \"number\"" in l]
    t.check(f"SpellCooldownInfo.{f} is not marked NeverSecret (secret when restricted)", len(line) > 0 and all("NeverSecret" not in l for l in line))
sb = texts["SpellBookDocumentation.lua"]
for f in ["spellID", "itemType", "name", "iconID", "isPassive", "isOffSpec"]:
    t.check(f"SpellBookItemInfo.{f} exists", re.search(r'Name = "SpellBookItemInfo".*?Name = "%s"' % f, sb, re.S) is not None)
for f in ["itemIndexOffset", "numSpellBookItems"]:
    t.check(f"SpellBookSkillLineInfo.{f} exists", re.search(r'Name = "SpellBookSkillLineInfo".*?Name = "%s"' % f, sb, re.S) is not None)
consts = texts["SpellBookConstantsDocumentation.lua"]
t.check("Enum.SpellBookSpellBank Player=0, Pet=1", re.search(r'Name = "Player".*?EnumValue = 0', consts, re.S) and re.search(r'Name = "Pet".*?EnumValue = 1', consts, re.S) is not None)
t.check("Enum.SpellBookItemType Spell=1", re.search(r'Name = "Spell", Type = "SpellBookItemType", EnumValue = 1', consts) is not None)

# the mock's own surface matches
c = Client("PALADIN")
for ns, name, *_ in EXPECT:
    if ns in ("C_Spell", "C_SpellBook", "C_UnitAuras", "C_Secrets", "C_Item", "C_PaperDollInfo"):
        t.check(f"mock defines {ns}.{name}", c.ev(f"type({ns}.{name})") == "function")
for g in ["GetTotemInfo", "issecretvalue", "UnitExists", "UnitIsUnit", "UnitAffectingCombat", "UnitClass", "InCombatLockdown", "GetTime", "CreateFrame"]:
    t.check(f"mock defines {g}", c.ev(f"type({g})") == "function")

# the weapon-enchant shim layout the mock reproduces
dep = open(os.path.join(SRC, "Interface/AddOns/Blizzard_Deprecated/Shared/Deprecated_12_1_0.lua"), encoding="utf-8").read()
m = re.search(r"function GetWeaponEnchantInfo\(\).*?\nend", dep, re.S)
shim = m.group(0) if m else ""
t.check("global GetWeaponEnchantInfo is a deprecated shim, only defined when loadDeprecationFallbacks is on",
        shim != "" and 'if not GetCVarBool("loadDeprecationFallbacks") then' in dep.split("function GetWeaponEnchantInfo")[0])
t.check("shim layout: 4 values per slot (has, remainingTimeMs, charges, enchantID) for main, off, ranged -> the addon's indexes 2/3 and 6/7 are right",
        all(s in shim for s in ["values[offset] = true", "remainingTimeMs", "chargesRemaining", "enchantID", "offset = offset + 4", "INVSLOT_MAINHAND, INVSLOT_OFFHAND, INVSLOT_RANGED"]))

# things Forever does not have (so the mock must not either)
def grep_all(pattern, exts=(".lua", ".xml")):
    hits = []
    rx = re.compile(pattern)
    for root, _, files in os.walk(os.path.join(SRC, "Interface")):
        for f in files:
            if f.endswith(exts):
                try:
                    for i, line in enumerate(open(os.path.join(root, f), encoding="utf-8", errors="replace"), 1):
                        if rx.search(line):
                            hits.append(f"{os.path.relpath(os.path.join(root, f), SRC)}:{i}")
                except OSError:
                    pass
    return hits
t.check("GetMinimapShape is not defined or used anywhere in the Forever UI source", grep_all(r"GetMinimapShape") == [], grep_all(r"GetMinimapShape")[:3])
t.check("C_Console namespace is not documented", not any(namespace(x) == "C_Console" for x in texts.values()))
t.check("no function named issecret is documented (only issecretvalue)", not any(n == "issecret" for (_, n) in FUNCS))
t.check("global OffhandHasWeapon is not defined anywhere (only C_PaperDollInfo.OffhandHasWeapon is documented)",
        grep_all(r"^\s*(function\s+OffhandHasWeapon|OffhandHasWeapon\s*=)") == [] and ("C_PaperDollInfo", "OffhandHasWeapon") in FUNCS)
spec_defs = grep_all(r"^\s*GetSpecialization\s*=|function\s+GetSpecialization\b")
t.check("global GetSpecialization exists only as the deprecated Standard-game-type shim", len(spec_defs) == 1 and "Deprecated_Specialization_Standard.lua" in spec_defs[0], spec_defs)
unitbuff = grep_all(r"^\s*UnitBuff\s*=|function\s+UnitBuff\b")
t.check("UnitBuff exists only in Blizzard_Deprecated shims", unitbuff != [] and all("Blizzard_Deprecated" in h for h in unitbuff), unitbuff)

# every C_Namespace.Function the addon references is documented in Forever
src = open(os.path.join(ROOT, "SpellCDTracker.lua"), encoding="utf-8").read()
refs = sorted(set(re.findall(r"\b(C_[A-Za-z]+)\.([A-Za-z]+)", src)))
documented = {(ns, n) for (ns, n) in FUNCS}
ALLOWED_UNDOCUMENTED = set()
for ns, n in refs:
    if (ns, n) in ALLOWED_UNDOCUMENTED:
        continue
    t.check(f"addon reference {ns}.{n} is documented in Forever", (ns, n) in documented)
t.check("addon never references C_Console", "C_Console" not in src)
t.check("addon asks for issecretvalue (not the retail-less 'issecret' global)", "issecretvalue" in src and not re.search(r"(?<![\w.])issecret\s*=\s*_G\.issecret\b", src))
globals_used = sorted(set(re.findall(r"(?<![\w.])(GetSpellCooldown|GetSpellInfo|UnitBuff|GetMinimapShape|GetSpecialization|OffhandHasWeapon|GetWeaponEnchantInfo|issecretvalue)\b", src)))
t.info("retail-or-deprecated globals the addon touches (all behind an existence check): " + ", ".join(globals_used))

t.finish()
