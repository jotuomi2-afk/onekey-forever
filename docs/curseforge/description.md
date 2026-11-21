# OneKey Forever

**One key for leveling in World of Warcraft: Forever.** Each press of your key does what fits the moment: buff, heal, eat, pick a target, pull or fight. Built for the feral druid, with a general engine for every other class.

> **Every action needs your own key press.** The addon never casts, moves or targets by itself, never acts on a timer, and nothing leaves your computer. It only decides which macro your key holds.

## Keys

| Key | Druid | Other classes |
|---|---|---|
| **F** | buffs, cures, pulls (Wrath, or Prowl and Shred/Ravage as a cat), fights as bear or cat | buffs, conjures, pulls and fights from the class list |
| **Shift+F** | heal yourself | the class's defensive spell (mage: Frost Nova) |
| **Alt+F** | Bash / roots; out of combat eat and drink | crowd control; out of combat eat and drink |
| **Ctrl+F** | leave form; as a cat: Shred from behind | the class's extra spell |
| **G** | emergency: heal, then the bear, potion; short of mana a mana potion and straight into the bear | one emergency spell, then the potion |
| **Shift+G** | cat ↔ bear (also breaks roots) | get away (mage: Blink) |
| **Ctrl+G** | hide before going away (Shadowmeld) | Stealth / Shadowmeld |

Class rotations follow the usual leveling advice: the warlock and priest put their damage over time on once and then use the wand, the mage opens with Fireball and keeps the mob slowed with Frostbolt, the rogue chains its stuns, the hunter keeps its pet and Auto Shot going.

## On screen

- your health and mana from the game itself
- XP per hour, time to the next level, rested XP
- the next quest step (hand in, take, what to kill) with coordinates; `/okd go` puts a pin on it
- warnings: low health, "DO NOT PULL" for mobs 3+ levels over you, elites, a big "RUN AWAY" when a fight turns bad, an alarm when you are attacked while away
- where to level next, what to buy, raw meat to cook

## Getting started

1. Install, log in, type **`/okd bind F`** to pick your key.
2. `/okd` lists every command (`status`, `quests`, `go`, `mode cat|bear|auto`, `log on|off`, `lang en|fi`, ...).

## Feedback and bugs

Please use the GitHub issues: https://github.com/jotuomi2-afk/onekey-forever/issues (bug report and feedback forms). A few lines of the session log around the problem help most; the log keeps other players' names out.

Source, tests and security policy: https://github.com/jotuomi2-afk/onekey-forever — MIT licence. Quest data from pfQuest (MIT).
