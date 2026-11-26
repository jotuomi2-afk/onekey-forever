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
    2383: ("Find Herbs", 1), 1850: ("Dash", 26), 779: ("Swipe", 16),
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


def druid_macros(lua, ns, level, mode, selfcast=True, mana=None, extra="", forms="{B=1,A=2,C=3}"):
    """The druid macros at a level, with every spell and talent known
    (Feral Charge included), as Logic.BuildMacros makes them."""
    N = lua.eval("""{bear="Bear Form",cat="Cat Form",ht="Healing Touch",rejuv="Rejuvenation",regrowth="Regrowth",
     grasp="Nature's Grasp",bash="Bash",maul="Maul",wrath="Wrath",moonfire="Moonfire",roots="Entangling Roots",
     enrage="Enrage",roar="Demoralizing Roar",claw="Claw",rip="Rip",rake="Rake",shred="Shred",prowl="Prowl",
     ff="Faerie Fire (Feral)",fb="Ferocious Bite",ravage="Ravage",pounce="Pounce",tf="Tiger's Fury",
     hibernate="Hibernate",thorns="Thorns",motw="Mark of the Wild",direbear="Dire Bear Form",
     charge="Feral Charge - Cat",chargeBear="Feral Charge",travel="Travel Form",shadowmeld="Shadowmeld",dash="Dash",swipe="Swipe"}""")
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
    o = ns.Logic.BuildMacros(kn, N, lua.eval(forms), mode, cfg,
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
        # Forever has no powershifting: the key swaps forms. In a fight it is one
        # way, into the bear, and as a bear it hits (pressed 69 times on 24.11.)
        if free.strip().split("\n") != ["/startattack [combat]",
                "/cast [combat,noform:1] Bear Form; [combat] Swipe; [nocombat,form:3] Bear Form; [nocombat] Cat Form",
                "/cast [combat,form:1] !Maul"]:
            p.append("break-free key: in a fight the bear and then its hit, out of a fight the swap: %r" % free)
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

    @S.test("druid: Alt+G runs - the cat and then Dash when Dash is ready as the fight starts, else Travel Form or the cat")
    def _():
        p = []
        lua = new_lua()
        nsl, _ = load_addon(lua, ["Logic.lua"])
        o = druid_macros(lua, nsl, 30, "cat", forms="{B=1,A=2,C=3,T=4}")
        if (o.run or "").split("\n") != ["/cast [noform:3] Cat Form", "/cast [form:3] Dash"]:
            p.append("Alt+G with Dash is %r" % o.run)
        if o.runSlow != "/cast [outdoors,noform:4] Travel Form; [indoors,noform:3] Cat Form":
            p.append("Alt+G without Dash at 30 is %r" % o.runSlow)
        o = druid_macros(lua, nsl, 24, "cat")
        if o.run or o.runSlow != "/cast [noform:3] Cat Form":
            p.append("level 24 (no Dash, no Travel Form): %r / %r" % (o.run, o.runSlow))
        o = druid_macros(lua, nsl, 14, "bear")
        if o.run or o.runSlow:
            p.append("a druid with no cat form has a run key: %r / %r" % (o.run, o.runSlow))
        for lvl in (26, 30, 40):
            o = druid_macros(lua, nsl, lvl, "cat", forms="{B=1,A=2,C=3,T=4}")
            for m in (o.run, o.runSlow):
                if "Dash" in m.split("\n")[0] or len(m) > 255 or "Nature" in m or "item:" in m:
                    p.append("level %d: something that can fail stands before the form, or too long: %r" % (lvl, m))
        # in the client: bound to Alt+G, and the Dash variant only when Dash is ready
        lua = new_lua()
        set_class(lua, "DRUID", 11, 27, druid_spells(27))
        lua.execute('STUB.buffs = { ["Mark of the Wild"] = true, ["Thorns"] = true } STUB.form = 3')
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(6, 0.25))
        for cmd in ("bind F", "sos G"):
            lua.eval("STUB.slash")(cmd)
        if lua.eval('STUB.bindings["ALT-G"]') != "OneKeyDruidRun":
            p.append("Alt+G is bound to %r; keys %r" % (lua.eval('STUB.bindings["ALT-G"]'), sorted(str(k) for k in lua.eval("STUB.bindings").keys())))
        run = lambda: macro_attrs(lua).get("OneKeyDruidRun:macrotext", "")
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        if "Dash" not in run():
            p.append("Dash is ready and not on Alt+G: %r" % run())
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        lua.execute('STUB.cds = STUB.cds or {} STUB.cds["Dash"] = { start = STUB.now, dur = 300 }')
        p += lua_list(tick(2, 0.25))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        if "Dash" in run() or "Cat Form" not in run():
            p.append("Dash on its cooldown as the fight starts is still on Alt+G: %r" % run())
        # an elite in the fight: the HUD names the run key
        lua.execute('STUB.combat = true STUB.targetClass = "elite" STUB.targetName = "Blackrock Sentry" STUB.targetLevel = 22 STUB.shown = {}')
        p += lua_list(tick(4, 0.25))
        if not any("ELITE: Alt+G runs" in t for t in lua_list(lua.eval("STUB.shown"))):
            p.append("an elite in the fight and no hint to run: %r" % lua_list(lua.eval("STUB.shown"))[-4:])
        shown = lambda: lua_list(lua.eval("STUB.shown"))
        lua.execute('STUB.targetClass = "normal" STUB.shown = {}')
        p += lua_list(tick(4, 0.25))
        if any("ELITE" in t for t in shown()):
            p.append("the elite hint stays on an ordinary mob")
        # a secret answer names no key and raises nothing; nor does a friendly elite
        lua.execute('STUB.targetClass = STUB_secret() STUB.shown = {}')
        p += lua_list(tick(4, 0.25))
        lua.execute('STUB.targetClass = "elite" local ca = UnitCanAttack UnitCanAttack = function() return false end STUB.ca = ca')
        p += lua_list(tick(4, 0.25))
        if any("ELITE" in t for t in shown()):
            p.append("the elite hint from a secret answer or on a friendly target")
        lua.execute("UnitCanAttack = STUB.ca")
        # after the first seconds the elite hint gives way
        p += lua_list(tick(40, 0.25))
        lua.execute("STUB.shown = {}")
        p += lua_list(tick(4, 0.25))
        if any("ELITE" in t for t in shown()):
            p.append("the elite hint still covers the other hints ten seconds into the fight")
        # three attackers: the HUD names both keys, in both languages
        lua.execute("""STUB.targetClass = "normal" STUB.shown = {}
            C_NamePlate.GetNamePlates = function()
              local t = {} for i = 1, 3 do t[i] = { namePlateUnitToken = "nameplate" .. i } end return t end
            local ca = UnitCanAttack
            UnitCanAttack = function(a, b) if tostring(b):find("^nameplate") then return true end return ca(a, b) end
            UnitThreatSituation = function() return 3 end UnitAffectingCombat = function() return true end""")
        p += lua_list(tick(4, 0.25))
        if not any("3 ENEMIES: Alt+G runs (G to stand)" in t for t in shown()):
            p.append("three attackers and no hint to run: %r" % shown()[-3:])
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        lua.eval("STUB.slash")("lang fi")
        lua.execute("STUB.combat = true STUB.shown = {}")
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        p += lua_list(tick(4, 0.25))
        if not any("3 VIHOLLISTA: Alt+G pakenee (G kestää)" in t for t in shown()):
            p.append("the Finnish hint with three attackers: %r" % shown()[-3:])
        # cooldowns the client keeps secret: Dash is counted from the player's own cast
        lua.execute("""STUB.combat = false
            C_Spell.GetSpellCooldown = function() return { startTime = STUB_secret(), duration = STUB_secret() } end""")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(1300, 0.25))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        if "Dash" not in run():
            p.append("secret cooldowns and no Dash cast for five minutes: Dash is not on Alt+G: %r" % run())
        p += lua_list(lua.eval("STUB.castDone")(1850))
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(8, 0.25))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        if "Dash" in run():
            p.append("secret cooldowns: Dash was cast seconds ago and is on Alt+G again: %r" % run())
        p += lua_list(lua.eval("STUB.violations") and lua_list(lua.eval("STUB.violations")) or [])
        return p

    @S.test("druid: Rip and the Bite take turns on ordinary mobs, the log notes which ran, and the analyser compares them")
    def _():
        p = []
        lua = new_lua()
        nsl, _ = load_addon(lua, ["Logic.lua"])
        for lvl in (28, 32, 40):
            o = druid_macros(lua, nsl, lvl, "cat")
            a = [l for l in o.fight.split("\n") if l.startswith("/castsequence [form:3]")]
            b = [l for l in (o.fightBite or "").split("\n") if l.startswith("/castsequence [form:3]")]
            if not a or not b:
                p.append("level %d: no second finisher plan: %r" % (lvl, o.fightBite))
                continue
            if "Rip" not in a[0] or "Rip" in b[0] or b[0].count("Ferocious Bite") != 1:
                p.append("level %d: the plans are not Rip and the Bite: %r / %r" % (lvl, a[0], b[0]))
            if not b[0].endswith("Rake, Claw, Claw, Claw, Ferocious Bite") or "Faerie Fire" not in b[0].split(",")[0]:
                p.append("level %d: the Bite plan is not Faerie Fire, Rake, Claws, the Bite: %r" % (lvl, b[0]))
            if len(o.fightBite) > 255 or o.fightBite.replace(b[0], "") != o.fight.replace(a[0], ""):
                p.append("level %d: the Bite plan differs from the Rip plan in more than the sequence, or is too long" % lvl)
        # a cat that went bear in the fight: F hits there too (Swipe; Maul before
        # Swipe is learned), on the Wrath line, and the Wrath pull stays
        for lvl in (20, 24, 28, 32, 36, 40):
            for sc in (True, False):
                o = druid_macros(lua, nsl, lvl, "cat", selfcast=sc)
                hit = [l for l in o.fight.split("\n") if "[form:1] Swipe" in l]
                if len(hit) != 1 or "Wrath" not in o.fight or len(o.fight) > 255:
                    p.append("level %d selfcast %s: a bear has no Swipe on F, or the Wrath pull fell out: %r" % (lvl, sc, o.fight))
                if o.fightBite and "[form:1] Swipe" not in o.fightBite:
                    p.append("level %d: the Bite plan has no Swipe for the bear" % lvl)
        if "[form:1] !Maul" not in druid_macros(lua, nsl, 12, "cat").fight and druid_macros(lua, nsl, 12, "cat").fight.count("Maul"):
            p.append("level 12: Maul for the bear is not bound to the bear form")
        if druid_macros(lua, nsl, 22, "cat").fightBite or druid_macros(lua, nsl, 30, "bear").fightBite:
            p.append("a second plan without both finishers, or for the bear")
        # in the client
        lua = new_lua()
        set_class(lua, "DRUID", 11, 28, druid_spells(28))
        lua.execute('STUB.buffs = { ["Mark of the Wild"] = true, ["Thorns"] = true } STUB.form = 3 STUB.targetName = "Wolf" STUB.targetLevel = 27 STUB.targetClass = "normal"')
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        lua.eval("STUB.slash")("log on")
        p += lua_list(tick(6, 0.25))
        main = lambda: macro_attrs(lua).get("OneKeyDruidButton:macrotext", "")
        plan = lambda t: "B" if "Rip" not in t and "Ferocious Bite" in t else "A"
        # the comparison is over (26.11.): Rip unless the test is asked for
        if plan(main()) != "A":
            p.append("with nothing set the key does not hold the Rip plan")
        lua.eval("STUB.slash")("finisher test")
        p += lua_list(tick(6, 0.25))

        def fight():
            p.extend(lua_list(tick(2, 0.25)))
            before = main()
            # as in the client: the event comes before the lockdown
            p.extend(lua_list(fire("PLAYER_REGEN_DISABLED")))
            lua.execute("STUB.combat = true")
            during = main()
            lua.execute("STUB.combat = false")
            p.extend(lua_list(fire("PLAYER_REGEN_ENABLED")))
            seq = lambda t: [l for l in t.split("\n") if l.startswith("/castsequence [form:3]")]
            if seq(before) and seq(before) != seq(during):
                p.append("the pull and the fight hold different sequences (the sequence would start twice): %r / %r" % (seq(before), seq(during)))
            return plan(during)

        got = [fight() for _ in range(4)]
        if sorted(got[:2]) != ["A", "B"] or got[:2] != got[2:]:
            p.append("the plans do not take turns: %r" % got)
        notes = lambda: [l.split("|")[6] for l in lua_list(lua.eval("OneKeyDruidDB.lines")) if l.split("|")[1] == "C+"]
        if notes() != got:
            p.append("the log notes %r, the key held %r" % (notes(), got))
        # no target as the fight starts (a mob came to you): still the turn's plan
        lua.execute("STUB.targetName = nil")
        if sorted([fight(), fight()]) != ["A", "B"]:
            p.append("with no target the plans do not take turns")
        lua.execute('STUB.targetName = "Wolf"')
        lua.execute('STUB.targetClass = "elite"')
        if [fight(), fight()] != ["A", "A"]:
            p.append("an elite gets the Bite plan")
        lua.execute('STUB.targetClass = "normal" STUB.targetLevel = 30')
        if [fight(), fight()] != ["A", "A"]:
            p.append("a mob two levels above gets the Bite plan")
        lua.execute("STUB.targetLevel = 27")
        lua.eval("STUB.slash")("finisher bite")
        if [fight(), fight()] != ["B", "B"]:
            p.append("/okd finisher bite does not hold the Bite")
        lua.eval("STUB.slash")("finisher rip")
        if [fight(), fight()] != ["A", "A"]:
            p.append("/okd finisher rip does not hold Rip")
        # forced plans are noted with a small letter and stay out of the comparison
        if notes()[6:] != ["a", "a", "a", "a", "b", "b", "a", "a"]:
            p.append("forced plans are not noted apart: %r" % notes()[6:])
        # the analyser
        import importlib.util
        spec = importlib.util.spec_from_file_location("analyze_log", os.path.join(ROOT, "tools", "analyze_log.py"))
        al = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(al)

        def session(n, dps_a, dps_b, kind="normal", form="cat"):
            e, t = [["0.0", "S", "1", "28"]], 1.0
            for i in range(n):
                for plan_, dps in (("A", dps_a), ("B", dps_b)):
                    e += [[str(t), "C+", "Wolf", str(25 + i % 2), kind, form, plan_], [str(t + 15), "C-", "15", "100", "5", "1"],
                          [str(t + 16), "M", str(dps * 15), "100", "0", "1000"]]
                    t += 20
            return e

        r = al.finisher_test([session(25, 60, 70)])
        if r["A"]["fights"] != 25 or r["B"]["dps"] != 70 or "B (the Bite) is ahead" not in r["verdict"]:
            p.append("the analyser does not see the Bite ahead: %r" % r)
        forced = [[x if i != 6 else x.lower() for i, x in enumerate(l)] for l in session(40, 200, 10)]
        mixed = al.finisher_test([session(25, 60, 70), forced])
        if mixed["A"]["fights"] != 25 or "B (the Bite) is ahead" not in mixed["verdict"]:
            p.append("forced fights (small letters) are counted: %r" % mixed)
        if "not enough" not in al.finisher_test([session(5, 60, 90)])["verdict"]:
            p.append("ten fights decide the comparison")
        if "no clear difference" not in al.finisher_test([session(25, 60, 61)])["verdict"]:
            p.append("a 2 % difference is called a winner")
        if al.finisher_test([session(25, 60, 70, kind="elite")])["A"]["fights"] or al.finisher_test([session(25, 60, 70, form="none")])["B"]["fights"]:
            p.append("elite fights or fights started out of the cat are counted")
        return p

    @S.test("druid: the warnings are shown big, in the middle of the screen")
    def _():
        p = []
        lua = new_lua()
        set_class(lua, "DRUID", 11, 28, druid_spells(28))
        lua.execute('STUB.buffs = { ["Mark of the Wild"] = true, ["Thorns"] = true } STUB.form = 3 STUB.targetName = "Ogre" STUB.targetLevel = 27 STUB.targetClass = "elite"')
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        for cmd in ("bind F", "sos G"):
            lua.eval("STUB.slash")(cmd)
        p += lua_list(tick(6, 0.25))
        big = lambda: ns.DruidAlert() or ""
        sizes = lua_list(lua.eval("STUB.fontSizes or {}"))
        if not any(s >= 30 for s in sizes):
            p.append("no text of 30 points or more is made: %r" % sizes)
        lua.execute("STUB.combat = true")
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        p += lua_list(tick(2, 0.25))
        if "ELITE: Alt+G runs" not in big():
            p.append("an elite in the fight, the big text says %r" % big())
        lua.execute('STUB.targetClass = "normal"')
        p += lua_list(tick(40, 0.25))
        if big():
            p.append("an ordinary fight and the big text says %r" % big())
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(2, 0.25))
        if big():
            p.append("out of the fight the big text stays: %r" % big())
        # in Prowl with an enemy picked: where the opener is
        lua.execute('STUB.buffs["Prowl"] = true')
        p += lua_list(tick(2, 0.25))
        if "Ctrl+F = Shred" not in big():
            p.append("in Prowl with an enemy picked the big text says %r (HUD %r)" % (big(), ns.DruidHud()))
        # the HUD switched off takes the big text with it
        lua.eval("STUB.slash")("hud off")
        p += lua_list(tick(2, 0.25))
        if big():
            p.append("/okd hud off leaves the big text on: %r" % big())
        lua.eval("STUB.slash")("hud on")
        p += lua_list(tick(2, 0.25))
        lua.eval("STUB.slash")("alert 0")
        p += lua_list(tick(2, 0.25))
        if big():
            p.append("/okd alert 0 leaves the big text on: %r" % big())
        lua.eval("STUB.slash")("alert 40")
        p += lua_list(tick(2, 0.25))
        if "Shred" not in big() or 40 not in lua_list(lua.eval("STUB.fontSizes")):
            p.append("/okd alert 40 does not bring the big text back at that size")
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
        want = ["/cast [swimming,noharm,noform:2][swimming,dead,noform:2] Aquatic Form", "/stopmacro [swimming,noharm][swimming,dead]",
                "/cast [noswimming,form:2] Cat Form", "/stopmacro [noswimming,form:2]"]
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
        # fighting in the water (owner, 24.11.): with a living enemy as the target
        # the HUD does not send you into Aquatic Form; with its corpse it does again
        lua.execute('STUB.swimming = true STUB.targetName = "Murloc" STUB.targetLevel = 20')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(tick(2, 0.25))
        if "Aquatic Form" in (ns.DruidHud() or ""):
            p.append("an enemy as the target in the water and the HUD says %r" % ns.DruidHud())
        # in Aquatic Form with a living enemy: F is the fighting form first
        lua.execute("STUB.form = 2")
        p += lua_list(fire("UPDATE_SHAPESHIFT_FORM"))
        p += lua_list(tick(2, 0.25))
        if main().split("\n")[-1] != "/cast [form:2] Cat Form" or "Cat Form" not in (ns.DruidHud() or ""):
            p.append("Aquatic Form and an enemy: F holds %r, the HUD says %r" % (main()[-60:], ns.DruidHud()))
        if len(main()) > 255:
            p.append("the water macro is %d characters" % len(main()))
        lua.execute("STUB.form = 3")
        p += lua_list(fire("UPDATE_SHAPESHIFT_FORM"))
        # a secret answer about the target: the land logic, not a key that does nothing
        lua.execute("local ca = UnitCanAttack STUB.ca2 = ca UnitCanAttack = function(a, b) if b == 'target' then return STUB_secret() end return ca(a, b) end")
        p += lua_list(tick(2, 0.25))
        if main().strip() in ("", "\n".join(want[:2])) or "Aquatic Form" in (ns.DruidHud() or ""):
            p.append("a secret target answer in the water leaves F with %r (HUD %r)" % (main()[:80], ns.DruidHud()))
        lua.execute("UnitCanAttack = STUB.ca2")
        lua.execute("UnitIsDead = function(u) return u == 'target' end")
        p += lua_list(tick(2, 0.25))
        if "Aquatic Form" not in (ns.DruidHud() or ""):
            p.append("a corpse as the target in the water and the HUD says %r" % ns.DruidHud())
        lua.execute("UnitIsDead = function() return false end STUB.targetName = nil STUB.swimming = false")
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
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

    @S.test("interrupt: the target casts, the mage's HUD names Counterspell's key until the cast ends or it is cast")
    def _():
        lua, ns, p, fire, tick = mage_session(30, ("cs",))
        lua.execute('STUB.targetName = "Defias Wizard" STUB.targetLevel = 30')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true")
        p += lua_list(tick(2, 0.25))
        if "Counterspell" in (ns.OneKeyAlert() or ""):
            p.append("no cast yet, the HUD says %r" % ns.OneKeyAlert())
        p += lua_list(fire("UNIT_SPELLCAST_START", "player", "x", 116))
        p += lua_list(tick(1, 0.25))
        if "Counterspell" in (ns.OneKeyAlert() or ""):
            p.append("the player's own cast counts as the target's: %r" % ns.OneKeyAlert())
        p += lua_list(fire("UNIT_SPELLCAST_START", "target", "x", 133))
        p += lua_list(tick(1, 0.25))
        t = ns.OneKeyAlert() or ""
        if "Counterspell" not in t or "Shift+G" not in t:
            p.append("the target casts, the HUD says %r" % t)
        p += lua_list(fire("UNIT_SPELLCAST_STOP", "target", "x", 133))
        p += lua_list(tick(1, 0.25))
        if "Counterspell" in (ns.OneKeyAlert() or ""):
            p.append("the cast ended, the hint stays: %r" % ns.OneKeyAlert())
        # a cast nobody stops ends by itself (no stop event seen)
        p += lua_list(fire("UNIT_SPELLCAST_START", "target", "x", 133))
        p += lua_list(tick(60, 0.25))
        if "Counterspell" in (ns.OneKeyAlert() or ""):
            p.append("15 s after a cast began the hint stays: %r" % ns.OneKeyAlert())
        # Counterspell cast: 30 s without the hint
        p += lua_list(lua.eval("STUB.castDone")(2139))
        p += lua_list(fire("UNIT_SPELLCAST_START", "target", "x", 133))
        p += lua_list(tick(1, 0.25))
        if "Counterspell" in (ns.OneKeyAlert() or ""):
            p.append("Counterspell on cooldown is named: %r" % ns.OneKeyAlert())
        p += lua_list(fire("UNIT_SPELLCAST_STOP", "target", "x", 133))
        p += lua_list(tick(140, 0.25))
        A = lambda: "Counterspell" in (ns.OneKeyAlert() or "")
        # what the client says about the cast, in plain values: its end ...
        lua.execute('STUB.targetCast = { "Fireball", (STUB.now + 2) * 1000, false }')
        p += lua_list(fire("UNIT_SPELLCAST_START", "target", "x", 133))
        p += lua_list(tick(4, 0.25))
        if not A():
            p.append("one second into a two second cast the hint is gone")
        p += lua_list(tick(8, 0.25))
        if A():
            p.append("the cast's own end has passed and the hint stays")
        # ... and that it cannot be interrupted: no key
        lua.execute('STUB.targetCast = { "Shielded Bolt", (STUB.now + 3) * 1000, true }')
        p += lua_list(fire("UNIT_SPELLCAST_START", "target", "x", 133))
        p += lua_list(tick(1, 0.25))
        if A():
            p.append("a cast that cannot be interrupted is named")
        lua.execute('STUB.targetCast = nil STUB.targetChannel = { "Shielded Drain", (STUB.now + 3) * 1000, true }')
        p += lua_list(fire("UNIT_SPELLCAST_CHANNEL_START", "target", "x", 133))
        p += lua_list(tick(1, 0.25))
        if A():
            p.append("a channel that cannot be interrupted is named")
        # secret answers: nothing is compared, the guess stands
        lua.execute('STUB.targetChannel = nil STUB.targetCast = { STUB_secret(), STUB_secret(), STUB_secret() }')
        p += lua_list(fire("UNIT_SPELLCAST_START", "target", "x", 133))
        p += lua_list(tick(1, 0.25))
        if not A():
            p.append("a cast with secret details is not named")
        p += lua_list(fire("UNIT_SPELLCAST_STOP", "target", "x", 133))
        # a channel says "succeeded" as it begins and goes on
        lua.execute('STUB.targetCast = nil STUB.targetChannel = { "Drain Life", (STUB.now + 5) * 1000, false }')
        p += lua_list(fire("UNIT_SPELLCAST_CHANNEL_START", "target", "x", 689))
        p += lua_list(fire("UNIT_SPELLCAST_SUCCEEDED", "target", "x", 689))
        p += lua_list(tick(1, 0.25))
        if not A():
            p.append("a channel loses its hint at its own start")
        p += lua_list(fire("UNIT_SPELLCAST_CHANNEL_STOP", "target", "x", 689))
        # a new target in the middle of a cast
        lua.execute('STUB.targetChannel = nil STUB.targetCast = { "Fireball", (STUB.now + 2) * 1000, false }')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(tick(1, 0.25))
        if not A():
            p.append("a target picked in the middle of its cast is not named")
        lua.execute('STUB.targetCast = nil')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(tick(1, 0.25))
        if A():
            p.append("a new target that is not casting is named")
        e = lua.eval("STUB.slash")("interrupt off")
        if e:
            p.append("/okd interrupt off: %s" % e)
        p += lua_list(tick(140, 0.25))
        p += lua_list(fire("UNIT_SPELLCAST_START", "target", "x", 133))
        p += lua_list(tick(1, 0.25))
        if "Counterspell" in (ns.OneKeyAlert() or ""):
            p.append("/okd interrupt off, the hint shows: %r" % ns.OneKeyAlert())
        return p

    @S.test("interrupt: the target casts, the druid is told Alt+F (as a cat twice: the bear, then Bash); not for a minute after Bash")
    def _():
        p = []
        lua = new_lua()
        set_class(lua, "DRUID", 11, 30, druid_spells(30))
        lua.execute("STUB.buffs = {} STUB.form = 1")
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        p += lua_list(tick(4, 0.25))
        lua.execute('STUB.targetName = "Nightbane Shadow Weaver" STUB.targetLevel = 28')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true")
        p += lua_list(tick(2, 0.25))
        if "Bash" in (ns.DruidAlert() or ""):
            p.append("no cast yet, the big text says %r" % ns.DruidAlert())
        p += lua_list(fire("UNIT_SPELLCAST_START", "target", "x", 695))
        p += lua_list(tick(1, 0.25))
        t = ns.DruidAlert() or ""
        if "Bash" not in t or "Alt+" not in t:
            p.append("a bear, the target casts, the big text says %r" % t)
        p += lua_list(fire("UNIT_SPELLCAST_INTERRUPTED", "target", "x", 695))
        p += lua_list(tick(1, 0.25))
        if "Bash" in (ns.DruidAlert() or ""):
            p.append("the cast was stopped, the text stays: %r" % ns.DruidAlert())
        # as a cat: the same key, twice (the bear, then Bash), big as well
        lua.execute("STUB.form = 3")
        p += lua_list(fire("UPDATE_SHAPESHIFT_FORM"))
        p += lua_list(fire("UNIT_SPELLCAST_CHANNEL_START", "target", "x", 695))
        p += lua_list(tick(1, 0.25))
        h = ns.DruidAlert() or ""
        if "Bash" not in h or "Alt+" not in h or "twice" not in h:
            p.append("a cat, the target casts, the big text says %r" % h)
        # the key itself: in a fight the bear first, then Bash; Roots only out of a fight
        cc = next((v for k, v in macro_attrs(lua).items() if "Bash" in str(v) and "Entangling Roots" in str(v)), "")
        if "/cast [combat,noform:1] Bear Form; [combat,harm,nodead] Bash" not in cc:
            p.append("Alt+F in a fight is not the bear and then Bash: %r" % cc)
        if "[nocombat,harm,nodead] Entangling Roots" not in cc or len(cc) > 255:
            p.append("Alt+F out of a fight has no Roots, or is too long: %r" % cc)
        p += lua_list(fire("UNIT_SPELLCAST_CHANNEL_STOP", "target", "x", 695))
        # Bash used: silent for its minute
        lua.execute("STUB.form = 1")
        p += lua_list(fire("UPDATE_SHAPESHIFT_FORM"))
        p += lua_list(lua.eval("STUB.castDone")(5211))
        p += lua_list(fire("UNIT_SPELLCAST_START", "target", "x", 695))
        p += lua_list(tick(1, 0.25))
        if "Bash" in (ns.DruidAlert() or ""):
            p.append("Bash on cooldown is named: %r" % ns.DruidAlert())
        return p

    @S.test("log: warnings and the AFK alarm are written (W), the meter's damage by spell after a fight (Y), a finisher's combo points")
    def _():
        p = []
        lua = new_lua()
        set_class(lua, "DRUID", 11, 30, druid_spells(30))
        lua.execute("STUB.buffs = {} STUB.form = 3")
        ns, errs = load_addon(lua)
        p += errs
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            p += lua_list(fire(e, "OneKeyDruid"))
        lines = lambda: [str(l) for l in lua_list(lua.eval("OneKeyDruidDB.lines"))]
        code = lambda c: [l.split("|") for l in lines() if l.split("|")[1] == c]
        # away from the keys for a minute, then something attacks: the alarm, in the log
        p += lua_list(tick(240, 0.25))
        lua.execute('STUB.targetName = "Nightbane Shadow Weaver" STUB.targetLevel = 30')
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true")
        p += lua_list(tick(2, 0.25))
        if not [w for w in code("W") if w[2] == "afk alarm"]:
            p.append("no AFK alarm in the log: %r" % code("W"))
        # the target casts: the warning is in the log once, as plain text
        p += lua_list(fire("UNIT_SPELLCAST_START", "target", "x", 695))
        p += lua_list(tick(3, 0.25))
        cast = [w for w in code("W") if "Bash" in "|".join(w[2:])]
        if len(cast) != 1:
            p.append("the cast warning is in the log %d times: %r" % (len(cast), code("W")))
        elif "|c" in "|".join(cast[0]) or len(cast[0]) != 3:
            p.append("the warning keeps its colour codes or has a '|' in it: %r" % cast[0])
        p += lua_list(fire("UNIT_SPELLCAST_STOP", "target", "x", 695))
        # five combo points, then Rip: the cast line carries the 5
        lua.execute("STUB.combo = 5")
        p += lua_list(fire("UNIT_POWER_UPDATE", "player", "COMBO_POINTS"))
        lua.execute("STUB.combo = 0")
        p += lua_list(fire("UNIT_POWER_UPDATE", "player", "COMBO_POINTS"))
        p += lua_list(lua.eval("STUB.castDone")(1079))
        rip = [a for a in code("A") if a[2] == "Rip"]
        if not rip or rip[-1][3:] != ["5"]:
            p.append("Rip is not logged with its five combo points: %r" % rip)
        p += lua_list(lua.eval("STUB.castDone")(1082))
        claw = [a for a in code("A") if a[2] == "Claw"]
        if not claw or len(claw[-1]) != 3:
            p.append("Claw (no finisher) carries a combo point field: %r" % claw)
        if code("Y"):
            p.append("damage by spell is written in the fight, when it is secret: %r" % code("Y"))
        # the fight ends: the meter's spells, strongest first
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(10, 0.25))
        y = code("Y")
        names = lambda r: [f.split("=")[0] for f in r[2:]]
        if len(y) != 1 or names(y[0])[:2] != ["Claw", "Rip"] or "Claw=812" not in y[0]:
            p.append("after the fight the damage by spell is %r" % y)
        # a client with no such call: nothing written, no error
        lua.execute("STUB.noMeterSpells = true")
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true")
        p += lua_list(tick(1, 0.25))
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(10, 0.25))
        if len(code("Y")) != 1:
            p.append("with no meter spells a Y line is written: %r" % code("Y"))
        lua.execute("STUB.noMeterSpells = false")
        # secret combo points in a fight: no error, and no count on the finisher
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true STUB.combo = STUB_secret()")
        p += lua_list(fire("UNIT_POWER_UPDATE", "player", "COMBO_POINTS"))
        p += lua_list(lua.eval("STUB.castDone")(1079))
        rip = [a for a in code("A") if a[2] == "Rip"]
        if len(rip[-1]) != 3:
            p.append("secret combo points gave the finisher a count: %r" % rip[-1])
        # the probe in a fight: the meter's spells are unreadable, and it says so
        e = lua.eval("STUB.slash")("probe")
        if e:
            p.append("/okd probe in a fight: %s" % e)
        probe = [str(l) for l in lua_list(lua.eval("OneKeyDruidDB.probes[#OneKeyDruidDB.probes]"))]
        spells = [l for l in probe if l.startswith("meter by spell:")]
        if not spells or "SECRET" not in spells[0]:
            p.append("the probe in a fight does not say the meter's spells are secret: %r" % spells)
        # the fight ends but the lock is still on when the timer comes: nothing read
        lua.execute("STUB.combo = 0")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(10, 0.25))
        if len(code("Y")) != 1:
            p.append("the meter was read while still locked: %r" % code("Y"))
        lua.execute("STUB.combat = false")
        # the meter's copy of your GUID is secret: your own GUID is used instead
        lua.execute("STUB.secretGuid = true")
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true")
        p += lua_list(tick(1, 0.25))
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(10, 0.25))
        if len(code("Y")) != 2:
            p.append("with a secret source GUID no damage by spell: %r" % code("Y"))
        e = lua.eval("STUB.slash")("probe")
        if e:
            p.append("/okd probe: %s" % e)
        probe = [str(l) for l in lua_list(lua.eval("OneKeyDruidDB.probes[#OneKeyDruidDB.probes]"))]
        if not any(l.startswith("percent: health") for l in probe) or not any(l.startswith("meter by spell: Claw=812") for l in probe):
            p.append("the probe has no percent or meter-by-spell line: %r" % probe)
        return p

    @S.test("macro: mage F is Frostbolt with up to two Fireballs before it, one macro per count; no cooldown on F")
    def _():
        p = []
        for level in (1, 4, 6, 10, 14, 15, 20, 26, 40):
            lua, ns, errs, fire, tick = mage_session(level, ("icelance",) if level >= 20 else ())
            p += errs
            M = ns.OneKeyMacros
            fight, heal, behind = M.fight or "", M.heal or "", M.behind or ""
            casts = [l for l in fight.split("\n") if l.startswith("/cast")]
            by = ns.OneKeyFightBy()
            if level < 4:
                if not casts or "Fireball" not in casts[0]:
                    p.append("level %d: Fireball is not the filler before Frostbolt: %r" % (level, casts[:1]))
            else:
                # the macro with no opener (attacked first): Frostbolt from the first press
                if "Fireball" in fight or not casts or "Frostbolt" not in casts[0]:
                    p.append("level %d: the plain fight macro is not Frostbolt first: %r" % (level, fight))
                # and one each for one and two Fireballs, once per target, then only
                # Frostbolt: the slow never lapses
                for n, want in ((1, "reset=target Fireball, null"), (2, "reset=target Fireball, Fireball, null")):
                    t = str(by[n] or "")
                    lines = [l for l in t.split("\n") if l.startswith("/cast")]
                    if want not in t or len(lines) < 2 or "Frostbolt" not in lines[1] or any("Fireball" in l for l in lines[1:]):
                        p.append("level %d: the macro for %d Fireball(s) is wrong: %r" % (level, n, t))
                    if len(t) > MACRO_LIMIT:
                        p.append("level %d: %d openers: %d chars" % (level, n, len(t)))
            for cd in ("Fire Blast", "Frost Nova", "Cone of Cold", "Ice Lance", "Ice Barrier"):
                if cd in fight:
                    p.append("level %d: %s (a cooldown) is on F and can stop the macro" % (level, cd))
            if level >= 20 and heal != "/castsequence [harm,nodead] reset=6/combat Frostbolt, Ice Lance":
                p.append("level %d: Shift+F is not Frostbolt, then Ice Lance, starting over after 6 s: %r" % (level, heal))
            # Frost Nova and Blink are on G only: a spell another key had put
            # on cooldown would hold G's sequence
            sos, others = M.sos or "", "\n".join([fight, heal, behind, M.cc or "", M.free or "", M.hide or ""])
            if "Frost Nova" in others or "Blink" in others:
                p.append("level %d: Frost Nova or Blink is on a key besides G" % level)
            want = [n for n, l in (("Frost Nova", 10), ("Blink", 20)) if level >= l]
            # reset by time only: the end of a fight must not put the sequence
            # back on Frost Nova while its cooldown still runs
            if want and not (sos.startswith("/castsequence reset=25 " + ", ".join(want)) and sos.split("\n")[0].endswith(", null")):
                p.append("level %d: G is not %s once through, starting over after 25 s: %r" % (level, ", ".join(want), sos))
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
            # two strikes before the first finisher: one that misses still
            # moves the sequence on, and a finisher with no point holds the key
            if level >= 10 and not seq.split("reset=target ")[-1].startswith("Sinister Strike, Sinister Strike, Slice and Dice, "):
                p.append("level %d: Slice and Dice is not the first finisher, after two strikes: %r" % (level, seq))
            if level >= 26 and "/cast [stealth] Cheap Shot\n" not in fight:
                p.append("level %d: no Cheap Shot opener from stealth" % level)
            if level >= 30:
                if not re.search(r"Sinister Strike, Kidney Shot, Sinister Strike, Gouge, .*Eviscerate$", seq):
                    p.append("level %d: the stun chain is wrong: %r" % (level, seq))
            elif "Gouge" not in seq or "Eviscerate" not in seq:
                p.append("level %d: no Gouge and finisher in the chain: %r" % (level, seq))
            if len(fight) > MACRO_LIMIT:
                p.append("level %d: %d chars" % (level, len(fight)))
        return p

    @S.test("mage: the opener by distance - two Fireballs from far with a short cast, one from the middle, none up close; /okd opener fixes it; G keeps the potion reachable")
    def _():
        p = []
        count = None
        # the arithmetic: d yards, opener cast, slow cast, at most
        lua, ns, errs, fire, tick = mage_session(10, drop=("water", "food"))
        p += errs
        count = ns.OneKeyOpenerCount
        for d, c_open, c_slow, want in ((32, 2.0, 1.8, 2), (25, 2.0, 1.8, 1), (12, 2.0, 1.8, 0),
                                        (32, 3.0, 2.5, 1), (25, 3.0, 2.5, 1), (12, 3.0, 2.5, 0),
                                        (33, 1.5, 1.5, 2), (32, 3.5, 3.0, 1)):
            got = count(d, c_open, c_slow, 2)
            if got != want:
                p.append("%d yd, Fireball %.1f s, Frostbolt %.1f s: %d openers, expected %d" % (d, c_open, c_slow, got, want))
        # on the key: a level 10 mage (2.0 s Fireball, 1.8 s Frostbolt) and a target
        lua.execute('STUB.buffs = { ["Arcane Intellect"] = true, ["Frost Armor"] = true } '
                    'STUB.targetName = "Wolf" STUB.targetLevel = 10 '
                    'STUB.castTime = { Fireball = 2000, Frostbolt = 1800 }')
        main = lambda: macro_attrs(lua).get("OneKeyMain:macrotext", "")
        def at(inrange):
            lua.execute("STUB.inRange = { %s }" % ", ".join('["%s"] = %s' % (k, "true" if v else "false") for k, v in inrange.items()))
            return lua_list(tick(2, 0.25))
        cases = (("far: only Fireball reaches", {"Fireball": True, "Frostbolt": False, "Fire Blast": False}, "Fireball, Fireball, null"),
                 ("middle: Frostbolt reaches", {"Fireball": True, "Frostbolt": True, "Fire Blast": False}, "reset=target Fireball, null"),
                 ("close: Fire Blast reaches", {"Fireball": True, "Frostbolt": True, "Fire Blast": True}, None),
                 ("too far yet", {"Fireball": False, "Frostbolt": False, "Fire Blast": False}, "Fireball, Fireball, null"))
        for what, inrange, want in cases:
            p += at(inrange)
            m = main()
            if (want and want not in m) or (not want and "Fireball" in m) or "Frostbolt" not in m:
                p.append("%s: %r" % (what, m))
        # the macro chosen for the pull stays when the fight begins
        p += at(cases[0][1])
        chosen = main()
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true")
        p += lua_list(tick(2, 0.25))
        if main() != chosen or "Fireball, Fireball, null" not in chosen:
            p.append("the opener chosen for the pull is replaced as the fight begins: %r" % main())
        v = [str(x) for x in lua.eval("STUB.violations").values()]
        if v:
            p.append("the opener touched secure state in the fight: %r" % v[:2])
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        # attacked first, with a buff still on the key: the plain fight macro
        lua.execute('STUB.buffs = {} STUB.targetName = nil')
        p += lua_list(tick(2, 0.25))
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        if "Fireball" in main() or "Frostbolt" not in main():
            p.append("attacked first: the key is not the plain fight macro: %r" % main())
        lua.execute('STUB.combat = false')
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        # the client does not say what reaches: one Fireball
        lua.execute('STUB.buffs = { ["Arcane Intellect"] = true, ["Frost Armor"] = true } STUB.targetName = "Wolf" STUB.inRange = nil')
        p += lua_list(tick(2, 0.25))
        if "reset=target Fireball, null" not in main():
            p.append("no range answer: not one Fireball: %r" % main())
        # below level 6 there is no Fire Blast to tell "close": one Fireball at most
        lua5, ns5, errs5, fire5, tick5 = mage_session(5, drop=("water", "food"))
        p += errs5
        lua5.execute('STUB.buffs = { ["Frost Armor"] = true } STUB.targetName = "Wolf" STUB.targetLevel = 5 '
                     'STUB.castTime = { Fireball = 1500, Frostbolt = 1500 } STUB.inRange = { Fireball = true, Frostbolt = false }')
        p += lua_list(tick5(2, 0.25))
        m5 = macro_attrs(lua5).get("OneKeyMain:macrotext", "")
        if "Fireball, Fireball" in m5 or "reset=target Fireball, null" not in m5:
            p.append("level 5 (no Fire Blast): not one Fireball: %r" % m5)
        # a count that is not a whole number (a hand-edited setting) still gives a macro
        lua.execute("OneKeyDruidDB.opener = 1.5")
        p += lua_list(tick(2, 0.25))
        if "Frostbolt" not in main():
            p.append("opener 1.5: the key has no fight macro: %r" % main())
        lua.execute("OneKeyDruidDB.opener = nil")
        # /okd opener N fixes the count, whatever the distance
        slash = lua.eval("STUB.slash")
        p += at(cases[2][1])
        for n, want in ((2, "Fireball, Fireball, null"), (1, "reset=target Fireball, null"), (0, None)):
            slash("opener %d" % n)
            p += lua_list(tick(2, 0.25))
            m = main()
            if (want and want not in m) or (not want and "Fireball" in m):
                p.append("/okd opener %d up close: %r" % (n, m))
        slash("opener auto")
        slash("opener 99")
        p += lua_list(tick(2, 0.25))
        if "Fireball" in main():
            p.append("/okd opener auto does not go back to the distance: %r" % main())
        # G: the sequence ends in null, so once through it lets the potion
        # line run; its reset (25 s) is not shorter than its longest cooldown
        CL = ns.CLASSES.MAGE
        seq = CL.sos[1]
        longest = max(CL.alert.cd[k] or 0 for k in seq[2].values())
        if not str(seq[4]).isdigit():
            p.append("G: the sequence resets on more than time (%r): after a fight it would stand on a spell still cooling" % seq[4])
        reset = int(str(seq[4]).split("/")[0])
        if not seq.stop or reset < longest:
            p.append("G: the sequence does not end, or resets (%d s) before its longest cooldown (%d s)" % (reset, longest))
        if CL.sos[2][1] != "potion":
            p.append("G: the potion is not the last line")
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
        if "Frost Nova" not in a or "IN MELEE: G " not in a:
            p.append("no Frost Nova hint on the emergency key after a melee hit: %r" % a)
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
    MAY_FAIL = ("Aimed Shot", "Summon Hawk", "Mortal Strike", "Bloodthirst", "Holy Strike", "Kidney Shot",
                "Slice and Dice",
                "Fire Blast", "Frost Nova", "Cone of Cold", "Ice Lance", "Mind Blast", "Arcane Shot",
                "Stormstrike", "Enrage", "Feral Charge", "Bash", "Nature's Grasp", "Hibernate",
                "Ice Barrier", "Evasion", "Feign Death", "Divine Shield", "Divine Protection", "Lay on Hands",
                "Retaliation", "Intimidating Shout", "Psychic Scream", "Death Coil", "Stoneclaw Totem", "Gouge",
                "Shred", "Ravage", "Backstab", "Ambush", "Overpower", "Execute", "Thunder Clap",
                "Judgement", "Earth Shock", "/use [combat]")

    def may_fail_early(text):
        acts = [l for l in text.split("\n") if l.startswith(("/cast", "/use"))]
        out = []
        for l in acts[:-1]:
            # The one exception: a sequence that ends (", null") and is reset
            # by time alone, no shorter than its longest cooldown, whose
            # spells are on no other key (the mage's G; both conditions are
            # tested in "mage: the opener by distance" and "macro: mage F").
            # It stands on a spell that is not ready only if another key
            # used that spell, or the reset came early.
            if re.match(r"^/castsequence reset=\d+ [^\n]*, null$", l):
                continue
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
                for k in ("fight", "fightBite", "sos", "cc", "heal", "catpull", "behind", "nuke", "free"):
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
            # a character has one strike talent
            spells = {v[1]: v[2] for v in CL.spells.values() if v[2] != "Bloodthirst"}
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

    def class_session(cls, cid, level, drop=(), setup=""):
        probe, _ = load_addon(new_lua(), ["Classes.lua"])
        spells = {v[1]: v[2] for v in probe.CLASSES[cls].spells.values() if v[2] not in drop}
        lua = new_lua()
        set_class(lua, cls, cid, level, spells)
        lua.execute("STUB.buffs = {} " + setup)
        ns, errs = load_addon(lua)
        fire, tick = lua.eval("STUB.fire"), lua.eval("STUB.tick")
        for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
            errs += lua_list(fire(e, "OneKeyDruid"))
        errs += lua_list(tick(4, 0.25))
        return lua, ns, errs, fire, tick

    def in_combat(lua, fire, tick):
        errs = lua_list(fire("PLAYER_REGEN_DISABLED"))
        lua.execute("STUB.combat = true")
        return errs + lua_list(tick(2, 0.25))

    @S.test("warrior: F is Rend once and Heroic Strike; with a strike talent Rend and the strike; the HUD names Overpower and Execute")
    def _():
        p = []
        strikes = ("Mortal Strike", "Bloodthirst")
        lua, ns, errs, fire, tick = class_session("WARRIOR", 1, 30, drop=strikes)
        p += errs
        M = ns.OneKeyMacros
        f = M.fight or ""
        if "Overpower" in f or "Execute" in f:
            p.append("a spell that is mostly unusable is on F: %r" % f)
        if "Rend, null" not in f or not f.endswith("!Heroic Strike"):
            p.append("F lacks Rend once or Heroic Strike: %r" % f)
        if "Overpower" not in (M.behind or "") or "Execute" not in (M.heal or ""):
            p.append("Overpower on Ctrl+F and Execute on Shift+F expected: %r / %r" % (M.behind, M.heal))
        if "Bloodrage" not in (M.free or ""):
            p.append("Bloodrage on Shift+G expected: %r" % M.free)
        for have in strikes:
            lua, ns, errs, fire, tick = class_session("WARRIOR", 1, 40, drop=[x for x in strikes if x != have],
                                                      setup='STUB.targetName = "Boar" STUB.usable = { Overpower = false, Execute = false }')
            p += errs
            f = ns.OneKeyMacros.fight or ""
            if "Rend, null" not in f or not f.endswith("/cast [harm,nodead] " + have) or "Heroic Strike" in f:
                p.append("with %s, F is not Rend once and the strike last: %r" % (have, f))
            p += in_combat(lua, fire, tick)
            if ns.OneKeyAlert():
                p.append("a hint with nothing usable: %r" % ns.OneKeyAlert())
            lua.execute("STUB.usable.Overpower = true")
            p += lua_list(tick(2, 0.25))
            a = ns.OneKeyAlert() or ""
            if "OVERPOWER" not in a or "Ctrl+F" not in a:
                p.append("no Overpower hint after a dodge: %r" % a)
            lua.execute("STUB.usable.Overpower = false STUB.usable.Execute = true")
            p += lua_list(tick(2, 0.25))
            a = ns.OneKeyAlert() or ""
            if "EXECUTE" not in a or "Shift+F" not in a:
                p.append("no Execute hint: %r" % a)
        return p

    @S.test("priest: Shadow Word: Pain once, then the wand; Smite only with no wand; the wand stays with Shadowform")
    def _():
        p = []
        for wand in (True, False):
            lua, ns, errs, fire, tick = class_session("PRIEST", 5, 24, drop=("Shadowform",),
                                                      setup="STUB.wand = %s" % ("true" if wand else "false"))
            p += errs
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
            if "Mind Blast" in f:
                p.append("Mind Blast (a cooldown) is in the fight macro: %r" % f)
        # Shadowform changes nothing: out of mana a Mind Flay line would
        # leave the key with nothing it can cast
        lua, ns, errs, fire, tick = class_session("PRIEST", 5, 40, setup="STUB.wand = true")
        p += errs
        f = ns.OneKeyMacros.fight or ""
        if not f.endswith("!Shoot") or "Mind Flay" in f:
            p.append("with Shadowform the wand is not the last line of F: %r" % f)
        return p

    @S.test("priest: before the pull F shields, then opens with Mind Blast; in the fight the HUD names Ctrl+F when it is ready")
    def _():
        p = []
        lua, ns, errs, fire, tick = class_session(
            "PRIEST", 5, 24, drop=("Shadowform",),
            setup='STUB.wand = true STUB.buffs = { ["Power Word: Fortitude"] = true, ["Inner Fire"] = true } '
                  'STUB.targetName = "Murloc" STUB.targetLevel = 24')
        p += errs
        main = lambda: macro_attrs(lua).get("OneKeyMain:macrotext", "")
        if main() != "/cast [@player] Power Word: Shield":
            p.append("with an enemy picked F is not the shield first: %r" % main())
        # Weakened Soul: no shield, the opener
        lua.execute('STUB.names[6788] = "Weakened Soul" STUB.debuffs = { ["Weakened Soul"] = true }')
        p += lua_list(tick(2, 0.25))
        if "Power Word: Shield" in main():
            p.append("F asks for the shield under Weakened Soul: %r" % main())
        lua.execute('STUB.debuffs = {}')
        p += lua_list(tick(2, 0.25))
        lua.execute('STUB.buffs["Power Word: Shield"] = true')
        p += lua_list(tick(2, 0.25))
        if not main().endswith("/cast [harm,nodead] Mind Blast"):
            p.append("with the shield up F does not open with Mind Blast: %r" % main())
        # the opener is out of range: one try, then the fight macro
        p += lua_list(lua.eval("STUB.click")("OneKeyMain", True))
        p += lua_list(tick(12, 0.25))
        if "Shadow Word: Pain" not in main():
            p.append("a Mind Blast press that failed holds the key: %r" % main())
        # in the fight: Mind Blast is named when ready, not while it cools
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(lua.eval("STUB.castDone")(8092))
        p += in_combat(lua, fire, tick)
        if ns.OneKeyAlert():
            p.append("a Mind Blast hint while it is on cooldown: %r" % ns.OneKeyAlert())
        p += lua_list(tick(36, 0.25))
        a = ns.OneKeyAlert() or ""
        if "MIND BLAST" not in a or "Ctrl+F" not in a:
            p.append("no Mind Blast hint when it is ready: %r" % a)
        # level 6: Smite opens, no Mind Blast yet
        lua, ns, errs, fire, tick = class_session("PRIEST", 5, 6, drop=("Shadowform", "Mind Blast", "Mind Flay"),
                                                  setup="STUB.wand = true")
        p += errs
        lua.execute('STUB.buffs = { ["Power Word: Fortitude"] = true } STUB.targetName = "Wolf" STUB.targetLevel = 6')
        p += lua_list(tick(2, 0.25))
        if "Power Word: Shield" in macro_attrs(lua).get("OneKeyMain:macrotext", ""):
            p.append("level 6: F shields before the pull")
        f = ns.OneKeyMacros.fight or ""
        if "/cast [nocombat,harm,nodead] Smite" not in f:
            p.append("before Mind Blast Smite does not open: %r" % f)
        return p

    @S.test("try once: hammering the key, a key-up or another key do not hold or cancel what F offers before a fight")
    def _():
        p = []
        click, main = None, None
        def session(setup):
            lua, ns, errs, fire, tick = class_session("PRIEST", 5, 24, drop=("Shadowform",), setup=setup)
            return lua, errs, fire, tick, lua.eval("STUB.click"), (lambda: macro_attrs(lua).get("OneKeyMain:macrotext", ""))
        base = ('STUB.wand = true STUB.buffs = { ["Power Word: Fortitude"] = true, ["Inner Fire"] = true } '
                'STUB.targetName = "Murloc" STUB.targetLevel = 24')
        # the shield never comes (silenced): F pressed twice a second lets go of it
        lua, errs, fire, tick, click, main = session(base)
        p += errs
        if "Power Word: Shield" not in main():
            return p + ["no shield offered: %r" % main()]
        for i in range(8):
            p += lua_list(click("OneKeyMain", True))
            p += lua_list(click("OneKeyMain", False))
            p += lua_list(tick(2, 0.25))
        if "Power Word: Shield" in main():
            p.append("hammering the key holds the shield offer after 4 s: %r" % main())
        # a key-up alone is not a try, and neither is another key
        lua, errs, fire, tick, click, main = session(base)
        p += errs
        p += lua_list(click("OneKeyMain", False))
        p += lua_list(click("OneKeyAlt", True))
        p += lua_list(tick(16, 0.25))
        if "Power Word: Shield" not in main():
            p.append("a key-up or Alt+F took the shield offer away: %r" % main())
        # a buff given up on is not offered again for every new target
        lua, errs, fire, tick, click, main = session('STUB.wand = true STUB.targetName = "Murloc" STUB.targetLevel = 24')
        p += errs
        first = main()
        p += lua_list(click("OneKeyMain", True))
        p += lua_list(tick(12, 0.25))
        p += lua_list(fire("PLAYER_TARGET_CHANGED"))
        p += lua_list(tick(2, 0.25))
        if main() == first:
            p.append("a buff that failed comes back with every new target: %r" % first)
        # what the client says cannot be cast now is not offered at all
        lua, ns, errs, fire, tick = class_session("WARRIOR", 1, 20, drop=("Mortal Strike", "Bloodthirst"),
                                                  setup='STUB.targetName = "Boar" STUB.usable = { ["Battle Shout"] = false }')
        p += errs
        m = macro_attrs(lua).get("OneKeyMain:macrotext", "")
        if "Battle Shout" in m:
            p.append("a warrior with no rage is offered Battle Shout: %r" % m)
        return p

    @S.test("hints fail closed: a secret usable answer names no key, a secret cooldown is counted from the cast")
    def _():
        p = []
        lua, ns, errs, fire, tick = class_session("WARRIOR", 1, 30, drop=("Mortal Strike", "Bloodthirst"),
                                                  setup='STUB.targetName = "Boar" STUB.secretUsable = true')
        p += errs
        p += in_combat(lua, fire, tick)
        p += lua_list(tick(8, 0.25))
        if ns.OneKeyAlert():
            p.append("a hint from a secret answer: %r" % ns.OneKeyAlert())
        # priest: the cooldown is secret in a fight
        lua, ns, errs, fire, tick = class_session(
            "PRIEST", 5, 24, drop=("Shadowform",),
            setup='STUB.wand = true STUB.targetName = "Murloc" STUB.targetLevel = 24 STUB.secretCooldown = true')
        p += errs
        # the fight begins with the cooldowns already secret (a /reload in
        # combat): nothing was read, no cast was seen, so nothing is named
        lua.execute("STUB.combat = true")
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        p += lua_list(tick(8, 0.25))
        if ns.OneKeyAlert():
            p.append("Mind Blast named ready with nothing to read and no cast seen: %r" % ns.OneKeyAlert())
        p += lua_list(lua.eval("STUB.castDone")(8092))
        p += lua_list(tick(8, 0.25))
        if ns.OneKeyAlert():
            p.append("Mind Blast named ready 2 s after its cast: %r" % ns.OneKeyAlert())
        p += lua_list(tick(28, 0.25))
        if "MIND BLAST" not in (ns.OneKeyAlert() or ""):
            p.append("Mind Blast not named 9 s after its cast (counted from the cast): %r" % ns.OneKeyAlert())
        return p

    @S.test("hints: cooldowns read as the fight begins; the mage's hints name nothing from a value that was not read")
    def _():
        p = []
        # read plainly on the way into the fight: Mind Blast is ready
        lua, ns, errs, fire, tick = class_session(
            "PRIEST", 5, 24, drop=("Shadowform",),
            setup='STUB.wand = true STUB.targetName = "Murloc" STUB.targetLevel = 24 STUB.secretCooldown = true')
        p += errs
        p += in_combat(lua, fire, tick)
        if "MIND BLAST" not in (ns.OneKeyAlert() or ""):
            p.append("Mind Blast, read as ready when the fight began, is not named: %r" % ns.OneKeyAlert())
        # mage after a /reload in a fight: hit in melee, Frost Nova's cooldown unreadable
        lua, ns, errs, fire, tick = mage_session(20, ("icelance",))
        p += errs
        lua.execute("STUB.secretCooldown = true STUB.combat = true")
        p += lua_list(fire("PLAYER_REGEN_DISABLED"))
        p += lua_list(fire("UNIT_COMBAT", "player", "WOUND", "", 30, 1))
        p += lua_list(tick(2, 0.25))
        if ns.OneKeyAlert():
            p.append("a Frost Nova hint from a cooldown nobody read: %r" % ns.OneKeyAlert())
        return p

    @S.test("try once: a press while mounted is no try; a buff given up on stays away after the fight")
    def _():
        p = []
        lua, ns, errs, fire, tick = class_session(
            "PRIEST", 5, 24, drop=("Shadowform",),
            setup='STUB.wand = true STUB.buffs = { ["Inner Fire"] = true } STUB.targetName = "Murloc" STUB.targetLevel = 24')
        p += errs
        click = lua.eval("STUB.click")
        main = lambda: macro_attrs(lua).get("OneKeyMain:macrotext", "")
        if "Power Word: Fortitude" not in main():
            return p + ["Fortitude not offered: %r" % main()]
        lua.execute("STUB.mounted = true")
        p += lua_list(tick(2, 0.25))
        p += lua_list(click("OneKeyMain", True))
        p += lua_list(tick(20, 0.25))
        lua.execute("STUB.mounted = false")
        p += lua_list(tick(2, 0.25))
        if "Power Word: Fortitude" not in main():
            p.append("a press while mounted counted as the try for Fortitude: %r" % main())
        # tried and failed: not offered again when the next fight has ended
        p += lua_list(click("OneKeyMain", True))
        p += lua_list(tick(12, 0.25))
        if "Power Word: Fortitude" in main():
            p.append("Fortitude still offered 3 s after its try: %r" % main())
        p += in_combat(lua, fire, tick)
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(4, 0.25))
        if "Power Word: Fortitude" in main():
            p.append("a buff given up on is back after one fight: %r" % main())
        return p

    @S.test("try once: a fight's presses are no try for a buff that was on the key when it began; G's hint waits for its sequence")
    def _():
        p = []
        lua, ns, errs, fire, tick = mage_session(10, drop=("water", "food"))
        p += errs
        lua.execute('STUB.buffs = { ["Frost Armor"] = true }')
        click = lua.eval("STUB.click")
        main = lambda: macro_attrs(lua).get("OneKeyMain:macrotext", "")
        p += lua_list(tick(2, 0.25))
        if "Arcane Intellect" not in main():
            return p + ["Arcane Intellect not offered: %r" % main()]
        # attacked first: six presses of F in the fight
        p += in_combat(lua, fire, tick)
        for i in range(6):
            p += lua_list(click("OneKeyMain", True))
            p += lua_list(tick(2, 0.25))
        # hit in melee, G never pressed: the hint names G and Frost Nova
        p += lua_list(fire("UNIT_COMBAT", "player", "WOUND", "", 30, 1))
        p += lua_list(tick(2, 0.25))
        if "IN MELEE: G " not in (ns.OneKeyAlert() or ""):
            p.append("no Frost Nova hint: %r" % ns.OneKeyAlert())
        # G pressed (Frost Nova cast), a new hit 10 s later with Nova read as ready
        # again by mistake: the hint must wait for the sequence's 25 s
        p += lua_list(click("OneKeySOS", True))
        lua.execute('STUB.cooldown["Frost Nova"] = 1')
        p += lua_list(lua.eval("STUB.castDone")(122))
        p += lua_list(tick(44, 0.25))
        p += lua_list(fire("UNIT_COMBAT", "player", "WOUND", "", 30, 1))
        p += lua_list(tick(2, 0.25))
        if "IN MELEE: G " in (ns.OneKeyAlert() or ""):
            p.append("the Frost Nova hint shows 11 s after a G press, while G's next press is not Frost Nova: %r" % ns.OneKeyAlert())
        lua.execute("STUB.combat = false")
        p += lua_list(fire("PLAYER_REGEN_ENABLED"))
        p += lua_list(tick(12, 0.25))
        if "Arcane Intellect" not in main():
            p.append("attacked first: the fight's presses took the Arcane Intellect offer away: %r" % main())
        return p

    @S.test("rogue: with no combo point and a key that casts nothing the HUD names Gouge")
    def _():
        p = []
        lua, ns, errs, fire, tick = class_session("ROGUE", 4, 30, setup='STUB.targetName = "Boar" STUB.usable = { Riposte = false } STUB.combo = 0')
        p += errs
        click = lua.eval("STUB.click")
        p += in_combat(lua, fire, tick)
        p += lua_list(lua.eval("STUB.castDone")(1752))
        for i in range(8):
            p += lua_list(click("OneKeyMain", True))
            p += lua_list(tick(2, 0.25))
        if ns.OneKeyAlert():
            p.append("a hint 4 s after the last cast: %r" % ns.OneKeyAlert())
        for i in range(8):
            p += lua_list(click("OneKeyMain", True))
            p += lua_list(tick(2, 0.25))
        a = ns.OneKeyAlert() or ""
        if "NO COMBO POINT" not in a or "Gouge" not in a or "Alt+F" not in a:
            p.append("no Gouge hint with no combo point and no cast for 8 s: %r" % a)
        # not while Gouge cannot be used, and not with no target
        lua.execute("STUB.usable.Gouge = false")
        p += lua_list(click("OneKeyMain", True))
        p += lua_list(tick(2, 0.25))
        if "NO COMBO POINT" in (ns.OneKeyAlert() or ""):
            p.append("the hint names Gouge while it cannot be used: %r" % ns.OneKeyAlert())
        lua.execute("STUB.usable.Gouge = true STUB.targetName = nil")
        p += lua_list(click("OneKeyMain", True))
        p += lua_list(tick(2, 0.25))
        if "NO COMBO POINT" in (ns.OneKeyAlert() or ""):
            p.append("the hint shows with no target: %r" % ns.OneKeyAlert())
        lua.execute('STUB.targetName = "Boar"')
        lua.execute("STUB.combo = 2")
        p += lua_list(click("OneKeyMain", True))
        p += lua_list(tick(2, 0.25))
        if "NO COMBO POINT" in (ns.OneKeyAlert() or ""):
            p.append("the hint stays with combo points: %r" % ns.OneKeyAlert())
        return p

    @S.test("rogue: Riposte on Ctrl+F in a fight, named after a parry")
    def _():
        p = []
        lua, ns, errs, fire, tick = class_session("ROGUE", 4, 30, setup='STUB.targetName = "Boar" STUB.usable = { Riposte = false }')
        p += errs
        b = ns.OneKeyMacros.behind or ""
        if b != "/cast [stealth,harm,nodead] Ambush\n/cast [nostealth,harm,nodead] Riposte":
            p.append("Ctrl+F is not Ambush in stealth and Riposte out of it: %r" % b)
        p += in_combat(lua, fire, tick)
        if ns.OneKeyAlert():
            p.append("a Riposte hint before a parry: %r" % ns.OneKeyAlert())
        lua.execute("STUB.usable.Riposte = true")
        p += lua_list(tick(2, 0.25))
        a = ns.OneKeyAlert() or ""
        if "RIPOSTE" not in a or "Ctrl+F" not in a:
            p.append("no Riposte hint after a parry: %r" % a)
        return p

    @S.test("hunter: the cooldown shots are one last sequence; hawks from Summon Hawk; the macro keeps Auto Shot")
    def _():
        p = []
        for hawk in (False, True):
            lua, ns, errs, fire, tick = class_session("HUNTER", 3, 60, drop=() if hawk else ("Summon Hawk",))
            p += errs
            f = ns.OneKeyMacros.fight or ""
            lines = f.split("\n")
            want = "Summon Hawk, Aimed Shot, Summon Hawk, Arcane Shot" if hawk else "Aimed Shot, Arcane Shot"
            if not lines[-1].endswith("reset=target " + want):
                p.append("hawk=%s: the last line is not the shot sequence: %r" % (hawk, lines[-1]))
            for need in ("/petattack", "Hunter's Mark, Serpent Sting, null", "!Auto Shot"):
                if need not in f:
                    p.append("hawk=%s: %s fell out of F (%d chars)" % (hawk, need, len(f)))
            if len(f) > MACRO_LIMIT:
                p.append("hawk=%s: %d chars" % (hawk, len(f)))
        return p

    @S.test("paladin: aura, blessing and seal are kept up out of combat; F is Judgement and Holy Strike in one sequence")
    def _():
        p = []
        lua, ns, errs, fire, tick = class_session("PALADIN", 2, 30, drop=("Seal of Command",))
        p += errs
        main = lambda: macro_attrs(lua).get("OneKeyMain:macrotext", "")
        f = ns.OneKeyMacros.fight or ""
        if not f.endswith("reset=target Judgement, Holy Strike, Judgement, Holy Strike, Seal of Righteousness"):
            p.append("F is not Judgement, Holy Strike twice, then the seal: %r" % f)
        seen = []
        for name in ("Retribution Aura", "Blessing of Might", "Seal of Righteousness"):
            seen.append(main())
            if main() != "/cast [@player] " + name:
                p.append("F does not put %s up: %r" % (name, main()))
            lua.execute('STUB.buffs["%s"] = true' % name)
            p += lua_list(tick(2, 0.25))
        lua, ns, errs, fire, tick = class_session("PALADIN", 2, 40)
        p += errs
        f = ns.OneKeyMacros.fight or ""
        if not f.endswith("Holy Strike, Seal of Command"):
            p.append("with Seal of Command learned it is not the seal: %r" % f)
        # level 4: no Holy Strike yet
        lua, ns, errs, fire, tick = class_session("PALADIN", 2, 4, drop=("Seal of Command", "Holy Strike", "Retribution Aura"))
        p += errs
        f = ns.OneKeyMacros.fight or ""
        if not f.endswith("reset=target Judgement, Judgement, Seal of Righteousness"):
            p.append("level 4: %r" % f)
        return p

    @S.test("shaman: the weapon imbue out of combat (Windfury over Rockbiter); F is Flame Shock, Stormstrike, Earth Shock")
    def _():
        p = []
        lua, ns, errs, fire, tick = class_session("SHAMAN", 7, 30, setup='STUB.buffs = { ["Lightning Shield"] = true }')
        p += errs
        main = lambda: macro_attrs(lua).get("OneKeyMain:macrotext", "")
        if main() != "/cast Windfury Weapon":
            p.append("with no imbue F is not Windfury Weapon: %r" % main())
        # a press that does nothing (no weapon) does not hold the key
        p += lua_list(lua.eval("STUB.click")("OneKeyMain", True))
        p += lua_list(tick(12, 0.25))
        if "Windfury" in main():
            p.append("an imbue press that failed holds the key: %r" % main())
        lua, ns, errs, fire, tick = class_session("SHAMAN", 7, 20, drop=("Windfury Weapon", "Stormstrike"),
                                                  setup='STUB.buffs = { ["Lightning Shield"] = true }')
        p += errs
        if main() != "/cast Rockbiter Weapon":
            p.append("before Windfury F is not Rockbiter Weapon: %r" % main())
        lua.execute("STUB.imbue = true")
        p += lua_list(tick(2, 0.25))
        if "Weapon" in main():
            p.append("with an imbue on F still asks for one: %r" % main())
        f = ns.OneKeyMacros.fight or ""
        if not f.endswith("reset=target Flame Shock, Earth Shock"):
            p.append("level 20: F is not Flame Shock, Earth Shock: %r" % f)
        lua, ns, errs, fire, tick = class_session("SHAMAN", 7, 30)
        p += errs
        f = ns.OneKeyMacros.fight or ""
        if not f.endswith("reset=target Flame Shock, Stormstrike, Earth Shock") or "[nocombat,harm,nodead] Lightning Bolt" not in f:
            p.append("level 30: F is not the Lightning Bolt pull and Flame Shock, Stormstrike, Earth Shock: %r" % f)
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
        ver = re.search(r"^## Version:\s*(\S+)", open(os.path.join(ADDON, "OneKeyDruid.toc"), encoding="utf-8").read(), re.M).group(1)
        if not any(l.split("|")[1] == "S" and l.endswith("|" + ver) for l in lines):
            p.append("the session line does not end with the addon version %s: %r" % (ver, lines[:2]))
        if "freeSlots(), VERSION)" not in open(os.path.join(ADDON, "Core.lua"), encoding="utf-8").read():
            p.append("the druid's session line does not end with the addon version")
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

    @S.test("release: a new version is published as a beta after every check; only release/STABLE makes it a release")
    def _():
        p = []
        wf = lambda n: open(os.path.join(ROOT, ".github", "workflows", n), encoding="utf-8").read()
        rel, pro, cf = wf("release.yml"), wf("promote.yml"), wf("curseforge.yml")
        # whole lines: a gate with "|| true", an "if:" or a changed call fails here
        must = {
            "release.yml": (rel, [
                "      - run: pip install --require-hashes -r tests/requirements.txt",
                "      - run: python3 -I tests/run_tests.py",
                "      - run: python3 -I tests/mutation_check.py",
                "      - run: python3 -I tests/fuzz_test.py --runs 500",
                "      - run: OKD_COVERAGE=1 python3 -I tests/run_tests.py --min-coverage 65",
                "      - run: python3 -I security/scan.py",
                "      - run: python3 -I tools/build.py --no-test",
                "    needs: plan",
                "    if: needs.plan.outputs.go == '1'",
                "    needs: [plan, release]",
                "    if: needs.plan.outputs.auto == '1'",
                "      prerelease: true",
                '          if gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/v$v" >/dev/null 2>&1; then',
                '          test "$top" = "$v" || { echo "$v is below the published $top"; exit 1; }',
                '          grep -Fxq "## $v" CHANGELOG.md || { echo "CHANGELOG.md has no section for $v"; exit 1; }',
                '            gh release create "$TAG" $files --target "$GITHUB_SHA" --prerelease \\',
                '            gh release create "$TAG" $files --draft --title "OneKey Forever ${TAG#v}" \\',
                '    paths: ["OneKeyDruid/OneKeyDruid.toc"]',
            ]),
            "promote.yml": (pro, [
                '    paths: ["release/STABLE"]',
                "    needs: promote",
                "    if: needs.promote.outputs.done == '1'",
                "      prerelease: false",
                '          sha256sum -c "OneKeyForever-$v.zip.sha256"',
                '          grep -Fxq "## $v: enough for a release" release/FIELD.md || { echo "release/FIELD.md does not say that $v has enough play behind it"; exit 1; }',
                '          test "$top" = "$v" || { echo "$v is below the latest release $latest"; exit 1; }',
                """          test "$state" = "$(printf 'false\\ttrue')" || { echo "$tag is not a published pre-release"; exit 1; }""",
            ]),
        }
        for name, (text, lines_) in must.items():
            have = text.splitlines()
            for l in lines_:
                if l not in have:
                    p.append("%s: the line is gone or changed: %s" % (name, l.strip()))
            for l in have:
                u = l.strip()
                if u.startswith("#"):
                    continue
                if "continue-on-error" in u or "|| true" in u.replace("2>/dev/null | sed 's/^v//' || true", "") \
                        or "true ||" in u or u in ("if: false", "if: always()") or "set +e" in u:
                    p.append("%s: a check is switched off: %s" % (name, u))
        if rel.count("gh release create") != 2 or "prerelease: false" in rel or "--prerelease=false" in rel or "--latest" in rel:
            p.append("release.yml can make a full release")
        if rel.count("\n    if:") != 2 or pro.count("\n    if:") != 1 or rel.count("        if:") or pro.count("        if:"):
            p.append("a job or step condition was added or removed in release.yml or promote.yml")
        gate_at = [rel.find(l) for l in must["release.yml"][1][:7]]
        if sorted(gate_at) != gate_at or not gate_at[-1] < rel.find("gh release create"):
            p.append("release.yml: the checks do not all run, in order, before the release is made")
        if "build.py" in pro or "gh release create" in pro or "gh release upload" in pro:
            p.append("promote.yml builds or uploads: it may only turn the tested pre-release into a release")
        if '"beta" if os.environ.get("PRERELEASE") == "true" else "release"' not in cf:
            p.append("curseforge.yml: the release type no longer follows the pre-release flag")
        for name, text in (("release.yml", rel), ("promote.yml", pro), ("curseforge.yml", cf)):
            for l in text.splitlines():
                u = l.strip()
                if u.startswith(("- uses:", "uses:")) and not u.split("uses:")[1].strip().startswith("./") \
                        and not re.search(r"@[0-9a-f]{40}\b", u):
                    p.append("%s: an action is not pinned to a commit: %s" % (name, u))
            if "pull_request_target" in text or "persist-credentials: true" in text:
                p.append("%s: unsafe trigger or kept credentials" % name)
        stable = open(os.path.join(ROOT, "release", "STABLE"), encoding="utf-8").read().strip()
        if not re.match(r"^\d+\.\d+\.\d+$", stable):
            p.append("release/STABLE is not one version number: %r" % stable)
        return p

    @S.test("log analyser: damage by spell (Y), combo points per finisher, warnings (W)")
    def _():
        import importlib.util
        p = []
        spec = importlib.util.spec_from_file_location("analyze_log", os.path.join(ROOT, "tools", "analyze_log.py"))
        al = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(al)
        e = [l.split("|") for l in (
            "0.0|S|1|30|0|100|0|Duskwood|1|2|0.39.0", "1.0|C+|Wolf|30|normal|cat|A", "2.0|A|Rip|5",
            "3.0|A|Rip|4", "3.5|A|Ferocious Bite|5", "4.0|A|Claw", "5.0|W|afk alarm", "5.5|W|afk alarm",
            "6.0|C-|5|10|1|1", "7.5|M|900|100|0|1000", "7.5|Y|Claw=600|Rip=300", "20.0|Y|Claw=100|Melee=0",
        )]
        d = al.spell_damage(e)
        if not d or list(d)[0] != "Claw" or not d["Claw"].startswith("700 (70 %)") or not d["Rip"].startswith("300 (30 %)"):
            p.append("damage by spell: %r" % d)
        cp = al.finisher_cp(e)
        if cp != {"Rip": {4: 1, 5: 1}, "Ferocious Bite": {5: 1}}:
            p.append("combo points per finisher: %r" % cp)
        s = al.summary(e)
        if s["warnings"] != [("afk alarm", 2)]:
            p.append("warnings: %r" % s["warnings"])
        if al.spell_damage(e[:3]) is not None or al.finisher_cp(e[:2]) is not None:
            p.append("a session with no Y or finisher lines is not None")
        return p

    @S.test("release: the log analyser counts the play behind a version (stamped sessions only)")
    def _():
        import importlib.util, tempfile
        p = []
        spec = importlib.util.spec_from_file_location("analyze_log", os.path.join(ROOT, "tools", "analyze_log.py"))
        al = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(al)

        def log(cls, ver, fights, seconds, dead=0, deaths=0):
            s = "0.0|S|1|10|0|100|0|Elwynn|" + ("1|2" if cls == "DRUID" else cls) + ("|" + ver if ver else "")
            out, t = [s], 1.0
            for i in range(fights):
                out += ["%.1f|C+|Wolf|10|normal" % t, "%.1f|P|fight|6" % t]
                if i >= dead:
                    out.append("%.1f|A|Claw" % t)
                out.append("%.1f|C-|5|10|1|1" % (t + 5))
                t += 6
            out += ["%.1f|D+|Wolf|10" % t] * deaths
            out.append("%.1f|T|Wolf|10" % seconds)
            return 'OneKeyDruidDB = {\n["lines"] = {\n' + "".join('"%s",\n' % l for l in out) + '},\n["pos"] = {\n"CENTER",\n},\n}\n'

        def verdict(*logs):
            ss = []
            for text in logs:
                with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as f:
                    f.write(text)
                ss += [al.summary(e) for e in al.sessions(f.name)]
                os.unlink(f.name)
            return al.field(ss, "9.9.9")

        d = log("DRUID", "9.9.9", 40, 3600)
        if verdict(d, d)["fights"] != 40:
            p.append("the same session from two files (the .bak) is counted twice")
        if verdict(d.replace('\n},\n["pos"]', '\n\t},\n["pos"]').replace('"CENTER"', '"99999|x|y"'))["minutes"] != 60:
            p.append("a string of another table is read as a log line")
        good = verdict(log("DRUID", "9.9.9", 40, 3600), log("MAGE", "9.9.9", 30, 2400))
        if good["missing"] or good["fights"] != 70 or good["minutes"] != 100:
            p.append("enough play is not enough: %r" % good)
        if not verdict(log("DRUID", "9.9.8", 40, 3600), log("MAGE", "", 30, 2400))["missing"] \
                or verdict(log("DRUID", "9.9.8", 40, 3600))["sessions"] != 0:
            p.append("sessions of another version, or with no stamp, are counted")
        if not any("another class" in m for m in verdict(log("DRUID", "9.9.9", 80, 7200))["missing"]):
            p.append("one class alone is enough")
        if not any("no cast" in m for m in verdict(log("DRUID", "9.9.9", 40, 3600, dead=5), log("MAGE", "9.9.9", 30, 2400))["missing"]):
            p.append("fights with the key pressed and no cast do not hold a release back")
        if not any("deaths" in m for m in verdict(log("DRUID", "9.9.9", 40, 3600, deaths=4), log("MAGE", "9.9.9", 30, 2400))["missing"]):
            p.append("four deaths in 100 minutes do not hold a release back")
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
            if len(f) != 17:
                p.append("quest %s: %d fields" % (qid, len(f)))
                continue
            if not re.match(r"^D?E?U?$", f[13]) or not re.match(r"^\d*$", f[14]) or not re.match(r"^\d$", f[15]):
                p.append("quest %s: bad flags, mob level or chain count: %r" % (qid, f[13:16]))
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
        if n < 3000:
            p.append("only %d quests" % n)
        # what the solo rating stands on, checked against well-known quests
        f = lambda qid: str(Q.q[qid]).split("|")
        if "E" not in f(176)[13]:
            p.append("Wanted: Hogger (176) is not marked elite: %r" % f(176)[13:15])
        if f(12)[13] != "" or f(12)[14] != "13" or "15 Defias Trappers" not in f(12)[16]:
            p.append("The People's Militia (12): flags, mob level or task line wrong: %r" % f(12)[13:])
        if f(12)[9] != "1436":
            p.append("The People's Militia (12) is not placed in Westfall (1436): %r" % f(12)[9])
        # dungeon quests: pfQuest has no position for most dungeon mobs, so a
        # target, an item source or a hand-in with no place outdoors marks them
        for qid, name in ((166, "The Defias Brotherhood"), (1198, "In Search of Thaelrid"), (1013, "The Book of Ur"),
                          (1098, "Deathstalkers in Shadowfang"), (4241, "Marshal Windsor"), (2278, "The Platinum Discs")):
            if not f(qid)[0].startswith(name) or not f(qid)[13]:
                p.append("%s (%d) carries no flag: it would be rated solo" % (name, qid))
        # ordinary quests must not: a cooking quest is not "too high" for
        # the mob that drops its meat a little more often three zones away
        for qid, name, lo, hi in ((22, "Goretusk Liver Pie", 10, 14), (38, "Westfall Stew", 10, 15), (418, "Thelsamar Blood Sausages", 9, 14),
                                  (385, "Crocolisk Hunting", 10, 16), (488, "Zenn's Bidding", 3, 7), (102, "Patrolling Westfall", 12, 15)):
            r = f(qid)
            if not r[0].startswith(name) or r[13] or not (lo <= int(r[14] or 0) <= hi):
                p.append("%s (%d): flags %r, mob level %r (expected none, %d-%d)" % (name, qid, r[13], r[14], lo, hi))
        # a quest started by an object takes its faction from who it is handed in to
        if f(398)[12] != "2" or f(2933)[12] != "2":
            p.append("Wanted: Maggot Eye (398) and Venom Bottles (2933) are not Horde quests: %r %r" % (f(398)[12], f(2933)[12]))
        deadmines = [q for q in Q.q.keys() if str(Q.q[q]).startswith("Collecting Memories|")]
        if not deadmines or not f(deadmines[0])[13]:
            p.append("Collecting Memories (the Deadmines) is not marked as a group quest")
        # an item many mobs drop: the ones in the quest's own zone, near its level
        goulash = f(92)
        if goulash[9] != "1433" or not (15 <= int(goulash[14] or 0) <= 20):
            p.append("Redridge Goulash (92) is not a Redridge quest with level 15-20 mobs: %r" % goulash[9:15])
        hogger = str(npcs[448]).split("|")
        if hogger[0] != "Hogger" or hogger[3] != "11" or hogger[4] != "1":
            p.append("Hogger: level and rank not in the npc record: %r" % hogger)
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

    @S.test("questdatanew: the Forever quests from All The Things parse, carry their notice and repeat nothing")
    def _():
        p = []
        lua = new_lua()
        ns, errs = load_addon(lua, ["QuestData.lua", "QuestDataNew.lua"])
        if errs:
            return errs
        X, Q = ns.QDBX, ns.QDB.q
        n = 0
        for qid in X.keys():
            n += 1
            f = str(X[qid]).split("|")
            if len(f) != 9:
                p.append("quest %s: %d fields" % (qid, len(f)))
                continue
            if Q[qid]:
                p.append("quest %s is in QuestData.lua too" % qid)
            if int(qid) < 20000:
                p.append("quest %s is a Classic id, not one Forever added" % qid)
            if int(f[0] or 0) < 1:
                p.append("quest %s has no level: it would be offered at every level" % qid)
            # one side only in the starting zones and capitals
            # Ratchet gives quests to both sides: no side from the zone in the Barrens
            if int(qid) in (92706, 97253) and f[1] != "":
                p.append("quest %s at Ratchet got a side from its zone: %r" % (qid, f[1]))
            if (f[3] in ("1420", "1412", "1411", "1454", "1456", "1458") and f[1] != "2") or \
               (f[3] in ("1429", "1426", "1438", "1453", "1455", "1457") and f[1] != "1"):
                p.append("quest %s on map %s has faction %r" % (qid, f[3], f[1]))
            xy = f[4].split(",")
            if not f[3].isdigit() or len(xy) != 2 or not all(0 <= float(v) <= 100 for v in xy):
                p.append("quest %s: no map or a point off the map: %r %r" % (qid, f[3], f[4]))
            if f[1] not in ("", "1", "2") or not re.match(r"^\d+$", f[0]) or not re.match(r"^B?$", f[6]):
                p.append("quest %s: bad level, faction or flags: %r" % (qid, f))
        if n < 500:
            p.append("only %d quests" % n)
        head = read(os.path.join(ADDON, "QuestDataNew.lua"))[:900]
        for need in ("All The Things", "MIT", "extract_att.py", "revision"):
            if need not in head:
                p.append("QuestDataNew.lua does not name %s in its header" % need)
        text = read(os.path.join(ADDON, "QuestDataNew.lua"))
        if "lore" in text or "description" in text:
            p.append("QuestDataNew.lua holds text fields; only ids, levels and positions belong there")
        return p

    def quest_session(level, mapid, x, y, setup="", cls=("DRUID", 11)):
        lua = new_lua()
        set_class(lua, cls[0], cls[1], level, druid_spells(level) if cls[0] == "DRUID" else {})
        lua.execute('STUB.map = %d STUB.x = %f STUB.y = %f STUB.quests = {} STUB.flagged = {} '
                    'STUB.faction = "Alliance" STUB.raceId = 4 STUB.race = "NightElf" %s' % (mapid, x / 100.0, y / 100.0, setup))
        ns, errs = load_addon(lua, ["QuestData.lua", "QuestDataNew.lua", "QuestHelp.lua", "QuestList.lua"])
        errs += lua_list(lua.eval("STUB.fire")("PLAYER_LOGIN"))
        return lua, ns, errs

    @S.test("solo: the rating - elite and dungeon need a group, mobs or a quest 3 levels over are too hard, the game's tag wins")
    def _():
        p = []
        lua, ns, errs = quest_session(12, 1436, 56, 47)
        p += errs
        rate = ns.QH.Rate
        t = lambda **kw: lua.table_from(kw)
        cases = [
            (t(level=12, mob=13, flags=""), 12, None, "solo"),
            (t(level=12, mob=15, flags=""), 12, None, "hard"),
            (t(level=15, mob=0, flags=""), 12, None, "hard"),
            (t(level=14, mob=14, flags=""), 12, None, "solo"),
            (t(level=12, mob=12, flags="E"), 12, None, "group"),
            (t(level=12, mob=0, flags="U"), 12, None, "unsure"),
            (t(level=18, mob=19, flags="D"), 25, None, "group"),
            (t(level=5, mob=5, flags=""), 12, None, "low"),
            (t(level=12, mob=12, flags=""), 12, t(group=True), "group"),
            (t(level=0, mob=0, flags="", new=True, min=10), 12, None, "new"),
            (t(level=0, mob=0, flags="", new=True, min=10), 12, t(level=13, group=False), "solo"),
        ]
        for q, lvl, g, want in cases:
            got = rate(q, lvl, g)
            if got != want:
                p.append("level %s mob %s flags %r at %d: %s, expected %s" % (q.level, q.mob, q.flags, lvl, got, want))
        return p

    @S.test("solo: the plan for Westfall - hand-ins first, one walk through the solo quests, group quests apart with the reason")
    def _():
        p = []
        # level 14 at Sentinel Hill; The People's Militia (12) is done and
        # ready to hand in, The Defias Brotherhood chain is in the log
        setup = ('STUB.quests = { { questID = 12, title = "The People\'s Militia", level = 12 }, '
                 '{ questID = 102, title = "Patrolling Westfall", level = 14 } } '
                 'STUB.questDone = { [12] = true } '
                 'STUB.objectives = { [102] = { { text = "Gnoll Paw: 3/8", finished = false } } }')
        lua, ns, errs = quest_session(14, 1436, 56, 47, setup)
        p += errs
        ns.QH.Refresh(14)
        plan = [r for r in ns.QH.Plan(False).values()]
        if not plan:
            return p + ["no plan for Westfall at level 14"]
        heads = [str(r.sep or r.head) for r in plan]
        if "Hand in: The People's Militia" not in heads[0]:
            p.append("the hand-in is not the first row: %r" % heads[0])
        sep = next((i for i, h in enumerate(heads) if h.startswith("Not on your own")), None)
        walk = plan[:sep] if sep is not None else plan
        if len(walk) < 4:
            p.append("only %d rows before the group quests: %r" % (len(walk), heads[:6]))
        for r in walk:
            if r.rate in ("group", "hard") and r.e.kind != "hand":
                p.append("a %s quest is in the walk: %s" % (r.rate, r.head))
        # the quest in the log shows the game's own count of what is left
        mine = [r for r in plan if not r.sep and r.e.q.id == 102]
        if not mine or "Gnoll Paw: 3/8" not in str(mine[0].sub):
            p.append("Patrolling Westfall does not show what is left: %r" % [str(r.sub) for r in mine])
        # the walk never doubles back: each stop is the best next from the last
        if sep is not None:
            apart = plan[sep + 1:]
            if not apart or any(not r.sep and " — " not in str(r.head) for r in apart[:3]):
                p.append("the rows left apart do not say why: %r" % [str(r.head) for r in apart[:3]])
        # nothing for the Horde
        for h in heads:
            if "Grom'gol" in h:
                p.append("a Horde quest in the plan: %s" % h)
        # the hint never names a quest that needs a group while a solo one is there
        best = ns.QH.Refresh(14)
        if best and best[2].kind != "hand" and best[2].rate in ("group", "hard"):
            p.append("the hint names a %s quest: %s" % (best[2].rate, ns.QH.Hint(False)))
        return p

    @S.test("solo: a finished quest handed in on another map does not break the list; no quest of the other side is offered")
    def _():
        p = []
        # The People's Militia is done; the player stands in Elwynn
        setup = ('STUB.quests = { { questID = 12, title = "The People\'s Militia", level = 12 }, '
                 '{ questID = 999002, title = "Odd One", level = 12 } } STUB.questDone = { [12] = true, [999002] = true }')
        lua, ns, errs = quest_session(12, 1429, 42, 65, setup)
        p += errs
        ns.QH.Refresh(12)
        ok, plan = lua.eval("pcall")(ns.QH.Plan, False)
        if not ok:
            return p + ["QH.Plan raised: %s" % plan]
        heads = [str(r.sep or r.head) for r in plan.values()]
        if not any("Elsewhere" in h for h in heads) or not any("The People's Militia" in h for h in heads):
            p.append("the hand-in on another map is not listed under Elsewhere: %r" % heads[-4:])
        ns.QL.Toggle()
        ok, err = ns.QL.Refresh(True)
        if not ok or len(list(ns.QL.Rows().values())) < 2:
            p.append("the list window does not draw: %r" % err)
        # an Alliance night elf in Tirisfal, a Horde orc in Teldrassil
        for fac, race, mapid, lvl, x, y in (("Alliance", 4, 1420, 10, 60, 52), ("Horde", 2, 1438, 6, 56, 60)):
            lua, ns, errs = quest_session(lvl, mapid, x, y)
            lua.execute('STUB.faction = "%s" STUB.raceId = %d' % (fac, race))
            ns, errs2 = load_addon(lua, ["QuestData.lua", "QuestDataNew.lua", "QuestHelp.lua"])
            p += errs + errs2
            ns.QH.Refresh(lvl)
            rows = [r for r in ns.QH.Plan(False).values() if not r.sep and r.e.kind == "take" and r.e.d < 999]
            if rows:
                p.append("%s on map %d is offered %d quests of the other side, e.g. %s" % (fac, mapid, len(rows), rows[0].head))
        return p

    @S.test("solo: a quest the game tags for a group is left apart, and Hogger is named elite before you take it")
    def _():
        p = []
        setup = ('STUB.quests = { { questID = 102, title = "Patrolling Westfall", level = 14, suggestedGroup = 3 } } '
                 'STUB.questTag = { [102] = 1 }')
        lua, ns, errs = quest_session(14, 1436, 56, 47, setup)
        p += errs
        ns.QH.Refresh(14)
        plan = [r for r in ns.QH.Plan(False).values()]
        heads = [str(r.sep or r.head) for r in plan]
        sep = next((i for i, h in enumerate(heads) if h.startswith("Not on your own")), None)
        at = next((i for i, r in enumerate(plan) if not r.sep and r.e.q.id == 102), None)
        if sep is None or at is None or at < sep or "needs a group" not in heads[at]:
            p.append("the group quest is not left apart with its reason: %r" % heads)
        # Elwynn at level 10, by the Hogger poster
        lua, ns, errs = quest_session(10, 1429, 24, 78)
        p += errs
        ns.QH.Refresh(10)
        rows = [r for r in ns.QH.Plan(False).values() if not r.sep and "Hogger" in str(r.head)]
        if not rows or rows[0].rate != "group" or "elite" not in str(rows[0].head):
            p.append("Wanted: Hogger is not offered as an elite quest: %r" % [str(r.head) for r in rows])
        return p

    @S.test("solo: quests Forever added are offered where they start, with the server's title or a plain name")
    def _():
        p = []
        lua, ns, errs = quest_session(6, 2521, 48, 78, 'STUB.questTitles = {}')
        p += errs
        ns.QH.Refresh(6)
        plan = [r for r in ns.QH.Plan(False).values() if not r.sep]
        new = [r for r in plan if r.rate == "new"]
        if not new:
            return p + ["no Forever quest offered on Zephras Isle (map 2521) at level 6: %r" % [str(r.head) for r in plan[:5]]]
        if "New Forever quest #" not in str(new[0].head) or "new in Forever" not in str(new[0].head):
            p.append("a new quest without a title is not named plainly: %r" % str(new[0].head))
        qid = new[0].e.q.id
        lua.execute('STUB.questTitles[%d] = "A Wind From The Isle"' % qid)
        ns.QH.Refresh(6)
        plan = [r for r in ns.QH.Plan(False).values() if not r.sep and r.e.q.id == qid]
        if not plan or "A Wind From The Isle" not in str(plan[0].head):
            p.append("the server's title is not used once known: %r" % [str(r.head) for r in plan])
        # a quest of the log no data file knows: the game's own point is the place
        setup = ('STUB.quests = { { questID = 999001, title = "Strange Tides", level = 6 } } '
                 'STUB.objectives = { [999001] = { { text = "Tide Crawler slain: 0/6", finished = false } } } '
                 'STUB.questPoi = { [2521] = { { questID = 999001, x = 0.52, y = 0.71 } } }')
        lua, ns, errs = quest_session(6, 2521, 48, 78, setup)
        p += errs
        ns.QH.Refresh(6)
        rows = [r for r in ns.QH.Plan(False).values() if not r.sep and r.e.q.id == 999001]
        if not rows or "Tide Crawler slain: 0/6" not in str(rows[0].head) or "52,71" not in str(rows[0].head) or not rows[0].go:
            p.append("an unknown quest does not use the game's point and count: %r" % [str(r.head) for r in rows])
        return p

    @S.test("solo: the list window - a left click sets the map pin and says what to do, a right click leaves the quest out; in a fight too")
    def _():
        p = []
        lua, ns, errs = quest_session(14, 1436, 56, 47)
        p += errs
        QL = ns.QL
        lua.eval("STUB.slash") if False else None
        QL.Toggle()
        rows = [r for r in QL.Rows().values()]
        if not QL.IsShown() or len(rows) < 3:
            return p + ["the list does not open with rows: %d" % len(rows)]
        first = next(i for i, r in enumerate(rows, 1) if not r.sep)
        lua.execute("STUB.waypoint = nil STUB.printed = {}")
        if QL.Press(first, "LeftButton") != "go" or not lua.eval("STUB.waypoint"):
            p.append("a left click does not set the game's waypoint")
        wp = lua.eval("STUB.waypoint")
        if wp and (wp[1] != 1436 or not (0 <= wp[2] <= 1 and 0 <= wp[3] <= 1)):
            p.append("the waypoint is not a point on the Westfall map: %r" % [wp[1], wp[2], wp[3]])
        said = "\n".join(str(x) for x in lua.eval("STUB.printed").values())
        if "map pin and arrow" not in said or str(rows[first - 1].head) not in said:
            p.append("the chat does not say what to do: %r" % said[:200])
        head = str(rows[first - 1].head)
        if QL.Press(first, "RightButton") != "skip":
            p.append("a right click does not leave the quest out")
        if any(str(r.head) == head for r in QL.Rows().values() if not r.sep):
            p.append("the quest left out is still in the list: %s" % head)
        # in a fight: clicking and closing are plain frames, nothing secure
        lua.execute("STUB.combat = true STUB.violations = {}")
        QL.Press(first, "LeftButton")
        QL.Toggle()
        QL.Toggle()
        v = [str(x) for x in lua.eval("STUB.violations").values()]
        if v:
            p.append("the list touched secure state in a fight: %r" % v[:2])
        # a row that is only a heading does nothing
        lua.execute("STUB.combat = false")
        rows = [r for r in QL.Rows().values()]
        seps = [i for i, r in enumerate(rows, 1) if r.sep]
        if seps and QL.Press(seps[0], "LeftButton") is not None:
            p.append("a heading row answers a click")
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
