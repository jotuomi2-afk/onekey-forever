# Changelog

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
