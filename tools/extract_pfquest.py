#!/usr/bin/env python3
"""Build OneKeyDruid/QuestData.lua from pfQuest's own database (MIT only).

    git clone https://github.com/shagu/pfQuest.git /tmp/pfQuest
    git -C /tmp/pfQuest checkout 104f35678ca39ab1fb78b655f815cc7016f5e0c8
    python3 -I tools/extract_pfquest.py /tmp/pfQuest OneKeyDruid/QuestData.lua

The script refuses another revision unless --any-revision is given: review
the upstream diff before moving the pin.

Reads pfQuest's Classic tables (db/quests.lua, units.lua, objects.lua,
items.lua and their enUS names) and writes the compact format QuestHelp.lua
reads. Nothing else goes in: no QuestieDB, no web or client data.

pfQuest stores positions per zone (AreaTable id); the game's map API uses
uiMap ids. ZONE_TO_UIMAP below maps the Classic outdoor zones and capitals
(both id lists are public facts of the Classic client). Places in other
zones (instances, Forever's new zones) keep their name but no position.
"""
import collections, os, subprocess, sys

try:
    from lupa.lua54 import LuaRuntime
except ImportError:
    from lupa import LuaRuntime

# AreaTable zone id -> uiMap id (Classic)
ZONE_TO_UIMAP = {
    1: 1426, 3: 1418, 4: 1419, 8: 1435, 10: 1431, 11: 1437, 12: 1429, 14: 1411, 15: 1445, 16: 1447,
    17: 1413, 28: 1422, 33: 1434, 36: 1416, 38: 1432, 40: 1436, 41: 1430, 44: 1433, 45: 1417, 46: 1428,
    47: 1425, 51: 1427, 85: 1420, 130: 1421, 139: 1423, 141: 1438, 148: 1439, 215: 1412, 267: 1424,
    331: 1440, 357: 1444, 361: 1448, 400: 1441, 405: 1443, 406: 1442, 440: 1446, 490: 1449, 493: 1450,
    618: 1452, 1377: 1451, 1497: 1458, 1519: 1453, 1537: 1455, 1637: 1454, 1638: 1456, 1657: 1457,
}
# pfQuest's positions are on the 1.12 maps. The WoW: Forever (Classic Era)
# client draws two of them on a different frame; measured from positions
# seen in the game (Lakeshire and Stormwind NPCs), percent -> percent:
#   x' = ax * x + bx,  y' = ay * y + by
MAP_FIX = {
    1433: (1.0, -5.1, 1.0, 0.0),          # Redridge Mountains
    1453: (0.7699, 19.82, 0.7670, 24.85),  # Stormwind City
}
ALLIANCE, HORDE = 1 | 4 | 8 | 64, 2 | 16 | 32 | 128
MAX_MIN_LEVEL, MAX_LEVEL = 60, 63
PINNED = "104f35678ca39ab1fb78b655f815cc7016f5e0c8"


def load(db):
    """Run pfQuest's data files in a sandbox: no os, io, require or file
    loading, each file in its own environment that holds only pfDB. The
    files are third-party code from a clone; they only build tables."""
    lua = LuaRuntime(unpack_returned_tuples=True, register_eval=False, register_builtins=False)
    lua.execute("""
        local load, setmetatable, rawset, error, tostring = load, setmetatable, rawset, error, tostring
        os, io, package, require, dofile, loadfile, debug, collectgarbage = nil, nil, nil, nil, nil, nil, nil, nil
        pfDB = setmetatable({}, {__index = function(t, k)
            local v = setmetatable({}, {__index = function(t2, k2) local x = {} rawset(t2, k2, x) return x end})
            rawset(t, k, v) return v end})
        function RUN_DATA(src, name)
            local env = { pfDB = pfDB }
            local f, e = load(src, "=" .. name, "t", env)
            if not f then error(name .. ": " .. tostring(e)) end
            f()
        end""")
    run = lua.eval("RUN_DATA")
    for f in ("quests.lua", "units.lua", "objects.lua", "items.lua",
              "enUS/quests.lua", "enUS/units.lua", "enUS/objects.lua", "enUS/items.lua"):
        with open(os.path.join(db, f), encoding="utf-8") as fh:
            run(fh.read(), f)
    return lua.eval("pfDB")


def ids(t):
    return [int(v) for v in t.values()] if t else []


def esc(s):
    s = str(s).replace("\\", "\\\\").replace('"', '\\"').replace("|", "/")
    # control characters as decimal escapes: the file must stay one line per record
    return "".join("\\%03d" % ord(c) if ord(c) < 32 else c for c in s)


def zones_of(data):
    """(outdoor points by zone, number of points in zones with no outdoor map)."""
    coords = data["coords"] if data else None
    pts = [tuple(c.values()) for c in coords.values()] if coords else []
    by_zone, inside = collections.defaultdict(list), 0
    for p in pts:
        if len(p) >= 3 and int(p[2]) in ZONE_TO_UIMAP:
            by_zone[int(p[2])].append(p)
        elif len(p) >= 3:
            inside += 1
    return by_zone, inside


def indoors(data):
    """Only found where there is no outdoor map: a dungeon or a raid."""
    by_zone, inside = zones_of(data)
    return inside > 0 and not by_zone


def top_level(data):
    """The highest level of a unit ("14-15" -> 15), 0 when unknown."""
    lvl = str(data["lvl"] or "") if data else ""
    nums = [int(x) for x in lvl.replace("-", " ").split() if x.isdigit()]
    return max(nums) if nums else 0


def place(name, data, unit=False):
    """name|uiMap|x,y,...|level|rank : the middle of its spawns in the zone
    where most of it is, then up to three spawns across that zone. Level
    ("14-15") and rank (1 elite, 2 rare elite, 3 boss, 4 rare) for units."""
    by_zone, _ = zones_of(data)
    tail = ""
    if unit and data:
        tail = "|%s|%s" % (esc(data["lvl"] or ""), esc(data["rnk"] or ""))
    if not by_zone:
        return esc(name) + ("||" + tail if tail.strip("|") else "")
    zone, zp = max(by_zone.items(), key=lambda kv: len(kv[1]))
    pick = [zp[0], zp[len(zp) // 2], zp[-1]] if len(zp) >= 3 else list(zp)
    if len(zp) >= 3:
        xs, ys = sorted(p[0] for p in zp), sorted(p[1] for p in zp)
        mid = (xs[len(xs) // 2], ys[len(ys) // 2])
        # the spawn nearest the middle: a real place, not a point in a lake
        pick.insert(0, min(zp, key=lambda p: (p[0] - mid[0]) ** 2 + (p[1] - mid[1]) ** 2))
    ax, bx, ay, by = MAP_FIX.get(ZONE_TO_UIMAP[zone], (1.0, 0.0, 1.0, 0.0))
    seen, out = set(), []
    for p in pick:
        k = (round(ax * p[0] + bx, 1), round(ay * p[1] + by, 1))
        if k not in seen:
            seen.add(k)
            out.append("%g,%g" % k)
    return "%s|%d|%s%s" % (esc(name), ZONE_TO_UIMAP[zone], ",".join(out), tail)


def main_map(refs, U, O):
    """The uiMap where most of these units and objects are."""
    count = collections.Counter()
    for kind, i in refs:
        by_zone, _ = zones_of((O if kind == "o" else U)[i])
        for z, pts in by_zone.items():
            count[ZONE_TO_UIMAP[z]] += len(pts)
    return count.most_common(1)[0][0] if count else 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src, out_path = args[0], args[1]
    db = os.path.join(src, "db")
    rev = subprocess.run(["git", "-C", src, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
    if rev != PINNED and "--any-revision" not in sys.argv:
        sys.exit("pfQuest is at %s, the pinned revision is %s (see the docstring)" % (rev, PINNED))
    pf = load(db)
    Q, U, O, I = pf["quests"]["data"], pf["units"]["data"], pf["objects"]["data"], pf["items"]["data"]
    QN, UN, ON, IN = pf["quests"]["enUS"], pf["units"]["enUS"], pf["objects"]["enUS"], pf["items"]["enUS"]

    # how many quests a quest opens, down its chain (at most 9)
    after = collections.defaultdict(set)
    for qid, q in Q.items():
        for pre in ids(q["pre"]):
            after[pre].add(int(qid))

    def opens(qid, seen=None, depth=0):
        seen = seen if seen is not None else set()
        for n in after.get(qid, ()):
            if n not in seen and depth < 6:
                seen.add(n)
                opens(n, seen, depth + 1)
        return min(9, len(seen))

    def item_sources(i):
        d = I[i]
        drops = sorted(((float(ch), int(u)) for u, ch in d["U"].items()), reverse=True)[:3] if d and d["U"] else []
        objs = sorted(((float(ch), int(o)) for o, ch in d["O"].items()), reverse=True)[:2] if d and d["O"] else []
        return [u for _, u in drops], [o for _, o in objs]

    quests, need_u, need_o, items = {}, set(), set(), {}
    for qid, q in Q.items():
        qid = int(qid)
        loc = QN[qid]
        title = loc["T"] if loc else None
        if not title or q["event"] or q["skill"]:
            continue
        lvl, mn = int(q["lvl"] or 0), int(q["min"] or 0)
        if lvl <= 0 or lvl > MAX_LEVEL or mn > MAX_MIN_LEVEL:
            continue
        race, cls = int(q["race"] or 0), int(q["class"] or 0)
        fac = ""
        if race and not race & HORDE:
            fac = "1"
        elif race and not race & ALLIANCE:
            fac = "2"
        # no race mask: the faction of the quest givers decides (pfQuest's
        # unit "fac": A, H or AH). A quest from Grom'gol is not for Alliance.
        if not fac and q["start"] and q["start"]["U"]:
            facs = {str(U[u]["fac"] or "") for u in ids(q["start"]["U"]) if U[u]}
            if facs == {"A"}:
                fac = "1"
            elif facs == {"H"}:
                fac = "2"
        starts = ["%d" % u for u in ids(q["start"]["U"] if q["start"] else None)] + \
                 ["o%d" % o for o in ids(q["start"]["O"] if q["start"] else None)]
        ends = ["%d" % u for u in ids(q["end"]["U"] if q["end"] else None)] + \
               ["o%d" % o for o in ids(q["end"]["O"] if q["end"] else None)]
        obj = []
        # what the quest sends you against: the units to kill and the units
        # that drop its items. Elite: every source of one objective is elite,
        # rare elite or a boss. Dungeon: one is found only indoors.
        targets, flags, mob = [], set(), 0
        if q["obj"]:
            for u in ids(q["obj"]["U"]):
                obj.append("k%dx1" % u)
                need_u.add(u)
                targets.append([("n", u)])
            for i in ids(q["obj"]["I"]):
                obj.append("i%dx1" % i)
                items[i] = None
                us, os_ = item_sources(i)
                if us and not os_:
                    targets.append([("n", u) for u in us])
            for o in ids(q["obj"]["O"]):
                obj.append("o%d" % o)
                need_o.add(o)
                targets.append([("o", o)])
        for group in targets:
            units = [U[i] for kind, i in group if kind == "n" and U[i]]
            if units and all(str(d["rnk"] or "") in ("1", "2", "3") for d in units):
                flags.add("E")
            if all(indoors((O if kind == "o" else U)[i]) for kind, i in group):
                flags.add("D")
            for d in units:
                mob = max(mob, top_level(d))
        for s in starts + ends:
            (need_o if s.startswith("o") else need_u).add(int(s.lstrip("o")))
        where = main_map([r for g in targets for r in g], U, O) or \
            main_map([("o" if s.startswith("o") else "n", int(s.lstrip("o"))) for s in starts], U, O)
        text = " ".join(str(loc["O"] or "").replace("$B", " ").replace("$b", " ").split())
        quests[qid] = "%s|%d|%d|%s|%s|%s||%s|%s|%s|%s|%s|%s|%s|%s|%d|%s" % (
            esc(title), lvl, mn, ",".join(starts), ",".join(ends),
            ",".join(str(p) for p in ids(q["pre"])), ",".join(str(c) for c in ids(q["close"])),
            ",".join(obj), where or "", race or "", cls or "", fac,
            "".join(sorted(flags)), mob or "", opens(qid), esc(text))

    # items: the three npcs that drop it most often, the two objects that hold it
    for i in list(items):
        us, os_ = item_sources(i)
        need_u.update(us)
        need_o.update(os_)
        items[i] = (IN[i] or "item %d" % i, us, os_)

    lines = [
        "-- OneKeyDruid/QuestData.lua: the Classic quests, both factions.",
        "-- Generated by tools/extract_pfquest.py from pfQuest (https://github.com/shagu/pfQuest),",
        "-- revision %s. pfQuest data: MIT License, Copyright (c) 2017-2021 Eric Mauser (Shagu)." % rev,
        "-- See THIRD_PARTY_NOTICES.md. Do not edit by hand.",
        '-- quest: "title|level|minLevel|starters|enders|pre(one of)|preAll|excl|objectives|uiMapID|raceMask|classMask|faction(1 A, 2 H)',
        '--         |flags(E elite, D dungeon)|highest mob level|quests it opens|what to do"',
        "--   starters/enders: npc ids, \"o\" before an object id; objectives: k<npc>x<n> kill, i<item>x<n> item, o<object>",
        '-- npc: "name|uiMapID|x,y,x,y...|level|rank(1 elite, 2 rare elite, 3 boss, 4 rare)"; object: "name|uiMapID|x,y,..."',
        '-- item: "name|npc,npc,npc|object,object"',
        "local _, ns = ...",
        "ns.QDB = { q = {",
    ]
    for qid in sorted(quests):
        lines.append('[%d]="%s",' % (qid, quests[qid]))
    lines.append("}, n = {")
    for u in sorted(need_u):
        if UN[u]:
            lines.append('[%d]="%s",' % (u, place(UN[u], U[u], True)))
    lines.append("}, o = {")
    for o in sorted(need_o):
        if ON[o]:
            lines.append('[%d]="%s",' % (o, place(ON[o], O[o])))
    lines.append("}, i = {")
    for i in sorted(items):
        name, us, os_ = items[i]
        lines.append('[%d]="%s|%s|%s",' % (i, esc(name), ",".join(str(u) for u in us), ",".join(str(o) for o in os_)))
    lines.append("} }")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("quests %d, npcs %d, objects %d, items %d (pfQuest %s)" % (len(quests), len(need_u), len(need_o), len(items), rev[:10]))


if __name__ == "__main__":
    main()
