#!/usr/bin/env python3
"""Tests for the tests: plants known faults in a copy of the addon and checks
that the suite catches each one. If a guard stops catching its fault, this
fails, so a weakened test cannot slip through unnoticed.

    python3 tests/mutation_check.py
"""
import os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (name, file, anchor, inserted after the anchor, test that must fail)
MUTANTS = [
    ("secret health compared", "Core.lua", "local function update()\n",
     '\tif UnitHealth("player") < 100 then return end\n', "smoke: druid"),
    ("spell cast from Lua (automation)", "Core.lua", "local function update()\n",
     '\tif false then CastSpellByName("Wrath") end\n', "security"),
    ("chat message sent (network)", "OneKey.lua", "local function update()\n",
     '\tif false then SendChatMessage("hi", "SAY") end\n', "security"),
    ("secure button changed in combat (taint)", "Core.lua", "local function enterCombat()\n",
     '\tif C_Timer then end\n', None),  # placeholder replaced below
    ("macro over 255 characters", "Logic.lua", "\tlocal fight = fit(L)\n",
     '\tfight = fight .. ("\\n/say x"):rep(60)\n', "macro"),
    ("pfQuest licence notice removed", "QuestData.lua", None, None, "security"),
]


def run_suite(root, only):
    r = subprocess.run([sys.executable, "-I", os.path.join(root, "tests", "run_tests.py"), "-k", only],
                       capture_output=True, text=True)
    return r.returncode, r.stdout


def main():
    failures = []
    for name, f, anchor, insert, must_fail in MUTANTS:
        tmp = tempfile.mkdtemp()
        dst = os.path.join(tmp, "repo")
        shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "dist", "__pycache__"))
        path = os.path.join(dst, "OneKeyDruid", f)
        src = open(path, encoding="utf-8").read()
        if name.startswith("secure button"):
            # change the fight button in the middle of a fight
            anchor, insert, must_fail = "local function combatHud()\n", '\tbutton:SetAttribute("macrotext", "")\n', "smoke: druid"
        if anchor is None:
            src = src.replace("pfQuest", "someone").replace("MIT", "")
        else:
            if anchor not in src:
                print("STALE   %s: anchor not found in %s (update the mutant)" % (name, f))
                failures.append(name)
                continue
            src = src.replace(anchor, anchor + insert, 1)
        open(path, "w", encoding="utf-8").write(src)
        code, out = run_suite(dst, must_fail)
        caught = code != 0
        print(("CAUGHT  " if caught else "MISSED  ") + name)
        if not caught:
            failures.append(name)
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d/%d faults caught" % (len(MUTANTS) - len(failures), len(MUTANTS)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
