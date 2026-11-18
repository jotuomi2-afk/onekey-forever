#!/usr/bin/env python3
"""Summarise a OneKey session log (the player's SavedVariables file).

    python3 tools/analyze_log.py path/to/SavedVariables/OneKeyDruid.lua [--since EPOCH] [--last N]

Log line format, "t|code|fields...", t = seconds since the session started:
  S   session start: epoch, level, xp, xpMax, rested, zone, ...
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


def sessions(path):
    txt = open(path, encoding="utf-8").read()
    i = txt.find('["lines"]')
    if i < 0:
        sys.exit("no session log in this file")
    lines = re.findall(r'^\s*"([^"\n]*)",$', txt[i:], re.M)
    starts = [k for k, l in enumerate(lines) if "|S|" in l] + [len(lines)]
    for a, b in zip(starts, starts[1:]):
        yield [l.split("|") for l in lines[a:b]]


def summary(e):
    s = e[0]
    t = max(num(x[0]) for x in e) or 1
    xp = sum(num(x[2]) for x in e if x[1] == "X")
    kill = sum(num(x[2]) for x in e if x[1] == "X" and len(x) > 3 and x[3] == "kill")
    fights = [x for x in e if x[1] == "C-"]
    deaths = [x for x in e if x[1] == "D+"]
    buckets = [x for x in e if x[1] == "B"]
    out = {
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--since", type=int, default=0, help="only sessions that started at or after this epoch")
    ap.add_argument("--last", type=int, default=3, help="the last N sessions (default 3)")
    a = ap.parse_args()
    all_s = [summary(e) for e in sessions(a.path)]
    chosen = [s for s in all_s if s["start"] >= a.since][-a.last:]
    for s in chosen:
        print("== session from %d, level %s, %.1f min" % (s["start"], s["level"], s["minutes"]))
        for k, v in s.items():
            if k in ("start", "level", "minutes", "death_context"):
                continue
            print("  %-26s %s" % (k, v))
        for ctx in s["death_context"]:
            print("  death, the 25 lines before it:")
            for l in ctx:
                print("    " + l)


if __name__ == "__main__":
    main()
