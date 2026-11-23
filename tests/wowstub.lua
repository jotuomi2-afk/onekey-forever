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
STUB_secret = secretValue -- for the tests
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
-- events reach a frame only after it registered them, as in the client
function frameMeta.RegisterEvent(self, e)
	if type(e) ~= "string" or e == "" then error("RegisterEvent: bad event " .. tostring(e), 2) end
	if not rawget(self, "_events") then rawset(self, "_events", {}) end
	rawget(self, "_events")[e] = true
end
function frameMeta.RegisterUnitEvent(self, e) frameMeta.RegisterEvent(self, e) end
function frameMeta.UnregisterEvent(self, e) local t = rawget(self, "_events") if t then t[e] = nil end end
function frameMeta.UnregisterAllEvents(self) rawset(self, "_events", {}) end
function frameMeta.IsEventRegistered(self, e) local t = rawget(self, "_events") return t and t[e] or false end
function frameMeta.SetAttribute(self, k, v)
	-- blocked in combat, as in the client: the change does not happen
	if STUB.combat then violation("SetAttribute(" .. tostring(k) .. ") in combat on " .. tostring(self._name)) return end
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

STUB.bindOwner = {}
function SetOverrideBindingClick(owner, prio, key, button)
	if STUB.combat then violation("SetOverrideBindingClick in combat") return end
	STUB.bindings[key] = button
	STUB.bindOwner[key] = owner
end
function ClearOverrideBindings(owner)
	if STUB.combat then violation("ClearOverrideBindings in combat") end
	for k, o in pairs(STUB.bindOwner) do
		if o == owner then STUB.bindings[k] = nil STUB.bindOwner[k] = nil end
	end
end
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
function UnitIsPlayer(u) return u == "target" and STUB.targetIsPlayer == true end
function UnitExists(u) if u == "target" then return STUB.targetName ~= nil end return u == "player" end
function UnitIsDead() return false end
function UnitIsUnit(a, b) return a == b end
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
function IsMounted() return STUB.mounted or false end
function IsResting() return false end
STUB.swimming = false
function IsSwimming() return STUB.swimming end
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
function IsEquippedItemType(t) return t == "Wands" and STUB.wand ~= false end
function GetCVarBool() return false end
STUB.cvars = { Sound_EnableErrorSpeech = "1", Sound_EnableSoundWhenGameIsInBG = "0" }
function SetCVar(k, v) STUB.cvars[k] = tostring(v) end
function GetCVar(k) return STUB.cvars[k] end
STUB.macros = {}
function GetMacroIndexByName(n) if STUB.macros[n] then STUB.macroIdx = n return 1 end return 0 end
function GetMacroInfo(i) local n = STUB.macroIdx return n, 1, STUB.macros[n] end
function EditMacro(i, name, icon, body)
	if STUB.combat then violation("EditMacro in combat") end
	STUB.macros[name or STUB.macroIdx] = body
end
function CreateMacro(n, icon, body, perChar)
	if STUB.combat then violation("CreateMacro in combat") end
	STUB.macros[n] = body
	return 1
end
STUB.sounds = 0
function PlaySound() STUB.sounds = STUB.sounds + 1 end
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
			-- STUB.castTime[name]: milliseconds, as the client gives it
			for _, n in pairs(STUB.known) do
				if n == x then return { name = x, castTime = STUB.castTime and STUB.castTime[x] or 0 } end
			end
			return nil
		end
		local n = STUB.names and STUB.names[x]
		return n and { name = n } or nil
	end,
	GetSpellPowerCost = function() return { { type = 0, cost = 40 } } end,
	-- STUB.usable[name] = false: a reactive spell that cannot be used now
	-- STUB.secretUsable: the answer is a secret value in combat
	IsSpellUsable = function(name)
		if STUB.secretUsable and STUB.combat then return STUB_secret(), STUB_secret() end
		if STUB.usable and STUB.usable[name] ~= nil then return STUB.usable[name], false end
		return true, false
	end,
	IsSpellPassive = function(id) return id == 16864 end,
	PickupSpell = function(id) STUB.cursor = id end,
	-- range: STUB.inRange[spell name] = true / false (nil: no answer)
	IsSpellInRange = function(name) return STUB.inRange and STUB.inRange[name] end,
	-- cooldowns as the client keeps them: STUB.cooldown[name] = seconds
	-- starts one when the spell is cast (STUB.castDone)
	-- STUB.secretCooldown: start and duration are secret values in combat
	GetSpellCooldown = function(x)
		if STUB.secretCooldown and STUB.combat then
			return { startTime = STUB_secret(), duration = STUB_secret(), isEnabled = true }
		end
		local name = type(x) == "number" and STUB.names and STUB.names[x] or x
		local c = STUB.cds and STUB.cds[name]
		if c and STUB.now < c.start + c.dur then return { startTime = c.start, duration = c.dur, isEnabled = true } end
		return { startTime = 0, duration = 0, isEnabled = true }
	end,
}
function GetSpellCooldown() return 0, 0, 1 end
-- combo points are plain values in the client: STUB.combo
function GetComboPoints() return STUB.combo or 0 end
-- the main hand's imbue: STUB.imbue = true / false
function GetWeaponEnchantInfo() return STUB.imbue and true or false end
C_UnitAuras = {
	-- buffs in STUB.buffs, debuffs in STUB.debuffs: the filter decides
	GetAuraDataBySpellName = function(unit, name, filter)
		local from = filter == "HARMFUL" and (STUB.debuffs or {}) or STUB.buffs
		if from[name] then return { name = name, expirationTime = 0 } end
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
	local v = STUB.bar[slot]
	if type(v) == "string" then return "macro", 1 end
	if v then return "spell", v end
end
function PickupMacro(name) if STUB.macros[name] then STUB.cursor = name end end
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
Enum = { LuaCurveType = { Step = 1 }, PowerType = { Mana = 0 },
	DamageMeterSessionType = { Overall = 0, Current = 1 },
	DamageMeterType = { DamageDone = 0, Dps = 1, HealingDone = 2, Hps = 3, DamageTaken = 4 } }
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
	SetUserWaypoint = function(p) STUB.waypoint = p end,
}
UiMapPoint = { CreateFromCoordinates = function(m, x, y) return { m, x, y } end }
C_SuperTrack = { SetSuperTrackedUserWaypoint = function() end }
C_QuestLog = {
	GetNumQuestLogEntries = function() return #(STUB.quests or {}) end,
	GetInfo = function(i) return STUB.quests[i] end,
	IsComplete = function(id) return STUB.questDone and STUB.questDone[id] or false end,
	IsQuestFlaggedCompleted = function(id) return STUB.flagged and STUB.flagged[id] or false end,
	-- STUB.objectives[id] = { { text = "Wolves slain: 2/8", finished = false }, ... }
	GetQuestObjectives = function(id) return STUB.objectives and STUB.objectives[id] or {} end,
	-- STUB.questTag[id] = 1 (group), 81 (dungeon), 62 (raid)
	GetQuestTagInfo = function(id)
		local t = STUB.questTag and STUB.questTag[id]
		return t and { tagID = t, tagName = "tag" } or nil
	end,
	-- STUB.questPoi[map] = { { questID = 1, x = 0.5, y = 0.5 }, ... }
	GetQuestsOnMap = function(map) return STUB.questPoi and STUB.questPoi[map] or {} end,
	-- titles come from the server: known only once asked for (STUB.questTitles)
	GetTitleForQuestID = function(id) return STUB.questTitles and STUB.questTitles[id] or nil end,
}
C_Minimap = {
	GetNumTrackingTypes = function() return 1 end,
	GetTrackingInfo = function() return { name = "Find Herbs", spellID = 2383, active = false } end,
	SetTracking = function() end,
}
C_NamePlate = { GetNamePlates = function() return {} end }
-- a key press on a named secure button: its PreClick scripts run
function STUB.click(name, down)
	local errs = {}
	for _, s in ipairs(STUB.scripts) do
		if s.event == "PreClick" and rawget(s.frame, "_name") == name then
			local ok, e = pcall(s.fn, s.frame, "LeftButton", down)
			if not ok then errs[#errs + 1] = tostring(e) end
		end
	end
	return errs
end

-- timers are real: STUB.tick runs every callback that is due
STUB.timers = {}
STUB.cds = {}
STUB.cooldown = { ["Nature's Grasp"] = 60, ["Frost Nova"] = 25, ["Ice Lance"] = 8, ["Kidney Shot"] = 20, ["Gouge"] = 10,
	["Mind Blast"] = 8 }
-- the client fires UNIT_SPELLCAST_SUCCEEDED and starts the spell's cooldown
function STUB.castDone(spellID)
	local name = STUB.names and STUB.names[spellID]
	if name and STUB.cooldown[name] then STUB.cds[name] = { start = STUB.now, dur = STUB.cooldown[name] } end
	return STUB.fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast", spellID)
end
C_Timer = {
	After = function(sec, fn)
		if type(sec) ~= "number" or type(fn) ~= "function" then error("C_Timer.After: bad arguments", 2) end
		STUB.timers[#STUB.timers + 1] = { at = STUB.now + sec, fn = fn }
	end,
	NewTicker = function() return { Cancel = function() end } end,
}
-- the damage meter: plain numbers out of combat, secret ones in combat,
-- as in the client. STUB.meter = false turns it off.
-- loss of control: STUB.rooted = true puts a root on the player
STUB.rooted = false
C_LossOfControl = {
	GetActiveLossOfControlDataCount = function() return STUB.rooted and 1 or 0 end,
	GetActiveLossOfControlData = function(i)
		if STUB.rooted and i == 1 then return { locType = "ROOT", duration = 8 } end
	end,
}
STUB.meter = true
C_DamageMeter = {
	IsDamageMeterAvailable = function() return STUB.meter, nil end,
	GetCombatSessionFromType = function(sessionType, kind)
		if not STUB.meter then return nil end
		local function v(n) if STUB.combat then return secretValue() end return n end
		return { combatSources = {
			{ name = v("Player"), isLocalPlayer = v(true), classFilename = v("DRUID"),
			  totalAmount = v(1234), amountPerSecond = v(56) },
		} }
	end,
}
C_CVar = { GetCVarBool = function() return false end, SetCVar = function() end }
C_AddOns = { IsAddOnLoaded = function() return false end }

-- drive the addon ------------------------------------------------------------------
function STUB.fire(event, ...)
	local errs = {}
	for _, s in ipairs(STUB.scripts) do
		if s.event == "OnEvent" and rawget(s.frame, "_events") and rawget(s.frame, "_events")[event] then
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
		local due, keep = {}, {}
		for _, t in ipairs(STUB.timers) do
			if t.at <= STUB.now then due[#due + 1] = t else keep[#keep + 1] = t end
		end
		STUB.timers = keep
		for _, t in ipairs(due) do
			local ok, e = pcall(t.fn)
			if not ok then errs[#errs + 1] = "timer: " .. tostring(e) end
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
