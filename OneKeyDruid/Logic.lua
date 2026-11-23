-- OneKeyDruid/Logic.lua: the decisions, with no game API in them, so they
-- can be tested outside the game.
--
--   Logic.Decide(s)        what one key press should do out of combat
--   Logic.BuildMacros(...) the macros the secure buttons run
--   Logic.Danger(...)      the warning about the target
--   Logic.Supplies(...)    what is missing for the next pulls
--
-- Out of combat the addon may read buffs and bags and swap a button's macro,
-- so Decide picks freely. In combat the client forbids any change to a
-- button, so the combat macros are fixed text that branches only on what
-- macro conditionals can see: form, stealth, target, modifier keys.
--
-- WoW: Forever keeps health and mana secret from addons, in and out of
-- combat. Decide then gets hp = nil and mana = nil and leaves healing,
-- eating and drinking to the Shift and Alt keys.

local ADDON, ns = ...
local Logic = {}
ns.Logic = Logic

Logic.MACRO_LIMIT = 255

Logic.DEFAULTS = {
	mode = "auto",   -- auto | cat | bear | caster
	heal = 60,       -- heal or eat below this health %
	drink = 35,      -- drink below this mana %
	buffs = true,    -- keep Mark of the Wild / Thorns / Omen of Clarity up
	pull = true,     -- open from range (Wrath, then Moonfire) before shifting
	roar = false,    -- bear: Demoralizing Roar once per target
	enrage = true,   -- kept for old settings; Enrage is no longer on F (its cooldown would stop the macro)
	prowl = true,    -- cat: Prowl before the pull, then Ravage/Shred from behind, Pounce or Claw
	manasafe = true, -- keep mana for the form: skip optional caster spells when it may not cover them
	hpregen = 0.005,  -- health regained per second out of combat, as a share of the maximum (0.5 %)
	manaregen = 2.5, -- mana per second assumed out of combat (low on purpose)
	prehot = true,   -- Rejuvenation on yourself as the mob comes, before the form
	escape = false,  -- Shift: Entangling Roots first, then the heals
	panic = 35,      -- in combat, warn below this health %
	shiftpower = false, -- cat: Shifting Power (mana to energy) when out of energy
	hud = true,
	lang = "en",     -- language of the texts on screen: en | fi (/okd lang fi)
	dps = true,      -- the small damage-per-second window at the left edge
	scale = 1.3,     -- size of the texts on screen
	sos = "G",       -- the emergency key; false for none
	nuke = true,     -- mobs known to have little health are fought in caster form
	autoheal = 8,    -- hits taken in a fight that earn one heal afterwards; 0 for none
	sound = true,    -- a warning sound when a second enemy joins the fight
	light = true,    -- the ready light: green when it is safe to pull
	log = true,      -- keep the session log (fights, experience, casts, time)
}

-- The fighting style for the spells known: cat from Cat Form on, bear from
-- Bear Form on, caster before that.
function Logic.Mode(cfg, known)
	local m = cfg.mode
	if m == "cat" and known.cat then return "cat" end
	if m == "bear" and (known.bear or known.direbear) then return "bear" end
	if m == "caster" then return "caster" end
	if known.cat then return "cat" end
	if known.bear or known.direbear then return "bear" end
	return "caster"
end

-- Which heal to cast on yourself out of combat. hp in percent.
local function pickHeal(s)
	local k, b = s.known, s.buffs
	if s.hp < 40 then
		if k.regrowth and not b.regrowth then return "regrowth" end
		return "ht"
	end
	if k.rejuv and not b.rejuv then return "rejuv" end
	if k.regrowth and not b.regrowth and s.hp < 50 then return "regrowth" end
	return "ht"
end

-- What the key does now, out of combat. Returns action, argument:
--   "none"   nothing (reason in arg)
--   "wait"   eating or drinking, keep sitting
--   "heal"   arg: spell key          "cure"  arg: spell key
--   "eat"    "drink"                 "buff"  arg: spell key, and a
--            party unit when the buff is for someone else
--   "attack" arg: "target" (find one) or "fight"
function Logic.Decide(s)
	local cfg, k, b = s.cfg, s.known, s.buffs
	if s.dead then return "none", "dead" end
	if s.taxi or s.mounted then return "none", "mounted" end

	-- hp and mana are nil where the client keeps them secret (WoW: Forever).
	-- Then the key cannot choose to heal, eat or drink: Shift and Alt do
	-- that, and the text on screen says when. Buffs and cures still work.
	local hp, mana = s.hp, s.mana
	local blind = not hp or not mana
	local live = s.target == "hostile"
	local feral = s.mode ~= "caster"
	local needHP = not blind and hp < cfg.heal
	local needMana = not blind and mana < cfg.drink
	local canHeal = k.ht and true or false
	local m = mana or 100

	-- Already sitting: add the other consumable if it is needed too, then
	-- stay put. A live target picked while resting means "fight anyway",
	-- unless health or mana is still below its threshold.
	local resting
	if blind then
		resting = s.eating or s.drinking
	else
		resting = (s.eating and hp < 95) or (s.drinking and mana < 95)
	end
	if resting and (not live or needHP or needMana) then
		if not blind then
			if s.eating and not s.drinking and s.hasWater and mana < 80 then return "drink" end
			if s.drinking and not s.eating and s.hasFood and hp < 80 then return "eat" end
		end
		return "wait"
	end

	if needHP then
		-- Feral forms fight on rage and energy, so mana is free for healing.
		-- A caster needs its mana to kill, so it eats when it can.
		local floor = feral and 25 or 45
		if canHeal and mana >= floor then return "heal", pickHeal(s) end
		if s.hasFood then return "eat" end
		if canHeal and mana >= 15 then return "heal", pickHeal(s) end
	end

	if needMana and s.hasWater and not live then return "drink" end

	if m >= 15 then
		if s.poison then
			if k.abolish and not b.abolish then return "cure", "abolish" end
			if k.curePoison and not k.abolish then return "cure", "curePoison" end
		end
		if s.curse and k.removeCurse then return "cure", "removeCurse" end
	end

	-- Health cannot be read, but the hits of the last fight were counted:
	-- after a rough one the key heals before the next pull.
	if blind and canHeal and (cfg.autoheal or 0) > 0 then
		if s.deficit and s.maxhp and s.maxhp > 0 then
			-- From the game's damage meter: health missing now (an estimate),
			-- and what the next fight usually costs. Heal first when you would
			-- end that fight under 40%; without a target, when under the heal
			-- threshold.
			local missing = s.deficit / s.maxhp
			local after = (s.deficit + (live and (s.expect or s.maxhp * 0.25) or 0)) / s.maxhp
			-- Only with real health missing (15 %): a tough mob's usual cost
			-- alone (over 60 % of your health) made the key heal at full
			-- health before every pull, ahead of Thorns and Mark of the Wild
			-- (reported 20.11.). A heal cannot fill more than the gap anyway.
			if (live and after > 0.6 and missing >= 0.15) or (not live and missing > (100 - cfg.heal) / 100) then
				-- a big gap takes the big heal
				if missing > 0.3 or not k.regrowth then return "heal", "ht" end
				return "heal", "regrowth"
			end
		elseif (s.owed or 0) > 0 then
			return "heal", k.regrowth and "regrowth" or "ht"
		end
	end

	-- Buffs before the pull, also with an enemy already targeted (F picks
	-- one itself, so "no target" hardly ever happens). Mark of the Wild and
	-- Omen of Clarity last long enough to be worth leaving a form for;
	-- Thorns too when no enemy is picked yet, else only in caster form.
	-- In cat or bear form with an enemy picked, the key does not leave the
	-- form to renew a Mark that still has time on it: "F turns me back
	-- into caster form now and then" (reported 22.11.); renewing waits for
	-- caster form or no target. A Mark that is gone is put back.
	if cfg.buffs and m >= 30 then
		local inForm = s.form ~= "none" and live
		if k.motw and not b.motw and (not inForm or not b.motwAny) then return "buff", "motw" end
		-- Omen of Clarity is passive in WoW: Forever: nothing to cast
		if k.thorns and not b.thorns and not inForm then return "buff", "thorns" end
		-- the party: Mark of the Wild on a member in range who lacks it
		-- (s.partyMotw is that unit, "party1".."party4")
		if k.motw and s.partyMotw and not inForm then return "buff", "motw", s.partyMotw end
	end

	return "attack", live and "fight" or "target"
end

-- How risky the target is, from what may be read before the pull.
--   diff: target level minus yours; nil for a skull (level unknown)
--   class: "elite", "rareelite", "worldboss", "rare", "normal", ...
--   trivial: grey to you (no experience); tapped: someone else's kill
-- Returns text, severity ("red" | "yellow" | "grey"), or nil for an
-- ordinary target.
function Logic.Danger(diff, class, trivial, tapped)
	local parts, sev = {}, nil
	local function add(text, s)
		parts[#parts + 1] = text
		if s == "red" or (s == "yellow" and sev ~= "red") or not sev then sev = s end
	end
	if class == "worldboss" then add("BOSS", "red")
	elseif class == "elite" or class == "rareelite" then add("ELITE", "red") end
	if not diff then add("level ??", "red")
	elseif diff >= 3 then add(("+%d levels"):format(diff), "red")
	elseif diff >= 1 then add(("+%d level%s"):format(diff, diff > 1 and "s" or ""), "yellow") end
	if tapped then add("tapped: no XP", "grey")
	elseif trivial then add("grey: no XP", "grey") end
	if #parts == 0 then return nil end
	return table.concat(parts, " · "), sev
end

-- What a kill of this kind has been worth so far.
--   m: { n, xp, time } summed over the fights seen (or nil)
--   best: the best experience per second among the levels seen (or nil)
-- Returns text, or nil with too little to go on.
function Logic.Worth(m, best)
	if not m or m.n < 1 or m.time <= 0 then return nil end
	local xp, secs = m.xp / m.n, m.time / m.n
	local text = ("~%d XP in %d s"):format(math.floor(xp + 0.5), math.floor(secs + 0.5))
	if best and best > 0 and (xp / secs) < best * 0.6 then text = text .. ", low" end
	return text
end

-- /okd report: what the fights so far say. mobs: the "#level" entries of
-- the learned table; b: seconds per activity. Returns a list of lines.
function Logic.Report(mobs, b, roarFights, fights)
	local out = {}
	local total = b.fight + b.rest + b.move + b.idle + b.dead + b.town + b.afk
	local levels = {}
	for key, m in pairs(mobs or {}) do
		if key:sub(1, 1) == "#" and m.n > 0 and m.time > 0 then
			levels[#levels + 1] = { lvl = tonumber(key:sub(2)) or 0, n = m.n, xp = m.xp / m.n, secs = m.time / m.n, rate = m.xp / m.time }
		end
	end
	table.sort(levels, function(a, c) return a.lvl < c.lvl end)
	local best
	if #levels > 0 then out[#out + 1] = "mob level: kills, XP each, seconds each, XP per second" end
	for _, l in ipairs(levels) do
		out[#out + 1] = ("  level %d: %d kills, %d XP, %d s, %.1f XP/s"):format(l.lvl, l.n, math.floor(l.xp + 0.5), math.floor(l.secs + 0.5), l.rate)
		if l.n >= 2 and (not best or l.rate > best.rate) then best = l end
	end
	if best then out[#out + 1] = ("advice: level %d mobs pay best so far (%.1f XP/s)."):format(best.lvl, best.rate) end
	if total > 300 then
		if b.rest < total * 0.02 and b.idle > total * 0.3 then
			out[#out + 1] = "advice: you stand a lot and never eat or drink. Alt + key rests faster than waiting."
		end
	end
	if fights and fights >= 4 and roarFights and roarFights > fights / 2 then
		out[#out + 1] = ("advice: Demoralizing Roar in %d of %d fights. Against one mob it delays Maul; skip it."):format(roarFights, fights)
	end
	return out
end

-- How much a heal restores, read from its tooltip text: "84 to 98" gives
-- the middle, plus half of "another 98 over"; else the first number.
-- Returns nil when the text has no number.
function Logic.HealAmount(desc)
	if type(desc) ~= "string" then return nil end
	desc = desc:gsub("(%d),(%d)", "%1%2")
	local a, b = desc:match("(%d+) to (%d+)")
	local amount
	if a then
		amount = (tonumber(a) + tonumber(b)) / 2
		local more = desc:match("another (%d+)")
		if more then amount = amount + tonumber(more) / 2 end
	else
		local n = desc:match("(%d+)")
		amount = n and tonumber(n) or nil
	end
	return amount
end

-- What to fetch in town. worst: the lowest durability of the gear in
-- percent, or nil.
function Logic.Supplies(hasFood, hasWater, worst, hasPotion, freeSlots)
	local t = {}
	if not hasFood then t[#t + 1] = "no food" end
	if not hasWater then t[#t + 1] = "no water" end
	if hasPotion == false then t[#t + 1] = "no healing potion" end
	if worst and worst < 20 then t[#t + 1] = "repair" end
	if freeSlots and freeSlots <= 2 then t[#t + 1] = "bags full" end
	if #t > 0 then return table.concat(t, " · ") end
end

---------------------------------------------------------------------------
-- Macros
---------------------------------------------------------------------------

-- Join lines; while the text is over the limit, drop the line with the
-- highest priority number (the least needed). lines: { {text, prio}, ... }
-- lines: { text, priority [, shorter text, its priority] }. Over the limit,
-- the cheapest step goes first: drop the line with the highest priority
-- number, or swap a line for its shorter form when that ranks higher (a
-- tie swaps, since a shorter line keeps more of the macro). Once it fits,
-- dropped lines that would still fit come back (the greedy drop can take
-- out more than needed). Text is never cut inside a line: with only
-- priority 1 lines left, the last one goes.
local function fit(lines)
	local limit = Logic.MACRO_LIMIT
	for i = 1, #lines do lines[i].at = i end
	local dropped = {}
	local function join(t)
		local parts = {}
		for i = 1, #t do parts[i] = t[i][1] end
		return table.concat(parts, "\n")
	end
	while #join(lines) > limit do
		local worst, at, swap = 1, nil, false
		for i = 1, #lines do
			local l = lines[i]
			if l[2] > worst then worst, at, swap = l[2], i, false end
			if l[3] and l[4] >= worst and l[4] > 1 then worst, at, swap = l[4], i, true end
		end
		if not at then
			if #lines <= 1 then return lines[1] and lines[1][1]:sub(1, limit) or "" end
			at = #lines
		end
		if swap then
			local l = lines[at]
			lines[at] = { l[3], l[2], at = l.at }
		else
			dropped[#dropped + 1] = table.remove(lines, at)
		end
	end
	-- give back what fits, the most important first
	table.sort(dropped, function(a, b) return a[2] < b[2] or a[2] == b[2] and a.at < b.at end)
	for _, d in ipairs(dropped) do
		local trial = {}
		local placed = false
		for i = 1, #lines do
			if not placed and lines[i].at > d.at then trial[#trial + 1] = d placed = true end
			trial[#trial + 1] = lines[i]
		end
		if not placed then trial[#trial + 1] = d end
		if #join(trial) <= limit then lines = trial end
	end
	return join(lines)
end

-- A spell name as a macro wants it: one that ends in a bracket needs "()"
-- after it, or the bracket is read as a rank.
local function M(name)
	if name:sub(-1) == ")" then return name .. "()" end
	return name
end

Logic.Fit = fit

local function seq(prefix, reset, list)
	if #list == 1 then return ("/cast %s%s"):format(prefix, M(list[1])) end
	local names = {}
	for i = 1, #list do names[i] = M(list[i]) end
	return ("/castsequence %sreset=%s %s"):format(prefix, reset, table.concat(names, ", "))
end

-- known: spell key -> true; N: spell key -> name on this client;
-- forms: { B = index, C = index, T = index } of the stance bar;
-- mode: Logic.Mode's answer.
-- items: { food = id, water = id } from the bags, or nil.
-- Returns { fight, heal, cc, behind }: the key's macro and the macros of
-- the Shift, Alt and Ctrl keys.
function Logic.BuildMacros(known, N, forms, mode, cfg, items)
	local B, C, T = forms.B, forms.C, forms.T
	items = items or {}
	local bearName = known.direbear and N.direbear or N.bear
	local TARGET = "/targetenemy [noharm][dead]"

	-- Mana is secret, so the addon proves a lower bound from the spells the
	-- game says can be cast (items.mana.lb), then kept as an estimate that
	-- errs low (items.mana.est). room(extra): the estimate covers `extra` and
	-- still the form. Without any mana information there is no limit.
	local function room(extra)
		local m = items.mana
		if not m then return true end
		-- no readable costs: nothing to go by, no limit
		if not m.cost.form or not m.est then return true end
		-- Only proven low mana limits: while every spell can still be cast
		-- (no upper bound), the estimate is too blind to hold anything back.
		if not m.ub then return true end
		return m.est >= m.cost.form + (extra or 0)
	end
	local mc = items.mana and items.mana.cost or {}

	-- Cast once per target: the second step is no spell, so the sequence
	-- waits there until the target changes.
	local function once(prefix, name)
		return ("/castsequence %sreset=target %s, null"):format(prefix, M(name))
	end

	-- One macro for the whole fight, because the key's button cannot change
	-- in combat: every line names the form it is for, and the client skips
	-- the lines that do not fit. Priorities (higher goes first when the text
	-- is over 255 characters) keep what matters.
	local L = { { TARGET, 1 } }
	local F = (mode == "cat" and C) or (mode == "bear" and B) or nil
	local formName = F and (mode == "cat" and N.cat or bearName)
	if F then
		local inForm = ("[form:%d] "):format(F)
		-- a cat's Claw starts the swing by itself, so for the cat this line is
		-- the first to go when space runs out; Maul (queued on the next
		-- swing) needs it, so the bear keeps it
		L[#L + 1] = { mode == "cat" and "/startattack [nostealth]" or "/startattack", mode == "cat" and 4 or 1 }
		-- Caster form. Out of combat: Wrath from range. Once the mob is
		-- coming: Rejuvenation on yourself, Moonfire, then the form.
		local hotOk = cfg.prehot and known.rejuv and room((mc.wrath or 0) + (mc.rejuv or 0) + (known.moonfire and mc.moonfire or 0))
		local moonOk = known.moonfire and room((mc.wrath or 0) + (mc.moonfire or 0))
		if cfg.pull and known.wrath and room(mc.wrath or 0) then
			L[#L + 1] = { "/cast [noform,nocombat,harm] " .. N.wrath, 2 }
			-- In combat and out of form: Rejuvenation and Moonfire once per
			-- target, then the form. The form is in the list twice, so
			-- that after healing in a fight the next presses go straight
			-- back into it.
			local back = (", " .. formName):rep(2)
			local hot = hotOk
			if hot and items.selfcast then
				-- with the game's auto self cast on, a heal cast with an enemy
				-- targeted lands on you, so one sequence does it all
				-- when space runs out the form goes in once instead of twice,
				-- which keeps the Wrath pull in the macro
				local head = ("/castsequence [noform,combat] reset=target %s%s"):format(N.rejuv,
					moonOk and (", " .. N.moonfire) or "")
				L[#L + 1] = { head .. back, 1, head .. ", " .. formName, 3 }
			else
				if hot then
					L[#L + 1] = { ("/castsequence [noform,combat,@player] reset=target %s, null"):format(N.rejuv), 5 }
				end
				if moonOk then
					local head = ("/castsequence [noform,combat] reset=target %s"):format(N.moonfire)
					L[#L + 1] = { head .. back, 1, head .. ", " .. formName, 3 }
				else
					L[#L + 1] = { "/cast [noform,combat] " .. formName, 1 }
				end
			end
		else
			L[#L + 1] = { "/cast [noform,harm,nodead] " .. formName, 1 }
		end
		if mode == "bear" then
			-- The client stops a macro at the first spell that fails: one on
			-- cooldown (Enrage) or out of range (Feral Charge next to the
			-- mob) would keep Maul from ever being queued, so neither is on
			-- F. A spell that cannot be used (no rage, not learned, a false
			-- [condition]) is skipped and does not stop the macro.
			-- Faerie Fire once per target first (after Maul it never came: Maul
			-- without rage stops the macro), Demoralizing Roar (off by default:
			-- it costs the first Maul), Maul.
			if known.ff then L[#L + 1] = { once(inForm, N.ff), 2 } end
			if cfg.roar and known.roar then L[#L + 1] = { once(inForm, N.roar), 4 } end
			if known.maul then L[#L + 1] = { "/cast " .. inForm .. "!" .. N.maul, 1 } end
		elseif known.claw then
			-- Cat: a line whose [condition] is false, or whose spell cannot
			-- be used (no energy), is skipped. A spell on cooldown or out
			-- of range is tried, fails and stops the macro, so Feral Charge
			-- (too close in melee) is not on F. Pounce from stealth, then the
			-- builder-finisher sequence, then Shifting Power.
			local nos = ("[form:%d,nostealth] "):format(F)
			if known.pounce then L[#L + 1] = { ("/cast [form:%d,stealth] %s"):format(F, M(N.pounce)), 6 } end
			-- Faerie Fire opens the sequence, and the sequence runs two rounds
			-- of builders and a finisher before it starts over, so Faerie Fire
			-- comes once a fight (it lasts 40 s) instead of every round. In
			-- 0.29.2 it was a line after the sequence, on the idea that a spell
			-- without energy is skipped: it is not, the client stops on "not
			-- enough energy", and Faerie Fire was never cast (reported 20.11.).
			-- Short of space: one round.
			local round = {}
			for _ = 1, (known.rake or known.fb or known.rip) and 3 or 1 do round[#round + 1] = N.claw end
			-- Finishers: Rip first (the bleed runs while the next combo points
			-- build), then Ferocious Bite to end the fight; with one of them
			-- known, that one both times.
			local fin1 = (known.rip and N.rip) or (known.fb and N.fb) or nil
			local fin2 = (known.fb and N.fb) or fin1
			local fin = fin1
			if fin then round[#round + 1] = fin end
			-- per round the Claws before its finisher: { 2, 3 } is Rake and two
			-- Claws (3 combo points) for Rip, then three Claws for the Bite.
			-- The log of 22.11. showed the Bite with only two Claws behind it.
			local function build(claws)
				local t = {}
				if known.ff then t[#t + 1] = N.ff end
				if known.rake then t[#t + 1] = N.rake end
				for r, n in ipairs(claws) do
					for _ = 1, n do t[#t + 1] = N.claw end
					if fin then t[#t + 1] = (r == 1) and fin1 or fin2 end
				end
				return t
			end
			local c = #round - (fin and 1 or 0)
			local long = seq(inForm, "target", build(fin and { c, c } or { c }))
			-- short of space: a Claw fewer before Rip (Rake gives its combo
			-- point), and a Claw fewer before the Bite only if that is too long
			local short = seq(inForm, "target", build(fin and { math.max(1, c - 1), c } or { math.max(1, c - 1) }))
			if #short > 120 then short = seq(inForm, "target", build(fin and { math.max(1, c - 1), math.max(1, c - 1) } or { 1 })) end
			L[#L + 1] = { long, 1, short, 3 }
			if cfg.shiftpower and known.shiftpower then L[#L + 1] = { "/cast " .. nos .. M(N.shiftpower), 8 } end
		end
	else
		L[#L + 1] = { "/startattack [harm]", 1 }
		local nukes = {}
		if known.moonfire then nukes[#nukes + 1] = N.moonfire end
		if known.wrath then
			for _ = 1, known.moonfire and 3 or 1 do nukes[#nukes + 1] = N.wrath end
		end
		if #nukes > 0 then L[#L + 1] = { seq("[noform] ", "target/combat", nukes), 1 } end
	end
	local fight = fit(L)

	local out = { fight = fight }

	-- For a mob with little health: stay in caster form and cast. It dies
	-- before it does much, and no time goes into shifting. The lines for the
	-- form keep the key working if you shift anyway.
	if F and known.wrath and room(5 * (mc.wrath or 0) + (known.moonfire and mc.moonfire or 0)) then
		local n = { { TARGET, 1 } }
		local spells = { N.wrath, N.wrath }
		if known.moonfire then spells[#spells + 1] = N.moonfire end
		spells[#spells + 1] = N.wrath
		-- if the spells did not kill it, into the form: the mob is close by now
		if formName then for _ = 1, 3 do spells[#spells + 1] = formName end end
		n[#n + 1] = { seq("[noform,harm,nodead] ", "target", spells), 1 }
		n[#n + 1] = { ("/startattack [form:%d]"):format(F), 2 }
		if mode == "bear" and known.maul then n[#n + 1] = { ("/cast [form:%d] !%s"):format(F, N.maul), 2 } end
		if mode == "cat" and known.claw then n[#n + 1] = { ("/cast [form:%d] %s"):format(F, N.claw), 2 } end
		out.nuke = fit(n)
	end

	-- Ctrl: leave the form. As a cat that knows Shred, the cat stays and it
	-- is the "I am behind the target" key: Ravage from stealth, else Shred.
	if C and known.shred then
		local c = known.ravage and ("/cast [form:%d,stealth] %s; [form:%d] %s"):format(C, N.ravage, C, N.shred)
			or ("/cast [form:%d] %s"):format(C, N.shred)
		out.behind = fit({ { ("/cancelform [form,noform:%d]"):format(C), 1 }, { TARGET, 2 }, { c, 1 },
			{ "/startattack [harm]", 1 } })
		out.behindIsShred = true
	else
		out.behind = "/cancelform"
	end

	-- Shift: heal yourself, from any form. Out of combat the big heal comes
	-- first. In combat the instant one does, so that a single press already
	-- helps, and the cast heals follow on the next presses.
	if known.ht then
		local quick = {}
		if known.rejuv then quick[#quick + 1] = N.rejuv end
		if known.regrowth then quick[#quick + 1] = N.regrowth end
		quick[#quick + 1] = N.ht
		if #quick > 1 then quick[#quick + 1] = N.ht end
		local calm = { N.ht }
		if known.rejuv then calm[2] = N.rejuv end
		local e = { { "/cancelform [form]", 1 } }
		-- Optional: root the mob first (outdoors), to step away from it.
		if cfg.escape and known.roots then e[#e + 1] = { once("[harm,nodead,outdoors] ", N.roots), 2 } end
		e[#e + 1] = { seq("[combat,@player] ", "10", quick), 1 }
		e[#e + 1] = { seq("[nocombat,@player] ", "6", calm), 1 }
		out.heal = fit(e)
	end

	-- Alt: stop the mob (Bash in bear, Entangling Roots otherwise). With no
	-- live enemy and out of combat: eat and drink.
	-- Out of combat the form is always left: rooting and eating both need
	-- the caster form. In combat the bear stays a bear, for Bash.
	local REST = "[nocombat,noharm][nocombat,dead]"
	local c = {}
	local bash = B and known.bash
	local rest = items.food or items.water
	if known.roots then
		if bash then
			c[#c + 1] = { ("/cancelform [nocombat][noform:%d]"):format(B), 1 }
			-- Roots hold any mob. Hibernate works only on beasts and
			-- dragonkin; on anything else it fails and would stop the macro
			-- before the roots, so it is not here.
			c[#c + 1] = { ("/cast [noform:%d,harm,nodead] %s"):format(B, N.roots), 1 }
		else
			c[#c + 1] = { "/cancelform", 1 }
			c[#c + 1] = { "/cast [harm,nodead] " .. N.roots, 1 }
		end
	elseif rest then
		c[#c + 1] = { "/cancelform [nocombat]", 1 }
	end
	if items.food then c[#c + 1] = { ("/use %s item:%d"):format(REST, items.food), 2 } end
	if items.water then c[#c + 1] = { ("/use %s item:%d"):format(REST, items.water), 2 } end
	-- Bash last: on cooldown it fails, and a failed cast stops the macro
	if bash then c[#c + 1] = { ("/cast [form:%d,combat,harm,nodead] %s"):format(B, N.bash), 1 } end
	if #c > 0 then out.cc = fit(c) end

	-- The emergency key, to be pressed again and again. The client stops a
	-- macro at the first spell or item that fails, and a potion, Bash or
	-- Nature's Grasp on cooldown fails, so none of them may come before the
	-- heal: they did, and every press after the first did nothing (a death
	-- in the log of 19.11.). Now: out of the form, Rejuvenation on yourself,
	-- back into a form to run or tank (travel, cat or bear); the potion
	-- comes last. It does not use the global cooldown, so it goes in on the
	-- same press as the heal, and when it is on cooldown nothing is lost
	-- after it. Bash stays on Alt+F.
	local sos, graspLine, manaFirst = {}, nil, false
	-- Leaving the form costs mana to get back into it: only when the mana
	-- is proven to cover Rejuvenation and the form; otherwise the bear stays
	-- (and the potion) and the heal key does the healing.
	--
	-- The key is set as the fight starts and cannot change in it, so the
	-- budget counts what the pull will spend first (Wrath twice, the
	-- Rejuvenation and Moonfire before the form, the form, Faerie Fire)
	-- and then Rejuvenation, Nature's Grasp and the bear. In the log of
	-- 21.11. the pull had spent the mana: G left cat form, healed, cast
	-- Nature's Grasp, and the bear failed for mana; eight seconds in caster
	-- form with two mobs on, and a death.
	local function afford(total)
		local m = items.mana
		if not m or not m.cost.form then return true end -- no readable costs
		-- the estimate only when low mana is proven; else the most there can be
		local have = (m.ub and m.est) or m.max
		if not have then return true end
		return have >= total
	end
	local bearCost = mc.bear or mc.form or 0
	local opener = 0
	if F then
		opener = (mode == "cat" and (mc.cat or mc.form) or bearCost) + (known.ff and mc.ff or 0)
		if cfg.pull and known.wrath then
			opener = opener + 2 * (mc.wrath or 0) + (cfg.prehot and known.rejuv and mc.rejuv or 0)
				+ (known.moonfire and mc.moonfire or 0)
		end
	end
	local leave = room(mc.rejuv or 0) and (known.rejuv or known.ht)
		and afford(opener + (mc.rejuv or 0) + bearCost)
	local graspOk = afford(opener + (mc.rejuv or 0) + (mc.grasp or 0) + bearCost)
	-- One pass, not a loop: Rejuvenation on yourself (and the potion), then
	-- Nature's Grasp (once a fight, only when it is ready as the fight
	-- starts: Core picks out.sosGrasp then), then the BEAR (more health and armour when they are on
	-- you; a cat or travel form only without one), then nothing more but the
	-- potion until 20 s without a press or the end of the fight. A loop
	-- came back to Nature's Grasp on its cooldown, and a failed cast stops
	-- the macro. Only a cat leaves its form here: from the bear,
	-- Rejuvenation leaves it by itself, and a later press must not drop
	-- the bear again. The potion is last: it goes in with the heal on the
	-- first press (it does not use the global cooldown).
	if leave then sos[#sos + 1] = { ("/cancelform [form:%d]"):format(C or 3), 1 } end
	local steps = {}
	if known.rejuv then
		steps[1] = N.rejuv
	else
		if known.regrowth then steps[#steps + 1] = N.regrowth end
		if known.ht then steps[#steps + 1] = N.ht end
	end
	if #steps > 0 then
		local stand = (B and bearName) or (known.cat and N.cat) or (known.travel and N.travel) or nil
		if stand then steps[#steps + 1] = stand end
		steps[#steps + 1] = "null"
	end
	-- A bear stays a bear: leaving the form near death drops its armour,
	-- and the heal comes too slowly (the death in the log of 21.11. evening:
	-- seven gnolls on a bear, G cast Rejuvenation and Nature's Grasp out of
	-- form, dead two seconds later). In bear form G is the potion only.
	local stay = B and ("[@player,noform:%d]"):format(B) or "[@player]"
	if leave and #steps > 0 then
		local plainSeq = ("/castsequence %s reset=20/combat %s"):format(stay, table.concat(steps, ", "))
		if known.grasp and graspOk then
			-- the heal (and the potion) on the first press, Nature's Grasp on
			-- the second: near death the heal cannot wait a global cooldown
			-- (a death in the log of 20.11. came with Grasp first)
			local g = {}
			for i, v in ipairs(steps) do
				g[#g + 1] = v
				if i == 1 then g[#g + 1] = N.grasp end
			end
			graspLine = ("/castsequence %s reset=20/combat %s"):format(stay, table.concat(g, ", "))
		end
		sos[#sos + 1] = { plainSeq, 1, nil, nil, grasp = graspLine }
	elseif B then
		-- no mana to leave: stay a bear, a cat goes straight into the bear
		-- (one shift, more armour and health), or back into it from caster.
		-- Short of mana, a mana potion comes first, once (it does not use the
		-- global cooldown, so the bear follows on the same press): without
		-- mana the bear fails, and a failed cast stops the macro.
		local cat = C and ("[form:%d]"):format(C) or ""
		if items.manaPotion then
			-- once a fight: on later presses the potion is on its cooldown,
			-- and a failed use would stop the bear behind it
			sos[#sos + 1] = { ("/castsequence [combat] reset=combat item:%d, null"):format(items.manaPotion), 1 }
			manaFirst = true
		end
		sos[#sos + 1] = { ("/cast %s[noform] %s"):format(cat, bearName), 1 }
	end
	-- the healing potion last; potions share a cooldown, so not after a
	-- mana potion (Core leaves out a potion still cooling as a fight starts)
	if items.potion and not manaFirst then sos[#sos + 1] = { ("/use [combat] item:%d"):format(items.potion), 1 } end
	local plain, with = {}, {}
	for i = 1, #sos do
		plain[i] = { sos[i][1], sos[i][2] }
		with[i] = { sos[i].grasp or sos[i][1], sos[i][2] }
	end
	out.sos = fit(plain)
	if graspLine then out.sosGrasp = fit(with) end

	-- Shift + emergency key: break free. Entering a form removes roots and
	-- slows. WoW: Forever has no powershifting (shifting into the form you
	-- are in), so the key swaps: cat to bear, bear to cat, caster form into
	-- the fighting form. Ctrl + emergency key brings you back to caster form.
	if F then
		-- in the fighting form the other one, anywhere else (caster, water,
		-- travel) the fighting form: "/cast [form:3] Bear Form; Cat Form"
		if C and B and known.cat then
			local inFight = (formName == N.cat) and C or B
			local other = (formName == N.cat) and bearName or N.cat
			out.free = ("/cast [form:%d] %s; %s"):format(inFight, other, formName)
		else
			out.free = "/cast " .. formName
		end
	end

	-- Ctrl + emergency key: hide before going away. Shadowmeld (night elf)
	-- holds while you stand still; Prowl as a cat otherwise.
	if known.shadowmeld then
		out.hide = "/cancelform [form]\n/cast [nocombat] " .. N.shadowmeld
	elseif known.prowl and C then
		out.hide = ("/cast [noform:%d] %s\n/cast [form:%d,nostealth] %s"):format(C, N.cat, C, N.prowl)
	end

	-- Alt + emergency key: run. The emergency key stands and heals (the
	-- bear); against three mobs or an elite that was a death in the logs of
	-- 23.11. This one leaves: the cat, then Dash on the next press. Each
	-- line fits only one state ([noform] / [form]), so nothing fails before
	-- its turn; Dash is last, where a cooldown stops nothing. Core puts
	-- out.run on the key only when Dash is ready as the fight starts;
	-- otherwise out.runSlow: Travel Form outdoors, the cat indoors.
	if C and known.cat then
		if T and known.travel then
			out.runSlow = ("/cast [outdoors,noform:%d] %s; [indoors,noform:%d] %s"):format(T, N.travel, C, N.cat)
		else
			out.runSlow = ("/cast [noform:%d] %s"):format(C, N.cat)
		end
		if known.dash then
			out.run = ("/cast [noform:%d] %s\n/cast [form:%d] %s"):format(C, N.cat, C, N.dash)
		end
	end

	return out
end

-- The macro for one of Decide's actions. spell: the name to cast; item: id.
-- A key the player typed for /okd bind or /okd sos, as the binding API
-- wants it, or nil and why not. Modifiers are refused: the addon adds
-- Shift, Alt and Ctrl itself.
function Logic.KeyName(text)
	local k = tostring(text or ""):gsub("^%s+", ""):gsub("%s+$", ""):upper()
	if k:find("SHIFT%-") or k:find("CTRL%-") or k:find("ALT%-") then
		return nil, "give the key without Shift, Ctrl or Alt: they are added for you"
	end
	if k:match("^[A-Z0-9]$") or k:match("^F[1-9]$") or k:match("^F1[0-2]$") or k:match("^NUMPAD[0-9]$")
		or k:match("^BUTTON[3-5]$") or k:match("^[;',%./%[%]\\%-=`]$") then
		return k
	end
	return nil, "not a key: use a letter, a digit, F1-F12, NUMPAD0-9 or BUTTON3-5"
end

function Logic.ActionMacro(action, spell, item, fight, unit)
	if action == "heal" or action == "cure" or action == "buff" then
		local who = (unit and unit:match("^party[1-4]$")) and unit or "player"
		return "/cancelform [form]\n/cast [@" .. who .. "] " .. spell
	elseif action == "eat" or action == "drink" then
		return "/use item:" .. item
	elseif action == "attack" then
		return fight
	elseif action == "find" then
		return "/targetenemy [noharm][dead]"
	end
	return ""
end

---------------------------------------------------------------------------
-- Where to level. Alliance zones by level in WoW: Forever (guides, Nov
-- 2026: questing beats grinding once mobs turn green; quest XP is not cut
-- for low mobs, kill XP is 4-20 % lower below your level). Druid trainer
-- spells by level are the Classic ones: check them at the trainer.
---------------------------------------------------------------------------
Logic.ZONES = {
	{ 1, 12, "Teldrassil" },
	{ 10, 18, "Darkshore", "Auberdine; boat to Stormwind Harbor" },
	{ 12, 18, "Westfall" }, { 12, 18, "Loch Modan" },
	{ 18, 21, "Redridge Mountains", "+ Deadmines 18-22" },
	{ 18, 25, "Ashenvale", "Astranaar; Blackfathom Deeps 23-26" },
	{ 21, 25, "Wetlands", "Menethil Harbor" },
	{ 24, 27, "Duskwood", "+ Stockade" },
	{ 27, 30, "Hillsbrad Foothills" }, { 27, 30, "Wetlands" },
	{ 30, 40, "Stranglethorn Vale" }, { 30, 38, "Arathi Highlands" },
	{ 30, 35, "Stonetalon Mountains" }, { 35, 45, "Desolace" },
}

Logic.TRAIN = {
	-- Forever moved Shred to 20 and Rake and Ferocious Bite to 24
	{ 20, "Cat Form, Claw, Prowl, Rip, Shred; talent Feral Charge" },
	{ 24, "Rake, Ferocious Bite, Tiger's Fury" }, { 26, "Dash" },
	{ 28, "Cower, Maul rank" }, { 30, "Travel Form" },
	{ 32, "Ravage" }, { 36, "Pounce" },
}

-- level: yours; zone: GetRealZoneText(). Returns the advice line (or nil
-- when this zone still fits), the zones that fit, and the next spells.
function Logic.Route(level, zone)
	local fit, here = {}, nil
	for _, z in ipairs(Logic.ZONES) do
		if z[3] == zone then here = here or z end
	end
	-- zones that fit: start at most a level above you and do not end yet,
	-- the ones made for higher levels first
	for _, z in ipairs(Logic.ZONES) do
		if z[3] ~= zone and z[1] <= level + 1 and level < z[2] then fit[#fit + 1] = z end
	end
	table.sort(fit, function(a, b) return a[1] > b[1] end)
	local train
	for _, t in ipairs(Logic.TRAIN) do
		if t[1] > level then train = t break end
	end
	local advice
	if here and level >= here[2] and #fit > 0 then
		local names = {}
		for i = 1, math.min(2, #fit) do names[i] = fit[i][3] end
		advice = ("%s is low for you: go to %s"):format(zone, table.concat(names, " or "))
	end
	return advice, fit, train
end

-- Vendor water for your level (Classic levels).
function Logic.WaterFor(level)
	if level >= 45 then return "Moonberry Juice" end
	if level >= 35 then return "Sweet Nectar" end
	if level >= 25 then return "Melon Juice" end
	if level >= 15 then return "Ice Cold Milk" end
	if level >= 5 then return "Refreshing Spring Water" end
	return "Refreshing Spring Water"
end
