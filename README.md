# OneKey Forever

One key for leveling in **World of Warcraft: Forever**. Each press does what
fits the moment: buff, heal, eat, pick a target, pull or fight. Built for the
feral druid, with a general engine for every other class.

> Every action needs your own key press. The addon never casts, moves or
> targets by itself, and nothing leaves your computer. See
> [SECURITY.md](SECURITY.md).

## Install

1. Download `OneKeyForever-<version>.zip` from [Releases](../../releases).
2. Unpack it into `World of Warcraft/_forever_/Interface/AddOns/` so that
   you get `AddOns/OneKeyDruid/`.
3. Restart the game. Type `/okd bind F` to pick your key.

The folder is called `OneKeyDruid` on purpose: your settings stay when you
update from an older version.

## Keys

| Key | Druid | Other classes |
|---|---|---|
| F | buffs, cures, pulls (Wrath, or Prowl and Shred/Ravage as a cat), fights as bear or cat | buffs, conjures, pulls and fights from the class list |
| Shift+F | heal yourself | the class's defensive spell (mage: Frost Nova) |
| Alt+F | Bash / roots; out of combat eat and drink | crowd control; out of combat eat and drink |
| Ctrl+F | leave form; as a cat: Shred from behind | wand or the class's extra spell |
| G | emergency: Rejuvenation, then the bear, potion; short of mana a mana potion and straight into the bear | one emergency spell, then the potion |
| Shift+G | cat ↔ bear (also breaks roots) | get away (mage: Blink) |
| Ctrl+G | hide before going away (Shadowmeld) | Stealth / Shadowmeld |

## On screen

- your health and mana from the game itself (WoW: Forever keeps them secret
  from addons; the addon shows them but cannot read them)
- XP per hour, time to the next level, rested XP
- the next quest step: hand in, take, or what to kill, with coordinates
  (`/okd go` puts a pin and an arrow on it)
- warnings: low health, "DO NOT PULL" for mobs 3+ levels over you, elites
  and skulls, a big "RUN AWAY" when a fight turns bad, an alarm when you are
  attacked while away from the keyboard
- where to level next, what to buy, raw meat to cook

## Commands

`/okd` lists them all. The most used: `bind KEY`, `status`, `quests`, `go`,
`skip`, `where`, `mode cat|bear|auto`, `brave on|off`, `prowl on|off`,
`alarm on|off`, `herbs on|off`, `log on|off|clear`, `lang en|fi` (English by default).

## Feedback and bugs

Open an issue: [bug report or feedback](../../issues/new/choose). A few
lines of the session log around the problem help most: it is written to
`WTF/Account/<ACCOUNT>/<server>/<character>/SavedVariables/OneKeyDruid.lua`
on `/reload` or logout, and keeps other players' names out. Security
problems: privately, see [SECURITY.md](SECURITY.md).

## For developers

```
pip install lupa
python3 tests/run_tests.py        # the addon in Lua 5.1 against a fake client
python3 tests/mutation_check.py   # proves the tests catch planted faults
python3 security/scan.py          # policy scan (no automation, no network, ...)
python3 tools/build.py            # all of the above, then dist/OneKeyForever-<v>.zip
```

How the tests and the security checks fit together, and the Claude agents and
skills that run them: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Releasing: [docs/RELEASE.md](docs/RELEASE.md); CurseForge: [docs/curseforge/](docs/curseforge/).

## Licence

MIT, see [LICENSE](LICENSE). The quest data comes from pfQuest (MIT); see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
