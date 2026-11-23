#!/usr/bin/env python3
"""Summarise a OneKey session log (the player's SavedVariables file).

    python3 tools/analyze_log.py path/to/SavedVariables/OneKeyDruid.lua [--since EPOCH] [--last N]
    python3 tools/analyze_log.py FILE [FILE ...] --field 0.35.2   # is there enough play behind a version?

Log line format, "t|code|fields...", t = seconds since the session started:
  S   session start: epoch, level, xp, xpMax, rested, zone, ..., addon version (last, from 0.35.2)
  C+  fight start: target, level, classification, form
  C-  fight end: seconds, xp, hits taken, most attackers at once
  M   damage meter after a fight: done, taken, healed, max health
  X   xp gained: amount, kind (kill/quest/...), mob, mob level
  A   own cast: spell        P   key press: action, count
  B   time buckets: fight, rest, move, idle, ...   (cumulative seconds)
  T   target: name, level   Q quest hint shown   Z zone   L level up
  D+/D- death / alive      V+/V- vendor or trainer window
"""
import argparse, collections, re, statistics, sys


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def sessions(path):
    txt = open(path, encoding="utf-8").read()
    i = txt.find('["lines"]')
    if i < 0:
        return
    # only the log table: other tables of the file (probes, the HUD's place)
    # hold strings too
    end = re.search(r"\n\s*\},", txt[i:])
    block = txt[i:i + end.start()] if end else txt[i:]
    lines = [l.split("|") for l in re.findall(r'^\s*"([^"\n]*)",$', block, re.M)]
    lines = [l for l in lines if len(l) >= 2]
    starts = [k for k, l in enumerate(lines) if l[1] == "S"] + [len(lines)]
    for a, b in zip(starts, starts[1:]):
        yield lines[a:b]


def stamp(s):
    """(class, addon version) of a session line; the version is written from
    0.35.2 on, as the last field."""
    ver = s[-1] if VERSION_RE.match(s[-1]) else "?"
    cls = next((f for f in s[8:] if f.isalpha() and f.isupper()), "DRUID")
    return cls, ver


def dead_fights(e):
    """Fights in which the fight key was pressed five times or more and no
    spell of the player went off: the sign of a macro that does nothing."""
    dead, presses, casts, inside = 0, 0, 0, False
    for x in e:
        if x[1] == "C+":
            inside, presses, casts = True, 0, 0
        elif x[1] == "C-":
            if inside and presses >= 5 and casts == 0:
                dead += 1
            inside = False
        elif inside and x[1] == "P" and len(x) > 3 and x[2] == "fight":
            presses += int(num(x[3]))
        elif inside and x[1] == "A":
            casts += 1
    return dead


def summary(e):
    s = e[0]
    t = max(num(x[0]) for x in e) or 1
    xp = sum(num(x[2]) for x in e if x[1] == "X")
    kill = sum(num(x[2]) for x in e if x[1] == "X" and len(x) > 3 and x[3] == "kill")
    fights = [x for x in e if x[1] == "C-"]
    deaths = [x for x in e if x[1] == "D+"]
    buckets = [x for x in e if x[1] == "B"]
    cls, ver = stamp(s)
    out = {
        "class": cls, "version": ver, "dead_key_fights": dead_fights(e),
        "seconds": t,
        "start": int(num(s[2])), "level": s[3], "minutes": round(t / 60, 1),
        "xp_per_hour": round(xp / t * 3600), "kill_xp_per_hour": round(kill / t * 3600),
        "fights": len(fights), "deaths": len(deaths),
        "time_fight_rest_move_idle": buckets[-1][2:6] if buckets else None,
        "attackers": dict(collections.Counter(int(num(x[5])) for x in fights if len(x) > 5)),
        "avg_fight_s": round(statistics.mean(num(x[2]) for x in fights), 1) if fights else None,
        "level_ups": [x[2] for x in e if x[1] == "L"],
        "zones": [x[2] for x in e if x[1] == "Z"],
        "presses": dict(collections.Counter(x[2] for x in e if x[1] == "P").most_common(12)),
        "casts": dict(collections.Counter(x[2] for x in e if x[1] == "A").most_common(16)),
        "target_levels": dict(collections.Counter(x[3] for x in e if x[1] == "T" and len(x) > 3).most_common(6)),
        "quest_hints": collections.Counter("|".join(x[2:])[:70] for x in e if x[1] == "Q").most_common(5),
        "death_context": [],
    }
    for k, x in enumerate(e):
        if x[1] == "D+":
            ctx = [ "|".join(y)[:90] for y in e[max(0, k - 25):k + 1] if y[1] not in ("B",) ]
            out["death_context"].append(ctx)
    return out


# What a version must have behind it in real play before it is published as
# a release instead of a beta (docs/RELEASE.md, "From beta to release").
FIELD = {"minutes": 90, "fights": 60, "class_fights": 20, "dead_share": 0.02, "deaths_per_hour": 1.0}


def field(all_s, version):
    """Totals of the sessions stamped with this version, and what is missing."""
    mine, seen = [], set()
    for s in all_s:  # a file and its .bak hold the same sessions: once each
        key = (s["class"], s["start"], s["level"])
        if s["version"] == version and key not in seen:
            seen.add(key)
            mine.append(s)
    minutes = sum(s["seconds"] for s in mine) / 60
    fights = sum(s["fights"] for s in mine)
    deaths = sum(s["deaths"] for s in mine)
    dead = sum(s["dead_key_fights"] for s in mine)
    per_class = collections.Counter()
    for s in mine:
        per_class[s["class"]] += s["fights"]
    enough = [c for c, n in per_class.items() if n >= FIELD["class_fights"]]
    missing = []
    if minutes < FIELD["minutes"]:
        missing.append("%.0f of %d minutes" % (minutes, FIELD["minutes"]))
    if fights < FIELD["fights"]:
        missing.append("%d of %d fights" % (fights, FIELD["fights"]))
    if "DRUID" not in enough:
        missing.append("druid: %d of %d fights" % (per_class["DRUID"], FIELD["class_fights"]))
    if not [c for c in enough if c != "DRUID"]:
        missing.append("another class: %d fights each needed" % FIELD["class_fights"])
    if fights and dead / fights > FIELD["dead_share"]:
        missing.append("%d fights with the key pressed and no cast" % dead)
    if minutes and deaths / (minutes / 60) > FIELD["deaths_per_hour"]:
        missing.append("%d deaths in %.0f minutes" % (deaths, minutes))
    return {"version": version, "sessions": len(mine), "minutes": round(minutes),
            "fights": fights, "deaths": deaths, "dead_key_fights": dead,
            "fights_by_class": dict(per_class), "missing": missing}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="+")
    ap.add_argument("--since", type=int, default=0, help="only sessions that started at or after this epoch")
    ap.add_argument("--last", type=int, default=3, help="the last N sessions (default 3)")
    ap.add_argument("--field", metavar="VERSION",
                    help="totals of the sessions that ran this addon version, over all the files given")
    a = ap.parse_args()
    if a.field:
        r = field([summary(e) for p in a.path for e in sessions(p)], a.field)
        for k, v in r.items():
            print("  %-18s %s" % (k, v))
        print("ENOUGH FOR A RELEASE" if not r["missing"] else "STAYS A BETA")
        sys.exit(0 if not r["missing"] else 1)
    all_s = [summary(e) for e in sessions(a.path[0])]
    if not all_s:
        sys.exit("no session log in this file")
    chosen = [s for s in all_s if s["start"] >= a.since][-a.last:]
    for s in chosen:
        print("== session from %d, %s %s, level %s, %.1f min" % (s["start"], s["class"].lower(), s["version"], s["level"], s["minutes"]))
        for k, v in s.items():
            if k in ("start", "level", "minutes", "death_context", "class", "version", "seconds"):
                continue
            print("  %-26s %s" % (k, v))
        for ctx in s["death_context"]:
            print("  death, the 25 lines before it:")
            for l in ctx:
                print("    " + l)


if __name__ == "__main__":
    main()
