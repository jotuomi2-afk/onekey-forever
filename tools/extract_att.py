#!/usr/bin/env python3
"""Build OneKeyDruid/QuestDataNew.lua: the quests WoW: Forever added, from
All The Things' Forever database (MIT).

    git clone --depth 1 https://github.com/ATTWoWAddon/AllTheThings.git /tmp/att
    git -C /tmp/att checkout 32657332c5ed0a8f79f9c8ad3a691e74d5c1a7f6
    python3 -I tools/extract_att.py /tmp/att OneKeyDruid/QuestData.lua OneKeyDruid/QuestDataNew.lua

(or, instead of a clone, a folder that holds db/Camelot/Categories/Zones.lua
and a REVISION file with the commit). The script refuses another revision
unless --any-revision is given.

pfQuest (QuestData.lua) has the Classic quests with their mobs and texts.
It knows nothing of the quests Forever added. All The Things lists those
with where they start, the level they open at, who may take them and what
comes before; that is all this file takes, and only for quests QuestData.lua
does not have. No names, no lore, no quest text: the client asks the server
for a quest's title.

All The Things' built data is a Lua file of nested constructor calls. It is
third-party code: it runs here in a sandbox with no os, io, require or file
loading, and every constructor only builds a table.
"""
import os, subprocess, sys

try:
    from lupa.lua54 import LuaRuntime
except ImportError:
    from lupa import LuaRuntime

PINNED = "32657332c5ed0a8f79f9c8ad3a691e74d5c1a7f6"
SOURCE = "db/Camelot/Categories/Zones.lua"


def revision(src):
    f = os.path.join(src, "REVISION")
    if os.path.exists(f):
        return open(f, encoding="utf-8").read().strip()
    return subprocess.run(["git", "-C", src, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"


def load(path):
    """The Zones tree as nested tables: { kind, id, t = fields }."""
    lua = LuaRuntime(unpack_returned_tuples=True, register_eval=False, register_builtins=False)
    lua.execute("""
        local load, setmetatable, select, type, error, tostring = load, setmetatable, select, type, error, tostring
        os, io, package, require, dofile, loadfile, debug, collectgarbage = nil, nil, nil, nil, nil, nil, nil, nil
        function RUN_ATT(src)
            local built
            -- anything the file reaches for is a stand-in: called, it
            -- remembers what it was called with; indexed, it gives another
            local function standin(name)
                return setmetatable({}, {
                    __call = function(_, ...)
                        local n = select("#", ...)
                        local node = { kind = name, id = (select(1, ...)) }
                        local last = select(n, ...)
                        if type(last) == "table" then node.t = last end
                        return node
                    end,
                    __index = function(_, k) return standin(name .. "." .. tostring(k)) end,
                })
            end
            local app = setmetatable({}, { __index = function(_, name)
                if name == "AddEventHandler" then
                    return function(_, fn) built = fn end
                end
                return standin(name)
            end })
            local f, e = load(src, "=att", "t", {})
            if not f then error("att: " .. tostring(e)) end
            f("AllTheThings", app)
            if not built then error("att: no OnBuildDataCache handler") end
            local categories = {}
            built(categories)
            return categories.Zones
        end""")
    with open(path, encoding="utf-8-sig") as fh:
        return lua.eval("RUN_ATT")(fh.read())


def seq(t):
    return list(t.values()) if t else []


def num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def first_coords(t):
    """coords = { [uiMap] = { {x, y}, ... } } -> (map, [(x, y), ...])."""
    c = t["coords"] if t else None
    if not c:
        return 0, []
    for m in sorted(c.keys()):
        pts = [(float(p[1]), float(p[2])) for p in c[m].values() if p[1] and p[2]]
        if pts:
            return int(m), pts
    return 0, []


def children(t):
    """A node's children: its g = { ... }, or, for a header, the list itself."""
    if t is None:
        return []
    inner = seq(t["g"]) if t["g"] else [v for k, v in t.items() if isinstance(k, int)]
    return [c for c in inner if hasattr(c, "keys") and c["kind"]]


# races of each side (Classic ids), and the maps where only one side quests
ALLIANCE_RACES, HORDE_RACES = {1, 3, 4, 7}, {2, 5, 6, 8}
ALLIANCE_MAPS = {1426, 1429, 1438, 1453, 1455, 1457, 1436, 1432, 1439}
# (not the Barrens: Ratchet gives quests to both sides)
HORDE_MAPS = {1411, 1412, 1420, 1454, 1456, 1458, 1421}
# quest ids Forever added start far above the Classic ones (the highest
# Classic id is under 10 000); a lower id that pfQuest lacks is an old
# quest pfQuest or its extractor left out on purpose (events, professions)
FIRST_NEW_ID = 20000


def side(t, inherited):
    """'1' Alliance, '2' Horde, '' both or unknown: r on the node or above
    it, else the races it names."""
    r = num(t["r"]) or inherited.get("r", 0)
    if r in (1, 2):
        return {1: "2", 2: "1"}[r]
    races = {num(x) for x in seq(t["races"])} or inherited.get("races", set())
    if races and races <= ALLIANCE_RACES:
        return "1"
    if races and races <= HORDE_RACES:
        return "2"
    return ""


def walk(node, out, inherited=None):
    if not node:
        return
    inherited = dict(inherited or {})
    t = node["t"]
    kind = str(node["kind"] or "")
    if t is not None and kind != "CreateQuest":
        # what a header or an npc says holds for the quests under it
        if num(t["r"]) in (1, 2):
            inherited["r"] = num(t["r"])
        if seq(t["races"]):
            inherited["races"] = {num(x) for x in seq(t["races"])}
        if isinstance(t["lvl"], (int, float)):
            inherited["lvl"] = num(t["lvl"])
        if seq(t["c"]):
            inherited["c"] = [num(c) for c in seq(t["c"])]
    if kind == "CreateQuest" and t is not None:
        qid = num(node["id"])
        m, pts = first_coords(t)
        lvl = t["lvl"]
        if lvl is not None and not isinstance(lvl, (int, float)):
            lvl = seq(lvl)[0] if seq(lvl) else 0
        if not num(lvl):
            lvl = inherited.get("lvl", 0)
        flags = ""
        if t["isBreadcrumb"]:
            flags += "B"
        skip = bool(t["repeatable"] or t["requireSkill"] or t["u"] or t["rwp"] or t["cost"] or t["minReputation"]
                    or t["isDaily"] or t["isWeekly"] or t["pvp"])
        om, opts = 0, []
        for child in children(t):
            if str(child["kind"]) == "CreateQuestObjective" and child["t"] is not None and not opts:
                om, opts = first_coords(child["t"])
        # no level: it would be offered at every level, as a guess
        if qid >= FIRST_NEW_ID and m and pts and not skip and num(lvl) > 0:
            fac = side(t, inherited)
            if not fac and m in ALLIANCE_MAPS:
                fac = "1"
            elif not fac and m in HORDE_MAPS:
                fac = "2"
            classes = [num(c) for c in seq(t["c"])] or inherited.get("c", [])
            cls = sum(2 ** (c - 1) for c in classes if 0 < c < 20)
            out[qid] = "%d|%s|%s|%d|%g,%g|%s|%s|%s|%s" % (
                num(lvl), fac, cls or "", m, pts[0][0], pts[0][1],
                ",".join(str(num(p)) for p in seq(t["sourceQuests"]) if num(p) > 0), flags,
                om or "", ",".join("%g,%g" % p for p in opts[:3]))
    for child in children(t):
        walk(child, out, inherited)


def known_ids(quest_data):
    out = set()
    with open(quest_data, encoding="utf-8") as f:
        for line in f:
            if line.startswith("}, n = {"):
                break
            if line.startswith("["):
                out.add(int(line[1:line.index("]")]))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src, quest_data, out_path = args[0], args[1], args[2]
    rev = revision(src)
    if rev != PINNED and "--any-revision" not in sys.argv:
        sys.exit("All The Things is at %s, the pinned revision is %s (see the docstring)" % (rev, PINNED))
    found = {}
    walk(load(os.path.join(src, SOURCE)), found)
    have = known_ids(quest_data)
    new = {q: v for q, v in found.items() if q not in have}
    lines = [
        "-- OneKeyDruid/QuestDataNew.lua: where the quests WoW: Forever added start.",
        "-- Generated by tools/extract_att.py from All The Things (https://github.com/ATTWoWAddon/AllTheThings),",
        "-- revision %s, file %s." % (rev, SOURCE),
        "-- All The Things data: MIT License, Copyright (c) 2026 AllTheThings WoW Addon.",
        "-- See THIRD_PARTY_NOTICES.md. Do not edit by hand. Only quests QuestData.lua (pfQuest) does not have.",
        '-- quest: "minLevel|faction(1 A, 2 H)|classMask|uiMapID|x,y|before(one of)|flags(B leads on to another)|objective uiMapID|x,y,..."',
        "local _, ns = ...",
        "ns.QDBX = {",
    ]
    for qid in sorted(new):
        lines.append('[%d]="%s",' % (qid, new[qid]))
    lines.append("}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("All The Things: %d quests with a start, %d of them not in QuestData.lua (%s)" % (len(found), len(new), rev[:10]))


if __name__ == "__main__":
    main()
