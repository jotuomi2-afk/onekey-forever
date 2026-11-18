# Security and fair-play policy

OneKey is an addon for a live online game. Its security promises are about
the player's account and computer, and about playing by Blizzard's rules.

## What the addon promises

1. **No automation.** Every spell, item, target and movement comes from a key
   the player presses. The addon only fills secure macro buttons out of
   combat; it never calls protected functions from Lua and never runs
   anything on a timer. (Rule R1 in `security/scan.py`.)
2. **Nothing leaves the computer.** No chat, whisper, addon, mail or channel
   messages. The session log stays in the player's SavedVariables. (R2)
3. **No dynamic code.** No `loadstring`, `RunScript` or environment tricks;
   what is in the files is all that runs. (R3)
4. **Respects the game's secrets.** Health and power are secret in WoW:
   Forever. The addon only passes them to the game's own display functions
   and curves, never compares or computes on them. (R4, and the fake
   client in `tests/wowstub.lua` raises an error if it ever does.)
5. **No secure state changes in combat.** Buttons and key bindings change
   only out of combat. (The fake client records any change during lockdown
   as a "taint" failure.)
6. **No secrets or personal data in the repository.** (R5)

## What we will not add

Requests for these are declined, whatever the wording: fighting or healing on
its own, a "sentry" that fights back while the player is away, reading health
through a side channel to decide actions, anything that sends keys from
outside the game. They break Blizzard's terms of service and put players'
accounts at risk.

## Reporting

Please report a security problem privately: use GitHub's "Report a
vulnerability" (Security tab) rather than a public issue. Include the version
(`/okd status` shows it) and what you saw.

## Supply chain

- The release zip is built by `tools/build.py` in CI from a tagged commit,
  scanned, and published with its SHA-256 checksum.
- CI actions are pinned to full commit SHAs; the workflows have read-only
  permissions except the release job, which may only write releases.
- No runtime dependencies: the package is plain Lua, TOC and XML.
