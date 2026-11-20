-- OneKeyDruid/Ranks.lua: when a new rank of a spell is learned, the spell on
-- the action bars is moved up to it (WoW: Forever leaves the old rank there).
--
-- Runs only out of combat, with an empty cursor, after the spellbook changes
-- (or at login, or on /okd ranks). A spell kept on purpose at a lower rank
-- (a low Healing Touch, say) is left alone after you put it back once:
-- the addon only upgrades a slot whose rank it has not upgraded before.
-- /okd ranks off turns it off. The addon's own keys use spell names without a
-- rank, so they always cast the highest rank anyway.

local _, ns = ...
local R = {}
ns.Ranks = R

local pending = true
local SLOTS = 120

local function rankOf(sub)
	if type(sub) ~= "string" then return 0 end
	return tonumber(sub:match("(%d+)")) or 0
end

-- every spell in the spellbook: id -> { name, rank }, and the best rank by name
local function book()
	local byId, best = {}, {}
	local tabs = GetNumSpellTabs and GetNumSpellTabs() or 0
	for t = 1, tabs do
		local _, _, offset, n = GetSpellTabInfo(t)
		for i = (offset or 0) + 1, (offset or 0) + (n or 0) do
			local ok, name, sub, id = pcall(GetSpellBookItemName, i, BOOKTYPE_SPELL or "spell")
			if ok and name and id then
				local r = rankOf(sub)
				byId[id] = { name = name, rank = r }
				local b = best[name]
				if r > 0 and (not b or r > b.rank) then best[name] = { rank = r, id = id } end
			end
		end
	end
	return byId, best
end

local function pickup(id)
	if C_Spell and C_Spell.PickupSpell then return pcall(C_Spell.PickupSpell, id) end
	if PickupSpell then return pcall(PickupSpell, id) end
	return false
end

-- returns the names upgraded
function R.Update()
	local db = OneKeyDruidDB
	if not db or db.ranks == false or InCombatLockdown() then return nil end
	if GetCursorInfo and GetCursorInfo() then return nil end -- the player holds something
	db.rankDone = db.rankDone or {}
	local byId, best = book()
	local done = {}
	for slot = 1, SLOTS do
		local kind, id = GetActionInfo(slot)
		if kind == "spell" and id and byId[id] then
			local have = byId[id]
			local top = best[have.name]
			local key = top and (slot .. ":" .. top.id)
			if top and top.rank > have.rank and not db.rankDone[key] then
				if pickup(top.id) and GetCursorInfo and GetCursorInfo() then
					PlaceAction(slot)
					ClearCursor()
					db.rankDone[key] = true
					done[#done + 1] = ("%s %d"):format(have.name, top.rank)
				else
					if ClearCursor then ClearCursor() end
				end
			end
		end
	end
	return done
end

-- Prowl on the action bars becomes the "OKD Prowl" macro (cat form first,
-- then Prowl), once per slot, out of combat, with an empty cursor. Pressing
-- Prowl outside cat form did nothing (reported 20.11.).
function R.SwapProwl(prowlName, macroName)
	local db = OneKeyDruidDB
	if not db or db.prowlkey == false or InCombatLockdown() or not PickupMacro then return 0 end
	if GetCursorInfo and GetCursorInfo() then return 0 end
	if not GetMacroIndexByName or GetMacroIndexByName(macroName) == 0 then return 0 end
	db.prowlSwapped = db.prowlSwapped or {}
	local byId = book()
	local n = 0
	for slot = 1, SLOTS do
		local kind, id = GetActionInfo(slot)
		if kind == "spell" and id and byId[id] and byId[id].name == prowlName and not db.prowlSwapped[slot] then
			local ok = pcall(PickupMacro, macroName)
			if ok and GetCursorInfo and GetCursorInfo() then
				PlaceAction(slot)
				ClearCursor()
				db.prowlSwapped[slot] = true
				n = n + 1
			elseif ClearCursor then
				ClearCursor()
			end
		end
	end
	return n
end

local function run(say)
	local ok, done = pcall(R.Update)
	-- an error between pickup and place would leave the spell on the
	-- cursor; Update starts only with an empty cursor, so clearing is safe
	if not ok and ClearCursor then pcall(ClearCursor) end
	-- nil: not now (settings not loaded yet, in combat, cursor busy): try later
	pending = not ok or done == nil
	if ok and done and #done > 0 and say then
		say(((OneKeyDruidDB and OneKeyDruidDB.lang == "fi") and "toimintapalkki päivitetty: " or "action bars updated: ")
			.. table.concat(done, ", "))
	end
end

local frame = CreateFrame("Frame")
for _, e in ipairs({ "PLAYER_LOGIN", "SPELLS_CHANGED", "LEARNED_SPELL_IN_TAB", "PLAYER_REGEN_ENABLED" }) do
	pcall(frame.RegisterEvent, frame, e)
end
frame:SetScript("OnEvent", function(_, event)
	if event ~= "PLAYER_REGEN_ENABLED" then pending = true end
	if pending and not InCombatLockdown() then
		run(function(msg) print("|cff7fd4ffOneKey|r " .. msg) end)
	end
end)

-- /okd ranks [on|off]: from the slash commands of Core.lua and OneKey.lua
function R.Slash(rest, say)
	local db = OneKeyDruidDB
	if rest == "off" or rest == "on" then
		db.ranks = rest == "on"
		say("rank updates " .. rest .. ".")
		return
	end
	if InCombatLockdown() then say("not in combat.") return end
	db.rankDone = {}
	local ok, done = pcall(R.Update)
	if not ok then say("could not update: " .. tostring(done)) return end
	say(done and #done > 0 and ("updated: " .. table.concat(done, ", ")) or "every spell on the bars is at its highest rank.")
end
