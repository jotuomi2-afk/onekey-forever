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
    5221: ("Shred", 20), 1822: ("Rake", 24), 5217: ("Tiger's Fury", 24), 783: ("Travel Form", 30),
    22568: ("Ferocious Bite", 24), 6785: ("Ravage", 32), 9005: ("Pounce", 36), 20580: ("Shadowmeld", 1),
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


def druid_macros(lua, ns, level, mode, selfcast=True, mana=None, extra=""):
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
                             lua.eval("{selfcast=%s,potion=118,food=4536,water=159,mana=%s,%s}" % (
                                 "true" if selfcast else "false", mana or "nil", extra)))
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

    @S.test("lang: English is the default, also for an old Finnish setting")
    def _():
        p = []
        for cls, cid in (("DRUID", 11), ("MAGE", 8)):
            for old in (None, "fi"):
                lua = new_lua()
                spells = druid_spells(20) if cls == "DRUID" else \
                    {v[1]: v[2] for v in load_addon(new_lua(), ["Classes.lua"])[0].CLASSES[cls].spells.values()}
                set_class(lua, cls, cid, 20, spells)
                lua.execute("STUB.buffs = {}")
                if old:
                    lua.execute('OneKeyDruidDB = { lang = "fi" }')
                ns, errs = load_addon(lua)
                p += errs
                fire = lua.eval("STUB.fire")
                for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
                    p += lua_list(fire(e, "OneKeyDruid"))
                lang = lua.eval("OneKeyDruidDB.lang")
                if lang != "en":
                    p.append("%s (old %s): lang is %r" % (cls.lower(), old, lang))
                # /okd lang fi still sticks after the move
                lua.eval("STUB.slash")("lang fi")
                for e in ("ADDON_LOADED",):
                    p += lua_list(fire(e, "OneKeyDruid"))
                if lua.eval("OneKeyDruidDB.lang") != "fi":
                    p.append("%s: /okd lang fi did not stick" % cls.lower())
        for f in ("Core.lua", "OneKey.lua"):
            src = read(os.path.join(ADDON, f))
            m = re.search(r"\ben = \{(.*?)\n\t\},?\n|\ben = \{([^\n]*)\}", src, re.S)
            body = (m.group(1) or m.group(2)) if m else ""
            if re.search("[\u00e4\u00f6]", body):
                p.append("%s: Finnish letters in the English texts" % f)
        return p

    @S.test("druid: rooted, the HUD says Shift+G breaks free; from caster form Ctrl+G brings you back")
    def _():
        p = []
        lua = new_lua()
        set_class(lua, "DRUID", 11, 22, druid_spells(22))
        lua.execute("STUB.buffs = {}")
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(4, 0.25))
        attrs = macro_attrs(lua)
        free = next((v for k, v in attrs.items() if "Free" in k or "free" in k), "")
        hide = next((v for k, v in attrs.items() if "Hide" in k or "hide" in k), "")
        # Forever has no powershifting: the key swaps forms
        if free.strip() != "/cast [form:3] Bear Form; Cat Form":
            p.append("break-free key: want cat to bear, anything else to cat: %r" % free)
        if "/cancelform" not in hide:
            p.append("Ctrl+G does not bring you back to caster form: %r" % hide)
        # caster form, in combat, rooted
        lua.execute('STUB.targetName = "Thistlefur Shaman" STUB.targetLevel = 23 STUB.form = 0')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true STUB.rooted = true")
        p += lua_list(tick(3, 0.25))
        t = ns.DruidHud() or ""
        if "Shift+G" not in t:
            p.append("rooted in caster form, the HUD says %r" % t)
        # Shift+G: into cat form, the root is gone
        lua.execute("STUB.rooted = false STUB.form = 3")
        p += lua_list(fire("UPDATE_SHAPESHIFT_FORM"))
        p += lua_list(tick(3, 0.25))
        t = ns.DruidHud() or ""
        if "Ctrl+G" not in t:
            p.append("after breaking free from caster form, the HUD says %r" % t)
        p += lua_list(tick(40, 0.25))
        if "Ctrl+G" in (ns.DruidHud() or ""):
            p.append("the back-to-caster hint stays too long")
        return p

    @S.test("druid: log of 20.11. (Faerie Fire once, Ctrl+F guard, health after a death)")
    def _():
        p = []
        lua = new_lua()
        nsl, _ = load_addon(lua, ["Logic.lua"])
        for level in (20, 23, 32, 40):
            for sc in (True, False):
                fight = druid_macros(lua, nsl, level, "cat", sc).fight
                seqs = [l for l in fight.split("\n") if l.startswith("/castsequence [form:3]")]
                seq = seqs[0] if seqs else ""
                # Faerie Fire opens the cat sequence (a line after it is never
                # reached: no energy stops the macro), once per two rounds
                if "reset=target Faerie Fire" not in seq:
                    p.append("level %d selfcast %s: Faerie Fire does not open the cat sequence: %r" % (level, sc, seq))
                fins = len(re.findall(r"\b(Rip|Ferocious Bite)\b", seq))
                if 20 <= level < 32 and not sc and fins < 2:
                    p.append("level %d: one round per Faerie Fire (it comes back every round): %r" % (level, seq))
                acts = [l for l in fight.split("\n") if l.startswith(("/cast", "/use"))]
                if acts and acts[-1] != seq:
                    p.append("level %d: a line after the cat sequence is never reached: %r" % (level, acts[-1]))
                if "nocombat,harm] Wrath" not in fight:
                    p.append("level %d selfcast %s: the Wrath pull fell out" % (level, sc))
        # Ctrl+F follows the pull guard; health after a resurrection
        lua = new_lua()
        set_class(lua, "DRUID", 11, 23, druid_spells(23))
        # buffed and in cat form: the key is down to targeting and fighting
        lua.execute('STUB.buffs = { ["Mark of the Wild"] = true, ["Thorns"] = true } STUB.form = 3')
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(4, 0.25))

        def behind():
            a = macro_attrs(lua)
            return next((v for k, v in a.items() if "Behind" in k or "behind" in k), None)
        before = behind()
        if not before:
            p.append("no Ctrl+F macro to start with")
        lua.execute('STUB.targetName = "Taskmaster Whipfang" STUB.targetLevel = 22 STUB.targetClass = "rareelite"')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(tick(4, 0.25))
        if behind():
            p.append("Ctrl+F still opens on a rare elite: %r (HUD %r)" % (behind(), ns.DruidHud()))
        lua.execute('STUB.targetClass = "normal" STUB.targetName = "Venture Co. Operator" STUB.targetLevel = 21')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(tick(4, 0.25))
        if behind() != before:
            p.append("Ctrl+F did not come back on a normal mob")
        lua.execute("STUB.targetName = nil")
        p += lua_list(fire("PLAYER_DEAD"))
        p += lua_list(fire("PLAYER_UNGHOST"))
        p += lua_list(tick(2, 0.25))
        main = macro_attrs(lua).get("OneKeyDruidButton:macrotext", "")
        if "Regrowth" not in main and "Healing Touch" not in main and "Rejuvenation" not in main and "item:" not in main:
            p.append("after a corpse run (half health) F does not heal or rest: %r" % main[:80])
        return p

    @S.test("logic: a cat with a target keeps its form for a Mark with time left; party members get the Mark")
    def _():
        p = []
        lua = new_lua()
        ns, errs = load_addon(lua, ["Logic.lua"])
        p += errs
        D = lua.eval("""function(L, form, target, motw, motwAny, party)
            local cfg = {}
            for k, v in pairs(L.DEFAULTS) do cfg[k] = v end
            local s = { cfg = cfg, known = { ht = true, motw = true, thorns = true },
                buffs = { motw = motw, motwAny = motwAny, thorns = true }, target = target, mode = "cat",
                form = form, partyMotw = party, mana = nil, hp = nil }
            local a, b, c = L.Decide(s)
            return tostring(a) .. ":" .. tostring(b) .. ":" .. tostring(c)
        end""")
        r = D(ns.Logic, "cat", "hostile", False, True, None)
        if not r.startswith("attack"):
            p.append("cat, target, Mark running out: %s (should keep fighting in form)" % r)
        r = D(ns.Logic, "cat", "hostile", False, False, None)
        if not r.startswith("buff:motw"):
            p.append("cat, target, no Mark at all: %s (should put it back)" % r)
        r = D(ns.Logic, "cat", "none", False, True, None)
        if not r.startswith("buff:motw"):
            p.append("no target, Mark running out: %s (should renew)" % r)
        r = D(ns.Logic, "none", "hostile", True, True, "party2")
        if r != "buff:motw:party2":
            p.append("a party member without the Mark: %s" % r)
        r = D(ns.Logic, "cat", "hostile", True, True, "party2")
        if r.startswith("buff"):
            p.append("a cat with a target leaves its form for a party buff: %s" % r)
        m = ns.Logic.ActionMacro("buff", "Mark of the Wild", None, "", "party2")
        if "/cast [@party2] Mark of the Wild" not in m:
            p.append("party buff macro: %r" % m)
        m = ns.Logic.ActionMacro("buff", "Mark of the Wild", None, "", "raid7")
        if "[@player]" not in m:
            p.append("a unit that is not party1-4 must not reach the macro: %r" % m)
        return p

    @S.test("logic: no heal at full health before a tough pull; buffs come first")
    def _():
        p = []
        lua = new_lua()
        ns, errs = load_addon(lua, ["Logic.lua"])
        p += errs
        D = lua.eval("""function(L, deficit, expect, motw)
            local cfg = {}
            for k, v in pairs(L.DEFAULTS) do cfg[k] = v end
            local s = { cfg = cfg, known = { ht = true, regrowth = true, rejuv = true, motw = true, thorns = true },
                buffs = { motw = motw, thorns = motw }, target = "hostile", mode = "cat",
                deficit = deficit, maxhp = 1000, expect = expect, mana = nil, hp = nil, mana_est = 80 }
            local a, b = L.Decide(s)
            return tostring(a) .. ":" .. tostring(b)
        end""")
        r = D(ns.Logic, 0, 700, False)
        if r.startswith("heal"):
            p.append("full health, tough mob, no buffs: %s (should buff)" % r)
        r = D(ns.Logic, 50, 700, True)
        if r.startswith("heal"):
            p.append("5 %% missing, tough mob: %s (should not heal)" % r)
        r = D(ns.Logic, 400, 400, True)
        if not r.startswith("heal"):
            p.append("40 %% missing before a tough mob: %s (should heal)" % r)
        return p

    @S.test("druid: G is Rejuvenation with the potion, Nature's Grasp (when ready), then the bear")
    def _():
        p = []
        lua = new_lua()
        nsl, _ = load_addon(lua, ["Logic.lua"])
        o = druid_macros(lua, nsl, 23, "cat")
        g, plain = o.sosGrasp or "", o.sos or ""
        lines = g.split("\n")
        want = ["/cancelform [form:3]",
                "/castsequence [@player,noform:1] reset=20/combat Rejuvenation, Nature's Grasp, Bear Form, null",
                "/use [combat] item:118"]
        if lines != want:
            p.append("G with Grasp is %r" % lines)
        if "Nature's Grasp" in plain or "Bear Form, null" not in plain:
            p.append("G without Grasp is %r" % plain)
        # Core: the fight start picks the version
        lua = new_lua()
        set_class(lua, "DRUID", 11, 23, druid_spells(23))
        lua.execute('STUB.buffs = { ["Mark of the Wild"] = true, ["Thorns"] = true } STUB.form = 3')
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(4, 0.25))

        def sos():
            a = macro_attrs(lua)
            return next((v for k, v in a.items() if "Sos" in k or "SOS" in k or "sos" in k), "")
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        if "Nature's Grasp" not in sos():
            p.append("fight start, Grasp ready: G lacks it: %r" % sos())
        lua.execute("STUB.combat = true")
        p += lua_list(lua.eval("STUB.castDone")(16689))
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(4, 0.25))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        if "Nature's Grasp" in sos():
            p.append("next fight within a minute: G still has Grasp (it would stop the key)")
        return p

    @S.test("druid: cat finishers are Rip first, then Ferocious Bite once it is learned")
    def _():
        p = []
        lua = new_lua()
        nsl, _ = load_addon(lua, ["Logic.lua"])
        for lvl in (23, 25, 40):
            f = druid_macros(lua, nsl, lvl, "cat").fight or ""
            seq = next((l for l in f.split("\n") if l.startswith("/castsequence") and "Claw" in l), "")
            if len(f) > 255:
                p.append("level %d: F is %d characters" % (lvl, len(f)))
            rip, fb = seq.find("Rip"), seq.find("Ferocious Bite")
            if lvl < 24 and fb >= 0:
                p.append("level %d: Ferocious Bite before it is learned: %r" % (lvl, seq))
            if lvl >= 24 and not (0 <= rip < fb):
                p.append("level %d: want Rip, then Ferocious Bite: %r" % (lvl, seq))
            # the Bite gets three Claws behind it (22.11.: two were too few)
            if lvl >= 24 and seq[rip:fb].count("Claw") < 3:
                p.append("level %d: fewer than three Claws before the Bite: %r" % (lvl, seq))
        return p

    @S.test("druid: a camp of enemies near the target holds the pull key (death of 21.11. evening)")
    def _():
        p = []
        lua = new_lua()
        set_class(lua, "DRUID", 11, 25, druid_spells(25))
        lua.execute("""STUB.buffs = { ["Mark of the Wild"] = true, ["Thorns"] = true }
            STUB.plates = 0
            C_NamePlate.GetNamePlates = function()
              local t = {} for i = 1, STUB.plates do t[i] = { namePlateUnitToken = "nameplate" .. i } end return t end
            local ca, ul = UnitCanAttack, UnitLevel
            UnitCanAttack = function(a, b) if tostring(b):find("^nameplate") then return true end return ca(a, b) end
            UnitLevel = function(u) if tostring(u):find("^nameplate") then return 23 end return ul(u) end
            local ir = C_Spell.IsSpellInRange
            C_Spell.IsSpellInRange = function(s, u) if tostring(u):find("^nameplate") then return true end return ir(s, u) end""")
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(4, 0.25))
        lua.execute('STUB.targetName = "Mosshide Trapper" STUB.targetLevel = 23')
        for plates, want in ((7, "DO NOT PULL: 7 more"), (2, "careful, 2 more"), (0, None)):
            lua.execute("STUB.plates = %d" % plates)
            p += lua_list(fire("PLAYER_TARGET_CHANGED"))
            p += lua_list(tick(1, 0.25))
            label = str(ns.DruidHud() or "")
            if want and want not in label:
                p.append("%d enemies close: label %r, want %r" % (plates, label, want))
            if not want and ("more mobs" in label or "PULL" in label):
                p.append("no camp, still a warning: %r" % label)
        lua.execute("OneKeyDruidDB.brave = true STUB.plates = 7")
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(tick(1, 0.25))
        if "DO NOT PULL" in str(ns.DruidHud() or ""):
            p.append("/okd brave on still holds the key at a camp")
        return p

    @S.test("druid: G fits the mana left after the pull (death in the log of 21.11.)")
    def _():
        p = []
        lua = new_lua()
        nsl, _ = load_addon(lua, ["Logic.lua"])
        # level 24 costs as the client gives them; 700 mana at most
        costs = "form=180,cat=180,bear=180,rejuv=105,wrath=55,moonfire=75,grasp=50,ff=60"
        poor = "{cost={%s},est=700,max=700}" % costs
        o = druid_macros(lua, nsl, 24, "cat", mana=poor)
        if o.sosGrasp:
            p.append("Nature's Grasp in G when the pull and G cost more than the mana: %r" % o.sosGrasp)
        if "/cancelform" in (o.sos or ""):
            p.append("G leaves cat form with no mana for the bear after: %r" % o.sos)
        if "/cast [form:3][noform] Bear Form" not in (o.sos or ""):
            p.append("a cat with no mana to spare does not go straight into the bear: %r" % o.sos)
        # short of mana with a mana potion: the potion once, then the bear,
        # and no healing potion behind it (they share a cooldown)
        o = druid_macros(lua, nsl, 24, "cat", mana=poor, extra="manaPotion=3827")
        want = ["/castsequence [combat] reset=combat item:3827, null", "/cast [form:3][noform] Bear Form"]
        if (o.sos or "").split("\n") != want:
            p.append("G short of mana with a mana potion is %r" % o.sos)
        rich = "{cost={%s},est=2000,max=2000}" % costs
        o = druid_macros(lua, nsl, 24, "cat", mana=rich)
        if not o.sosGrasp or "/cancelform" not in (o.sos or ""):
            p.append("with mana enough G should heal and Grasp: %r / %r" % (o.sos, o.sosGrasp))
        return p

    @S.test("druid: a potion still cooling when the fight starts is left out of G")
    def _():
        p = []
        lua = new_lua()
        set_class(lua, "DRUID", 11, 23, druid_spells(23))
        lua.execute("""STUB.buffs = { ["Mark of the Wild"] = true, ["Thorns"] = true } STUB.form = 3
            C_Container.GetContainerNumSlots = function(b) return b == 0 and 1 or 0 end
            C_Container.GetContainerItemID = function() return 929 end
            C_Item.GetItemSpell = function() return "Healing Potion" end
            C_Item.GetItemInfo = function() return "Healing Potion", nil, nil, nil, 12 end""")
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD", "BAG_UPDATE_DELAYED"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(6, 0.25))

        def sos():
            return next((v for k, v in macro_attrs(lua).items() if "os" in k.lower() and "sos" in k.lower()), "")
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        if "item:929" not in sos():
            p.append("a ready potion is not in G: %r" % sos())
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(2, 0.25))
        lua.execute("GetItemCooldown = function() return STUB.now - 10, 120, 1 end C_Container.GetItemCooldown = GetItemCooldown")
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        if "item:929" in sos():
            p.append("a potion on its cooldown is still in G: %r" % sos())
        return p

    @S.test("druid: Prowl on the bar becomes cat form + Prowl, once, out of combat")
    def _():
        p = []
        lua = new_lua()
        set_class(lua, "DRUID", 11, 23, druid_spells(23))
        lua.execute("STUB.buffs = {}")
        # the spellbook and a bar with Prowl in slot 5
        lua.execute("""STUB.book = {} local i = 0
            for id, name in pairs(STUB.names) do i = i + 1 STUB.book[i] = { name, 1, id } end
            STUB.bar[5] = 5215""")
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(4, 0.25))
        body = lua.eval('STUB.macros["OKD Prowl"]') or ""
        if "/cast [noform:3] Cat Form; [nostealth] Prowl" not in body:
            p.append("no OKD Prowl macro, or a wrong one: %r" % body)
        # a macro from an older version with the wrong stance number is put right
        lua.execute('STUB.macros["OKD Prowl"] = "#showtooltip Prowl\\n/cast [noform:9] Cat Form; [nostealth] Prowl"')
        p += lua_list(fire("SPELLS_CHANGED"))
        p += lua_list(tick(4, 0.25))
        body = lua.eval('STUB.macros["OKD Prowl"]') or ""
        if "[noform:3] Cat Form" not in body:
            p.append("an old OKD Prowl macro was not put right: %r" % body)
        if lua.eval("STUB.bar[5]") != "OKD Prowl":
            p.append("Prowl on the bar was not swapped: %r" % lua.eval("STUB.bar[5]"))
        for v in lua_list(lua.eval("STUB.violations")):
            p.append("taint: " + v)
        # put Prowl back by hand: the addon leaves it alone after that
        lua.execute("STUB.bar[5] = 5215")
        p += lua_list(fire("SPELLS_CHANGED"))
        p += lua_list(tick(4, 0.25))
        if lua.eval("STUB.bar[5]") != 5215:
            p.append("the addon swapped Prowl again after the player put it back")
        return p

    @S.test("druid: Prowl is swapped on a client without the old spellbook functions (21.11.)")
    def _():
        p = []
        lua = new_lua()
        set_class(lua, "DRUID", 11, 24, druid_spells(24))
        # the newer client: no GetSpellBookItemName / GetNumSpellTabs, only
        # C_SpellBook; and a second time with no spellbook at all
        lua.execute("""STUB.buffs = {} STUB.bar[5] = 5215
            GetSpellBookItemName, GetNumSpellTabs, GetSpellTabInfo = nil, nil, nil
            local ids = {} for id in pairs(STUB.names) do ids[#ids + 1] = id end
            C_SpellBook = {
              GetNumSpellBookSkillLines = function() return 1 end,
              GetSpellBookSkillLineInfo = function() return { itemIndexOffset = 0, numSpellBookItems = #ids } end,
              GetSpellBookItemName = function(i) return STUB.names[ids[i]], "Rank 1" end,
              GetSpellBookItemInfo = function(i) return { spellID = ids[i] } end }""")
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(4, 0.25))
        if lua.eval("STUB.bar[5]") != "OKD Prowl":
            p.append("C_SpellBook client: Prowl not swapped: %r" % lua.eval("STUB.bar[5]"))
        lua2 = new_lua()
        set_class(lua2, "DRUID", 11, 24, druid_spells(24))
        lua2.execute("STUB.buffs = {} STUB.bar[7] = 5215 GetSpellBookItemName, GetNumSpellTabs = nil, nil C_SpellBook = nil")
        ns2, errs = load_addon(lua2)
        p += errs
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(lua2.eval("STUB.fire")(e, "OneKeyDruid"))
        p += lua_list(lua2.eval("STUB.tick")(4, 0.25))
        if lua2.eval("STUB.bar[7]") != "OKD Prowl":
            p.append("no spellbook API: Prowl not swapped by its name: %r" % lua2.eval("STUB.bar[7]"))
        e = lua2.eval("STUB.slash")("prowlkey on")
        if e:
            p.append("/okd prowlkey on: " + e)
        return p

    @S.test("druid: in water F holds Aquatic Form, on land the fighting form again")
    def _():
        p = []
        lua = new_lua()
        set_class(lua, "DRUID", 11, 23, druid_spells(23))
        lua.execute('STUB.buffs = { ["Mark of the Wild"] = true, ["Thorns"] = true } STUB.form = 3')
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(4, 0.25))

        def main():
            return macro_attrs(lua).get("OneKeyDruidButton:macrotext", "")
        # the game decides by [swimming] when you press; the addon only sets it up
        want = ["/cast [swimming,noform:2] Aquatic Form", "/stopmacro [swimming]",
                "/cast [noswimming,form:2] Cat Form", "/stopmacro [form:2]"]
        if main().split("\n")[:4] != want:
            p.append("out of combat F does not start with the water lines: %r" % main()[:160])
        # in water the label says so (where the client tells)
        lua.execute("STUB.swimming = true")
        p += lua_list(tick(2, 0.25))
        if "Aquatic Form" not in (ns.DruidHud() or ""):
            p.append("in water the HUD says %r" % ns.DruidHud())
        if main().split("\n")[:2] != want[:2]:
            p.append("in water F holds %r" % main())
        # a secret or missing swim state: the macro still works
        lua.execute("STUB.swimming = STUB_secret()")
        p += lua_list(tick(2, 0.25))
        if main().split("\n")[:2] != want[:2]:
            p.append("with a secret swim state F holds %r" % main())
        lua.execute("STUB.swimming = false")
        # in combat nothing changes
        lua.execute("STUB.swimming = true STUB.combat = true")
        p += lua_list(tick(2, 0.25))
        for v in lua_list(lua.eval("STUB.violations")):
            p.append("taint: " + v)
        return p

    @S.test("hunter: in melee the HUD says Ctrl+F; Ctrl+F is Wing Clip, Mongoose, Raptor; no error voice")
    def _():
        p = []
        probe, _ = load_addon(new_lua(), ["Classes.lua"])
        CL = probe.CLASSES["HUNTER"]
        spells = {v[1]: v[2] for v in CL.spells.values()}
        lua = new_lua()
        set_class(lua, "HUNTER", 3, 20, spells)
        lua.execute("STUB.buffs = {}")
        ns, errs = load_addon(lua)
        p += errs
        fire, tick, slash = lua.eval("STUB.fire"), lua.eval("STUB.tick"), lua.eval("STUB.slash")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(4, 0.25))
        behind = ns.OneKeyMacros.behind or ""
        acts = [l for l in behind.split("\n") if l.startswith("/cast")]
        if len(acts) < 3 or "Wing Clip, null" not in acts[0] or "Raptor Strike" not in acts[-1]:
            p.append("Ctrl+F is %r" % behind)
        if lua.eval("STUB.cvars.Sound_EnableErrorSpeech") != "0":
            p.append("the spoken error stays on")
        lua.execute('STUB.targetName = "Venture Co. Operator" STUB.targetLevel = 20')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute('STUB.combat = true STUB.inRange = { ["Raptor Strike"] = false }')
        p += lua_list(tick(2, 0.25))
        if ns.OneKeyAlert():
            p.append("a melee hint at range: %r" % ns.OneKeyAlert())
        lua.execute('STUB.inRange = { ["Raptor Strike"] = true }')
        p += lua_list(tick(2, 0.25))
        if "Ctrl+F" not in (ns.OneKeyAlert() or ""):
            p.append("in melee the HUD says %r" % ns.OneKeyAlert())
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        e = slash("errorvoice on")
        if e:
            p.append(e)
        if lua.eval("STUB.cvars.Sound_EnableErrorSpeech") != "1":
            p.append("/okd errorvoice on did not bring the voice back")
        return p

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
            # still sounding a minute into the fight (22.11.: it stopped at 30 s)
            errs += lua_list(tick(60, 0.5))     # 40 s into the fight
            n = lua.eval("STUB.sounds")
            errs += lua_list(tick(40, 0.5))
            if lua.eval("STUB.sounds") <= n:
                errs.append("the alarm went quiet before the fight ended")
            return errs

    def mage_session(level, extra=(), drop=()):
        probe, _ = load_addon(new_lua(), ["Classes.lua"])
        CL = probe.CLASSES["MAGE"]
        allspells = {v[1]: (v[2], k) for k, v in CL.spells.items()}
        trained = {"fireball": 1, "frostarmor": 1, "frostbolt": 4, "ai": 6, "fireblast": 6, "water": 4, "food": 6,
                   "missiles": 8, "poly": 8, "nova": 10, "shoot": 1, "blink": 20, "cone": 26}
        for k in extra:
            trained[k] = 1
        for k in drop:
            trained.pop(k, None)
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

    @S.test("macro: mage opens with Fireball below level 15 and with Frostbolt from 15; no cooldown on F")
    def _():
        p = []
        for level in (1, 4, 6, 10, 14, 15, 20, 26, 40):
            lua, ns, errs, fire, tick = mage_session(level, ("icelance",) if level >= 20 else ())
            p += errs
            M = ns.OneKeyMacros
            fight, heal, behind = M.fight or "", M.heal or "", M.behind or ""
            casts = [l for l in fight.split("\n") if l.startswith("/cast")]
            if level < 4:
                if not casts or "Fireball" not in casts[0]:
                    p.append("level %d: Fireball is not the filler before Frostbolt: %r" % (level, casts[:1]))
            elif level < 15:
                # Fireball once per target, then only Frostbolt: the slow never lapses
                if "reset=target Fireball, null" not in fight or "Fireball" not in casts[0]:
                    p.append("level %d: Fireball is not a once-per-target opener: %r" % (level, fight))
                after = casts[1:]
                if not after or "Frostbolt" not in after[0]:
                    p.append("level %d: Frostbolt is not the filler after the opener: %r" % (level, fight))
                if any("Fireball" in l for l in after):
                    p.append("level %d: Fireball is cast again mid-fight (the slow can lapse)" % level)
            else:
                # the guides' frost opener: Frostbolt from the first press
                if "Fireball" in fight:
                    p.append("level %d: Fireball is still on F: %r" % (level, fight))
                if not casts or "Frostbolt" not in casts[0]:
                    p.append("level %d: the first spell is not Frostbolt: %r" % (level, casts[:1]))
            for cd in ("Fire Blast", "Frost Nova", "Cone of Cold", "Ice Lance", "Ice Barrier"):
                if cd in fight:
                    p.append("level %d: %s (a cooldown) is on F and can stop the macro" % (level, cd))
            if level >= 10 and not heal.startswith("/castsequence reset=10/combat Frost Nova, Frostbolt"):
                p.append("level %d: Shift+F is not Frost Nova, then Frostbolt, starting over after 10 s: %r" % (level, heal))
            if level >= 20 and not heal.endswith("Frost Nova, Frostbolt, Ice Lance"):
                p.append("level %d: Shift+F does not end Nova, Frostbolt with Ice Lance: %r" % (level, heal))
            if level >= 6 and "Fire Blast" not in behind:
                p.append("level %d: Ctrl+F has no Fire Blast: %r" % (level, behind))
            if "!Shoot" not in fight:
                p.append("level %d: no wand fallback on F" % level)
            for k in ("fight", "heal", "behind", "hide"):
                if len(M[k] or "") > MACRO_LIMIT:
                    p.append("level %d %s: %d chars" % (level, k, len(M[k])))
        return p

    @S.test("mage: Ice Barrier before the pull, once; a press that fails does not hold the key")
    def _():
        p = []
        lua, ns, errs, fire, tick = mage_session(40, ("icelance", "barrier", "icearmor", "magearmor"), drop=("water", "food"))
        p += errs
        lua.execute('STUB.buffs = { ["Arcane Intellect"] = true, ["Ice Armor"] = true }')
        lua.execute('STUB.cooldown["Ice Barrier"] = 30')
        lua.execute('STUB.targetName = "Dustwind Harpy" STUB.targetLevel = 40')
        main = lambda: macro_attrs(lua).get("OneKeyMain:macrotext", "")
        # Ice Armor is the armour kept up, not Mage Armor
        p += lua_list(tick(4, 0.25))
        if "Mage Armor" in main():
            p.append("F asks for Mage Armor with Ice Armor up: %r" % main())
        if main() != "/cast [@player] Ice Barrier":
            p.append("with an enemy picked and no barrier, F is not Ice Barrier: %r" % main())
        if (ns.OneKeyMacros.hide or "") != "/cast Ice Barrier":
            p.append("Ctrl+G is not Ice Barrier: %r" % ns.OneKeyMacros.hide)
        # the cast goes through: the buff is up, the key attacks
        p += lua_list(lua.eval("STUB.click")("OneKeyMain", True))
        lua.execute('STUB.buffs["Ice Barrier"] = true')
        p += lua_list(lua.eval("STUB.castDone")(11426))
        p += lua_list(tick(4, 0.25))
        if "Frostbolt" not in main():
            p.append("with the barrier up F does not attack: %r" % main())
        # the shield is gone and still cooling: no barrier line, the key attacks
        lua.execute('STUB.buffs["Ice Barrier"] = nil')
        p += lua_list(tick(4, 0.25))
        if "Frostbolt" not in main():
            p.append("with Ice Barrier on cooldown F does not attack: %r" % main())
        # cooldown over, but the press does nothing (no mana): one try, then attack
        p += lua_list(tick(140, 0.25))
        if main() != "/cast [@player] Ice Barrier":
            p.append("after the cooldown F is not Ice Barrier again: %r" % main())
        p += lua_list(lua.eval("STUB.click")("OneKeyMain", True))
        p += lua_list(tick(12, 0.25))
        if "Frostbolt" not in main():
            p.append("a barrier press that failed holds the key: %r" % main())
        # a new target: one more try
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(tick(2, 0.25))
        if main() != "/cast [@player] Ice Barrier":
            p.append("a new target does not get a new try: %r" % main())
        return p

    @S.test("hud: mage with five Frostbolts in is told to Cone of Cold (level 35), and to renew Ice Barrier")
    def _():
        p = []
        for level in (30, 35):
            lua, ns, errs, fire, tick = mage_session(level, ("icelance",))
            p += errs
            lua.execute('STUB.cooldown["Cone of Cold"] = 10')
            p += lua_list(fire("PLAYER_REGEN_DISABLED"))
            lua.execute("STUB.combat = true")
            done = lua.eval("STUB.castDone")
            for i in range(4):
                p += lua_list(done(116))
                p += lua_list(tick(8, 0.25))
            if ns.OneKeyAlert():
                p.append("level %d: a hint after four Frostbolts: %r" % (level, ns.OneKeyAlert()))
            p += lua_list(done(116))
            p += lua_list(tick(2, 0.25))
            a = ns.OneKeyAlert() or ""
            if level < 35:
                if a:
                    p.append("level %d: a Cone of Cold hint before Winter's Chill: %r" % (level, a))
                continue
            if "Cone of Cold" not in a or "Ctrl+F" not in a:
                p.append("no Cone of Cold hint at five casts: %r" % a)
            p += lua_list(done(120))
            p += lua_list(tick(2, 0.25))
            if ns.OneKeyAlert():
                p.append("the hint stays after Cone of Cold: %r" % ns.OneKeyAlert())
            # /okd cone off
            for i in range(5):
                p += lua_list(done(116))
            lua.eval("STUB.slash")("cone off")
            p += lua_list(tick(50, 0.25))
            if ns.OneKeyAlert():
                p.append("a hint with /okd cone off: %r" % ns.OneKeyAlert())
        # Frigid Power lasts a minute: a hint to cast Ice Barrier again
        lua, ns, errs, fire, tick = mage_session(40, ("icelance", "barrier"))
        p += errs
        lua.execute('STUB.buffs["Ice Barrier"] = true STUB.cooldown["Ice Barrier"] = 30')
        p += lua_list(lua.eval("STUB.castDone")(11426))
        p += lua_list(tick(4, 0.25))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true")
        p += lua_list(tick(80, 0.25))
        if ns.OneKeyAlert():
            p.append("an Ice Barrier hint 20 s after the cast: %r" % ns.OneKeyAlert())
        p += lua_list(tick(160, 0.25))
        a = ns.OneKeyAlert() or ""
        if "Ice Barrier" not in a or "Ctrl+G" not in a:
            p.append("no Ice Barrier hint a minute after the cast: %r" % a)
        return p

    @S.test("macro: rogue chains the stuns (Cheap Shot, Kidney Shot, Gouge)")
    def _():
        p = []
        probe, _ = load_addon(new_lua(), ["Classes.lua"])
        CL = probe.CLASSES["ROGUE"]
        allspells = {v[1]: (v[2], k) for k, v in CL.spells.items()}
        trained = {"ss": 1, "evis": 1, "stealth": 1, "cs": 26, "gouge": 6, "kick": 12, "evasion": 8,
                   "sprint": 10, "vanish": 22, "kidney": 30, "ambush": 18, "snd": 10, "throw": 1}
        for level in (6, 26, 30, 40):
            spells = {sid: name for sid, (name, k) in allspells.items() if trained.get(k, 99) <= level}
            lua = new_lua()
            set_class(lua, "ROGUE", 4, level, spells)
            lua.execute("STUB.buffs = {}")
            ns, errs = load_addon(lua)
            p += errs
            fire = lua.eval("STUB.fire")
            for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
                p += lua_list(fire(e, "OneKeyDruid"))
            p += lua_list(lua.eval("STUB.tick")(2, 0.25))
            fight = ns.OneKeyMacros.fight or ""
            seq = next((l for l in fight.split("\n") if l.startswith("/castsequence")), "")
            if level >= 26 and "[stealth,harm,nodead] Cheap Shot" not in fight:
                p.append("level %d: no Cheap Shot opener from stealth" % level)
            if level >= 30:
                if not re.search(r"Sinister Strike, Kidney Shot, Sinister Strike, Gouge, .*Eviscerate$", seq):
                    p.append("level %d: the stun chain is wrong: %r" % (level, seq))
            elif "Gouge" not in seq or "Eviscerate" not in seq:
                p.append("level %d: no Gouge and finisher in the chain: %r" % (level, seq))
            if len(fight) > MACRO_LIMIT:
                p.append("level %d: %d chars" % (level, len(fight)))
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
                "Shred", "Ravage", "Backstab", "Ambush", "Overpower", "Execute", "Thunder Clap",
                "Judgement", "Earth Shock", "/use [combat]")

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

    @S.test("warlock: DoTs once, then the wand; Shadow Bolt only with no wand; a press keeps Drain Life")
    def _():
        p = []
        probe, _ = load_addon(new_lua(), ["Classes.lua"])
        spells = {v[1]: v[2] for v in probe.CLASSES["WARLOCK"].spells.values()}
        for wand in (True, False):
            lua = new_lua()
            set_class(lua, "WARLOCK", 9, 30, spells)
            lua.execute("STUB.buffs = {} STUB.wand = %s" % ("true" if wand else "false"))
            ns, errs = load_addon(lua)
            p += errs
            fire = lua.eval("STUB.fire")
            for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
                p += lua_list(fire(e, "OneKeyDruid"))
            p += lua_list(lua.eval("STUB.tick")(4, 0.25))
            f = ns.OneKeyMacros.fight or ""
            acts = [l for l in f.split("\n") if l.startswith(("/cast", "/use"))]
            for dot in ("Corruption", "Curse of Agony", "Siphon Life"):
                if not any(dot in l and l.startswith("/castsequence") and l.endswith("null") for l in acts):
                    p.append("wand=%s: %s is not cast once per target: %r" % (wand, dot, f))
            if "Immolate" in f:
                p.append("Immolate costs too much mana for F: %r" % f)
            last = acts[-1] if acts else ""
            if wand and ("!Shoot" not in last or "Shadow Bolt" in f):
                p.append("with a wand the filler must be the wand, last: %r" % f)
            if not wand and ("Shadow Bolt" not in last or "Shoot" in f):
                p.append("with no wand the filler must be Shadow Bolt: %r" % f)
            for l in acts:
                if "nochanneling" not in l:
                    p.append("%r would cut Drain Life short" % l)
            if "Drain Life" not in (ns.OneKeyMacros.heal or "") or "Life Tap" not in (ns.OneKeyMacros.free or ""):
                p.append("Drain Life on Shift+F and Life Tap on Shift+G expected")
            if "Immolate" not in (ns.OneKeyMacros.behind or ""):
                p.append("Ctrl+F burst lost Immolate")
        return p

    @S.test("warrior: F is Rend once and Heroic Strike; Overpower and Execute on their own keys")
    def _():
        p = []
        probe, _ = load_addon(new_lua(), ["Classes.lua"])
        spells = {v[1]: v[2] for v in probe.CLASSES["WARRIOR"].spells.values()}
        lua = new_lua()
        set_class(lua, "WARRIOR", 1, 30, spells)
        lua.execute("STUB.buffs = {}")
        ns, errs = load_addon(lua)
        p += errs
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(lua.eval("STUB.fire")(e, "OneKeyDruid"))
        p += lua_list(lua.eval("STUB.tick")(4, 0.25))
        M = ns.OneKeyMacros
        f = M.fight or ""
        if "Overpower" in f or "Execute" in f:
            p.append("a spell that is mostly unusable is on F: %r" % f)
        if "Rend, null" not in f or "!Heroic Strike" not in f:
            p.append("F lacks Rend once or Heroic Strike: %r" % f)
        if "Overpower" not in (M.behind or "") or "Execute" not in (M.heal or ""):
            p.append("Overpower on Ctrl+F and Execute on Shift+F expected: %r / %r" % (M.behind, M.heal))
        if "Bloodrage" not in (M.free or ""):
            p.append("Bloodrage on Shift+G expected: %r" % M.free)
        return p

    @S.test("priest: Shadow Word: Pain once, then the wand; Smite only with no wand")
    def _():
        p = []
        probe, _ = load_addon(new_lua(), ["Classes.lua"])
        spells = {v[1]: v[2] for v in probe.CLASSES["PRIEST"].spells.values()}
        for wand in (True, False):
            lua = new_lua()
            set_class(lua, "PRIEST", 5, 24, spells)
            lua.execute("STUB.buffs = {} STUB.wand = %s" % ("true" if wand else "false"))
            ns, errs = load_addon(lua)
            p += errs
            for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
                p += lua_list(lua.eval("STUB.fire")(e, "OneKeyDruid"))
            p += lua_list(lua.eval("STUB.tick")(4, 0.25))
            f = ns.OneKeyMacros.fight or ""
            acts = [l for l in f.split("\n") if l.startswith(("/cast", "/use"))]
            if not acts or "Shadow Word: Pain, null" not in acts[0]:
                p.append("wand=%s: Shadow Word: Pain not first, once: %r" % (wand, f))
            last = acts[-1] if acts else ""
            if wand and ("!Shoot" not in last or "Smite" in f or "Mind Flay" in f):
                p.append("with a wand the filler must be the wand: %r" % f)
            if not wand and ("Smite" not in f or "Shoot" in f):
                p.append("with no wand Smite is the filler: %r" % f)
            if f.count("Shoot") > 1:
                p.append("the wand twice: %r" % f)
        return p

    @S.test("log: every class writes the session log the analyzer reads (no player names)")
    def _():
        p = []
        probe, _ = load_addon(new_lua(), ["Classes.lua"])
        spells = {v[1]: v[2] for v in probe.CLASSES["WARLOCK"].spells.values()}
        lua = new_lua()
        set_class(lua, "WARLOCK", 9, 20, spells)
        lua.execute("STUB.buffs = {}")
        ns, errs = load_addon(lua)
        p += errs
        fire, tick, click = lua.eval("STUB.fire"), lua.eval("STUB.tick"), lua.eval("STUB.click")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(4, 0.25))
        lua.execute('STUB.targetName = "Defias Pillager" STUB.targetLevel = 20')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true")
        for _ in range(3):
            p += lua_list(click("OneKeyMain", True))
        p += lua_list(lua.eval("STUB.castDone")(172))
        p += lua_list(fire("UNIT_COMBAT", "player", "WOUND", "", 10, 1))
        p += lua_list(tick(8, 0.25))
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(fire("PLAYER_LEVEL_UP", 21))
        lines = lua_list(ns.OneKeyLog())
        codes = [l.split("|")[1] for l in lines]
        for c in ("S", "T", "C+", "P", "A", "C-", "L"):
            if c not in codes:
                p.append("no %s line in %r" % (c, lines))
        if not any(l.split("|")[1:3] == ["P", "fight"] and l.endswith("|3") for l in lines):
            p.append("three fight presses not one P line: %r" % lines)
        if not any(l.split("|")[1:3] == ["A", "Corruption"] for l in lines):
            p.append("the cast is not logged: %r" % lines)
        cm = [l for l in lines if "|C-|" in l]
        if cm and cm[0].split("|")[4] != "1":
            p.append("the hit is not counted: %r" % cm)
        # another player as the target: the name stays out
        lua.execute('STUB.targetIsPlayer = true STUB.targetName = "Someone"')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        if any("Someone" in l for l in lua_list(ns.OneKeyLog())):
            p.append("a player's name in the log")
        e = lua.eval("STUB.slash")("log off")
        if e or lua.eval("OneKeyDruidDB.log"):
            p.append("/okd log off: %r" % e)
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
