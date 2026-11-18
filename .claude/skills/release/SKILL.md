---
name: release
description: Prepare a OneKey release - bump the version in the toc, Core.lua and OneKey.lua, write the CHANGELOG section, run every check, build the zip with its SHA-256 - and hand the owner the tag commands. Use when the owner asks for a new version.
---

# Release

Plan and rules: `docs/RELEASE.md`. Never push, tag or publish without the
owner saying so in this conversation.

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
5. `python3 -I tools/build.py` → `dist/OneKey-X.Y.Z.zip` and `.sha256`.
   Unzip it and check it holds exactly one folder, `OneKeyDruid/`.
6. Commit: `git commit -am "OneKey X.Y.Z"`.
7. Give the owner the next commands, to run themselves:
   ```
   git push origin main
   git tag -s vX.Y.Z -m "OneKey X.Y.Z" && git push origin vX.Y.Z
   ```
   The release workflow builds the draft release; the owner tests the zip in
   game and publishes it.
8. Optional, with the owner's go-ahead: install the zip on the owner's own
   computer (copy the `OneKeyDruid/` files into
   `.../_forever_/Interface/AddOns/OneKeyDruid/` and check the file sizes);
   a new file in the toc needs a full game restart, not `/reload`.
