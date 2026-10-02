-- Spell Cooldown Tracker (folder and saved variables keep the name SpellCDTracker)
-- 1) Cooldown row: an icon appears only while a spell is on cooldown.
-- 2) Paladin panel: Seal countdown, Aura on/off indicators, "my Blessing on me" check.
-- 3) Minimap button + options window (sizes, lock, reset).
--
-- Combat note: in Forever, aura reads throw and cooldown numbers are "secret values" while in
-- combat. Cooldowns are handed to the Cooldown widget as duration objects; the Paladin panel
-- keeps its last known state and updates it from your own spell casts.

local ADDON = ...

local defaults = {
    cdSize = 40,
    palaSize = 40,
    textScale = 100,      -- percent
    minimapAngle = 200,
    minimapHide = false,
    swingCombatOnly = true,   -- hide Forever's built-in swing timer bars out of combat
    cd   = { point = "CENTER", relPoint = "CENTER", x = 0, y = -150 },
    pala = { point = "CENTER", relPoint = "CENTER", x = 0, y = -215 },
    ignore = {},          -- legacy global list; copied into each new class/spec profile
    profiles = {},        -- "CLASS" or "CLASS:spec" -> { ignore = {...}, seal/blessing/rf/auras = false to hide }
    spellCache = {},      -- CLASS -> sorted { {name, icon}, ... } snapshot of spells seen on that class
    lastSpec = {},        -- CLASS -> last tab viewed in Tracked spells
    buff = { point = "CENTER", relPoint = "CENTER", x = 0, y = -215 },
    pbuff = { point = "CENTER", relPoint = "CENTER", x = 0, y = -280 },   -- Paladin active-buff row
    buffIcons = {},       -- buff group key -> last seen icon
    durations = {},       -- aura name -> last seen duration (for combat timers)
}

local db
local known = {}          -- spell name -> { name, id, icon, slot, ...cache }
local dirty = true        -- rescan spells on next tick
local editMode = false    -- frames can only be dragged in edit mode (never saved; always starts off)
local editHook            -- set by the options window to refresh its button
local className, playerClass = UnitClass("player")
local isPaladin = (playerClass == "PALADIN")

local GAP = 4
local MIN_CD = 2          -- ignore anything at or under the global cooldown
local FONT = "Fonts\\FRIZQT__.TTF"

local issecret = issecretvalue or function() return false end

local PALADIN_AURAS = {
    "Devotion Aura", "Retribution Aura", "Concentration Aura", "Sanctity Aura",
    "Fire Resistance Aura", "Frost Resistance Aura", "Shadow Resistance Aura", "Crusader Aura",
}

-- print each distinct error only once
local seenErr = {}
local function Guard(fn, ...)
    local ok, err = pcall(fn, ...)
    if not ok then
        err = tostring(err)
        if not seenErr[err] then
            seenErr[err] = true
            print("|cffff5555Spell Cooldown Tracker error:|r " .. err)
        end
    end
    return ok
end

local function InCombat()
    return InCombatLockdown and InCombatLockdown()
end

------------------------------------------------------------------------
-- per class/spec profiles
--   db.profiles["PALADIN"]   = class-wide settings ("All specs")
--   db.profiles["PALADIN:2"] = settings for one spec; only exists once you change something for it
-- A spec without its own profile uses the class-wide one.
------------------------------------------------------------------------
local currentProf, profileKey, profileLabel, profileHook
local EMPTY_PROF = { ignore = {} }   -- read-only placeholder, never modified

local CLASS_ORDER = { "WARRIOR", "PALADIN", "HUNTER", "ROGUE", "PRIEST", "SHAMAN", "MAGE", "WARLOCK", "DRUID" }
-- display names for classes other than the one you are playing; your own class uses the game's names
local SPEC_NAMES = {
    WARRIOR = { "Arms", "Fury", "Protection" },
    PALADIN = { "Holy", "Protection", "Retribution" },
    HUNTER  = { "Beast Mastery", "Marksmanship", "Survival" },
    ROGUE   = { "Assassination", "Combat", "Subtlety" },
    PRIEST  = { "Discipline", "Holy", "Shadow" },
    SHAMAN  = { "Elemental", "Enhancement", "Restoration" },
    MAGE    = { "Arcane", "Fire", "Frost" },
    WARLOCK = { "Affliction", "Demonology", "Destruction" },
    DRUID   = { "Balance", "Feral Combat", "Restoration" },
}

local function ClassName(key)
    return (LOCALIZED_CLASS_NAMES_MALE and LOCALIZED_CLASS_NAMES_MALE[key])
        or (key:sub(1, 1) .. key:sub(2):lower())
end

local function ClassColor(key)
    local c = RAID_CLASS_COLORS and RAID_CLASS_COLORS[key]
    if c then return c.r, c.g, c.b end
    return 1, 0.82, 0
end

-- spec index (1-3) if the client reports one, otherwise nil
local function DetectSpecIndex()
    if GetSpecialization then
        local ok, idx = pcall(GetSpecialization)
        if ok and type(idx) == "number" and idx >= 1 and idx <= 3 then return idx end
    end
end

local function SpecName(class, idx)
    if class == playerClass and GetSpecializationInfo then
        local ok, _, name = pcall(GetSpecializationInfo, idx)
        if ok and type(name) == "string" and name ~= "" then return name end
    end
    local t = SPEC_NAMES[class]
    return (t and t[idx]) or ("Spec " .. idx)
end

-- returns profile, exists. With create=true a missing profile is made (a spec profile starts as
-- a copy of the class-wide one); with create=false a missing spec profile falls back to class-wide.
local function ProfileFor(class, spec, create)
    local base = db.profiles[class]
    if not base and (create or spec) then
        if create then
            base = { ignore = CopyTable(db.ignore or {}) }
            db.profiles[class] = base
        end
    end
    if not spec then
        return base or EMPTY_PROF, base ~= nil
    end
    local key = class .. ":" .. spec
    local p = db.profiles[key]
    if p then return p, true end
    if not create then return base or EMPTY_PROF, false end
    p = CopyTable(base)
    p.ignore = p.ignore or {}
    db.profiles[key] = p
    return p, true
end

local function RefreshProfile()
    local spec = DetectSpecIndex()
    local key = playerClass
    if spec and db.profiles[playerClass .. ":" .. spec] then key = playerClass .. ":" .. spec end
    local prof = ProfileFor(playerClass, nil, true)      -- the class-wide profile always exists
    if key ~= playerClass then prof = db.profiles[key] end
    prof.ignore = prof.ignore or {}
    profileLabel = (className or playerClass) .. " - " .. (key == playerClass and "All specs" or SpecName(playerClass, spec))
    if key == profileKey and currentProf == prof then return end
    profileKey, currentProf = key, prof
    if profileHook then profileHook() end
end

------------------------------------------------------------------------
-- helpers
------------------------------------------------------------------------
local function FormatTime(t)
    if t >= 3600 then return string.format("%dh", math.ceil(t / 3600))
    elseif t >= 60 then return string.format("%dm", math.ceil(t / 60))
    elseif t >= 10 then return string.format("%d", math.floor(t))
    else return string.format("%.1f", t) end
end

local function StyleIcon(f, size)
    local scale = (db.textScale or 100) / 100
    local key = size * scale
    if f.styleKey == key then return end
    f.styleKey = key
    f.text:SetFont(FONT, math.max(8, math.floor(size * 0.38 * scale)), "OUTLINE")
    f.label:SetFont(FONT, math.max(7, math.floor(size * 0.22 * scale)), "OUTLINE")
end

local function CreateIcon(parent)
    local f = CreateFrame("Frame", nil, parent)
    f:SetSize(40, 40)

    f.border = f:CreateTexture(nil, "BACKGROUND")
    f.border:SetPoint("TOPLEFT", -2, 2)
    f.border:SetPoint("BOTTOMRIGHT", 2, -2)
    f.border:SetColorTexture(0, 0, 0, 1)

    f.icon = f:CreateTexture(nil, "ARTWORK")
    f.icon:SetAllPoints()
    f.icon:SetTexCoord(0.07, 0.93, 0.07, 0.93)

    f.cd = CreateFrame("Cooldown", nil, f, "CooldownFrameTemplate")
    f.cd:SetAllPoints()
    if f.cd.SetHideCountdownNumbers then f.cd:SetHideCountdownNumbers(true) end
    if f.cd.SetDrawEdge then f.cd:SetDrawEdge(false) end

    f.overlay = CreateFrame("Frame", nil, f)
    f.overlay:SetAllPoints()
    f.overlay:SetFrameLevel(f.cd:GetFrameLevel() + 2)

    f.text = f.overlay:CreateFontString(nil, "OVERLAY")
    f.text:SetFont(FONT, 14, "OUTLINE")
    f.text:SetPoint("CENTER")

    f.label = f.overlay:CreateFontString(nil, "OVERLAY")
    f.label:SetFont(FONT, 9, "OUTLINE")
    f.label:SetPoint("TOP", f, "BOTTOM", 0, -3)

    f:Hide()
    return f
end

local function SetBorder(f, r, g, b)
    f.border:SetColorTexture(r, g, b, 1)
end

local function MakeMovable(frame, key)
    frame:SetMovable(true)
    frame:SetClampedToScreen(true)
    frame:RegisterForDrag("LeftButton")
    frame:SetScript("OnDragStart", function(self) self:StartMoving() end)
    frame:SetScript("OnDragStop", function(self)
        self:StopMovingOrSizing()
        local point, _, relPoint, x, y = self:GetPoint(1)
        db[key].point, db[key].relPoint, db[key].x, db[key].y = point, relPoint, x, y
    end)

    frame.bg = frame:CreateTexture(nil, "BACKGROUND")
    frame.bg:SetAllPoints()
    frame.bg:SetColorTexture(0, 1, 0, 0.25)
    frame.bg:Hide()

    frame.title = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    frame.title:SetPoint("BOTTOM", frame, "TOP", 0, 2)
    frame.title:Hide()
end

local function ApplyPosition(frame, key)
    local p = db[key]
    frame:ClearAllPoints()
    frame:SetPoint(p.point, UIParent, p.relPoint, p.x, p.y)
end

local function ApplyLock()
    for _, f in ipairs({ SpellCDTrackerCDFrame, SpellCDTrackerPalaFrame, SpellCDTrackerBuffFrame }) do
        if f then
            f:EnableMouse(editMode)      -- clicks pass straight through when not editing
            f.bg:SetShown(editMode)
            f.title:SetShown(editMode)
        end
    end
end

local function SetEditMode(on)
    editMode = on and true or false
    ApplyLock()
    if editHook then editHook() end
end

------------------------------------------------------------------------
-- data access (supports both modern C_ APIs and older global ones)
------------------------------------------------------------------------
local function SpellNameByID(id)
    if C_Spell and C_Spell.GetSpellName then return C_Spell.GetSpellName(id) end
    if GetSpellInfo then return (GetSpellInfo(id)) end
end

local function SpellIconByID(id)
    if C_Spell and C_Spell.GetSpellTexture then return C_Spell.GetSpellTexture(id) end
    if GetSpellTexture then return GetSpellTexture(id) end
end

local function ScanSpells()
    local old = known
    known = {}

    -- 1) spellbook
    if C_SpellBook and C_SpellBook.GetNumSpellBookSkillLines then
        for line = 1, C_SpellBook.GetNumSpellBookSkillLines() do
            local li = C_SpellBook.GetSpellBookSkillLineInfo(line)
            if li then
                for slot = li.itemIndexOffset + 1, li.itemIndexOffset + li.numSpellBookItems do
                    local it = C_SpellBook.GetSpellBookItemInfo(slot, Enum.SpellBookSpellBank.Player)
                    if it and it.itemType == Enum.SpellBookItemType.Spell and it.spellID
                        and not it.isPassive and not it.isOffSpec then
                        local name = it.name or SpellNameByID(it.spellID)
                        if name then
                            known[name] = { name = name, id = it.spellID, icon = it.iconID, slot = slot }
                        end
                    end
                end
            end
        end
    elseif GetNumSpellTabs then
        for tab = 1, GetNumSpellTabs() do
            local _, _, offset, num = GetSpellTabInfo(tab)
            for i = offset + 1, offset + num do
                local kind, id = GetSpellBookItemInfo(i, "spell")
                if kind == "SPELL" and not IsPassiveSpell(i, "spell") then
                    local name = GetSpellBookItemName(i, "spell")
                    if name then
                        known[name] = { name = name, id = id, icon = GetSpellTexture(i, "spell"), slot = i }
                    end
                end
            end
        end
    end

    -- 2) action bars (catches anything the spellbook scan missed)
    if GetActionInfo then
        for slot = 1, 180 do
            local kind, id = GetActionInfo(slot)
            if kind == "spell" and id and not issecret(id) then
                local name = SpellNameByID(id)
                if name and not known[name] then
                    known[name] = { name = name, id = id, icon = SpellIconByID(id) }
                end
            end
        end
    end

    -- keep per-spell cooldown cache across rescans
    for name, s in pairs(known) do
        local o = old[name]
        if o then
            s.cStart, s.cEnd, s.seenAt, s.onGCD, s.gen = o.cStart, o.cEnd, o.seenAt, o.onGCD, o.gen
        end
    end

    -- snapshot for the Tracked spells window (so other classes can be browsed from alts)
    if db and playerClass and next(known) then
        local list = {}
        for name, s in pairs(known) do list[#list + 1] = { name = name, icon = s.icon } end
        table.sort(list, function(x, y) return x.name < y.name end)
        db.spellCache = db.spellCache or {}
        db.spellCache[playerClass] = list
        if profileHook then profileHook() end
    end
end

------------------------------------------------------------------------
-- cooldown reading (secret-value safe)
--   returns "none"
--        or "known",  start, duration   (numbers we may read and do math on)
--        or "secret"                    (active, but numbers are hidden; use duration object)
------------------------------------------------------------------------
local function ReadCooldown(s)
    local start, dur, active
    if C_Spell and C_Spell.GetSpellCooldown then
        local info = C_Spell.GetSpellCooldown(s.name) or C_Spell.GetSpellCooldown(s.id)
        if not info then s.cEnd = nil; return "none" end
        start, dur, active = info.startTime, info.duration, info.isActive
    elseif GetSpellCooldown then
        start, dur = GetSpellCooldown(s.name)
    else
        return "none"
    end

    if not (issecret(start) or issecret(dur)) then
        if start and dur and start > 0 and dur > MIN_CD then
            s.cStart, s.cEnd = start, start + dur
            return "known", start, dur
        end
        s.cEnd = nil
        return "none"
    end

    -- numbers are hidden. A cooldown we saw start earlier is still readable from our cache.
    local now = GetTime()
    if s.cEnd and s.cEnd > now and active ~= false then
        return "known", s.cStart, s.cEnd - s.cStart
    end
    if active and not s.onGCD then return "secret" end
    return "none"
end

local function GetDurationObject(s)
    if not (C_Spell and C_Spell.GetSpellCooldownDuration) then return nil end
    local ok, obj = pcall(C_Spell.GetSpellCooldownDuration, s.id)
    if ok and obj then return obj end
    ok, obj = pcall(C_Spell.GetSpellCooldownDuration, s.name)
    if ok then return obj end
end

local function UpdateGCDFlags()
    if not (C_Spell and C_Spell.GetSpellCooldown) then return end
    for _, s in pairs(known) do
        local info = C_Spell.GetSpellCooldown(s.name)
        s.onGCD = (info and info.isOnGCD) and true or false
        s.gen = (s.gen or 0) + 1
    end
end

------------------------------------------------------------------------
-- cooldown row
------------------------------------------------------------------------
local cdFrame = CreateFrame("Frame", "SpellCDTrackerCDFrame", UIParent)
cdFrame.icons = {}

local function UpdateCooldowns()
    local now = GetTime()
    local active = {}
    local ignore = (currentProf and currentProf.ignore) or {}
    for name, s in pairs(known) do
        if not ignore[name:lower()] then
            local kind, start, dur = ReadCooldown(s)
            if kind == "known" then
                s.seenAt = s.seenAt or now
                active[#active + 1] = { s = s, kind = kind, start = start, dur = dur,
                                        rem = start + dur - now, order = s.seenAt }
            elseif kind == "secret" then
                s.seenAt = s.seenAt or now
                active[#active + 1] = { s = s, kind = kind, rem = math.huge, order = s.seenAt }
            else
                s.seenAt = nil
            end
        else
            s.seenAt = nil
        end
    end
    table.sort(active, function(a, b)
        if a.rem ~= b.rem then return a.rem < b.rem end
        return a.order < b.order
    end)

    local size = db.cdSize
    local n = math.min(#active, 16)
    local total = math.max(n, 3) * (size + GAP) - GAP
    cdFrame:SetSize(total, size)
    cdFrame.title:SetText("Cooldowns (drag to move)")

    for i = 1, n do
        local a = active[i]
        local ic = cdFrame.icons[i]
        if not ic then
            ic = CreateIcon(cdFrame)
            cdFrame.icons[i] = ic
        end
        ic:SetSize(size, size)
        StyleIcon(ic, size)
        ic:ClearAllPoints()
        local off = (i - 1) * (size + GAP) - (n * (size + GAP) - GAP) / 2 + size / 2
        ic:SetPoint("CENTER", cdFrame, "CENTER", off, 0)
        ic.icon:SetTexture(a.s.icon)

        if a.kind == "known" then
            ic.boundSpell = nil
            ic.cd:SetHideCountdownNumbers(true)
            ic.cd:SetCooldown(a.start, a.dur)
            ic.text:SetText(FormatTime(math.max(a.rem, 0)))
            if a.rem <= 3 then ic.text:SetTextColor(1, 0.3, 0.3) else ic.text:SetTextColor(1, 1, 1) end
        else
            -- numbers are hidden in combat: give the widget a duration object and let it draw
            ic.text:SetText("")
            if ic.cd.SetCooldownFromDurationObject then
                if ic.boundSpell ~= a.s.name or ic.boundGen ~= a.s.gen then
                    local obj = GetDurationObject(a.s)
                    if obj then Guard(ic.cd.SetCooldownFromDurationObject, ic.cd, obj) end
                    ic.boundSpell, ic.boundGen = a.s.name, a.s.gen
                end
                ic.cd:SetHideCountdownNumbers(false)
            end
        end
        SetBorder(ic, 0, 0, 0)
        ic:Show()
    end
    for i = n + 1, #cdFrame.icons do
        cdFrame.icons[i]:Hide()
        cdFrame.icons[i].boundSpell = nil
    end
end

------------------------------------------------------------------------
-- paladin panel
------------------------------------------------------------------------
local palaFrame
local QUESTION = "Interface\\Icons\\INV_Misc_QuestionMark"

-- last known state (aura reads are blocked in combat, so this is what we draw from)
local pstate = { seal = nil, blessing = nil, rf = nil, aura = nil }

local function AurasLocked()
    if C_Secrets and C_Secrets.ShouldAurasBeSecret then
        local ok, res = pcall(C_Secrets.ShouldAurasBeSecret)
        if ok then return res and true or false end
    end
    return false
end

local function GetPlayerBuffs()
    local out = {}
    if C_UnitAuras and C_UnitAuras.GetAuraDataByIndex then
        for i = 1, 40 do
            local d = C_UnitAuras.GetAuraDataByIndex("player", i, "HELPFUL")
            if not d then break end
            out[#out + 1] = { name = d.name, icon = d.icon, duration = d.duration,
                              expires = d.expirationTime, source = d.sourceUnit }
        end
    else
        for i = 1, 40 do
            local name, icon, _, _, duration, expires, source = UnitBuff("player", i)
            if not name then break end
            out[#out + 1] = { name = name, icon = icon, duration = duration, expires = expires, source = source }
        end
    end
    return out
end

local function IsMine(a)
    return a.source and UnitIsUnit(a.source, "player")
end

local function RefreshPaladinFromAuras()
    local buffs = GetPlayerBuffs()
    local seal, bless, rf, aura
    for _, a in ipairs(buffs) do
        local name = a.name
        if not seal and name:find("^Seal of") then
            seal = { name = name, icon = a.icon, duration = a.duration, expires = a.expires }
        elseif not bless and (name:find("^Blessing of") or name:find("^Greater Blessing of")) and IsMine(a) then
            bless = { name = name, icon = a.icon, duration = a.duration, expires = a.expires }
        elseif not rf and name == "Righteous Fury" and (IsMine(a) or not a.source) then
            rf = { name = name, icon = a.icon, duration = a.duration, expires = a.expires }
        elseif not aura and (IsMine(a) or not a.source) then
            for _, an in ipairs(PALADIN_AURAS) do
                if an == name then aura = name break end
            end
        end
    end
    if seal then db.lastSealIcon = seal.icon end
    if bless then db.lastBlessIcon = bless.icon end
    if rf then db.lastRFIcon = rf.icon end
    if seal and seal.duration and seal.duration > 0 then db.durations[seal.name] = seal.duration end
    if bless and bless.duration and bless.duration > 0 then db.durations[bless.name] = bless.duration end
    if rf and rf.duration and rf.duration > 0 then db.durations[rf.name] = rf.duration end
    pstate.seal, pstate.blessing, pstate.rf, pstate.aura = seal, bless, rf, aura
end

-- your own casts are still readable in combat: use them to keep Seal and Aura current
local function OnPlayerCast(spellID)
    if not isPaladin or not spellID or issecret(spellID) then return end
    local name = SpellNameByID(spellID)
    if not name then return end
    if name:find("^Seal of") then
        local d = db.durations[name]
        local icon = SpellIconByID(spellID)
        if icon then db.lastSealIcon = icon end
        pstate.seal = { name = name, icon = icon, duration = d,
                        expires = d and (GetTime() + d) or 0 }
    elseif name == "Righteous Fury" then
        -- lasts 30 min (from the spell tooltip); use the last seen duration if we have one
        local d = db.durations[name] or 1800
        local icon = SpellIconByID(spellID)
        if icon then db.lastRFIcon = icon end
        pstate.rf = { name = name, icon = icon, duration = d, expires = GetTime() + d }
    else
        for _, an in ipairs(PALADIN_AURAS) do
            if an == name then pstate.aura = name break end
        end
    end
end

local function BuildPaladin()
    palaFrame = CreateFrame("Frame", "SpellCDTrackerPalaFrame", UIParent)
    palaFrame.seal = CreateIcon(palaFrame)
    palaFrame.blessing = CreateIcon(palaFrame)
    palaFrame.rf = CreateIcon(palaFrame)
    palaFrame.auraIcons = {}
    for i, name in ipairs(PALADIN_AURAS) do
        palaFrame.auraIcons[i] = CreateIcon(palaFrame)
        palaFrame.auraIcons[i].auraName = name
    end
    palaFrame.warn = palaFrame:CreateFontString(nil, "OVERLAY")
    palaFrame.warn:SetFont(FONT, 14, "OUTLINE")
    palaFrame.warn:SetTextColor(1, 0.2, 0.2)
end

-- icon shown (dimmed) when a Seal/Blessing is missing: last one you used, else one you know
local function MissingIcon(prefix, preferred, cached)
    if cached then return cached end
    if preferred and known[preferred] and known[preferred].icon then return known[preferred].icon end
    local names = {}
    for name in pairs(known) do
        if name:find("^" .. prefix) then names[#names + 1] = name end
    end
    table.sort(names)
    if names[1] then return known[names[1]].icon end
end

local function ShowMissing(ic, icon, word)
    ic.cd:Clear()
    SetBorder(ic, 1, 0.1, 0.1)
    if icon then
        ic.icon:SetTexture(icon)
        ic.icon:SetDesaturated(true)
        ic:SetAlpha(0.55)
        ic.text:SetText("")
    else
        -- nothing to show yet: plain dark tile with the word instead of a question mark
        ic.icon:SetColorTexture(0.12, 0.12, 0.12, 1)
        ic.icon:SetDesaturated(false)
        ic:SetAlpha(1)
        ic.text:SetTextColor(1, 0.3, 0.3)
        ic.text:SetText(word)
    end
    ic.label:SetText("")
end

local function UpdatePaladin()
    if not palaFrame then return end
    local now = GetTime()
    local size = db.palaSize
    local prof = currentProf or {}

    if AurasLocked() then
        -- combat: keep last known state, let expired timers lapse
        for _, key in ipairs({ "seal", "blessing", "rf" }) do
            local a = pstate[key]
            if a and a.expires and a.expires > 0 and now > a.expires then pstate[key] = nil end
        end
    else
        Guard(RefreshPaladinFromAuras)   -- if blocked after all, cached state is kept
    end

    palaFrame.title:SetText("Paladin (drag to move)")

    local idx = 0
    local function place(ic)
        idx = idx + 1
        ic:SetSize(size, size)
        StyleIcon(ic, size)
        ic:ClearAllPoints()
        ic:SetPoint("LEFT", palaFrame, "LEFT", (idx - 1) * (size + GAP), 0)
        ic:SetAlpha(1)
        ic.text:SetTextColor(1, 1, 1)
        ic:Show()
    end

    -- a timed buff: active = icon + countdown, missing = dimmed icon with red border
    local function DrawBuff(ic, buff, prefix, preferred, cachedIcon, word, warnBelow)
        place(ic)
        ic.icon:SetDesaturated(false)
        if buff then
            ic.icon:SetTexture(buff.icon)
            if buff.expires and buff.expires > 0 and buff.duration and buff.duration > 0 then
                local rem = buff.expires - now
                ic.cd:SetCooldown(buff.expires - buff.duration, buff.duration)
                ic.text:SetText(FormatTime(math.max(rem, 0)))
                if warnBelow and rem <= warnBelow then SetBorder(ic, 1, 0.2, 0.2) else SetBorder(ic, 0, 0, 0) end
            else
                ic.cd:Clear()
                ic.text:SetText("")
                SetBorder(ic, 0, 0, 0)
            end
            ic.label:SetText("")
        else
            ShowMissing(ic, MissingIcon(prefix, preferred, cachedIcon), word)
        end
    end

    if prof.seal ~= false then
        DrawBuff(palaFrame.seal, pstate.seal, "Seal of", "Seal of Righteousness", db.lastSealIcon, "SEAL", 5)
    else
        palaFrame.seal:Hide()
    end

    if prof.blessing ~= false then
        DrawBuff(palaFrame.blessing, pstate.blessing, "Blessing of", "Blessing of Might", db.lastBlessIcon, "BLESS", nil)
    else
        palaFrame.blessing:Hide()
    end

    -- Righteous Fury (tanks): only if you know it and it is switched on for this class/spec
    if prof.rf ~= false and known["Righteous Fury"] then
        DrawBuff(palaFrame.rf, pstate.rf, "Righteous Fury", "Righteous Fury", db.lastRFIcon, "RF", 60)
    else
        palaFrame.rf:Hide()
    end

    -- Auras -------------------------------------------------------------
    local shownAuras = {}
    for _, ic in ipairs(palaFrame.auraIcons) do
        if prof.auras ~= false and known[ic.auraName] then shownAuras[#shownAuras + 1] = ic else ic:Hide() end
    end
    local anyAura = false
    for _, ic in ipairs(shownAuras) do
        place(ic)
        ic.icon:SetTexture(known[ic.auraName].icon)
        ic.cd:Clear()
        ic.text:SetText("")
        ic.label:SetText("")
        if pstate.aura == ic.auraName then
            anyAura = true
            ic.icon:SetDesaturated(false)
            ic:SetAlpha(1)
        else
            ic.icon:SetDesaturated(true)
            ic:SetAlpha(0.4)
        end
        SetBorder(ic, 0, 0, 0)
    end

    palaFrame:SetSize(math.max(idx, 3) * (size + GAP) - GAP, size)

    if #shownAuras > 0 and not anyAura then
        local scale = (db.textScale or 100) / 100
        palaFrame.warn:SetFont(FONT, math.max(9, math.floor(size * 0.3 * scale)), "OUTLINE")
        palaFrame.warn:ClearAllPoints()
        palaFrame.warn:SetPoint("LEFT", palaFrame, "RIGHT", 10, 0)
        palaFrame.warn:SetText("NO AURA")
    else
        palaFrame.warn:SetText("")
    end
end


------------------------------------------------------------------------
-- buff row for every non-Paladin class (Paladins have their own panel above)
--   "maintain" groups always show: active = icon + timer, missing = dimmed icon + red border
--   other groups show only while active
-- Names are matched against your own spellbook, so a buff you have not learned never shows.
------------------------------------------------------------------------
local function G(key, maintain, ...) return { key = key, maintain = maintain, spells = { ... } } end
local BUFF_GROUPS = {
    PALADIN = {   -- Seal / Blessing / Aura / Righteous Fury live in the Paladin panel; these show only while active
        G("hs", false, "Holy Shield"), G("ds", false, "Divine Shield"), G("dp", false, "Divine Protection"),
        G("aw", false, "Avenging Wrath"), G("df", false, "Divine Favor"), G("sd", false, "Sacred Duty"),
    },
    SHAMAN = {
        G("shield", true, "Lightning Shield", "Water Shield", "Earth Shield"),
        G("sr", false, "Shamanistic Rage"), G("bl", false, "Bloodlust", "Heroism"),
        G("gw", false, "Ghost Wolf"), G("ns", false, "Nature's Swiftness"),
        G("em", false, "Elemental Mastery"),
    },
    WARRIOR = {
        G("shout", true, "Battle Shout", "Commanding Shout"),
        G("sb", false, "Shield Block"), G("ls", false, "Last Stand"), G("sw", false, "Shield Wall"),
        G("rk", false, "Recklessness"), G("rt", false, "Retaliation"), G("br", false, "Berserker Rage"),
        G("bo", false, "Bloodrage"), G("dw", false, "Death Wish"), G("ss", false, "Sweeping Strikes"),
        G("ew", false, "Enraged Regeneration"),
    },
    HUNTER = {
        G("aspect", true, "Aspect of the Hawk", "Aspect of the Monkey", "Aspect of the Cheetah",
            "Aspect of the Pack", "Aspect of the Wild", "Aspect of the Beast", "Aspect of the Viper",
            "Aspect of the Dragonhawk"),
        G("rf", false, "Rapid Fire"), G("bw", false, "Bestial Wrath"), G("de", false, "Deterrence"),
        G("ta", false, "Trueshot Aura"), G("qs", false, "Quick Shots"), G("md", false, "Misdirection"),
    },
    ROGUE = {
        G("snd", false, "Slice and Dice"), G("ev", false, "Evasion"), G("sp", false, "Sprint"),
        G("bf", false, "Blade Flurry"), G("ar", false, "Adrenaline Rush"), G("cb", false, "Cold Blood"),
        G("st", false, "Stealth"), G("va", false, "Vanish"), G("ee", false, "Envenom"),
    },
    PRIEST = {
        G("fort", true, "Power Word: Fortitude", "Prayer of Fortitude"),
        G("fire", true, "Inner Fire"),
        G("spirit", false, "Divine Spirit", "Prayer of Spirit"), G("sprot", false, "Shadow Protection", "Prayer of Shadow Protection"),
        G("pws", false, "Power Word: Shield"), G("sf", false, "Shadowform"), G("pi", false, "Power Infusion"),
        G("ren", false, "Renew"), G("fw", false, "Fear Ward"),
    },
    MAGE = {
        G("armor", true, "Frost Armor", "Ice Armor", "Mage Armor", "Molten Armor"),
        G("int", true, "Arcane Intellect", "Arcane Brilliance"),
        G("ib", false, "Ice Barrier"), G("ms", false, "Mana Shield"), G("pom", false, "Presence of Mind"),
        G("ap", false, "Arcane Power"), G("iv", false, "Icy Veins"), G("cbt", false, "Combustion"),
        G("ibk", false, "Ice Block"), G("ward", false, "Fire Ward", "Frost Ward"),
        G("magic", false, "Amplify Magic", "Dampen Magic"), G("ev", false, "Evocation"),
    },
    WARLOCK = {
        G("armor", true, "Demon Skin", "Demon Armor", "Fel Armor"),
        G("sl", false, "Soul Link"), G("sw", false, "Shadow Ward"), G("sac", false, "Sacrifice"),
        G("ub", false, "Unending Breath"), G("dfr", false, "Fel Domination"),
    },
    DRUID = {
        G("motw", true, "Mark of the Wild", "Gift of the Wild"),
        G("th", false, "Thorns"), G("ooc", false, "Omen of Clarity"),
        G("form", false, "Bear Form", "Dire Bear Form", "Cat Form", "Travel Form", "Aquatic Form",
            "Moonkin Form", "Tree of Life", "Flight Form", "Swift Flight Form"),
        G("bk", false, "Barkskin"), G("fr", false, "Frenzied Regeneration"), G("tf", false, "Tiger's Fury"),
        G("inn", false, "Innervate"), G("ng", false, "Nature's Grasp"), G("ns", false, "Nature's Swiftness"),
        G("en", false, "Enrage"),
    },
}
local IMBUE_SPELLS = { "Rockbiter Weapon", "Flametongue Weapon", "Frostbrand Weapon", "Windfury Weapon" }

local POISON_ICON = "Interface\\Icons\\Ability_Poisons"
local IMBUE = {   -- weapon-enchant slots: Shaman imbues, Rogue poisons
    SHAMAN = { spells = IMBUE_SPELLS, word = "IMBUE" },
    ROGUE  = { spells = { "Poisons" }, word = "POISON", icon = POISON_ICON },
}
local PET_SPELLS = {
    HUNTER  = { "Call Pet" },
    WARLOCK = { "Summon Imp", "Summon Voidwalker", "Summon Succubus", "Summon Felhunter", "Summon Felguard" },
}
local buffGroups = BUFF_GROUPS[playerClass]
local imbueCfg = IMBUE[playerClass]
local hasImbues = imbueCfg ~= nil
local hasTotems = (playerClass == "SHAMAN")
local petSpells = PET_SPELLS[playerClass]
local petSet = {}
for _, n in ipairs(petSpells or {}) do petSet[n] = true end
local buffFrame
local BUFF_KEY = "buff"
local bstate = {}        -- group key -> { name, icon, duration, expires }
local imbueState = { main = nil, off = nil }   -- { expires = absolute time } from the weapon-enchant API

local function BuffSpellSet()
    local set = {}
    for _, g in ipairs(buffGroups or {}) do
        for _, n in ipairs(g.spells) do set[n] = g end
    end
    return set
end
local buffSet = BuffSpellSet()
local imbueNameSet = {}
for _, n in ipairs(imbueCfg and imbueCfg.spells or {}) do imbueNameSet[n] = true end

local function Ignored(name)
    local ig = currentProf and currentProf.ignore
    return ig and ig[name:lower()] and true or false
end

local imbueApi = "untested"     -- which source is driving the imbue slot (shown in /scdt debug)
local imbueRaw = ""
local auraImbue                 -- imbue seen as a normal aura (if this client exposes it that way)
local castImbue                  -- { at, dur } from your last imbue/poison cast (fallback when the API reports nothing)
local imbueApiTrusted = false       -- set once the API has reported a real enchant: then we believe it over casts

local function SpellDurationSeconds(id)
    local fn = (C_Spell and C_Spell.GetSpellDescription) or GetSpellDescription
    if not fn then return nil end
    local ok, desc = pcall(fn, id)
    if not ok or type(desc) ~= "string" or issecret(desc) then return nil end
    local m = desc:match("(%d+)%s*[Mm]in")
    if m then return tonumber(m) * 60 end
    local sec = desc:match("(%d+)%s*[Ss]ec")
    if sec then return tonumber(sec) end
end

local function RefreshBuffsFromAuras()
    local found = {}
    auraImbue = nil
    for _, a in ipairs(GetPlayerBuffs()) do
        if hasImbues and a.name and imbueNameSet[a.name] and not auraImbue then
            auraImbue = { expires = a.expires or 0, duration = a.duration, icon = a.icon, name = a.name }
            if a.icon then db.lastImbueIcon = a.icon end
        end
        local g = a.name and buffSet[a.name]
        if g and not found[g.key] and not Ignored(a.name) then
            found[g.key] = { name = a.name, icon = a.icon, duration = a.duration, expires = a.expires }
            if a.duration and a.duration > 0 then db.durations[a.name] = a.duration end
            db.buffIcons[g.key] = a.icon
        end
    end
    bstate = found
end

local function OnBuffCast(spellID)
    local name = SpellNameByID(spellID)
    if not name then return end
    local icon = SpellIconByID(spellID)
    local g = buffSet[name]
    if g then
        local d = db.durations[name]
        bstate[g.key] = { name = name, icon = icon, duration = d, expires = d and (GetTime() + d) or 0 }
        if icon then db.buffIcons[g.key] = icon end
    end
    if hasImbues and imbueNameSet[name] then
        castImbue = { at = GetTime(), dur = SpellDurationSeconds(spellID) }
        if icon and playerClass == "SHAMAN" then db.lastImbueIcon = icon end
    end
    if petSet[name] and icon then db.buffIcons.pet = icon end
end

local function ReadImbues()
    local now = GetTime()
    local main, off
    local usable = false
    if not GetWeaponEnchantInfo then
        imbueApi = "GetWeaponEnchantInfo missing"
    else
        local r = { pcall(GetWeaponEnchantInfo) }
        if not r[1] then
            imbueApi = "GetWeaponEnchantInfo errored"
        else
            local parts = {}
            local anySecret = false
            for i = 2, 7 do
                local v = r[i]
                if issecret(v) then anySecret = true; parts[#parts + 1] = "secret" else parts[#parts + 1] = tostring(v) end
            end
            imbueRaw = table.concat(parts, ", ")
            if anySecret then
                imbueApi = "GetWeaponEnchantInfo returns secret values"
            else
                usable = true
                imbueApi = "GetWeaponEnchantInfo"
                local hasMain, mainExp, hasOff, offExp = r[2], r[3], r[6], r[7]
                if hasMain then main = { expires = now + (tonumber(mainExp) or 0) / 1000 } end
                if hasOff then off = { expires = now + (tonumber(offExp) or 0) / 1000 } end
            end
        end
    end
    if main then imbueApiTrusted = imbueApiTrusted or usable end
    if not main and auraImbue then
        main = { expires = auraImbue.expires or 0 }
        imbueApi = (usable and imbueApi or "") .. (usable and " + aura" or "imbue seen as an aura")
    end
    if not main and castImbue and not imbueApiTrusted then
        -- the API reports nothing (or is unusable): trust your own cast, with the tooltip duration if we could read one
        if castImbue.dur then
            if now < castImbue.at + castImbue.dur then
                main = { expires = castImbue.at + castImbue.dur }
            else
                castImbue = nil
            end
        else
            main = { expires = 0 }
        end
        if main then imbueApi = (usable and "GetWeaponEnchantInfo reports none; " or "") .. "using your cast" .. (castImbue and castImbue.dur and " + tooltip duration" or " (no timer)") end
    end
    imbueState.main, imbueState.off = main, off
end

-- Shaman totems: slots 1-4 (fire, earth, water, air). GetTotemInfo is not an aura read, but guard it anyway.
local totemState = {}
local function ReadTotems()
    if not GetTotemInfo then return end
    local now = GetTime()
    for slot = 1, 4 do
        local ok, have, name, start, dur, icon = pcall(GetTotemInfo, slot)
        if ok and not (issecret(have) or issecret(start) or issecret(dur) or issecret(name)) then
            if have and name and name ~= "" and start and dur and dur > 0 then
                totemState[slot] = { name = name, icon = icon, duration = dur, expires = start + dur }
            else
                totemState[slot] = nil
            end
        elseif totemState[slot] and totemState[slot].expires <= now then
            totemState[slot] = nil       -- unreadable: keep the cache until its timer runs out
        end
    end
end


------------------------------------------------------------------------
-- gear check: warn when the equipped weapons don't fit the class
--   Paladin / Warrior / Shaman / Rogue: a one-hander (or an empty main hand) needs something in the
--   off hand (shield, weapon or held item); a two-hander is fine. Hunter: needs a ranged weapon.
--   This is a rule of thumb, not spec detection, and can be switched off per class/spec.
------------------------------------------------------------------------
local GEAR_RULES = {
    PALADIN = { offhand = true },
    WARRIOR = { offhand = true },
    SHAMAN  = { offhand = true },
    ROGUE   = { offhand = true },
    HUNTER  = { ranged = true },
}
local gearRule = GEAR_RULES[playerClass]
local GEAR_ICONS = {
    main    = "Interface\\PaperDoll\\UI-PaperDoll-Slot-MainHand",
    offhand = "Interface\\PaperDoll\\UI-PaperDoll-Slot-SecondaryHand",
    ranged  = "Interface\\PaperDoll\\UI-PaperDoll-Slot-Ranged",
}
local TWO_HAND = { INVTYPE_2HWEAPON = true }
local RANGED_LOC = { INVTYPE_RANGED = true, INVTYPE_RANGEDRIGHT = true, INVTYPE_THROWN = true }
local OFFHAND_OK = { INVTYPE_SHIELD = true, INVTYPE_WEAPON = true, INVTYPE_WEAPONOFFHAND = true, INVTYPE_HOLDABLE = true }

local gearWarn = {}        -- list of keys from GEAR_ICONS that are a problem right now
local gearAt = 0           -- last time we checked (0 = check on the next tick)
local gearInfo = ""        -- what we saw, for /scdt debug

local function SlotLoc(slot)
    if not GetInventoryItemID then return nil end
    local ok, id = pcall(GetInventoryItemID, "player", slot)
    if not ok or issecret(id) or not id then return nil, nil end
    local info = C_Item and C_Item.GetItemInfoInstant or GetItemInfoInstant
    if not info then return nil, id end
    local ok2, _, _, _, loc = pcall(info, id)
    if ok2 and type(loc) == "string" and not issecret(loc) and loc ~= "" then return loc, id end
    return nil, id
end

local function CheckGear()
    gearWarn = {}
    if not gearRule or not GetInventoryItemID then gearInfo = "equipment API missing"; return end
    local main, mainId = SlotLoc(16)
    local off, offId = SlotLoc(17)
    local rng, rngId = SlotLoc(18)
    gearInfo = string.format("main=%s(%s) off=%s(%s) ranged=%s(%s)", tostring(main), tostring(mainId),
        tostring(off), tostring(offId), tostring(rng), tostring(rngId))
    if gearRule.ranged then
        -- a ranged weapon can sit in the ranged slot or (in some clients) the main hand
        if not (RANGED_LOC[rng or ""] or RANGED_LOC[main or ""] or (rngId and not rng) or (mainId and not main)) then
            gearWarn[#gearWarn + 1] = "ranged"
        end
    elseif gearRule.offhand then
        if not mainId then
            gearWarn[#gearWarn + 1] = "main"
        elseif main and not TWO_HAND[main] and not RANGED_LOC[main] then
            -- one-hander: wants an off-hand item (unknown item type with an id present counts as filled)
            if not offId then gearWarn[#gearWarn + 1] = "offhand" end
        end
    end
end

local function BuildBuffs()
    buffFrame = CreateFrame("Frame", "SpellCDTrackerBuffFrame", UIParent)
    buffFrame.icons = {}
    for i = 1, 14 do buffFrame.icons[i] = CreateIcon(buffFrame) end
end

local function UpdateBuffs()
    if not buffFrame then return end
    local now = GetTime()
    local size = db.palaSize
    local prof = currentProf or EMPTY_PROF

    if AurasLocked() then
        for key, a in pairs(bstate) do
            if a.expires and a.expires > 0 and now > a.expires then bstate[key] = nil end
        end
        for _, k in ipairs({ "main", "off" }) do
            local a = imbueState[k]
            if a and a.expires > 0 and now > a.expires then imbueState[k] = nil end
        end
    else
        Guard(RefreshBuffsFromAuras)
    end
    if hasImbues then Guard(ReadImbues) end
    if hasTotems then Guard(ReadTotems) end

    buffFrame.title:SetText("Buffs (drag to move)")
    local used = 0
    local function slot_()
        used = used + 1
        local ic = buffFrame.icons[used]
        if not ic then used = used - 1; return nil end
        ic:SetSize(size, size)
        StyleIcon(ic, size)
        ic:ClearAllPoints()
        ic:SetPoint("LEFT", buffFrame, "LEFT", (used - 1) * (size + GAP), 0)
        ic:SetAlpha(1)
        ic.icon:SetDesaturated(false)
        ic.text:SetTextColor(1, 1, 1)
        ic:Show()
        return ic
    end
    local function DrawActive(ic, icon, expires, duration, warnBelow)
        ic.icon:SetTexture(icon or QUESTION)
        ic.label:SetText("")
        if expires and expires > 0 then
            local rem = expires - now
            if duration and duration > 0 then ic.cd:SetCooldown(expires - duration, duration) else ic.cd:Clear() end
            ic.text:SetText(FormatTime(math.max(rem, 0)))
            if warnBelow and rem <= warnBelow then SetBorder(ic, 1, 0.2, 0.2) else SetBorder(ic, 0, 0, 0) end
        else
            ic.cd:Clear(); ic.text:SetText(""); SetBorder(ic, 0, 0, 0)
        end
    end

    -- gear warnings come first: a missing off hand / ranged weapon is something to fix before combat
    if gearRule and (prof.gear ~= false) then
        if GetTime() - gearAt >= 1 then
            gearAt = GetTime()
            Guard(CheckGear)
        end
        for _, key in ipairs(gearWarn) do
            local ic = slot_()
            if ic then ShowMissing(ic, GEAR_ICONS[key], "") end
        end
    end

    -- warrior stance (current stance icon, neutral)
    if playerClass == "WARRIOR" and GetShapeshiftForm and GetShapeshiftFormInfo and not Ignored("Stance") then
        local ok, idx = pcall(GetShapeshiftForm)
        if ok and type(idx) == "number" and not issecret(idx) and idx > 0 then
            local ok2, icon = pcall(GetShapeshiftFormInfo, idx)
            if ok2 and icon and not issecret(icon) then
                local ic = slot_()
                if ic then DrawActive(ic, icon, nil, nil, nil) end
            end
        end
    end

    -- weapon enchants: Shaman imbues / Rogue poisons, one slot per weapon
    if hasImbues then
        local anyKnown = false
        for _, n in ipairs(imbueCfg.spells) do
            if known[n] and not Ignored(n) then anyKnown = true end
        end
        if imbueState.main or imbueState.off then anyKnown = true end
        if anyKnown then
            local fallback = imbueCfg.icon
            for _, n in ipairs(imbueCfg.spells) do if known[n] and not fallback then fallback = known[n].icon end end
            local icon = (playerClass == "SHAMAN" and db.lastImbueIcon) or fallback
            local hands = { "main" }
            if OffhandHasWeapon and OffhandHasWeapon() then hands[2] = "off" end
            for _, h in ipairs(hands) do
                local ic = slot_()
                if ic then
                    local st = imbueState[h]
                    if st then DrawActive(ic, icon, st.expires, nil, 120) else ShowMissing(ic, icon, imbueCfg.word) end
                end
            end
        end
    end

    -- pet missing (Hunter / Warlock)
    if petSpells and UnitExists then
        local any, first = false, nil
        for _, n in ipairs(petSpells) do
            if known[n] and not Ignored(n) then any = true; first = first or known[n] end
        end
        if any then
            local ok, have = pcall(UnitExists, "pet")
            if ok and not issecret(have) and not have then
                local ic = slot_()
                if ic then ShowMissing(ic, db.buffIcons.pet or first.icon, "PET") end
            end
        end
    end

    -- totems: shown only while they are down
    if hasTotems then
        for slot = 1, 4 do
            local t = totemState[slot]
            if t and not Ignored(t.name) then
                local ic = slot_()
                if ic then DrawActive(ic, t.icon, t.expires, t.duration, 10) end
            end
        end
    end

    for _, g in ipairs(buffGroups or {}) do
        local shown = false
        local st = bstate[g.key]
        if st and not Ignored(st.name) then
            local ic = slot_()
            if ic then
                DrawActive(ic, st.icon, st.expires, st.duration, g.maintain and 10 or nil)
                shown = true
            end
        elseif g.maintain then
            local first
            for _, n in ipairs(g.spells) do
                if known[n] and not Ignored(n) then first = first or known[n] end
            end
            if first then
                local ic = slot_()
                if ic then ShowMissing(ic, db.buffIcons[g.key] or first.icon, g.key:upper()) end
            end
        end
    end
    for i = used + 1, #buffFrame.icons do buffFrame.icons[i]:Hide() end
    buffFrame:SetSize(math.max(used, 2) * (size + GAP) - GAP, size)
end

------------------------------------------------------------------------
-- Forever's built-in swing timer: show only while in combat
-- (only touches alpha, so the bars keep their Edit Mode position and nothing gets Hidden/tainted)
------------------------------------------------------------------------
local SWING_FRAMES = { "SwingTimerMainHandFrame", "SwingTimerOffHandFrame", "SwingTimerRangedFrame" }
local swingManaged = false

local function InBlizzardEditMode()
    return EditModeManagerFrame and EditModeManagerFrame.IsShown and EditModeManagerFrame:IsShown()
end

local function SetSwingAlpha(a)
    for _, name in ipairs(SWING_FRAMES) do
        local f = _G[name]
        if f and f.GetAlpha and math.abs(f:GetAlpha() - a) > 0.01 then f:SetAlpha(a) end
    end
end

local function UpdateSwingTimer()
    if not db.swingCombatOnly then
        if swingManaged then          -- option switched off: give the bars back
            SetSwingAlpha(1)
            swingManaged = false
        end
        return
    end
    swingManaged = true
    local fighting = InCombat() or (UnitAffectingCombat and UnitAffectingCombat("player"))
    -- stay visible while the user is positioning bars in Blizzard's Edit Mode
    if fighting or InBlizzardEditMode() then SetSwingAlpha(1) else SetSwingAlpha(0) end
end

------------------------------------------------------------------------
-- options window
------------------------------------------------------------------------
local options
local refreshers = {}

local function MakeSlider(parent, label, minV, maxV, step, get, set, y)
    local s = CreateFrame("Slider", nil, parent)
    s:SetOrientation("HORIZONTAL")
    s:SetSize(220, 16)
    s:SetPoint("TOPLEFT", 24, y)
    s:SetMinMaxValues(minV, maxV)
    s:SetValueStep(step)
    if s.SetObeyStepOnDrag then s:SetObeyStepOnDrag(true) end

    local track = s:CreateTexture(nil, "BACKGROUND")
    track:SetPoint("LEFT", 0, 0)
    track:SetPoint("RIGHT", 0, 0)
    track:SetHeight(4)
    track:SetColorTexture(0.25, 0.25, 0.25, 1)

    s:SetThumbTexture("Interface\\Buttons\\UI-SliderBar-Button-Horizontal")
    s:GetThumbTexture():SetSize(16, 28)

    local text = s:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    text:SetPoint("BOTTOMLEFT", s, "TOPLEFT", 0, 4)

    local function refresh()
        local v = get()
        s:SetValue(v)
        text:SetText(label .. ": " .. v)
    end
    refresh()
    s:SetScript("OnValueChanged", function(_, value)
        value = math.floor(value / step + 0.5) * step
        set(value)
        text:SetText(label .. ": " .. value)
    end)
    refreshers[#refreshers + 1] = refresh
    return s
end

local function MakeCheck(parent, label, get, set, y, list, x)
    local cb = CreateFrame("CheckButton", nil, parent, "UICheckButtonTemplate")
    cb:SetPoint("TOPLEFT", x or 20, y)
    cb:SetSize(26, 26)
    local text = cb:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    text:SetPoint("LEFT", cb, "RIGHT", 2, 0)
    text:SetText(label)
    cb:SetScript("OnClick", function(self) set(self:GetChecked() and true or false) end)
    list = list or refreshers
    list[#list + 1] = function() cb:SetChecked(get()) end
    cb:SetChecked(get())
    return cb
end

------------------------------------------------------------------------
-- tracked spells window: class icons, spec tabs, spell list
------------------------------------------------------------------------
local spellsWin
local spellsRefreshers = {}
local SPELL_ROWS = 12
local selClass, selSpec                 -- selSpec: nil = "All specs"
local spellList, spellOffset = {}, 0
local SP_ICON_SIZE, SP_ICON_GAP = 40, 10
local GENERIC_ICON = "Interface\\Icons\\INV_Misc_QuestionMark"

-- Class icon: prefer the modern atlas, fall back to the classic class-icon sheet.
local function SetClassIcon(tex, key)
    local atlas = "classicon-" .. key:lower()
    if C_Texture and C_Texture.GetAtlasInfo and C_Texture.GetAtlasInfo(atlas) then
        tex:SetAtlas(atlas)
    elseif CLASS_ICON_TCOORDS and CLASS_ICON_TCOORDS[key] then
        tex:SetTexture("Interface\\Glues\\CharacterCreate\\UI-CharacterCreate-Classes")
        tex:SetTexCoord(unpack(CLASS_ICON_TCOORDS[key]))
    else
        tex:SetTexture(GENERIC_ICON)
    end
end

local function byName(a, b) return a.name < b.name end

-- spells for a class: live spellbook for your own class, saved snapshot for the others
local function ListSpells(class)
    if class == playerClass then
        local out = {}
        for name, s in pairs(known) do out[#out + 1] = { name = name, icon = s.icon } end
        table.sort(out, byName)
        if #out > 0 then return out end
    end
    return db.spellCache[class] or {}
end

local function ViewProf() return (ProfileFor(selClass, selSpec, false)) end
local function EditProf() return (ProfileFor(selClass, selSpec, true)) end

local function RefreshSpells()
    local win = spellsWin
    if not win or not db or not selClass then return end
    local prof, own = ProfileFor(selClass, selSpec, false)

    -- class icons: selected = full colour + class-coloured bar
    for key, b in pairs(win.classButtons) do
        local on = key == selClass
        b.icon:SetDesaturated(not on)
        b.icon:SetAlpha(on and 1 or 0.55)
        b.selected:SetShown(on)
    end

    win.header:SetText(ClassName(selClass))
    win.header:SetTextColor(ClassColor(selClass))
    win.active:SetText(selClass == playerClass and ("Active now: " .. (profileLabel or "")) or "")

    -- spec tabs: three specs, then All specs
    for i, t in ipairs(win.tabs) do
        local idx = win.tabSpec[i]
        t:SetText(idx and SpecName(selClass, idx) or "All specs")
        if idx == selSpec then t:LockHighlight() else t:UnlockHighlight() end
    end

    -- spec without its own profile: explain, or offer to drop the separate profile
    if selSpec and own then
        win.note:SetText("")
        win.resetBtn:Show()
    elseif selSpec then
        win.note:SetText("Uses your All specs settings. Changing anything here creates a separate profile for this spec.")
        win.resetBtn:Hide()
    else
        win.note:SetText("")
        win.resetBtn:Hide()
    end

    -- Paladin indicator toggles belong to the Paladin class only
    for _, cb in ipairs(win.toggles) do cb:SetShown(selClass == "PALADIN") end
    local hasGear = GEAR_RULES[selClass] ~= nil
    win.gearToggle:SetShown(hasGear)
    win.gearToggle:ClearAllPoints()
    win.gearToggle:SetPoint("TOPLEFT", win, "TOPLEFT", selClass == "PALADIN" and 372 or 20, -158)

    spellList = ListSpells(selClass)
    local maxOff = math.max(0, #spellList - SPELL_ROWS)
    if spellOffset > maxOff then spellOffset = maxOff end
    if spellOffset < 0 then spellOffset = 0 end

    for i = 1, SPELL_ROWS do
        local row = win.rows[i]
        local e = spellList[spellOffset + i]
        if e then
            win.rowSpell[i] = e.name
            row.icon:SetTexture(e.icon or GENERIC_ICON)
            row.text:SetText(e.name)
            row.check:SetChecked(not prof.ignore[e.name:lower()])
            row:Show()
        else
            win.rowSpell[i] = nil
            row:Hide()
        end
    end

    if #spellList == 0 then
        win.empty:SetText(selClass == playerClass and "No spells found yet."
            or ("Log in once on a " .. ClassName(selClass) .. " and its spells will show up here."))
        win.empty:Show()
        win.count:SetText("")
    else
        win.empty:Hide()
        win.count:SetText(string.format("%d-%d of %d", spellOffset + 1,
            math.min(spellOffset + SPELL_ROWS, #spellList), #spellList))
    end
    for _, r in ipairs(spellsRefreshers) do r() end
end

local function DefaultSpecFor(class)
    if class == playerClass then return DetectSpecIndex() end
    local n = db.lastSpec and db.lastSpec[class]
    if n and n > 0 then return n end
end

local function SelectClass(key)
    selClass = key
    selSpec = DefaultSpecFor(key)
    spellOffset = 0
    RefreshSpells()
end

local function SelectSpec(idx)
    selSpec = idx
    db.lastSpec[selClass] = idx or 0
    spellOffset = 0
    RefreshSpells()
end

local function BuildSpells()
    local tmpl = BackdropTemplateMixin and "BackdropTemplate" or nil
    local win = CreateFrame("Frame", "SpellCDTrackerSpells", UIParent, tmpl)
    spellsWin = win
    win:SetSize(480, 570)
    win:SetFrameStrata("DIALOG")
    win:SetPoint("CENTER", UIParent, "CENTER", 400, 0)
    win:SetMovable(true)
    win:EnableMouse(true)
    win:SetClampedToScreen(true)
    win:RegisterForDrag("LeftButton")
    win:SetScript("OnDragStart", function(self) self:StartMoving() end)
    win:SetScript("OnDragStop", function(self) self:StopMovingOrSizing() end)
    if win.SetBackdrop then
        win:SetBackdrop({
            bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background",
            edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
            tile = true, tileSize = 32, edgeSize = 32,
            insets = { left = 11, right = 12, top = 12, bottom = 11 },
        })
    end

    local title = win:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
    title:SetPoint("TOP", 0, -18)
    title:SetText("Tracked spells")
    local close = CreateFrame("Button", nil, win, "UIPanelCloseButton")
    close:SetPoint("TOPRIGHT", -6, -6)

    -- class icons (one row, centred)
    win.classButtons = {}
    local rowWidth = #CLASS_ORDER * SP_ICON_SIZE + (#CLASS_ORDER - 1) * SP_ICON_GAP
    for i, key in ipairs(CLASS_ORDER) do
        local b = CreateFrame("Button", nil, win)
        b:SetSize(SP_ICON_SIZE, SP_ICON_SIZE)
        b:SetPoint("TOPLEFT", win, "TOP", -rowWidth / 2 + (i - 1) * (SP_ICON_SIZE + SP_ICON_GAP), -48)
        b.icon = b:CreateTexture(nil, "ARTWORK")
        b.icon:SetAllPoints()
        SetClassIcon(b.icon, key)
        b.selected = b:CreateTexture(nil, "OVERLAY")
        b.selected:SetColorTexture(ClassColor(key))
        b.selected:SetPoint("TOPLEFT", b, "BOTTOMLEFT", 0, -2)
        b.selected:SetPoint("TOPRIGHT", b, "BOTTOMRIGHT", 0, -2)
        b.selected:SetHeight(3)
        b:SetHighlightTexture("Interface\\Buttons\\ButtonHilight-Square", "ADD")
        b:SetScript("OnClick", function() SelectClass(key) end)
        b:SetScript("OnEnter", function(self)
            GameTooltip:SetOwner(self, "ANCHOR_TOP")
            GameTooltip:AddLine(ClassName(key), ClassColor(key))
            if key ~= playerClass and not (db.spellCache[key] and #db.spellCache[key] > 0) then
                GameTooltip:AddLine("No spells saved yet. Log in on this class once.", 0.7, 0.7, 0.7, true)
            end
            GameTooltip:Show()
        end)
        b:SetScript("OnLeave", function() GameTooltip:Hide() end)
        win.classButtons[key] = b
    end

    -- class header + active profile
    win.header = win:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
    win.header:SetPoint("TOPLEFT", 24, -102)
    win.active = win:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    win.active:SetPoint("TOPRIGHT", -24, -106)

    -- spec tabs: three specs + All specs
    win.tabs, win.tabSpec = {}, { 1, 2, 3, nil }
    for i = 1, 4 do
        local t = CreateFrame("Button", nil, win, "UIPanelButtonTemplate")
        t:SetSize(104, 22)
        t:SetPoint("TOPLEFT", win, "TOPLEFT", 24 + (i - 1) * 110, -130)
        local idx = (i <= 3) and i or nil
        t:SetScript("OnClick", function() SelectSpec(idx) end)
        win.tabs[i] = t
    end

    -- Paladin indicators (this profile)
    win.toggles = {}
    local items = {
        { "seal", "Seal", 20 }, { "blessing", "Blessing", 92 },
        { "rf", "Righteous Fury", 190 }, { "auras", "Auras", 330 },
    }
    for _, it in ipairs(items) do
        local key = it[1]
        win.toggles[#win.toggles + 1] = MakeCheck(win, it[2],
            function() return ViewProf()[key] ~= false end,
            function(v) EditProf()[key] = v; RefreshSpells() end,
            -158, spellsRefreshers, it[3])
    end

    -- gear warnings toggle (classes with a weapon rule); sits at the right on Paladin, at the left otherwise
    win.gearToggle = MakeCheck(win, "Gear warning",
        function() return ViewProf().gear ~= false end,
        function(v) EditProf().gear = v; RefreshSpells() end,
        -158, spellsRefreshers, 20)

    -- track all / none, spec note, reset
    local all = CreateFrame("Button", nil, win, "UIPanelButtonTemplate")
    all:SetSize(90, 22)
    all:SetPoint("TOPLEFT", 24, -190)
    all:SetText("Track all")
    all:SetScript("OnClick", function() wipe(EditProf().ignore); RefreshSpells() end)

    local none = CreateFrame("Button", nil, win, "UIPanelButtonTemplate")
    none:SetSize(90, 22)
    none:SetPoint("LEFT", all, "RIGHT", 6, 0)
    none:SetText("Track none")
    none:SetScript("OnClick", function()
        local ig = EditProf().ignore
        for _, e in ipairs(ListSpells(selClass)) do ig[e.name:lower()] = true end
        RefreshSpells()
    end)

    win.note = win:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    win.note:SetPoint("TOPLEFT", 232, -186)
    win.note:SetWidth(224)
    win.note:SetJustifyH("LEFT")
    win.note:SetTextColor(0.75, 0.75, 0.75)

    win.resetBtn = CreateFrame("Button", nil, win, "UIPanelButtonTemplate")
    win.resetBtn:SetSize(150, 22)
    win.resetBtn:SetPoint("TOPLEFT", 232, -190)
    win.resetBtn:SetText("Use All specs settings")
    win.resetBtn:SetScript("OnClick", function()
        if selSpec then db.profiles[selClass .. ":" .. selSpec] = nil end
        RefreshSpells()
    end)
    win.resetBtn:Hide()

    -- spell rows
    local y0 = -222
    win.rows, win.rowSpell = {}, {}
    for i = 1, SPELL_ROWS do
        local row = CreateFrame("Frame", nil, win)
        row:SetSize(432, 24)
        row:SetPoint("TOPLEFT", 24, y0 - (i - 1) * 24)
        row.check = CreateFrame("CheckButton", nil, row, "UICheckButtonTemplate")
        row.check:SetSize(24, 24)
        row.check:SetPoint("LEFT", 0, 0)
        row.icon = row:CreateTexture(nil, "ARTWORK")
        row.icon:SetSize(18, 18)
        row.icon:SetPoint("LEFT", row.check, "RIGHT", 2, 0)
        row.icon:SetTexCoord(0.07, 0.93, 0.07, 0.93)
        row.text = row:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
        row.text:SetPoint("LEFT", row.icon, "RIGHT", 6, 0)
        row.text:SetWidth(360)
        row.text:SetJustifyH("LEFT")
        row.check:SetScript("OnClick", function(self)
            local name = win.rowSpell[i]
            if name then
                EditProf().ignore[name:lower()] = (not self:GetChecked()) or nil
                RefreshSpells()
            end
        end)
        win.rows[i] = row
    end

    win.empty = win:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    win.empty:SetPoint("TOP", win, "TOP", 0, y0 - 60)
    win.empty:SetWidth(360)
    win.empty:Hide()

    -- footer: paging
    local footY = y0 - SPELL_ROWS * 24 - 8
    local prev = CreateFrame("Button", nil, win, "UIPanelButtonTemplate")
    prev:SetSize(34, 22)
    prev:SetPoint("TOPLEFT", 24, footY)
    prev:SetText("<")
    prev:SetScript("OnClick", function() spellOffset = spellOffset - SPELL_ROWS; RefreshSpells() end)
    local nxt = CreateFrame("Button", nil, win, "UIPanelButtonTemplate")
    nxt:SetSize(34, 22)
    nxt:SetPoint("LEFT", prev, "RIGHT", 6, 0)
    nxt:SetText(">")
    nxt:SetScript("OnClick", function() spellOffset = spellOffset + SPELL_ROWS; RefreshSpells() end)
    win.count = win:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    win.count:SetPoint("LEFT", nxt, "RIGHT", 10, 0)

    win:SetSize(480, -footY + 22 + 28)
    win:EnableMouseWheel(true)
    win:SetScript("OnMouseWheel", function(_, delta)
        spellOffset = spellOffset - delta * 3
        RefreshSpells()
    end)
    win:SetScript("OnShow", RefreshSpells)

    selClass = selClass or playerClass
    selSpec = DefaultSpecFor(selClass)
    profileHook = RefreshSpells
    tinsert(UISpecialFrames, "SpellCDTrackerSpells")
    win:Hide()
end

local function ToggleSpells()
    if not spellsWin then BuildSpells() end
    if spellsWin:IsShown() then spellsWin:Hide() else spellsWin:Show() end
end

local function UpdateMinimapButton() end   -- replaced below

local function BuildOptions()
    local tmpl = BackdropTemplateMixin and "BackdropTemplate" or nil
    options = CreateFrame("Frame", "SpellCDTrackerOptions", UIParent, tmpl)
    options:SetSize(280, isPaladin and 380 or 330)
    options:SetPoint("CENTER")
    options:SetFrameStrata("DIALOG")
    options:SetMovable(true)
    options:EnableMouse(true)
    options:SetClampedToScreen(true)
    options:RegisterForDrag("LeftButton")
    options:SetScript("OnDragStart", function(self) self:StartMoving() end)
    options:SetScript("OnDragStop", function(self) self:StopMovingOrSizing() end)
    if options.SetBackdrop then
        options:SetBackdrop({
            bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background",
            edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
            tile = true, tileSize = 32, edgeSize = 32,
            insets = { left = 11, right = 12, top = 12, bottom = 11 },
        })
    end

    local title = options:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
    title:SetPoint("TOP", 0, -18)
    title:SetText("Spell Cooldown Tracker")

    local close = CreateFrame("Button", nil, options, "UIPanelCloseButton")
    close:SetPoint("TOPRIGHT", -6, -6)

    local y = -62
    MakeSlider(options, "Cooldown icon size", 16, 96, 2,
        function() return db.cdSize end, function(v) db.cdSize = v end, y)
    y = y - 50
    if isPaladin then
        MakeSlider(options, "Paladin icon size", 16, 96, 2,
            function() return db.palaSize end, function(v) db.palaSize = v end, y)
        y = y - 50
    end
    MakeSlider(options, "Text size %", 50, 200, 10,
        function() return db.textScale end, function(v) db.textScale = v; if cdFrame then for _, i in ipairs(cdFrame.icons) do i.styleKey = nil end end
            if palaFrame then palaFrame.seal.styleKey = nil; palaFrame.blessing.styleKey = nil
                for _, i in ipairs(palaFrame.auraIcons) do i.styleKey = nil end end end, y)
    y = y - 40
    local editBtn = CreateFrame("Button", nil, options, "UIPanelButtonTemplate")
    editBtn:SetSize(232, 24)
    editBtn:SetPoint("TOPLEFT", 24, y)
    local function refreshEdit()
        editBtn:SetText(editMode and "Edit mode: ON (click to lock)" or "Edit mode: OFF (click to move frames)")
    end
    editBtn:SetScript("OnClick", function() SetEditMode(not editMode) end)
    editHook = refreshEdit
    refreshers[#refreshers + 1] = refreshEdit
    refreshEdit()
    y = y - 34
    MakeCheck(options, "Swing timer only in combat",
        function() return db.swingCombatOnly end, function(v) db.swingCombatOnly = v end, y)
    y = y - 30
    MakeCheck(options, "Hide minimap button",
        function() return db.minimapHide end, function(v) db.minimapHide = v; UpdateMinimapButton() end, y)
    y = y - 40

    local reset = CreateFrame("Button", nil, options, "UIPanelButtonTemplate")
    reset:SetSize(100, 24)
    reset:SetPoint("TOPLEFT", 24, y)
    reset:SetText("Reset positions")
    reset:SetScript("OnClick", function()
        db.cd = CopyTable(defaults.cd); db.pala = CopyTable(defaults.pala)
        ApplyPosition(cdFrame, "cd")
        if palaFrame then ApplyPosition(palaFrame, "pala") end
        db.buff = CopyTable(defaults.buff); db.pbuff = CopyTable(defaults.pbuff)
        if buffFrame then ApplyPosition(buffFrame, BUFF_KEY) end
    end)

    local spellsBtn = CreateFrame("Button", nil, options, "UIPanelButtonTemplate")
    spellsBtn:SetSize(122, 24)
    spellsBtn:SetPoint("LEFT", reset, "RIGHT", 8, 0)
    spellsBtn:SetText("Tracked spells...")
    spellsBtn:SetScript("OnClick", function() ToggleSpells() end)

    local hint = options:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    hint:SetPoint("BOTTOMLEFT", 24, 22)
    hint:SetWidth(232)
    hint:SetJustifyH("LEFT")
    hint:SetText("Tracked spells are saved per class and spec.")

    options:SetScript("OnShow", function() for _, r in ipairs(refreshers) do r() end end)
    tinsert(UISpecialFrames, "SpellCDTrackerOptions")
    options:Hide()
end

local function ToggleOptions()
    if not options then BuildOptions() end
    if options:IsShown() then options:Hide() else options:Show() end
end

------------------------------------------------------------------------
-- minimap button
------------------------------------------------------------------------
local mm

local function PositionMinimapButton()
    local angle = math.rad(db.minimapAngle or 200)
    local radius = (Minimap:GetWidth() / 2) + 5
    mm:ClearAllPoints()
    mm:SetPoint("CENTER", Minimap, "CENTER", math.cos(angle) * radius, math.sin(angle) * radius)
end

local function BuildMinimapButton()
    mm = CreateFrame("Button", "SpellCDTrackerMinimapButton", Minimap)
    mm:SetSize(31, 31)
    mm:SetFrameStrata("MEDIUM")
    mm:SetFrameLevel(8)
    mm:RegisterForClicks("LeftButtonUp")
    mm:RegisterForDrag("LeftButton")

    local icon = mm:CreateTexture(nil, "ARTWORK")
    icon:SetTexture("Interface\\Icons\\INV_Misc_PocketWatch_01")
    icon:SetSize(20, 20)
    icon:SetPoint("TOPLEFT", 7, -5)
    icon:SetTexCoord(0.07, 0.93, 0.07, 0.93)

    local border = mm:CreateTexture(nil, "OVERLAY")
    border:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
    border:SetSize(53, 53)
    border:SetPoint("TOPLEFT")

    mm:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")

    mm:SetScript("OnClick", function() ToggleOptions() end)
    mm:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_LEFT")
        GameTooltip:AddLine("Spell Cooldown Tracker")
        GameTooltip:AddLine("Click: options", 1, 1, 1)
        GameTooltip:AddLine("Drag: move button", 1, 1, 1)
        GameTooltip:Show()
    end)
    mm:SetScript("OnLeave", function() GameTooltip:Hide() end)

    mm:SetScript("OnDragStart", function(self)
        self:SetScript("OnUpdate", function()
            local mx, my = Minimap:GetCenter()
            local cx, cy = GetCursorPosition()
            local scale = Minimap:GetEffectiveScale()
            cx, cy = cx / scale, cy / scale
            local atan = math.atan2 or math.atan
            db.minimapAngle = math.deg(atan(cy - my, cx - mx))
            PositionMinimapButton()
        end)
    end)
    mm:SetScript("OnDragStop", function(self) self:SetScript("OnUpdate", nil) end)

    PositionMinimapButton()
end

UpdateMinimapButton = function()
    if not mm then return end
    if db.minimapHide then mm:Hide() else mm:Show() end
end

------------------------------------------------------------------------
-- debug helper
------------------------------------------------------------------------
local function Debug(arg)
    local count = 0
    for _ in pairs(known) do count = count + 1 end
    print(string.format("Spell Cooldown Tracker: %d spells tracked | in combat: %s | auras locked: %s | secret API: %s",
        count, tostring(InCombat() and true or false), tostring(AurasLocked()), tostring(issecretvalue ~= nil)))
    local names = (arg and arg ~= "") and { arg } or { "Judgement", "Judgment", "Holy Strike", "Consecration" }
    local swingFound = {}
    print("  profile: " .. tostring(profileKey) .. " (" .. tostring(profileLabel) .. ")"
        .. (GetSpecialization and "" or " | client has no GetSpecialization: profiles are per class"))
    if buffGroups then
        local parts = {}
        for _, g in ipairs(buffGroups) do
            local st = bstate[g.key]
            parts[#parts + 1] = g.key .. "=" .. (st and st.name or "-")
        end
        print("  buffs: " .. table.concat(parts, ", ") .. (hasImbues and (" | imbues main/off: "
            .. tostring(imbueState.main and true or false) .. "/" .. tostring(imbueState.off and true or false)
            .. " | source: " .. tostring(imbueApi) .. " | raw: " .. tostring(imbueRaw)) or ""))
    end
    if gearRule then
        print("  gear: " .. (#gearWarn > 0 and ("WARNING " .. table.concat(gearWarn, ", ")) or "ok") .. " | " .. gearInfo)
    end
    for _, n in ipairs(SWING_FRAMES) do
        swingFound[#swingFound + 1] = n .. (_G[n] and " (found)" or " (NOT found)")
    end
    print("  swing timer: " .. table.concat(swingFound, ", ") .. " | combat-only: " .. tostring(db.swingCombatOnly and true or false))
    for _, want in ipairs(names) do
        local found
        for name, s in pairs(known) do
            if name:lower() == want:lower() then found = s break end
        end
        if not found then
            print("  " .. want .. ": not found in spell list")
        else
            local kind, st, d = ReadCooldown(found)
            print(string.format("  %s: id %s, state %s, start %s, duration %s, ignored: %s",
                found.name, tostring(found.id), kind,
                st and string.format("%.1f", st) or "-", d and string.format("%.1f", d) or "-",
                tostring((currentProf and currentProf.ignore[found.name:lower()]) and true or false)))
        end
    end
end

------------------------------------------------------------------------
-- main loop
------------------------------------------------------------------------
local elapsed = 0
local driver = CreateFrame("Frame")
driver:SetScript("OnUpdate", function(_, dt)
    elapsed = elapsed + dt
    if elapsed < 0.1 or not db then return end
    elapsed = 0
    -- separate guards: a failure in one part must not freeze the others
    if dirty and not InCombat() then
        dirty = false
        Guard(ScanSpells)
    end
    Guard(RefreshProfile)
    Guard(UpdateCooldowns)
    Guard(UpdateSwingTimer)
    if isPaladin then Guard(UpdatePaladin) end
    if buffFrame then Guard(UpdateBuffs) end
end)

driver:RegisterEvent("ADDON_LOADED")
driver:RegisterEvent("PLAYER_ENTERING_WORLD")
driver:RegisterEvent("SPELLS_CHANGED")
driver:RegisterEvent("ACTIONBAR_SLOT_CHANGED")
driver:RegisterEvent("PLAYER_REGEN_ENABLED")
driver:RegisterEvent("PLAYER_EQUIPMENT_CHANGED")
driver:RegisterEvent("SPELL_UPDATE_COOLDOWN")
if driver.RegisterUnitEvent then
    driver:RegisterUnitEvent("UNIT_SPELLCAST_SUCCEEDED", "player")
else
    driver:RegisterEvent("UNIT_SPELLCAST_SUCCEEDED")
end

driver:SetScript("OnEvent", function(_, event, arg1, arg2, arg3)
    if event == "ADDON_LOADED" then
        if arg1 ~= ADDON then return end
        SpellCDTrackerDB = SpellCDTrackerDB or {}
        db = SpellCDTrackerDB
        -- migrate v0.1 single size setting
        if db.size then
            db.cdSize = db.cdSize or db.size
            db.palaSize = db.palaSize or db.size
            db.size = nil
        end
        for k, v in pairs(defaults) do
            if db[k] == nil then
                db[k] = (type(v) == "table") and CopyTable(v) or v
            end
        end
        MakeMovable(cdFrame, "cd")
        ApplyPosition(cdFrame, "cd")
        if isPaladin then
            BuildPaladin()
            MakeMovable(palaFrame, "pala")
            ApplyPosition(palaFrame, "pala")
        end
        if buffGroups then
            BUFF_KEY = isPaladin and "pbuff" or "buff"
            BuildBuffs()
            MakeMovable(buffFrame, BUFF_KEY)
            ApplyPosition(buffFrame, BUFF_KEY)
        end
        ApplyLock()
        BuildMinimapButton()
        UpdateMinimapButton()
    elseif not db then
        return
    elseif event == "PLAYER_EQUIPMENT_CHANGED" then
        gearAt = 0
    elseif event == "SPELL_UPDATE_COOLDOWN" then
        Guard(UpdateGCDFlags)
    elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
        if arg1 == "player" then
            Guard(OnPlayerCast, arg3)
            if buffGroups and arg3 and not issecret(arg3) then Guard(OnBuffCast, arg3) end
        end
    else
        dirty = true
    end
end)

------------------------------------------------------------------------
-- slash commands
------------------------------------------------------------------------
SLASH_SPELLCDTRACKER1 = "/scdt"
SlashCmdList["SPELLCDTRACKER"] = function(msg)
    local cmd, rest = msg:match("^(%S*)%s*(.-)$")
    cmd = cmd:lower()
    if db and not currentProf then RefreshProfile() end
    if cmd == "" or cmd == "options" or cmd == "config" then
        ToggleOptions()
    elseif cmd == "edit" then
        SetEditMode(not editMode)
        print("Spell Cooldown Tracker: edit mode " .. (editMode and "ON - drag the green boxes" or "OFF"))
    elseif cmd == "swing" then
        db.swingCombatOnly = not db.swingCombatOnly
        print("Spell Cooldown Tracker: swing timer " .. (db.swingCombatOnly and "shows only in combat" or "always visible (untouched)"))
    elseif cmd == "lock" then
        SetEditMode(false); print("Spell Cooldown Tracker: edit mode OFF")
    elseif cmd == "unlock" then
        SetEditMode(true); print("Spell Cooldown Tracker: edit mode ON - drag the green boxes")
    elseif cmd == "size" and tonumber(rest) then
        local v = math.max(16, math.min(96, tonumber(rest)))
        db.cdSize, db.palaSize = v, v
        print("Spell Cooldown Tracker: icon size " .. v)
    elseif cmd == "ignore" and rest ~= "" then
        currentProf.ignore[rest:lower()] = true; print("Spell Cooldown Tracker: no longer tracking " .. rest .. " (" .. tostring(profileLabel) .. ")")
    elseif cmd == "unignore" and rest ~= "" then
        currentProf.ignore[rest:lower()] = nil; print("Spell Cooldown Tracker: tracking " .. rest .. " again (" .. tostring(profileLabel) .. ")")
    elseif cmd == "spells" or cmd == "track" then
        ToggleSpells()
    elseif cmd == "reset" then
        db.cd = CopyTable(defaults.cd); db.pala = CopyTable(defaults.pala)
        ApplyPosition(cdFrame, "cd")
        if palaFrame then ApplyPosition(palaFrame, "pala") end
        db.buff = CopyTable(defaults.buff); db.pbuff = CopyTable(defaults.pbuff)
        if buffFrame then ApplyPosition(buffFrame, BUFF_KEY) end
        print("Spell Cooldown Tracker: positions reset")
    elseif cmd == "debug" then
        Debug(rest)
    else
        print("Spell Cooldown Tracker: /scdt (options) | spells | edit | swing | size <n> | ignore <spell> | unignore <spell> | reset | debug [spell]")
    end
end
