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
--   { "opener", "spell", "[conditions] ", count = n, slow = "spell", near = "spell" }
--       up to n times per target, as many as fit before the slow spell
--       lands (by the distance: "near" is a spell with a short range)
-- need / without = "spell": the line only when the spell is (not) learned;
-- below / from = level: only under, or from, that character level.
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
	-- Frost, as the WoW Forever guides play it (Icy Veins, Wowhead, Method,
	-- Warcraft Tavern; read 22.11.2026). At level 60 the priority is: Ice
	-- Barrier up (its Frigid Power buff adds damage), Cone of Cold at five
	-- stacks of Winter's Chill, Ice Lance on a frozen target or with Fingers
	-- of Frost, Frostbolt for everything else.
	--
	-- Ice or Frost Armor before Mage Armor: alone in the world the armour
	-- and the chill on whatever hits you are worth more than the mana.
	buffs = { { "ai" }, { "icearmor", "frostarmor", "magearmor" } },
	-- F, out of combat with an enemy picked: Ice Barrier first when it is
	-- not up and not on cooldown (OneKey.lua, decide). The guides cast it
	-- just before the pull.
	shield = "barrier",
	-- The client stops a macro at the first spell that fails (on cooldown,
	-- out of range), so F holds only spells without a cooldown.
	-- The opener (from play, 23.11.): from far off there is time for two
	-- Fireballs before the mob arrives, from nearer for one; then the
	-- Frostbolt that slows it, and every press after that is Frostbolt.
	-- Fireball reaches 35 yd and hits harder than a low Frostbolt. How many
	-- fit is worked out before each pull from how far the target is and
	-- how long the two spells take to cast now (OneKey.lua, openerFor):
	-- the slow must land while the mob is still some yards away. With the
	-- 3 s Fireball of the higher levels that is one from range and none up
	-- close. /okd opener 0-3 fixes the number; /okd opener auto goes back
	-- to the distance. The macro is chosen out of combat and stays for the
	-- fight: a mob that joins later gets the same opener.
	-- Before Frostbolt is learned, Fireball is the filler.
	pull = {},
	fight = {
		{ "opener", "fireball", H, need = "frostbolt", count = 2, slow = "frostbolt", near = "fireblast" },
		{ "cast", "fireball", H, without = "frostbolt" },
		{ "cast", "frostbolt", H },
	},
	-- Shift+F, on a frozen mob (after G's Frost Nova, or when the game
	-- lights up Ice Lance): Frostbolt with Ice Lance right behind it, so
	-- both land while it is frozen (Shatter). Left alone for 6 s it starts
	-- over at Frostbolt.
	heal = { { "seq", { "frostbolt", "icelance" }, H, "6/combat" } },
	-- Ctrl+F: instant damage while you move: Fire Blast, then Cone of Cold.
	-- With five stacks of Winter's Chill the HUD asks for the Cone.
	behind = { { "seq", { "fireblast", "cone" }, H, "combat" } },
	alert = { freeze = "nova", freezeKey = "sos", lance = "icelance", bolt = "frostbolt",
		cd = { nova = 25, icelance = 8, cone = 10, barrier = 30, blink = 15 },
		-- Winter's Chill (talent, level 35): Frostbolt and Ice Lance casts
		-- build it, Cone of Cold spends it at five
		chill = { level = 35, build = { "frostbolt", "icelance" }, spend = "cone", stacks = 5 },
		-- Frigid Power lasts a minute from the Ice Barrier cast
		shield = { spell = "barrier", every = 57 } },
	cc = { { "cast", "poly", H } },
	-- G, the way out when a mob is on you: Frost Nova, then Blink away,
	-- then Mana Shield, one press each, and the potion with the first.
	-- One sequence that ends (null): after the three it stays out of the
	-- way, so the potion line is still reached, and 25 s after the last
	-- press it starts over, when Frost Nova is ready again. Only the time
	-- resets it: the end of a fight must not (Frost Nova's cooldown runs
	-- on into the next fight, and a sequence back on a spell that is not
	-- ready holds the key and the potion behind it). Frost Nova and Blink
	-- are on no other key, for the same reason.
	sos = { { "seq", { "nova", "blink", "manashield" }, "", "25", stop = true }, { "potion" } },
	-- Shift+G: Counterspell
	free = { { "cast", "cs", H } },
	-- Ctrl+G: Ice Barrier again in a long fight (the HUD says when)
	hide = { { "cast", "barrier", "" } }, hideIsSpell = true,
}

-- The classes below follow the WoW Forever levelling guides (Warcraft
-- Tavern, Method; read 23.11.2026). What a guide casts "on cooldown" or
-- "when available" cannot be on F with other spells (a failed cast stops
-- the macro), so it sits inside one sequence, which waits, or on a helper
-- key that the HUD names when the spell is ready (hints).

C.WARRIOR = {
	melee = true,
	spells = {
		shout = { 6673, "Battle Shout" }, charge = { 100, "Charge" }, hs = { 78, "Heroic Strike" },
		rend = { 772, "Rend" }, op = { 7384, "Overpower" }, execute = { 5308, "Execute" },
		tc = { 6343, "Thunder Clap" }, demo = { 1160, "Demoralizing Shout" }, ham = { 1715, "Hamstring" },
		bloodrage = { 2687, "Bloodrage" }, retal = { 20230, "Retaliation" }, fear = { 5246, "Intimidating Shout" },
		shoot = { 3018, "Shoot" }, throw = { 2764, "Throw" },
		ms = { 12294, "Mortal Strike" }, bt = { 23881, "Bloodthirst" },
	},
	buffs = { { "shout" } },
	pull = { { "cast", "charge", "[nocombat,harm,nodead] " } },
	-- Overpower (only after a dodge) and Execute (only under 20 % health)
	-- cannot be used most of the time, and a spell that cannot be used stops
	-- the macro: first on F they kept Rend and Heroic Strike from ever being
	-- reached. They have keys of their own, and the HUD names the key when
	-- the client says the spell can be used.
	-- The guides: Charge, Rend, Overpower whenever it is up, Mortal Strike
	-- or Bloodthirst on cooldown, Heroic Strike with rage left over. With a
	-- strike talent F is Rend once and the strike: Heroic Strike on every
	-- press took the rage the strike needs (it stays on your action bar for
	-- a full rage bar). Without one, Heroic Strike as before.
	fight = {
		{ "once", "rend", H },
		{ "cast", "hs", H, bang = true, without = "strike" },
		{ "cast", "bt", H, without = "ms" },
		{ "cast", "ms", H },
	},
	-- "strike" is known when Mortal Strike or Bloodthirst is (OneKey.lua)
	either = { strike = { "ms", "bt" } },
	-- Shift+F: Execute, for the mob's last fifth of health
	heal = { { "cast", "execute", H } },
	cc = { { "cast", "ham", H } },
	-- Ctrl+F: Overpower right after the mob dodges
	behind = { { "cast", "op", H } },
	hints = { { spell = "op", key = "behind", react = true }, { spell = "execute", key = "heal", react = true } },
	cd = { op = 5 },
	sos = { { "cast", "demo", "" }, { "potion" } },
	-- Shift+G: Bloodrage, rage at the start of a fight
	free = { { "cast", "bloodrage", "" } },
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
		kidney = { 408, "Kidney Shot" }, riposte = { 14251, "Riposte" },
	},
	buffs = {},
	-- The guides (combat): Cheap Shot from stealth, Sinister Strike to
	-- build, Slice and Dice as soon as possible, Eviscerate at 3-5 points.
	-- So Slice and Dice is the first finisher, after two Sinister Strikes:
	-- a strike that misses still moves the sequence on, and a finisher with
	-- no combo point would hold the key, so one strike before it is too
	-- few. Then the stun chain: two more Sinister Strikes, Kidney Shot, one
	-- more Sinister Strike
	-- while it is stunned, Gouge as the stun ends (it breaks on damage, so
	-- the energy comes back while it holds), then Sinister Strike and
	-- Eviscerate. In one /castsequence: Kidney Shot and Gouge have
	-- cooldowns, and in a line of their own a cooldown would stop the
	-- macro; in the sequence the press waits for them. A spell without
	-- energy is skipped and the sequence waits. Before Kidney Shot (level
	-- 30): Slice and Dice, Sinister Strike, Eviscerate, Gouge in between.
	-- Short conditions: the chain must fit 255 characters with Cheap Shot.
	-- In stealth Cheap Shot goes first and its global cooldown holds the
	-- sequence back, so the sequence needs no [nostealth].
	pull = { { "cast", "cs", "[stealth] " } },
	fight = {
		{ "seq", { "ss", "ss", "snd", "ss", "ss", "kidney", "ss", "gouge", "ss", "ss", "evis" },
			"", "target", need = "kidney" },
		{ "seq", { "ss", "ss", "snd", "ss", "ss", "evis", "gouge", "ss", "ss", "ss", "evis" },
			"", "target", without = "kidney" },
	},
	heal = { { "cast", "kick", H } },
	cc = { { "cast", "gouge", H } },
	-- Ctrl+F: Ambush from stealth; in a fight Riposte, after a parry (the
	-- HUD says when). The two conditions never hold together, and a false
	-- condition is passed over.
	behind = { { "cast", "ambush", "[stealth,harm,nodead] " }, { "cast", "riposte", "[nostealth,harm,nodead] " } },
	hints = { { spell = "riposte", key = "behind", react = true } },
	-- Two strikes that both miss leave Slice and Dice without a combo
	-- point, and the sequence waits on it. Gouge (Alt+F) gives a point.
	stuck = { spell = "gouge", key = "cc" },
	cd = { riposte = 6, gouge = 10 },
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
		wing = { 2974, "Wing Clip" }, disengage = { 781, "Disengage" }, aimed = { 19434, "Aimed Shot" },
		-- new in Forever (a talent, level 25); known by its name
		summon = { 0, "Summon Hawk" },
	},
	buffs = { { "hawk", "monkey" } },
	pull = {},
	-- The guides: the pet in, Serpent Sting, Auto Shot, Arcane Shot and
	-- Aimed Shot on cooldown; from level 25 two hawks up at all times
	-- (Summon Hawk lasts 18 s and shares a 6 s cooldown with Arcane Shot,
	-- so Arcane Shot is every third cast). The shots with a cooldown are
	-- one sequence, the last line: a press waits for the one that is next,
	-- and nothing comes after it. Hawk at 0 s, Aimed Shot, hawk at 6 s,
	-- Arcane Shot at 12 s, and round again at 18 s as the first hawk goes.
	-- Hunter's Mark and Serpent Sting once per target, in one line (room).
	fight = {
		{ "raw", "/petattack [harm,nodead]" },
		{ "seq", { "mark", "serpent" }, H, "target", once = true, stop = true },
		{ "cast", "auto", H, bang = true },
		{ "seq", { "summon", "aimed", "summon", "arcane" }, H, "target", need = "summon" },
		{ "seq", { "aimed", "arcane" }, H, "target", without = "summon" },
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
	-- The guides (shadow): Power Word: Shield and Mind Blast before the
	-- pull, Shadow Word: Pain, then the wand; Mind Blast again when it is
	-- ready. (From Shadowform the guides fill with Mind Flay. The wand stays
	-- on F all the same: with the mana gone a Mind Flay line would leave the
	-- key with nothing it can cast. Mind Flay is on your own action bar.)
	-- Out of combat, with an enemy picked, F gives the shield and then
	-- casts Mind Blast (OneKey.lua, decide); in the fight Mind Blast is on
	-- Ctrl+F, and the HUD says when it is ready: it has a cooldown, and the
	-- client stops a macro at the first spell that fails.
	-- The shield from level 10 (the guides wand without it before), and
	-- not while Weakened Soul forbids it.
	shield = "pws", shieldFrom = 10, shieldBlock = 6788, opener = "mb", -- 6788: Weakened Soul
	-- Before Mind Blast (level 10) Smite opens, from range.
	pull = { { "cast", "smite", "[nocombat,harm,nodead] ", without = "mb" } },
	-- Shadow Word: Pain once per target, then the wand, which costs no
	-- mana. Mind Flay and Smite are the filler only with no wand on: as the
	-- last line the wand was never reached (a spell with no mana stops the
	-- macro; it is not skipped), so the mana ran dry. "wand" is known with
	-- a wand on.
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
	hints = { { spell = "mb", key = "behind" } },
	cd = { mb = 8, pws = 4 },
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
		-- the guides pull with Bane of Agony (it starts slow), then Corruption
		{ "seq", { "agony", "corruption", "siphon" }, HC, "target", once = true, stop = true },
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
		retaura = { 7294, "Retribution Aura" }, soc = { 20375, "Seal of Command" },
		-- new in Forever (level 6); known by its name
		strike = { 0, "Holy Strike" },
	},
	-- The guides: a blessing, Retribution Aura (level 16) and a seal up;
	-- Seal of Command once it is learned, Seal of Righteousness before.
	-- In Forever Judgement no longer uses the seal up, so the seal is kept
	-- up like a buff, out of combat.
	buffs = { { "retaura", "devotion" }, { "might" }, { "soc", "seal" } },
	pull = {},
	fight = {
		-- Judgement and Holy Strike, each when it is ready: in one sequence
		-- a press waits for the one that is next. The seal again after two
		-- rounds, for a long fight. A new target starts at Judgement.
		{ "seq", { "judge", "strike", "judge", "strike", "soc" }, H, "target", need = "soc" },
		{ "seq", { "judge", "strike", "judge", "strike", "seal" }, H, "target", without = "soc" },
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
		wf = { 8232, "Windfury Weapon" },
	},
	buffs = { { "ls" } },
	-- The guides: Rockbiter Weapon to level 30, Windfury Weapon from 30.
	-- F puts it on out of combat when the main hand has no imbue.
	imbue = { "wf", "rb" },
	pull = { { "cast", "lb", "[nocombat,harm,nodead] " } },
	-- The guides (enhancement): Lightning Bolt pulls, Flame Shock is kept
	-- up, Stormstrike on cooldown, Earth Shock fills. The shocks share a
	-- 6 s cooldown and Flame Shock burns for 12 s, so one sequence does it:
	-- Flame Shock at 0 s, Stormstrike, Earth Shock at 6 s, Flame Shock
	-- again at 12 s. A press waits for the spell that is next (the shock's
	-- cooldown, or the mob coming into reach for Stormstrike).
	fight = {
		{ "seq", { "fs", "stormstrike", "es" }, H, "target" },
	},
	heal = { { "cast", "lhw", "[@player]" }, { "cast", "hw", "[@player]" } },
	cc = { { "cast", "earthbind", "" } },
	-- Ctrl+F: Stormstrike alone
	behind = { { "cast", "stormstrike", H } },
	sos = { { "cast", "hw", "[@player]" }, { "potion" } },
	free = { { "cast", "ghost", "[nocombat]" } },
}
