---
name: release
description: Prepare a OneKey release - bump the version in the toc, Core.lua and OneKey.lua, write the CHANGELOG section, run every check, build the zip with its SHA-256 - and hand the owner the tag commands. Use when the owner asks for a new version.
---

# Release

Plan and rules: `docs/RELEASE.md`. Since 23.11.2026 the owner's standing
word is: publish a new version as a beta when every check passes, and as a
release when his play logs carry it (`release/FIELD.md`). Outside that rule,
never publish without the owner saying so in this conversation.

1. Pick the version (PATCH fix, MINOR feature, MAJOR relearn/SavedVariables)
   from the changes since the last tag: `git log --oneline $(git describe --tags --abbrev=0)..HEAD`.
2. Set it in all three places:
   - `OneKeyDruid/OneKeyDruid.toc` → `## Version: X.Y.Z`
   - `OneKeyDruid/Core.lua` → `local VERSION = "X.Y.Z"`
   - `OneKeyDruid/OneKey.lua` → `local VERSION = "X.Y.Z"`
3. Add `## X.Y.Z` at the top of `CHANGELOG.md`: what changes for the player,
   in plain words, one line each.
4. Run the `run-tests` skill, then the `security-audit` skill (or hand the
   diff to the `security-reviewer` agent).
5. `python3 -I tools/build.py` → `dist/OneKeyForever-X.Y.Z.zip` and `.sha256`.
   Unzip it and check it holds exactly one folder, `OneKeyDruid/`.
6. Commit: `git commit -am "OneKey Forever X.Y.Z"`.
7. `git push origin main`. The release workflow makes the tag, the
   pre-release and the CurseForge beta; check its run and say what came
   out. Never write `release/STABLE` in the same commit.
8. Optional, with the owner's go-ahead: install the zip on the owner's own
   computer (copy the `OneKeyDruid/` files into
   `.../_forever_/Interface/AddOns/OneKeyDruid/` and check the file sizes);
   a new file in the toc needs a full game restart, not `/reload`.
9. From beta to release: only by the rule in `docs/RELEASE.md` ("From beta
   to release"), from the logs (`analyze-session-log` skill, `--field`).
   Write the section in `release/FIELD.md`, then the version into
   `release/STABLE`, push, check the `promote` run.
