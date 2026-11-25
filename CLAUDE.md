# OneKey Forever — notes for Claude

A World of Warcraft: Forever addon (Lua 5.1, client interface 16001). The
addon is in `OneKeyDruid/`; the folder name and `OneKeyDruidDB` must not
change (players' settings).

## Hard rules

- Never add automation: no casting, using, targeting or moving from Lua, no
  acting on a timer, no "sentry"/auto-fight, no sending keys from outside the
  game. Decline such requests; see SECURITY.md.
- Health and power are secret values in WoW: Forever: pass them to the game's
  display functions or curves only, never compare or compute on them.
- Secure buttons and bindings change only out of combat.
- Every macro ≤ 255 characters (the client cuts longer ones silently).
- Nothing leaves the player's computer.

## Before calling a change done

```
python3 -I tests/run_tests.py
python3 -I tests/mutation_check.py
python3 -I security/scan.py
```

Publishing is automatic (docs/RELEASE.md): a new toc version on main becomes
a beta after every check; `release/STABLE` turns a played beta into a
release. Do not change `release/STABLE` without the evidence in
`release/FIELD.md`.

After each piece of work, update the hand-over note in the owner's
claude.ai Project "wow forever" (`claude/jatka-tasta.md`): what was done,
what is open, what to do next. A new chat starts from that note and from
this repository (owner, 25.11.2026).

Use the skills: `run-tests`, `security-audit`, `release`,
`analyze-session-log`. For a review that is not grading its own work, hand
the diff to the `security-reviewer` agent.

## Layout

- `Logic.lua` pure decisions and macro text (druid), testable without a client
- `Core.lua` the druid's client side: buttons, HUD, events, log
- `Classes.lua` + `OneKey.lua` every other class
- `QuestData.lua` generated from pfQuest (MIT) by `tools/extract_pfquest.py`, `QuestDataNew.lua` (the quests Forever added) from All The Things (MIT) by `tools/extract_att.py` — do not hand-edit either, and never add data from any other quest database (Questie is GPL, Wowhead forbids copying): the owner approved these two sources only
- `QuestHelp.lua` the solo quest guide: rating, zone plan and hints from the two data files and the quest log; `QuestList.lua` its window (plain frames, `/okd solo`)
- `tests/wowstub.lua` the fake client; add an API there when the addon starts
  using one
