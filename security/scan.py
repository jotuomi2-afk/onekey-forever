#!/usr/bin/env python3
"""Static security and policy scan for the OneKey addon.

    python3 security/scan.py [addon_dir]      # exit 1 on any finding

What it enforces (see docs/ARCHITECTURE.md, "Security"):

  R1 no automation   - no API that acts without a key press: casting, using,
                       targeting or moving from Lua (CastSpellByName, UseAction,
                       TargetUnit, MoveForwardStart, ...). Everything goes
                       through secure buttons the player clicks.
  R2 no network      - nothing leaves the computer: no chat/whisper/addon
                       messages, no mail, no guild/channel calls.
  R3 no dynamic code - no loadstring/RunScript/getfenv/setfenv, no
                       executing strings.
  R4 no secret maths - health and power values are never compared or
                       computed on (WoW: Forever keeps them secret).
  R5 secrets/PII     - no tokens, keys or e-mail addresses in the code.
  R6 data licence    - QuestData.lua keeps the pfQuest MIT notice.
  R7 package content - only .lua/.toc/.xml/.md/LICENSE files in the addon.
"""
import os, re, sys

FORBIDDEN_CALLS = {
    "R1": ["CastSpellByName", "CastSpellByID", "CastSpell", "UseAction", "UseItemByName", "UseInventoryItem",
           "UseContainerItem", "TargetUnit", "TargetNearestEnemy", "AssistUnit", "AttackTarget", "StartAttack",
           "MoveForwardStart", "MoveBackwardStart", "TurnLeftStart", "TurnRightStart", "StrafeLeftStart",
           "StrafeRightStart", "JumpOrAscendStart", "ToggleAutoRun", "InteractUnit", "SpellStopCasting",
           "CancelShapeshiftForm", "RunMacro", "RunMacroText", "PetAttack", "CameraOrSelectOrMoveStart",
           "AcceptTrade", "AcceptGroup", "ConfirmLootSlot", "LootSlot", "BuyMerchantItem", "PickupContainerItem"],
    "R2": ["SendChatMessage", "SendAddonMessage", "C_ChatInfo.SendAddonMessage", "SendMail", "BNSendWhisper",
           "BNSendGameData", "GuildInvite", "InviteUnit", "JoinChannelByName", "C_ChatInfo.SendChatMessage"],
    "R3": ["loadstring", "RunScript", "getfenv", "setfenv", "load", "dofile", "require"],
}
SECRET_APIS = ["UnitHealth", "UnitPower", "UnitHealthPercent", "UnitPowerPercent", "UnitHealthMissing"]
TOKEN_PATTERNS = [r"ghp_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}", r"sk-[A-Za-z0-9]{20,}",
                  r"AKIA[0-9A-Z]{16}", r"xox[baprs]-[A-Za-z0-9-]{10,}", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}"]
ALLOWED_EXT = (".lua", ".toc", ".xml", ".md")
ALLOWED_NAMES = ("LICENSE",)


def strip_comments_and_strings(src):
    """Remove Lua comments and string contents so that names inside them
    (macro text like "/cast Claw", or this kind of note) do not count."""
    src = re.sub(r"--\[(=*)\[.*?\]\1\]", "", src, flags=re.S)
    src = re.sub(r"--[^\n]*", "", src)
    src = re.sub(r"\[(=*)\[.*?\]\1\]", '""', src, flags=re.S)
    src = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', src)
    src = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", src)
    return src


def scan(addon_dir):
    findings = []
    for name in sorted(os.listdir(addon_dir)):
        path = os.path.join(addon_dir, name)
        if os.path.isdir(path):
            findings.append((name, 0, "R7", "directory in the package"))
            continue
        if not (name.endswith(ALLOWED_EXT) or name in ALLOWED_NAMES):
            findings.append((name, 0, "R7", "file type not allowed in the package"))
            continue
        raw = open(path, encoding="utf-8", errors="replace").read()
        for pat in TOKEN_PATTERNS:
            for m in re.finditer(pat, raw):
                line = raw.count("\n", 0, m.start()) + 1
                findings.append((name, line, "R5", "looks like a secret or an address: " + m.group(0)[:12] + "..."))
        if not name.endswith(".lua"):
            continue
        code = strip_comments_and_strings(raw)
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            for rule, names in FORBIDDEN_CALLS.items():
                for fn in names:
                    # a call or a reference to the global, not a field of our own tables
                    if re.search(r"(?<![\w.:])%s\s*[\(\"']" % re.escape(fn), line) or \
                       re.search(r"(?<![\w.:])%s\s*[,)]" % re.escape(fn), line) and rule != "R3":
                        findings.append((name, i, rule, "uses " + fn))
            for api in SECRET_APIS:
                # the value of a secret API used in a comparison or arithmetic on the same line
                if re.search(r"(?<![\w.])%s\s*\([^)]*\)\s*(?:[<>]=?|==|~=|[-+*/%%])" % api, line) or \
                   re.search(r"(?:[<>]=?|==|~=|[-+*/%%])\s*%s\s*\(" % api, line):
                    if "Max" not in api:
                        findings.append((name, i, "R4", "compares or computes on " + api))
    qd = os.path.join(addon_dir, "QuestData.lua")
    if os.path.exists(qd):
        head = open(qd, encoding="utf-8").read(2000)
        if "pfQuest" not in head or "MIT" not in head:
            findings.append(("QuestData.lua", 1, "R6", "pfQuest MIT notice missing"))
    return findings


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "OneKeyDruid")
    f = scan(d)
    for x in f:
        print("%s:%d [%s] %s" % x)
    print("%d finding(s)" % len(f))
    sys.exit(1 if f else 0)
