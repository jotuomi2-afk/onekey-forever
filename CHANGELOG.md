# Changelog

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
