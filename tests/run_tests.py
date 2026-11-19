#!/usr/bin/env python3
"""OneKey test suite: runs the addon in a real Lua 5.1 (lupa) against the fake
client in tests/wowstub.lua.

    python3 tests/run_tests.py            # all tests
    python3 tests/run_tests.py -k macro   # only tests whose name contains "macro"
    python3 tests/run_tests.py --json out.json

Exit code 0 when every test passes. Needs: pip install lupa
"""
import argparse, json, os, re, sys, time, traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "OneKeyDruid")
STUB = os.path.join(ROOT, "tests", "wowstub.lua")
MACRO_LIMIT = 255

try:
    from lupa.lua51 import LuaRuntime
except ImportError:  # lupa without a bundled 5.1
    sys.exit("lupa with Lua 5.1 is needed: pip install lupa")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def toc_files():
    toc = read(os.path.join(ADDON, "OneKeyDruid.toc"))
    return [l.strip() for l in toc.splitlines() if l.strip().endswith(".lua")]


def toc_field(name):
    m = re.search(r"^## %s:\s*(.+)$" % re.escape(name), read(os.path.join(ADDON, "OneKeyDruid.toc")), re.M)
    return m.group(1).strip() if m else None


# Spells by class with the level they are learned at (Classic levels; the test
# only needs a believable set per level). id -> (name, level)
DRUID_SPELLS = {
    5176: ("Wrath", 1), 1126: ("Mark of the Wild", 1), 5185: ("Healing Touch", 1),
    8921: ("Moonfire", 4), 774: ("Rejuvenation", 4), 467: ("Thorns", 6), 339: ("Entangling Roots", 8),
    5487: ("Bear Form", 10), 6807: ("Maul", 10), 99: ("Demoralizing Roar", 10), 6795: ("Growl", 10),
    8936: ("Regrowth", 12), 5229: ("Enrage", 12), 5211: ("Bash", 14), 1066: ("Aquatic Form", 16),
    770: ("Faerie Fire", 18), 2637: ("Hibernate", 18), 16689: ("Nature's Grasp", 10),
    768: ("Cat Form", 20), 1082: ("Claw", 20), 1079: ("Rip", 20), 5215: ("Prowl", 20),
    5221: ("Shred", 22), 1822: ("Rake", 24), 5217: ("Tiger's Fury", 24), 783: ("Travel Form", 30),
    22568: ("Ferocious Bite", 32), 6785: ("Ravage", 32), 9005: ("Pounce", 36), 20580: ("Shadowmeld", 1),
    2383: ("Find Herbs", 1),
}


class Suite:
    def __init__(self, only=None):
        self.only = only
        self.results = []

    def test(self, name):
        def wrap(fn):
            if self.only and self.only not in name:
                return fn
            t0 = time.time()
            try:
                problems = fn() or []
            except Exception:
                problems = ["exception: " + traceback.format_exc(limit=3)]
            self.results.append({"name": name, "ok": not problems, "problems": problems[:20],
                                 "more": max(0, len(problems) - 20), "secs": round(time.time() - t0, 2)})
            return fn
        return wrap


def new_lua():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(read(STUB))
    return lua


def load_addon(lua, files=None):
    """Load the toc's files in order, as the client does. Returns load errors."""
    ns = lua.eval("{}")
    loader = lua.eval("""function(src, name, ns)
        local f, e = loadstring(src, "@" .. name)
        if not f then return "compile " .. name .. ": " .. tostring(e) end
        local ok, err = pcall(f, "OneKeyDruid", ns)
        if not ok then return "run " .. name .. ": " .. tostring(err) end
    end""")
    errs = []
    for f in files or toc_files():
        e = loader(read(os.path.join(ADDON, f)), f, ns)
        if e:
            errs.append(e)
    return ns, errs


def set_class(lua, cls, class_id, level, spells):
    """spells: id -> name of everything learned."""
    lua.execute("STUB.known = {} STUB.names = {}")
    known, names = lua.eval("STUB.known"), lua.eval("STUB.names")
    for sid, name in spells.items():
        known[sid] = name
        names[sid] = name
    lua.execute('STUB.class = "%s" STUB.classId = %d STUB.level = %d' % (cls, class_id, level))


def druid_spells(level):
    return {sid: n for sid, (n, lvl) in DRUID_SPELLS.items() if lvl <= level}


def lua_list(t):
    return [t[i] for i in range(1, len(t) + 1)] if t else []


def run_session(lua, with_target=True):
    """Login, rest, pull, fight, leave combat, slash commands. Returns errors."""
    errs = []
    errs += lua_list(lua.eval("STUB.fire")("ADDON_LOADED", "OneKeyDruid"))
    errs += lua_list(lua.eval("STUB.fire")("PLAYER_LOGIN"))
    errs += lua_list(lua.eval("STUB.fire")("PLAYER_ENTERING_WORLD"))
    errs += lua_list(lua.eval("STUB.tick")(20, 0.25))
    if with_target:
        lua.execute('STUB.targetName = "Redridge Mongrel" STUB.targetLevel = STUB.level')
        errs += lua_list(lua.eval("STUB.tick")(8, 0.25))
    # the client fires REGEN_DISABLED just before the lockdown starts
    errs += lua_list(lua.eval("STUB.fire")("PLAYER_REGEN_DISABLED"))
    lua.execute("STUB.combat = true")
    errs += lua_list(lua.eval("STUB.fire")("UNIT_COMBAT", "player", "WOUND", "", 10, 1))
    errs += lua_list(lua.eval("STUB.tick")(40, 0.25))
    lua.execute("STUB.combat = false STUB.targetName = nil")
    errs += lua_list(lua.eval("STUB.fire")("PLAYER_REGEN_ENABLED"))
    errs += lua_list(lua.eval("STUB.tick")(10, 0.25))
    for cmd in ["", "status", "quests", "where", "go", "skip", "skip clear", "herbs", "brave off",
                "alarm on", "lang en", "lang fi", "runtest", "report", "session", "presses"]:
        e = lua.eval("STUB.slash")(cmd)
        if e:
            errs.append("/okd %s: %s" % (cmd, e))
    return errs


def macro_attrs(lua):
    out = {}
    attrs = lua.eval("STUB.attrs")
    for k in attrs.keys():
        if str(k).endswith(":macrotext") and attrs[k]:
            out[str(k)] = str(attrs[k])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", dest="only")
    ap.add_argument("--json")
    a = ap.parse_args()
    S = Suite(a.only)

    @S.test("compile: every Lua file compiles in Lua 5.1")
    def _():
        lua = LuaRuntime()
        check = lua.eval("function(s, n) local f, e = loadstring(s, n) return e end")
        bad = []
        for dirpath, _, files in os.walk(ROOT):
            if "/.git" in dirpath:
                continue
            for f in files:
                if f.endswith(".lua"):
                    p = os.path.join(dirpath, f)
                    e = check(read(p), f)
                    if e:
                        bad.append("%s: %s" % (os.path.relpath(p, ROOT), e))
        return bad

    @S.test("toc: files exist, versions agree, interface set")
    def _():
        p = []
        for f in toc_files():
            if not os.path.exists(os.path.join(ADDON, f)):
                p.append("toc lists a missing file: " + f)
        v = toc_field("Version")
        if not v:
            p.append("no ## Version")
        for f in ("Core.lua", "OneKey.lua"):
            m = re.search(r'local VERSION = "([^"]+)"', read(os.path.join(ADDON, f)))
            if not m or m.group(1) != v:
                p.append("%s VERSION %s != toc %s" % (f, m and m.group(1), v))
        if toc_field("Interface") is None:
            p.append("no ## Interface")
        if toc_field("SavedVariablesPerCharacter") != "OneKeyDruidDB":
            p.append("SavedVariables renamed: players would lose their settings")
        return p

    @S.test("macro: druid macros fit 255 characters at every level and setting")
    def _():
        p = []
        lua = new_lua()
        ns, errs = load_addon(lua, ["Logic.lua"])
        if errs:
            return errs
        L = ns.Logic
        N = lua.eval("""{bear="Bear Form",cat="Cat Form",ht="Healing Touch",rejuv="Rejuvenation",regrowth="Regrowth",
            grasp="Nature's Grasp",bash="Bash",maul="Maul",wrath="Wrath",moonfire="Moonfire",roots="Entangling Roots",
            enrage="Enrage",roar="Demoralizing Roar",claw="Claw",rip="Rip",rake="Rake",shred="Shred",prowl="Prowl",
            ff="Faerie Fire",fb="Ferocious Bite",ravage="Ravage",pounce="Pounce",tf="Tiger's Fury",hibernate="Hibernate",
            thorns="Thorns",motw="Mark of the Wild",direbear="Dire Bear Form",shadowmeld="Shadowmeld",
            travel="Travel Form",aquatic="Aquatic Form"}""")
        key_by_name = {v: k for k, v in N.items()}
        for level in (1, 4, 10, 14, 18, 20, 22, 24, 30, 32, 36, 40):
            kn = lua.eval("{}")
            for sid, (name, lvl) in DRUID_SPELLS.items():
                if lvl <= level and name in key_by_name:
                    kn[key_by_name[name]] = True
            forms = lua.eval("{B=1,A=2,C=3}") if level >= 20 else lua.eval("{B=1}") if level >= 10 else lua.eval("{}")
            for mode in ("caster", "bear", "cat"):
                if mode == "cat" and level < 20 or mode == "bear" and level < 10:
                    continue
                for sc in ("true", "false"):
                    items = lua.eval("{selfcast=%s,potion=118,food=4536,water=159}" % sc)
                    o = L.BuildMacros(kn, N, forms, mode, L.DEFAULTS, items)
                    for k in o.keys():
                        v = o[k]
                        if isinstance(v, str) and len(v) > MACRO_LIMIT:
                            p.append("level %d %s %s: %d chars" % (level, mode, k, len(v)))
                    fight = o.fight or ""
                    if mode == "cat" and "Claw" not in fight:
                        p.append("level %d cat fight has no Claw" % level)
                    if mode == "cat" and level >= 18 and "Faerie Fire" not in fight:
                        p.append("level %d cat fight lost Faerie Fire (selfcast %s)" % (level, sc))
                    if mode == "bear" and "Maul" not in fight:
                        p.append("level %d bear fight has no Maul" % level)
                    if mode != "caster" and "Form" not in fight:
                        p.append("level %d %s fight never shifts into a form" % (level, mode))
                    if mode == "cat" and "Prowl" in (o.catpull or "") and "Claw" not in o.catpull:
                        p.append("level %d catpull without a fallback Claw" % level)
        return p

    @S.test("macro: nuke mode ends in a form")
    def _():
        lua = new_lua()
        ns, errs = load_addon(lua, ["Logic.lua"])
        N = lua.eval('{bear="Bear Form",cat="Cat Form",wrath="Wrath",moonfire="Moonfire",claw="Claw",rip="Rip",maul="Maul"}')
        kn = lua.eval("{bear=true,cat=true,wrath=true,moonfire=true,claw=true,rip=true,maul=true}")
        o = ns.Logic.BuildMacros(kn, N, lua.eval("{B=1,C=3}"), "cat", ns.Logic.DEFAULTS, lua.eval("{}"))
        if o.nuke and "Cat Form" not in o.nuke:
            return ["nuke macro never shifts into a form: a fight could stay in caster form"]

    @S.test("logic: route and water advice")
    def _():
        lua = new_lua()
        ns, errs = load_addon(lua, ["Logic.lua"])
        L, p = ns.Logic, []
        adv = L.Route(18, "Darkshore")
        adv = adv[0] if isinstance(adv, tuple) else adv
        if not adv or "Darkshore" not in adv:
            p.append("no advice to leave Darkshore at 18: %r" % adv)
        r14 = L.Route(14, "Darkshore")
        if (r14[0] if isinstance(r14, tuple) else r14):
            p.append("advice to leave Darkshore at 14")
        if L.WaterFor(18) != "Ice Cold Milk":
            p.append("water for 18: " + str(L.WaterFor(18)))
        return p

    classes = [("DRUID", 11), ("MAGE", 8), ("WARRIOR", 1), ("ROGUE", 4), ("HUNTER", 3),
               ("PRIEST", 5), ("WARLOCK", 9), ("PALADIN", 2), ("SHAMAN", 7)]

    for cls, cid in classes:
        for level in ((5, 20, 32) if cls == "DRUID" else (20,)):
            @S.test("smoke: %s level %d — login, rest, fight, slash commands" % (cls.lower(), level))
            def _(cls=cls, cid=cid, level=level):
                lua = new_lua()
                if cls == "DRUID":
                    spells = druid_spells(level)
                else:
                    # every spell of the class list, so all its macro lines are built
                    probe, _ = load_addon(new_lua(), ["Classes.lua"])
                    spells = {}
                    for k, v in probe.CLASSES[cls].spells.items():
                        spells[v[1]] = v[2]
                set_class(lua, cls, cid, level, spells)
                lua.execute('STUB.buffs = {}')
                ns, errs = load_addon(lua)
                errs += run_session(lua)
                for v in lua_list(lua.eval("STUB.violations")):
                    errs.append("taint: " + v)
                for k, v in macro_attrs(lua).items():
                    if len(v) > MACRO_LIMIT:
                        errs.append("%s: %d chars" % (k, len(v)))
                e = lua.eval("STUB.slash")("bind F")
                if e:
                    errs.append("/okd bind F: " + e)
                b = lua.eval("STUB.bindings")
                if not b["F"]:
                    errs.append("no key bound to F after /okd bind F")
                if not b["G"]:
                    errs.append("emergency key G not bound")
                return errs

    @S.test("ranks: a new rank replaces the old one on the bars, never in combat, only once")
    def _():
        p = []
        lua = new_lua()
        set_class(lua, "DRUID", 11, 20, druid_spells(20))
        lua.execute("""STUB.book = { {"Healing Touch", 1, 5185}, {"Healing Touch", 2, 5186}, {"Wrath", 1, 5176} }
                       STUB.bar = { [1] = 5185, [2] = 5176, [13] = 5185 }""")
        ns, errs = load_addon(lua)
        p += errs
        lua.execute("STUB.combat = true")
        p += lua_list(lua.eval("STUB.fire")("SPELLS_CHANGED"))
        if lua.eval("#STUB.placed") != 0:
            p.append("bars changed in combat")
        lua.execute("STUB.combat = false")
        p += lua_list(lua.eval("STUB.fire")("ADDON_LOADED", "OneKeyDruid"))
        p += lua_list(lua.eval("STUB.fire")("PLAYER_REGEN_ENABLED"))
        bar = lua.eval("STUB.bar")
        if bar[1] != 5186 or bar[13] != 5186:
            p.append("Healing Touch not moved to rank 2: %s, %s" % (bar[1], bar[13]))
        if bar[2] != 5176:
            p.append("Wrath changed although it has one rank")
        if lua.eval("STUB.cursor"):
            p.append("cursor left holding a spell")
        # the player puts rank 1 back on purpose: it stays
        lua.execute("STUB.bar[1] = 5185")
        p += lua_list(lua.eval("STUB.fire")("SPELLS_CHANGED"))
        if lua.eval("STUB.bar")[1] != 5185:
            p.append("a rank put back on purpose was replaced again")
        for v in lua_list(lua.eval("STUB.violations")):
            p.append("taint: " + v)
        return p

    @S.test("questdata: every record parses and its references resolve")
    def _():
        lua = new_lua()
        ns, errs = load_addon(lua, ["QuestData.lua"])
        if errs:
            return errs
        Q = ns.QDB
        p, missing_start, n = [], 0, 0
        npcs, objs, items = Q.n, Q.o, Q.i
        for qid in Q.q.keys():
            n += 1
            f = str(Q.q[qid]).split("|")
            if len(f) != 13:
                p.append("quest %s: %d fields" % (qid, len(f)))
                continue
            starts = [s for s in f[3].split(",") if s]
            if not starts:
                continue
            s = starts[0]
            ok = objs[int(s[1:])] if s.startswith("o") else npcs[int(s)]
            if not ok:
                missing_start += 1
            for o in [x for x in f[8].split(",") if x]:
                m = re.match(r"^([kioa])(\d+)", o)
                if not m:
                    p.append("quest %s: bad objective %r" % (qid, o))
                elif m.group(1) == "i" and not items[int(m.group(2))]:
                    pass  # items without a known source exist in the data
        if n < 1000:
            p.append("only %d quests" % n)
        # positions checked in the game (WoW: Forever): Chef Breanna in Lakeshire
        # stood 36 yards from a player at 17.9, 46.3 on the Redridge map
        cb = str(npcs[343] or "")
        m = re.match(r"Chef Breanna\|1433\|([\d.]+),([\d.]+)", cb)
        if not m or abs(float(m.group(1)) - 17.9) > 2 or abs(float(m.group(2)) - 46.3) > 3:
            p.append("Chef Breanna not where the game shows her: " + cb)
        head = read(os.path.join(ADDON, "QuestData.lua"))[:1500]
        if "extract_pfquest.py" not in head or "revision" not in head:
            p.append("QuestData.lua does not name its generator and pfQuest revision")
        if missing_start > n * 0.02:
            p.append("%d of %d quests have a giver with no location" % (missing_start, n))
        return p

    @S.test("questhelp: hints for an Alliance druid in Darkshore and Redridge")
    def _():
        p = []
        for zone, mapid, level in (("Darkshore", 1439, 14), ("Redridge Mountains", 1433, 20)):
            lua = new_lua()
            set_class(lua, "DRUID", 11, level, druid_spells(level))
            lua.execute('STUB.zone = "%s" STUB.map = %d STUB.quests = {} STUB.flagged = {}' % (zone, mapid))
            ns, errs = load_addon(lua, ["QuestData.lua", "QuestHelp.lua"])
            p += errs
            best = ns.QH.Refresh(level)
            hint = ns.QH.Hint(True)
            if not hint:
                p.append("%s level %d: no hint" % (zone, level))
            # nothing for the Horde or for another class
            L = ns.QH
            out = []
            L.List(lambda s: out.append(s), 50)
            text = "\n".join(out)
            for horde in ("Orgrimmar", "Thunder Bluff", "Undercity"):
                if "@ " + horde in text:
                    p.append("Horde quest offered: " + horde)
        return p

    @S.test("security: static scan finds nothing")
    def _():
        sys.path.insert(0, os.path.join(ROOT, "security"))
        import scan
        return ["%s:%d %s: %s" % f for f in scan.scan(ADDON)]

    t0 = time.time()
    # the decorators already ran every test
    ok = sum(r["ok"] for r in S.results)
    for r in S.results:
        print(("PASS " if r["ok"] else "FAIL ") + r["name"] + " (%.2fs)" % r["secs"])
        for x in r["problems"]:
            print("     - " + x.replace("\n", "\n       "))
        if r["more"]:
            print("     ... and %d more" % r["more"])
    print("\n%d/%d passed" % (ok, len(S.results)))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(S.results, f, indent=1)
    sys.exit(0 if ok == len(S.results) else 1)


if __name__ == "__main__":
    main()
