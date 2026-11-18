# Release plan

## Before the first public release (blockers)

1. **Quest data licence.** `QuestData.lua` was extracted from Polestar's
   pack, which mixes pfQuest (MIT) with QuestieDB facts (maintainers ask for
   all rights reserved), web quest XP and Blizzard client tables. Choose one:
   - rebuild it straight from pfQuest's repository (MIT only) — change
     `tools/extract_questdb.py` to read pfQuest's `db/` tables; or
   - ship without quest hints (drop QuestData.lua and QuestHelp.lua from the
     toc; the addon already runs without them).
2. **Name.** "OneKey" may clash with other addons on CurseForge/Wago; search
   before announcing. The folder stays `OneKeyDruid` either way.
3. **Repository settings** (once, by the owner):
   - Settings → Environments → `release`: required reviewer = owner
   - Settings → Code security: private vulnerability reporting on,
     Dependabot alerts on, secret scanning and push protection on
   - Branch protection on `main`: PR required, `ci / test` must pass, no
     force push
4. **In-game check of the zip**: unpack the CI-built zip into a clean
   AddOns folder, log in with a druid and one other class, `/okd status`.

## Versioning

`MAJOR.MINOR.PATCH` in the toc (`## Version`), mirrored in `VERSION` in
Core.lua and OneKey.lua (a test checks they agree).

- PATCH: fixes (a lost macro line, a wrong hint)
- MINOR: new behaviour (a new key, a new class list, quest hints)
- MAJOR: anything that changes what a key does in a way players must relearn
  — or a SavedVariables change (avoid)

`## Interface` follows the WoW: Forever client (16001 now); bump it when the
client's interface number changes, after the in-game check.

## Steps for each release

1. `release-manager` agent (or by hand): bump the version in the three
   places, add a `## x.y.z` section at the top of CHANGELOG.md.
2. Open a PR. CI runs the tests, the tests for the tests, the scan and the
   build. The `security-reviewer` agent reviews the diff.
3. Merge. Tag on main: `git tag -s vX.Y.Z -m "OneKey X.Y.Z"` and push the tag.
4. The `release` workflow checks the tag against the toc, runs everything
   again, builds `OneKey-X.Y.Z.zip` and its `.sha256`, and creates a **draft**
   release with the CHANGELOG section as notes.
5. The owner downloads the draft's zip, does the in-game check, publishes.
6. Optional later: CurseForge/Wago through the BigWigsMods packager
   (`.pkgmeta` is ready; needs `CF_API_KEY` / `WAGO_API_TOKEN` as
   environment secrets of `release`).

## First repository layout

```
OneKeyDruid/          the addon (what goes into the zip)
tests/                run_tests.py, wowstub.lua, mutation_check.py, requirements.txt
security/scan.py      policy scan
tools/                build.py, extract_questdb.py, analyze_log.py
docs/                 ARCHITECTURE.md, RELEASE.md
.claude/agents/       test-runner, security-reviewer, release-manager, log-analyst
.claude/skills/       run-tests, security-audit, release, analyze-session-log
.github/workflows/    ci.yml, release.yml
README.md CHANGELOG.md SECURITY.md THIRD_PARTY_NOTICES.md LICENSE CLAUDE.md
```

## Publishing the repository

Create it empty on GitHub (public or private first), then from this folder:

```
git remote add origin git@github.com:<owner>/onekey.git
git push -u origin main
```

Start private until blocker 1 is settled; switch to public after.
