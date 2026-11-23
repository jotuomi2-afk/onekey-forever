-- OneKeyDruid/OneKey.lua: the one key for every class but the druid (the
-- druid has its own, Core.lua). The class's lists are in Classes.lua.
--
-- Keys (as for the druid): F out of combat buffs, conjures, pulls or finds
-- a target; in combat fights. Shift+F, Alt+F, Ctrl+F: the class's helper
-- spells; Alt+F out of combat with no enemy eats and drinks. G: emergency,
-- Shift+G: get away, Ctrl+G: hide.
--
-- Health and power are secret in WoW: Forever. Low health and low mana show
-- as texts whose alpha the game sets from a step curve; the HUD shows the
-- game's own percentages as text, unread.

local ADDON, ns = ...
local _, CLASS = UnitClass("player")
if CLASS == "DRUID" then return end
local CL = ns.CLASSES and ns.CLASSES[CLASS]
local Logic = ns.Logic

local VERSION = "0.35.2"
local PREFIX = "|cff7fd4ffOneKey|r "
local LIMIT = 255
local NAMES = { fight = "OneKeyMain", heal = "OneKeyHeal", cc = "OneKeyAlt", behind = "OneKeyCtrl",
	sos = "OneKeySOS", free = "OneKeyFree", hide = "OneKeyHide" }

local db
local N, known = {}, {}
local buttons = {}
local macros = {}
ns.OneKeyMacros = macros -- read by the tests
local food, water, potion
local hud, warn = nil, {}
local ready, dirty, bagsDirty = false, true, true
local current = { text = nil }
local clicks = {}
local fightPress = 0 -- the last key-down of the fight key
local sosPress = 0 -- and of the emergency key
local live = { start = 0, times = {} }
local adds = { n = 0, at = 0, warned = false }
local logEvent -- the session log, further down

local function say(msg) print(PREFIX .. msg) end
local function secret(v) return v ~= nil and issecretvalue ~= nil and issecretvalue(v) and true or false end
local function locked() return InCombatLockdown() end

local function spellName(id)
	local n
	if C_Spell and C_Spell.GetSpellName then n = C_Spell.GetSpellName(id) end
	if not n and GetSpellInfo then n = GetSpellInfo(id) end
	return n
end

local function isKnown(id, name)
	if id then
		if IsPlayerSpell and IsPlayerSpell(id) then return true end
		if IsSpellKnown and IsSpellKnown(id) then return true end
	end
	if C_Spell and C_Spell.GetSpellInfo then
		local ok, info = pcall(C_Spell.GetSpellInfo, name)
		if ok and info then return true end
	elseif GetSpellInfo and GetSpellInfo(name) then
		return true
	end
	return false
end

local function hasBuff(name)
	if not name then return false end
	if C_UnitAuras and C_UnitAuras.GetAuraDataBySpellName then
		local ok, has = pcall(function() return C_UnitAuras.GetAuraDataBySpellName("player", name, "HELPFUL") ~= nil end)
		if ok then return has and true or false end
	end
	if AuraUtil and AuraUtil.FindAuraByName then
		local ok, a = pcall(AuraUtil.FindAuraByName, name, "player", "HELPFUL")
		return ok and a ~= nil
	end
	return false
end

-- a debuff on the player, by its English name (out of combat only: auras
-- are secret in a fight)
local function hasDebuff(name)
	if not (name and C_UnitAuras and C_UnitAuras.GetAuraDataBySpellName) then return false end
	local ok, has = pcall(function() return C_UnitAuras.GetAuraDataBySpellName("player", name, "HARMFUL") ~= nil end)
	return ok and has and true or false
end

-- false only when the client says plainly that the spell cannot be cast
-- now (no rage, no mana, no reagent); true when it can or will not say
local function castable(name)
	if not (name and C_Spell and C_Spell.IsSpellUsable) then return true end
	local ok, usable = pcall(C_Spell.IsSpellUsable, name)
	if ok and not secret(usable) and usable == false then return false end
	return true
end

local function readSpells()
	if not CL then return end
	for key, s in pairs(CL.spells) do
		local name = spellName(s[1]) or s[2]
		N[key], known[key] = name, isKnown(s[1], name) or nil
	end
	-- a name for "one of these is learned" (warrior: a strike talent)
	for name, list in pairs(CL.either or {}) do
		known[name] = nil
		for _, k in ipairs(list) do if known[k] then known[name] = true end end
	end
	-- a wand in the ranged slot (for classes whose filler is the wand)
	known.wand = nil
	if CL.wand and IsEquippedItemType then
		local ok, w = pcall(IsEquippedItemType, "Wands")
		if ok and w and not secret(w) then known.wand = true end
	end
end

local FOOD_SPELL, DRINK_SPELL = 433, 430
local foodName, drinkName
local potionNames = {}

local function scanBags()
	food, water, potion = nil, nil, nil
	foodName = spellName(FOOD_SPELL) or "Food"
	drinkName = spellName(DRINK_SPELL) or "Drink"
	potionNames = { ["Healing Potion"] = true }
	for _, id in ipairs({ 439, 440, 441, 2024, 4042, 17534 }) do
		local n = spellName(id)
		if n then potionNames[n] = true end
	end
	local Cn = C_Container
	if not (Cn and Cn.GetContainerNumSlots and Cn.GetContainerItemID) then return end
	local itemSpell = (C_Item and C_Item.GetItemSpell) or GetItemSpell
	local itemInfo = (C_Item and C_Item.GetItemInfo) or GetItemInfo
	local level = UnitLevel("player") or 1
	local bf, bw, bp = -1, -1, -1
	for bag = 0, 4 do
		for slot = 1, Cn.GetContainerNumSlots(bag) or 0 do
			local id = Cn.GetContainerItemID(bag, slot)
			if id then
				local spell = itemSpell and itemSpell(id)
				local need = (itemInfo and select(5, itemInfo(id))) or 0
				if need <= level then
					if spell and potionNames[spell] and need > bp then potion, bp = id, need
					elseif spell == foodName and need > bf then food, bf = id, need
					elseif spell == drinkName and need > bw then water, bw = id, need end
				end
			end
		end
	end
end

local function targetKind()
	local e = UnitExists("target")
	if secret(e) then return "unknown" end
	if not e then return "none" end
	local d, a = UnitIsDead("target"), UnitCanAttack("player", "target")
	if secret(d) or secret(a) then return "unknown" end
	if d then return "dead" end
	if a then return "hostile" end
	return "friendly"
end

---------------------------------------------------------------------------
-- Macros from the class's lists
---------------------------------------------------------------------------

-- lines: { text, priority }. Logic.Fit drops the least needed lines first
-- and gives back any that fit afterwards.
local function fit(lines)
	for i = 1, #lines do lines[i][2] = lines[i][2] or 1 end
	return Logic.Fit(lines)
end

local function M(name)
	if name:sub(-1) == ")" then return name .. "()" end
	return name
end

local openerN -- how many openers the fight macro being built gets
local fightBy = {} -- the fight macro for 0, 1, 2 ... openers
ns.OneKeyFightBy = function() return fightBy end -- read by the tests

-- one line of a class list as macro text, or nil when not learned
local function line(e)
	-- need / without: the line only when a spell is (not) known, for
	-- chains that change shape as the class learns spells
	if e.need and not known[e.need] then return nil end
	if e.without and known[e.without] then return nil end
	local kind = e[1]
	if e.below or e.from then
		local lvl = UnitLevel("player")
		if secret(lvl) or type(lvl) ~= "number" then lvl = 1 end
		if e.below and lvl >= e.below then return nil end
		if e.from and lvl < e.from then return nil end
	end
	if kind == "opener" then
		-- as often as the variant being built says (rebuild: one fight
		-- macro for each number of openers)
		local n = openerN or 0
		if n < 1 or not known[e[2]] then return nil end
		local list = {}
		for i = 1, n do list[i] = M(N[e[2]]) end
		return ("/castsequence %sreset=target %s, null"):format(e[3] or "", table.concat(list, ", "))
	end
	if kind == "potion" then
		return potion and ("/use [combat] item:%d"):format(potion) or nil
	elseif kind == "raw" then
		for _, k in ipairs(e.needs or {}) do if not known[k] then return nil end end
		return e[2]
	elseif kind == "cast" then
		if not known[e[2]] then return nil end
		return ("/cast %s%s%s"):format(e[3] or "", e.bang and "!" or "", M(N[e[2]]))
	elseif kind == "once" then
		if not known[e[2]] then return nil end
		return ("/castsequence %sreset=target %s, null"):format(e[3] or "", M(N[e[2]]))
	elseif kind == "seq" then
		local list = {}
		for _, k in ipairs(e[2]) do if known[k] then list[#list + 1] = M(N[k]) end end
		if #list == 0 then return nil end
		-- stop: once through, then the line is passed over until its reset
		if e.stop and e[4] then
			return ("/castsequence %sreset=%s %s, null"):format(e[3] or "", e[4], table.concat(list, ", "))
		end
		if #list == 1 and e.once then return ("/castsequence %sreset=target %s, null"):format(e[3] or "", list[1]) end
		if #list == 1 then return ("/cast %s%s"):format(e[3] or "", list[1]) end
		-- stop: once through per target, then the line is passed over
		if e.stop then list[#list + 1] = "null" end
		return ("/castsequence %sreset=%s %s"):format(e[3] or "", e[4] or "target", table.concat(list, ", "))
	end
end

-- Priorities: the head (targeting, auto attack), raw lines (the pet) and
-- the last learned line, which is the class's main filler spell, are never
-- dropped. Of the others, later lines go first.
local function build(list, head)
	-- a potion goes last, whatever the list says (see Classes.lua, sos)
	if list then
		local rest, pots = {}, {}
		for _, e in ipairs(list) do
			if e[1] == "potion" then pots[#pots + 1] = e else rest[#rest + 1] = e end
		end
		for _, e in ipairs(pots) do rest[#rest + 1] = e end
		list = rest
	end
	local L = {}
	for _, h in ipairs(head or {}) do L[#L + 1] = { h, 1 } end
	local body = {}
	for _, e in ipairs(list or {}) do
		local t = line(e)
		if t then body[#body + 1] = { t, e[1] == "raw" and 1 or 2 + #body } end
	end
	if #body > 0 then body[#body][2] = 1 end
	for _, b in ipairs(body) do L[#L + 1] = b end
	if #L == 0 then return "" end
	return fit(L)
end

local TARGET = "/targetenemy [noharm][dead]"

local function rebuild()
	if locked() or not CL then return end
	readSpells()
	local head = { TARGET }
	if CL.melee and CL.attack ~= false then head[#head + 1] = CL.attack or "/startattack [harm,nodead]" end
	local all = {}
	for _, e in ipairs(CL.pull or {}) do all[#all + 1] = e end
	for _, e in ipairs(CL.fight or {}) do all[#all + 1] = e end
	-- with nothing learned that hits, the wand or the white swing does it
	local function fightWith(n)
		openerN = n
		local text = build(all, head)
		if CL.wand and known.shoot and not CL.melee and not CL.wandFiller then
			-- out of mana the spells above are skipped (not stopped on) and the
			-- wand shoots; "!" keeps a second press from turning it off
			text = fit({ { text, 1 }, { ("/cast [harm,nodead,nochanneling] !%s"):format(N.shoot), 2 } })
		end
		return text
	end
	-- one fight macro per number of openers; which one sits on the key is
	-- chosen before each pull (decide). With no opener in the class list
	-- there is the one macro.
	local top = 0
	for _, e in ipairs(CL.fight or {}) do
		if e[1] == "opener" and known[e[2]] and (not e.need or known[e.need]) then
			top = math.max(e.count or 1, math.min(3, math.floor(tonumber(db.opener) or 0)))
		end
	end
	fightBy = {}
	for n = 0, top do fightBy[n] = fightWith(n) end
	openerN = nil
	-- the fight macro when nothing was chosen (attacked first): no opener
	macros.fight = fightBy[0]
	macros.heal = build(CL.heal)
	-- Alt: the class's stop, and out of combat with no enemy: eat and drink
	local REST = "[nocombat,noharm][nocombat,dead]"
	local rest = {}
	if food then rest[#rest + 1] = ("/use %s item:%d"):format(REST, food) end
	if water then rest[#rest + 1] = ("/use %s item:%d"):format(REST, water) end
	macros.cc = build(CL.cc, rest)
	macros.behind = build(CL.behind)
	macros.sos = build(CL.sos)
	macros.free = build(CL.free)
	-- hide: the class's own, else Shadowmeld for a night elf
	local hide = build(CL.hide)
	if hide == "" then
		local sm = spellName(20580)
		if sm and isKnown(20580, sm) then hide = "/cast [nocombat] " .. sm end
	end
	macros.hide = hide
	for key, b in pairs(buttons) do
		if key ~= "fight" then b:SetAttribute("macrotext", macros[key] or "") end
	end
	current.text = nil
	dirty = false
end

---------------------------------------------------------------------------
-- What the key does now (out of combat)
---------------------------------------------------------------------------

local TEXT = {
	en = { target = "%s: find a target", fight = "%s: attack", buff = "%s: buff (%s)", conjure = "%s: conjure (%s)",
		hold = "DO NOT PULL: too strong (%s). /okd brave on", dead = "You are dead", mounted = "Mounted",
		cFight = "%s: fight", cMany = "%d enemies: press %s or run", run = "RUN AWAY!  %s",
		low = "LOW HEALTH   press %s", drinkHint = "Low mana: Alt+%s to eat and drink",
		afk = "Going AFK? Ctrl+%s: hide", noClass = "no list for this class yet",
		aMelee = "IN MELEE: Ctrl+%s  %s, then step back and %s", aNova = "IN MELEE: Shift+%s  %s", aLance = "FROZEN: step back, Shift+%s x2  %s + %s",
		aBack = "FROZEN: step back, %s", aCone = "WINTER'S CHILL x%d: close in, Ctrl+%s until %s",
		aShield = "%s: Ctrl+%s", aKey = "%s: %s%s", aNovaKey = "IN MELEE: %s  %s, then %s" },
	fi = { target = "%s: etsi kohde", fight = "%s: hyökkää", buff = "%s: buffaa (%s)", conjure = "%s: loihdi (%s)",
		hold = "ÄLÄ VEDÄ: liian vahva (%s). /okd brave on", dead = "Olet kuollut", mounted = "Ratsailla",
		cFight = "%s: taistele", cMany = "%d vihollista: paina %s tai pakene", run = "PAKENE!  %s",
		low = "VÄHÄN HP:TA   paina %s", drinkHint = "Mana vähissä: Alt+%s syö ja juo",
		afk = "Menossa AFK? Ctrl+%s: piiloon", noClass = "tälle luokalle ei vielä ole listaa",
		aMelee = "LÄHITAISTELU: Ctrl+%s  %s, sitten taakse ja %s", aNova = "LÄHITAISTELU: Shift+%s  %s", aLance = "JÄÄSSÄ: peräänny, Shift+%s x2  %s + %s",
		aBack = "JÄÄSSÄ: peräänny, %s", aCone = "WINTER'S CHILL x%d: lähelle, Ctrl+%s kunnes %s",
		aShield = "%s: Ctrl+%s", aKey = "%s: %s%s", aNovaKey = "LÄHITAISTELU: %s  %s, sitten %s" },
}
local function tr(key, ...)
	local t = TEXT[db and db.lang] or TEXT.en
	local f = t[key] or TEXT.en[key] or key
	if select("#", ...) > 0 then return f:format(...) end
	return f
end

local function apply(text, label)
	if hud then hud.text:SetText(label or "") end
	if locked() or text == current.text then return end
	current.text = text
	current.what = "out"
	for k, v in pairs(macros) do if v == text then current.what = k end end
	for _, v in pairs(fightBy) do if v == text then current.what = "fight" end end
	buttons.fight:SetAttribute("macrotext", text or "")
end

-- What F offers out of combat before the fight (a buff, the shield, the
-- weapon imbue, the opener) must never hold the key. A press that does not
-- help (no rage or mana, out of range, a debuff in the way) is tried once;
-- after it the key moves on, until the target changes or a fight ends.
-- The try is the first press of the fight key (key down, not the other
-- keys) after the offer came up; two seconds after it the offer is over,
-- however often the key is pressed in between. A spell the client says
-- cannot be cast now is not offered at all.
local tries = {}
local cooldownLeft

local onKey, pressedOffer -- the offer on the fight key now; the one its last press met

local function mayTry(tag, now)
	local t = tries[tag]
	if t and t.skip and now >= t.skip then t = nil end
	if not t then t = { offered = now } tries[tag] = t end
	if t.skip then return false end
	if not t.pressed and pressedOffer == tag and fightPress > t.offered then t.pressed = fightPress end
	-- given up: not again for five minutes (a buff someone else's stronger
	-- one keeps off would otherwise cost two seconds after every fight)
	if t.pressed and now - t.pressed > 2 then t.skip = now + 300 return false end
	return true
end

-- buffs the class keeps up; the first learned of each group
local function missingBuff(now)
	for _, group in ipairs(CL.buffs or {}) do
		for _, k in ipairs(group) do
			if known[k] then
				if hasBuff(N[k]) then tries["buff:" .. k] = nil
				elseif castable(N[k]) and mayTry("buff:" .. k, now) then return k end
				break
			end
		end
	end
end

-- the weapon imbue (shaman): the first learned of the list, when the main
-- hand has none
local function missingImbue(now)
	if not CL.imbue or not GetWeaponEnchantInfo then return nil end
	local ok, has = pcall(GetWeaponEnchantInfo)
	if not ok or secret(has) then return nil end
	if has then tries.imbue = nil return nil end
	for _, k in ipairs(CL.imbue) do
		if known[k] then return castable(N[k]) and mayTry("imbue", now) and k or nil end
	end
end

-- the class's shield before the pull (mage: Ice Barrier, priest: Power
-- Word: Shield)
local function wantShield(now)
	local k = CL.shield
	if not k or not known[k] then return false end
	local lvl = UnitLevel("player")
	if CL.shieldFrom and (secret(lvl) or type(lvl) ~= "number" or lvl < CL.shieldFrom) then return false end
	if hasBuff(N[k]) then tries.shield = nil return false end
	if CL.shieldBlock and hasDebuff(spellName(CL.shieldBlock)) then return false end
	if cooldownLeft(k, now) > 0 or not castable(N[k]) then return false end
	return mayTry("shield", now)
end

-- a spell with a cooldown that opens the fight (priest: Mind Blast). In
-- combat the key is the fight macro, which holds no cooldown spell.
local function wantOpener(now)
	local k = CL.opener
	if not k or not known[k] or cooldownLeft(k, now) > 0 or not castable(N[k]) then return false end
	return mayTry("opener", now)
end

-- How many opening casts fit before the slowing spell lands with the mob
-- still some way off. The mob starts to run when the first opener lands
-- and covers about 7 yards a second; a bolt flies about 22. From d yards,
-- with n openers of cOpen seconds each and the slow of cSlow seconds, the
-- slow lands while the mob is still 8 yards away when
--   n * cOpen + cSlow + 0.5 - (cOpen + d / 22) <= (d - 8) / 7
local function openerCount(d, cOpen, cSlow, max)
	if cOpen <= 0 then return 0 end
	local n = math.floor(((d - 8) / 7 + d / 22 - cSlow - 0.5) / cOpen + 1)
	return math.max(0, math.min(max, n))
end
ns.OneKeyOpenerCount = openerCount -- read by the tests

local function castSeconds(name, fallback)
	if name and C_Spell and C_Spell.GetSpellInfo then
		local ok, info = pcall(C_Spell.GetSpellInfo, name)
		if ok and type(info) == "table" and type(info.castTime) == "number" and not secret(info.castTime)
			and info.castTime > 0 then
			return info.castTime / 1000
		end
	end
	return fallback
end

local function reaches(key)
	if not (known[key] and C_Spell and C_Spell.IsSpellInRange) then return nil end
	local ok, r = pcall(C_Spell.IsSpellInRange, N[key], "target")
	if not ok or secret(r) or r == nil then return nil end
	return r == true or r == 1
end

-- The opener for this pull: /okd opener N when set, else by how far the
-- target is. The client only says which spells reach: the short one (Fire
-- Blast, 20 yd) means close, the slow (Frostbolt, 30 yd) the middle, only
-- the opener (Fireball, 35 yd) far. Returns the count and the distance used.
local function openerFor()
	local top = 0
	for n in pairs(fightBy) do if n > top then top = n end end
	if top == 0 then return 0 end
	if tonumber(db.opener) then return math.max(0, math.min(top, math.floor(tonumber(db.opener)))), nil end
	local O
	for _, e in ipairs(CL.fight or {}) do if e[1] == "opener" then O = e end end
	if not O then return 0 end
	local d
	if O.near and reaches(O.near) then d = 12
	elseif O.slow and reaches(O.slow) then d = 25
	elseif reaches(O[2]) then d = 32
	elseif reaches(O[2]) == false then d = 33 -- too far yet: the pull will be from the edge of the range
	else return math.min(top, 1), nil end -- the client does not say
	-- with no short-range spell learned "close" cannot be told from the
	-- middle: one opener at most
	if O.near and not known[O.near] then top = math.min(top, 1) end
	return openerCount(d, castSeconds(N[O[2]], 3), castSeconds(O.slow and N[O.slow], 2.5), math.min(top, O.count or 1)), d
end

local function decide()
	local key = db.key or "F"
	if UnitIsDeadOrGhost("player") then return "", tr("dead") end
	if IsMounted and IsMounted() then return "", tr("mounted") end
	local tk = targetKind()
	-- conjured water and food when the bags have none
	if CL.conjure then
		if not water and known[CL.conjure.water] then
			return "/cast " .. N[CL.conjure.water], tr("conjure", key, N[CL.conjure.water])
		end
		if not food and known[CL.conjure.food] then
			return "/cast " .. N[CL.conjure.food], tr("conjure", key, N[CL.conjure.food])
		end
	end
	local now = GetTime()
	local b = missingBuff(now)
	if b then return "/cast [@player] " .. N[b], tr("buff", key, N[b]), "buff:" .. b end
	b = missingImbue(now)
	if b then return "/cast " .. N[b], tr("buff", key, N[b]), "imbue" end
	if tk == "hostile" then
		local lvl, mine = UnitLevel("target"), UnitLevel("player")
		local class = UnitClassification and UnitClassification("target")
		if not (secret(lvl) or secret(mine) or secret(class)) and lvl and mine and not db.brave then
			local diff = lvl > 0 and (lvl - mine) or 99
			if diff >= 3 or class == "elite" or class == "rareelite" or class == "worldboss" then
				return "", "|cffff3030" .. tr("hold", diff < 99 and ("+" .. diff) or "??") .. "|r"
			end
		end
		if wantShield(now) then
			return "/cast [@player] " .. N[CL.shield], tr("buff", key, N[CL.shield]), "shield"
		end
		if wantOpener(now) then
			return TARGET .. "\n/cast [harm,nodead] " .. N[CL.opener], tr("fight", key), "opener"
		end
		local n = openerFor()
		if n > 0 and fightBy[n] then
			local O
			for _, e in ipairs(CL.fight or {}) do if e[1] == "opener" then O = e end end
			return fightBy[n], tr("fight", key) .. (" (%dx %s)"):format(n, N[O[2]])
		end
		return macros.fight, tr("fight", key)
	end
	-- No enemy: the press only picks one. The next update checks its level
	-- and class before the key will attack it.
	if tk ~= "unknown" then return TARGET, tr("target", key) end
	return macros.fight, tr("target", key)
end

---------------------------------------------------------------------------
-- HUD: the line, the game's own health and power, warnings, RUN AWAY
---------------------------------------------------------------------------

local function stepCurve(percent, below, above)
	if not (C_CurveUtil and C_CurveUtil.CreateColorCurve and CreateColor) then return end
	local ok, c = pcall(function()
		local c = C_CurveUtil.CreateColorCurve()
		if Enum and Enum.LuaCurveType and c.SetType then c:SetType(Enum.LuaCurveType.Step) end
		c:AddPoint(0, CreateColor(1, 1, 1, below))
		c:AddPoint(math.max(0.01, percent / 100), CreateColor(1, 1, 1, above))
		return c
	end)
	if ok then return c end
end

local function alphaFrom(frame, ok, color)
	if not ok or type(color) == "nil" then return false end
	local got, _, _, _, a = pcall(function() return color:GetRGBA() end)
	return got and pcall(frame.SetAlpha, frame, a) or false
end

local function powerType()
	local t = UnitPowerType and UnitPowerType("player")
	if secret(t) then return 0 end
	return t or 0
end

local function setWarn(w, isHealth)
	if not w or not w.frame or not w.curve then return end
	if isHealth then
		alphaFrom(w.frame, pcall(UnitHealthPercent, "player", false, w.curve))
	elseif powerType() == 0 then
		alphaFrom(w.frame, pcall(UnitPowerPercent, "player", 0, false, w.curve))
	else
		w.frame:SetAlpha(0)
	end
end

local function setVitals()
	if not hud then return end
	local scale = CurveConstants and CurveConstants.ScaleTo100
	local okH, hp = pcall(UnitHealthPercent, "player", false, scale)
	local pt = powerType()
	local okP, pw = pcall(UnitPowerPercent, "player", pt, false, scale)
	local label = pt == 0 and "MP" or pt == 1 and "Rage" or pt == 3 and "Energy" or "Power"
	local ok = okH and type(hp) ~= "nil" and pcall(function()
		if okP and type(pw) ~= "nil" then
			hud.vitals:SetFormattedText("|cffff6060HP %.0f%%|r |cff60a0ff" .. label .. " %.0f%%|r", hp, pw)
		else
			hud.vitals:SetFormattedText("|cffff6060HP %.0f%%|r", hp)
		end
	end)
	if not ok then hud.vitals:SetText("") end
end

local function attackers()
	if not (C_NamePlate and C_NamePlate.GetNamePlates) then return 0 end
	local ok, list = pcall(C_NamePlate.GetNamePlates)
	if not ok or type(list) ~= "table" then return 0 end
	local n = 0
	for _, plate in ipairs(list) do
		local okU, unit = pcall(function() return plate.namePlateUnitToken or (plate.UnitFrame and plate.UnitFrame.unit) end)
		if okU and type(unit) == "string" then
			local ok2, hostile, threat = pcall(function()
				return UnitCanAttack("player", unit), UnitThreatSituation and UnitThreatSituation("player", unit)
			end)
			if ok2 and not secret(hostile) and hostile and not secret(threat) and threat then n = n + 1 end
		end
	end
	return n
end

local function setNote()
	setVitals()
	local text
	local tk = targetKind()
	if not locked() then
		local lvl = UnitLevel("player")
		local zone = GetRealZoneText and GetRealZoneText()
		if tk == "hostile" then
			local name = UnitName("target")
			local qt = not secret(name) and ns.QH and ns.QH.ForMob and ns.QH.ForMob(name)
			if qt then text = "|cffffff00" .. (db.lang == "fi" and "Questiin: " or "Quest: ") .. qt .. "|r" end
		else
			local need = {}
			if not water and powerType() == 0 then need[#need + 1] = db.lang == "fi" and "ei juomaa" or "no water" end
			if not potion then need[#need + 1] = db.lang == "fi" and "ei parannuspottia" or "no healing potion" end
			if #need > 0 then text = "|cffffa040" .. table.concat(need, " · ") .. "|r" end
			if Logic and Logic.Route and lvl and zone then
				local advice = Logic.Route(lvl, zone)
				if advice then text = (text and (text .. "  ") or "") .. "|cff80ff80" .. advice .. "|r" end
			end
			local lastC = clicks[#clicks]
			if macros.hide and macros.hide ~= "" and not CL.hideIsSpell and lastC and GetTime() - lastC > 90 then
				text = (text and (text .. "  ") or "") .. "|cffffd060" .. tr("afk", db.sos or "G") .. "|r"
			end
			if ns.QH and ns.QH.Refresh and db.quests ~= false then
				if ns.QH.Age() > 5 then pcall(ns.QH.Refresh, lvl) end
				local okH, hint = pcall(ns.QH.Hint, db.lang == "fi")
				if okH and hint then text = (text and (text .. "\n") or "") .. "|cff66ccff" .. hint .. "|r" end
			end
		end
	elseif adds.n >= 2 then
		text = "|cffff4040" .. tr("cMany", adds.n, db.sos or "G") .. "|r"
	end
	if text ~= hud.noteText then hud.noteText = text hud.note:SetText(text or "") end
end

-- The freeze hint (mage): the key cannot test range or cooldowns (the
-- client gives macros no such conditions, and the macro is locked in
-- combat), so the HUD tells which key to press. It only shows text.
local lastCast = {}
local cdAtStart = {}
local readCooldowns
local chill = { n = 0, at = 0 }
cooldownLeft = function(key, now)
	local name = N[key]
	if not name then return 99 end
	if C_Spell and C_Spell.GetSpellCooldown then
		local ok, cd = pcall(C_Spell.GetSpellCooldown, name)
		if ok and type(cd) == "table" and not secret(cd.startTime) and not secret(cd.duration)
			and type(cd.startTime) == "number" and type(cd.duration) == "number" then
			-- the global cooldown is not the spell's own
			if cd.duration <= 1.5 then return 0, true end
			return math.max(0, cd.startTime + cd.duration - now), true
		end
	end
	local t = lastCast[key]
	local len = CL and ((CL.alert and CL.alert.cd and CL.alert.cd[key]) or (CL.cd and CL.cd[key])) or 0
	if t and len > 0 then return math.max(0, t + len - now), true end
	-- no cast seen in this fight: what the client said as the fight began
	local e = cdAtStart[key]
	if e then return math.max(0, e - now), true end
	-- nothing readable and no cast seen: "ready" is a guess (second value)
	return 0, false
end

-- As a fight begins the cooldowns are still plain values: keep where each
-- of the class's cooldown spells stands, for the fight's hints.
readCooldowns = function()
	cdAtStart = {}
	if not (CL and C_Spell and C_Spell.GetSpellCooldown) then return end
	local now = GetTime()
	for _, list in ipairs({ CL.alert and CL.alert.cd or {}, CL.cd or {} }) do
		for key in pairs(list) do
			local name = N[key]
			local ok, cd = false, nil
			if name then ok, cd = pcall(C_Spell.GetSpellCooldown, name) end
			if ok and type(cd) == "table" and not secret(cd.startTime) and not secret(cd.duration)
				and type(cd.startTime) == "number" and type(cd.duration) == "number" then
				cdAtStart[key] = cd.duration <= 1.5 and 0 or (cd.startTime + cd.duration)
			end
		end
	end
end

local lastOwnCast, shieldCast
local function noteCast(spellID)
	lastOwnCast = GetTime()
	if not CL or secret(spellID) or type(spellID) ~= "number" then return end
	local name
	if C_Spell and C_Spell.GetSpellName then
		local ok, n = pcall(C_Spell.GetSpellName, spellID)
		if ok and not secret(n) then name = n end
	end
	if not name then return end
	local now = GetTime()
	local W = CL.alert and CL.alert.chill
	for key, n in pairs(N) do
		if n == name then
			lastCast[key] = now
			if CL.alert and CL.alert.shield and CL.alert.shield.spell == key then shieldCast = now end
			if W then
				if key == W.spend then chill.n = 0 end
				for _, b in ipairs(W.build) do
					if key == b then chill.n, chill.at = math.min(W.stacks, chill.n + 1), now end
				end
			end
		end
	end
end

-- Winter's Chill is on the target and secret in combat, so the stacks are
-- counted from the player's own casts (a resist is not seen). They go with
-- the target, the fight, or 15 s without a new one.
local function chillStacks(now)
	local W = CL.alert and CL.alert.chill
	if not W or db.cone == false or not known[W.spend] then return 0 end
	local lvl = UnitLevel("player")
	if secret(lvl) or type(lvl) ~= "number" or lvl < W.level then return 0 end
	if now - chill.at > 15 then chill.n = 0 end
	return chill.n
end

-- Is the target within melee reach? The client's range check for a melee
-- spell, when it gives a plain answer; otherwise a hit taken in the last
-- 2.5 s. Text only: the key cannot change in combat.
local function inMelee(spellKey, now)
	if C_Spell and C_Spell.IsSpellInRange and N[spellKey] then
		local ok, r = pcall(C_Spell.IsSpellInRange, N[spellKey], "target")
		if ok and not secret(r) and r ~= nil then return r == true or r == 1 end
	end
	for i = #live.times, 1, -1 do
		if now - live.times[i] <= 2.5 then return true end
	end
	return false
end

-- Spells the fight key cannot hold, on the helper keys: a reactive spell
-- (usable only now and then: after a dodge, a parry, under 20 % health) is
-- named when the client says it can be used, a cooldown spell when it is
-- ready. Only the first that applies; only text.
local COMBO = { heal = "Shift+", cc = "Alt+", behind = "Ctrl+" }
local function keyHint(now)
	local key = db.key or "F"
	for _, r in ipairs(CL and CL.hints or {}) do
		local name = known[r.spell] and N[r.spell]
		local left, sure = 99, false
		if name and COMBO[r.key] and (macros[r.key] or ""):find(name, 1, true) then left, sure = cooldownLeft(r.spell, now) end
		if left == 0 then
			-- a cooldown spell is named only when its cooldown could be
			-- read or counted; a reactive one when the client says usable
			local show = not r.react and sure
			if r.react and C_Spell and C_Spell.IsSpellUsable then
				local ok, usable = pcall(C_Spell.IsSpellUsable, name)
				show = ok and not secret(usable) and usable == true
			end
			if show and targetKind() == "hostile" then return tr("aKey", name:upper(), COMBO[r.key], key) end
		end
	end
	return nil
end

-- A finisher with no combo point holds the rogue's sequence (two strikes
-- that both missed). Combo points are plain values: with none, and the
-- key pressed for five seconds without a cast, name the key that makes one.
local function stuckHint(now)
	local S = CL and CL.stuck
	if not S or not known[S.spell] or not GetComboPoints then return nil end
	local ok, cp = pcall(GetComboPoints, "player", "target")
	if not ok or secret(cp) or cp ~= 0 or targetKind() ~= "hostile" then return nil end
	-- seven seconds: longer than waiting for the energy of one strike
	if now - live.start < 7 or now - (lastOwnCast or 0) < 7 or now - fightPress > 2 then return nil end
	local left, sure = cooldownLeft(S.spell, now)
	if left > 0 or not sure then return nil end
	if C_Spell and C_Spell.IsSpellUsable then
		local okU, usable = pcall(C_Spell.IsSpellUsable, N[S.spell])
		if not okU or secret(usable) or usable ~= true then return nil end
	end
	return tr("aKey", (S.label or "NO COMBO POINT") .. ": " .. N[S.spell], COMBO[S.key] or "", db.key or "F")
end

local function alertText(now)
	local stuck = stuckHint(now)
	if stuck then return stuck end
	local key = db.key or "F"
	local H = CL and CL.meleeHint
	if H and known[H.spell] and inMelee(H.spell, now) then
		return tr("aMelee", key, N[H.spell], key)
	end
	local A = CL and CL.alert
	if not A or not known[A.freeze] then return keyHint(now) end
	local frozenAt = lastCast[A.freeze]
	if frozenAt and now - frozenAt < 8 then
		local left, sure = cooldownLeft(A.lance or "", now)
		if A.lance and known[A.lance] and left == 0 and sure then
			return tr("aLance", key, N[A.bolt] or "", N[A.lance])
		end
		return tr("aBack", key)
	end
	local hit = false
	for i = #live.times, 1, -1 do
		if now - live.times[i] <= 2.5 then hit = true break end
	end
	local fLeft, fSure = cooldownLeft(A.freeze, now)
	if hit and fLeft == 0 and fSure then
		-- the freeze is on the emergency key (mage), or on Shift+F
		if A.freezeKey ~= "sos" then return tr("aNova", key, N[A.freeze]) end
		-- the key's sequence starts over 25 s after its last press: until
		-- then its next press is not the freeze
		if db.sos and now - sosPress > 25 then
			return tr("aNovaKey", db.sos, N[A.freeze], known.blink and N.blink or key)
		end
	end
	local W = A.chill
	local wLeft, wSure = 99, false
	if W then wLeft, wSure = cooldownLeft(W.spend, now) end
	if W and chillStacks(now) >= W.stacks and wLeft == 0 and wSure then
		return tr("aCone", W.stacks, key, N[W.spend])
	end
	local S = A and A.shield
	if S and db.sos and known[S.spell] and macros.hide and macros.hide:find(N[S.spell], 1, true)
		and select(2, cooldownLeft(S.spell, now)) and cooldownLeft(S.spell, now) == 0
		and now - (shieldCast or -999) >= S.every
		and now - live.start >= 3 then
		return tr("aShield", N[S.spell], db.sos)
	end
	return keyHint(now)
end
local shownAlert
ns.OneKeyAlert = function() return shownAlert end -- read by the tests

local function updateAlert(now)
	if not hud or not hud.alert then return end
	local text = locked() and alertText(now) or nil
	if text ~= shownAlert then
		shownAlert = text
		hud.alert:SetText(text and ("|cff80d0ff" .. text .. "|r") or "")
	end
end

local runBox
local function updateRun(now)
	if not runBox then return end
	local n5 = 0
	for i = #live.times, 1, -1 do
		if now - live.times[i] <= 5 then n5 = n5 + 1 else table.remove(live.times, i) end
	end
	local strong = adds.n >= 3 or n5 >= 5 or (live.start > 0 and now - live.start > 45)
	if strong and locked() then
		runBox.text:SetText(tr("run", db.sos or "G"))
		runBox.box:Show()
		setWarn(runBox.w, true)
	else
		runBox.box:Hide()
	end
end

local function createHud()
	hud = CreateFrame("Frame", "OneKeyHud", UIParent)
	hud:SetSize(220, 22)
	local p = db.pos
	if p then hud:SetPoint(p[1], UIParent, p[2], p[3], p[4]) else hud:SetPoint("CENTER", UIParent, "CENTER", 0, -160) end
	hud:SetScale(db.scale or 1)
	hud.text = hud:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	hud.text:SetPoint("CENTER")
	hud.alert = hud:CreateFontString(nil, "OVERLAY", "GameFontNormalHuge")
	hud.alert:SetPoint("BOTTOM", hud, "TOP", 0, 40)
	hud.note = hud:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
	hud.note:SetPoint("BOTTOM", hud, "TOP", 0, -2)
	hud.vitals = hud:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
	hud.vitals:SetPoint("LEFT", hud.text, "RIGHT", 8, 0)
	local y = 0
	for _, w in ipairs({ { "low", 35, true, "GameFontNormalLarge" }, { "drink", 35, false, "GameFontNormalSmall" } }) do
		local f = CreateFrame("Frame", nil, hud)
		f:SetSize(240, 18)
		f:SetPoint("TOP", hud, "BOTTOM", 0, y)
		f:SetAlpha(0)
		local t = f:CreateFontString(nil, "OVERLAY", w[4])
		t:SetPoint("CENTER")
		warn[w[1]] = { frame = f, text = t, curve = stepCurve(w[2], 1, 0), health = w[3] }
		y = y - 20
	end
	warn.low.text:SetText("|cffff3030" .. tr("low", db.sos or "G") .. "|r")
	warn.drink.text:SetText("|cff60a0ff" .. tr("drinkHint", db.key or "F") .. "|r")
	local box = CreateFrame("Frame", nil, UIParent)
	box:SetSize(700, 90)
	box:SetPoint("CENTER", UIParent, "CENTER", 0, 170)
	box:SetFrameStrata("HIGH")
	box:Hide()
	local inner = CreateFrame("Frame", nil, box)
	inner:SetAllPoints(box)
	inner:SetAlpha(0)
	local t = inner:CreateFontString(nil, "OVERLAY")
	t:SetPoint("CENTER")
	if not pcall(t.SetFont, t, STANDARD_TEXT_FONT, 60, "THICKOUTLINE") then t:SetFontObject("GameFontNormalHuge") end
	t:SetTextColor(1, 0.1, 0.1)
	runBox = { box = box, text = t, w = { frame = inner, curve = stepCurve(60, 1, 0) } }
	hud:SetMovable(true)
	hud:EnableMouse(true)
	hud:RegisterForDrag("LeftButton")
	hud:SetScript("OnDragStart", function(f) if IsShiftKeyDown() then f:StartMoving() end end)
	hud:SetScript("OnDragStop", function(f)
		f:StopMovingOrSizing()
		local a, _, b, x, yy = f:GetPoint()
		db.pos = { a, b, x, yy }
	end)
end

---------------------------------------------------------------------------
-- Buttons and keys
---------------------------------------------------------------------------

-- after a /reload in combat the attributes wait for the fight to end
local secureLater = {}
local function secureButton(name)
	local b = CreateFrame("Button", name, UIParent, "SecureActionButtonTemplate")
	b:SetSize(1, 1)
	b:SetPoint("TOPLEFT", UIParent, "TOPLEFT", -10, 10)
	b:RegisterForClicks("AnyUp", "AnyDown")
	if locked() then
		secureLater[#secureLater + 1] = b
	else
		b:SetAttribute("type", "macro")
		b:SetAttribute("macrotext", "")
	end
	local what
	for k, v in pairs(NAMES) do if v == name then what = k end end
	b:HookScript("PreClick", function(_, _, down)
		clicks[#clicks + 1] = GetTime() if #clicks > 12 then table.remove(clicks, 1) end
		if what == "fight" and down ~= false then
			-- in a fight the key holds the fight macro, whatever was offered before it
			fightPress, pressedOffer = GetTime(), (not locked()) and onKey or nil
		end
		if what == "sos" and down ~= false then sosPress = GetTime() end
		-- a key held down clicks on both down and up; count one press
		if logEvent and down ~= false then logEvent("P", (what == "fight" and not locked()) and (current.what or "out") or what) end
	end)
	return b
end

local function bindKey()
	if locked() or not buttons.fight then return end
	ClearOverrideBindings(buttons.fight)
	local k = db.key or "F"
	SetOverrideBindingClick(buttons.fight, true, k, NAMES.fight, "LeftButton")
	SetOverrideBindingClick(buttons.fight, true, "SHIFT-" .. k, NAMES.heal, "LeftButton")
	SetOverrideBindingClick(buttons.fight, true, "ALT-" .. k, NAMES.cc, "LeftButton")
	SetOverrideBindingClick(buttons.fight, true, "CTRL-" .. k, NAMES.behind, "LeftButton")
	if db.sos then
		SetOverrideBindingClick(buttons.fight, true, db.sos, NAMES.sos, "LeftButton")
		SetOverrideBindingClick(buttons.fight, true, "SHIFT-" .. db.sos, NAMES.free, "LeftButton")
		SetOverrideBindingClick(buttons.fight, true, "CTRL-" .. db.sos, NAMES.hide, "LeftButton")
	end
end


---------------------------------------------------------------------------
-- Session log (same lines as the druid's, so tools/analyze_log.py reads it)
---------------------------------------------------------------------------
-- "seconds|code|fields": S start (epoch, level, xp, xp max, rested, zone),
-- C+ fight starts (target name, level, classification), C- fight ends
-- (seconds, xp, hits taken, most attackers), X xp (amount, kill|other),
-- A own spell cast, P key presses (key, count), D+/D- died/alive,
-- L level up, Z zone. Secret values are written as "?"; other players'
-- names as "player". /okd log on|off|clear.

local LOG_MAX = 8000
local lg = { t0 = 0, n = 0 }

local function plain(v)
	if v == nil or secret(v) then return "?" end
	return tostring(v)
end

local function flushPresses()
	if not lg.pressWhat then return end
	local lines = db.lines
	lines[#lines + 1] = ("%.1f|P|%s|%d"):format(lg.pressAt - lg.t0, lg.pressWhat, lg.pressCount)
	lg.pressWhat, lg.pressCount = nil, 0
end

logEvent = function(code, ...)
	if not db or not db.log or not db.lines or lg.t0 == 0 then return end
	if code == "P" then
		local what = ...
		if lg.pressWhat ~= what then
			flushPresses()
			lg.pressWhat, lg.pressCount, lg.pressAt = what, 0, GetTime()
		end
		lg.pressCount = lg.pressCount + 1
		return
	end
	flushPresses()
	local t = { ("%.1f"):format(GetTime() - lg.t0), code }
	for i = 1, select("#", ...) do t[#t + 1] = (plain((select(i, ...))):gsub("|", "/")) end
	local lines = db.lines
	lines[#lines + 1] = table.concat(t, "|")
	if #lines > LOG_MAX then
		local keep = {}
		for i = math.floor(LOG_MAX / 5) + 1, #lines do keep[#keep + 1] = lines[i] end
		db.lines = keep
	end
end

local function xpNow()
	local x, m = UnitXP and UnitXP("player"), UnitXPMax and UnitXPMax("player")
	if secret(x) or secret(m) then return nil end
	return x, m
end

local function logXp()
	local x, m = xpNow()
	if not x then return end
	if lg.xp then
		local gain = x - lg.xp
		if gain < 0 then gain = (lg.xpMax or 0) - lg.xp + x end
		if gain > 0 then
			if lg.inFight then lg.fightXp = lg.fightXp + gain end
			logEvent("X", gain, (lg.inFight or GetTime() - (lg.fightEnd or -9) < 3) and "kill" or "other", lg.lastName, lg.lastLevel)
		end
	end
	lg.xp, lg.xpMax = x, m
end

local function logTarget()
	if targetKind() ~= "hostile" then return nil end
	local name, lvl = UnitName("target"), UnitLevel("target")
	local class = UnitClassification and UnitClassification("target")
	local isPlayer = UnitIsPlayer and UnitIsPlayer("target")
	if isPlayer and not secret(isPlayer) then name = "player" end
	return plain(name), plain(lvl), plain(class)
end

local function logStart()
	db.lines = db.lines or {}
	lg.t0 = GetTime()
	lg.xp, lg.xpMax = xpNow()
	logEvent("S", time and time() or 0, UnitLevel("player"), lg.xp, lg.xpMax,
		GetXPExhaustion and GetXPExhaustion() or 0, GetRealZoneText and GetRealZoneText() or "?", CLASS, VERSION)
end

local function logCombat(on)
	if on then
		local name, lvl, class = logTarget()
		if name then lg.lastName, lg.lastLevel = name, lvl end
		lg.inFight, lg.fightAt, lg.fightXp, lg.hits, lg.most = true, GetTime(), 0, 0, 0
		logEvent("C+", name, lvl, class)
	elseif lg.inFight then
		lg.inFight, lg.fightEnd = false, GetTime()
		logEvent("C-", ("%.1f"):format(GetTime() - lg.fightAt), lg.fightXp, lg.hits, lg.most)
	end
end

local function logCast(spellID)
	if secret(spellID) or type(spellID) ~= "number" or not (C_Spell and C_Spell.GetSpellName) then return end
	local ok, name = pcall(C_Spell.GetSpellName, spellID)
	if ok and name and not secret(name) then logEvent("A", name) end
end
ns.OneKeyLog = function() return db and db.lines end -- read by the tests

---------------------------------------------------------------------------
-- Loop, alarm, events
---------------------------------------------------------------------------

local alarm = { on = false, n = 0 }
local function alarmTick()
	if not alarm.on then return end
	local last = clicks[#clicks] or 0
	-- the first tick runs on the combat event, just before the lock
	if (alarm.n > 0 and not locked()) or last > alarm.since or alarm.n >= 60 then alarm.on = false return end
	alarm.n = alarm.n + 1
	if PlaySound then pcall(PlaySound, 8959, "Master") end
	if FlashClientIcon then pcall(FlashClientIcon) end
	-- every 2 s for half a minute, then every 3 s for as long as the fight
	-- lasts, up to three minutes (22.11.: a wolf took 78 s to kill an AFK
	-- druid, and the alarm had stopped after 30 s)
	if C_Timer and C_Timer.After then C_Timer.After(alarm.n < 15 and 2 or 3, alarmTick) end
end

local function enterCombat()
	onKey, pressedOffer = nil, nil
	logCombat(true)
	lastCast = {}
	if readCooldowns then readCooldowns() end
	live.start, live.times = GetTime(), {}
	adds.warned = false
	if db.alarm ~= false and not alarm.on and GetTime() - (clicks[#clicks] or 0) >= 30 then
		alarm.on, alarm.n, alarm.since = true, 0, GetTime()
		alarmTick()
	end
	if not locked() then
		-- the fight macro chosen for this pull stays (its opener count);
		-- anything else on the key (a buff, the target line) gives way
		local chosen = false
		for _, t in pairs(fightBy) do if t == current.text then chosen = true end end
		if not chosen then
			current.text = macros.fight
			buttons.fight:SetAttribute("macrotext", macros.fight or "")
		end
	end
	if hud then hud.text:SetText(tr("cFight", db.key or "F")) end
end

local function update()
	if not ready or not CL then return end
	setWarn(warn.low, true)
	setWarn(warn.drink, false)
	if locked() then
		warn.drink.frame:Hide()
		local now = GetTime()
		if now - adds.at >= 0.5 then
			adds.at, adds.n = now, attackers()
			if lg.inFight and adds.n > lg.most then lg.most = adds.n end
			if adds.n >= 2 and not adds.warned then
				adds.warned = true
				if db.sound ~= false and PlaySound then pcall(PlaySound, 8959) end
			end
		end
		updateRun(now)
		updateAlert(now)
		setNote()
		return
	end
	warn.drink.frame:Show()
	if runBox then runBox.box:Hide() end
	updateAlert(GetTime())
	if bagsDirty then scanBags() bagsDirty, dirty = false, true end
	if dirty then rebuild() end
	local text, label, offer = decide()
	onKey = offer
	apply(text, label)
	setNote()
end

local function trackGathering()
	local M = C_Minimap
	if db.herbs == false or locked() or not (M and M.GetNumTrackingTypes and M.GetTrackingInfo and M.SetTracking) then return end
	local okN, n = pcall(M.GetNumTrackingTypes)
	if not okN or type(n) ~= "number" then return end
	local want = { [2383] = true, [2580] = true } -- Find Herbs, Find Minerals
	for i = 1, n do
		local ok, a, _, active, _, _, sid = pcall(M.GetTrackingInfo, i)
		if ok then
			local id, on = sid, active
			if type(a) == "table" then id, on = a.spellID, a.active end
			if id and want[id] then
				if not on then pcall(M.SetTracking, i, true) end
				return
			end
		end
	end
end

local driver = CreateFrame("Frame")
local elapsed = 0
driver:SetScript("OnEvent", function(_, event, arg1, arg2, arg3)
	if event == "ADDON_LOADED" then
		if arg1 ~= ADDON then return end
		OneKeyDruidDB = OneKeyDruidDB or {}
		db = OneKeyDruidDB
		if db.key == nil then db.key = "F" end
		if db.sos == nil then db.sos = "G" end
		-- English by default; 0.29 moves every character to it once
		-- (Finnish: /okd lang fi)
		if db.lang == nil or (db.langSet or 0) < 29 then db.lang, db.langSet = "en", 29 end
		-- the session log is on unless turned off (/okd log off)
		if db.log == nil then db.log = true end
	elseif event == "PLAYER_LOGIN" then
		if not CL then say(tr("noClass")) return end
		buttons.fight = secureButton(NAMES.fight)
		for key, name in pairs(NAMES) do if key ~= "fight" then buttons[key] = secureButton(name) end end
		createHud()
		bindKey()
		ready = true
		if db.log then logStart() end
		if C_Timer and C_Timer.After then C_Timer.After(3, trackGathering) end
		-- the alarm must be heard with the game in the background; the old
		-- setting is kept and comes back with /okd alarm off
		-- One key pressed again and again meets "not ready yet" and "target
		-- too close" all the time, and the game says each one out loud. The
		-- spoken error is off while the addon runs (the red text stays);
		-- /okd errorvoice on brings it back as it was.
		if db.errorvoice ~= true and SetCVar and GetCVar then
			local was = GetCVar("Sound_EnableErrorSpeech")
			if was ~= "0" then
				db.errorVoiceWas = was or "1"
				pcall(SetCVar, "Sound_EnableErrorSpeech", "0")
			end
		end
		if db.alarm ~= false and SetCVar and GetCVar then
			local was = GetCVar("Sound_EnableSoundWhenGameIsInBG")
			if was ~= "1" then
				db.bgSoundWas = was or "0"
				pcall(SetCVar, "Sound_EnableSoundWhenGameIsInBG", "1")
			end
		end
		say(("%s %s loaded: %s fights, Shift/Alt/Ctrl+%s help, %s emergency."):format(CLASS:lower(), VERSION,
			db.key, db.key, tostring(db.sos)))
	elseif not ready then
		return
	elseif event == "PLAYER_REGEN_DISABLED" then
		enterCombat()
	elseif event == "PLAYER_REGEN_ENABLED" then
		logCombat(false)
		current.text = nil
		adds.n = 0
		chill.n, tries.shield, tries.opener = 0, nil, nil
		if #secureLater > 0 then
			for _, b in ipairs(secureLater) do b:SetAttribute("type", "macro") end
			secureLater = {}
			rebuild()
		end
		bindKey()
	elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
		if arg1 == "player" then noteCast(arg3) logCast(arg3) end
	elseif event == "UNIT_COMBAT" then
		-- only damage taken counts as a hit (not heals, dodges or misses)
		if arg1 == "player" and arg2 == "WOUND" then
			live.times[#live.times + 1] = GetTime()
			if lg.inFight then lg.hits = lg.hits + 1 end
		end
	elseif event == "BAG_UPDATE_DELAYED" then
		bagsDirty = true
	elseif event == "MERCHANT_SHOW" then
		local need = {}
		if not water and powerType() == 0 and Logic and Logic.WaterFor and not (CL.conjure and known[CL.conjure.water]) then
			need[#need + 1] = (db.lang == "fi" and "vettä: " or "water: ") .. Logic.WaterFor(UnitLevel("player"))
		end
		if not potion then need[#need + 1] = "Healing Potion" end
		if #need > 0 then say((db.lang == "fi" and "osta: " or "buy: ") .. table.concat(need, " · ")) end
	elseif event == "PLAYER_XP_UPDATE" then
		logXp()
	elseif event == "PLAYER_DEAD" then
		logEvent("D+", lg.lastName, lg.lastLevel)
	elseif event == "ZONE_CHANGED_NEW_AREA" then
		logEvent("Z", GetRealZoneText and GetRealZoneText() or "?")
	elseif event == "PLAYER_TARGET_CHANGED" then
		chill.n, tries.shield, tries.opener = 0, nil, nil
		if not locked() then
			local name, lvl, class = logTarget()
			if name then lg.lastName, lg.lastLevel = name, lvl logEvent("T", name, lvl, class) end
		end
	elseif event == "PLAYER_UNGHOST" or event == "PLAYER_ALIVE" then
		if not UnitIsDeadOrGhost("player") then logEvent("D-") end
		if C_Timer and C_Timer.After then C_Timer.After(2, trackGathering) end
	else
		if event == "PLAYER_LEVEL_UP" then logEvent("L", arg1) end
		dirty = true
	end
end)
for _, e in ipairs({ "ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_REGEN_DISABLED", "PLAYER_REGEN_ENABLED",
	"BAG_UPDATE_DELAYED", "SPELLS_CHANGED", "PLAYER_LEVEL_UP", "PLAYER_ENTERING_WORLD", "MERCHANT_SHOW",
	"PLAYER_UNGHOST", "PLAYER_ALIVE", "QUEST_LOG_UPDATE", "PLAYER_XP_UPDATE", "PLAYER_DEAD",
	"ZONE_CHANGED_NEW_AREA", "PLAYER_TARGET_CHANGED", "PLAYER_EQUIPMENT_CHANGED" }) do
	pcall(driver.RegisterEvent, driver, e)
end
pcall(driver.RegisterUnitEvent, driver, "UNIT_COMBAT", "player")
pcall(driver.RegisterUnitEvent, driver, "UNIT_SPELLCAST_SUCCEEDED", "player")

driver:SetScript("OnUpdate", function(_, dt)
	elapsed = elapsed + dt
	if elapsed < 0.2 then return end
	elapsed = 0
	update()
end)

---------------------------------------------------------------------------
-- /okd
---------------------------------------------------------------------------

SLASH_ONEKEYDRUID1, SLASH_ONEKEYDRUID2 = "/okd", "/onekey"
SlashCmdList.ONEKEYDRUID = function(msg)
	local cmd, rest = (msg or ""):match("^%s*(%S*)%s*(.-)%s*$")
	cmd = (cmd or ""):lower()
	if cmd == "bind" and rest ~= "" then
		if locked() then say("not in combat.") return end
		local k, why = Logic.KeyName(rest)
		if not k then say(why) return end
		if k == db.sos then say(k .. " is the emergency key. Choose another key, or move it with /okd sos <key>.") return end
		db.key = k
		bindKey()
		say("key: " .. db.key)
	elseif cmd == "sos" and rest ~= "" then
		if locked() then say("not in combat.") return end
		if rest:lower() == "off" then
			db.sos = false
		else
			local k, why = Logic.KeyName(rest)
			if not k then say(why) return end
			if k == db.key then say(k .. " is the fight key. Choose another key.") return end
			db.sos = k
		end
		bindKey()
	elseif cmd == "lang" and (rest == "fi" or rest == "en") then
		db.lang = rest
	elseif cmd == "brave" then
		db.brave = rest:lower() == "on"
		say(db.brave and "the key pulls anything." or "the key will not pull mobs 3+ levels over you, elites or skulls.")
	elseif cmd == "errorvoice" then
		db.errorvoice = rest:lower() == "on"
		if SetCVar then
			if db.errorvoice then
				pcall(SetCVar, "Sound_EnableErrorSpeech", db.errorVoiceWas or "1")
				db.errorVoiceWas = nil
			else
				pcall(SetCVar, "Sound_EnableErrorSpeech", "0")
			end
		end
		say("error voice " .. (db.errorvoice and "on" or "off") .. ".")
	elseif cmd == "alarm" then
		db.alarm = rest:lower() ~= "off"
		if not db.alarm and db.bgSoundWas and SetCVar then
			pcall(SetCVar, "Sound_EnableSoundWhenGameIsInBG", db.bgSoundWas)
			db.bgSoundWas = nil
		end
	elseif cmd == "opener" then
		if locked() then say("not in combat.") return end
		local n = tonumber(rest)
		if rest:lower() == "auto" then db.opener = nil
		elseif n and n >= 0 and n <= 3 then db.opener = math.floor(n)
		else say("opener 0-3 — how many times the opening spell is cast before the filler; auto — by the distance to the target.") return end
		dirty = true
		say("opener: " .. (db.opener and tostring(db.opener) or "auto") .. ".")
	elseif cmd == "cone" then
		db.cone = rest:lower() ~= "off"
		say("Cone of Cold hint " .. (db.cone and "on" or "off") .. ".")
	elseif cmd == "herbs" then
		db.herbs = rest:lower() ~= "off"
		trackGathering()
	elseif cmd == "solo" and ns.QL and ns.QL.Slash then
		ns.QL.Slash(rest:lower())
	elseif cmd == "skip" and ns.QH and ns.QH.Skip then
		if rest:lower() == "clear" then ns.QH.ClearSkips() say("left-out quests are back.")
		else say("left out: " .. tostring(ns.QH.Skip() or "nothing")) end
	elseif cmd == "quests" and ns.QH and ns.QH.Refresh then
		pcall(ns.QH.Refresh, UnitLevel("player"))
		ns.QH.List(say, 5)
	elseif cmd == "go" and ns.QH and ns.QH.Go then
		pcall(ns.QH.Refresh, UnitLevel("player"))
		local ok, name = ns.QH.Go()
		say(ok and ("map pin and arrow: " .. tostring(name)) or "no place to point to.")
	elseif cmd == "where" and Logic and Logic.Route then
		local lvl, zone = UnitLevel("player"), GetRealZoneText and GetRealZoneText() or "?"
		local advice, fit = Logic.Route(lvl, zone)
		say(("level %d in %s. %s"):format(lvl, zone, advice or "This zone still fits."))
		for _, z in ipairs(fit) do say(("  %s (%d-%d)"):format(z[3], z[1], z[2])) end
	elseif cmd == "log" and (rest == "on" or rest == "off" or rest == "clear") then
		if rest == "clear" then db.lines = {} else db.log = rest == "on" end
		if db.log then logStart() end
		say("session log " .. (db.log and "on" or "off") .. ".")
	elseif cmd == "ranks" then
		if ns.Ranks then ns.Ranks.Slash(rest, say) end
	elseif cmd == "status" then
		say(("%s %s"):format(CLASS, VERSION))
		for _, k in ipairs({ "fight", "heal", "cc", "behind", "sos", "free", "hide" }) do
			say(k .. ":\n" .. tostring(macros[k]))
		end
	else
		say(VERSION .. " — " .. CLASS:lower())
		print("  bind KEY · sos KEY|off · lang en|fi · brave on|off · alarm on|off · herbs on|off · cone on|off · opener 0-3|auto")
		print("  solo [print|button] · quests · go · skip [clear] · where · status · ranks [on|off] · log on|off|clear")
	end
end
