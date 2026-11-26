# Security and fair-play policy

OneKey is an addon for a live online game. Its security promises are about
the player's account and computer, and about playing by Blizzard's rules.

## What the addon promises

1. **No automation.** Every spell, item, target and movement comes from a key
   the player presses. The addon only fills secure macro buttons out of
   combat; it never calls protected functions from Lua, and nothing that
   runs on a timer or an event casts, uses, targets or moves. Timers and
   the frame update only redraw text, re-read the state for the next
   out-of-combat macro, sound the away alarm and turn herb tracking on.
   (Rule R1 in `security/scan.py`.)
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
values (the damage meter's totals, `IsSpellUsable`, the maximum health),
and it looks at which spells reach the target and how long they take to
cast (the mage's opener).
The estimate only chooses which macro sits on the key before the next
press. The player still presses for every action, and nothing is chosen
during combat, when the macro is locked.

In combat the addon shows text, and only text. A hint may name a helper
key ("OVERPOWER: Ctrl+F") when the client itself says, in a plain value,
that the spell can be used (`C_Spell.IsSpellUsable`) or that its cooldown
is over; when the answer is a secret value, or there is none, no key is
named. Cooldowns are read once as a fight begins, while they are still
plain, and after that counted from the player's own casts. Two hints count the player's own finished casts, which the client
reports openly: the Winter's Chill stacks behind the Cone of Cold hint
(`/okd cone off`) and the minute since Ice Barrier. They do not read the
target's or the player's auras, which are secret in combat, and they
change no macro. The owner decides whether such a count stays; it is
listed here so that the policy says what the addon does.

One hint reads the target (0.38.0): while a hostile target is casting, the
HUD names the key that holds the class's interrupt or stun
(`/okd interrupt off`). It uses the client's own cast events for the unit
"target" and, where the client gives plain values, the cast's end and its
"not interruptible" mark; a secret answer is never compared. The key is
named only when its cooldown is known to be over. Nothing is cast or
pressed: the player decides. The owner asked for this hint on 26.11.2026.

The quest list (`/okd solo`) is made of plain frames. A click on a row
sets the game's own map pin and arrow and prints the task; it never
casts, targets, interacts or moves. No addon button is clicked from Lua
(the scanner flags `Click` as a call, a field or a string; it cannot see
a name built at run time, which is why `_G` under another name is flagged
too).

## Reporting

Please report a security problem privately: use GitHub's "Report a
vulnerability" (Security tab) rather than a public issue. Include the version
(`/okd status` shows it) and what you saw.

## Supply chain

- The release zip is built by `tools/build.py` in CI, scanned, and
  published with its SHA-256 checksum.
- A new version number on `main` is published by CI as a pre-release (a
  beta on CurseForge) after every check has run again in the release job;
  it becomes a release only through `release/STABLE`, which re-checks the
  tested zip against its checksum and builds nothing. Whoever can push to
  `main` can therefore publish: keep that to the owner (branch protection,
  and a required reviewer on the `release` environment if a person should
  approve each publication).
- CI actions are pinned to full commit SHAs; the workflows have read-only
  permissions except the release and promote jobs, which may only write
  releases and tags.
- No runtime dependencies: the package is plain Lua, TOC and XML.
