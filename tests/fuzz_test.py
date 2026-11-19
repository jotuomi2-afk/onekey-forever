#!/usr/bin/env python3
"""Property-based fuzzing: random but reproducible play sessions for every
class, checked against invariants that must hold whatever happens.

    python3 tests/fuzz_test.py                 # 40 runs per class (CI)
    python3 tests/fuzz_test.py --runs 500      # deeper, nightly or before a release
    python3 tests/fuzz_test.py --seed 1234     # replay one failing run

Each run picks a class, a level and a learned spell set, then plays a random
sequence of events: targets of random level and classification, entering
and leaving combat, hits, level ups, learning spells, zone changes, bag
changes, death and release, merchant windows, quest log changes, random
slash commands (including junk). Invariants after every step:

  I1 no Lua error in any handler
  I2 no secure change during combat (SetAttribute, bindings, PlaceAction)
  I3 every macro on a button is at most 255 characters
  I4 no comparison or arithmetic on a secret value (the stub raises)
  I5 no new global variables beyond the documented ones
"""
import argparse, os, random, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_tests as T  # noqa: E402

ALLOWED_GLOBALS = {"OneKeyDruidDB", "SLASH_ONEKEYDRUID1", "SLASH_ONEKEYDRUID2", "OneKeyHud",
                   "BINDING_HEADER_ONEKEYDRUID", "BINDING_NAME_CLICK OneKeyDruidButton:LeftButton"}
CLASSES = [("DRUID", 11), ("MAGE", 8), ("WARRIOR", 1), ("ROGUE", 4), ("HUNTER", 3),
           ("PRIEST", 5), ("WARLOCK", 9), ("PALADIN", 2), ("SHAMAN", 7)]
JUNK = ["", " ", "bind", "bind ", "bind SHIFT-F", "bind ctrl-alt-x", "sos off", "sos G", "lang xx", "mode",
        "mode cat", "mode bear", "mode auto", "nuke off", "nuke on", "prowl off", "quests off", "quests on",
        "skip", "skip clear", "go", "where", "ranks", "ranks off", "ranks on", "hpregen 3", "hpregen -1",
        "manaregen 999", "status", "report", "%s%s%n", "ää ö €", "x" * 300, "brave on", "brave off",
        "alarm off", "herbs off", "runtest", "debug", "log off", "log on"]
ZONES = [("Darkshore", 1439), ("Redridge Mountains", 1433), ("Wetlands", 1437), ("Stormwind City", 1453),
         ("The Deadmines", 9999), ("", 0)]
TARGETS = ["Redridge Mongrel", "Blackrock Champion", "Chef Breanna", "X%sY", "Dragon|Whelp", "Ölli", None]


def spells_for(lua, cls, level, rnd):
    if cls == "DRUID":
        s = T.druid_spells(level)
    else:
        probe, _ = T.load_addon(T.new_lua(), ["Classes.lua"])
        s = {v[1]: v[2] for v in probe.CLASSES[cls].spells.values()}
    # sometimes a random subset: not every spell is trained
    if rnd.random() < 0.4:
        s = {k: v for k, v in s.items() if rnd.random() < 0.7}
    return s


def snapshot_globals(lua):
    g = lua.globals()
    return set(str(k) for k in g.keys())


def one_run(seed, steps=120):
    rnd = random.Random(seed)
    cls, cid = rnd.choice(CLASSES)
    level = rnd.choice([1, 5, 10, 14, 18, 20, 24, 30, 32, 40, 60])
    lua = T.new_lua()
    T.set_class(lua, cls, cid, level, spells_for(lua, cls, level, rnd))
    lua.execute("STUB.buffs = {} STUB.quests = {} STUB.flagged = {}")
    # client variations: no scale curve, no damage meter
    if rnd.random() < 0.3:
        lua.execute("CurveConstants = nil")
    if rnd.random() < 0.3:
        lua.execute("STUB.meter = false")
    before = snapshot_globals(lua)
    ns, errs = T.load_addon(lua)
    if errs:
        return cls, level, ["load: " + e for e in errs]
    fire, tick, slash = lua.eval("STUB.fire"), lua.eval("STUB.tick"), lua.eval("STUB.slash")
    problems = []

    def check(where):
        for v in T.lua_list(lua.eval("STUB.violations")):
            problems.append("%s: taint: %s" % (where, v))
        lua.execute("STUB.violations = {}")
        for k, v in T.macro_attrs(lua).items():
            if len(v) > T.MACRO_LIMIT:
                problems.append("%s: %s is %d chars" % (where, k, len(v)))

    for e in ("ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD"):
        problems += T.lua_list(fire(e, "OneKeyDruid"))
    for i in range(steps):
        a = rnd.random()
        where = "step %d" % i
        if a < 0.25:
            problems += T.lua_list(tick(rnd.randint(1, 8), 0.25))
        elif a < 0.35:
            name = rnd.choice(TARGETS)
            if name:
                lua.execute('STUB.targetName = %r STUB.targetLevel = %d STUB.targetClass = %r'
                            % (name, max(1, level + rnd.randint(-8, 5)),
                               rnd.choice(["normal", "elite", "rare", "rareelite", "worldboss", "trivial", "minus"])))
            else:
                lua.execute("STUB.targetName = nil")
            problems += T.lua_list(fire("PLAYER_TARGET_CHANGED"))
        elif a < 0.45 and not lua.eval("STUB.combat"):
            problems += T.lua_list(fire("PLAYER_REGEN_DISABLED"))
            lua.execute("STUB.combat = true")
        elif a < 0.52 and lua.eval("STUB.combat"):
            lua.execute("STUB.combat = false")
            problems += T.lua_list(fire("PLAYER_REGEN_ENABLED"))
        elif a < 0.60:
            problems += T.lua_list(fire("UNIT_COMBAT", "player", rnd.choice(["WOUND", "HEAL", "DODGE"]), "", rnd.randint(1, 200), 1))
        elif a < 0.64:
            lua.execute("STUB.form = %d" % rnd.choice([0, 1, 2, 3]))
            problems += T.lua_list(fire("UPDATE_SHAPESHIFT_FORM"))
        elif a < 0.67:
            z, m = rnd.choice(ZONES)
            lua.execute('STUB.zone = %r STUB.map = %d' % (z, m))
            problems += T.lua_list(fire("ZONE_CHANGED_NEW_AREA"))
        elif a < 0.70:
            problems += T.lua_list(fire(rnd.choice(["BAG_UPDATE_DELAYED", "SPELLS_CHANGED", "LEARNED_SPELL_IN_TAB",
                                                     "PLAYER_LEVEL_UP", "QUEST_LOG_UPDATE", "MERCHANT_SHOW",
                                                     "MERCHANT_CLOSED", "PLAYER_XP_UPDATE", "UNIT_AURA"]), "player"))
        elif a < 0.72:
            lua.execute("STUB.combat = false")
            problems += T.lua_list(fire("PLAYER_DEAD"))
            problems += T.lua_list(fire("PLAYER_ALIVE"))
            problems += T.lua_list(fire("PLAYER_UNGHOST"))
        elif a < 0.80:
            cmd = rnd.choice(JUNK)
            e = slash(cmd)
            if e:
                problems.append("%s: /okd %r: %s" % (where, cmd[:30], e))
        else:
            problems += T.lua_list(tick(1, 0.25))
        check(where)
        if problems:
            break
    leaked = snapshot_globals(lua) - before - ALLOWED_GLOBALS
    leaked = {g for g in leaked if not g.startswith("OneKey")}  # named frames
    if leaked:
        problems.append("new globals: " + ", ".join(sorted(leaked)))
    return cls, level, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=40, help="runs per class")
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    seeds = [a.seed] if a.seed is not None else range(1, a.runs * len(CLASSES) + 1)
    t0, failed = time.time(), 0
    for seed in seeds:
        cls, level, problems = one_run(seed)
        if problems:
            failed += 1
            print("FAIL seed %d (%s level %d): %s" % (seed, cls.lower(), level, problems[0]))
            for p in problems[1:4]:
                print("     " + p)
    n = len(list(seeds))
    print("\n%d/%d runs passed (%.1fs). Replay a failure: python3 tests/fuzz_test.py --seed N" % (n - failed, n, time.time() - t0))
    if T.COVERAGE:
        T.coverage_report()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
