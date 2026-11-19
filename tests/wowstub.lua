-- tests/wowstub.lua: a fake WoW: Forever client, just enough to load the
-- addon and drive it outside the game. Loaded into a Lua 5.1 state by
-- tests/run_tests.py before the addon files.
--
-- What it checks while the addon runs (the "taint guard"):
--   * SetAttribute, SetOverrideBindingClick and ClearOverrideBindings fail
--     during combat lockdown, as in the real client (a secure button may
--     not change in combat). Any call there is recorded in STUB.violations.
--   * Health and power read through the plain API come back as "secret"
--     values: comparing or doing arithmetic on them raises an error, as in
--     WoW: Forever. Passing them on (SetValue, pcall, string.format) is fine.

STUB = {
	class = "DRUID", classId = 11, race = "NightElf", raceId = 4, faction = "Alliance",
	level = 20, combat = false, now = 1000, known = {}, buffs = {}, form = 0,
	violations = {}, scripts = {}, attrs = {}, bindings = {}, printed = {},
	zone = "Darkshore", map = 1439, x = 0.37, y = 0.44,
}

local function violation(what)
	STUB.violations[#STUB.violations + 1] = what
end

-- secret values: any comparison or arithmetic on one is an error
local SECRET = {}
local secretMeta = {
	__lt = function() error("compared a secret value", 2) end,
	__le = function() error("compared a secret value", 2) end,
	__add = function() error("arithmetic on a secret value", 2) end,
	__sub = function() error("arithmetic on a secret value", 2) end,
	__mul = function() error("arithmetic on a secret value", 2) end,
	__div = function() error("arithmetic on a secret value", 2) end,
	__concat = function() error("concatenated a secret value", 2) end,
	__tostring = function() return "<secret>" end,
}
local function secretValue() return setmetatable({}, secretMeta) end
function issecretvalue(v) return type(v) == "table" and getmetatable(v) == secretMeta end

-- frames --------------------------------------------------------------------
local frameMeta = {}
frameMeta.__index = function(t, k)
	local v = rawget(frameMeta, k)
	if v then return v end
	return function() end -- every other widget method is a no-op
end

function frameMeta.SetScript(self, event, fn)
	STUB.scripts[#STUB.scripts + 1] = { frame = self, event = event, fn = fn }
end
function frameMeta.HookScript(self, event, fn) frameMeta.SetScript(self, event, fn) end
function frameMeta.SetAttribute(self, k, v)
	if STUB.combat then violation("SetAttribute(" .. tostring(k) .. ") in combat on " .. tostring(self._name)) end
	STUB.attrs[(self._name or "?") .. ":" .. k] = v
end
function frameMeta.GetAttribute(self, k) return STUB.attrs[(self._name or "?") .. ":" .. k] end
function frameMeta.CreateFontString(self) return CreateFrame("FontString") end
function frameMeta.CreateTexture(self) return CreateFrame("Texture") end
function frameMeta.GetText() return "" end
function frameMeta.GetPoint() return "CENTER", nil, "CENTER", 0, 0 end
function frameMeta.GetFrameLevel() return 1 end
function frameMeta.GetWidth() return 100 end
function frameMeta.GetHeight() return 20 end
function frameMeta.GetStringWidth() return 50 end
function frameMeta.IsShown() return false end
function frameMeta.GetAlpha() return 1 end
function frameMeta.GetName(self) return self._name end
function frameMeta.SetFormattedText(self, fmt, ...)
	-- string.format on secret values is allowed in the client
	local args = { ... }
	for i = 1, select("#", ...) do if issecretvalue(args[i]) then args[i] = 50 end end
	self._text = string.format(fmt, unpack(args))
end
function frameMeta.SetText(self, t) self._text = t end
function frameMeta.SetAlpha(self, a)
	if issecretvalue(a) then return end
	self._alpha = a
end

function CreateFrame(kind, name, parent, template)
	local f = setmetatable({ _kind = kind, _name = name, _template = template }, frameMeta)
	if name then _G[name] = f end
	return f
end
UIParent = CreateFrame("Frame", "UIParent")
Minimap = CreateFrame("Frame", "Minimap")
STANDARD_TEXT_FONT = "Fonts\\FRIZQT__.TTF"

function SetOverrideBindingClick(owner, prio, key, button)
	if STUB.combat then violation("SetOverrideBindingClick in combat") end
	STUB.bindings[key] = button
end
function ClearOverrideBindings() if STUB.combat then violation("ClearOverrideBindings in combat") end end
function SetOverrideBinding() end
function GetBindingKey() return nil end
function GetBindingAction() return "" end
function SetBinding() return true end
function SaveBindings() end
function GetCurrentBindingSet() return 1 end
function InCombatLockdown() return STUB.combat end
function GetTime() return STUB.now end
function time() return 1794000000 + math.floor(STUB.now) end
function date() return "2026-11-18 12:00:00" end
function GetLocale() return "enUS" end
function print(...)
	local t = {}
	for i = 1, select("#", ...) do t[#t + 1] = tostring((select(i, ...))) end
	STUB.printed[#STUB.printed + 1] = table.concat(t, " ")
end
function strsplit(sep, s)
	local t = {}
	for part in (s .. sep):gmatch("(.-)" .. sep:gsub("%p", "%%%0")) do t[#t + 1] = part end
	return unpack(t)
end
function strtrim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end
function wipe(t) for k in pairs(t) do t[k] = nil end return t end
function tinsert(t, v) t[#t + 1] = v end
SlashCmdList = {}
hooksecurefunc = function() end

-- player ----------------------------------------------------------------------
function UnitClass(u) if u == "player" then return STUB.class, STUB.class, STUB.classId end end
function UnitRace(u) return STUB.race, STUB.race, STUB.raceId end
function UnitFactionGroup() return STUB.faction end
function UnitLevel(u) if u == "player" then return STUB.level end return STUB.targetLevel or STUB.level end
function UnitName(u) if u == "target" then return STUB.targetName end return "Tester" end
function UnitExists(u) if u == "target" then return STUB.targetName ~= nil end return u == "player" end
function UnitIsDead() return false end
function UnitIsDeadOrGhost() return false end
function UnitCanAttack(a, b) return b == "target" and STUB.targetName ~= nil end
function UnitIsFriend() return false end
function UnitClassification() return STUB.targetClass or "normal" end
function UnitCreatureType() return "Beast" end
function UnitIsTapDenied() return false end
function UnitIsTrivial() return false end
function UnitAffectingCombat() return STUB.combat end
function UnitThreatSituation() return nil end
function UnitHealth() return secretValue() end
function UnitPower() return secretValue() end
function UnitHealthMax() return 600 end
function UnitPowerMax() return 500 end
function UnitPowerType() return 0 end
function UnitHealthPercent() return secretValue() end
function UnitPowerPercent() return secretValue() end
function UnitXP() return 5000 end
function UnitXPMax() return 25000 end
function GetXPExhaustion() return 1200 end
function UnitBuff() return nil end
function UnitDebuff() return nil end
function UnitOnTaxi() return false end
function IsMounted() return false end
function IsResting() return false end
function IsSwimming() return false end
function IsFlying() return false end
function IsShiftKeyDown() return false end
function IsAltKeyDown() return false end
function IsControlKeyDown() return false end
function GetShapeshiftForm() return STUB.form end
function GetNumShapeshiftForms() return 3 end
function GetShapeshiftFormInfo(i)
	local ids = { 5487, 1066, 768 }
	return nil, STUB.form == i, true, ids[i]
end
function GetRealZoneText() return STUB.zone end
function GetZoneText() return STUB.zone end
function GetSubZoneText() return "" end
function GetMoney() return 10000 end
function GetInventoryItemDurability() return 50, 100 end
function GetCVarBool() return false end
function SetCVar() end
function GetCVar() return "0" end
function PlaySound() end
function FlashClientIcon() end
function GetNumGroupMembers() return 0 end
function IsInGroup() return false end
function IsInRaid() return false end

-- spells ------------------------------------------------------------------------
-- STUB.known: spell id -> name of the spells the character has learned
function IsPlayerSpell(id) return STUB.known[id] ~= nil end
function IsSpellKnown(id) return STUB.known[id] ~= nil end
function GetSpellInfo(x)
	if type(x) == "number" then return STUB.names and STUB.names[x] end
	for _, n in pairs(STUB.known) do if n == x then return x end end
	return nil
end
C_Spell = {
	GetSpellName = function(id) return STUB.names and STUB.names[id] end,
	GetSpellInfo = function(x)
		if type(x) == "string" then
			for _, n in pairs(STUB.known) do if n == x then return { name = x } end end
			return nil
		end
		local n = STUB.names and STUB.names[x]
		return n and { name = n } or nil
	end,
	GetSpellPowerCost = function() return { { type = 0, cost = 40 } } end,
	IsSpellUsable = function() return true, false end,
	IsSpellPassive = function(id) return id == 16864 end,
	PickupSpell = function(id) STUB.cursor = id end,
	GetSpellCooldown = function() return { startTime = 0, duration = 0, isEnabled = true } end,
}
function GetSpellCooldown() return 0, 0, 1 end
C_UnitAuras = {
	GetAuraDataBySpellName = function(unit, name)
		if STUB.buffs[name] then return { name = name, expirationTime = 0 } end
		return nil
	end,
	GetAuraDataByIndex = function() return nil end,
}
AuraUtil = { FindAuraByName = function(name) return STUB.buffs[name] and name or nil end }

-- spellbook and action bars ---------------------------------------------------
-- STUB.book: list of { name, rank, id }; STUB.bar: slot -> spell id
STUB.book, STUB.bar, STUB.placed, STUB.cursor = {}, {}, {}, nil
BOOKTYPE_SPELL = "spell"
function GetNumSpellTabs() return 1 end
function GetSpellTabInfo() return "General", nil, 0, #STUB.book end
function GetSpellBookItemName(i)
	local b = STUB.book[i]
	if b then return b[1], "Rank " .. b[2], b[3] end
end
function GetActionInfo(slot)
	if STUB.bar[slot] then return "spell", STUB.bar[slot] end
end
function GetCursorInfo() return STUB.cursor and "spell" or nil end
function ClearCursor() STUB.cursor = nil end
function PickupSpell(id) STUB.cursor = id end
C_Spell_PickupSpell = PickupSpell
function PlaceAction(slot)
	if STUB.combat then STUB.violations[#STUB.violations + 1] = "PlaceAction in combat" end
	STUB.bar[slot], STUB.cursor = STUB.cursor, STUB.bar[slot]
	STUB.placed[#STUB.placed + 1] = slot
end

-- items and bags --------------------------------------------------------------
C_Container = {
	GetContainerNumSlots = function() return 0 end,
	GetContainerItemID = function() return nil end,
	GetContainerItemInfo = function() return nil end,
	GetContainerNumFreeSlots = function() return 10, 0 end,
}
C_Item = {
	GetItemSpell = function() return nil end,
	GetItemInfo = function() return nil end,
	GetItemCount = function() return 0 end,
}
GetItemCount = function() return 0 end
GetItemCooldown = function() return 0, 0, 1 end

-- curves, maps, quests, meters -------------------------------------------------
Enum = { LuaCurveType = { Step = 1 }, PowerType = { Mana = 0 } }
CurveConstants = { ScaleTo100 = {} }
function CreateColor(r, g, b, a)
	return { GetRGBA = function() return r, g, b, a end }
end
C_CurveUtil = {
	CreateColorCurve = function()
		return { SetType = function() end, AddPoint = function() end }
	end,
}
C_Map = {
	GetBestMapForUnit = function() return STUB.map end,
	GetPlayerMapPosition = function() return { GetXY = function() return STUB.x, STUB.y end } end,
	GetMapInfo = function(id) return { name = "map" .. tostring(id) } end,
	SetUserWaypoint = function() end,
}
UiMapPoint = { CreateFromCoordinates = function(m, x, y) return { m, x, y } end }
C_SuperTrack = { SetSuperTrackedUserWaypoint = function() end }
C_QuestLog = {
	GetNumQuestLogEntries = function() return #(STUB.quests or {}) end,
	GetInfo = function(i) return STUB.quests[i] end,
	IsComplete = function(id) return STUB.questDone and STUB.questDone[id] or false end,
	IsQuestFlaggedCompleted = function(id) return STUB.flagged and STUB.flagged[id] or false end,
}
C_Minimap = {
	GetNumTrackingTypes = function() return 1 end,
	GetTrackingInfo = function() return { name = "Find Herbs", spellID = 2383, active = false } end,
	SetTracking = function() end,
}
C_NamePlate = { GetNamePlates = function() return {} end }
C_Timer = { After = function() end, NewTicker = function() return { Cancel = function() end } end }
C_DamageMeter = nil
C_CVar = { GetCVarBool = function() return false end, SetCVar = function() end }
C_AddOns = { IsAddOnLoaded = function() return false end }

-- drive the addon ------------------------------------------------------------------
function STUB.fire(event, ...)
	local errs = {}
	for _, s in ipairs(STUB.scripts) do
		if s.event == "OnEvent" then
			local ok, e = pcall(s.fn, s.frame, event, ...)
			if not ok then errs[#errs + 1] = event .. ": " .. tostring(e) end
		end
	end
	return errs
end

function STUB.tick(n, dt)
	local errs = {}
	for _ = 1, n or 1 do
		STUB.now = STUB.now + (dt or 0.25)
		for _, s in ipairs(STUB.scripts) do
			if s.event == "OnUpdate" then
				local ok, e = pcall(s.fn, s.frame, dt or 0.25)
				if not ok then errs[#errs + 1] = "OnUpdate: " .. tostring(e) end
			end
		end
	end
	return errs
end

function STUB.slash(msg)
	local f = SlashCmdList.ONEKEYDRUID
	if not f then return "no /okd" end
	local ok, e = pcall(f, msg)
	if not ok then return tostring(e) end
end
