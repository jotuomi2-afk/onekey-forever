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


COVERAGE = os.environ.get("OKD_COVERAGE") == "1"
_HIT = {}  # file -> set of executed lines


def new_lua():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(read(STUB))
    if COVERAGE:
        # Lua line hook: records every executed line of the addon's chunks
        lua.execute("""COV = {}
        debug.sethook(function(_, line)
            local s = debug.getinfo(2, "S").source
            if s:sub(1, 1) == "@" then
                local t = COV[s] if not t then t = {} COV[s] = t end
                t[line] = true
            end
        end, "l")""")
        _COV_RUNTIMES.append(lua)
    return lua


_COV_RUNTIMES = []


def collect_coverage():
    for lua in _COV_RUNTIMES:
        cov = lua.eval("COV")
        for src in cov.keys():
            name = str(src)[1:]
            hits = _HIT.setdefault(name, set())
            for ln in cov[src].keys():
                hits.add(int(ln))
    _COV_RUNTIMES.clear()


_NONEXEC = re.compile(r"^\s*(--.*|end[,);]*|else|\}[,)]*|\)|\]\]|)\s*$")


def coverage_report(minimum=None):
    """Approximate line coverage: a line counts as executable unless it is
    blank, a comment, or a bare closer. Data files are excluded."""
    collect_coverage()
    rows, tot_e, tot_h = [], 0, 0
    for f in toc_files():
        if not f.endswith(".lua") or f == "QuestData.lua":
            continue
        lines = read(os.path.join(ADDON, f)).split("\n")
        in_long = False
        exe = set()
        for i, l in enumerate(lines, 1):
            if in_long:
                if "]]" in l:
                    in_long = False
                continue
            if l.strip().startswith("--[["):
                in_long = "]]" not in l
                continue
            if not _NONEXEC.match(l):
                exe.add(i)
        hit = _HIT.get(f, set()) & exe
        rows.append((f, len(hit), len(exe)))
        tot_e += len(exe)
        tot_h += len(hit)
    print("\nLine coverage (approximate)")
    for f, h, e in rows:
        print("  %-14s %5d/%-5d %5.1f%%" % (f, h, e, 100.0 * h / max(e, 1)))
    pct = 100.0 * tot_h / max(tot_e, 1)
    print("  %-14s %5d/%-5d %5.1f%%" % ("total", tot_h, tot_e, pct))
    if minimum is not None and pct < minimum:
        print("coverage %.1f%% is below the gate %.1f%%" % (pct, minimum))
        return False
    return True


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


def druid_fight(lua, ns, level, mode, selfcast=True):
    return druid_macros(lua, ns, level, mode, selfcast).fight


def druid_macros(lua, ns, level, mode, selfcast=True):
    """The druid macros at a level, with every spell and talent known
    (Feral Charge included), as Logic.BuildMacros makes them."""
    N = lua.eval("""{bear="Bear Form",cat="Cat Form",ht="Healing Touch",rejuv="Rejuvenation",regrowth="Regrowth",
     grasp="Nature's Grasp",bash="Bash",maul="Maul",wrath="Wrath",moonfire="Moonfire",roots="Entangling Roots",
     enrage="Enrage",roar="Demoralizing Roar",claw="Claw",rip="Rip",rake="Rake",shred="Shred",prowl="Prowl",
     ff="Faerie Fire (Feral)",fb="Ferocious Bite",ravage="Ravage",pounce="Pounce",tf="Tiger's Fury",
     hibernate="Hibernate",thorns="Thorns",motw="Mark of the Wild",direbear="Dire Bear Form",
     charge="Feral Charge - Cat",chargeBear="Feral Charge",travel="Travel Form",shadowmeld="Shadowmeld"}""")
    kb = {v: k for k, v in N.items()}
    kb["Faerie Fire"] = "ff"
    kn = lua.eval("{}")
    for sid, (name, lvl) in DRUID_SPELLS.items():
        if lvl <= level and name in kb:
            kn[kb[name]] = True
    if level >= 20:
        kn["charge"] = True
        kn["chargeBear"] = True
    cfg = lua.eval("{}")
    for k in ns.Logic.DEFAULTS.keys():
        cfg[k] = ns.Logic.DEFAULTS[k]
    cfg["enrage"] = True
    o = ns.Logic.BuildMacros(kn, N, lua.eval("{B=1,A=2,C=3}"), mode, cfg,
                             lua.eval("{selfcast=%s,potion=118,food=4536,water=159}" % ("true" if selfcast else "false")))
    return o


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
    ap.add_argument("--min-coverage", type=float, help="with OKD_COVERAGE=1: fail below this %%")
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
            ff="Faerie Fire (Feral)",fb="Ferocious Bite",ravage="Ravage",pounce="Pounce",tf="Tiger's Fury",hibernate="Hibernate",
            thorns="Thorns",motw="Mark of the Wild",direbear="Dire Bear Form",shadowmeld="Shadowmeld",
            travel="Travel Form",aquatic="Aquatic Form"}""")
        key_by_name = {v: k for k, v in N.items()}
        key_by_name["Faerie Fire"] = "ff"  # the client resolves ff to the feral spell
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
                    if mode != "caster" and "Wrath" in N.values() and level >= 1 and "wrath" in kn.keys() \
                            and "nocombat" not in fight:
                        p.append("level %d %s fight has no out-of-combat pull (selfcast %s)" % (level, mode, sc))
                    if mode == "bear" and level >= 18 and "Faerie Fire" not in fight:
                        p.append("level %d bear fight lost Faerie Fire (selfcast %s)" % (level, sc))
                    for k in o.keys():
                        v = o[k]
                        if isinstance(v, str) and re.search(r"\(Feral\)(?!\()", v):
                            p.append("level %d %s %s: 'Faerie Fire (Feral)' without () is read as a rank" % (level, mode, k))
                    if mode == "bear" and "Maul" not in fight:
                        p.append("level %d bear fight has no Maul" % level)
                    if mode != "caster" and "Form" not in fight:
                        p.append("level %d %s fight never shifts into a form" % (level, mode))
                    cp = o.catpull or ""
                    if mode == "cat" and "Prowl" in cp and "Claw" not in cp and "Pounce" not in cp:
                        p.append("level %d catpull without an opener" % level)
                    for pos in ("Ravage", "Shred"):
                        if pos in cp:
                            p.append("level %d catpull has %s, which fails from the front and stops F" % (level, pos))
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

    @S.test("keys: /okd bind takes only real keys and never the emergency key")
    def _():
        p = []
        lua = new_lua()
        ns, errs = load_addon(lua, ["Logic.lua"])
        KN = ns.Logic.KeyName

        def K(x):
            r = KN(x)
            return r if isinstance(r, tuple) else (r, None)
        for good, want in (("f", "F"), (" g ", "G"), ("F12", "F12"), ("numpad5", "NUMPAD5"), ("button4", "BUTTON4")):
            if K(good)[0] != want:
                p.append("%r should be the key %s" % (good, want))
        for bad in ("shift-f", "F G", "\u00e4", "50%", "F13", "", "ctrl-x"):
            if K(bad)[0] is not None:
                p.append("%r was accepted as a key" % bad)
        for cls, cid in (("DRUID", 11), ("MAGE", 8)):
            lua = new_lua()
            spells = druid_spells(20) if cls == "DRUID" else \
                {v[1]: v[2] for v in load_addon(new_lua(), ["Classes.lua"])[0].CLASSES[cls].spells.values()}
            set_class(lua, cls, cid, 20, spells)
            lua.execute("STUB.buffs = {}")
            ns, e2 = load_addon(lua)
            p += e2
            fire, slash = lua.eval("STUB.fire"), lua.eval("STUB.slash")
            for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
                p += lua_list(fire(e, "OneKeyDruid"))
            for cmd in ("bind F", "sos G", "bind G", "bind shift-f"):
                e = slash(cmd)
                if e:
                    p.append("%s /okd %s: %s" % (cls, cmd, e))
            b = lua.eval("STUB.bindings")
            if b["SHIFT-SHIFT-F"]:
                p.append("%s: bound SHIFT-SHIFT-F" % cls)
            if not b["F"]:
                p.append("%s: /okd bind G (the emergency key) moved the fight key off F" % cls)
        return p

    for cls, cid in (("DRUID", 11), ("MAGE", 8)):
        @S.test("reload in combat: %s keys work once the fight ends" % cls.lower())
        def _(cls=cls, cid=cid):
            lua = new_lua()
            spells = druid_spells(20) if cls == "DRUID" else \
                {v[1]: v[2] for v in load_addon(new_lua(), ["Classes.lua"])[0].CLASSES[cls].spells.values()}
            set_class(lua, cls, cid, 20, spells)
            lua.execute("STUB.buffs = {} STUB.combat = true")
            ns, errs = load_addon(lua)
            fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
            for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
                errs += lua_list(fire(e, "OneKeyDruid"))
            errs += lua_list(tick(8, 0.25))
            for v in lua_list(lua.eval("STUB.violations")):
                errs.append("taint while locked: " + v)
            lua.execute("STUB.combat = false STUB.violations = {}")
            errs += lua_list(fire("PLAYER_REGEN_ENABLED"))
            errs += lua_list(tick(4, 0.25))
            attrs = lua.eval("STUB.attrs")
            types = [str(k) for k in attrs.keys() if str(k).endswith(":type") and attrs[k] == "macro"]
            if len(types) < 5:
                errs.append("only %d buttons got type=macro after the fight" % len(types))
            return errs

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

    for cls, cid in (("DRUID", 11), ("MAGE", 8)):
        @S.test("alarm: %s attacked while away hears a sound" % cls.lower())
        def _(cls=cls, cid=cid):
            lua = new_lua()
            spells = druid_spells(20) if cls == "DRUID" else \
                {v[1]: v[2] for v in load_addon(new_lua(), ["Classes.lua"])[0].CLASSES[cls].spells.values()}
            set_class(lua, cls, cid, 20, spells)
            lua.execute("STUB.buffs = {}")
            ns, errs = load_addon(lua)
            fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
            for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
                errs += lua_list(fire(e, "OneKeyDruid"))
            errs += lua_list(tick(60, 10))          # ten minutes without a press
            errs += lua_list(fire("PLAYER_REGEN_DISABLED"))  # comes before the lock
            lua.execute("STUB.combat = true")
            errs += lua_list(tick(20, 0.5))
            if lua.eval("STUB.sounds") == 0:
                errs.append("no alarm sound in a fight after ten idle minutes")
            return errs

    def mage_session(level, extra=()):
        probe, _ = load_addon(new_lua(), ["Classes.lua"])
        CL = probe.CLASSES["MAGE"]
        allspells = {v[1]: (v[2], k) for k, v in CL.spells.items()}
        trained = {"fireball": 1, "frostarmor": 1, "frostbolt": 4, "ai": 6, "fireblast": 6, "water": 4, "food": 6,
                   "missiles": 8, "poly": 8, "nova": 10, "shoot": 1, "blink": 20, "cone": 26}
        for k in extra:
            trained[k] = 1
        spells = {sid: name for sid, (name, k) in allspells.items() if trained.get(k, 99) <= level}
        lua = new_lua()
        set_class(lua, "MAGE", 8, level, spells)
        lua.execute("STUB.buffs = {}")
        ns, errs = load_addon(lua)
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            errs += lua_list(fire(e, "OneKeyDruid"))
        errs += lua_list(tick(2, 0.25))
        return lua, ns, errs, fire, tick

    @S.test("macro: mage opens with the longest range (Fireball), then the Frostbolt slow")
    def _():
        p = []
        for level in (1, 4, 6, 10, 20, 26, 40):
            lua, ns, errs, fire, tick = mage_session(level, ("icelance",) if level >= 20 else ())
            p += errs
            M = ns.OneKeyMacros
            fight, heal, behind = M.fight or "", M.heal or "", M.behind or ""
            casts = [l for l in fight.split("\n") if l.startswith("/cast")]
            if not casts or "Fireball" not in casts[0]:
                p.append("level %d: the first spell is not Fireball: %r" % (level, casts[:1]))
            if level >= 4 and not re.search(r"Fireball, Frostbolt, Frostbolt", fight):
                p.append("level %d: Frostbolt does not follow Fireball: %r" % (level, fight))
            for cd in ("Fire Blast", "Frost Nova", "Cone of Cold", "Ice Lance"):
                if cd in fight:
                    p.append("level %d: %s (a cooldown) is on F and can stop the macro" % (level, cd))
            if level >= 10 and "Frost Nova" not in heal:
                p.append("level %d: Shift+F has no Frost Nova: %r" % (level, heal))
            if level >= 20 and "Frost Nova, Ice Lance" not in heal:
                p.append("level %d: Shift+F does not follow Nova with Ice Lance: %r" % (level, heal))
            if level >= 6 and "Fire Blast" not in behind:
                p.append("level %d: Ctrl+F has no Fire Blast: %r" % (level, behind))
            if "!Shoot" not in fight:
                p.append("level %d: no wand fallback on F" % level)
            for k in ("fight", "heal", "behind"):
                if len(M[k] or "") > MACRO_LIMIT:
                    p.append("level %d %s: %d chars" % (level, k, len(M[k])))
        return p

    @S.test("hud: mage hit in melee is told to Frost Nova, then Ice Lance")
    def _():
        lua, ns, p, fire, tick = mage_session(20, ("icelance",))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true")
        p += lua_list(tick(2, 0.25))
        if ns.OneKeyAlert():
            p.append("a hint before any hit: %r" % ns.OneKeyAlert())
        p += lua_list(fire("UNIT_COMBAT", "player", "WOUND", "", 30, 1))
        p += lua_list(tick(2, 0.25))
        a = ns.OneKeyAlert() or ""
        if "Frost Nova" not in a or "Shift+F" not in a:
            p.append("no Frost Nova hint after a melee hit: %r" % a)
        p += lua_list(fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast-1", 122))
        p += lua_list(tick(2, 0.25))
        a = ns.OneKeyAlert() or ""
        if "Ice Lance" not in a:
            p.append("no Ice Lance hint after Frost Nova: %r" % a)
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(2, 0.25))
        if ns.OneKeyAlert():
            p.append("the hint stays after the fight: %r" % ns.OneKeyAlert())
        return p

    # The client stops a macro at the first spell or item that fails (on
    # cooldown, out of range, wrong target, not behind); only a failed
    # usable-check (no mana, not learned, reactive not ready) or a false
    # [condition] skips a line. So anything that can fail that way may only
    # be the last thing a macro tries.
    MAY_FAIL = ("Fire Blast", "Frost Nova", "Cone of Cold", "Ice Lance", "Mind Blast", "Arcane Shot",
                "Stormstrike", "Enrage", "Feral Charge", "Bash", "Nature's Grasp", "Hibernate",
                "Ice Barrier", "Evasion", "Feign Death", "Divine Shield", "Divine Protection", "Lay on Hands",
                "Retaliation", "Intimidating Shout", "Psychic Scream", "Death Coil", "Stoneclaw Totem", "Gouge",
                "Shred", "Ravage", "Backstab", "Ambush", "/use [combat]")

    def may_fail_early(text):
        acts = [l for l in text.split("\n") if l.startswith(("/cast", "/use"))]
        out = []
        for l in acts[:-1]:
            for cd in MAY_FAIL:
                if cd in l:
                    out.append("%r can fail and comes before %r" % (l, acts[-1]))
        return out

    @S.test("macro: nothing that can fail comes before another spell (F, G and the druid keys)")
    def _():
        p = []
        probe, _ = load_addon(new_lua(), ["Classes.lua"])
        for cls, cid in (("MAGE", 8), ("WARRIOR", 1), ("ROGUE", 4), ("HUNTER", 3), ("PRIEST", 5),
                         ("WARLOCK", 9), ("PALADIN", 2), ("SHAMAN", 7)):
            CL = probe.CLASSES[cls]
            spells = {v[1]: v[2] for v in CL.spells.values()}
            lua = new_lua()
            set_class(lua, cls, cid, 60, spells)
            lua.execute("STUB.buffs = {}")
            ns, errs = load_addon(lua)
            p += errs
            fire = lua.eval("STUB.fire")
            for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
                p += lua_list(fire(e, "OneKeyDruid"))
            p += lua_list(lua.eval("STUB.tick")(4, 0.25))
            M = ns.OneKeyMacros
            if not M.fight:
                p.append("%s: no fight macro" % cls.lower())
            for k in ("fight", "sos"):
                p += ["%s %s: %s" % (cls.lower(), k, x) for x in may_fail_early(M[k] or "")]
            if cls == "PRIEST":
                for l in (M.fight or "").split("\n"):
                    if l.startswith("/cast") and "nochanneling" not in l:
                        p.append("priest: %r would cut Mind Flay short" % l)
        for level in (12, 22, 30, 40):
            lua = new_lua()
            nsl, _ = load_addon(lua, ["Logic.lua"])
            for mode in ("bear", "cat"):
                o = druid_macros(lua, nsl, level, mode)
                for k in ("fight", "sos", "cc", "heal", "catpull", "behind", "nuke"):
                    p += ["druid %d %s %s: %s" % (level, mode, k, x) for x in may_fail_early(o[k] or "")]
                if level >= 10 and "Rejuvenation" not in (o.sos or "") and mode == "cat":
                    p.append("druid %d: G has no heal: %r" % (level, o.sos))
        return p

    @S.test("macro: every class keeps its main spell, and no enemy means only targeting")
    def _():
        p = []
        probe, _ = load_addon(new_lua(), ["Classes.lua"])
        for cls, cid in (("MAGE", 8), ("WARRIOR", 1), ("ROGUE", 4), ("HUNTER", 3), ("PRIEST", 5),
                         ("WARLOCK", 9), ("PALADIN", 2), ("SHAMAN", 7)):
            CL = probe.CLASSES[cls]
            spells = {v[1]: v[2] for v in CL.spells.values()}
            # the main spell: the last fight line that names a spell
            last = None
            for i in range(1, len(CL.fight) + 1):
                e = CL.fight[i]
                if e[1] in ("cast", "once"):
                    last = CL.spells[e[2]][2]
                elif e[1] == "seq":
                    last = CL.spells[e[2][1]][2]
            lua = new_lua()
            set_class(lua, cls, cid, 60, spells)
            lua.execute("STUB.buffs = {} STUB.targetName = nil")
            ns, errs = load_addon(lua)
            p += errs
            fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
            for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
                p += lua_list(fire(e, "OneKeyDruid"))
            p += lua_list(tick(4, 0.25))
            fight = ns.OneKeyMacros.fight or ""
            if last and last not in fight:
                p.append("%s: main spell %s fell out of the fight macro (%d chars)" % (cls.lower(), last, len(fight)))
            main = macro_attrs(lua).get("OneKeyMain:macrotext", "")
            # a buff or a conjure is fine; an attack is not
            if "[harm" in main or "/startattack" in main:
                p.append("%s: with no target the key does more than target: %r" % (cls.lower(), main[:60]))
        return p

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

    @S.test("questhelp: hints for an Alliance druid in Darkshore, Redridge and Stranglethorn")
    def _():
        p = []
        for zone, mapid, level in (("Darkshore", 1439, 14), ("Redridge Mountains", 1433, 20),
                                   ("Stranglethorn Vale", 1434, 35)):
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
            # every offered quest by title must have an Alliance or neutral record
            horde_only = set()
            qdb = ns.QDB.q
            for qid in qdb.keys():
                f = str(qdb[qid]).split("|")
                if f[-1] == "2":
                    horde_only.add(f[0].strip())
            alliance = {str(qdb[q]).split("|")[0].strip() for q in qdb.keys() if str(qdb[q]).split("|")[-1] != "2"}
            # known Horde quests, independent of the data's own faction field
            for t in ("The Defense of Grom'gol", "Mok'thardin's Enchantment", "Hunt for Yenniku"):
                if t in text or t in (hint or ""):
                    p.append("%s level %d: Horde quest offered: %s (known Horde)" % (zone, level, t))
            for t in sorted(horde_only - alliance):
                if t in text or t in (hint or ""):
                    p.append("%s level %d: Horde quest offered: %s" % (zone, level, t))
        return p

    @S.test("performance: QuestHelp.Refresh stays inside its frame budget")
    def _():
        if COVERAGE:
            return []  # the line hook distorts timing
        lua = new_lua()
        set_class(lua, "DRUID", 11, 20, druid_spells(20))
        lua.execute('STUB.zone = "Redridge Mountains" STUB.map = 1433 STUB.quests = {} STUB.flagged = {}')
        ns, errs = load_addon(lua, ["QuestData.lua", "QuestHelp.lua"])
        if errs:
            return errs
        bench = lua.eval("""function(QH, n)
            local t = os.clock()
            for i = 1, n do QH.Refresh(20) QH.Hint(true) end
            return (os.clock() - t) / n * 1000
        end""")
        bench(ns.QH, 5)  # warm up
        ms = bench(ns.QH, 50)
        print("     QuestHelp.Refresh+Hint: %.2f ms per call" % ms)
        # Refresh runs on quest-log and zone events and every few seconds, never
        # per frame; 8 ms here leaves room for a slower game machine.
        return [] if ms < 8 else ["Refresh+Hint took %.2f ms (budget 8 ms)" % ms]

    @S.test("security: static scan finds nothing")
    def _():
        sys.path.insert(0, os.path.join(ROOT, "security"))
        import scan
        return ["%s:%d %s: %s" % f for f in scan.scan(ADDON)]

    @S.test("traceability: every requirement has a test")
    def _():
        p, names = [], [r["name"] for r in S.results]
        text = read(os.path.join(ROOT, "docs", "TEST_STRATEGY.md"))
        reqs = re.findall(r"^\| (REQ-\d+) \| [^|]+ \| ([^|]+) \|", text, re.M)
        if len(reqs) < 10:
            return ["only %d requirements found in TEST_STRATEGY.md" % len(reqs)]
        for req, tests in reqs:
            for t in (x.strip() for x in tests.split(";")):
                if t == "fuzz":
                    if not os.path.exists(os.path.join(ROOT, "tests", "fuzz_test.py")):
                        p.append("%s: fuzz test missing" % req)
                elif not any(n.startswith(t) for n in names):
                    p.append("%s: no test named %r" % (req, t))
        return p

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
    cov_ok = coverage_report(a.min_coverage) if COVERAGE else True
    sys.exit(0 if ok == len(S.results) and cov_ok else 1)


if __name__ == "__main__":
    main()
