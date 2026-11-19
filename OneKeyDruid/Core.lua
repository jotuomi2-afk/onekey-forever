-- OneKeyDruid/Core.lua: reads the game, asks Logic what the key should do,
-- and keeps the secure buttons' macros in step with the answer.
--
-- Four keys, four buttons: the key itself, and Shift, Alt and Ctrl with it,
-- each bound straight to a button of its own. The key's button changes only
-- out of combat (the client forbids it in combat); entering combat puts the
-- fight macro on it, which branches on form by itself.
--
-- WoW: Forever keeps health and mana secret from addons. The texts on screen
-- that say "low health" get their alpha from the game itself, through a step
-- curve (UnitHealthPercent, UnitPowerPercent); the addon never sees a number.

local ADDON, ns = ...
local Logic = ns.Logic

local _, CLASS = UnitClass("player")
if CLASS ~= "DRUID" then return end

local VERSION = "0.28.0"
local BUTTON = "OneKeyDruidButton"
-- The buttons of the modifier keys.
local NAMES = { heal = "OneKeyDruidHeal", cc = "OneKeyDruidStop", behind = "OneKeyDruidBehind",
	sos = "OneKeyDruidSOS", free = "OneKeyDruidFree", hide = "OneKeyDruidHide" }
local PREFIX = "|cff7fd4ffOneKey|r "

-- Each spell: id, English name, then alternatives the same way. An id only
-- serves to get the name on this client; the first one learned wins.
local SPELLS = {
	wrath = { 5176, "Wrath" }, moonfire = { 8921, "Moonfire" }, ht = { 5185, "Healing Touch" },
	rejuv = { 774, "Rejuvenation" }, regrowth = { 8936, "Regrowth" },
	motw = { 1126, "Mark of the Wild" }, thorns = { 467, "Thorns" }, omen = { 16864, "Omen of Clarity" },
	bear = { 5487, "Bear Form" }, direbear = { 9634, "Dire Bear Form" }, cat = { 768, "Cat Form" },
	travel = { 783, "Travel Form" }, aquatic = { 1066, "Aquatic Form" },
	hibernate = { 2637, "Hibernate" }, enrage = { 5229, "Enrage" }, grasp = { 16689, "Nature's Grasp" }, maul = { 6807, "Maul" }, roar = { 99, "Demoralizing Roar" }, bash = { 5211, "Bash" }, claw = { 1082, "Claw" }, rake = { 1822, "Rake" },
	rip = { 1079, "Rip" }, fb = { 22568, "Ferocious Bite" }, pounce = { 9005, "Pounce" },
	shred = { 5221, "Shred" }, ravage = { 6785, "Ravage" },
	ff = { 16857, "Faerie Fire (Feral)", 770, "Faerie Fire" },
	charge = { 49376, "Feral Charge - Cat", false, "Feral Charge (Cat)", 16979, "Feral Charge" },
	chargeBear = { 16979, "Feral Charge", false, "Feral Charge - Bear", false, "Feral Charge (Bear)" },
	shiftpower = { false, "Shifting Power" },
	roots = { 339, "Entangling Roots" },
	curePoison = { 8946, "Cure Poison" }, abolish = { 2893, "Abolish Poison" }, removeCurse = { 2782, "Remove Curse" },
	shadowmeld = { 20580, "Shadowmeld" }, prowl = { 5215, "Prowl" },
}
local FOOD_SPELL, DRINK_SPELL = 433, 430

local db
local N, known, forms = {}, {}, {}
local macros = { fight = "" }
local foodName, drinkName = "Food", "Drink"
local food, water, potion
local potionNames = { ["Healing Potion"] = true }  -- the names a healing potion's use effect goes by
local button, hud
local kids = {}        -- the modifier keys' buttons, by NAMES key
local clicks = {}      -- the last presses, for /okd status
local logEvent         -- set by the session log below
local current = {}     -- the key's macro now, and what it is for
local currentLabel
local dirty = true     -- spells, forms or settings changed: rebuild the macros
local manaSig, manaCheckAt -- the proven mana level, checked on every tick
local bagsDirty = true

local function say(msg) print(PREFIX .. msg) end

local function secret(v)
	return v ~= nil and issecretvalue ~= nil and issecretvalue(v) and true or false
end

local function plainText(v)
	if type(v) == "nil" then return "nil" end
	if issecretvalue ~= nil and issecretvalue(v) then return "secret" end
	return tostring(v)
end

local function locked()
	return InCombatLockdown and InCombatLockdown() and true or false
end

---------------------------------------------------------------------------
-- Reading the game
---------------------------------------------------------------------------

local function spellName(id)
	local n
	if C_Spell and C_Spell.GetSpellName then n = C_Spell.GetSpellName(id) end
	if not n and GetSpellInfo then n = GetSpellInfo(id) end
	return n
end

-- Learned: by id, or by name (a name answers only from the spellbook, and
-- covers the higher ranks, which have other ids).
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

local function readSpells()
	for key, list in pairs(SPELLS) do
		N[key], known[key] = nil, nil
		for i = 1, #list, 2 do
			local id, english = list[i], list[i + 1]
			local name = (id and spellName(id)) or english
			N[key] = N[key] or name
			if isKnown(id, name) then
				N[key], known[key] = name, true
				break
			end
		end
	end
	-- a passive spell (Omen of Clarity is a talent in WoW: Forever) is no
	-- buff to cast: without this the key would ask for it forever
	for _, key in ipairs({ "omen", "motw", "thorns" }) do
		if known[key] then
			local id = SPELLS[key][1]
			local passive = false
			if C_Spell and C_Spell.IsSpellPassive then
				local ok, v = pcall(C_Spell.IsSpellPassive, id)
				passive = ok and v and true or false
			elseif IsPassiveSpell then
				local ok, v = pcall(IsPassiveSpell, id)
				passive = ok and v and true or false
			end
			if passive then known[key] = nil end
		end
	end
	potionNames = { ["Healing Potion"] = true }
	for _, id in ipairs({ 439, 440, 441, 2024, 4042, 17534 }) do
		local n = spellName(id)
		if n then potionNames[n] = true end
	end
	foodName = spellName(FOOD_SPELL) or "Food"
	drinkName = spellName(DRINK_SPELL) or "Drink"
end

-- The stance bar's index of each form: it depends on the forms learned.
local function readForms()
	forms.B, forms.C, forms.T, forms.A = nil, nil, nil, nil
	for i = 1, (GetNumShapeshiftForms and GetNumShapeshiftForms() or 0) do
		local _, a, _, d = GetShapeshiftFormInfo(i)
		local name = type(a) == "string" and a or (d and spellName(d))
		if name == N.bear or name == N.direbear then forms.B = i
		elseif name == N.cat then forms.C = i
		elseif name == N.travel then forms.T = i
		elseif name == N.aquatic then forms.A = i end
	end
end

local function formNow()
	local i = GetShapeshiftForm and GetShapeshiftForm() or 0
	if secret(i) or not i or i == 0 then return "none" end
	if i == forms.B then return "bear" end
	if i == forms.C then return "cat" end
	if i == forms.T then return "travel" end
	if i == forms.A then return "aquatic" end
	return "other"
end

local function hasBuff(name)
	if not name then return false end
	if C_UnitAuras and C_UnitAuras.GetAuraDataBySpellName then
		local ok, a = pcall(C_UnitAuras.GetAuraDataBySpellName, "player", name, "HELPFUL")
		if ok then return a ~= nil end
	end
	if AuraUtil and AuraUtil.FindAuraByName then
		local ok, a = pcall(AuraUtil.FindAuraByName, name, "player", "HELPFUL")
		return ok and a ~= nil
	end
	return false
end

-- A buff counts as on only while it has more than `left` seconds to go, so
-- it is renewed before a pull rather than falling off in the middle of one.
local function buffLeft(name, left)
	if not name then return false end
	if C_UnitAuras and C_UnitAuras.GetAuraDataBySpellName then
		local ok, a = pcall(C_UnitAuras.GetAuraDataBySpellName, "player", name, "HELPFUL")
		if ok then
			if a == nil then return false end
			local exp = a.expirationTime
			if secret(exp) or not exp or exp == 0 then return true end
			return exp - GetTime() > left
		end
	end
	return hasBuff(name)
end

local function debuffs()
	local poison, curse = false, false
	for i = 1, 40 do
		local kind
		if C_UnitAuras and C_UnitAuras.GetAuraDataByIndex then
			local ok, a = pcall(C_UnitAuras.GetAuraDataByIndex, "player", i, "HARMFUL")
			if not ok or not a then break end
			kind = a.dispelName
		elseif UnitDebuff then
			local name, _, _, t = UnitDebuff("player", i)
			if not name then break end
			kind = t
		else
			break
		end
		if not secret(kind) then
			if kind == "Poison" then poison = true elseif kind == "Curse" then curse = true end
		end
	end
	return poison, curse
end

local function percent(cur, max)
	if secret(cur) or secret(max) or not cur or not max or max <= 0 then return nil end
	return cur / max * 100
end

-- The best food and water in the bags the character may use: the highest
-- required level. A setting (/okd food, /okd water) wins while it is in the bags.
local meat = nil -- raw meat to cook: { name, n }
local function scanBags()
	food, water, potion, meat = nil, nil, nil, nil
	local C = C_Container
	if not (C and C.GetContainerNumSlots and C.GetContainerItemID) then return end
	local itemSpell = (C_Item and C_Item.GetItemSpell) or GetItemSpell
	local itemInfo = (C_Item and C_Item.GetItemInfo) or GetItemInfo
	local level = UnitLevel("player") or 1
	local bestFood, bestWater, bestPotion = -1, -1, -1
	for bag = 0, 4 do
		for slot = 1, C.GetContainerNumSlots(bag) or 0 do
			local id = C.GetContainerItemID(bag, slot)
			if id then
				local spell = itemSpell and itemSpell(id)
				if not spell and itemInfo then
					local name, _, _, _, _, _, sub = itemInfo(id)
					if name and (sub == "Meat" or name:find("Meat") or name:find("Flank") or name:find("Haunch")) then
						local okI, info = pcall(C.GetContainerItemInfo, bag, slot)
						local n = okI and type(info) == "table" and info.stackCount or 1
						if not meat then meat = { name = name, n = 0 } end
						if meat.name == name then meat.n = meat.n + n end
					end
				end
				if spell and potionNames[spell] then
					local need = itemInfo and select(5, itemInfo(id)) or 0
					need = need or 0
					if need <= level and need > bestPotion then potion, bestPotion = id, need end
				elseif spell == foodName or spell == drinkName or id == db.food or id == db.water then
					local need = itemInfo and select(5, itemInfo(id)) or 0
					need = need or 0
					if need <= level then
						if id == db.food then food, bestFood = id, 999
						elseif id == db.water then water, bestWater = id, 999
						elseif spell == foodName and need > bestFood then food, bestFood = id, need
						elseif spell == drinkName and need > bestWater then water, bestWater = id, need end
					end
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

local state = { buffs = {} }
local owed = 0         -- heals the last fight earned (by hits taken)
-- Health missing, as an estimate: the game's damage meter says after each
-- fight what you took and what healed you; heals cast out of combat are
-- taken off by their tooltip amount. nil until the meter has been read.
local hpEst = { frac = nil, at = nil } -- health missing as a share of the maximum: it holds across forms
local function hpMax()
	local m = UnitHealthMax("player")
	if secret(m) or not m or m <= 0 then return nil end
	return m
end
-- Health comes back by itself out of combat: the estimate shrinks with time
-- (/okd hpregen N, percent of the maximum per second).
local function hpStep(now)
	if hpEst.frac and not locked() then
		local dt = hpEst.at and (now - hpEst.at) or 0
		if dt > 1 then dt = 1 end
		hpEst.frac = math.max(0, hpEst.frac - (db.hpregen or 0.005) * dt)
	end
	hpEst.at = now
end

-- Find Herbs on the minimap. Only one gathering track can be on at a time;
-- this turns herbs on at login and after a death, and leaves it alone
-- otherwise, so a choice made by hand stands. /okd herbs on|off.
local HERB_SPELL = 2383
local function trackHerbs()
	if db.herbs == false or locked() then return end
	local M = C_Minimap
	if not (M and M.GetNumTrackingTypes and M.GetTrackingInfo and M.SetTracking) then return end
	local okN, n = pcall(M.GetNumTrackingTypes)
	if not okN or type(n) ~= "number" then return end
	local herbName = spellName(HERB_SPELL)
	for i = 1, n do
		local ok, a, b, active, d, e, spellId = pcall(M.GetTrackingInfo, i)
		if ok then
			local name, sid, on = a, spellId, active
			if type(a) == "table" then name, sid, on = a.name, a.spellID, a.active end
			if (sid == HERB_SPELL or (herbName and name == herbName) or name == "Find Herbs") then
				if not on then pcall(M.SetTracking, i, true) end
				return true
			end
		end
	end
end

local function readState()
	local s = state
	s.cfg, s.known = db, known
	s.mode = Logic.Mode(db, known)
	s.hp = percent(UnitHealth("player"), UnitHealthMax("player"))
	s.mana = percent(UnitPower("player", 0), UnitPowerMax("player", 0))
	s.form = formNow()
	s.target = targetKind()
	s.dead = UnitIsDeadOrGhost("player") and true or false
	s.mounted = IsMounted and IsMounted() and true or false
	s.taxi = UnitOnTaxi and UnitOnTaxi("player") and true or false
	s.eating, s.drinking = hasBuff(foodName), hasBuff(drinkName)
	s.hasFood, s.hasWater = food ~= nil, water ~= nil
	s.owed = owed
	if s.eating then
		owed = 0
		if hpEst.frac then hpEst.frac = 0 end
	end
	s.maxhp, s.expect = UnitHealthMax("player"), nil
	if secret(s.maxhp) then s.maxhp = nil end
	s.deficit = hpEst.frac and s.maxhp and hpEst.frac * s.maxhp or nil
	if s.target == "hostile" and hpEst.frac then
		local name, lvl = UnitName("target"), UnitLevel("target")
		if not secret(name) and not secret(lvl) and name then
			local m = db.mobs and (db.mobs[tostring(name) .. "#" .. tostring(lvl)] or db.mobs["#" .. tostring(lvl)])
			if m and (m.tn or 0) > 0 then s.expect = m.tk / m.tn end
		end
	end
	local b = s.buffs
	b.motw, b.thorns, b.omen = buffLeft(N.motw, 300), buffLeft(N.thorns, 60), hasBuff(N.omen)
	b.rejuv, b.regrowth, b.abolish = hasBuff(N.rejuv), hasBuff(N.regrowth), hasBuff(N.abolish)
	s.poison, s.curse = debuffs()
	return s
end

---------------------------------------------------------------------------
-- The button
---------------------------------------------------------------------------

-- The main line says what to do next, with the key to press. Two
-- languages: /okd lang fi|en.
local TEXT = {
	en = {
		dead = "You are dead", mounted = "Mounted", wait = "Resting: stay seated", eat = "%s: eat", drink = "%s: drink",
		target = "%s: find a target", fight = "%s: attack", danger = "%s: attack (dangerous target)",
		nuke = "%s: attack with spells (weak target)",
		heal = "%s: heal first (%s)", cure = "%s: cure (%s)", buff = "%s: buff (%s)",
		cFight = "%s: hit", cFinish = "%s: finish it", cForm = "%s: back to your form",
		cHits = "Many hits taken: Shift+%s to heal", cTwo = "2 enemies: Alt+%s stops one, %s if it gets bad",
		cMany = "%d enemies: press %s or run", mHeal = "Shift held: healing", mStop = "Alt held: stop the mob",
		mRest = "Alt held: eat and drink", mLeave = "Ctrl held: leave the form", mBehind = "Ctrl held: leave form / attack from behind",
		low = "LOW HEALTH   press %s", lowNoSos = "LOW HEALTH   Shift+%s", healHint = "Heal: Shift+%s", drinkHint = "Low mana: Alt+%s to drink",
		enemies = "%d ENEMIES", run = "RUN AWAY!  %s", catProwl = "%s: Prowl", toBear = "bear: Shift+%s", catOpen = "%s: from behind Ravage/Shred, else Claw", hold = "DO NOT PULL: too strong (%s). /okd brave on",
		afk = "Going AFK? Ctrl+%s: Shadowmeld", mHide = "Ctrl held: hide (Shadowmeld)",
	},
	fi = {
		dead = "Olet kuollut", mounted = "Ratsailla", wait = "Lepää: pysy istumassa", eat = "%s: syö", drink = "%s: juo",
		target = "%s: etsi kohde", fight = "%s: hyökkää", danger = "%s: hyökkää (vaarallinen kohde)",
		nuke = "%s: hyökkää loitsuilla (heikko kohde)",
		heal = "%s: paranna ensin (%s)", cure = "%s: poista (%s)", buff = "%s: buffaa (%s)",
		cFight = "%s: lyö", cFinish = "%s: viimeistele", cForm = "%s: takaisin muotoon",
		cHits = "Paljon osumia: Shift+%s parantaa", cTwo = "2 vihollista: Alt+%s pysäyttää yhden, %s jos pahenee",
		cMany = "%d vihollista: paina %s tai pakene", mHeal = "Shift pohjassa: parannat", mStop = "Alt pohjassa: pysäytä kohde",
		mRest = "Alt pohjassa: syö ja juo", mLeave = "Ctrl pohjassa: muodosta pois", mBehind = "Ctrl pohjassa: muodosta pois / lyö takaa",
		low = "VÄHÄN HP:TA   paina %s", lowNoSos = "VÄHÄN HP:TA   Shift+%s", healHint = "Paranna: Shift+%s", drinkHint = "Mana vähissä: Alt+%s juo",
		enemies = "%d VIHOLLISTA", run = "PAKENE!  %s", catProwl = "%s: hiivi (Prowl)", toBear = "karhuksi: Shift+%s", catOpen = "%s: takaa Ravage/Shred, muuten Claw", hold = "ÄLÄ VEDÄ: liian vahva (%s). /okd brave on",
		afk = "Menossa AFK? Ctrl+%s: Shadowmeld", mHide = "Ctrl pohjassa: piiloon (Shadowmeld)",
	},
}
-- the notes come from Logic in English; in Finnish their words are swapped
local FI_WORDS = {
	{ "no healing potion", "ei parannuspottia" }, { "no food", "ei ruokaa" }, { "no water", "ei juomaa" }, { "repair", "korjaa varusteet" },
	{ "bags full", "laukut täynnä" }, { "ELITE", "ELIITTI" }, { "BOSS", "POMO" }, { "level %?%?", "taso ??" },
	{ "(%+%d+) levels?", "%1 tasoa" }, { "tapped: no XP", "toisen: ei XP:tä" }, { "grey: no XP", "harmaa: ei XP:tä" },
	{ "~(%d+) XP in (%d+) s", "~%1 XP, %2 s" }, { ", low", ", heikko" },
	{ "(.-) is low for you: go to ", "%1 on sinulle matala: mene " }, { " or ", " tai " },
}

local function tr(key, ...)
	local t = TEXT[db and db.lang] or TEXT.en
	local f = t[key] or TEXT.en[key] or key
	if select("#", ...) > 0 then return f:format(...) end
	return f
end

local function trNote(text)
	if not text or not db or db.lang ~= "fi" then return text end
	for _, w in ipairs(FI_WORDS) do text = text:gsub(w[1], w[2]) end
	return text
end

-- what the fight looks like so far, for the advice in combat
local live = { hits = 0, at = 0, times = {}, start = 0, lastKill = nil }

local function setHud(text)
	if hud and hud.text and text ~= currentLabel then
		currentLabel = text
		hud.text:SetText(text)
	end
end

-- Sets the key's macro (out of combat only).
local function apply(text, label, what)
	setHud(label)
	current.what = what
	if locked() or text == current.text then return end
	current.text = text
	button:SetAttribute("macrotext", text)
end

local MODS = { { "SHIFT-", "heal" }, { "ALT-", "cc" }, { "CTRL-", "behind" } }

-- Does this client act on key down?
local function keyDown()
	local f = (C_CVar and C_CVar.GetCVarBool) or GetCVarBool
	return f and f("ActionButtonUseKeyDown") and true or false
end

-- Mana is secret, but two things about it are not: what a spell costs, and
-- whether the game says there is enough mana for it. A spell that can be
-- cast proves mana is at least its cost (lb); the macros are built so that
-- the form can always be re-entered after the optional caster spells.
local function manaCost(name)
	if not name or not (C_Spell and C_Spell.GetSpellPowerCost) then return nil end
	local ok, t = pcall(C_Spell.GetSpellPowerCost, name)
	if not ok or type(t) ~= "table" then return nil end
	for _, p in ipairs(t) do
		if type(p) == "table" and (p.type == 0 or p.name == "MANA") and p.cost and not secret(p.cost) then return p.cost end
	end
	return nil
end

local function manaEnough(name)
	local f = C_Spell and C_Spell.IsSpellUsable
	if not name or not f then return nil end
	local ok, usable, noMana = pcall(f, name)
	if not ok or secret(usable) or secret(noMana) then return nil end
	if usable then return true end
	if noMana then return false end
	return nil
end

-- The estimate errs low: it starts from what the game proves (lb), loses
-- the cost of every cast, and gains only a slow regeneration out of combat
-- (/okd manaregen N, mana per second) and while drinking.
local manaState = { v = nil, at = nil, lastCast = 0 }

-- Mana per second assumed out of combat: what has been measured, with a
-- margin, else the setting.
local function manaRate()
	if db.manaregenLearned then return db.manaregenLearned * 0.85 end
	return db.manaregen or 2.5
end

local function manaStep()
	local now = GetTime()
	local dt = manaState.at and (now - manaState.at) or 0
	manaState.at = now
	if dt > 1 then dt = 1 end
	local v = manaState.v or 0
	local rate = 0
	if hasBuff(drinkName) then rate = 10
	elseif not locked() and now - manaState.lastCast > 5 then rate = manaRate() end
	manaState.v = v + rate * dt
end

local function manaEstimate(m)
	local max = UnitPowerMax and UnitPowerMax("player", 0)
	if secret(max) or not max or max <= 0 then max = nil end
	local v = manaState.v or 0
	if m.lb and v < m.lb then v = m.lb end
	if m.ub and v >= m.ub then v = m.ub - 1 end
	if max and v > max then v = max end
	manaState.v = v
	return v
end

-- Anchors: when a spell that could not be cast a second ago can be cast
-- now, mana has just reached its cost, to within a second of regeneration.
-- That corrects the estimate (down as well as up), and two anchors with no
-- cast between them measure the regeneration.
local function manaAnchor(m, now)
	local prev, prevAt = manaState.prev, manaState.prevAt
	local cur, best = {}, nil
	for _, f in ipairs(m.flags or {}) do
		cur[f.name] = f.ok
		if prev and prev[f.name] == false and f.ok == true and manaState.lastCast <= (prevAt or 0) then
			if not best or f.cost > best then best = f.cost end
		end
	end
	manaState.prev, manaState.prevAt = cur, now
	if not best then return end
	local a0 = manaState.anchor
	if a0 and manaState.lastCast <= a0.t and best > a0.c and now - a0.t >= 2 and not locked() then
		local rate = (best - a0.c) / (now - a0.t)
		if rate >= 0.5 and rate <= 25 then
			local old = db.manaregenLearned or rate
			db.manaregenLearned = 0.7 * old + 0.3 * rate
		end
	end
	manaState.anchor = { c = best, t = now }
	manaState.v = best
end

local manaFrame = CreateFrame("Frame")
pcall(manaFrame.RegisterUnitEvent, manaFrame, "UNIT_SPELLCAST_SUCCEEDED", "player")
pcall(manaFrame.RegisterEvent, manaFrame, "PLAYER_DEAD")
manaFrame:SetScript("OnEvent", function(_, event, _, _, spellId)
	if event == "PLAYER_DEAD" then manaState.v = 0 return end
	if secret(spellId) or not spellId then return end
	manaState.lastCast = GetTime()
	local cost = manaCost(spellId)
	if cost and manaState.v then manaState.v = math.max(0, manaState.v - cost) end
end)

local function manaInfo()
	local m = { cost = {}, lb = nil, ub = nil }
	local formName = known.direbear and N.direbear or N.bear
	if Logic.Mode(db, known) == "cat" and known.cat then formName = N.cat end
	m.cost.form = manaCost(formName)
	m.cost.rejuv, m.cost.moonfire, m.cost.wrath = manaCost(N.rejuv), manaCost(N.moonfire), manaCost(N.wrath)
	m.flags = {}
	for _, name in ipairs({ N.ht, N.regrowth, N.rejuv, N.moonfire, N.wrath, formName }) do
		local cost, ok = manaCost(name), manaEnough(name)
		if cost then m.flags[#m.flags + 1] = { name = name, cost = cost, ok = ok } end
		if cost and ok == true and (not m.lb or cost > m.lb) then m.lb, m.probe = cost, name end
		if cost and ok == false and (not m.ub or cost < m.ub) then m.ub = cost end
	end
	m.est = manaEstimate(m)
	return m
end

local function items()
	local cvar = (C_CVar and C_CVar.GetCVarBool) or GetCVarBool
	return { food = food, water = water, potion = potion, mana = db.manasafe ~= false and manaInfo() or nil,
		selfcast = cvar and cvar("autoSelfCast") and true or false }
end

local function rebuild()
	if locked() then return end
	readSpells()
	readForms()
	macros = Logic.BuildMacros(known, N, forms, Logic.Mode(db, known), db, items())
	kids.heal:SetAttribute("macrotext", macros.heal or "")
	kids.cc:SetAttribute("macrotext", macros.cc or "")
	kids.behind:SetAttribute("macrotext", macros.behind or "")
	kids.sos:SetAttribute("macrotext", macros.sos or "")
	kids.free:SetAttribute("macrotext", macros.free or "")
	kids.hide:SetAttribute("macrotext", macros.hide or "")
	current.text = nil
	dirty = false
end

local function heldMod()
	if IsShiftKeyDown() then return "heal" end
	if IsAltKeyDown() then return "cc" end
	if IsControlKeyDown() then return "behind" end
end

local function modLabel(mod)
	if mod == "heal" then return tr("mHeal") end
	if mod == "cc" then
		if not locked() and targetKind() ~= "hostile" and (food or water) then return tr("mRest") end
		return tr("mStop")
	end
	return macros.behindIsShred and tr("mBehind") or tr("mLeave")
end

---------------------------------------------------------------------------
-- Warnings: texts whose alpha the game sets from health and mana
---------------------------------------------------------------------------

local warn = {}        -- low, heal, drink: { frame, curve, at }
local gauge = "none"   -- how the warnings are driven: curve | number | none

-- Alpha `below` under `percent`, `above` from there on.
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

-- The colour's alpha may be secret: it goes straight to SetAlpha, unread.
local function alphaFrom(frame, ok, color)
	if not ok or type(color) == "nil" then return false end
	local got, _, _, _, a = pcall(function() return color:GetRGBA() end)
	return got and pcall(frame.SetAlpha, frame, a) or false
end

-- w: { frame, curve, at, below, above }. Sets the frame's alpha to `below`
-- or `above` by health (or mana) against w.at; `unknown` where neither the
-- game nor a number can tell.
local function setWarn(w, isHealth, unknown)
	if not w.frame then return end
	if w.at <= 0 then w.frame:SetAlpha(w.above) return end
	if w.curve then
		local ok
		if isHealth then
			ok = UnitHealthPercent and alphaFrom(w.frame, pcall(UnitHealthPercent, "player", false, w.curve))
		elseif UnitPowerPercent then
			ok = alphaFrom(w.frame, pcall(UnitPowerPercent, "player", 0, false, w.curve))
				or alphaFrom(w.frame, pcall(UnitPowerPercent, "player", 0, w.curve))
		end
		if ok then gauge = "curve" return end
	end
	local v
	if isHealth then v = percent(UnitHealth("player"), UnitHealthMax("player"))
	else v = percent(UnitPower("player", 0), UnitPowerMax("player", 0)) end
	if v then
		gauge = "number"
		w.frame:SetAlpha(v < w.at and w.below or w.above)
	else
		w.frame:SetAlpha(unknown or 0)
	end
end

local light             -- the ready light: { red, hp = w, mana = w }
local questDirty = true -- the quest log changed: work out the next step again
local lastHint          -- the quest hint last shown (logged when it changes)
local runBox            -- the RUN AWAY texts, one per danger level
local RUN_AT = { 65, 50 } -- health percent below which each level shows

local function buildWarnings()
	local key = db.key or "key"
	local function make(name, at, text)
		local w = warn[name]
		w.at, w.below, w.above = at, 1, 0
		w.curve = stepCurve(at, 1, 0)
		w.text:SetText(text)
	end
	make("low", db.panic, "|cffff3030" .. (db.sos and tr("low", db.sos) or tr("lowNoSos", key)) .. "|r")
	make("heal", db.heal, "|cffffd060" .. tr("healHint", key) .. "|r")
	make("drink", db.drink, "|cff60b0ff" .. tr("drinkHint", key) .. "|r")
	if light then
		-- Green needs both: health from `heal` up, mana from `drink` up.
		light.hp.at, light.hp.curve = db.heal, stepCurve(db.heal, 0, 1)
		light.mana.at, light.mana.curve = db.drink, stepCurve(db.drink, 0, 1)
	end
end

local function updateWarnings()
	if not warn.low then return end
	setWarn(warn.low, true)
	setWarn(warn.heal, true)
	setWarn(warn.drink, false)
	-- Drinking is for between fights.
	if locked() then warn.drink.frame:Hide() else warn.drink.frame:Show() end
	if light and light.red:IsShown() then
		setWarn(light.hp, true, 1)
		setWarn(light.mana, false, 1)
	end
end

-- The ready light, out of combat. Red lies under green. Green is two
-- nested frames, one with its alpha from health and one from mana, so it
-- covers the red only when both are above their thresholds. `ready` is what
-- the addon itself knows (buffs up, nothing to cure).
local function setLight(show, ready)
	if not light then return end
	if not show or not db.light then light.red:Hide() return end
	light.red:Show()
	if ready then light.hp.frame:Show() else light.hp.frame:Hide() end
end

local SEV = { red = "|cffff4040", yellow = "|cffffd060", grey = "|cff999999" }

-- Enemies with a nameplate that have you on their threat list (or, where
-- that cannot be read, that are fighting): the size of the pull.
local function attackers()
	if not (C_NamePlate and C_NamePlate.GetNamePlates) then return 0 end
	local ok, list = pcall(C_NamePlate.GetNamePlates)
	if not ok or type(list) ~= "table" then return 0 end
	local n = 0
	for _, plate in ipairs(list) do
		-- a nameplate may be off limits to addons: reading it then raises
		local okU, unit = pcall(function()
			return plate.namePlateUnitToken or (plate.UnitFrame and plate.UnitFrame.unit)
		end)
		if okU and type(unit) == "string" then
			local ok2, hostile, threat, fighting = pcall(function()
				return UnitCanAttack("player", unit), UnitThreatSituation and UnitThreatSituation("player", unit),
					UnitAffectingCombat(unit)
			end)
			if ok2 and not secret(hostile) and hostile then
				if UnitThreatSituation and not secret(threat) then
					if type(threat) ~= "nil" then n = n + 1 end
				elseif not secret(fighting) and fighting then
					n = n + 1
				end
			end
		end
	end
	return n
end

local adds = { n = 0, at = 0, warned = false }

-- name#level, and #level for any mob of that level
-- the best XP rate of any level, worked out again only after a new sample
-- (this runs several times a second in a fight)
local bestRate, bestDirty = nil, true
local function mobStats(name, lvl)
	local mobs = db.mobs
	if not mobs then return nil end
	if bestDirty then
		bestRate, bestDirty = nil, false
		for key, m in pairs(mobs) do
			if key:sub(1, 1) == "#" and m.n >= 2 and m.time > 0 then
				local rate = m.xp / m.time
				if not bestRate or rate > bestRate then bestRate = rate end
			end
		end
	end
	return mobs[tostring(name) .. "#" .. tostring(lvl)] or mobs["#" .. tostring(lvl)], bestRate
end

-- The real health and mana percent from the game itself. The value is secret:
-- it goes straight into the text, unread (as the DPS window does).
local function setVitals()
	if not hud or not hud.vitals then return end
	local fs = hud.vitals
	local scale = CurveConstants and CurveConstants.ScaleTo100
	local okH, hpv = false, nil
	if UnitHealthPercent then
		okH, hpv = pcall(UnitHealthPercent, "player", false, scale)
		if not okH or type(hpv) == "nil" then okH, hpv = pcall(UnitHealthPercent, "player") end
	end
	local okM, mpv = false, nil
	if UnitPowerPercent then
		okM, mpv = pcall(UnitPowerPercent, "player", 0, false, scale)
		if not okM or type(mpv) == "nil" then okM, mpv = pcall(UnitPowerPercent, "player", 0) end
	end
	-- the addon's own mana estimate, in grey, to check it against the real figure
	local tail = ""
	local pmax = UnitPowerMax and UnitPowerMax("player", 0)
	if manaState and manaState.v and manaState.low and pmax and not secret(pmax) and pmax > 0 then
		tail = (" |cff888888~%d%%|r"):format(math.floor(manaState.v / pmax * 100 + 0.5)):gsub("%%", "%%%%")
	end
	local shown = false
	if okH and type(hpv) ~= "nil" then
		local mul = scale and 1 or 100 -- without the scale curve the game gives 0..1
		local ok = pcall(function()
			if mul == 1 then
				fs:SetFormattedText("|cffff6060HP %.0f%%|r", hpv)
			elseif not secret(hpv) then
				-- no scale curve: only a plain number may be scaled, never a secret
				fs:SetFormattedText("|cffff6060HP %.0f%%|r", hpv * 100)
			else
				error("no scale curve for a secret value")
			end
		end)
		shown = ok
	end
	if not shown then fs:SetText("") end
	hud.hpShown = shown
	if okM and type(mpv) ~= "nil" and shown then
		pcall(function()
			local cur = fs:GetText() or ""
			if scale then fs:SetFormattedText("|cffff6060HP %.0f%%|r |cff60a0ffMP %.0f%%|r" .. tail, hpv, mpv)
			elseif not (secret(hpv) or secret(mpv)) then
				fs:SetFormattedText("|cffff6060HP %.0f%%|r |cff60a0ffMP %.0f%%|r" .. tail, hpv * 100, mpv * 100)
			end
		end)
	end
end

-- The line above the main text: the target's danger, else what to buy.

-- XP per hour over the last 15 minutes (or the session, if shorter), the
-- time to the next level at that rate, and the rested pool.
local xpm = { list = {}, last = nil, lastMax = nil, start = nil }
local function xpGain()
	local cur, max = UnitXP("player"), UnitXPMax("player")
	if secret(cur) or secret(max) or not cur then return end
	local now = GetTime()
	xpm.start = xpm.start or now
	if xpm.last then
		local d = cur - xpm.last
		if d < 0 and xpm.lastMax then d = xpm.lastMax - xpm.last + cur end -- a new level
		if d > 0 then xpm.list[#xpm.list + 1] = { now, d } end
	end
	xpm.last, xpm.lastMax = cur, max
end

local function xpLine()
	local now = GetTime()
	xpGain() -- picks up any change since the last look
	if not xpm.start then return nil end
	while xpm.list[1] and now - xpm.list[1][1] > 900 do table.remove(xpm.list, 1) end
	local sum = 0
	for _, e in ipairs(xpm.list) do sum = sum + e[2] end
	local span = math.min(900, now - xpm.start)
	if span < 60 then return nil end
	local rate = sum / span * 3600
	local cur, max = UnitXP("player"), UnitXPMax("player")
	local rested = GetXPExhaustion and GetXPExhaustion()
	if secret(cur) or secret(max) or secret(rested) then return nil end
	local fi = db.lang == "fi"
	local s = ("XP/h %d"):format(math.floor(rate / 100 + 0.5) * 100)
	if rate > 0 and max and cur then
		local mins = (max - cur) / rate * 60
		s = s .. (fi and " · tasoon %d min" or " · level in %d min"):format(math.floor(mins + 0.5))
	end
	if rested and rested > 0 then s = s .. (" · rested %d"):format(rested) end
	return s
end

local function setNote(s)
	setVitals()
	if hud.xp then
		local okX, line = pcall(xpLine)
		hud.xp:SetText(okX and line or "")
	end
	if not hud or not hud.note then return end
	local text
	if s.target == "hostile" then
		local lvl, mine = UnitLevel("target"), UnitLevel("player")
		local class = UnitClassification and UnitClassification("target")
		local trivial = UnitIsTrivial and UnitIsTrivial("target")
		local tapped = UnitIsTapDenied and UnitIsTapDenied("target")
		if not (secret(lvl) or secret(mine) or secret(class) or secret(trivial) or secret(tapped)) and lvl and mine then
			local t, sev = Logic.Danger(lvl > 0 and (lvl - mine) or nil, class, trivial, tapped)
			if t then text = SEV[sev] .. t .. "|r" end
			local name = UnitName("target")
			if not secret(name) and name and not tapped and not trivial then
				local w = Logic.Worth(mobStats(name, lvl))
				if w then text = (text and (text .. "  ") or "") .. "|cffbbbbbb" .. w .. "|r" end
				local qt = ns.QH and ns.QH.ForMob and ns.QH.ForMob(name)
				if qt then text = (text and (text .. "  ") or "") .. "|cffffff00" .. ((db.lang == "fi") and "Questiin: " or "Quest: ") .. qt .. "|r" end
			end
		end
	elseif not locked() then
		local worst
		if GetInventoryItemDurability then
			for slot = 1, 18 do
				local cur, max = GetInventoryItemDurability(slot)
				if cur and max and max > 0 then
					local p = cur / max * 100
					if not worst or p < worst then worst = p end
				end
			end
		end
		local free
		if C_Container and C_Container.GetContainerNumFreeSlots then
			free = 0
			for bag = 0, 4 do free = free + (C_Container.GetContainerNumFreeSlots(bag) or 0) end
		end
		local t = Logic.Supplies(s.hasFood, s.hasWater, worst, potion ~= nil, free)
		if t then text = "|cffffa040" .. t .. "|r" end
		-- no food but raw meat: cook it at a campfire (Cooking, Camping)
		if not food and meat then
			text = (text and (text .. "  ") or "") .. "|cffffc080" .. ((db.lang == "fi")
				and ("Kypsennä nuotiolla: %s ×%d") or ("Cook at a campfire: %s x%d")):format(meat.name, meat.n) .. "|r"
		end
		-- the zone has gone green: where to go next
		local lvl = UnitLevel("player")
		local zone = GetRealZoneText and GetRealZoneText()
		if not secret(lvl) and lvl and zone and not secret(zone) then
			local advice = Logic.Route(lvl, zone)
			if advice then text = (text and (text .. "  ") or "") .. "|cff80ff80" .. advice .. "|r" end
			-- no key pressed for a while: going away? hide first
			local lastC = clicks[#clicks]
			if macros.hide and macros.hide ~= "" and lastC and GetTime() - lastC[1] > 90 then
				text = (text and (text .. "  ") or "") .. "|cffffd060" .. tr("afk", db.sos or "G") .. "|r"
			end
			-- the next quest step
			if ns.QH and ns.QH.Refresh and db.quests ~= false then
				if ns.QH.Age() > 5 or questDirty then
					questDirty = false
					pcall(ns.QH.Refresh, lvl)
				end
				local okH, hint = pcall(ns.QH.Hint, db.lang == "fi")
				if okH and hint then text = (text and (text .. "\n") or "") .. "|cff66ccff" .. hint .. "|r" end
				if okH and hint ~= lastHint then
					lastHint = hint
					if logEvent and hint then logEvent("Q", (hint:gsub("|", "/"))) end
				end
			end
		end
	end
	-- the health estimate, out of combat, so you can check it against the bar
	if not hud.hpShown and not locked() and s.deficit and s.maxhp and s.maxhp > 0 then
		local pct = math.max(0, math.floor((1 - s.deficit / s.maxhp) * 100 + 0.5))
		text = (text and (text .. "  ") or "") .. ("|cff88bbffHP ~%d%%|r"):format(pct)
	end
	if locked() and adds.n >= 2 then
		text = "|cffff4040" .. tr("enemies", adds.n) .. "|r" .. (text and ("  " .. text) or "")
		if formNow() == "cat" and known.bear then
			text = text .. "  |cffffd060" .. tr("toBear", db.sos or "G") .. "|r"
		end
	end
	text = trNote(text)
	if text ~= hud.noteText then
		hud.noteText = text
		hud.note:SetText(text or "")
	end
end

-- RUN AWAY. What the addon can read says how the fight is going; health
-- stays secret, so the game's own step curve decides whether the text is
-- seen: a frame is shown for a danger level, and inside it the text's alpha
-- comes from health. Strong signals (three enemies, a hit a second) show it
-- below 65 % health; weak ones (a fight that will not end, a mob that has
-- cost nearly all your health before) below 50 %.
local function updateRun(now)
	if not runBox then return end
	local n5 = 0
	for i = #live.times, 1, -1 do
		if now - live.times[i] <= 5 then n5 = n5 + 1 else table.remove(live.times, i) end
	end
	local strong = adds.n >= 3 or n5 >= 5
	local since = now - (live.lastKill or live.start or now)
	local weak = since > 45 or (state.expect and state.maxhp and state.expect >= 0.9 * state.maxhp)
	local text = tr("run", db.sos or "G")
	for i, r in ipairs(runBox) do
		local on = (i == 1 and strong) or (i == 2 and weak)
		if on then
			if r.label ~= text then r.label = text r.text:SetText(text) end
			r.box:Show()
			setWarn(r.w, true)
		else
			r.box:Hide()
		end
	end
end

local function hideRun()
	if runBox then for _, r in ipairs(runBox) do r.box:Hide() end end
end

local function combatHud()
	setLight(false)
	-- Count the pull twice a second; one warning sound per fight.
	local now = GetTime()
	if now - adds.at >= 0.5 then
		adds.at, adds.n = now, attackers()
		if adds.n >= 2 and not adds.warned then
			adds.warned = true
			if db.sound and PlaySound then pcall(PlaySound, 8959) end
		end
	end
	state.target = targetKind()
	updateRun(now)
	setNote(state)
	local mod = heldMod()
	local key, sos = db.key or "?", db.sos or "G"
	local text
	if mod and macros[mod] then
		text = modLabel(mod)
	elseif adds.n >= 3 then
		text = "|cffff4040" .. tr("cMany", adds.n, sos) .. "|r"
	elseif adds.n == 2 then
		text = "|cffffa040" .. tr("cTwo", key, sos) .. "|r"
	elseif formNow() == "none" and Logic.Mode(db, known) ~= "caster" and now - live.at > 8 then
		-- out of the form well into a fight: you have been healing
		text = tr("cForm", key)
	else
		-- what this kind of mob usually takes: time, and from that a share of hits
		local usual
		local name, lvl = UnitName("target"), UnitLevel("target")
		if not secret(name) and not secret(lvl) and name then
			local m = mobStats(name, lvl)
			if m and m.n > 0 then usual = m.time / m.n end
		end
		if live.hits >= (db.autoheal or 8) * 2 then
			text = "|cffffd060" .. tr("cHits", key) .. "|r"
		elseif usual and now - live.at > usual * 0.75 then
			text = tr("cFinish", key)
		else
			text = tr("cFight", key)
		end
	end
	setHud(text)
end

local function update()
	updateWarnings()
	if locked() then combatHud() return end
	hideRun()
	if bagsDirty then
		local f, w, p = food, water, potion
		scanBags()
		bagsDirty = false
		if f ~= food or w ~= water or p ~= potion then dirty = true end
	end
	-- what mana is proven to cover changes the macros: rebuild when it does
	manaStep()
	local nowT = GetTime()
	hpStep(nowT)
	if nowT - (manaCheckAt or 0) >= 0.15 then
		manaCheckAt = nowT
		local mi = manaInfo()
		manaAnchor(mi, nowT)
		manaState.low = mi.ub ~= nil
		mi.est = manaEstimate(mi)
		local sig = tostring(mi.lb) .. "/" .. tostring(mi.cost.form) .. "/" .. tostring(math.floor((mi.est or 0) / 15))
		if sig ~= manaSig then manaSig, dirty = sig, true end
	end
	if dirty then rebuild() end
	local s = readState()
	local action, arg = Logic.Decide(s)
	local label, spell, item
	local key = db.key or "?"
	if action == "heal" or action == "cure" or action == "buff" then
		spell = N[arg]
		label = tr(action, key, spell)
	elseif action == "eat" then
		item = food
		label = tr("eat", key)
	elseif action == "drink" then
		item = water
		label = tr("drink", key)
	elseif action == "attack" then
		if arg == "fight" then
			-- a red note on the target makes it a warned attack
			local lvl, mine = UnitLevel("target"), UnitLevel("player")
			local class = UnitClassification and UnitClassification("target")
			local red = false
			if not (secret(lvl) or secret(mine) or secret(class)) and lvl and mine then
				local _, sev = Logic.Danger(lvl > 0 and (lvl - mine) or nil, class)
				red = sev == "red"
				-- three levels over you, a skull or an elite: the key does not pull
				local diff = lvl > 0 and (lvl - mine) or 99
				if not db.brave and (diff >= 3 or class == "elite" or class == "rareelite" or class == "worldboss") then
					action = "hold"
					label = "|cffff3030" .. tr("hold", diff < 99 and ("+" .. diff) or "??") .. "|r"
				end
			end
			if action ~= "hold" then label = tr(red and "danger" or "fight", key) end
			-- a mob known to have little health: spells, no form
			local name = UnitName("target")
			local m = db.nuke and macros.nuke and s.form == "none" and not secret(name) and not secret(lvl) and name
				and db.mobs and db.mobs[tostring(name) .. "#" .. tostring(lvl)]
			if action ~= "hold" and m and (m.hn or 0) >= 3 and s.maxhp and m.hp / m.hn <= s.maxhp * 0.3 then
				action, label = "nuke", tr("nuke", key)
			end
			-- a cat with an enemy picked: Prowl, then the opener from behind
			if action == "attack" and s.form == "cat" and macros.catpull then
				action = "catpull"
				label = tr(hasBuff(N.prowl) and "catOpen" or "catProwl", key)
			end
		else
			-- no enemy: the press only picks one; the next update checks
			-- its level and class before the key will attack it
			action = "find"
			label = tr("target", key)
		end
	elseif action == "wait" then
		label = tr("wait")
	else
		label = tr(arg == "dead" and "dead" or "mounted")
	end
	setLight(action ~= "none", action == "attack" or action == "nuke" or action == "catpull")
	setNote(s)
	local mod = heldMod()
	if mod and macros[mod] then label = modLabel(mod) end
	if action == "nuke" then
		apply(macros.nuke, label, action)
	elseif action == "catpull" then
		apply(macros.catpull, label, action)
	else
		apply(Logic.ActionMacro(action, spell, item, macros.fight), label, action)
	end
end

-- Combat begins: from here on the button is locked, so it gets the fight
-- macro now. This event comes before the lock.
-- AFK alarm: something attacked you and none of the keys was pressed for
-- a while. Sound (also with the game in the background) and a flashing
-- taskbar icon, until you press a key or the fight ends.
local alarm = { on = false, n = 0 }
local function lastPress()
	local c = clicks[#clicks]
	return c and c[1] or 0
end
local function alarmTick()
	if not alarm.on then return end
	-- the first tick runs on the combat event, just before the lock
	if (alarm.n > 0 and not locked()) or lastPress() > alarm.since or alarm.n >= 15 then alarm.on = false return end
	alarm.n = alarm.n + 1
	if PlaySound then pcall(PlaySound, 8959, "Master") end
	if FlashClientIcon then pcall(FlashClientIcon) end
	if C_Timer and C_Timer.After then C_Timer.After(2, alarmTick) end
end
local function startAlarm()
	if db.alarm == false or alarm.on then return end
	if GetTime() - lastPress() < 30 then return end
	alarm.on, alarm.n, alarm.since = true, 0, GetTime()
	alarmTick()
end

local function enterCombat()
	live.hits, live.at = 0, GetTime()
	startAlarm()
	live.times, live.start, live.lastKill = {}, GetTime(), nil
	combatHud()
	if locked() or current.what == "nuke" then return end
	current.text, current.what = macros.fight, "attack"
	button:SetAttribute("macrotext", macros.fight)
end

local function bindKey()
	if locked() then return end
	ClearOverrideBindings(button)
	local key = db.key
	if not key then return end
	SetOverrideBindingClick(button, true, key, BUTTON, "LeftButton")
	for _, m in ipairs(MODS) do
		SetOverrideBindingClick(button, true, m[1] .. key, NAMES[m[2]], "LeftButton")
	end
	if db.sos then
		SetOverrideBindingClick(button, true, db.sos, NAMES.sos, "LeftButton")
		SetOverrideBindingClick(button, true, "SHIFT-" .. db.sos, NAMES.free, "LeftButton")
		SetOverrideBindingClick(button, true, "CTRL-" .. db.sos, NAMES.hide, "LeftButton")
	end
end

-- Remembers the last presses, so /okd status can show what a key did.
local function logClick(self, mouse, down)
	local mods = (IsShiftKeyDown() and "S" or "") .. (IsAltKeyDown() and "A" or "") .. (IsControlKeyDown() and "C" or "")
	local text = self:GetAttribute("macrotext")
	text = type(text) == "string" and (text:match("^[^\n]*") or ""):sub(1, 40) or "-"
	clicks[#clicks + 1] = { GetTime(), ("%s %s%s%s%s  %s"):format(self:GetName(), down and "down" or "up",
		mods ~= "" and (" +" .. mods) or "", locked() and " combat" or "", mouse ~= "LeftButton" and (" " .. tostring(mouse)) or "", text) }
	if #clicks > 12 then table.remove(clicks, 1) end
	-- The session log keeps what each press was for (on the edge that acts).
	if logEvent and down == keyDown() then
		local what = locked() and "fight" or current.what or "?"
		if what == "heal" then what = "autoheal" end -- the key's own heal, not Shift
		for key, name in pairs(NAMES) do
			if name == self:GetName() then what = key break end
		end
		logEvent("P", what)
	end
end

-- A /reload in combat runs PLAYER_LOGIN under the lock: the attributes
-- then wait for the fight to end (see PLAYER_REGEN_ENABLED).
local secureLater = {}
local function secureButton(name)
	local b = CreateFrame("Button", name, UIParent, "SecureActionButtonTemplate")
	b:SetSize(1, 1)
	b:SetPoint("TOPLEFT", UIParent, "TOPLEFT", -10, 10)
	-- Both edges reach the button; the client's key-down setting picks the
	-- one that acts, so a press acts once.
	b:RegisterForClicks("AnyUp", "AnyDown")
	if locked() then
		secureLater[#secureLater + 1] = b
	else
		b:SetAttribute("type", "macro")
		b:SetAttribute("macrotext", "")
	end
	b:HookScript("PreClick", logClick)
	return b
end

local function createButton()
	button = secureButton(BUTTON)
	for key, name in pairs(NAMES) do kids[key] = secureButton(name) end
end

local function createHud()
	hud = CreateFrame("Frame", "OneKeyDruidHud", UIParent)
	hud:SetSize(220, 22)
	local p = db.pos
	if p then hud:SetPoint(p[1], UIParent, p[2], p[3], p[4]) else hud:SetPoint("CENTER", UIParent, "CENTER", 0, -160) end
	hud:SetScale(db.scale or 1)
	hud.text = hud:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	hud.text:SetPoint("CENTER")
	hud.note = hud:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
	hud.note:SetPoint("BOTTOM", hud, "TOP", 0, -2)
	-- XP per hour, time to the next level, rested XP
	hud.xp = hud:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
	hud.xp:SetPoint("BOTTOM", hud.note, "TOP", 0, 2)
	-- The real health and mana, as the game computes them: shown, never read.
	hud.vitals = hud:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
	hud.vitals:SetPoint("LEFT", hud.text, "RIGHT", 8, 0)
	-- The ready light, left of the text.
	local function square(parent, r, g, b)
		local t = parent:CreateTexture(nil, "OVERLAY")
		t:SetAllPoints(parent)
		t:SetColorTexture(r, g, b, 1)
		return t
	end
	local red = CreateFrame("Frame", nil, hud)
	red:SetSize(12, 12)
	red:SetPoint("RIGHT", hud.text, "LEFT", -6, 0)
	square(red, 0.9, 0.15, 0.15)
	local hpF = CreateFrame("Frame", nil, red)
	hpF:SetAllPoints(red)
	local manaF = CreateFrame("Frame", nil, hpF)
	manaF:SetAllPoints(red)
	manaF:SetFrameLevel(red:GetFrameLevel() + 2)
	square(manaF, 0.2, 0.85, 0.25)
	light = { red = red, hp = { frame = hpF, at = 0, below = 0, above = 1 },
		mana = { frame = manaF, at = 0, below = 0, above = 1 } }
	red:Hide()
	-- One frame per warning: its alpha is the warning's on/off.
	local y = -20
	for _, name in ipairs({ "low", "heal", "drink" }) do
		local f = CreateFrame("Frame", nil, hud)
		f:SetSize(220, 18)
		f:SetPoint("TOP", hud, "BOTTOM", 0, y + 20)
		f:SetAlpha(0)
		local t = f:CreateFontString(nil, "OVERLAY", name == "low" and "GameFontNormalLarge" or "GameFontNormalSmall")
		t:SetPoint("CENTER")
		warn[name] = { frame = f, text = t, at = 0, below = 1, above = 0 }
		y = y - (name == "low" and 22 or 16)
	end
	buildWarnings()
	-- the RUN AWAY texts: big, in the middle, above the character
	runBox = {}
	for i, at in ipairs(RUN_AT) do
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
		runBox[i] = { box = box, inner = inner, text = t,
			w = { frame = inner, curve = stepCurve(at, 1, 0), at = at, below = 1, above = 0 } }
	end
	hud:SetMovable(true)
	hud:EnableMouse(true)
	hud:RegisterForDrag("LeftButton")
	hud:SetScript("OnDragStart", function(f) if IsShiftKeyDown() then f:StartMoving() end end)
	hud:SetScript("OnDragStop", function(f)
		f:StopMovingOrSizing()
		local a, _, r, x, y = f:GetPoint()
		db.pos = { a, r, x, y }
	end)
	if not db.hud then hud:Hide() end
end

---------------------------------------------------------------------------
-- Ready-made macros for the action bars (/okd macros)
---------------------------------------------------------------------------

local function makeMacros()
	if locked() then say("Not in combat.") return end
	readSpells()
	local list = {}
	if known.ht then
		list[#list + 1] = { "OKD Heal", "#showtooltip " .. N.ht .. "\n/cancelform [form]\n/cast [@mouseover,help,nodead][help,nodead][@player] " .. N.ht }
	end
	if known.motw then
		local b = known.thorns and ("/castsequence [@mouseover,help,nodead][help,nodead][@player] reset=5 " .. N.motw .. ", " .. N.thorns)
			or ("/cast [@mouseover,help,nodead][help,nodead][@player] " .. N.motw)
		list[#list + 1] = { "OKD Buff", "#showtooltip\n/cancelform [form]\n" .. b }
	end
	if known.roots then
		list[#list + 1] = { "OKD Roots", "#showtooltip " .. N.roots .. "\n/cancelform [form]\n/cast [@mouseover,harm,nodead][harm,nodead] " .. N.roots }
	end
	if known.travel or known.cat then
		local c = {}
		if known.aquatic then c[#c + 1] = "[swimming] " .. N.aquatic end
		if known.travel then c[#c + 1] = "[outdoors] " .. N.travel end
		if known.cat then c[#c + 1] = N.cat end
		list[#list + 1] = { "OKD Travel", "#showtooltip\n/cast " .. table.concat(c, "; ") }
	end
	if known.shadowmeld then
		list[#list + 1] = { "OKD Hide", "#showtooltip " .. N.shadowmeld .. "\n/cancelform [form]\n/cast [nocombat] " .. N.shadowmeld }
	end
	local made, kept = 0, 0
	for _, m in ipairs(list) do
		if GetMacroIndexByName(m[1]) ~= 0 then
			kept = kept + 1
		else
			local ok = pcall(CreateMacro, m[1], "INV_MISC_QUESTIONMARK", m[2], true)
			if ok then made = made + 1 end
		end
	end
	say(("%d macros made, %d already there. Open /macro and drag them to your bars."):format(made, kept))
end

---------------------------------------------------------------------------
-- Commands
---------------------------------------------------------------------------

local function itemId(text)
	return tonumber(text:match("item:(%d+)") or text:match("^(%d+)$"))
end

-- The last presses: which button, which edge, which modifiers, and the
-- first line of the macro it ran.
local function presses()
	if #clicks == 0 then say("presses: none yet.") return end
	say("last presses (seconds ago):")
	local now = GetTime()
	for i = math.max(1, #clicks - 9), #clicks do
		print(("  %5.1f  %s"):format(now - clicks[i][1], clicks[i][2]))
	end
end

---------------------------------------------------------------------------
-- DPS window: the game's own damage meter, shown small at the left edge
---------------------------------------------------------------------------
-- The numbers come from C_DamageMeter. In combat they are secret: they go
-- straight into the texts, unread and unsorted (the game lists the sources
-- in its own order). Alone: your own line. In a group: up to five lines.

local dps = { rows = {}, at = 0, state = "not started" }
local DPS_ROWS = 5

local function dpsSetNumber(fs, v)
	if type(v) == "nil" then fs:SetText("") return end
	if pcall(fs.SetFormattedText, fs, "%.0f", v) then return end
	if pcall(function() fs:SetText(string.format("%.0f", v)) end) then return end
	fs:SetText("?")
end

local function dpsSession(kind, overall)
	local M, E = C_DamageMeter, Enum
	if not (M and M.GetCombatSessionFromType and E and E.DamageMeterSessionType and E.DamageMeterType) then
		return nil, "no damage meter in this client"
	end
	if M.IsDamageMeterAvailable then
		local ok, yes, why = pcall(M.IsDamageMeterAvailable)
		if ok and not secret(yes) and not yes then return nil, "meter not available: " .. plainText(why) end
	end
	local ok, session = pcall(M.GetCombatSessionFromType,
		overall and E.DamageMeterSessionType.Overall or E.DamageMeterSessionType.Current, kind or E.DamageMeterType.Dps)
	if not ok or type(session) ~= "table" then return nil, "no session" end
	return session
end

local function dpsUpdate()
	if not dps.frame or not db.dps then return end
	local session, why = dpsSession()
	local shown = 0
	if session and type(session.combatSources) == "table" then
		local group = IsInGroup and IsInGroup()
		for _, src in ipairs(session.combatSources) do
			if shown >= DPS_ROWS then break end
			local mine = src.isLocalPlayer
			if not secret(mine) and (group or mine) then
				shown = shown + 1
				local row = dps.rows[shown]
				if group then
					if not pcall(row.name.SetText, row.name, src.name) then row.name:SetText("?") end
				else
					row.name:SetText("DPS")
				end
				local c = RAID_CLASS_COLORS and not secret(src.classFilename) and RAID_CLASS_COLORS[src.classFilename]
				if c and group then row.name:SetTextColor(c.r, c.g, c.b) else row.name:SetTextColor(0.8, 0.8, 0.8) end
				row.value:SetTextColor(1, mine and 0.82 or 1, mine and 0 or 1)
				dpsSetNumber(row.value, src.amountPerSecond)
				row.name:Show()
				row.value:Show()
			end
		end
		dps.state = ("ok, %d line%s"):format(shown, shown == 1 and "" or "s")
	else
		dps.state = why or "no data"
	end
	for i = shown + 1, DPS_ROWS do
		dps.rows[i].name:Hide()
		dps.rows[i].value:Hide()
	end
end

-- The meter's totals for the log: your own damage done, damage taken and
-- healing, of the last fight or overall. Out of combat they can be read.
local function meterTotals(overall)
	local T = Enum and Enum.DamageMeterType
	if not T then return "?", "?", "?" end
	local out = {}
	for i, kind in ipairs({ T.DamageDone, T.DamageTaken, T.HealingDone }) do
		out[i] = "?"
		local session = dpsSession(kind, overall)
		if session and type(session.combatSources) == "table" then
			out[i] = 0
			for _, src in ipairs(session.combatSources) do
				if not secret(src.isLocalPlayer) and src.isLocalPlayer then out[i] = plainText(src.totalAmount) end
			end
		end
	end
	return out[1], out[2], out[3]
end

local function createDps()
	local f = CreateFrame("Frame", "OneKeyDruidDps", UIParent)
	dps.frame = f
	f:SetSize(120, DPS_ROWS * 13)
	local p = db.dpsPos
	if p then f:SetPoint(p[1], UIParent, p[2], p[3], p[4]) else f:SetPoint("LEFT", UIParent, "LEFT", 6, 110) end
	f:SetAlpha(0.75)
	f:SetScale(db.scale or 1)
	for i = 1, DPS_ROWS do
		local name = f:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
		name:SetPoint("TOPLEFT", f, "TOPLEFT", 0, -(i - 1) * 13)
		name:SetWidth(78)
		name:SetJustifyH("LEFT")
		name:SetWordWrap(false)
		local value = f:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
		value:SetPoint("TOPRIGHT", f, "TOPRIGHT", 0, -(i - 1) * 13)
		value:SetJustifyH("RIGHT")
		dps.rows[i] = { name = name, value = value }
		name:Hide()
		value:Hide()
	end
	f:SetMovable(true)
	f:EnableMouse(true)
	f:RegisterForDrag("LeftButton")
	f:SetScript("OnDragStart", function(self) if IsShiftKeyDown() then self:StartMoving() end end)
	f:SetScript("OnDragStop", function(self)
		self:StopMovingOrSizing()
		local a, _, r, x, y = self:GetPoint()
		db.dpsPos = { a, r, x, y }
	end)
	for _, e in ipairs({ "DAMAGE_METER_COMBAT_SESSION_UPDATED", "DAMAGE_METER_CURRENT_SESSION_UPDATED", "DAMAGE_METER_RESET",
		"GROUP_ROSTER_UPDATE" }) do
		pcall(f.RegisterEvent, f, e)
	end
	f:SetScript("OnEvent", function() dps.dirty = true end)
	f:SetScript("OnUpdate", function(_, dt)
		dps.at = dps.at + dt
		if dps.at < 0.5 and not (dps.dirty and dps.at > 0.2) then return end
		dps.at, dps.dirty = 0, false
		local ok, err = pcall(dpsUpdate)
		if not ok then dps.state = "error: " .. tostring(err):sub(1, 80) end
	end)
	if not db.dps then f:Hide() end
end

-- What this client lets an addon read. Never prints a secret: only whether
-- a value is one. The lines are kept in the saved variables as well.
local function probe()
	local lines = {}
	local function out(fmt, ...) lines[#lines + 1] = fmt:format(...) end
	local function show(v)
		if type(v) == "nil" then return "nil" end
		if secret(v) then return "SECRET" end
		return tostring(v)
	end
	-- call a global function by path; "missing" when the client lacks it
	local function call(path, ...)
		local f = _G
		for part in path:gmatch("[^%.]+") do
			f = type(f) == "table" and f[part] or nil
		end
		if type(f) ~= "function" then return "missing" end
		local function pack(...) return select("#", ...), { ... } end
		local n, r = pack(pcall(f, ...))
		if not r[1] then return "ERROR" end
		local t = {}
		for i = 2, math.max(2, math.min(n, 4)) do t[#t + 1] = show(r[i]) end
		return table.concat(t, ", ")
	end
	local build, _, _, toc = "?", nil, nil, "?"
	if GetBuildInfo then build, _, _, toc = GetBuildInfo() end
	out("probe %s | client %s (%s) | %s | form %s", VERSION, tostring(build), tostring(toc),
		locked() and "IN COMBAT" or "out of combat", formNow())
	for _, p in ipairs({ { "mana", 0 }, { "rage", 1 }, { "energy", 3 }, { "combo", 4 } }) do
		out("%s: value %s | max %s | secrecy %s | shouldBeSecret %s", p[1], call("UnitPower", "player", p[2]),
			call("UnitPowerMax", "player", p[2]), call("C_Secrets.GetPowerTypeSecrecy", p[2]),
			call("C_Secrets.ShouldUnitPowerBeSecret", "player", p[2]))
	end
	out("GetComboPoints %s | health %s | health max %s", call("GetComboPoints", "player", "target"),
		call("UnitHealth", "player"), call("UnitHealthMax", "player"))
	out("secrets: auras %s | cooldowns %s | stats %s", call("C_Secrets.ShouldAurasBeSecret"),
		call("C_Secrets.ShouldCooldownsBeSecret"), call("C_Secrets.ShouldUnitStatsBeSecret"))
	out("assisted combat: available %s | next spell %s", call("C_AssistedCombat.IsAvailable"),
		call("C_AssistedCombat.GetNextCastSpell"))
	out("xp %s / %s | rested %s | level %s", call("UnitXP", "player"), call("UnitXPMax", "player"),
		call("GetXPExhaustion"), call("UnitLevel", "player"))
	local spell = (known.wrath and N.wrath) or (known.ht and N.ht)
	if spell then
		out("%s: usable %s | in range %s | cooldown call %s", spell, call("C_Spell.IsSpellUsable", spell),
			call("C_Spell.IsSpellInRange", spell, "target"), call("C_Spell.GetSpellCooldown", spell) ~= "ERROR" and "ok" or "ERROR")
	end
	out("target: exists %s | level %s | class %s | type %s | attackable %s | trivial %s", call("UnitExists", "target"),
		call("UnitLevel", "target"), call("UnitClassification", "target"), call("UnitCreatureType", "target"),
		call("UnitCanAttack", "player", "target"), call("UnitIsTrivial", "target"))
	out("threat on target %s | in combat: me %s, target %s", call("UnitThreatSituation", "player", "target"),
		call("UnitAffectingCombat", "player"), call("UnitAffectingCombat", "target"))
	local plates = "missing"
	if C_NamePlate and C_NamePlate.GetNamePlates then
		local ok, list = pcall(C_NamePlate.GetNamePlates)
		plates = ok and type(list) == "table" and tostring(#list) or "ERROR"
	end
	out("nameplates %s | glow api %s | curves %s | snippets %s | key down %s", plates,
		type(C_SpellActivationOverlay), type(C_CurveUtil), type(loadstring_untainted), tostring(keyDown()))
	-- the game's damage meter: is it there, and what may be read from it now
	local cvar = C_CVar and C_CVar.GetCVar and C_CVar.GetCVar("damageMeterEnabled")
	local function meter(kindName)
		local kind = Enum and Enum.DamageMeterType and Enum.DamageMeterType[kindName]
		if not kind then return "missing" end
		local session, why = dpsSession(kind)
		if not session then return tostring(why) end
		local n = type(session.combatSources) == "table" and #session.combatSources or 0
		return ("%d sources, total %s"):format(n, show(session.totalAmount))
	end
	out("damage meter: setting %s | window %s | dps: %s | damage taken: %s | healing: %s", tostring(cvar), dps.state,
		meter("Dps"), meter("DamageTaken"), meter("HealingDone"))
	say("probe (also saved; /reload writes it to disk):")
	for _, l in ipairs(lines) do print("  " .. l) end
	db.probes = db.probes or {}
	table.insert(db.probes, lines)
	while #db.probes > 6 do table.remove(db.probes, 1) end
end

local function status()
	local s = readState()
	local action, arg = Logic.Decide(s)
	say(("version %s | mode %s, form %s, target %s"):format(VERSION, s.mode, s.form, s.target))
	say(("health %s, mana %s | warnings by %s | keys act on %s"):format(
		s.hp and (math.floor(s.hp) .. "%") or "hidden by the game", s.mana and (math.floor(s.mana) .. "%") or "hidden by the game",
		gauge, keyDown() and "down" or "up"))
	say(("next press: %s %s | food %s, water %s | key %s"):format(action, tostring(arg or ""),
		tostring(food), tostring(water), tostring(db.key)))
	say(("fight (%d of 255 characters):\n%s"):format(#macros.fight, macros.fight))
	if macros.nuke then say("weak targets:\n" .. macros.nuke) end
	say("on the key now:\n" .. tostring(button:GetAttribute("macrotext")))
	if macros.heal then say("Shift:\n" .. macros.heal) end
	if macros.cc then say("Alt:\n" .. macros.cc) end
	if macros.behind then say("Ctrl:\n" .. macros.behind) end
	if macros.free then say("Shift+" .. tostring(db.sos) .. " (break free):\n" .. macros.free) end
	if macros.sos then say(("emergency (%s), potion %s:\n%s"):format(tostring(db.sos), tostring(potion), macros.sos)) end
	do
		local mi = manaInfo()
		say(("mana: estimate %s (proven at least %s by %s, below %s) | form costs %s, Rejuvenation %s, Moonfire %s, Wrath %s | regen %s/s (measured %s), manasafe %s | health missing ~%s%% (regen %s%%/s)"):format(
			tostring(math.floor(mi.est or 0)), tostring(mi.lb), tostring(mi.probe), tostring(mi.ub), tostring(mi.cost.form), tostring(mi.cost.rejuv),
			tostring(mi.cost.moonfire), tostring(mi.cost.wrath), tostring(db.manaregen),
			db.manaregenLearned and ("%.1f"):format(db.manaregenLearned) or "none yet", tostring(db.manasafe),
			hpEst.frac and tostring(math.floor(hpEst.frac * 100 + 0.5)) or "?", ("%.2f"):format((db.hpregen or 0.005) * 100)))
	end
	if db.key and GetBindingAction then
		for _, m in ipairs({ "", "SHIFT-", "ALT-", "CTRL-" }) do
			say(m .. db.key .. " -> " .. tostring(GetBindingAction(m .. db.key, true)))
		end
	end
	local miss = {}
	for _, k in ipairs({ "ht", "wrath", "moonfire", "roots", "roar", "ff", "charge", "shred", "rake", "fb", "rip", "ravage", "pounce", "shiftpower" }) do
		if not known[k] then miss[#miss + 1] = N[k] end
	end
	if #miss > 0 then say("not learned (left out): " .. table.concat(miss, ", ")) end
	say("dps window: " .. (db.dps and dps.state or "off"))
	presses()
end

local function help()
	say("commands (/okd):")
	print("  bind KEY · unbind — the key (also in the game's Keybindings)")
	print("  sos KEY|off — the emergency key (G): potion, Bash, Nature's Grasp, Rejuvenation, back to form")
	print("  mode auto|cat|bear|caster")
	print("  heal N · drink N · panic N — thresholds in percent · scale N — text size (1.3)")
	print("  lang fi|en — language of the texts on screen")
	print("  buffs · pull · prehot · enrage · roar · escape · shiftpower · hud · light · sound · dps · nuke · manasafe — each on|off (manaregen N)")
	print("  food [item link]|auto · water [item link]|auto")
	print("  macros — make action bar macros · status — show what the key does")
	print("  presses — what the last key presses did")
	print("  probe — what this client lets an addon read (run it in a fight too)")
	print("  session — this session's time and experience · log on|off|clear")
	print("  ranks [on|off] — move spells on the action bars up to the newest rank")
	print("  quests — hand-ins, quests to take and objectives near you · go — map pin and arrow to the next step")
	print("  alarm on|off — loud sound and a flashing taskbar when something attacks you while you are away")
	print("  where — which zone fits your level, what to train next, your XP by zone")
	print("  report — what your fights say: best mobs, advice · autoheal N — heal after N hits (8, 0 = off)")
end

---------------------------------------------------------------------------
-- Session log: what happened and when, for looking at afterwards
---------------------------------------------------------------------------
-- Lines are "seconds|code|fields", seconds counted from the session start.
-- Only values the client lets an addon read; a secret is written as "?".
--   S  session start: epoch, level, xp, xp max, rested, zone, money, free bag slots
--   C+ fight starts: target name, target level, classification, form
--   C- fight ends: seconds, xp gained, hits taken, most attackers seen
--   X  experience: amount, source (kill | quest | other), target name, target level
--   T  hostile target picked out of combat: name, level, classification
--   A  own spell cast: name
--   P  key presses: what for (fight, attack, buff, heal, cc, behind, ...), how many
--   R+ / R-  starts / stops eating or drinking
--   D+ / D-  died / alive again
--   L  level up: new level      Z  zone: name
--   V+ / V-  vendor or trainer window opens / closes: kind
--   B  time so far in seconds: fight, rest, move, idle, dead, town, afk
--   M  the game's meter after a fight: damage done, damage taken, healing; max health
--   H  after a heal out of combat: spell, overall damage taken, overall healing

local LOG_MAX = 8000
local lg = { t0 = 0, buckets = { fight = 0, rest = 0, move = 0, idle = 0, dead = 0, town = 0, afk = 0 } }

local function plain(v)
	if type(v) == "nil" or secret(v) then return "?" end
	return tostring(v)
end

-- Key presses come several a second while the key is held, so they are
-- counted and written as one line, "P|what|presses", when anything else
-- happens or what the key is for changes.
local function flushPresses()
	local what, n, at = lg.pressWhat, lg.pressCount, lg.pressAt
	if not what then return end
	lg.pressWhat, lg.pressCount = nil, 0
	local lines = db.lines
	lines[#lines + 1] = ("%.1f|P|%s|%d"):format(at - lg.t0, what, n)
end

logEvent = function(code, ...)
	if not db or not db.log or not db.lines then return end
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
	local n = select("#", ...)
	local t = { ("%.1f"):format(GetTime() - lg.t0), code }
	for i = 1, n do t[#t + 1] = plain((select(i, ...))) end
	local lines = db.lines
	lines[#lines + 1] = table.concat(t, "|")
	if #lines > LOG_MAX then
		-- drop the oldest fifth in one go
		local cut = math.floor(LOG_MAX / 5)
		local keep = {}
		for i = cut + 1, #lines do keep[#keep + 1] = lines[i] end
		db.lines = keep
	end
end

local function addSample(name, lvl, xp, secs)
	if not name or name == "?" or not tonumber(lvl) or not xp or xp <= 0 or secs <= 0 then return end
	db.mobs = db.mobs or {}
	lg.sampleKeys = { name .. "#" .. lvl, "#" .. lvl }
	for _, key in ipairs(lg.sampleKeys) do
		local m = db.mobs[key] or { n = 0, xp = 0, time = 0 }
		m.n, m.xp, m.time = m.n + 1, m.xp + xp, m.time + secs
		db.mobs[key] = m
	end
	bestDirty = true
	-- keep the table bounded: past 1500 mobs, forget the ones seen once
	db.mobCount = (db.mobCount or 0) + 1
	if db.mobCount > 1500 then
		local n = 0
		for k, v in pairs(db.mobs) do
			if v.n < 2 and k:sub(1, 1) ~= "#" then db.mobs[k] = nil else n = n + 1 end
		end
		db.mobCount = n
	end
end

-- Once: learn from the fights already in the log.
local function backfill()
	if db.mobs or not db.lines then return end
	db.mobs = {}
	local kills, name, lvl, xp
	for _, line in ipairs(db.lines) do
		local _, code, f1, f2, f3, f4 = strsplit("|", line)
		if code == "C+" then
			kills = 0
		elseif code == "X" and f2 == "kill" and kills then
			kills, xp, name, lvl = kills + 1, tonumber(f1), f3, f4
		elseif code == "C-" then
			if kills == 1 and (tonumber(f4) or 0) <= 1 then addSample(name, lvl, xp, tonumber(f1) or 0) end
			kills = nil
		end
	end
end

local function xpNow()
	local x, m = UnitXP and UnitXP("player"), UnitXPMax and UnitXPMax("player")
	if secret(x) or secret(m) then return nil end
	return x, m
end

local function targetInfo()
	if targetKind() ~= "hostile" then return nil end
	local name, lvl = UnitName("target"), UnitLevel("target")
	local class = UnitClassification and UnitClassification("target")
	-- other players' names stay out of the log (it may be shared for analysis)
	local isPlayer = UnitIsPlayer and UnitIsPlayer("target")
	if isPlayer and not secret(isPlayer) then name = "player" end
	return plain(name), plain(lvl), plain(class)
end

local function freeSlots()
	local C, n = C_Container, 0
	if not (C and C.GetContainerNumFreeSlots) then return "?" end
	for bag = 0, 4 do n = n + (C.GetContainerNumFreeSlots(bag) or 0) end
	return n
end

local function logStart()
	db.lines = db.lines or {}
	lg.t0 = GetTime()
	lg.xp, lg.xpMax = xpNow()
	lg.bucketAt = 0
	local zone = GetRealZoneText and GetRealZoneText() or "?"
	logEvent("S", time and time() or 0, UnitLevel("player"), lg.xp, lg.xpMax,
		GetXPExhaustion and GetXPExhaustion() or 0, zone, GetMoney and GetMoney() or 0, freeSlots())
	lg.inFight = locked()
	if lg.inFight then lg.fightAt, lg.fightXp, lg.hits, lg.most = GetTime(), 0, 0, 0 end
end

local function logXp()
	local x, m = xpNow()
	if not x then return end
	local gain
	if lg.xp then
		gain = x - lg.xp
		if gain < 0 then gain = (lg.xpMax or 0) - lg.xp + x end -- levelled up
	end
	lg.xp, lg.xpMax = x, m
	if not gain or gain <= 0 then return end
	local source = "other"
	if lg.questAt and GetTime() - lg.questAt < 2 then
		source = "quest"
	elseif lg.inFight or (lg.fightEnd and GetTime() - lg.fightEnd < 3) then
		source = "kill"
	end
	if lg.inFight then lg.fightXp = (lg.fightXp or 0) + gain end
	if lg.inFight and source == "kill" then
		lg.kills = (lg.kills or 0) + 1
		lg.killName, lg.killLevel = lg.lastName, lg.lastLevel
	end
	if source == "kill" then
		logEvent("X", gain, source, lg.lastName, lg.lastLevel)
	else
		logEvent("X", gain, source)
	end
end

local function logTarget()
	local name, lvl, class = targetInfo()
	if not name then return end
	lg.lastName, lg.lastLevel = name, lvl
	if not locked() then logEvent("T", name, lvl, class) end
end

local logger = CreateFrame("Frame")
local LOG_EVENTS = {
	"PLAYER_REGEN_DISABLED", "PLAYER_REGEN_ENABLED", "PLAYER_XP_UPDATE", "PLAYER_TARGET_CHANGED",
	"QUEST_TURNED_IN", "PLAYER_DEAD", "PLAYER_ALIVE", "PLAYER_UNGHOST", "PLAYER_LEVEL_UP",
	"ZONE_CHANGED_NEW_AREA", "MERCHANT_SHOW", "MERCHANT_CLOSED", "TRAINER_SHOW", "TRAINER_CLOSED",
}

logger:SetScript("OnEvent", function(_, event, a1, a2, a3)
	-- hits taken count for the advice on screen too, log or no log
	if event == "UNIT_COMBAT" and a1 == "player" and locked() and not secret(a2) and a2 == "WOUND" then
		live.hits = live.hits + 1
		live.times[#live.times + 1] = GetTime()
	end
	if event == "PLAYER_XP_UPDATE" and locked() then live.lastKill = GetTime() end
	if not db or not db.log or not db.lines then return end
	if event == "PLAYER_REGEN_DISABLED" then
		lg.inFight, lg.fightAt, lg.fightXp, lg.hits, lg.most, lg.kills = true, GetTime(), 0, 0, 0, 0
		local name, lvl, class = targetInfo()
		if name then lg.lastName, lg.lastLevel = name, lvl end
		logEvent("C+", name, lvl, class, formNow())
	elseif event == "PLAYER_REGEN_ENABLED" then
		if lg.inFight then
			local secs = GetTime() - (lg.fightAt or GetTime())
			logEvent("C-", ("%.1f"):format(secs), lg.fightXp or 0, lg.hits or 0, lg.most or 0)
			lg.fights = (lg.fights or 0) + 1
			if lg.roared then lg.roarFights = (lg.roarFights or 0) + 1 end
			lg.roared = false
			-- A clean fight (one mob, one kill) teaches what that mob is worth.
			lg.sampleKeys = nil
			if lg.kills == 1 and (lg.most or 0) <= 1 then addSample(lg.killName, lg.killLevel, lg.fightXp, secs) end
		end
		-- hits taken earn heals for the key to cast before the next pull
		if lg.inFight and (db.autoheal or 0) > 0 then
			owed = math.min(2, math.floor((lg.hits or 0) / db.autoheal))
		end
		lg.inFight, lg.fightEnd = false, GetTime()
		if C_Timer and C_Timer.After then
			C_Timer.After(1.5, function()
				if locked() then return end
				local ok, done, taken, healed = pcall(meterTotals, false)
				if ok then logEvent("M", done, taken, healed, UnitHealthMax("player")) end
				local t, h = ok and tonumber(taken), ok and tonumber(healed)
				if t and h then
					-- the fight's net loss goes onto the estimate, and into
					-- what this kind of mob usually costs
					local net = math.max(0, t - h)
					local mx = hpMax()
					if mx then hpEst.frac = math.max(0, (hpEst.frac or 0) + (t - h) / mx) end
					if lg.sampleKeys and db.mobs then
						for _, key in ipairs(lg.sampleKeys) do
							local m = db.mobs[key]
							if m then
								m.tk, m.tn = (m.tk or 0) + net, (m.tn or 0) + 1
								-- your damage done in a clean kill is the mob's health
								local d = tonumber(done)
								if d and d > 0 then m.hp, m.hn = (m.hp or 0) + d, (m.hn or 0) + 1 end
							end
						end
					end
				end
				lg.sampleKeys = nil
			end)
		end
	elseif event == "PLAYER_XP_UPDATE" then
		logXp()
	elseif event == "PLAYER_TARGET_CHANGED" then
		logTarget()
	elseif event == "QUEST_TURNED_IN" then
		lg.questAt = GetTime()
	elseif event == "PLAYER_DEAD" then
		lg.dead = true
		logEvent("D+", lg.lastName, lg.lastLevel)
	elseif event == "PLAYER_ALIVE" or event == "PLAYER_UNGHOST" then
		if lg.dead and not UnitIsDeadOrGhost("player") then
			lg.dead = false
			hpEst.frac = nil -- health after a death is not known
			logEvent("D-")
		end
	elseif event == "PLAYER_LEVEL_UP" then
		if hpEst.frac then hpEst.frac = 0 end -- a new level fills health
		logEvent("L", a1)
	elseif event == "ZONE_CHANGED_NEW_AREA" then
		logEvent("Z", GetRealZoneText and GetRealZoneText() or "?")
	elseif event == "MERCHANT_SHOW" or event == "TRAINER_SHOW" then
		lg.town = true
		logEvent("V+", event == "MERCHANT_SHOW" and "vendor" or "trainer")
	elseif event == "MERCHANT_CLOSED" or event == "TRAINER_CLOSED" then
		lg.town = false
		logEvent("V-", event == "MERCHANT_CLOSED" and "vendor" or "trainer")
	elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
		-- a1 unit, a3 spell id
		if a1 == "player" and not secret(a3) and a3 then
			local name = spellName(a3)
			if name and not secret(name) then
				logEvent("A", name)
				if name == N.roar and lg.inFight then lg.roared = true end
				if name == N.ht or name == N.regrowth then lg.paying = false end
				if (name == N.ht or name == N.regrowth or name == N.rejuv) and not locked() and hpEst.frac then
					-- a heal out of combat: take its tooltip amount off the estimate
					local amount
					if C_Spell and C_Spell.GetSpellDescription then
						local okD, desc = pcall(C_Spell.GetSpellDescription, a3)
						if okD and not secret(desc) then amount = Logic.HealAmount(desc) end
					end
					if not amount then
						local max = UnitHealthMax("player")
						local share = name == N.ht and 0.4 or name == N.regrowth and 0.25 or 0.1
						amount = (not secret(max) and max or 0) * share
					end
					lg.lastHealEst = math.floor(amount)
					local mx = hpMax()
					if mx then hpEst.frac = math.max(0, hpEst.frac - amount / mx) end
				end
				if (name == N.ht or name == N.regrowth or name == N.rejuv) and not locked() and C_Timer and C_Timer.After then
					C_Timer.After(1, function()
						if locked() then return end
						local ok, _, taken, healed = pcall(meterTotals, true)
						if ok then logEvent("H", name, taken, healed, lg.lastHealEst) end
					end)
				end
			end
		end
	elseif event == "UNIT_SPELLCAST_START" or event == "UNIT_SPELLCAST_INTERRUPTED" then
		-- A heal owed counts as paid when its cast starts, so that a held key
		-- does not begin one more; an interrupted cast is owed again.
		if a1 == "player" and not secret(a3) and a3 then
			local name = spellName(a3)
			if name and not secret(name) and (name == N.ht or name == N.regrowth) then
				if event == "UNIT_SPELLCAST_START" then
					if owed > 0 then owed, lg.paying = owed - 1, true end
				elseif lg.paying then
					owed, lg.paying = owed + 1, false
				end
			end
		end
	elseif event == "UNIT_COMBAT" then
		-- a2 is the kind of hit; the amount is never read
		if a1 == "player" and lg.inFight and not secret(a2) and a2 == "WOUND" then
			lg.hits = (lg.hits or 0) + 1
		end
	end
end)

local logTick = 0
logger:SetScript("OnUpdate", function(_, dt)
	if not db or not db.log or not db.lines or lg.t0 == 0 then return end
	logTick = logTick + dt
	if logTick < 1 then return end
	local step = logTick
	logTick = 0
	local b = lg.buckets
	local resting = false
	if not locked() then
		resting = hasBuff(foodName) or hasBuff(drinkName)
		if resting ~= (lg.resting or false) then
			lg.resting = resting
			logEvent(resting and "R+" or "R-")
		end
	end
	local speed = GetUnitSpeed and GetUnitSpeed("player") or 0
	if secret(speed) then speed = 0 end
	local afk = UnitIsAFK and UnitIsAFK("player")
	local key
	if UnitIsDeadOrGhost("player") then key = "dead"
	elseif locked() then key = "fight"
	elseif afk and not secret(afk) then key = "afk"
	elseif lg.town then key = "town"
	elseif resting then key = "rest"
	elseif speed > 0 or (UnitOnTaxi and UnitOnTaxi("player")) then key = "move"
	else key = "idle" end
	b[key] = b[key] + step
	if lg.inFight and adds.n > (lg.most or 0) then lg.most = adds.n end
	local now = GetTime() - lg.t0
	if now - (lg.bucketAt or 0) >= 60 then
		lg.bucketAt = now
		logEvent("B", math.floor(b.fight), math.floor(b.rest), math.floor(b.move), math.floor(b.idle),
			math.floor(b.dead), math.floor(b.town), math.floor(b.afk))
	end
end)

-- /okd session: this session in a few lines.
local function sessionSummary()
	if not db.log then say("the session log is off (/okd log on).") return end
	local b = lg.buckets
	local total = b.fight + b.rest + b.move + b.idle + b.dead + b.town + b.afk
	if total < 1 then say("session: nothing yet.") return end
	local function pc(v) return math.floor(v / total * 100 + 0.5) end
	say(("session %d min: fight %d%%, rest %d%%, moving %d%%, idle %d%%, dead %d%%, town %d%%, afk %d%%"):format(
		math.floor(total / 60), pc(b.fight), pc(b.rest), pc(b.move), pc(b.idle), pc(b.dead), pc(b.town), pc(b.afk)))
	local kills, killXp, questXp, fights, fightTime = 0, 0, 0, 0, 0
	local start
	for i = #db.lines, 1, -1 do
		if db.lines[i]:find("|S|", 1, true) then start = i break end
	end
	for i = start or 1, #db.lines do
		local _, code, f1, f2 = strsplit("|", db.lines[i])
		if code == "X" then
			if f2 == "kill" then kills, killXp = kills + 1, killXp + (tonumber(f1) or 0)
			elseif f2 == "quest" then questXp = questXp + (tonumber(f1) or 0) end
		elseif code == "C-" then
			fights, fightTime = fights + 1, fightTime + (tonumber(f1) or 0)
		end
	end
	local hours = total / 3600
	say(("xp: %d from %d kills, %d from quests | %d xp/hour | %d fights, %.0f s each on average"):format(
		killXp, kills, questXp, math.floor((killXp + questXp) / hours), fights, fights > 0 and fightTime / fights or 0))
	say(("log: %d lines. /reload writes it to disk."):format(#db.lines))
end

local function startLog()
	for _, e in ipairs(LOG_EVENTS) do pcall(logger.RegisterEvent, logger, e) end
	pcall(logger.RegisterUnitEvent, logger, "UNIT_SPELLCAST_SUCCEEDED", "player")
	pcall(logger.RegisterUnitEvent, logger, "UNIT_COMBAT", "player")
	pcall(logger.RegisterUnitEvent, logger, "UNIT_SPELLCAST_START", "player")
	pcall(logger.RegisterUnitEvent, logger, "UNIT_SPELLCAST_INTERRUPTED", "player")
	backfill()
	if db.log then logStart() end
end

SLASH_ONEKEYDRUID1, SLASH_ONEKEYDRUID2 = "/okd", "/onekey"
SlashCmdList.ONEKEYDRUID = function(msg)
	local cmd, rest = (msg or ""):match("^%s*(%S*)%s*(.-)%s*$")
	cmd = cmd:lower()
	local on = rest:lower() == "on"
	if cmd == "bind" and rest ~= "" then
		if locked() then say("Not in combat.") return end
		local k, why = Logic.KeyName(rest)
		if not k then say(why) return end
		if k == db.sos then say(k .. " is the emergency key. Choose another key, or move it with /okd sos <key>.") return end
		db.key = k
		bindKey()
		buildWarnings()
		say("bound to " .. db.key .. " (Shift+" .. db.key .. " heals, Alt+" .. db.key .. " stops the mob or eats and drinks, Ctrl+" .. db.key .. " leaves the form).")
	elseif cmd == "unbind" then
		if locked() then say("Not in combat.") return end
		db.key = nil
		bindKey()
		say("key removed.")
	elseif cmd == "mode" and Logic.DEFAULTS.mode and (rest == "auto" or rest == "cat" or rest == "bear" or rest == "caster") then
		db.mode = rest
		dirty = true
		say("mode " .. rest .. ".")
	elseif (cmd == "heal" or cmd == "drink" or cmd == "panic") and tonumber(rest) then
		db[cmd] = math.max(0, math.min(95, tonumber(rest)))
		buildWarnings()
		say(cmd .. " below " .. db[cmd] .. "%.")
	elseif cmd == "buffs" or cmd == "pull" or cmd == "hud" or cmd == "shiftpower" or cmd == "roar" or cmd == "escape" or cmd == "enrage" or cmd == "prehot" or cmd == "light" or cmd == "sound" or cmd == "dps" or cmd == "nuke" or cmd == "manasafe" or cmd == "prowl" then
		if rest == "" then
			-- no on/off: tell, do not change (a bare /okd hud used to hide the HUD)
			say(("%s is %s. /okd %s on|off"):format(cmd, db[cmd] == false and "off" or (db[cmd] and "on" or "default"), cmd))
			return
		end
		db[cmd] = on
		dirty = true
		if cmd == "hud" and hud then if on then hud:Show() else hud:Hide() end end
		if cmd == "dps" and dps.frame then if on then dps.frame:Show() else dps.frame:Hide() end end
		say(cmd .. (on and " on." or " off."))
	elseif cmd == "runtest" then
		if runBox and runBox[1] then
			local r = runBox[1]
			r.text:SetText(tr("run", db.sos or "G"))
			r.label = nil
			r.box:Show()
			r.inner:SetAlpha(1)
			say("RUN AWAY text for 4 seconds.")
			if C_Timer and C_Timer.After then C_Timer.After(4, function() if not locked() then r.box:Hide() end end) end
		end
	elseif cmd == "hpregen" and tonumber(rest) then
		db.hpregen = math.max(0, math.min(5, tonumber(rest))) / 100
		say(("health regeneration assumed: %.2f%% of the maximum per second out of combat."):format(db.hpregen * 100))
	elseif cmd == "manaregen" and tonumber(rest) then
		db.manaregen = math.max(0, math.min(30, tonumber(rest)))
		db.manaregenLearned = nil
		dirty = true
		say("mana regeneration assumed: " .. db.manaregen .. " per second out of combat.")
	elseif cmd == "food" or cmd == "water" then
		db[cmd] = itemId(rest)
		bagsDirty = true
		say(cmd .. ": " .. (db[cmd] and ("item " .. db[cmd]) or "automatic") .. ".")
	elseif cmd == "presses" then
		presses()
	elseif cmd == "probe" then
		probe()
	elseif cmd == "quests" then
		if rest == "off" or rest == "on" then
			db.quests = rest == "on"
			say("quest hints " .. rest .. ".")
		elseif ns.QH and ns.QH.Refresh then
			ns.QH.Refresh(UnitLevel("player"))
			ns.QH.List(say, 5)
		end
	elseif cmd == "ranks" then
		if ns.Ranks then ns.Ranks.Slash(rest, say) end
	elseif cmd == "skip" then
		if rest == "clear" and ns.QH and ns.QH.ClearSkips then
			ns.QH.ClearSkips() questDirty = true say("skipped hints back.")
		elseif ns.QH and ns.QH.Skip then
			local t = ns.QH.Skip()
			say(t and ("hint skipped: " .. t .. " (/okd skip clear)") or "nothing to skip.")
			questDirty = true
		end
	elseif cmd == "go" then
		if ns.QH and ns.QH.Go then
			ns.QH.Refresh(UnitLevel("player"))
			local ok, name = ns.QH.Go()
			say(ok and ("map pin and arrow set: " .. tostring(name)) or "no place to point to.")
		end
	elseif cmd == "brave" then
		db.brave = rest:lower() == "on"
		say(db.brave and "the key pulls anything." or "the key will not pull mobs 3+ levels over you, elites or skulls.")
	elseif cmd == "alarm" then
		db.alarm = rest:lower() ~= "off"
		if not db.alarm and db.bgSoundWas and SetCVar then
			pcall(SetCVar, "Sound_EnableSoundWhenGameIsInBG", db.bgSoundWas)
			db.bgSoundWas = nil
		end
		say("AFK alarm " .. (db.alarm and "on." or "off."))
	elseif cmd == "herbs" then
		db.herbs = rest:lower() ~= "off"
		if db.herbs then
			say(trackHerbs() and "Find Herbs on the minimap." or "Find Herbs not found: is Herbalism learned?")
		else
			say("herb tracking left as you set it.")
		end
	elseif cmd == "where" then
		local lvl, zone = UnitLevel("player"), GetRealZoneText and GetRealZoneText() or "?"
		local advice, fit, train = Logic.Route(lvl, zone)
		say(("level %d in %s. %s"):format(lvl, zone, advice or "This zone still fits."))
		for _, z in ipairs(fit) do say(("  %s (%d-%d)%s"):format(z[3], z[1], z[2], z[4] and (" - " .. z[4]) or "")) end
		if train then say(("next at the trainer: level %d - %s"):format(train[1], train[2])) end
		-- your own XP per hour by zone, from the log
		if db.lines then
			local zz, at, per = "?", 0, {}
			for _, line in ipairs(db.lines) do
				local t, code, f1, f2 = strsplit("|", line)
				t = tonumber(t) or 0
				if code == "S" then at = t
				elseif code == "Z" then zz, at = f1, t
				elseif code == "X" then
					local p = per[zz] or { xp = 0, q = 0, first = t, last = t }
					per[zz] = p
					p.xp = p.xp + (tonumber(f1) or 0)
					if f2 ~= "kill" then p.q = p.q + (tonumber(f1) or 0) end
					p.last = t
				end
			end
			say("your XP by zone (log): total XP, of it quests")
			for name, p in pairs(per) do say(("  %s: %d XP (%d from quests)"):format(name, p.xp, p.q)) end
		end
		say("Questing with kills on the way beats grinding; /okd quests shows the next steps.")
	elseif cmd == "report" then
		sessionSummary()
		for _, l in ipairs(Logic.Report(db.mobs, lg.buckets, lg.roarFights, lg.fights)) do print("  " .. l) end
	elseif cmd == "autoheal" and tonumber(rest) then
		db.autoheal = math.max(0, math.floor(tonumber(rest)))
		say(db.autoheal > 0 and ("one heal after a fight for every " .. db.autoheal .. " hits taken.") or "no heals by hits taken.")
	elseif cmd == "session" then
		sessionSummary()
	elseif cmd == "log" and (rest == "on" or rest == "off" or rest == "clear") then
		if rest == "clear" then
			db.lines = {}
			if db.log then logStart() end
			say("log cleared.")
		else
			db.log = on
			if on then logStart() end
			say("session log " .. rest .. ".")
		end
	elseif cmd == "sos" and rest ~= "" then
		if locked() then say("Not in combat.") return end
		if rest:lower() == "off" then
			db.sos = false
		else
			local k, why = Logic.KeyName(rest)
			if not k then say(why) return end
			if k == db.key then say(k .. " is the fight key. Choose another key.") return end
			db.sos = k
		end
		bindKey()
		buildWarnings()
		say(db.sos and ("emergency key: " .. db.sos .. ".") or "emergency key off.")
	elseif cmd == "lang" and (rest == "fi" or rest == "en") then
		db.lang = rest
		currentLabel = nil
		buildWarnings()
		say(rest == "fi" and "tekstit suomeksi." or "texts in English.")
	elseif cmd == "scale" and tonumber(rest) then
		db.scale = math.max(0.5, math.min(3, tonumber(rest)))
		if hud then hud:SetScale(db.scale) end
		if dps.frame then dps.frame:SetScale(db.scale) end
		say("text size " .. db.scale .. ".")
	elseif cmd == "macros" then
		makeMacros()
	elseif cmd == "status" then
		status()
	else
		help()
	end
end

_G["BINDING_NAME_CLICK " .. BUTTON .. ":LeftButton"] = "Smart action"

---------------------------------------------------------------------------
-- Events
---------------------------------------------------------------------------

local driver = CreateFrame("Frame")
local ready = false
local elapsed = 0

driver:SetScript("OnEvent", function(_, event, arg1)
	if event == "ADDON_LOADED" then
		if arg1 ~= ADDON then return end
		OneKeyDruidDB = OneKeyDruidDB or {}
		db = OneKeyDruidDB
		for k, v in pairs(Logic.DEFAULTS) do
			if db[k] == nil then db[k] = v end
		end
		-- 0.6: Demoralizing Roar is off unless asked for again.
		if (db.version or 0) < 6 then db.roar, db.version = false, 6 end
		-- 0.7: Shift heals at once; rooting first is off unless asked for.
		if db.version < 7 then db.escape, db.version = false, 7 end
	elseif event == "PLAYER_LOGIN" then
		createButton()
		createHud()
		createDps()
		bindKey()
		startLog()
		ready = true
		if C_Timer and C_Timer.After then C_Timer.After(3, trackHerbs) else trackHerbs() end
		-- the AFK alarm needs sound with the game in the background
		-- the alarm must be heard with the game in the background; the old
		-- setting is kept and comes back with /okd alarm off
		if db.alarm ~= false and SetCVar and GetCVar then
			local was = GetCVar("Sound_EnableSoundWhenGameIsInBG")
			if was ~= "1" then
				db.bgSoundWas = was or "0"
				pcall(SetCVar, "Sound_EnableSoundWhenGameIsInBG", "1")
			end
		end
		if not db.key and not GetBindingKey("CLICK " .. BUTTON .. ":LeftButton") then
			say("loaded. Pick the key: /okd bind F   (help: /okd)")
		end
	elseif not ready then
		return
	elseif event == "PLAYER_REGEN_DISABLED" then
		enterCombat()
	elseif event == "MERCHANT_SHOW" then
		local lvl = UnitLevel("player")
		local w = Logic.WaterFor(lvl)
		local need = {}
		if not water then need[#need + 1] = (db.lang == "fi" and "vettä: " or "water: ") .. w end
		if not potion then need[#need + 1] = db.lang == "fi" and "Healing Potion (huutokauppa tai alkemisti)" or "Healing Potion (auction house or an alchemist)" end
		if #need > 0 then say((db.lang == "fi" and "osta: " or "buy: ") .. table.concat(need, " · ")) end
	elseif event == "QUEST_LOG_UPDATE" or event == "QUEST_TURNED_IN" or event == "QUEST_ACCEPTED" then
		questDirty = true
	elseif event == "PLAYER_UNGHOST" or event == "PLAYER_ALIVE" then
		if C_Timer and C_Timer.After then C_Timer.After(2, trackHerbs) end
	elseif event == "PLAYER_REGEN_ENABLED" then
		current.text = nil
		adds.n, adds.warned = 0, false
		if #secureLater > 0 then
			for _, b in ipairs(secureLater) do b:SetAttribute("type", "macro") end
			secureLater = {}
			rebuild()
		end
		bindKey()
		update()
	elseif event == "MODIFIER_STATE_CHANGED" then
		update()
	elseif event == "BAG_UPDATE_DELAYED" then
		bagsDirty = true
	elseif event == "CVAR_UPDATE" then
		if arg1 == "ActionButtonUseKeyDown" or arg1 == "autoSelfCast" then dirty = true end
	else
		dirty = true
	end
end)

for _, e in ipairs({
	"ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_REGEN_DISABLED", "PLAYER_REGEN_ENABLED",
	"BAG_UPDATE_DELAYED", "SPELLS_CHANGED", "UPDATE_SHAPESHIFT_FORMS", "PLAYER_LEVEL_UP",
	"PLAYER_ENTERING_WORLD", "MODIFIER_STATE_CHANGED", "CVAR_UPDATE", "PLAYER_UNGHOST", "PLAYER_ALIVE",
	"QUEST_LOG_UPDATE", "QUEST_TURNED_IN", "QUEST_ACCEPTED", "MERCHANT_SHOW",
}) do
	pcall(driver.RegisterEvent, driver, e)
end

driver:SetScript("OnUpdate", function(_, dt)
	if not ready then return end
	elapsed = elapsed + dt
	if elapsed < 0.15 then return end
	elapsed = 0
	update()
end)
