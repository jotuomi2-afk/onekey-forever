# Test policy and strategy — OneKey Forever

The structure follows ISO/IEC/IEEE 29119-3 (organisational test policy, test
strategy, risk register, test plan, completion report), scaled down for a
one-person addon. Testing is risk based (29119-2): each risk below has an
owner test, and a risk without a test is a gap that blocks a release.

## 1. Test policy

* An addon that breaks in combat costs the player a character death, so the
  combat path is held to the strictest gates.
* The addon must stay inside Blizzard's rules for addons. One press does at
  most one action. Nothing runs on its own. There is no automation of play.
  The tests prove that the secure path is never changed in combat (taint).
* No user data leaves the machine. SavedVariables and logs are never
  uploaded, and no test fixture contains real player data.
* Only MIT-licensed third-party data (pfQuest) is shipped.
* A failing gate stops the release; nothing is waived silently.

## 2. Test levels and types

| Level | What | Tool | When |
|---|---|---|---|
| L1 static | Security rules R1–R7: forbidden APIs, network and file access, globals, licence markers, workflow pinning | `security/scan.py` | every commit, CI |
| L2 unit | Macro builder at every level, form and setting; 255-character limit; toc and version agreement; quest-data integrity | `tests/run_tests.py` | every commit, CI |
| L3 integration | The whole addon loaded in a simulated client (`tests/wowstub.lua`): secret values raise on comparison or arithmetic; secure changes in combat are recorded and blocked, as in the client; events reach only frames that registered them; timers run; the damage meter returns secret values in combat | `tests/run_tests.py` | every commit, CI |
| L3 property / fuzz | Random reproducible sessions for nine classes: random targets, combat, forms, zones, deaths, events, and slash input, including junk; client variations (no scale curve, no damage meter) | `tests/fuzz_test.py` | 40 runs per class in CI, 500 before a release |
| L3 performance | `QuestHelp.Refresh` + `Hint` under 8 ms per call | `tests/run_tests.py` | every commit |
| Test-quality check | Mutation check: the unchanged suite must pass first, then 13 planted faults must each fail the named test with the expected message | `tests/mutation_check.py` | CI |
| Coverage | Approximate line coverage with a Lua line hook; gate 65 % | `OKD_COVERAGE=1 tests/run_tests.py --min-coverage 65` | CI |
| L4 acceptance | Playing in the real client: `/okd runtest`, session log, `tools/analyze_log.py` | manual | before a release |

The pyramid is deliberate. Most checks are fast unit and simulated-client
tests, and only the last level needs the game. The real client cannot be
driven by tests without breaking the no-automation policy.

## 3. Entry and exit criteria

Entry (a change may be tested): it compiles in Lua 5.1, and the toc lists every file.

Exit (a release may be built), the quality gates:

1. Every test in `run_tests.py` passes.
2. The fuzz run passes (500 runs per class before a release).
3. All mutants are caught.
4. The scan reports no findings.
5. Line coverage is at least 65 %.
6. Every requirement in section 5 has a passing test.
7. One session has been played in the real client with no Lua error.
8. The tag matches the toc version (checked by the release workflow).

## 4. Risk register

Likelihood (L) and impact (I) are rated 1–3; their product sets the depth of testing.

| ID | Risk | L | I | Mitigation and test |
|---|---|---|---|---|
| RK1 | A Lua error in combat stops the key | 2 | 3 | REQ-01, fuzz I1 |
| RK2 | Taint: a secure attribute or binding changes in combat and is blocked | 2 | 3 | REQ-02, fuzz I2 |
| RK3 | A macro over 255 characters is cut and loses a spell | 3 | 2 | REQ-03, fit() priorities |
| RK4 | Arithmetic on a secret value raises an error | 2 | 3 | REQ-04, the stub raises |
| RK5 | A fight never shifts into a form | 2 | 2 | REQ-05 |
| RK6 | The pull spell falls out of the macro (seen at level 32) | 2 | 2 | REQ-06 |
| RK7 | Quest data of an incompatible licence gets in | 1 | 3 | REQ-07, scan R6, mutant |
| RK8 | Quest hints for the wrong faction or class | 2 | 1 | REQ-08 |
| RK9 | Rank updating moves buttons in combat or with a full cursor | 1 | 2 | REQ-09 |
| RK10 | A leaked global clashes with another addon | 2 | 1 | REQ-10, fuzz I5 |
| RK11 | Quest refresh causes stutter | 1 | 2 | REQ-11 |
| RK12 | Junk slash input crashes the addon | 2 | 1 | REQ-12 |
| RK13 | Supply-chain attack through CI actions or Python packages | 1 | 3 | REQ-13, pinned SHAs, hashed requirements |
| RK14 | Automation creeps in (a button or timer acts without a press) | 1 | 3 | REQ-14, scan R1/R2 (tokenizer, `_G` lookups, XML scripts) |
| RK15 | The "find a target" press also pulls, past the elite/+3 guard | 2 | 2 | REQ-21 | The mage pulls with the longest-range spell (Fireball), then slows with Frostbolt | macro: mage opens |
| REQ-20 |
| RK16 | The AFK alarm stays silent | 2 | 2 | REQ-16 |
| RK17 | After a /reload in combat the keys do nothing | 1 | 3 | REQ-18 |
| RK18 | Quest hints offer the other faction's quests | 2 | 1 | REQ-08 (independent list of known Horde quests) |

## 5. Requirements and traceability

The test `traceability: every requirement has a test` reads this table and
fails when a test listed here does not exist in the suite. A requirement can
point to several tests; names are matched on their beginning.

| REQ | Requirement | Tests |
|---|---|---|
| REQ-01 | The addon loads and runs a session for every class without a Lua error | smoke:; fuzz |
| REQ-02 | Nothing secure changes during combat | smoke:; fuzz |
| REQ-03 | Every macro fits 255 characters | macro: druid macros fit |
| REQ-04 | Secret values are only displayed, never computed | smoke:; fuzz |
| REQ-05 | Every melee fight shifts into its form, and nuke mode ends in a form | macro: druid macros fit; macro: nuke mode |
| REQ-06 | Faerie Fire and the out-of-combat pull stay in the macro at every level | macro: druid macros fit |
| REQ-07 | Quest data comes only from pfQuest (MIT), with the notice | questdata:; security: |
| REQ-08 | Quest hints respect faction, race and class | questhelp: |
| REQ-09 | Rank upgrades happen only out of combat, once per spell | ranks: |
| REQ-10 | No globals beyond the documented ones | fuzz |
| REQ-11 | Quest refresh stays under its time budget | performance: |
| REQ-12 | Any slash input is handled without an error | fuzz |
| REQ-13 | CI actions are pinned to commits and Python packages to hashes | security: |
| REQ-14 | No automation: no API that acts without a key press | security: |
| REQ-15 | toc, Core.lua and OneKey.lua carry the same version | toc: |
| REQ-16 | The AFK alarm sounds when the player is attacked after being idle | alarm: |
| REQ-17 | /okd bind and /okd sos take only real keys, and never each other's key | keys: |
| REQ-18 | After a /reload in combat the keys work once the fight ends | reload in combat: |
| REQ-19 | Every class keeps its main spell in the fight macro | macro: every class |
| REQ-21 | The mage pulls with the longest-range spell (Fireball), then slows with Frostbolt | macro: mage opens |
| REQ-20 | With no enemy targeted, the key only targets; the next update checks the target before attacking | macro: every class; smoke: |

## 6. Threat model (STRIDE)

| Threat | Where | Control |
|---|---|---|
| Spoofing | Chat or addon messages pretending to be the addon | The addon reads no addon messages and no chat; scan R3 |
| Tampering | A changed release zip | Reproducible build and SHA-256 file; the release is a draft until it is checked |
| Tampering | Game strings (NPC, quest or zone names) inside macros or patterns | Names come from the spellbook, never from targets; patterns use plain find; fuzz with `%`, `|` and non-ASCII names |
| Repudiation | Not relevant: no server and no accounts | — |
| Information disclosure | The SavedVariables log | Kept local; no network API exists in the client; documented in SECURITY.md |
| Denial of service | A heavy refresh or an error loop in combat | Performance test; fuzz; every handler is protected |
| Elevation of privilege | Protected functions called from insecure code (taint), or automation | Secure button only; taint guard in the stub; scan R1/R2; no-automation policy |

## 7. Roles

* Test runner agent (`.claude/agents/test-runner.md`): runs L1–L3 and reports.
* Security reviewer agent: reviews against section 6 and SECURITY.md, independently of the author.
* Release manager agent: checks the exit criteria before a tag.
* Log analyst agent: reads L4 session logs.

## 8. Completion report

Each release adds a short entry to CHANGELOG.md with the test count, the fuzz
runs, the mutation score, coverage, and any known gaps.
