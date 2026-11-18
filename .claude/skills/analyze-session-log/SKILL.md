---
name: analyze-session-log
description: Analyse a player's OneKey session log (SavedVariables/OneKeyDruid.lua) - XP per hour, time use, fights, deaths and their causes, key presses and casts, quest hints shown - and propose addon changes. Use when the player says "analysoi"/"analyze" or asks how the addon is doing.
---

# Analyse the session log

The log lives in
`World of Warcraft/_forever_/WTF/Account/<ACCOUNT>/<realm>/<character>/SavedVariables/OneKeyDruid.lua`.
The game writes it only on `/reload` or logout: check the file's time first,
and say so if it is older than the play the player means.

1. Summarise the last sessions:
   `python3 -I tools/analyze_log.py <path> --last 3`
   (`--since EPOCH` to start after a given install). The line format is in
   the script's docstring.
2. Name the addon version each session ran: a session that started before
   an install ran the old version. Compare with the install time.
3. Read, in this order:
   - deaths: the 25 lines before each (attackers, target level vs. own
     level, which keys were pressed, whether G was used, potions)
   - XP/h and kill XP/h; quest XP share; target levels vs. own level (mobs
     3+ below give much less)
   - time: fight / rest / move / idle; idle or travel above ~40 % is the
     biggest loss
   - casts per fight: does the rotation do what the macro intends (Prowl
     then Shred/Claw, Faerie Fire once, finisher); a spell missing from
     casts that should be there often means a macro line was cut at 255
   - quest hints: the same hint repeated many times means a hint the player
     does not follow
4. Report what the log shows separately from what you infer, with numbers.
5. For each proposed change, name the test or rule that will guard it
   (a macro test, a stub check, a scan rule), so findings become tests.
6. The log is the player's data: do not upload or copy it elsewhere.
