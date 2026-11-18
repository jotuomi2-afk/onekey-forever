# Changelog

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
