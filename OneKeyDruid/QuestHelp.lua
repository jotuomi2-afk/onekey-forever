-- OneKeyDruid/QuestHelp.lua: the quest guide for a player on their own.
-- What to do next for XP, and a plan for the zone you are in: what to hand
-- in, which quests to take, what to work on, in the order of a short walk,
-- each one rated for a solo player. Quests that need a group (elite
-- targets, dungeons) or are too high are listed apart, with the reason.
--
-- Three sources, in this order of trust:
--   the game itself, for quests in your log (objectives and progress, the
--     group tag, the place the game's own map shows),
--   QuestData.lua (pfQuest, MIT): the Classic quests, their givers, mobs
--     with level and rank, and the one-line task,
--   QuestDataNew.lua (All The Things, MIT): where the quests Forever added
--     start; no titles (the client asks the server) and no mobs.
-- It only reads and shows. Going there is the player's part: a click sets
-- the game's own map pin and arrow.

local _, ns = ...
local QDB = ns.QDB
local QDBX = ns.QDBX or {}
local QH = {}
ns.QH = QH
if not QDB then return end

local cache = { q = {}, n = {}, o = {}, i = {} }

local function secret(v) return v ~= nil and issecretvalue ~= nil and issecretvalue(v) and true or false end

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

local function points(s)
	local pts, v = {}, ids(s)
	for k = 1, #v - 1, 2 do pts[#pts + 1] = { tonumber(v[k]), tonumber(v[k + 1]) } end
	return pts
end

-- a quest Forever added: where it starts, from what level, for whom
local function newQuest(id)
	local raw = QDBX[id]
	if not raw then return nil end
	local f = split(raw, "|")
	local map, pts = tonumber(f[4]), points(f[5])
	local q = { id = id, new = true, level = tonumber(f[1]) or 0, min = tonumber(f[1]) or 0,
		faction = tonumber(f[2]), classes = tonumber(f[3]), starts = {}, ends = {}, pre = ids(f[6]), preAll = {},
		excl = {}, obj = {}, flags = "", mob = 0, opens = (f[7] or ""):find("B", 1, true) and 1 or 0,
		zone = map, from = map and pts[1] and { name = nil, map = map, pts = pts } or nil }
	local omap, opts = tonumber(f[8]), points(f[9])
	if omap and opts[1] then q.at = { name = nil, map = omap, pts = opts } end
	return q
end

local function quest(id)
	local c = cache.q[id]
	if c ~= nil then return c or nil end
	local raw = QDB.q[id]
	if not raw then
		c = newQuest(id)
		cache.q[id] = c or false
		return c
	end
	local f = split(raw, "|")
	c = { id = id, title = f[1], level = tonumber(f[2]) or 0, min = tonumber(f[3]) or 0,
		starts = ids(f[4]), ends = ids(f[5]), pre = ids(f[6]), preAll = ids(f[7]), excl = ids(f[8]),
		obj = {}, zone = tonumber(f[10]), races = tonumber(f[11]), classes = tonumber(f[12]), faction = tonumber(f[13]),
		flags = f[14] or "", mob = tonumber(f[15]) or 0, opens = tonumber(f[16]) or 0, text = f[17] ~= "" and f[17] or nil }
	for _, o in ipairs(ids(f[9])) do
		local kind, oid, n = o:match("^(%a)(%d+)x?(%d*)$")
		if kind then c.obj[#c.obj + 1] = { kind = kind, id = tonumber(oid), n = tonumber(n) } end
	end
	cache.q[id] = c
	return c
end

-- npc or object: { name, map, pts = { {x, y}, ... }, lvl = "14-15", rank }
local function place(kind, id)
	local store = kind == "o" and QDB.o or QDB.n
	local c = cache[kind == "o" and "o" or "n"]
	if c[id] ~= nil then return c[id] or nil end
	local raw = store[id]
	if not raw then c[id] = false return nil end
	local f = split(raw, "|")
	local p = { name = f[1], map = tonumber(f[2]), pts = points(f[3]),
		lvl = f[4] ~= "" and f[4] or nil, rank = tonumber(f[5]) }
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
	return { name = f[1], from = ids(f[2]), objs = ids(f[3]) }
end

---------------------------------------------------------------------------
-- The game: quest log, completed quests, where you are
---------------------------------------------------------------------------

local function done(id)
	local f = (C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted) or IsQuestFlaggedCompleted
	if not f then return false end
	local ok, v = pcall(f, id)
	return ok and not secret(v) and v and true or false
end

-- tags the game puts on a quest that one player cannot do: 1 group/elite,
-- 62 raid, 81 dungeon, 85 heroic
local GROUP_TAG = { [1] = true, [62] = true, [81] = true, [85] = true }

-- what the game says of a quest in the log: who it is for, what is left
local function live(id, info)
	local out = { title = info and info.title, level = info and tonumber(info.level) or nil, group = false, left = {} }
	if info and type(info.suggestedGroup) == "number" and info.suggestedGroup > 1 then out.group = true end
	local C = C_QuestLog
	if C and C.GetQuestTagInfo then
		local ok, tag = pcall(C.GetQuestTagInfo, id)
		if ok and type(tag) == "table" and not secret(tag.tagID) and GROUP_TAG[tag.tagID] then out.group = true end
	end
	if C and C.GetQuestObjectives then
		local ok, list = pcall(C.GetQuestObjectives, id)
		if ok and type(list) == "table" then
			for _, o in ipairs(list) do
				if type(o) == "table" and not secret(o.text) and not secret(o.finished) and o.text and not o.finished then
					out.left[#out.left + 1] = o.text
				end
			end
		end
	end
	return out
end

-- active quests: id -> { title, complete, level, group, left }
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
					local e = live(info.questID, info)
					e.complete = okC and not secret(comp) and comp and true or false
					out[info.questID] = e
				end
			end
			return out
		end
	end
	if GetNumQuestLogEntries and GetQuestLogTitle then
		local n = GetNumQuestLogEntries()
		for i = 1, n do
			local title, level, group, header, _, complete, _, id = GetQuestLogTitle(i)
			if not header and id and id > 0 then
				out[id] = { title = title, level = tonumber(level), left = {},
					group = type(group) == "number" and group > 1, complete = complete == 1 or complete == true }
			end
		end
	end
	return out
end

-- where the game's own map puts the quests of the log on a map: id -> {x, y}
local function gamePoints(map)
	local out = {}
	local C = C_QuestLog
	if not (map and C and C.GetQuestsOnMap) then return out end
	local ok, list = pcall(C.GetQuestsOnMap, map)
	if ok and type(list) == "table" then
		for _, e in ipairs(list) do
			if type(e) == "table" and e.questID and not secret(e.x) and type(e.x) == "number" and type(e.y) == "number" then
				out[e.questID] = { e.x * 100, e.y * 100 }
			end
		end
	end
	return out
end

local function here()
	if not (C_Map and C_Map.GetBestMapForUnit and C_Map.GetPlayerMapPosition) then return nil end
	local ok, map = pcall(C_Map.GetBestMapForUnit, "player")
	if not ok or not map or secret(map) then return nil end
	local okP, pos = pcall(C_Map.GetPlayerMapPosition, map, "player")
	if not okP or not pos then return map end
	local okX, x, y = pcall(pos.GetXY, pos)
	if not okX or not x or secret(x) or secret(y) then return map end
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

local function titleOf(q, fi)
	if q.title then return q.title end
	local C = C_QuestLog
	if C and C.GetTitleForQuestID then
		local ok, t = pcall(C.GetTitleForQuestID, q.id)
		if ok and type(t) == "string" and not secret(t) and t ~= "" then q.title = t return t end
		-- not known yet: ask the server once, the answer is there next time
		if not q.asked and C.RequestLoadQuestByID then
			q.asked = true
			pcall(C.RequestLoadQuestByID, q.id)
		end
	end
	return (fi and "Uusi Forever-quest #%d" or "New Forever quest #%d"):format(q.id)
end

---------------------------------------------------------------------------
-- Who may take a quest, and can one player do it
---------------------------------------------------------------------------

local state = { at = 0, log = {}, mobs = {}, best = nil, lists = nil, plan = nil }

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

-- Can one player do it at this level?
--   "group": the game tags it for a group, an objective is elite, or it
--            is in a dungeon
--   "hard":  its mobs, or the quest itself, are 3 or more levels over you
--            (the fight key will not pull such mobs either)
--   "low":   6 or more levels under you: next to no XP
--   "new":   a quest Forever added: where it starts is known, its mobs not
--   "solo":  everything else
-- g: what the game says of it, when it is in the log
function QH.Rate(q, lvl, g)
	if g and g.group then return "group" end
	local flags = q.flags or ""
	if flags:find("D", 1, true) or flags:find("E", 1, true) then return "group" end
	local level = g and g.level or q.level or 0
	if q.new and not g then return "new" end
	if (q.mob or 0) >= lvl + 3 or level >= lvl + 3 then return "hard" end
	if level > 0 and level <= lvl - 6 then return "low" end
	return "solo"
end
local SOLO = { solo = true, new = true, low = true }

-- a quest may be taken: not done, not in the log, level fits, the quests
-- before it are done and none that rules it out
local skipped = {}
local function canTake(q, lvl, log)
	-- cheap checks first: done() asks the client
	if skipped[q.id] or log[q.id] then return false end
	if q.new then
		-- no quest level is known, only the level it opens at
		if q.min > lvl or (q.min > 0 and q.min < lvl - 8) then return false end
	elseif q.min > lvl or q.level < lvl - 5 or q.level > lvl + 3 then
		return false
	end
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
	return #q.starts > 0 or q.from ~= nil
end

-- XP weight: higher quests pay more, a quest far under you pays little,
-- and one that opens a chain is worth the walk
local function weight(q, lvl)
	local diff = q.level - lvl
	local w
	if q.new then w = q.min > 0 and 0.9 or 0.5
	elseif diff <= -5 then w = 0.2
	elseif diff <= -3 then w = 0.6
	else w = 1 + math.max(0, diff) * 0.1 end
	return w * (1 + math.min(5, q.opens or 0) * 0.06)
end

-- the level window of a record, without taking the whole line apart
local levels = {}
local function levelOf(id, raw)
	local v = levels[id]
	if not v then
		local l, m = raw:match("^[^|]*|(%d+)|(%d+)")
		v = { tonumber(l) or 0, tonumber(m) or 0 }
		levels[id] = v
	end
	return v[1], v[2]
end

local function lvlText(p)
	if not p or not p.lvl then return "" end
	local rank = p.rank == 1 and " elite" or p.rank == 2 and " rare elite" or p.rank == 3 and " boss" or ""
	return (" (%s%s)"):format(p.lvl, rank)
end

---------------------------------------------------------------------------
-- What to do
---------------------------------------------------------------------------

function QH.Refresh(lvl)
	local now = GetTime()
	state.at = now
	local log = questLog()
	state.log = log
	local map, x, y = here()
	local gp = gamePoints(map)
	lvl = lvl or 1
	-- the mobs your quests need, by name
	local mobs = {}
	local function need(p, title)
		if p and p.name then mobs[p.name] = mobs[p.name] or title end
	end
	local hand, work = {}, {}
	local function add(list, e)
		e.rate = QH.Rate(e.q, lvl, e.g)
		list[#list + 1] = e
	end
	for id, info in pairs(log) do
		local q = quest(id)
		if not q then
			-- a quest no data file has: what the game shows is all there is
			q = { id = id, title = info.title, level = info.level or 0, min = 0, starts = {}, ends = {}, obj = {},
				flags = "", mob = 0, opens = 0, unknown = true }
		elseif not q.title then
			q.title = info.title
		end
		if not skipped[id] then
			-- the game's own point for this quest on this map, when it gives one
			local spot = gp[id] and { name = nil, map = map, pts = { gp[id] } } or nil
			if info.complete then
				local p
				for _, e in ipairs(q.ends) do p = who(e) if p then break end end
				p = p or spot
				local pt, d = nearest(p, map, x, y)
				add(hand, { kind = "hand", q = q, g = info, p = p, pt = pt, d = d })
			else
				local n0 = #work
				for _, o in ipairs(q.obj) do
					if o.kind == "k" or o.kind == "o" then
						local p = place(o.kind == "o" and "o" or "n", o.id)
						if o.kind == "k" then need(p, q.title) end
						local pt, d = nearest(p, map, x, y)
						if p then
							add(work, { kind = "work", q = q, g = info, p = p, pt = pt, d = d,
								what = (o.kind == "k" and "kill %s%s" or "%s%s"):format(p.name, lvlText(p)) })
						end
					elseif o.kind == "i" then
						local it = item(o.id)
						if it then
							for _, src in ipairs(it.from) do
								local p = place("n", tonumber(src))
								need(p, q.title)
								local pt, d = nearest(p, map, x, y)
								if p then
									add(work, { kind = "work", q = q, g = info, p = p, pt = pt, d = d,
										what = ("%s from %s%s"):format(it.name, p.name, lvlText(p)) })
								end
							end
							for _, src in ipairs(it.objs) do
								local p = place("o", tonumber(src))
								local pt, d = nearest(p, map, x, y)
								if p then
									add(work, { kind = "work", q = q, g = info, p = p, pt = pt, d = d,
										what = ("%s in %s"):format(it.name, p.name) })
								end
							end
						end
					end
				end
				if #work == n0 then
					-- nothing in the data to go to: the game's point, or the
					-- place All The Things names for the objective
					local p = spot or q.at
					local pt, d = nearest(p, map, x, y)
					add(work, { kind = "work", q = q, g = info, p = p, pt = pt, d = d, what = info.left[1] or q.text })
				end
			end
		end
	end
	state.mobs = mobs
	-- quests to take, near you first; the far ones count by zone
	local take = {}
	local function offer(q)
		if q and canTake(q, lvl, log) then
			local p = q.from or who(q.starts[1])
			local pt, d = nearest(p, map, x, y)
			if p then
				local e = { kind = "take", q = q, p = p, pt = pt, d = d, w = weight(q, lvl) }
				add(take, e)
			end
		end
	end
	for id, raw in pairs(QDB.q) do
		local l, m = levelOf(id, raw)
		if m <= lvl and l >= lvl - 5 and l <= lvl + 3 and not log[id] and not skipped[id] then offer(quest(id)) end
	end
	for id in pairs(QDBX) do
		if not log[id] and not skipped[id] then offer(quest(id)) end
	end
	local function byDist(a, b) return a.d < b.d end
	table.sort(hand, byDist)
	table.sort(work, byDist)
	table.sort(take, function(a, b)
		-- distance in map percent, worth by quest level
		return a.d / a.w < b.d / b.w
	end)
	state.lists = { hand = hand, work = work, take = take, map = map, x = x, y = y, lvl = lvl }
	state.plan = nil
	-- the one thing to do next, of what one player can do: a hand-in
	-- nearby, a quest to take nearby, else work on the nearest objective,
	-- else the nearest anything
	local function first(list)
		for _, e in ipairs(list) do if e.kind == "hand" or SOLO[e.rate] then return e end end
	end
	local h1, t1, w1 = first(hand), first(take), first(work)
	local best
	local function near(e) return e and e.d < 25 end
	-- this map before another: a far hand-in waits until nothing is left here
	local function onMap(e) return e and e.d < 999 end
	if near(h1) then best = { "hand", h1 }
	elseif near(t1) and (not w1 or t1.d <= w1.d + 10) then best = { "take", t1 }
	elseif onMap(w1) then best = { "work", w1 }
	elseif onMap(t1) then best = { "take", t1 }
	elseif onMap(h1) then best = { "hand", h1 }
	elseif h1 then best = { "hand", h1 }
	elseif t1 then best = { "take", t1 } end
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
	if not e.p or not e.p.map then return "?" end
	if not e.pt then return mapName(e.p.map) end
	local s = ("%.0f,%.0f"):format(e.pt[1], e.pt[2])
	if e.d >= 999 then s = mapName(e.p.map) .. " " .. s end
	return s
end

-- one entry as a line: what to do and where; fi: Finnish
local function line(e, fi)
	local title = titleOf(e.q, fi)
	if e.kind == "hand" then
		if e.p and e.p.name then
			return (fi and "Palauta: %s → %s (%s)" or "Hand in: %s → %s (%s)"):format(title, e.p.name, where(e))
		end
		return (fi and "Palauta: %s (%s)" or "Hand in: %s (%s)"):format(title, where(e))
	elseif e.kind == "take" then
		if e.p and e.p.name then
			return (fi and "Ota: %s @ %s (%s)" or "Take: %s @ %s (%s)"):format(title, e.p.name, where(e))
		end
		return (fi and "Ota: %s (%s)" or "Take: %s (%s)"):format(title, where(e))
	end
	return (fi and "Tee: %s (%s)" or "Do: %s (%s)"):format(e.what or title, where(e))
end

-- the line for the HUD
function QH.Hint(fi)
	local b = state.best
	if not b then return nil end
	return line(b[2], fi)
end

-- the quest a target is needed for, by its name
function QH.ForMob(name)
	return name and state.mobs[name]
end

function QH.Age() return GetTime() - (state.at or 0) end

---------------------------------------------------------------------------
-- The plan for the zone you are in
---------------------------------------------------------------------------

local WHY = {
	en = { group = "needs a group", hard = "too high for now", low = "little XP", new = "new in Forever",
		elite = "elite", dungeon = "dungeon" },
	fi = { group = "vaatii ryhmän", hard = "vielä liian korkea", low = "vähän XP:tä", new = "uusi Foreverissa",
		elite = "eliitti", dungeon = "dungeon" },
}

local function reason(e, fi)
	local W = fi and WHY.fi or WHY.en
	if e.rate == "group" then
		local f = e.q.flags or ""
		if f:find("D", 1, true) then return W.dungeon end
		if f:find("E", 1, true) then return W.elite end
		return W.group
	end
	return W[e.rate]
end

-- what the quest asks, in a line: what is left by the game's count for a
-- quest in the log, the quest's own task line otherwise
local function task(e)
	if e.g and e.g.left and #e.g.left > 0 then return table.concat(e.g.left, " · ") end
	return e.q.text
end

-- Rows for the list, in the order to do them: hand-ins on this map, then
-- one walk through what a single player can take and do here (always the
-- nearest next, by worth), then what is left out and why, then the nearest
-- things on other maps. Each row: { e = entry, head, sub, rate, go }.
function QH.Plan(fi, max)
	local L = state.lists
	if not L then return {} end
	if state.plan and state.planFi == fi then return state.plan end
	max = max or 40
	local rows, apart, far = {}, {}, {}
	local seenWork = {}
	local function row(e, list)
		local lvl = e.g and e.g.level or e.q.level or 0
		local tag = e.q.new and not e.g and (e.q.min > 0 and ("%d+"):format(e.q.min) or "?") or tostring(lvl)
		local why = reason(e, fi)
		list[#list + 1] = { e = e, rate = e.rate, go = e.pt ~= nil,
			head = ("[%s] %s"):format(tag, line(e, fi)) .. (why and ("  — " .. why) or ""),
			sub = task(e) }
	end
	for _, e in ipairs(L.hand) do
		if e.d < 999 then row(e, rows) else row(e, far) end
	end
	-- the walk: from where you stand, the best next stop, then from there
	local stops = {}
	for _, e in ipairs(L.take) do
		if e.d < 999 and SOLO[e.rate] and e.rate ~= "low" then stops[#stops + 1] = e
		elseif e.d < 999 then apart[#apart + 1] = e end
	end
	for _, e in ipairs(L.work) do
		-- one stop per quest: its nearest objective
		if not seenWork[e.q.id] then
			seenWork[e.q.id] = true
			if e.d < 999 and SOLO[e.rate] then stops[#stops + 1] = e
			elseif e.d < 999 or e.rate == "group" or e.rate == "hard" then apart[#apart + 1] = e
			else far[#far + 1] = e end
		end
	end
	local px, py = L.x, L.y
	while #stops > 0 and #rows < max do
		local bi, bs
		for i, e in ipairs(stops) do
			local d = e.d
			if px and e.pt then d = math.sqrt((e.pt[1] - px) ^ 2 + (e.pt[2] - py) ^ 2) end
			local s = d / (e.w or 1)
			if not bs or s < bs then bi, bs = i, s end
		end
		local e = table.remove(stops, bi)
		if e.pt then px, py = e.pt[1], e.pt[2] end
		row(e, rows)
	end
	local out = {}
	for _, r in ipairs(rows) do out[#out + 1] = r end
	if #apart > 0 then
		out[#out + 1] = { sep = fi and "Ei yksin juuri nyt:" or "Not on your own right now:" }
		table.sort(apart, function(a, b) return a.d < b.d end)
		for i = 1, math.min(8, #apart) do row(apart[i], out) end
	end
	if #rows == 0 then
		-- nothing to do here: the nearest of what is elsewhere
		for _, e in ipairs(L.take) do if e.d >= 999 and SOLO[e.rate] and #far < 6 then far[#far + 1] = e end end
	end
	if #far > 0 then
		out[#out + 1] = { sep = fi and "Muualla:" or "Elsewhere:" }
		for i = 1, math.min(6, #far) do row(far[i], out) end
	end
	state.plan, state.planFi = out, fi
	return out
end

-- a map pin and the game's arrow to an entry (the suggestion, when none
-- is given). The player goes there; nothing moves on its own.
function QH.Go(e)
	e = e or (state.best and state.best[2])
	if not e or not e.pt or not e.p or not e.p.map then return false end
	if not (C_Map and C_Map.SetUserWaypoint and UiMapPoint and UiMapPoint.CreateFromCoordinates) then return false end
	local ok = pcall(function()
		C_Map.SetUserWaypoint(UiMapPoint.CreateFromCoordinates(e.p.map, e.pt[1] / 100, e.pt[2] / 100))
		if C_SuperTrack and C_SuperTrack.SetSuperTrackedUserWaypoint then C_SuperTrack.SetSuperTrackedUserWaypoint(true) end
	end)
	return ok, e.p.name or titleOf(e.q)
end

function QH.List(say, n)
	local L = state.lists
	if not L then say("no quest data yet.") return end
	n = n or 5
	local function show(head, list)
		if #list == 0 then return end
		say(head)
		for i = 1, math.min(n, #list) do
			local e = list[i]
			local why = reason(e)
			say(("  [%d] %s%s"):format(e.g and e.g.level or e.q.level or 0, line(e):gsub("^%a[%a ]*: ", ""), why and ("  — " .. why) or ""))
		end
	end
	show("hand in:", L.hand)
	show("to take:", L.take)
	show("to do:", L.work)
end

-- leave a quest out (the one the hint names, when none is given), for this
-- session; "clear" brings all back
function QH.Skip(e)
	e = (type(e) == "table" and e) or (state.best and state.best[2])
	if not e then return nil end
	skipped[e.q.id] = true
	state.at = 0
	return titleOf(e.q)
end
function QH.ClearSkips() skipped = {} state.at = 0 end

-- for the tests and /okd status
function QH.Count()
	local a, b = 0, 0
	for _ in pairs(QDB.q) do a = a + 1 end
	for _ in pairs(QDBX) do b = b + 1 end
	return a, b
end
