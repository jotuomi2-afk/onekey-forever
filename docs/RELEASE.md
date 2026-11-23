# Release plan

## Before the first public release (blockers)

1. ~~Quest data licence~~ — done in 0.25.0: QuestData.lua is now built
   from pfQuest's own repository (MIT only) by `tools/extract_pfquest.py`
   (since 0.35.0 also `QuestDataNew.lua` from All The Things, MIT, by
   `tools/extract_att.py`);
   `security/scan.py` (R6) fails if another source appears in it.
2. ~~Name~~ — decided: **OneKey Forever** (repository `onekey-forever`,
   zip `OneKeyForever-X.Y.Z.zip`). No WoW addon of that name was found; the
   folder stays `OneKeyDruid` for players' settings.
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

The owner decided on 23.11.2026 that releases are published without him
pressing a button: a beta as soon as a new version passes every check, a
release when the play logs show it works.

1. Bump the version in the three places, add a `## x.y.z` section at the
   top of CHANGELOG.md, run every check (`release` skill). The
   `security-reviewer` agent reviews the diff.
2. Push to main. The `release` workflow sees a version number with no tag,
   runs everything again (tests, the tests for the tests, 500 fuzz runs per
   class, the coverage gate, the scan, the build), creates the tag
   `vX.Y.Z` and a **pre-release** with `OneKeyForever-X.Y.Z.zip` and its
   `.sha256`, and uploads the zip to CurseForge as a **beta**.
   - It refuses a number below one that is published, and a version with
     no CHANGELOG section.
   - A commit that does not change the toc publishes nothing.
3. The zip is installed on the owner's computer; he plays.
4. From beta to release: see below.

A person can still publish by hand: a tag pushed by a person gets a draft
release; a release published from the Releases page gets the files
attached and goes to CurseForge by its own pre-release flag.

## From beta to release

A pre-release becomes a release when the owner's play logs show that this
exact version works. The addon stamps its version on every session line
(from 0.35.2), so the logs say which version was played.

`python3 -I tools/analyze_log.py <every character's OneKeyDruid.lua> --field X.Y.Z`
answers with the totals and what is missing. A version has enough behind
it when its stamped sessions hold:

| What | Needed | Why |
|---|---|---|
| Play time | 90 minutes | loading, zoning, vendors, a death or two all happen |
| Fights | 60 | the macros are chosen and pressed often enough |
| Classes | the druid and one other class, 20 fights each | the two engines (Core.lua, OneKey.lua) both ran |
| Fights with F pressed 5+ times and no cast | at most 2 % | a macro that does nothing |
| Deaths | at most one an hour, each read | none may come from the addon (a key that did nothing, a hint that was wrong) |

And by judgement, written down in `release/FIELD.md`:

- every death and every repeated hint of those sessions was read;
- nothing the owner reported about this version is open;
- what the version changed was actually used in the sessions (a mage fix
  needs mage fights; a quest list change needs quest hints followed).

When all of it holds:

1. Add `## X.Y.Z: enough for a release` to `release/FIELD.md` with the
   totals (version, classes, minutes, fights, deaths: no character names,
   no times, no lines of the log; the log itself never leaves the
   computer).
2. Write `X.Y.Z` into `release/STABLE` and push. The `promote` workflow
   checks the section, checks the released zip against its SHA-256, turns
   the pre-release into the latest release and uploads the same zip to
   CurseForge as a release.

A version that does not get there stays a beta; the next version starts
its own count. `release/FIELD.md` also notes why a version stayed a beta.

## First repository layout

```
OneKeyDruid/          the addon (what goes into the zip)
tests/                run_tests.py, wowstub.lua, mutation_check.py, requirements.txt
security/scan.py      policy scan
tools/                build.py, extract_pfquest.py, analyze_log.py
docs/                 ARCHITECTURE.md, RELEASE.md
.claude/agents/       test-runner, security-reviewer, release-manager, log-analyst
.claude/skills/       run-tests, security-audit, release, analyze-session-log
.github/workflows/    ci.yml, release.yml, promote.yml, curseforge.yml
release/              STABLE (the stable version), FIELD.md (the play behind each version)
README.md CHANGELOG.md SECURITY.md THIRD_PARTY_NOTICES.md LICENSE CLAUDE.md
```

## Publishing the repository

Create it empty on GitHub (public or private first), then from this folder:

```
git remote add origin git@github.com:<owner>/onekey-forever.git
git push -u origin main
```

Start private until blocker 1 is settled; switch to public after.
