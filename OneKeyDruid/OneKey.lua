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

local VERSION = "0.29.2"
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
local live = { start = 0, times = {} }
local adds = { n = 0, at = 0, warned = false }

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
		local ok, a = pcall(C_UnitAuras.GetAuraDataBySpellName, "player", name, "HELPFUL")
		if ok then return a ~= nil end
	end
	if AuraUtil and AuraUtil.FindAuraByName then
		local ok, a = pcall(AuraUtil.FindAuraByName, name, "player", "HELPFUL")
		return ok and a ~= nil
	end
	return false
end

local function readSpells()
	if not CL then return end
	for key, s in pairs(CL.spells) do
		local name = spellName(s[1]) or s[2]
		N[key], known[key] = name, isKnown(s[1], name) or nil
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

-- one line of a class list as macro text, or nil when not learned
local function line(e)
	-- need / without: the line only when a spell is (not) known, for
	-- chains that change shape as the class learns spells
	if e.need and not known[e.need] then return nil end
	if e.without and known[e.without] then return nil end
	local kind = e[1]
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
		if #list == 1 and e.once then return ("/castsequence %sreset=target %s, null"):format(e[3] or "", list[1]) end
		if #list == 1 then return ("/cast %s%s"):format(e[3] or "", list[1]) end
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
	macros.fight = build(all, head)
	if CL.wand and known.shoot and not CL.melee then
		-- out of mana the spells above are skipped (not stopped on) and the
		-- wand shoots; "!" keeps a second press from turning it off
		macros.fight = fit({ { macros.fight, 1 }, { ("/cast [harm,nodead,nochanneling] !%s"):format(N.shoot), 2 } })
	end
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
		aNova = "IN MELEE: Shift+%s  %s", aLance = "FROZEN: Shift+%s  %s, then step back and %s",
		aBack = "FROZEN: step back, %s" },
	fi = { target = "%s: etsi kohde", fight = "%s: hyökkää", buff = "%s: buffaa (%s)", conjure = "%s: loihdi (%s)",
		hold = "ÄLÄ VEDÄ: liian vahva (%s). /okd brave on", dead = "Olet kuollut", mounted = "Ratsailla",
		cFight = "%s: taistele", cMany = "%d vihollista: paina %s tai pakene", run = "PAKENE!  %s",
		low = "VÄHÄN HP:TA   paina %s", drinkHint = "Mana vähissä: Alt+%s syö ja juo",
		afk = "Menossa AFK? Ctrl+%s: piiloon", noClass = "tälle luokalle ei vielä ole listaa",
		aNova = "LÄHITAISTELU: Shift+%s  %s", aLance = "JÄÄSSÄ: Shift+%s  %s, sitten taakse ja %s",
		aBack = "JÄÄSSÄ: peräänny, %s" },
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
	buttons.fight:SetAttribute("macrotext", text or "")
end

-- buffs the class keeps up; the first learned of each group
local function missingBuff()
	for _, group in ipairs(CL.buffs or {}) do
		for _, k in ipairs(group) do
			if known[k] then
				if not hasBuff(N[k]) then return k end
				break
			end
		end
	end
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
	local b = missingBuff()
	if b then return "/cast [@player] " .. N[b], tr("buff", key, N[b]) end
	if tk == "hostile" then
		local lvl, mine = UnitLevel("target"), UnitLevel("player")
		local class = UnitClassification and UnitClassification("target")
		if not (secret(lvl) or secret(mine) or secret(class)) and lvl and mine and not db.brave then
			local diff = lvl > 0 and (lvl - mine) or 99
			if diff >= 3 or class == "elite" or class == "rareelite" or class == "worldboss" then
				return "", "|cffff3030" .. tr("hold", diff < 99 and ("+" .. diff) or "??") .. "|r"
			end
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
			if macros.hide and macros.hide ~= "" and lastC and GetTime() - lastC > 90 then
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
local function cooldownLeft(key, now)
	local name = N[key]
	if not name then return 99 end
	if C_Spell and C_Spell.GetSpellCooldown then
		local ok, cd = pcall(C_Spell.GetSpellCooldown, name)
		if ok and type(cd) == "table" and not secret(cd.startTime) and not secret(cd.duration)
			and type(cd.startTime) == "number" and type(cd.duration) == "number" then
			-- the global cooldown is not the spell's own
			if cd.duration <= 1.5 then return 0 end
			return math.max(0, cd.startTime + cd.duration - now)
		end
	end
	local t, len = lastCast[key], CL and CL.alert and CL.alert.cd and CL.alert.cd[key] or 0
	if not t then return 0 end
	return math.max(0, t + len - now)
end

local function noteCast(spellID)
	if not CL or secret(spellID) or type(spellID) ~= "number" then return end
	local name
	if C_Spell and C_Spell.GetSpellName then
		local ok, n = pcall(C_Spell.GetSpellName, spellID)
		if ok and not secret(n) then name = n end
	end
	if not name then return end
	for key, n in pairs(N) do
		if n == name then lastCast[key] = GetTime() end
	end
end

local function alertText(now)
	local A = CL and CL.alert
	if not A or not known[A.freeze] then return nil end
	local key = db.key or "F"
	local frozenAt = lastCast[A.freeze]
	if frozenAt and now - frozenAt < 8 then
		if A.lance and known[A.lance] and cooldownLeft(A.lance, now) == 0 then
			return tr("aLance", key, N[A.lance], key)
		end
		return tr("aBack", key)
	end
	local hit = false
	for i = #live.times, 1, -1 do
		if now - live.times[i] <= 2.5 then hit = true break end
	end
	if hit and cooldownLeft(A.freeze, now) == 0 then return tr("aNova", key, N[A.freeze]) end
	return nil
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
	b:HookScript("PreClick", function() clicks[#clicks + 1] = GetTime() if #clicks > 12 then table.remove(clicks, 1) end end)
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
-- Loop, alarm, events
---------------------------------------------------------------------------

local alarm = { on = false, n = 0 }
local function alarmTick()
	if not alarm.on then return end
	local last = clicks[#clicks] or 0
	-- the first tick runs on the combat event, just before the lock
	if (alarm.n > 0 and not locked()) or last > alarm.since or alarm.n >= 15 then alarm.on = false return end
	alarm.n = alarm.n + 1
	if PlaySound then pcall(PlaySound, 8959, "Master") end
	if FlashClientIcon then pcall(FlashClientIcon) end
	if C_Timer and C_Timer.After then C_Timer.After(2, alarmTick) end
end

local function enterCombat()
	live.start, live.times = GetTime(), {}
	adds.warned = false
	if db.alarm ~= false and not alarm.on and GetTime() - (clicks[#clicks] or 0) >= 30 then
		alarm.on, alarm.n, alarm.since = true, 0, GetTime()
		alarmTick()
	end
	if not locked() then
		current.text = macros.fight
		buttons.fight:SetAttribute("macrotext", macros.fight or "")
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
	local text, label = decide()
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
	elseif event == "PLAYER_LOGIN" then
		if not CL then say(tr("noClass")) return end
		buttons.fight = secureButton(NAMES.fight)
		for key, name in pairs(NAMES) do if key ~= "fight" then buttons[key] = secureButton(name) end end
		createHud()
		bindKey()
		ready = true
		if C_Timer and C_Timer.After then C_Timer.After(3, trackGathering) end
		-- the alarm must be heard with the game in the background; the old
		-- setting is kept and comes back with /okd alarm off
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
		current.text = nil
		adds.n = 0
		if #secureLater > 0 then
			for _, b in ipairs(secureLater) do b:SetAttribute("type", "macro") end
			secureLater = {}
			rebuild()
		end
		bindKey()
	elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
		if arg1 == "player" then noteCast(arg3) end
	elseif event == "UNIT_COMBAT" then
		-- only damage taken counts as a hit (not heals, dodges or misses)
		if arg1 == "player" and arg2 == "WOUND" then live.times[#live.times + 1] = GetTime() end
	elseif event == "BAG_UPDATE_DELAYED" then
		bagsDirty = true
	elseif event == "MERCHANT_SHOW" then
		local need = {}
		if not water and powerType() == 0 and Logic and Logic.WaterFor and not (CL.conjure and known[CL.conjure.water]) then
			need[#need + 1] = (db.lang == "fi" and "vettä: " or "water: ") .. Logic.WaterFor(UnitLevel("player"))
		end
		if not potion then need[#need + 1] = "Healing Potion" end
		if #need > 0 then say((db.lang == "fi" and "osta: " or "buy: ") .. table.concat(need, " · ")) end
	elseif event == "PLAYER_UNGHOST" or event == "PLAYER_ALIVE" then
		if C_Timer and C_Timer.After then C_Timer.After(2, trackGathering) end
	else
		dirty = true
	end
end)
for _, e in ipairs({ "ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_REGEN_DISABLED", "PLAYER_REGEN_ENABLED",
	"BAG_UPDATE_DELAYED", "SPELLS_CHANGED", "PLAYER_LEVEL_UP", "PLAYER_ENTERING_WORLD", "MERCHANT_SHOW",
	"PLAYER_UNGHOST", "PLAYER_ALIVE", "QUEST_LOG_UPDATE" }) do
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
	elseif cmd == "alarm" then
		db.alarm = rest:lower() ~= "off"
		if not db.alarm and db.bgSoundWas and SetCVar then
			pcall(SetCVar, "Sound_EnableSoundWhenGameIsInBG", db.bgSoundWas)
			db.bgSoundWas = nil
		end
	elseif cmd == "herbs" then
		db.herbs = rest:lower() ~= "off"
		trackGathering()
	elseif cmd == "quests" and ns.QH and ns.QH.Refresh then
		ns.QH.Refresh(UnitLevel("player"))
		ns.QH.List(say, 5)
	elseif cmd == "go" and ns.QH and ns.QH.Go then
		ns.QH.Refresh(UnitLevel("player"))
		local ok, name = ns.QH.Go()
		say(ok and ("map pin and arrow: " .. tostring(name)) or "no place to point to.")
	elseif cmd == "where" and Logic and Logic.Route then
		local lvl, zone = UnitLevel("player"), GetRealZoneText and GetRealZoneText() or "?"
		local advice, fit = Logic.Route(lvl, zone)
		say(("level %d in %s. %s"):format(lvl, zone, advice or "This zone still fits."))
		for _, z in ipairs(fit) do say(("  %s (%d-%d)"):format(z[3], z[1], z[2])) end
	elseif cmd == "ranks" then
		if ns.Ranks then ns.Ranks.Slash(rest, say) end
	elseif cmd == "status" then
		say(("%s %s"):format(CLASS, VERSION))
		for _, k in ipairs({ "fight", "heal", "cc", "behind", "sos", "free", "hide" }) do
			say(k .. ":\n" .. tostring(macros[k]))
		end
	else
		say(VERSION .. " — " .. CLASS:lower())
		print("  bind KEY · sos KEY|off · lang en|fi · brave on|off · alarm on|off · herbs on|off")
		print("  quests · go · where · status · ranks [on|off]")
	end
end
