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
		dampen = { 604, "Dampen Magic" },
	},
	buffs = { { "ai" }, { "magearmor", "icearmor", "frostarmor" } },
	-- The pull is the first spell of the sequence: Fireball has the longest
	-- range (35 yd; Frostbolt 30, Fire Blast 20). Then Frostbolt slows the
	-- mob as it runs in, a second Frostbolt keeps it slow, and the sequence
	-- starts over. Fire Blast, instant, goes in whenever it is ready once the
	-- fight is on and the mob is within 20 yd; until then the press moves on
	-- to the sequence. A new target or the end of the fight restarts it at
	-- Fireball.
	pull = {},
	fight = {
		{ "cast", "fireblast", "[combat,harm,nodead] " },
		{ "seq", { "fireball", "frostbolt", "frostbolt" }, H, "target/combat" },
	},
	heal = { { "cast", "nova", "" }, { "cast", "cone", H } },
	cc = { { "cast", "poly", H } },
	behind = { { "cast", "shoot", H } },
	sos = { { "potion" }, { "cast", "barrier", "" }, { "cast", "nova", "" }, { "cast", "manashield", "" } },
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
	sos = { { "potion" }, { "cast", "retal", "" }, { "cast", "fear", "" }, { "cast", "demo", "" } },
}

C.ROGUE = {
	melee = true, attack = "/startattack [nostealth,harm,nodead]",
	spells = {
		ss = { 1752, "Sinister Strike" }, evis = { 2098, "Eviscerate" }, snd = { 5171, "Slice and Dice" },
		stealth = { 1784, "Stealth" }, cs = { 1833, "Cheap Shot" }, ambush = { 8676, "Ambush" },
		gouge = { 1776, "Gouge" }, kick = { 1766, "Kick" }, evasion = { 5277, "Evasion" },
		sprint = { 2983, "Sprint" }, vanish = { 1856, "Vanish" }, throw = { 2764, "Throw" },
	},
	buffs = {},
	pull = { { "cast", "cs", "[stealth,harm,nodead] " } },
	fight = {
		{ "seq", { "ss", "ss", "ss", "evis" }, "[nostealth,harm,nodead] ", "target" },
	},
	heal = { { "cast", "kick", H } },
	cc = { { "cast", "gouge", H } },
	behind = { { "cast", "ambush", "[stealth,harm,nodead] " } },
	sos = { { "potion" }, { "cast", "evasion", "" }, { "cast", "gouge", H } },
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
		{ "cast", "arcane", H },
		{ "cast", "raptor", H },
	},
	heal = { { "cast", "mend", "[@pet,exists,nodead]" } },
	cc = { { "cast", "conc", H }, { "cast", "wing", H } },
	behind = { { "cast", "mongoose", H } },
	sos = { { "potion" }, { "cast", "fd", "" } },
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
	pull = { { "cast", "mb", "[nocombat,harm,nodead] " }, { "cast", "smite", "[nocombat,harm,nodead] " } },
	fight = {
		{ "once", "swp", H },
		{ "cast", "mb", H },
		{ "cast", "flay", H },
		{ "cast", "smite", H },
	},
	heal = { { "cast", "flash", "[@player]" }, { "cast", "heal", "[@player]" }, { "cast", "lheal", "[@player]" } },
	cc = { { "cast", "scream", "" } },
	behind = { { "cast", "shoot", H } },
	sos = { { "potion" }, { "cast", "pws", "[@player]" }, { "cast", "scream", "" }, { "cast", "renew", "[@player]" } },
}

C.WARLOCK = {
	melee = false, wand = true, pet = true,
	spells = {
		sb = { 686, "Shadow Bolt" }, immolate = { 348, "Immolate" }, corruption = { 172, "Corruption" },
		agony = { 980, "Curse of Agony" }, drain = { 689, "Drain Life" }, tap = { 1454, "Life Tap" },
		skin = { 687, "Demon Skin" }, armor = { 706, "Demon Armor" }, fear = { 5782, "Fear" },
		coil = { 6789, "Death Coil" }, shoot = { 5019, "Shoot" }, health = { 755, "Health Funnel" },
	},
	buffs = { { "armor", "skin" } },
	pull = {},
	fight = {
		{ "raw", "/petattack [harm,nodead]" },
		{ "once", "corruption", H }, { "once", "agony", H }, { "once", "immolate", H },
		{ "cast", "sb", H },
	},
	heal = { { "cast", "drain", H } },
	cc = { { "cast", "fear", H } },
	behind = { { "cast", "shoot", H } },
	sos = { { "potion" }, { "cast", "coil", H }, { "cast", "fear", H } },
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
	sos = { { "potion" }, { "cast", "ds", "" }, { "cast", "dp", "" }, { "cast", "loh", "[@player]" } },
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
		{ "cast", "stormstrike", H },
		{ "once", "fs", H },
		{ "cast", "es", H },
	},
	heal = { { "cast", "lhw", "[@player]" }, { "cast", "hw", "[@player]" } },
	cc = { { "cast", "earthbind", "" } },
	behind = { { "cast", "es", H } },
	sos = { { "potion" }, { "cast", "stoneclaw", "" }, { "cast", "hw", "[@player]" } },
	free = { { "cast", "ghost", "[nocombat]" } },
}
