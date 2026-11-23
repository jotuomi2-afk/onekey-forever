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
* Only MIT-licensed third-party data (pfQuest, All The Things) is shipped.
* A failing gate stops the release; nothing is waived silently.

## 2. Test levels and types

| Level | What | Tool | When |
|---|---|---|---|
| L1 static | Security rules R1–R7: forbidden APIs, network and file access, globals, licence markers, workflow pinning | `security/scan.py` | every commit, CI |
| L2 unit | Macro builder at every level, form and setting; 255-character limit; toc and version agreement; quest-data integrity | `tests/run_tests.py` | every commit, CI |
| L3 integration | The whole addon loaded in a simulated client (`tests/wowstub.lua`): secret values raise on comparison or arithmetic; secure changes in combat are recorded and blocked, as in the client; events reach only frames that registered them; timers run; the damage meter returns secret values in combat | `tests/run_tests.py` | every commit, CI |
| L3 property / fuzz | Random reproducible sessions for nine classes: random targets, combat, forms, zones, deaths, events, and slash input, including junk; client variations (no scale curve, no damage meter) | `tests/fuzz_test.py` | 40 runs per class in CI, 500 before a release |
| L3 performance | `QuestHelp.Refresh` + `Hint` under 8 ms per call | `tests/run_tests.py` | every commit |
| Test-quality check | Mutation check: the unchanged suite must pass first, then 29 planted faults must each fail the named test with the expected message | `tests/mutation_check.py` | CI |
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
| RK15 | The "find a target" press also pulls, past the elite/+3 guard | 2 | 2 | REQ-20 |
| RK16 | The AFK alarm stays silent | 2 | 2 | REQ-16 |
| RK17 | After a /reload in combat the keys do nothing | 1 | 3 | REQ-18 |
| RK18 | Quest hints offer the other faction's quests | 2 | 1 | REQ-08 (independent list of known Horde quests) |
| RK19 | A spell on cooldown or out of range early in a macro stops it, so the key does nothing | 3 | 2 | REQ-22 |
| RK20 | A buff, shield, imbue or opener that cannot be cast holds the fight key out of combat | 2 | 3 | REQ-44 (hammering, key-up and other keys tested), two mutants |
| RK21 | The quest guide sends a lone player to a group quest, a dungeon or mobs far over their level | 2 | 2 | REQ-51, REQ-52 |
| RK22 | Data from a second source (All The Things) breaks the licence rule or repeats pfQuest's quests | 1 | 3 | REQ-07, REQ-53, scan R6, two mutants |
| RK23 | The quest list taints the fight keys or acts for the player (a click that casts, targets or moves) | 1 | 3 | REQ-54, scan R1 (Click, aliased calls), mutants |
| RK24 | A hint reads a secret value in combat, or names a key from a value it could not read | 2 | 2 | REQ-45, REQ-55, mutant |
| RK25 | A version is published with no person pressing a button: a broken or unchecked build reaches players, or a beta is called a release with no play behind it | 2 | 3 | REQ-56, REQ-57, mutant (version stamp); every check runs in the release job before the release is made; a new version is only ever a pre-release |

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
| REQ-07 | Quest data comes only from pfQuest (MIT) and, for the quests Forever added, All The Things (MIT), each file with its notice and generator | questdata:; questdatanew:; security: |
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
| REQ-21 | The mage's opener: as many Fireballs (two at most) as fit before the slowing Frostbolt lands with the mob still away, worked out before each pull from which spells reach the target and from the cast times; none when attacked first; the chosen macro stays for the fight; /okd opener fixes the count; cooldown spells sit on the helper keys | macro: mage F is Frostbolt; mage: the opener by distance |
| REQ-22 | No macro (F, G, the druid keys) tries anything that can fail (cooldown, range, target type, position, a potion) before another spell: the client stops a macro at the first failed cast | macro: nothing that can fail |
| REQ-24 | The rogue chains its stuns: Cheap Shot, Kidney Shot, Gouge, inside one sequence | macro: rogue chains |
| REQ-26 | Rooted, the druid breaks free with Shift+G in any form (cat and bear swap: Forever has no powershift); from caster form the HUD offers Ctrl+G back | druid: rooted |
| REQ-27 | From the log of 20.11.: Faerie Fire once per round at most (not every sequence), Ctrl+F follows the pull guard, half health after a corpse run makes F heal or rest | druid: log of 20.11. |
| REQ-28 | No heal at full health before a pull: a heal needs at least 15 % health missing; buffs come first | logic: no heal at full health |
| REQ-29 | The druid's G: Rejuvenation with the potion first, then Nature's Grasp (only when ready at the fight's start), then the bear; never a loop back onto a cooldown | druid: G is |
| REQ-30 | Prowl pressed outside cat form shifts to cat first: Prowl on the bars becomes the OKD Prowl macro, once per slot, out of combat | druid: Prowl on the bar |
| REQ-31 | Out of combat, in water F holds Aquatic Form, and on land again the fighting form | druid: in water |
| REQ-32 | Hunter: in melee the HUD points to Ctrl+F (Wing Clip, Mongoose Bite, Raptor Strike); the spoken error is off (restorable) | hunter: in melee |
| REQ-33 | Warlock: F puts Corruption, Bane of Agony and Siphon Life on once per target, then wands (Shadow Bolt only with no wand); no F line cuts Drain Life short | warlock: DoTs once |
| REQ-34 | Every class writes the session log (S, T, C+, P, A, C-, X, D, L, Z) that tools/analyze_log.py reads; other players are written as "player"; /okd log on/off/clear | log: every class |
| REQ-35 | The druid's G fits the mana the pull leaves: it leaves cat form to heal (and adds Nature's Grasp) only when the pull, the heal (and Grasp) and the bear all fit; otherwise a cat goes straight into the bear | druid: G fits the mana |
| REQ-36 | Short of mana the druid's G drinks a mana potion once a fight, then the bear; a potion still cooling as a fight starts is left out of G | druid: a potion still cooling |
| REQ-37 | Priest: F puts Shadow Word: Pain on once per target, then wands; Mind Flay and Smite only with no wand | priest: Shadow Word: Pain once |
| REQ-38 | Druid: before a pull, 4+ other living enemies in Wrath's range hold F (DO NOT PULL), 2-3 warn; /okd brave on lifts the hold. In bear form G does not leave the form (potion only) | druid: a camp of enemies |
| REQ-39 | Druid cat F: Rip is the first finisher, Ferocious Bite the second once learned, with three Claws before the Bite; F stays within 255 characters | druid: cat finishers are Rip first |
| REQ-40 | Warrior: F holds no spell that is usable only now and then (Overpower, Execute); they have Ctrl+F and Shift+F | warrior: F is Rend once |
| REQ-41 | Druid F out of combat: in cat or bear form with a target it does not leave the form to renew a Mark with time left; a party member in range without Mark of the Wild gets it ([@partyN]) | logic: a cat with a target keeps its form |
| REQ-25 | The mage keeps the Frostbolt slow up: Fireball only opens. Shift+F is Frostbolt, Ice Lance for a frozen mob. G is the way out: Frost Nova, Blink, Mana Shield once through with the potion, reset by time alone (25 s, not by the end of a fight); Frost Nova and Blink are on no other key; the G hint waits for the sequence | macro: mage F is Frostbolt; mage: the opener by distance; try once: a fight |
| REQ-42 | Mage: out of combat with an enemy picked F casts Ice Barrier first when it is not up and not on cooldown; a press that does not bring the buff does not hold the key; Ice Armor comes before Mage Armor; Ctrl+G is Ice Barrier | mage: Ice Barrier before the pull |
| REQ-43 | Mage HUD: five Frostbolt or Ice Lance casts on a target ask for Cone of Cold (Winter's Chill, level 35; /okd cone off); a minute after Ice Barrier it asks for it again | hud: mage with five Frostbolts |
| REQ-44 | What F offers before a fight (buff, shield, imbue, opener) is tried once: two seconds after the first press of the fight key made while the offer was on it, it is over, however the key is hammered; a key-up, another key or a press while mounted is no try; a buff given up on stays away for five minutes; what the client says cannot be cast is not offered | mage: Ice Barrier before the pull; priest: before the pull; shaman: the weapon imbue; try once: hammering; try once: a press while mounted |
| REQ-45 | The HUD names a helper key when its spell can be used: reactive spells from the client's usable check (Overpower, Execute, Riposte), cooldown spells when ready (Mind Blast) | warrior: F is Rend once; rogue: Riposte; priest: before the pull |
| REQ-46 | Hunter: the shots with a cooldown are one sequence as the last line of F (with Summon Hawk: hawk, Aimed Shot, hawk, Arcane Shot); F keeps the pet, the once-per-target line and Auto Shot within 255 characters | hunter: the cooldown shots |
| REQ-47 | Paladin: aura, blessing and seal are kept up out of combat; F is Judgement and Holy Strike in one sequence, the seal again after two rounds | paladin: aura, blessing and seal |
| REQ-48 | Shaman: out of combat F puts the weapon imbue on (Windfury over Rockbiter); F is Lightning Bolt to pull, then Flame Shock, Stormstrike, Earth Shock in one sequence | shaman: the weapon imbue |
| REQ-49 | Priest: from level 10 F shields before the pull (not under Weakened Soul) and opens with Mind Blast; the wand stays the last line of F with Shadowform too | priest: before the pull; priest: Shadow Word: Pain once |
| REQ-50 | Rogue: Slice and Dice is the first finisher, after two Sinister Strikes; when both miss the sequence waits on a finisher with no combo point, and the HUD then names Gouge (Alt+F), which gives one; the chain with Cheap Shot fits 255 characters | macro: rogue chains; rogue: with no combo point |
| REQ-23 | The HUD tells a mage in melee to press the emergency key (Frost Nova, then Blink), then Shift+F for Frostbolt and Ice Lance | hud: mage hit in melee |
| REQ-20 | With no enemy targeted, the key only targets; the next update checks the target before attacking | macro: every class; smoke: |
| REQ-51 | The solo rating: a quest the game tags for a group, with an elite objective or in a dungeon needs a group; a target, an item's every source or a hand-in with no place outdoors is "unsure" (how dungeon quests look in the data) and left apart; mobs or a quest 3 levels over the player is too hard; 6 under gives little XP; ordinary quests carry no flag | solo: the rating; questdata: |
| REQ-52 | The zone plan: hand-ins first, then one walk from the last hand-in through what one player can take and do (nearest next, by worth), group, unsure and too-hard quests apart with the reason; a hand-in on another map is listed under Elsewhere and never breaks the list; the hint never names a group quest while a solo one is there; no quest of the other side is offered | solo: the plan; solo: a quest the game tags; solo: a finished quest |
| REQ-53 | Quests Forever added (All The Things: ids from 20000, with a level, one side only in the starting zones) are offered where they start, named by the server's title or plainly; a quest of the log no file knows uses the game's own point and count; no record repeats a pfQuest quest | solo: quests Forever added; questdatanew: |
| REQ-54 | The quest list is plain frames: a left click sets the game's waypoint and prints the task, a right click leaves the quest out; nothing secure is touched, in a fight too | solo: the list window; security: |
| REQ-55 | A hint from a secret answer names no key; cooldowns are read as the fight begins and then counted from the player's own casts, and with neither nothing is named, for the mage's hints too | hints fail closed:; hints: cooldowns read |
| REQ-56 | Publishing: a new version number on main becomes a pre-release only after the tests, the mutants, 500 fuzz runs per class, the coverage gate, the scan and the build, never below a published number and never without a changelog section; a pre-release becomes a release only through release/STABLE, with the tested zip checked against its SHA-256 and a passing section in release/FIELD.md; actions are pinned | release: a new version |
| REQ-57 | The play behind a version: every class stamps the addon version on the session line; the analyser counts only sessions with that stamp and holds a release back for too little play, one class alone, fights with the key pressed and no cast, or many deaths | release: the log analyser; log: every class |

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
