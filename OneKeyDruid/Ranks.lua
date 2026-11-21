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

-- one spellbook entry: name, rank text, spell id. The old globals first,
-- then C_SpellBook, which newer clients have instead (Forever has one or
-- the other; with neither found, nothing was ever upgraded or swapped).
local function bookEntry(i)
	if GetSpellBookItemName then
		local ok, name, sub, id = pcall(GetSpellBookItemName, i, BOOKTYPE_SPELL or "spell")
		if ok and name and id then return name, sub, id end
	end
	local SB = C_SpellBook
	if SB and SB.GetSpellBookItemName and SB.GetSpellBookItemInfo then
		local bank = Enum and Enum.SpellBookSpellBank and Enum.SpellBookSpellBank.Player or 0
		local ok, name, sub = pcall(SB.GetSpellBookItemName, i, bank)
		local ok2, info = pcall(SB.GetSpellBookItemInfo, i, bank)
		local id = ok2 and type(info) == "table" and (info.spellID or info.actionID)
		if ok and name and id then return name, sub, id end
	end
end

local function bookRanges()
	local out = {}
	if GetNumSpellTabs and GetSpellTabInfo then
		for t = 1, GetNumSpellTabs() or 0 do
			local _, _, offset, n = GetSpellTabInfo(t)
			out[#out + 1] = { offset or 0, n or 0 }
		end
	elseif C_SpellBook and C_SpellBook.GetNumSpellBookSkillLines and C_SpellBook.GetSpellBookSkillLineInfo then
		for t = 1, C_SpellBook.GetNumSpellBookSkillLines() or 0 do
			local ok, info = pcall(C_SpellBook.GetSpellBookSkillLineInfo, t)
			if ok and type(info) == "table" then out[#out + 1] = { info.itemIndexOffset or 0, info.numSpellBookItems or 0 } end
		end
	end
	return out
end

-- every spell in the spellbook: id -> { name, rank }, and the best rank by name
local function book()
	local byId, best = {}, {}
	for _, r in ipairs(bookRanges()) do
		for i = r[1] + 1, r[1] + r[2] do
			local name, sub, id = bookEntry(i)
			if name and id then
				local rk = rankOf(sub)
				byId[id] = { name = name, rank = rk }
				local b = best[name]
				if rk > 0 and (not b or rk > b.rank) then best[name] = { rank = rk, id = id } end
			end
		end
	end
	return byId, best
end

-- the name of the spell an action slot holds, whatever the spellbook says
local function actionSpellName(id, byId)
	if byId[id] then return byId[id].name end
	if C_Spell and C_Spell.GetSpellName then
		local ok, n = pcall(C_Spell.GetSpellName, id)
		if ok and type(n) == "string" then return n end
	end
	if GetSpellInfo then
		local ok, n = pcall(GetSpellInfo, id)
		if ok and type(n) == "string" then return n end
	end
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
		if kind == "spell" and id and not db.prowlSwapped[slot] and actionSpellName(id, byId) == prowlName then
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
