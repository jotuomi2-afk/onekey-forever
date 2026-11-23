# Changelog

## 0.35.1

- Mage, F: the opener now goes by how far the target is. Before each pull
  the addon works out how many Fireballs fit before the Frostbolt that
  slows the mob lands with it still some yards away: from what reaches the
  target (only Fireball: far; Frostbolt too: the middle; Fire Blast too:
  close) and from how long Fireball and Frostbolt take to cast right now.
  - With the short casts of the low levels: two Fireballs from far, one
    from the middle, none up close.
  - With the 3 s Fireball of the higher levels: one from range, none up
    close.
  - Attacked first: Frostbolt straight away.
  - The HUD says what is on the key: "F: attack (2x Fireball)".
  - `/okd opener 0|1|2` fixes the number; `/okd opener auto` goes back to
    the distance. The level-15 rule of 0.35.0 is gone.
  - The macro is chosen before the pull and stays for the fight (macros
    are locked in combat): a mob that joins later gets the same opener.

## 0.35.0

The solo quest guide, and the fixes from the independent review of 0.34.0.
Tested in the simulated client only; nothing here has been played yet.

- `/okd solo`, or the small "Q" button at the left edge of the screen: a
  list of what to do in the zone you are in, for a player on their own.
  - Hand-ins first, then one walk through the quests you can take and work
    on here: always the best next stop from the last one.
  - Every row is rated. Green: fine alone. Blue: a quest Forever added
    (where it starts is known, its mobs are not). Under "Not on your own
    right now": quests with an elite target or in a dungeon, quests the
    game tags for a group, and quests that are, or whose mobs are, 3 or more
    levels over you, each with the reason.
  - Under each row, what to do: for a quest in your log the game's own
    count of what is left ("Gnoll Paw: 3/8"), otherwise the quest's task
    line. Mobs are named with their level ("kill Defias Trapper (11-12)").
  - Left click: the game's map pin and arrow go to the place, and the chat
    says what to do there. Right click: leave the quest out (`/okd skip
    clear` brings all back). The mouse wheel scrolls. `/okd solo print`
    writes the rows to the chat; `/okd solo button` hides the "Q" button.
  - The addon does not walk for you and puts no markers of its own on the
    world map: the pin and the arrow are the game's.
- The HUD's one-line hint no longer names a quest that needs a group while
  there is one you can do alone.
- Quest data: every Classic quest to level 60 (it stopped at about 45),
  with each mob's level and rank, elite and dungeon quests marked, and
  the task line (pfQuest, MIT). New: where about 1 000 quests that Forever added
  start, Zephras Isle and the other new zones among them (All The Things,
  MIT; no titles or texts, the game supplies the title). Quests of your log
  that neither file knows use the place the game's own map shows.
- `/okd skip` now works for every class, not only the druid.

Mage, from play on 23.11.:

- G did nothing below level 20 (its only spell was Mana Shield). G is now
  the way out when a mob is on you: Frost Nova, then Blink, then Mana
  Shield, one press each, with the healing potion on the first press. The
  HUD says "IN MELEE: G  Frost Nova, then Blink". 25 seconds after the
  last press G starts over at Frost Nova.
- Frost Nova and Blink are on G only, so that no other key can leave G
  waiting on a cooldown. Shift+F is now Frostbolt, then Ice Lance, for a
  frozen mob (after G, or when the game lights up Ice Lance). Shift+G is
  Counterspell.
- F opens with two Fireballs, not one, below level 15: there is time for
  both before the mob arrives. From level 15 it opens with Frostbolt, as
  the guides do. `/okd opener 0|1|2` sets the number of Fireballs for every
  level; `/okd opener auto` goes back to this.

Fixes from the second independent review (of the quest guide):

- The list no longer breaks when a finished quest is handed in on another
  map (it showed no rows at all); such hand-ins are under "Elsewhere".
- Dungeon quests were rated fine alone: pfQuest has no position for most
  dungeon mobs. A quest whose target, whose item's every source, or whose
  hand-in has no place outdoors is now listed apart ("no place outdoors
  known: a dungeon?"). Still not caught before you take the quest: a few
  dungeon or elite quests the data gives no sign of (WANTED: Murkdeep!,
  Jail Break!); once in your log the game's own tag marks them.
- Ordinary quests were rated too high (Goretusk Liver Pie, Westfall Stew,
  Zenn's Bidding): the mob level came from whichever mob drops the item
  most, anywhere. Now from ordinary mobs in the quest's own zone, near its
  level.
- Quests of the other side were offered (object-started quests such as
  Wanted: Maggot Eye; Forever's quests in the starting zones). Faction now
  also comes from who the quest is handed in to, from All The Things'
  headers, and from the zone.
- Forever quests: only ids Forever added (five old ones had slipped in),
  and only with a known level.
- The walk starts from the last hand-in, not from where you stand.
- "Tried once": a press while mounted or dead no longer counts, and a buff
  given up on stays away for five minutes instead of coming back after
  every fight.
- Rogue: the changelog of the first fix overstated it. Two strikes that
  both miss still leave Slice and Dice without a combo point, and F then
  waits. The HUD now says "NO COMBO POINT: Gouge: Alt+F"; Gouge gives one.
- The mage's hints (Frost Nova, Ice Lance, Cone of Cold, Ice Barrier) also
  name nothing from a cooldown that could not be read. Cooldowns are read
  as a fight begins and then counted from your casts.
- Scanner: `_G` under another name, API names spelt with escapes and code
  inside a data file are caught; 27 planted faults, each caught.
- `/okd solo reset` puts the list and the Q button back.

Fixes from the first review:

- Rogue: Slice and Dice comes after two Sinister Strikes, not one. A
  strike that misses still moves the sequence on, and a finisher with no
  combo point would have held F for the rest of the fight.
- "Tried once" (0.34.0) did not hold when F was hammered: the offer stayed
  as long as the key was pressed. Now it is over two seconds after the
  first press of F. A key-up or another key no longer counts as the try, a
  buff given up on does not come back with every new target, and a spell
  the game says cannot be cast now (Battle Shout with no rage) is not
  offered at all.
- Priest: the wand stays the last line of F with Shadowform too. With
  Mind Flay there instead, F had nothing it could cast once the mana was
  gone. Mind Flay is on your own action bar.
- Hints fail closed: a helper key is named only when the game gave a plain
  answer. When the cooldown is hidden in a fight it is counted from your
  own cast, and with neither nothing is named.
- Weakened Soul is found by its spell, not its English name.
- The security scanner also catches a forbidden call behind another name
  (`m.RunMacroText`), a button clicked from Lua and a secret value taken
  under another name.
- SECURITY.md says what the in-combat hints are: text, from plain values.

## 0.34.0

The other seven classes, set against the WoW Forever levelling guides
(Warcraft Tavern and Method; read 23.11.2026). None of this has been
played yet: the macros are tested in the simulated client only.

- New for every class: the HUD names a helper key when its spell can be
  used. A reactive spell (after a dodge or a parry, under 20 % health) is
  named when the game says it is usable; a cooldown spell when it is ready.
- New for every class: what F offers before a fight (a buff, a shield, a
  weapon imbue, an opener) is tried once. A press that does not help (no
  rage or mana, out of range) no longer holds the key; the next press
  attacks.
- Warrior:
  - With Mortal Strike or Bloodthirst learned, F is Rend once and the
    strike. Heroic Strike on every press took the rage the strike needs;
    it stays on your own action bar for a full rage bar. Without a strike
    talent F is Rend and Heroic Strike, as before.
  - The HUD says "OVERPOWER: Ctrl+F" after a dodge and "EXECUTE: Shift+F"
    under 20 % health.
- Rogue:
  - Slice and Dice is the first finisher, right after the first Sinister
    Strike (the guides: as soon as possible). Then the stun chain as
    before.
  - Ctrl+F in a fight is Riposte; the HUD says so after a parry. From
    stealth it is still Ambush.
- Hunter:
  - Aimed Shot and Arcane Shot are one sequence, the last line of F, so
    each goes out when it is ready.
  - With Summon Hawk (level 25): hawk, Aimed Shot, hawk, Arcane Shot. Two
    hawks stay up, as the guides ask (the hawk shares Arcane Shot's
    cooldown).
  - Hunter's Mark and Serpent Sting are one line, once per target, so that
    the macro fits.
- Priest:
  - Before a pull, from level 10: Power Word: Shield (not under Weakened
    Soul), then Mind Blast as the opener, then the fight: Shadow Word:
    Pain and the wand.
  - In the fight the HUD says "MIND BLAST: Ctrl+F" when it is ready.
  - Before Mind Blast, Smite opens from range.
  - From Shadowform Mind Flay fills, not the wand.
- Warlock: Bane of Agony first, then Corruption, then Siphon Life. The
  wand stays the filler on F: Drain Life, the guides' filler from level 30,
  reaches less far than the wand, and a cast out of range stops the key.
  It is on Shift+F.
- Paladin:
  - In Forever Judgement no longer uses the seal up. The seal is now kept
    up out of combat like a buff (Seal of Command once learned), with
    Retribution Aura (before it Devotion Aura) and Blessing of Might.
  - F is Judgement, Holy Strike, Judgement, Holy Strike, then the seal
    again, in one sequence: each when it is ready. It was the seal and
    Judgement by turns, and Holy Strike was missing.
- Shaman:
  - Out of combat F puts on Windfury Weapon (Rockbiter Weapon before
    level 30) when the main hand has no imbue.
  - F is Flame Shock, Stormstrike, Earth Shock in one sequence. The shocks
    share a cooldown and Flame Shock burns for 12 seconds, so it is renewed
    as it ends, and Stormstrike goes in between.
- Left out, and why:
  - Victory Rush, Blade Flurry, Adrenaline Rush, Rapid Fire, Bestial
    Wrath, Devouring Plague, Shadow Word: Death, Consecration, totems:
    no free key, a long cooldown, or a use the addon cannot judge. Use
    them from your own action bar.
  - Shank (rogue) and the other new Forever spells whose cost and cooldown
    the guides do not give.
  - Summon Hawk and Holy Strike are found by their English names.

## 0.33.0

Frost mage, set against the WoW Forever guides (Icy Veins, Wowhead, Method,
Warcraft Tavern; read 22.11.2026). Their priority at level 60: Ice Barrier
up, Cone of Cold at five stacks of Winter's Chill, Ice Lance on a frozen
target or with Fingers of Frost, Frostbolt for everything else.

- F from level 15: Frostbolt from the first press. It is the faster cast,
  the mob is slowed from the first hit, and every hit can freeze it
  (Frostbite), give Fingers of Frost and build Winter's Chill. Below
  level 15 Fireball still opens once per target, as before.
- F before a pull, level 40: with an enemy picked, Ice Barrier first when
  it is not up and not on cooldown; the next press attacks. Its Frigid
  Power buff adds damage for a minute. A press that does not bring the
  shield (no mana) is tried once, then the key attacks.
- Ctrl+G: Ice Barrier in a fight. The HUD asks for it a minute after the
  last cast ("Ice Barrier: Ctrl+G").
- Shift+F: Frost Nova, then Frostbolt, then Ice Lance, so that both land on
  the frozen mob (Shatter). It was Nova, Ice Lance. The HUD says "FROZEN:
  step back, Shift+F x2". Left alone for 10 seconds the sequence starts
  over, so the next Nova is the first press again (before, the key could
  be left waiting on Ice Lance).
- Winter's Chill, level 35: the HUD counts your Frostbolt and Ice Lance
  casts on the target and at five asks for Cone of Cold ("WINTER'S CHILL
  x5: close in, Ctrl+F until Cone of Cold"). The stacks themselves are
  secret in combat, so a resisted cast is counted too. `/okd cone off`
  turns the hint off (for a build without the talent).
- Ice Armor (or Frost Armor) is the armour F keeps up, before Mage Armor:
  alone in the world the armour and the chill on attackers are worth more.
- Not done, because the addon cannot see it: Fingers of Frost and Frostbite
  procs are auras, and auras are secret in combat. When the game lights up
  Ice Lance at range, press Ice Lance on your own action bar right after
  a Frostbolt (Shift+F would start with Frost Nova).

## 0.32.4

- Druid, F (reported 22.11.: "F turns me from cat into caster form now
  and then"): in cat or bear form with an enemy picked, F no longer leaves
  the form to renew a Mark of the Wild that still has time on it (it
  renewed five minutes early). The Mark is renewed in caster form or with
  no target; a Mark that is gone altogether is still put back.
  (In the log the other changes to caster form in a fight were Shift+F.)
- Druid, F in a party: out of combat, a party member in range without
  Mark of the Wild gets it (`/cast [@party2] Mark of the Wild`); the HUD
  says who. Not in a raid, and not while you are in form with a target.

## 0.32.3

- The AFK alarm (every class) keeps sounding for as long as the fight
  lasts, up to three minutes: every 2 s for half a minute, then every 3 s.
  In the log of 22.11. a Rabid Dire Wolf took 78 seconds to kill the druid
  while away, and the alarm had gone quiet after 30 seconds.

## 0.32.2

- Druid, cat F (from the log of 22.11.): Ferocious Bite came with only two
  Claws behind it, so it hit with two or three combo points. The sequence is
  now Faerie Fire, Rake, Claw, Claw, Rip, Claw, Claw, Claw, Ferocious Bite:
  Rip with three combo points (Rake and two Claws), the Bite with three
  Claws more.
- Shorter, sturdier macros:
  - Druid, Shift+G is now one short line: `/cast [form:3] Bear Form; Cat
    Form` (cat to bear, anything else, water and travel form too, to cat).
  - Warrior, F: Overpower and Execute were first on F, but they can be
    used only after a dodge or under 20 % health, and a spell that cannot
    be used stops the macro, so Rend and Heroic Strike were seldom reached.
    F is now Rend once and Heroic Strike; Ctrl+F is Overpower, Shift+F
    Execute, Shift+G Bloodrage. The macro test now knows these spells.
- The trainer hints follow Forever: Shred at 20, Rake and Ferocious Bite at
  24 (Classic had 22 and 32).

## 0.32.1

From the log of 21.11. evening (a death at a gnoll camp: a Wrath pull,
seven gnolls on, 35 hits in 42 seconds):

- Druid, F: before a pull the HUD counts the other living enemies within
  Wrath's range (from their nameplates). Two or three: an orange "careful,
  N more mobs close". Four or more: "DO NOT PULL", and F does not pull, as
  for an elite. `/okd brave on` lets you pull anyway.
- Druid, cat F: once Ferocious Bite is learned (level 32) the sequence
  finishes with Rip first and Ferocious Bite second (before, Bite replaced
  Rip in both rounds). Short of space, two rounds with a Claw fewer instead
  of one round, so Faerie Fire is not recast every round.
- Druid, G in bear form stays in the bear and drinks the potion: leaving
  the form near death dropped its armour, and Rejuvenation and Nature's
  Grasp came too late. From cat or caster form G heals as before.

## 0.32.0

- Priest, F: Shadow Word: Pain goes on once per target, then the wand
  shoots until the mob dies. Before, Mind Flay or Smite was the last spell
  and the wand line after it was never reached: a spell with no mana stops
  the macro instead of being skipped, so the priest ran dry. With no wand
  on, Mind Flay and Smite are the filler as before; Mind Blast stays on
  Ctrl+F. (The same fix the warlock got in 0.31.0.)

## 0.31.3

- Druid, G: when the mana is too short for the heal and the bear, G drinks
  a mana potion (if you carry one) once in the fight, then takes the bear
  on the same press. A macro cannot read your mana; this is the fight-start
  budget of 0.31.2. No healing potion follows it (potions share a cooldown).
- A potion still on its cooldown as a fight starts is left out of G: a
  failed use stops the macro, and the bear behind it never came.

## 0.31.2

- Druid, G (from the log of 21.11.): the death came when G left cat form
  with two mobs on, healed, cast Nature's Grasp, and then could not afford
  Bear Form: the pull (Wrath twice, Rejuvenation, Moonfire, cat form,
  Faerie Fire) had spent the mana. Eight seconds in caster form, and dead.
  - G is set when the fight starts, so it now counts the pull's mana too.
    It leaves cat form to heal only when the pull, Rejuvenation and the bear
    all fit in your mana; Nature's Grasp only when it fits as well.
  - Otherwise G takes a cat straight into the bear (one shift) and the
    potion; heal with Shift+F.

## 0.31.1

- Druid: Prowl on the action bars now really becomes the OKD Prowl macro.
  The swap looked Prowl up in the spellbook through functions this client
  does not have, so it never found it (and rank upgrades never ran either).
  It now reads the spellbook through C_SpellBook too, and knows Prowl on a
  bar by its name.
  - First press in caster form: cat form. Second press: Prowl. (The game
    cannot do both on one press: the form changes only after the press.)
  - `/okd prowlkey on` says what it did, or that Prowl was not found on the
    bars (then drag OKD Prowl from /macro onto the bar).

## 0.31.0

- Warlock, F: the pet goes in, then Corruption, Bane of Agony and Siphon
  Life (when learned) go on once per target, and then the wand shoots until
  the mob dies. Before, Shadow Bolt was the filler: it spent all the mana,
  and the wand line after it was never reached.
  - With no wand on, Shadow Bolt is the filler as before.
  - No line of F cuts Drain Life (Shift+F) short.
  - Ctrl+F: Immolate once, then Shadow Bolt, for a mob that must die fast.
- Every class now writes the session log, like the druid (on by default,
  `/okd log on|off|clear`): fights, casts, key presses, experience, deaths,
  level-ups, zones. `tools/analyze_log.py` reads it. Other players are
  written as "player".

## 0.30.4

- Hunter, in melee: when the mob is on you, a large HUD line says "IN
  MELEE: Ctrl+F Raptor Strike, then step back and F".
  - F cannot switch to melee by itself: a macro cannot see the range, and
    the game stops it on "target too close".
  - Ctrl+F is now Wing Clip (once per target, to slow the mob so you can
    step back), Mongoose Bite after a dodge, then Raptor Strike.
- Every class: the game's spoken error ("not ready yet", "target too
  close") is off while the addon runs. One key pressed again and again set
  it off all the time. The red text stays. `/okd errorvoice on` brings the
  voice back as it was.

## 0.30.3

- Druid: the OKD Prowl macro prowls again.
  - It names cat form by its stance number. When it was made before the game
    had listed your forms, it got a guessed number. Your cat form has another
    number, so the macro turned cat form off and on ("Ability is not ready
    yet") instead of prowling.
  - The macro is now made only once your forms are known.
  - If the existing macro has the wrong number, the addon corrects it out of
    combat. It changes no other macro.

## 0.30.2

- Druid, water: the shift into and out of Aquatic Form now goes into F's
  macro as the game's own `[swimming]` condition. The game checks it at
  the moment you press. In 0.30.1 the addon tried to find out itself
  whether you were swimming, and on WoW: Forever that did not work. Out of
  combat, in water F goes into Aquatic Form; out of the water, still in
  Aquatic Form, it goes into your fighting form. The long fight macro has
  no room for these lines.

## 0.30.1

- Druid, out of combat: in water F shifts you into Aquatic Form, and back on
  land it shifts you into your fighting form (cat, or bear in bear mode).
  Each shift takes one press. The HUD shows what F will do. In combat F
  stays the fight key.

## 0.30.0

- Druid: pressing Prowl outside cat form now shifts into cat form first; the
  next press prowls. The addon makes the macro "OKD Prowl" once and puts it
  in place of Prowl on your action bars. This happens out of combat, once
  per slot: if you put Prowl back by hand, it stays. `/okd prowlkey off`
  leaves your bars alone. Pressing it again while you prowl does not end
  the stealth.

## 0.29.6

- Druid G: the heal comes first. In order: Rejuvenation together with the
  potion, then Nature's Grasp, then Bear Form. In the death to Ilkrud
  Magthrull, Nature's Grasp came first and took the global cooldown when
  the heal was needed.
- Druid Shift+G (break free from roots) swaps forms: cat to bear, bear to
  cat, caster form to your fighting form. WoW: Forever has no
  powershifting, so the 0.29.1 way of shifting back into the same form
  did not work.

## 0.29.5

- Druid: Faerie Fire is cast again.
  - In 0.29.2 it moved to a line after the cat sequence, on the idea that
    a spell without energy is skipped. The game instead stops on "not
    enough energy", so Faerie Fire was never reached.
  - Cat: Faerie Fire now opens the sequence, and the sequence runs two
    rounds (Claw ×3, Rip, Claw ×3, Rip) before it starts over. That makes
    it once a fight rather than every round. From level 32 there is only
    room for one round.
  - Bear: Faerie Fire once per target, before Maul. A Maul without rage
    stops the macro, so Faerie Fire placed after it never came.

## 0.29.4

- Druid G (the emergency key), reworked after "no Nature's Grasp and no
  bear with two mobs on me". Press it repeatedly:
  1. Nature's Grasp: the next mob to hit you is rooted. Once per fight,
     and only when it is ready as the fight starts; the key is set then.
  2. Rejuvenation on yourself, plus the potion.
  3. Bear Form: more health and armour while they are on you. The old key
     went into cat or travel form instead.
  4. After that, only the potion, until 20 s without a press or the end
     of the fight.
  The old key looped back to the start, where a spell on cooldown stops
  the whole macro. From cat form the key leaves the form first; from
  bear form Rejuvenation leaves it by itself, so a later press does not
  drop the bear again.
- The simulated client keeps spell cooldowns.

## 0.29.3

- Druid: F no longer heals at full health before a pull. When a mob type
  has usually cost over 60 % of your health (a tough mob at +1 or +2
  levels), F healed before every pull, even at full health, and only then
  cast Thorns and Mark of the Wild. A heal before a pull now needs at
  least 15 % of your health missing, so the buffs come first.

## 0.29.2

From the log of 20.11. (three sessions, level 22-23, Ashenvale and
Stonetalon, three deaths):

- Cat: Faerie Fire is no longer part of the Claw-Rip sequence, where it came
  back every round (about 60 times in 29 fights), each time taking a global
  cooldown away from Claw. It now comes after the sequence, so it is cast
  only while the sequence waits for energy. Feral Faerie Fire costs no
  energy, so this uses time the cat would otherwise stand idle. When space
  runs out, the cat drops the start-attack line first, because Claw starts
  the swing by itself.
- Bear: Maul comes before Faerie Fire. On its cooldown (a new mob within
  6 s), Faerie Fire would have stopped the Maul.
- Ctrl+F (Shred/Ravage from behind) follows the pull guard. On an elite or
  a mob three levels above you it does nothing, unless you have typed
  `/okd brave on`. One death came from opening on Taskmaster Whipfang, a
  rare elite, with Shred from stealth.
- After a corpse run the addon counts you at half health, so F heals and
  rests before the next pull. One death came from a pull right after a
  resurrection, against three mobs.

## 0.29.1

- Druid, rooted: the HUD shows "ROOTED: Shift+G breaks free".
  - In cat or bear form, Shift+G powershifts straight back into the same
    form, which removes the roots. Without enough mana the game refuses the
    shift, so you are never left rooted in caster form.
  - In caster form, Shift+G goes into your fighting form, which also
    removes the roots. For 8 seconds after that the HUD shows "Back to
    caster form: Ctrl+G".
  - A macro cannot remember the form you came from, and keys cannot change
    in combat, so the return to caster form takes its own press.

## 0.29.0

- The addon's texts are in English by default, for release. Characters
  that had Finnish switch to English once; `/okd lang fi` brings Finnish
  back and stays.

## 0.28.3

- Rogue: F chains the stuns, as the WoW Forever guides advise:
  - Cheap Shot from stealth, Sinister Strike up to 5 combo points, then
    Kidney Shot.
  - One more Sinister Strike while the mob is stunned, then Gouge as the
    stun ends (the energy comes back while Gouge holds).
  - Then Sinister Strike again and Eviscerate.
  - Kidney Shot and Gouge sit inside one sequence: on cooldown, a press
    waits for them instead of stopping the whole key.
  - Before Kidney Shot (level 30): Sinister Strike to 5 points, Eviscerate,
    Gouge, and round again.
- Mage: the Frostbolt slow never lapses. Fireball opens once per target,
  and every press after that is Frostbolt, whose slow lasts longer than its
  cast. Fireball no longer comes back mid-fight.

## 0.28.2

From the log of 19.11. (a death in Ashenvale against three furbolgs):

- The emergency key G did nothing after the first press. Its first lines
  (the potion, Bash, Nature's Grasp) were on cooldown, and the game stops
  a macro at the first failed cast, so 49 presses in 13 seconds did
  nothing.
  - Druid G now: out of the form, Rejuvenation on yourself, back into a
    form (travel, cat or bear), with the potion last. The potion does not
    trigger the global cooldown, so it goes in on the same press.
  - Bash stays on Alt+F, and Nature's Grasp is on the action bar.
- All other classes: G is one emergency spell, then the potion.
  - Mage: Mana Shield. Warrior: Demoralizing Shout. Rogue: Evasion.
  - Hunter: Feign Death. Priest: Power Word: Shield. Warlock: Fear.
  - Paladin: Divine Shield. Shaman: Healing Wave.
- Druid Alt+F: Entangling Roots before Hibernate. Hibernate fails on
  anything but beasts and dragonkin, and so stopped the roots. Bash is now
  last.
- The test now checks every macro: F, G and all the druid keys. Run on the
  old code, it found 20 such problems.

## 0.28.1

- Druid, cat in stealth: F opens with Pounce, or with Claw before Pounce is
  learned. Ravage and Shred fail from the front of a mob, and a failed
  cast stops the macro, so F in stealth did nothing from the front. They
  stay on Ctrl+F, the key for when you are behind the mob. The HUD says
  so.
- Hunter: Arcane Shot is the last line of F, after Auto Shot, so its
  cooldown cannot stop anything. Ctrl+F is the melee key: Mongoose Bite
  after a dodge, otherwise Raptor Strike. Shots fail inside their minimum
  range, so F cannot also hold the melee attacks.
- Priest: a press during Mind Flay no longer cuts it short. The wand waits
  for channels to end for every class.
- The test that keeps cooldown spells away from the start of F now also
  covers spells that need you behind the target (Shred, Ravage, Backstab,
  Ambush).

## 0.28.0

The game stops a macro at the first spell that fails, for example one on
cooldown or out of range, and the lines after it never run. Spells the game
cannot use at all (no mana, not learned) are skipped. The old macros
assumed that a spell on cooldown was skipped too, so a cooldown early in a
macro could block the whole key.

- Mage:
  - F: Fireball (the longest range), then Frostbolt ×4, which keeps the mob
    slowed. The wand fires when you are out of mana. No cooldown spells
    remain on F.
  - Shift+F: Frost Nova, then Ice Lance on the frozen mob (Shatter).
  - Ctrl+F: Fire Blast, then Cone of Cold, for instant damage while moving.
  - In combat, a large HUD line says when a mob has reached you
    ("IN MELEE: Shift+F Frost Nova"), and after the Nova "FROZEN: Shift+F
    Ice Lance, then step back and F". It only shows text: the key cannot
    see range or cooldowns, and macros are locked in combat.
- Druid: Enrage and Feral Charge are no longer on F. With Enrage on cooldown
  or Feral Charge too close to the mob, they stopped the macro before Maul
  or the cat sequence.
- Priest: Mind Blast moved to Ctrl+F. Shaman: Stormstrike moved to Ctrl+F.
  Hunter: Arcane Shot moved to Ctrl+F (after Mongoose Bite).
- A new test checks that no fight macro has a cooldown spell before
  another spell.

## 0.27.1

- Mage: F pulls with Fireball, the longest-range spell (35 yd), then casts
  Frostbolt twice to slow the mob as it runs in, then Fireball again.
  Fire Blast goes in whenever it is ready once the fight has started and
  the mob is within 20 yards. A new target or the end of the fight starts
  over at Fireball. Before this, F opened with Frostbolt and never cast
  Fireball in a fight.

## 0.27.0

The addon is now called **OneKey Forever** (the folder and the saved
settings keep their names, so nothing is lost). Restart the game once: the
addon's title changed.

Fixes from an independent bug hunt and security review:

- With no enemy targeted, the key now only picks a target. The next update
  checks its level and class, so the "do not pull: elite or +3" guard can no
  longer be skipped in the same press.
- The AFK alarm sounds again (it switched itself off at the start of every
  fight).
- Quest hints no longer offer Horde quests to Alliance players (for example
  Grom'gol in Stranglethorn): a quest's faction now also comes from its quest
  giver. Hints are worked out twice as fast.
- Druid: Faerie Fire stays in the bear macro, and the Wrath pull stays in the
  cat macro from level 32 (the cat sequence uses two Claws when space is
  short). "Faerie Fire (Feral)" is written so that the game does not read it
  as a rank. Macros are never cut in the middle of a line.
- Other classes: the main spell (Shadow Bolt, Raptor Strike, ...) is no
  longer dropped when the macro is long. Paladins no longer recast the seal
  on every press: the seal, then Judgement when ready, then the seal again.
- `/okd bind` and `/okd sos` accept only real keys (no `shift-f`, no `F G`)
  and refuse each other's key.
- After a `/reload` in combat the keys start working when the fight ends.
- Other classes count only damage taken as hits (heals and dodges used to
  set off RUN AWAY).
- `/okd hud` (and the other switches) without on/off now tells the setting
  instead of turning it off.
- `/okd alarm off` gives back the game's "sound in background" setting.
- The session log writes "player" instead of other players' names.

Testing (see docs/TEST_STRATEGY.md): a test strategy with a risk register,
quality gates and a requirement-to-test table; property-based fuzzing
(4,500 random sessions before a release); line coverage with a 65 % gate
(74 % now); 13 planted faults, each of which must be caught with the right
message, after a passing baseline; a static scanner with a real Lua
tokenizer that also sees `_G` lookups, strings that name an API and XML
scripts; the quest-data generator runs pfQuest's files in a sandbox and only
at the pinned revision.

## 0.26.0

- When you learn a new rank of a spell, the spell on your action bars moves
  up to it (out of combat, after training). A lower rank you put back on
  purpose stays. `/okd ranks` checks the bars now, `/okd ranks off` turns it
  off.

## 0.25.0

- Quest hints now come from pfQuest's own database only (MIT), built by
  `tools/extract_pfquest.py`. Positions are corrected for mobs that span two
  zones (for example Redridge and Swamp of Sorrows mobs).
- Forever's new zones and quests are not in pfQuest, so they get no hints.

## 0.24.3

First packaged version.

- Druid: one key for buffs, cures, pulls and fights as caster, bear or cat.
  Cat pulls with Prowl and Shred/Ravage from behind; Faerie Fire opens the
  cat's builder-finisher sequence. Shift+G switches cat ↔ bear and breaks
  roots. G is the emergency key; Ctrl+G hides (Shadowmeld) before going away.
- Every other class: a general engine with class lists (mage tuned most).
- Health and mana shown from the game's own values (secret to addons in
  WoW: Forever); low-health, "DO NOT PULL" and "RUN AWAY" warnings; an alarm
  when attacked while away.
- Quest hints (hand in, take, do) with coordinates and a map pin
  (`/okd go`), `/okd skip`, automatic skip of a quest the giver will not
  offer.
- XP per hour, time to the next level, rested XP; zone advice; what to buy;
  raw meat to cook; Find Herbs on the minimap.
