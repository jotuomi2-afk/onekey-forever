#!/usr/bin/env python3
"""Tests for the tests: plants known faults in a copy of the addon and checks
that the suite catches each one, with the right message. If a guard stops
catching its fault, this fails, so a weakened test cannot slip through.

    python3 tests/mutation_check.py

First the unchanged copy must pass the whole suite (a broken suite "catches"
everything). Then each mutant must make the named test fail, and the output
must contain the mutant's expected text, so a fault caught for the wrong
reason does not count.
"""
import os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (name, file, anchor, text inserted after the anchor, test to run, text the failure must contain)
MUTANTS = [
    ("secret health compared", "Core.lua", "local function update()\n",
     '\tif UnitHealth("player") < 100 then return end\n', "smoke: druid", "compare"),
    ("spell cast from Lua (automation)", "Core.lua", "local function update()\n",
     '\tif false then CastSpellByName("Wrath") end\n', "security", "uses CastSpellByName"),
    ("automation hidden behind _G", "OneKey.lua", "local function update()\n",
     '\tif false then _G.UseAction(1) end\n', "security", "uses UseAction"),
    ("API name built from strings", "Ranks.lua", "local function run(say)\n",
     '\tlocal f = _G["Cast" .. "SpellByName"]\n', "security", "computed key"),
    ("dynamic code", "QuestHelp.lua", "local _, ns = ...\n",
     'local _ls = loadstring\n', "security", "uses loadstring"),
    ("chat message sent (network)", "OneKey.lua", "local function update()\n",
     '\tif false then SendChatMessage("hi", "SAY") end\n', "security", "uses SendChatMessage"),
    ("script in XML", "Bindings.xml", "</Bindings>",
     None, "security", "inline script"),
    ("secure button changed in combat (taint)", "Core.lua", "local function combatHud()\n",
     '\tbutton:SetAttribute("macrotext", "")\n', "smoke: druid", "in combat"),
    ("macro over 255 characters", "Logic.lua", "\tlocal fight = fit(L)\n",
     '\tfight = fight .. ("\\n/say x"):rep(60)\n', "macro", "chars"),
    ("pull spell dropped from the macro", "Logic.lua", "\tlocal fight = fit(L)\n",
     '\tfight = fight:gsub("nocombat", "combat")\n', "macro", "out-of-combat pull"),
    ("a pre-fight offer that fails holds the key", "OneKey.lua", "local function mayTry(tag, now)\n",
     '\tif true then return true end\n', "priest", "holds the key"),
    ("a reactive spell is named when it cannot be used", "OneKey.lua",
     "\t\t\t\tshow = ok and not secret(usable) and usable == true\n",
     '\t\t\t\tshow = true\n', "warrior", "a hint with nothing usable"),
    ("pfQuest licence notice removed", "QuestData.lua", None, None, "security", "MIT notice"),
    ("data from another quest database", "QuestData.lua", "local _, ns = ...\n",
     "-- merged from QuestieDB\n", "security", "another source"),
    ("data from another database, deep in the file", "QuestData.lua", "$END",
     "\n-- extra quests from wowhead\n", "security", "another source"),
]


def run_suite(root, only=None):
    cmd = [sys.executable, "-I", os.path.join(root, "tests", "run_tests.py")]
    if only:
        cmd += ["-k", only]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def copy_repo():
    tmp = tempfile.mkdtemp()
    dst = os.path.join(tmp, "repo")
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "dist", "__pycache__"))
    return tmp, dst


def main():
    tmp, dst = copy_repo()
    code, out = run_suite(dst)
    shutil.rmtree(tmp, ignore_errors=True)
    if code != 0:
        print("BASELINE FAILED: the unchanged suite must pass before mutants mean anything")
        print(out[-2000:])
        sys.exit(2)
    print("baseline: the unchanged suite passes")
    failures = []
    for name, f, anchor, insert, only, expect in MUTANTS:
        tmp, dst = copy_repo()
        path = os.path.join(dst, "OneKeyDruid", f)
        src = open(path, encoding="utf-8").read()
        if f == "Bindings.xml":
            src = src.replace(anchor, '\t<Binding name="X">CastSpellByName("Wrath")</Binding>\n' + anchor, 1)
        elif anchor is None:
            src = src.replace("pfQuest", "someone").replace("MIT", "")
        elif anchor == "$END":
            src = src + insert
        else:
            if anchor not in src:
                print("STALE   %s: anchor not found in %s (update the mutant)" % (name, f))
                failures.append(name)
                shutil.rmtree(tmp, ignore_errors=True)
                continue
            src = src.replace(anchor, anchor + insert, 1)
        open(path, "w", encoding="utf-8").write(src)
        code, out = run_suite(dst, only)
        caught = code != 0 and expect in out
        why = "" if caught else ("  (suite passed)" if code == 0 else "  (failed without %r)" % expect)
        print(("CAUGHT  " if caught else "MISSED  ") + name + why)
        if not caught:
            failures.append(name)
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d/%d faults caught" % (len(MUTANTS) - len(failures), len(MUTANTS)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
