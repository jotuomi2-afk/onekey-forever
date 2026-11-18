#!/usr/bin/env python3
"""Build OneKeyDruid/QuestData.lua from pfQuest's own database (MIT only).

    git clone https://github.com/shagu/pfQuest.git /tmp/pfQuest
    python3 tools/extract_pfquest.py /tmp/pfQuest OneKeyDruid/QuestData.lua

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
MAX_MIN_LEVEL, MAX_LEVEL = 45, 48


def load(db):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""pfDB = setmetatable({}, {__index = function(t, k)
        local v = setmetatable({}, {__index = function(t2, k2) local x = {} rawset(t2, k2, x) return x end})
        rawset(t, k, v) return v end})""")
    for f in ("quests.lua", "units.lua", "objects.lua", "items.lua",
              "enUS/quests.lua", "enUS/units.lua", "enUS/objects.lua", "enUS/items.lua"):
        with open(os.path.join(db, f), encoding="utf-8") as fh:
            lua.execute(fh.read())
    return lua.eval("pfDB")


def ids(t):
    return [int(v) for v in t.values()] if t else []


def esc(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("|", "/").replace("\n", " ")


def place(name, data):
    """name|uiMap|x,y,... : up to three points in the zone where most of it is."""
    coords = data["coords"] if data else None
    pts = [tuple(c.values()) for c in coords.values()] if coords else []
    by_zone = collections.defaultdict(list)
    for p in pts:
        if len(p) >= 3 and int(p[2]) in ZONE_TO_UIMAP:
            by_zone[int(p[2])].append(p)
    if not by_zone:
        return esc(name)
    zone, zp = max(by_zone.items(), key=lambda kv: len(kv[1]))
    pick = [zp[0], zp[len(zp) // 2], zp[-1]] if len(zp) >= 3 else zp
    ax, bx, ay, by = MAP_FIX.get(ZONE_TO_UIMAP[zone], (1.0, 0.0, 1.0, 0.0))
    seen, out = set(), []
    for p in pick:
        k = (round(ax * p[0] + bx, 1), round(ay * p[1] + by, 1))
        if k not in seen:
            seen.add(k)
            out.append("%g,%g" % k)
    return "%s|%d|%s" % (esc(name), ZONE_TO_UIMAP[zone], ",".join(out))


def main():
    src, out_path = sys.argv[1], sys.argv[2]
    db = os.path.join(src, "db")
    rev = subprocess.run(["git", "-C", src, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
    pf = load(db)
    Q, U, O, I = pf["quests"]["data"], pf["units"]["data"], pf["objects"]["data"], pf["items"]["data"]
    QN, UN, ON, IN = pf["quests"]["enUS"], pf["units"]["enUS"], pf["objects"]["enUS"], pf["items"]["enUS"]

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
        starts = ["%d" % u for u in ids(q["start"]["U"] if q["start"] else None)] + \
                 ["o%d" % o for o in ids(q["start"]["O"] if q["start"] else None)]
        ends = ["%d" % u for u in ids(q["end"]["U"] if q["end"] else None)] + \
               ["o%d" % o for o in ids(q["end"]["O"] if q["end"] else None)]
        obj = []
        if q["obj"]:
            for u in ids(q["obj"]["U"]):
                obj.append("k%dx1" % u)
                need_u.add(u)
            for i in ids(q["obj"]["I"]):
                obj.append("i%dx1" % i)
                items[i] = None
            for o in ids(q["obj"]["O"]):
                obj.append("o%d" % o)
                need_o.add(o)
        for s in starts + ends:
            (need_o if s.startswith("o") else need_u).add(int(s.lstrip("o")))
        quests[qid] = "%s|%d|%d|%s|%s|%s||%s|%s||%s|%s|%s" % (
            esc(title), lvl, mn, ",".join(starts), ",".join(ends),
            ",".join(str(p) for p in ids(q["pre"])), ",".join(str(c) for c in ids(q["close"])),
            ",".join(obj), race or "", cls or "", fac)

    # items: the three npcs that drop it most often
    for i in list(items):
        d = I[i]
        drops = sorted(((float(ch), int(u)) for u, ch in d["U"].items()), reverse=True)[:3] if d and d["U"] else []
        for _, u in drops:
            need_u.add(u)
        items[i] = (IN[i] or "item %d" % i, [u for _, u in drops])

    lines = [
        "-- OneKeyDruid/QuestData.lua: quests up to level ~45, both factions.",
        "-- Generated by tools/extract_pfquest.py from pfQuest (https://github.com/shagu/pfQuest),",
        "-- revision %s. pfQuest data: MIT License, Copyright (c) 2017-2021 Eric Mauser (Shagu)." % rev,
        "-- See THIRD_PARTY_NOTICES.md. Do not edit by hand.",
        '-- quest: "title|level|minLevel|starters|enders|pre(one of)|preAll|excl|objectives|zone|raceMask|classMask|faction(1 A, 2 H)"',
        "--   starters/enders: npc ids, \"o\" before an object id; objectives: k<npc>x<n> kill, i<item>x<n> item, o<object>",
        '-- npc/object: "name|uiMapID|x,y,x,y..."; item: "name|npc,npc,npc"',
        "local _, ns = ...",
        "ns.QDB = { q = {",
    ]
    for qid in sorted(quests):
        lines.append('[%d]="%s",' % (qid, quests[qid]))
    lines.append("}, n = {")
    for u in sorted(need_u):
        if UN[u]:
            lines.append('[%d]="%s",' % (u, place(UN[u], U[u])))
    lines.append("}, o = {")
    for o in sorted(need_o):
        if ON[o]:
            lines.append('[%d]="%s",' % (o, place(ON[o], O[o])))
    lines.append("}, i = {")
    for i in sorted(items):
        name, srcs = items[i]
        lines.append('[%d]="%s|%s",' % (i, esc(name), ",".join(str(u) for u in srcs)))
    lines.append("} }")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("quests %d, npcs %d, objects %d, items %d (pfQuest %s)" % (len(quests), len(need_u), len(need_o), len(items), rev[:10]))


if __name__ == "__main__":
    main()
