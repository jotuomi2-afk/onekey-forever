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
its own, a "sentry" that fights back while the player is away, getting
around the game's secret health and power values (screen or pixel reading,
inverting the display curves, timing tricks), anything that sends keys from
outside the game. They break Blizzard's terms of service and put players'
accounts at risk.

What the addon does use, and why it stays within the rules: out of combat
it estimates health and mana from numbers the client hands out as plain
values (the damage meter's totals, `IsSpellUsable`, the maximum health).
The estimate only chooses which macro sits on the key before the next
press. The player still presses for every action, and nothing is chosen
during combat, when the macro is locked.

In combat the addon shows text, and only text. A hint may name a helper
key ("OVERPOWER: Ctrl+F") when the client itself says, in a plain value,
that the spell can be used (`C_Spell.IsSpellUsable`) or that its cooldown
is over; when the answer is a secret value, or there is none, no key is
named. Two hints count the player's own finished casts, which the client
reports openly: the Winter's Chill stacks behind the Cone of Cold hint
(`/okd cone off`) and the minute since Ice Barrier. They do not read the
target's or the player's auras, which are secret in combat, and they
change no macro. The owner decides whether such a count stays; it is
listed here so that the policy says what the addon does.

The quest list (`/okd solo`) is made of plain frames. A click on a row
sets the game's own map pin and arrow and prints the task; it never
casts, targets, interacts or moves. No addon button is clicked from Lua
(the scanner forbids `:Click`).

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
