---
name: security-audit
description: Security and fair-play audit of the OneKey addon or a change to it - the static scan (rules R1-R7) plus a manual review for automation, secret values, combat taint, network use, supply chain and licences. Use for every PR and before a release.
---

# Security audit

The rules and their reasons are in `SECURITY.md` and
`docs/ARCHITECTURE.md`. In short: no automation (R1), no network (R2), no
dynamic code (R3), no maths on secret health/power (R4), no secrets or
personal data (R5), licence notices kept (R6), only addon files in the
package (R7).

1. `python3 -I security/scan.py` — must print `0 finding(s)`.
2. Find what changed: `git diff --stat <base>...HEAD` and read every changed
   `.lua`, `.toc`, `.xml`, workflow and test file.
3. For each new or changed WoW API call, look up whether it is protected,
   whether it acts on the world, and whether it returns secret values in
   WoW: Forever. Acting or protected → finding.
4. Look for a decision moved from the player to the addon: code that runs on
   a timer or an event and changes what happens next without a key press,
   or a macro that does more than its label says.
5. Secure state: `SetAttribute`, `SetOverrideBinding*`,
   `ClearOverrideBindings` only in functions that return early on
   `InCombatLockdown()` or run on `PLAYER_REGEN_DISABLED`/`ENABLED`.
6. Supply chain: workflows keep `permissions: contents: read` (release job:
   `contents: write` only), actions pinned to full SHAs,
   `tests/requirements.txt` pinned with hashes; no new download steps.
7. Guards not weakened: compare `security/scan.py`, `tests/wowstub.lua`,
   `tests/mutation_check.py` with the base; a removed rule or mutant needs
   a stated reason.
8. Data and licences: new data or code from elsewhere carries its licence in
   THIRD_PARTY_NOTICES.md; QuestData.lua must come from pfQuest only and QuestDataNew.lua from All The Things only
   (`tools/extract_pfquest.py`).
9. Report findings as `rule | file:line | risk | fix`, most severe first, or
   say plainly that there are none.
