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
    ("hammering the key holds a pre-fight offer", "OneKey.lua", "\tif t.skip then return false end\n",
     '\tif fightPress > t.offered then t.pressed = fightPress end\n', "try once", "hammering"),
    ("a secret usable answer read as yes", "OneKey.lua",
     "\t\t\t\tlocal ok, usable = pcall(C_Spell.IsSpellUsable, name)\n",
     '\t\t\t\tif secret(usable) then usable = true end\n', "hints fail closed", "a hint from a secret answer"),
    ("automation behind an alias table", "OneKey.lua", "local function update()\n",
     '\tlocal m = C_Macro if false then m.RunMacroText("/cast Wrath") end\n', "security", "RunMacroText as a field"),
    ("a button clicked from Lua", "QuestList.lua", "local function paint()\n",
     '\tif false then OneKeyMain:Click() end\n', "security", "Click as a field"),
    ("a timer that could act", "OneKey.lua", "local function update()\n",
     '\tif false then C_Timer.NewTimer(1, update) end\n', "security", "uses C_Timer.NewTimer"),
    ("secret health behind another name", "Core.lua", "local function update()\n",
     '\tlocal hp = UnitHealth\n', "security", "takes UnitHealth as a value"),
    ("All The Things licence notice removed", "QuestDataNew.lua", "local _, ns = ...\n",
     None, "security", "All The Things MIT notice"),
    ("Questie data in the Forever quest file", "QuestDataNew.lua", "local _, ns = ...\n",
     "-- merged from QuestieDB\n", "security", "another source"),
    ("_G under another name", "OneKey.lua", "local function update()\n",
     '\tlocal g = _G if false then g["Cast" .. "SpellByName"]("Wrath") end\n', "security", "_G used as a value"),
    ("an API name spelt with an escape", "OneKey.lua", "local function update()\n",
     '\tif false then _G["CastSpellByN\\97me"]("Wrath") end\n', "security", "string names CastSpellByName"),
    ("code in a data file", "QuestDataNew.lua", "ns.QDBX = {\n",
     '[1]="x", [2]=RunMacroText"/cast Wrath",\n', "security", "not a data record"),
    ("the list breaks on a hand-in elsewhere", "QuestHelp.lua", "\t\telse\n\t\t\tfar[#far + 1] = e\n",
     '\t\t\tfar[#far] = { e = e }\n', "solo: a finished quest", "QH.Plan raised"),
    ("the probe helper called with a built path", "Core.lua", "local function update()\n",
     '\tif false then call("Cast" .. "SpellByName", "Wrath") end\n', "security", "not a literal"),
    ("a fight's presses count as the try for a buff", "OneKey.lua",
     "\t\t\tfightPress, pressedOffer = GetTime(), (not locked()) and onKey or nil\n",
     '\t\t\tif locked() then pressedOffer = "buff:ai" end\n', "try once: a fight", "attacked first"),
    ("pfQuest licence notice removed", "QuestData.lua", None, None, "security", "MIT notice"),
    ("data from another quest database", "QuestData.lua", "local _, ns = ...\n",
     "-- merged from QuestieDB\n", "security", "another source"),
    ("data from another database, deep in the file", "QuestData.lua", "$END",
     "\n-- extra quests from wowhead\n", "security", "another source"),
    ("the session line loses the addon version", "OneKey.lua", "local function logStart()\n",
     '\tlocal VERSION = nil\n', "log: every class", "addon version"),
    ("release: the scan step switched off", "../.github/workflows/release.yml", "      - run: python3 -I security/scan.py\n",
     "        if: false\n", "release: a new version", "condition was added"),
    ("release: the beta upload called as a release", "../.github/workflows/release.yml", "      prerelease: true",
     " # was\n      prerelease: false", "release: a new version", "line is gone or changed"),
    ("promote: the checksum no longer stops it", "../.github/workflows/promote.yml", 'sha256sum -c "OneKeyForever-$v.zip.sha256"',
     " || true", "release: a new version", "line is gone or changed"),
    ("druid: Dash on Alt+G although it is on its cooldown", "Logic.lua",
     "\t\t\tout.run = (\"/cast [noform:%d] %s\\n/cast [form:%d] %s\"):format(C, N.cat, C, N.dash)\n",
     "\t\t\tout.runSlow = out.run\n", "druid: Alt+G runs", "without Dash at 30"),
    ("druid: Dash's own cast is not remembered", "Core.lua", "\t\t\t\tif name == N.dash then dashAt = GetTime() end\n",
     "\t\t\t\tdashAt = -300\n", "druid: Alt+G runs", "cast seconds ago"),
    ("druid: the elite hint reads the class unguarded", "Core.lua", "local function targetElite()\n",
     '\tif UnitClassification("target") == "elite" then return true end\n', "druid: Alt+G runs", "on a friendly target"),
    ("druid: in the water the HUD sends a fighting cat into Aquatic Form", "Core.lua",
     '\t\treturn UnitCanAttack and UnitCanAttack("player", "target"), UnitIsDead and UnitIsDead("target")\n\tend)\n',
     "\tfoe = false\n", "druid: in water F holds", "an enemy as the target"),
    ("druid: the finisher plans never take turns", "Core.lua",
     '\tif event == "PLAYER_REGEN_ENABLED" and db then db.biteTurn = not db.biteTurn end\n',
     "\tif db then db.biteTurn = false end\n", "druid: Rip and the Bite take turns", "do not take turns"),
    ("druid: the big warnings are never shown", "Core.lua", "local function setAlert(text)\n",
     "\tdo return end\n", "druid: the warnings are shown big", "the big text says"),
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
        elif insert is None and f == "QuestDataNew.lua":
            src = src.replace("All The Things", "someone").replace("MIT", "")
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
