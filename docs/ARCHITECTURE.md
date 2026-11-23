# Test and security architecture

OneKey runs inside a game client we cannot run in CI. The architecture makes
up for that in layers, each catching what the one before cannot, and lets
Claude agents run all of them through skills. The test policy, risk register,
quality gates, requirement traceability and threat model are in
[TEST_STRATEGY.md](TEST_STRATEGY.md) (ISO/IEC/IEEE 29119-3 structure).

```
                ┌──────────────────────────────────────────────────────┐
  change ──────▶│ L1  static     security/scan.py   rules R1–R7        │
                │ L2  unit       tests/run_tests.py  Logic, macros, data│
                │ L3  simulated  tests/wowstub.lua   whole addon, 9     │
                │                classes, login → rest → fight → slash  │
                │     fuzz       tests/fuzz_test.py  random sessions    │
                │     coverage   OKD_COVERAGE=1 … --min-coverage 65     │
                │ L4  meta       tests/mutation_check.py planted faults │
                └──────────────┬───────────────────────────────────────┘
                               │ all green
                ┌──────────────▼───────────────────────────────────────┐
                │ L5  in-game    the player's session log (SavedVars), │
                │                read by the log-analysis skill        │
                └──────────────────────────────────────────────────────┘
```

## L1 Static scan (`security/scan.py`)

Reads the addon's Lua with a real Lua 5.1 tokenizer, so comments and macro
text (`/cast Claw`) are data, while a forbidden name is found however it is
reached: a call, a bare reference, `_G.Name`, `_G["Name"]`, a string that
names the API, or `_G[...]` with a computed key. Inline scripts in XML files
(`<Script>`, `On…` handlers, `<Binding>` bodies) are scanned the same way.
Reviewed exceptions (Ranks.lua's `PlaceAction`, `/okd macros`'s
`CreateMacro`) are listed with their reason in `ALLOWED_USES`. It enforces:

| Rule | What | Why |
|---|---|---|
| R1 | no casting, using, targeting or moving from Lua | automation breaks the game's terms; only secure buttons the player clicks may act |
| R2 | no chat, addon, mail or channel messages | nothing leaves the computer |
| R3 | no `loadstring`, `RunScript`, `getfenv`/`setfenv` | no hidden or downloaded code |
| R4 | no comparison or arithmetic on `UnitHealth`, `UnitPower`, … | WoW: Forever keeps them secret; it would error in game |
| R5 | no tokens, keys or e-mail addresses | secrets and personal data |
| R6 | the quest data is pfQuest (MIT) plus, for Forever's new quests, All The Things (MIT): each file with its notice and generator named, no other quest database | licence |
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
  and, as in the real client, do not take effect
- **events** reach only frames that registered them; **timers**
  (`C_Timer.After`) run when due; the **damage meter** returns plain numbers
  out of combat and secret ones in combat
- every macro written to a button is ≤ 255 characters; F and G are bound

`tests/fuzz_test.py` plays random but reproducible sessions (a seed per run)
for all classes and checks five invariants after every step: no Lua error,
no secure change in combat, no macro over 255 characters, no maths on a
secret value, no new globals. Some runs drop the client's scale curve or the
damage meter. Line coverage is measured with a Lua line hook.

## L4 Tests for the tests (`tests/mutation_check.py`)

First runs the unchanged suite, which must pass (a broken suite would
"catch" everything). Then plants 13 known faults in a copy of the addon —
a secret comparison, a spell cast from Lua, automation behind `_G`, an API
name built from strings, `loadstring`, a chat message, a script in XML, a
button change in combat, a 256+ character macro, a dropped pull spell, a
removed licence notice, other quest databases at the top and deep in the
data — and fails unless the named test fails with the expected message. A
weakened test therefore cannot pass review quietly.

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
| licence problem with bundled data | R6: QuestData.lua generated from pfQuest (MIT), QuestDataNew.lua from All The Things (MIT), nothing else |
| SavedVariables rename loses player settings | toc test |
