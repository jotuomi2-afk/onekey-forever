-- OneKeyDruid/QuestHelp.lua: what to do next for XP, from the quest data in
-- QuestData.lua and the game's quest log. No route: the nearest useful
-- thing, in this order: hand in a finished quest, take a new one, work on
-- one you have. Marks the mobs your quests need.

local _, ns = ...
local QDB = ns.QDB
local QH = {}
ns.QH = QH
if not QDB then return end

local cache = { q = {}, n = {}, o = {}, i = {} }

local function split(s, sep)
	local t = {}
	for part in (s .. sep):gmatch("(.-)" .. sep:gsub("%p", "%%%0")) do t[#t + 1] = part end
	return t
end

local function ids(s)
	local t = {}
	if s and s ~= "" then for _, v in ipairs(split(s, ",")) do t[#t + 1] = v end end
	return t
end

local function quest(id)
	local c = cache.q[id]
	if c ~= nil then return c or nil end
	local raw = QDB.q[id]
	if not raw then cache.q[id] = false return nil end
	local f = split(raw, "|")
	c = { id = id, title = f[1], level = tonumber(f[2]) or 0, min = tonumber(f[3]) or 0,
		starts = ids(f[4]), ends = ids(f[5]), pre = ids(f[6]), preAll = ids(f[7]), excl = ids(f[8]),
		obj = {}, zone = tonumber(f[10]), races = tonumber(f[11]), classes = tonumber(f[12]), faction = tonumber(f[13]) }
	for _, o in ipairs(ids(f[9])) do
		local kind, oid, n = o:match("^(%a)(%d+)x?(%d*)$")
		if kind then c.obj[#c.obj + 1] = { kind = kind, id = tonumber(oid), n = tonumber(n) } end
	end
	cache.q[id] = c
	return c
end

-- npc or object: { name, map, pts = { {x, y}, ... } }
local function place(kind, id)
	local store = kind == "o" and QDB.o or QDB.n
	local c = cache[kind == "o" and "o" or "n"]
	if c[id] ~= nil then return c[id] or nil end
	local raw = store[id]
	if not raw then c[id] = false return nil end
	local f = split(raw, "|")
	local p = { name = f[1], map = tonumber(f[2]), pts = {} }
	if f[3] then
		local v = ids(f[3])
		for k = 1, #v - 1, 2 do p.pts[#p.pts + 1] = { tonumber(v[k]), tonumber(v[k + 1]) } end
	end
	c[id] = p
	return p
end

-- "o123" is an object, "123" an npc
local function who(ref)
	if type(ref) ~= "string" then ref = tostring(ref) end
	if ref:sub(1, 1) == "o" then return place("o", tonumber(ref:sub(2))) end
	return place("n", tonumber(ref))
end

local function item(id)
	local raw = QDB.i[id]
	if not raw then return nil end
	local f = split(raw, "|")
	return { name = f[1], from = ids(f[2]) }
end

---------------------------------------------------------------------------
-- The game: quest log, completed quests, where you are
---------------------------------------------------------------------------

local function done(id)
	local f = (C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted) or IsQuestFlaggedCompleted
	if not f then return false end
	local ok, v = pcall(f, id)
	return ok and v and true or false
end

-- active quests: id -> { title, complete }
local function questLog()
	local out = {}
	local C = C_QuestLog
	if C and C.GetNumQuestLogEntries and C.GetInfo then
		local ok, n = pcall(C.GetNumQuestLogEntries)
		if ok and type(n) == "number" then
			for i = 1, n do
				local okI, info = pcall(C.GetInfo, i)
				if okI and type(info) == "table" and not info.isHeader and info.questID and info.questID > 0 then
					local okC, comp = pcall(C.IsComplete, info.questID)
					out[info.questID] = { title = info.title, complete = okC and comp and true or false }
				end
			end
			return out
		end
	end
	if GetNumQuestLogEntries and GetQuestLogTitle then
		local n = GetNumQuestLogEntries()
		for i = 1, n do
			local title, _, _, header, _, complete, _, id = GetQuestLogTitle(i)
			if not header and id and id > 0 then out[id] = { title = title, complete = complete == 1 or complete == true } end
		end
	end
	return out
end

local function here()
	if not (C_Map and C_Map.GetBestMapForUnit and C_Map.GetPlayerMapPosition) then return nil end
	local ok, map = pcall(C_Map.GetBestMapForUnit, "player")
	if not ok or not map then return nil end
	local okP, pos = pcall(C_Map.GetPlayerMapPosition, map, "player")
	if not okP or not pos then return map end
	local okX, x, y = pcall(pos.GetXY, pos)
	if not okX or not x then return map end
	return map, x * 100, y * 100
end

local function mapName(map)
	if not (map and C_Map and C_Map.GetMapInfo) then return "?" end
	local ok, info = pcall(C_Map.GetMapInfo, map)
	return ok and info and info.name or ("map " .. tostring(map))
end

-- the nearest point of a place to you; far = another map
local function nearest(p, map, x, y)
	if not p or not p.map then return nil, 999 end
	if p.map ~= map or not x then return p.pts[1], 999 end
	local best, bd
	for _, pt in ipairs(p.pts) do
		local d = math.sqrt((pt[1] - x) ^ 2 + (pt[2] - y) ^ 2)
		if not bd or d < bd then best, bd = pt, d end
	end
	return best, bd or 999
end

---------------------------------------------------------------------------
-- What to do
---------------------------------------------------------------------------

local state = { at = 0, log = {}, mobs = {}, best = nil, lists = nil }

-- a quest may be taken: not done, not in the log, level fits, the quests
-- before it are done and none that rule it out
-- who you are: race and class as bits of the quest masks, faction 1 or 2
local me
local function whoAmI()
	if me then return me end
	local _, _, raceId = UnitRace("player")
	local _, _, classId = UnitClass("player")
	local fac = UnitFactionGroup and UnitFactionGroup("player")
	me = { race = raceId and 2 ^ (raceId - 1), class = classId and 2 ^ (classId - 1),
		faction = fac == "Alliance" and 1 or fac == "Horde" and 2 or nil }
	return me
end

local function hasBit(mask, bit)
	if not mask or mask == 0 or not bit then return true end
	return math.floor(mask / bit) % 2 == 1
end

local function forMe(q)
	local m = whoAmI()
	if q.faction and m.faction and q.faction ~= m.faction then return false end
	return hasBit(q.races, m.race) and hasBit(q.classes, m.class)
end

local skipped = {}
local function canTake(q, lvl, log)
	-- cheap checks first: done() asks the client, about 2000 quests a refresh
	if skipped[q.id] or log[q.id] then return false end
	if q.min > lvl or q.level < lvl - 5 or q.level > lvl + 3 then return false end
	if not forMe(q) then return false end
	if done(q.id) then return false end
	if #q.pre > 0 then
		local any = false
		for _, p in ipairs(q.pre) do if done(tonumber(p)) then any = true break end end
		if not any then return false end
	end
	for _, p in ipairs(q.preAll) do if not done(tonumber(p)) then return false end end
	for _, x in ipairs(q.excl) do
		local xi = tonumber(x)
		if done(xi) or log[xi] then return false end
	end
	return #q.starts > 0
end

-- XP weight: higher quests pay more; a quest far under you pays little
local function weight(q, lvl)
	local diff = q.level - lvl
	if diff <= -5 then return 0.2 end
	if diff <= -3 then return 0.6 end
	return 1 + math.max(0, diff) * 0.1
end

function QH.Refresh(lvl)
	local now = GetTime()
	state.at = now
	local log = questLog()
	state.log = log
	local map, x, y = here()
	-- the mobs your quests need, by name
	local mobs = {}
	local function need(npcRef, title)
		local p = who(npcRef)
		if p and p.name then mobs[p.name] = mobs[p.name] or title end
	end
	local hand, work = {}, {}
	for id, info in pairs(log) do
		local q = quest(id)
		if q and not skipped[id] then
			if info.complete then
				for _, e in ipairs(q.ends) do
					local p = who(e)
					local pt, d = nearest(p, map, x, y)
					if p then hand[#hand + 1] = { q = q, p = p, pt = pt, d = d } break end
				end
			else
				for _, o in ipairs(q.obj) do
					if o.kind == "k" then
						need(o.id, q.title)
						local p = place("n", o.id)
						local pt, d = nearest(p, map, x, y)
						if p then work[#work + 1] = { q = q, p = p, pt = pt, d = d, what = ("kill %s"):format(p.name) } end
					elseif o.kind == "i" then
						local it = item(o.id)
						if it then
							for _, src in ipairs(it.from) do
								need(src, q.title)
								local p = place("n", tonumber(src))
								local pt, d = nearest(p, map, x, y)
								if p then work[#work + 1] = { q = q, p = p, pt = pt, d = d, what = ("%s from %s"):format(it.name, p.name) } end
							end
						end
					end
				end
			end
		end
	end
	state.mobs = mobs
	-- quests to take, near you first; the far ones count by zone
	local take = {}
	if lvl then
		for id in pairs(QDB.q) do
			local q = quest(id)
			if q and canTake(q, lvl, log) then
				local p = who(q.starts[1])
				local pt, d = nearest(p, map, x, y)
				if p then take[#take + 1] = { q = q, p = p, pt = pt, d = d, w = weight(q, lvl) } end
			end
		end
	end
	local function byDist(a, b) return a.d < b.d end
	table.sort(hand, byDist)
	table.sort(work, byDist)
	table.sort(take, function(a, b)
		-- distance in map percent, worth by quest level
		return a.d / a.w < b.d / b.w
	end)
	state.lists = { hand = hand, work = work, take = take, map = map }
	-- the one thing to do next: a hand-in nearby, a quest to take nearby,
	-- else work on the nearest objective, else the nearest anything
	local best
	local function near(e) return e and e.d < 25 end
	-- this map before another: a far hand-in waits until nothing is left here
	local function here(e) return e and e.d < 999 end
	if near(hand[1]) then best = { "hand", hand[1] }
	elseif near(take[1]) and (not work[1] or take[1].d <= work[1].d + 10) then best = { "take", take[1] }
	elseif here(work[1]) then best = { "work", work[1] }
	elseif here(take[1]) then best = { "take", take[1] }
	elseif here(hand[1]) then best = { "hand", hand[1] }
	elseif hand[1] then best = { "hand", hand[1] }
	elseif take[1] then best = { "take", take[1] } end
	-- standing at the giver of a hinted quest for half a minute without
	-- taking it: it is not offered (a missing step before it, or not
	-- wanted). Leave it out for this session.
	if best and best[1] == "take" and best[2].d < 3 then
		local id = best[2].q.id
		if state.waitId ~= id then state.waitId, state.waitAt = id, now
		elseif now - state.waitAt > 30 then skipped[id] = true state.waitId = nil end
	else
		state.waitId = nil
	end
	state.best = best
	return best
end

local function where(e)
	if not e.pt then return mapName(e.p.map) end
	local s = ("%.0f,%.0f"):format(e.pt[1], e.pt[2])
	if e.d >= 999 then s = mapName(e.p.map) .. " " .. s end
	return s
end

-- the line for the HUD; fi: Finnish
function QH.Hint(fi)
	local b = state.best
	if not b then return nil end
	local e = b[2]
	if b[1] == "hand" then
		return (fi and "Palauta: %s → %s (%s)" or "Hand in: %s → %s (%s)"):format(e.q.title, e.p.name, where(e))
	elseif b[1] == "take" then
		return (fi and "Ota: %s @ %s (%s)" or "Take: %s @ %s (%s)"):format(e.q.title, e.p.name, where(e))
	else
		return (fi and "Tee: %s (%s)" or "Do: %s (%s)"):format(e.what, where(e))
	end
end

-- the quest a target is needed for, by its name
function QH.ForMob(name)
	return name and state.mobs[name]
end

function QH.Age() return GetTime() - (state.at or 0) end

-- a map pin and the game's arrow to the suggestion
function QH.Go()
	local b = state.best
	if not b or not b[2].pt then return false end
	local e = b[2]
	if not (C_Map and C_Map.SetUserWaypoint and UiMapPoint and UiMapPoint.CreateFromCoordinates) then return false end
	local ok = pcall(function()
		C_Map.SetUserWaypoint(UiMapPoint.CreateFromCoordinates(e.p.map, e.pt[1] / 100, e.pt[2] / 100))
		if C_SuperTrack and C_SuperTrack.SetSuperTrackedUserWaypoint then C_SuperTrack.SetSuperTrackedUserWaypoint(true) end
	end)
	return ok, e.p.name
end

function QH.List(say, n)
	local L = state.lists
	if not L then say("no quest data yet.") return end
	n = n or 5
	local function show(head, list, fmt)
		if #list == 0 then return end
		say(head)
		for i = 1, math.min(n, #list) do say("  " .. fmt(list[i])) end
	end
	show("hand in:", L.hand, function(e) return ("%s → %s (%s)"):format(e.q.title, e.p.name, where(e)) end)
	show("to take:", L.take, function(e) return ("[%d] %s @ %s (%s)"):format(e.q.level, e.q.title, e.p.name, where(e)) end)
	show("to do:", L.work, function(e) return ("%s: %s (%s)"):format(e.q.title, e.what, where(e)) end)
end

-- leave out the quest the hint names now (session only); "clear" brings all back
function QH.Skip(arg)
	local b = state.best
	if not b then return nil end
	skipped[b[2].q.id] = true
	return b[2].q.title
end
function QH.ClearSkips() skipped = {} end
