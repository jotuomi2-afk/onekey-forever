# Changelog

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
