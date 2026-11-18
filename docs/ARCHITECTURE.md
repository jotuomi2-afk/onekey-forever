# Test and security architecture

OneKey runs inside a game client we cannot run in CI. The architecture makes
up for that in four layers, each catching what the one before cannot, and
lets Claude agents run all of them through skills.

```
                ┌──────────────────────────────────────────────────────┐
  change ──────▶│ L1  static     security/scan.py   rules R1–R7        │
                │ L2  unit       tests/run_tests.py  Logic, macros, data│
                │ L3  simulated  tests/wowstub.lua   whole addon, 9     │
                │                classes, login → rest → fight → slash  │
                │ L4  meta       tests/mutation_check.py planted faults │
                └──────────────┬───────────────────────────────────────┘
                               │ all green
                ┌──────────────▼───────────────────────────────────────┐
                │ L5  in-game    the player's session log (SavedVars), │
                │                read by the log-analysis skill        │
                └──────────────────────────────────────────────────────┘
```

## L1 Static scan (`security/scan.py`)

Reads the addon's files with comments and strings removed (macro text such as
`/cast Claw` is data, not a call) and enforces:

| Rule | What | Why |
|---|---|---|
| R1 | no casting, using, targeting or moving from Lua | automation breaks the game's terms; only secure buttons the player clicks may act |
| R2 | no chat, addon, mail or channel messages | nothing leaves the computer |
| R3 | no `loadstring`, `RunScript`, `getfenv`/`setfenv` | no hidden or downloaded code |
| R4 | no comparison or arithmetic on `UnitHealth`, `UnitPower`, … | WoW: Forever keeps them secret; it would error in game |
| R5 | no tokens, keys or e-mail addresses | secrets and personal data |
| R6 | the quest data keeps its pfQuest MIT notice | licence |
| R7 | only `.lua .toc .xml .md LICENSE` in the package | no stray scripts or data |

It also runs on the staged release folder in `tools/build.py`, so the zip
itself is checked, not only the source.

## L2 Unit tests (in `tests/run_tests.py`)

- every `.lua` compiles in **Lua 5.1** (the client's version)
- the toc lists existing files; `## Version` equals `VERSION` in Core.lua and
  OneKey.lua; the SavedVariables name never changes
- `Logic.BuildMacros` for the druid at levels 1–40, caster/bear/cat,
  selfcast on/off: every macro ≤ 255 characters (the client cuts longer
  ones silently — this is how Faerie Fire once fell out unnoticed), the cat
  keeps Claw and Faerie Fire, the bear keeps Maul, a fight always ends in a
  form, the cat pull has a fallback
- zone advice and water by level
- quest data: every record has 13 fields, objectives parse, at most 2 % of
  quest givers lack a location

## L3 Simulated client (`tests/wowstub.lua`)

A fake WoW: Forever, loaded into Lua 5.1 before the addon's toc files. Each
of the nine classes logs in, rests, gets a target, enters combat, takes hits,
leaves combat and runs every slash command. The fake client enforces the
real client's rules:

- **secret values**: `UnitHealth`, `UnitPower`, `UnitHealthPercent`… return
  objects that raise an error on comparison, arithmetic or concatenation;
  passing them to `SetFormattedText`, `SetAlpha` or `pcall` works, as in
  game
- **taint guard**: `SetAttribute`, `SetOverrideBindingClick` and
  `ClearOverrideBindings` during combat lockdown are recorded as violations
  (the real client blocks them and the key stops working)
- every macro written to a button is ≤ 255 characters; F and G are bound

## L4 Tests for the tests (`tests/mutation_check.py`)

Plants six known faults in a copy of the addon — a secret comparison, a
spell cast from Lua, a chat message, a button change in combat, a 256+
character macro, a removed licence notice — and fails unless the suite
catches every one. A weakened test therefore cannot pass review quietly.

## L5 In-game evidence

The fake client cannot tell whether a rotation is good. The player's session
log (SavedVariables, never sent anywhere) records fights, casts, key
presses, XP, deaths and the quest hints shown. The `analyze-session-log`
skill turns it into XP/h, time use, deaths and their causes, and the
proposed next change. Findings that can be turned into a rule become L2 or
L3 tests (the 255-character test came from such a finding).

## Agents and skills

| Agent (`.claude/agents/`) | Uses skills | Can change code? |
|---|---|---|
| `test-runner` | `run-tests` | no — reports failures with the failing line |
| `security-reviewer` | `security-audit` | no — read-only review, reports findings by rule |
| `release-manager` | `run-tests`, `security-audit`, `release` | bumps version and changelog; never pushes or tags without the owner |
| `log-analyst` | `analyze-session-log` | no — reads the player's log, proposes changes |

The security reviewer works from a fresh context and does not see the change
being made, so the work is not grading itself. Its review goes beyond the
scanner: new APIs, a change that moves a decision from the player to the
addon, anything that waits on a timer to act.

## Threat model (short)

| Threat | Control |
|---|---|
| addon acts by itself (ban risk) | R1, L3 taint guard, reviewer agent, SECURITY.md "will not add" |
| data leaves the computer | R2; log only in SavedVariables |
| malicious contribution hides code | R3, R7, mandatory review, CI on every PR |
| compromised CI action or dependency | actions pinned to SHAs, `lupa` pinned with hashes, read-only permissions |
| tampered release zip | built in CI from the tag, SHA-256 published, draft reviewed before publishing |
| licence problem with bundled data | R6; open question on the quest data source (docs/RELEASE.md) |
| SavedVariables rename loses player settings | toc test |
