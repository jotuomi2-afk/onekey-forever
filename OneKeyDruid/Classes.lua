-- OneKeyDruid/Classes.lua: the other classes, for the general engine in
-- OneKey.lua. Each class: its spells (id, English name), the buffs the key
-- keeps up out of combat, and the lines of its macros. A line only goes in
-- when its spells are learned, so one list serves every level.
--
-- Line kinds in a list:
--   { "cast", "spell", "[conditions] " }          /cast
--   { "once", "spell", "[conditions] " }          once per target
--   { "seq",  { "spell", ... }, "[conditions] ", reset }
--   { "raw",  "text", needs = { "spell", ... } }  as it is
-- The key's own buttons: fight (F), heal (Shift+F), cc (Alt+F),
-- behind (Ctrl+F), sos (G), free (Shift+G), hide (Ctrl+G).

local _, ns = ...
local C = {}
ns.CLASSES = C

local H = "[harm,nodead] "
-- sos (the emergency key): the client stops a macro at the first spell or
-- item that fails, and one on cooldown fails, so each list has one spell
-- and the potion last. The potion does not use the global cooldown: it goes
-- in on the same press, and when it is on cooldown nothing after it is lost.

C.MAGE = {
	melee = false, wand = true, conjure = { water = "water", food = "food" },
	spells = {
		frostbolt = { 116, "Frostbolt" }, fireball = { 133, "Fireball" }, fireblast = { 2136, "Fire Blast" },
		nova = { 122, "Frost Nova" }, missiles = { 5143, "Arcane Missiles" }, cone = { 120, "Cone of Cold" },
		ae = { 1449, "Arcane Explosion" }, ai = { 1459, "Arcane Intellect" }, frostarmor = { 168, "Frost Armor" },
		icearmor = { 7302, "Ice Armor" }, magearmor = { 6117, "Mage Armor" }, poly = { 118, "Polymorph" },
		blink = { 1953, "Blink" }, manashield = { 1463, "Mana Shield" }, barrier = { 11426, "Ice Barrier" },
		cs = { 2139, "Counterspell" }, evo = { 12051, "Evocation" }, shoot = { 5019, "Shoot" },
		water = { 5504, "Conjure Water" }, food = { 587, "Conjure Food" }, gem = { 759, "Conjure Mana Agate" },
		dampen = { 604, "Dampen Magic" }, icelance = { 30455, "Ice Lance" },
	},
	buffs = { { "ai" }, { "magearmor", "icearmor", "frostarmor" } },
	-- The client stops a macro at the first spell that fails (on cooldown,
	-- out of range), so F holds only spells without a cooldown: Fireball
	-- pulls from the longest range (35 yd; Frostbolt 30, Fire Blast 20).
	-- (A spell with no mana stops the macro too, so the wand line the engine
	-- adds after Frostbolt shoots only when Frostbolt is not learned yet.)
	-- Frostbolt keeps the mob slowed the whole fight: Fireball only opens
	-- (once per target), every press after that is Frostbolt, whose slow
	-- lasts longer than its cast, so it never runs out. Before Frostbolt is
	-- learned, Fireball is the filler.
	pull = {},
	fight = {
		{ "once", "fireball", H, need = "frostbolt" },
		{ "cast", "frostbolt", H },
		{ "cast", "fireball", H, without = "frostbolt" },
	},
	-- Shift+F, when the mob reaches you (the HUD says when): Frost Nova
	-- freezes it, then Ice Lance on the frozen target (Shatter). Step back
	-- and F goes on with Frostbolt.
	heal = { { "seq", { "nova", "icelance" }, "", "combat" } },
	-- Ctrl+F: instant damage while you move: Fire Blast, then Cone of Cold.
	behind = { { "seq", { "fireblast", "cone" }, H, "combat" } },
	alert = { freeze = "nova", lance = "icelance", cd = { nova = 25, icelance = 8 } },
	cc = { { "cast", "poly", H } },
	sos = { { "cast", "manashield", "" }, { "potion" } },
	free = { { "cast", "blink", "" } },
}

C.WARRIOR = {
	melee = true,
	spells = {
		shout = { 6673, "Battle Shout" }, charge = { 100, "Charge" }, hs = { 78, "Heroic Strike" },
		rend = { 772, "Rend" }, op = { 7384, "Overpower" }, execute = { 5308, "Execute" },
		tc = { 6343, "Thunder Clap" }, demo = { 1160, "Demoralizing Shout" }, ham = { 1715, "Hamstring" },
		bloodrage = { 2687, "Bloodrage" }, retal = { 20230, "Retaliation" }, fear = { 5246, "Intimidating Shout" },
		shoot = { 3018, "Shoot" }, throw = { 2764, "Throw" },
	},
	buffs = { { "shout" } },
	pull = { { "cast", "charge", "[nocombat,harm,nodead] " } },
	fight = {
		{ "cast", "op", H }, { "cast", "execute", H }, { "once", "rend", H },
		{ "cast", "hs", H, bang = true },
	},
	heal = { { "cast", "bloodrage", "" } },
	cc = { { "cast", "ham", H } },
	behind = { { "cast", "tc", "" }, { "cast", "demo", "" } },
	sos = { { "cast", "demo", "" }, { "potion" } },
}

C.ROGUE = {
	-- no /startattack line: Cheap Shot and Sinister Strike start the swing
	-- themselves, and the stun chain needs the room in the macro
	melee = true, attack = false,
	spells = {
		ss = { 1752, "Sinister Strike" }, evis = { 2098, "Eviscerate" }, snd = { 5171, "Slice and Dice" },
		stealth = { 1784, "Stealth" }, cs = { 1833, "Cheap Shot" }, ambush = { 8676, "Ambush" },
		gouge = { 1776, "Gouge" }, kick = { 1766, "Kick" }, evasion = { 5277, "Evasion" },
		sprint = { 2983, "Sprint" }, vanish = { 1856, "Vanish" }, throw = { 2764, "Throw" },
		kidney = { 408, "Kidney Shot" },
	},
	buffs = {},
	-- The stun chain (WoW Forever guides): Cheap Shot from stealth (4 s,
	-- 2 combo points), Sinister Strike to 5 points, Kidney Shot (5 s at 5
	-- points), one more Sinister Strike while it is stunned, Gouge as the
	-- stun ends (it breaks on damage, so the energy comes back while it
	-- holds), then Sinister Strike and Eviscerate. In one /castsequence:
	-- Kidney Shot and Gouge have cooldowns, and in a line of their own a
	-- cooldown would stop the macro; in the sequence the press waits for
	-- them. A spell without energy is skipped and the sequence waits. Before
	-- Kidney Shot (level 30): Sinister Strike, Eviscerate, Gouge in between.
	pull = { { "cast", "cs", "[stealth,harm,nodead] " } },
	fight = {
		{ "seq", { "ss", "ss", "ss", "kidney", "ss", "gouge", "ss", "ss", "evis" },
			"[nostealth,harm,nodead] ", "target", need = "kidney" },
		{ "seq", { "ss", "ss", "ss", "evis", "gouge", "ss", "ss", "ss", "evis" },
			"[nostealth,harm,nodead] ", "target", without = "kidney" },
	},
	heal = { { "cast", "kick", H } },
	cc = { { "cast", "gouge", H } },
	behind = { { "cast", "ambush", "[stealth,harm,nodead] " } },
	sos = { { "cast", "evasion", "" }, { "potion" } },
	free = { { "cast", "sprint", "" } },
	hide = { { "cast", "stealth", "[nocombat,nostealth]" } },
}

C.HUNTER = {
	melee = false, pet = true,
	spells = {
		mark = { 1130, "Hunter's Mark" }, serpent = { 1978, "Serpent Sting" }, arcane = { 3044, "Arcane Shot" },
		auto = { 75, "Auto Shot" }, raptor = { 2973, "Raptor Strike" }, mongoose = { 1495, "Mongoose Bite" },
		hawk = { 13165, "Aspect of the Hawk" }, monkey = { 13163, "Aspect of the Monkey" },
		mend = { 136, "Mend Pet" }, conc = { 5116, "Concussive Shot" }, fd = { 5384, "Feign Death" },
		wing = { 2974, "Wing Clip" }, disengage = { 781, "Disengage" },
	},
	buffs = { { "hawk", "monkey" } },
	pull = {},
	fight = {
		{ "raw", "/petattack [harm,nodead]" },
		{ "once", "mark", H }, { "once", "serpent", H },
		{ "cast", "auto", H, bang = true },
		-- last: when it is on cooldown nothing after it is lost
		{ "cast", "arcane", H },
	},
	heal = { { "cast", "mend", "[@pet,exists,nodead]" } },
	cc = { { "cast", "conc", H }, { "cast", "wing", H } },
	-- The melee key. Shots fail inside their minimum range and a failed
	-- cast stops the macro, and a macro cannot tell the range, so F (ranged)
	-- cannot also hold the melee attacks: when the mob is on you, the HUD
	-- says Ctrl+F. Wing Clip once (it slows the mob, so you can step back
	-- and shoot), Mongoose Bite after a dodge (skipped otherwise), Raptor
	-- Strike last (on its cooldown it fails, and nothing is after it).
	behind = { { "once", "wing", H }, { "cast", "mongoose", H }, { "cast", "raptor", H } },
	meleeHint = { spell = "raptor" },
	sos = { { "cast", "fd", "" }, { "potion" } },
	free = { { "cast", "disengage", H } },
}

C.PRIEST = {
	melee = false, wand = true, heals = true,
	spells = {
		smite = { 585, "Smite" }, swp = { 589, "Shadow Word: Pain" }, mb = { 8092, "Mind Blast" },
		pws = { 17, "Power Word: Shield" }, renew = { 139, "Renew" }, lheal = { 2050, "Lesser Heal" },
		heal = { 2054, "Heal" }, flash = { 2061, "Flash Heal" }, fort = { 1243, "Power Word: Fortitude" },
		inner = { 588, "Inner Fire" }, scream = { 8122, "Psychic Scream" }, shoot = { 5019, "Shoot" },
		form = { 15473, "Shadowform" }, flay = { 15407, "Mind Flay" },
	},
	buffs = { { "fort" }, { "inner" } },
	-- Mind Blast has a cooldown, and the client stops a macro at the first
	-- spell that fails, so it is on Ctrl+F, not F.
	pull = {},
	-- Levelling the priest way: Shadow Word: Pain once per target, then the
	-- wand, which costs no mana. Mind Flay and Smite are the filler only
	-- with no wand on: as the last line the wand was never reached (a spell
	-- with no mana stops the macro; it is not skipped), so the mana ran dry.
	fight = {
		-- [nochanneling]: a press during Mind Flay must not cut it short
		{ "once", "swp", "[harm,nodead,nochanneling] " },
		{ "cast", "flay", "[harm,nodead,nochanneling] ", without = "wand" },
		{ "cast", "smite", "[harm,nodead,nochanneling] ", without = "wand" },
		{ "cast", "shoot", "[harm,nodead,nochanneling] ", bang = true, need = "wand" },
	},
	wandFiller = true,
	heal = { { "cast", "flash", "[@player]" }, { "cast", "heal", "[@player]" }, { "cast", "lheal", "[@player]" } },
	cc = { { "cast", "scream", "" } },
	behind = { { "cast", "mb", H } },
	sos = { { "cast", "pws", "[@player]" }, { "potion" } },
}

local HC = "[harm,nodead,nochanneling] "
C.WARLOCK = {
	melee = false, wand = true, pet = true,
	spells = {
		sb = { 686, "Shadow Bolt" }, immolate = { 348, "Immolate" }, corruption = { 172, "Corruption" },
		-- Forever calls it Bane of Agony; the name comes from the id
		agony = { 980, "Curse of Agony" }, siphon = { 18265, "Siphon Life" },
		drain = { 689, "Drain Life" }, tap = { 1454, "Life Tap" },
		skin = { 687, "Demon Skin" }, armor = { 706, "Demon Armor" }, fear = { 5782, "Fear" },
		coil = { 6789, "Death Coil" }, shoot = { 5019, "Shoot" }, health = { 755, "Health Funnel" },
	},
	buffs = { { "armor", "skin" } },
	pull = {},
	-- Levelling the affliction way: the pet in, each damage over time once
	-- per target, then the wand, which costs no mana, until the mob dies.
	-- Shadow Bolt is the filler only with no wand on. "wand" is known when
	-- a wand is equipped (OneKey.lua).
	-- [nochanneling]: a press during Drain Life does not cut it short.
	fight = {
		{ "raw", "/petattack [harm,nodead]" },
		{ "seq", { "corruption", "agony", "siphon" }, HC, "target", once = true, stop = true },
		{ "cast", "sb", HC, without = "wand" },
		{ "cast", "shoot", HC, bang = true, need = "wand" },
	},
	wandFiller = true,
	heal = { { "cast", "drain", H } },
	cc = { { "cast", "fear", H } },
	-- Ctrl: burst for a mob that must die fast: Immolate once, Shadow Bolt
	behind = { { "once", "immolate", H }, { "cast", "sb", H } },
	sos = { { "cast", "fear", H }, { "potion" } },
	free = { { "cast", "tap", "" } },
}

C.PALADIN = {
	melee = true, heals = true,
	spells = {
		might = { 19740, "Blessing of Might" }, devotion = { 465, "Devotion Aura" }, seal = { 21084, "Seal of Righteousness" },
		judge = { 20271, "Judgement" }, hl = { 635, "Holy Light" }, fol = { 19750, "Flash of Light" },
		hoj = { 853, "Hammer of Justice" }, dp = { 498, "Divine Protection" }, ds = { 642, "Divine Shield" },
		loh = { 633, "Lay on Hands" }, purify = { 1152, "Purify" }, sotc = { 21082, "Seal of the Crusader" },
	},
	buffs = { { "devotion" }, { "might" } },
	pull = {},
	fight = {
		-- Seal, then Judgement when it is ready, then the seal again: the
		-- sequence waits on Judgement's cooldown instead of resealing on
		-- every press. Without Judgement the seal goes on once per target.
		{ "seq", { "seal", "judge" }, H, "target", once = true },
	},
	heal = { { "cast", "fol", "[@player]" }, { "cast", "hl", "[@player]" } },
	cc = { { "cast", "hoj", H } },
	behind = { { "cast", "purify", "[@player]" } },
	sos = { { "cast", "ds", "" }, { "potion" } },
}

C.SHAMAN = {
	melee = true, heals = true,
	spells = {
		lb = { 403, "Lightning Bolt" }, es = { 8042, "Earth Shock" }, fs = { 8050, "Flame Shock" },
		ls = { 324, "Lightning Shield" }, hw = { 331, "Healing Wave" }, lhw = { 8004, "Lesser Healing Wave" },
		earthbind = { 2484, "Earthbind Totem" }, stoneclaw = { 5730, "Stoneclaw Totem" },
		rb = { 8017, "Rockbiter Weapon" }, stormstrike = { 17364, "Stormstrike" }, ghost = { 2645, "Ghost Wolf" },
	},
	buffs = { { "ls" } },
	pull = { { "cast", "lb", "[nocombat,harm,nodead] " } },
	fight = {
		{ "once", "fs", H },
		{ "cast", "es", H },
	},
	heal = { { "cast", "lhw", "[@player]" }, { "cast", "hw", "[@player]" } },
	cc = { { "cast", "earthbind", "" } },
	-- Stormstrike has a cooldown: off F, on Ctrl+F (a failed cast stops the macro)
	behind = { { "cast", "stormstrike", H } },
	sos = { { "cast", "hw", "[@player]" }, { "potion" } },
	free = { { "cast", "ghost", "[nocombat]" } },
}