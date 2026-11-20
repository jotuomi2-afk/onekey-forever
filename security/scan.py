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
    "R1": ["CastSpellByName", "CastSpellByID", "CastSpell", "CastShapeshiftForm", "UseAction", "UseItemByName",
           "UseInventoryItem", "UseContainerItem", "C_Container.UseContainerItem", "TargetUnit", "TargetNearestEnemy",
           "TargetNearest", "AssistUnit", "AttackTarget", "StartAttack", "MoveForwardStart", "MoveBackwardStart",
           "TurnLeftStart", "TurnRightStart", "StrafeLeftStart", "StrafeRightStart", "JumpOrAscendStart",
           "ToggleAutoRun", "InteractUnit", "SpellStopCasting", "CancelShapeshiftForm", "RunMacro", "RunMacroText",
           "PetAttack", "CameraOrSelectOrMoveStart", "AcceptTrade", "AcceptGroup", "ConfirmLootSlot", "LootSlot",
           "BuyMerchantItem", "PickupContainerItem", "PlaceAction", "PickupSpell", "C_Spell.PickupSpell",
           "CreateMacro", "EditMacro", "SetOverrideBindingSpell", "SetOverrideBindingMacro",
           "SetOverrideBindingItem", "SetBindingSpell", "SetBindingMacro", "SetBindingItem", "C_Timer.NewTicker",
           "SecureCmdOptionParse"],
    "R2": ["SendChatMessage", "SendAddonMessage", "C_ChatInfo.SendAddonMessage", "C_ChatInfo.SendAddonMessageLogged",
           "SendMail", "BNSendWhisper", "BNSendGameData", "GuildInvite", "InviteUnit", "JoinChannelByName",
           "C_ChatInfo.SendChatMessage", "ChatEdit_SendText", "C_Club.SendMessage", "C_BattleNet.SendWhisper"],
    "R3": ["loadstring", "RunScript", "getfenv", "setfenv", "load", "dofile", "loadfile", "require", "getglobal",
           "setglobal", "rawget", "rawset"],
}
# Uses that were reviewed and are allowed, each with its reason. A name that
# is allowed here is still a finding anywhere else.
ALLOWED_USES = {
    ("Ranks.lua", "PlaceAction"): "replaces a lower rank on the player's own bars, out of combat, once",
    ("Ranks.lua", "PickupSpell"): "the spell to place, see PlaceAction",
    ("Ranks.lua", "C_Spell.PickupSpell"): "the spell to place, see PlaceAction",
    ("Core.lua", "CreateMacro"): "/okd macros, and the OKD Prowl macro once: macros the player presses himself",
    ("Core.lua", "EditMacro"): "puts the addon's own OKD Prowl macro right (its cat form number); no other macro",
}
SECRET_APIS = ["UnitHealth", "UnitPower", "UnitHealthPercent", "UnitPowerPercent", "UnitHealthMissing"]
TOKEN_PATTERNS = [r"ghp_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}", r"sk-[A-Za-z0-9]{20,}",
                  r"AKIA[0-9A-Z]{16}", r"xox[baprs]-[A-Za-z0-9-]{10,}", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}"]
ALLOWED_EXT = (".lua", ".toc", ".xml", ".md")
ALLOWED_NAMES = ("LICENSE",)
ALL_FORBIDDEN = {fn: rule for rule, names in FORBIDDEN_CALLS.items() for fn in names}
# _G may only be written with a literal key prefix, for the binding labels
_G_WRITE_OK = ("BINDING_HEADER_", "BINDING_NAME_")


def tokenize(src):
    """A Lua 5.1 lexer: yields (kind, text, line). Comments are dropped;
    strings come out as one token with their decoded-enough content."""
    i, n, line, out = 0, len(src), 1, []
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1; i += 1; continue
        if c in " \t\r":
            i += 1; continue
        if src.startswith("--", i):
            m = re.match(r"--\[(=*)\[", src[i:])
            if m:
                close = "]" + m.group(1) + "]"
                j = src.find(close, i)
                j = n if j < 0 else j + len(close)
            else:
                j = src.find("\n", i)
                j = n if j < 0 else j
            line += src.count("\n", i, j); i = j; continue
        m = re.match(r"\[(=*)\[", src[i:])
        if m:
            close = "]" + m.group(1) + "]"
            j = src.find(close, i)
            j = n if j < 0 else j + len(close)
            out.append(("str", src[i + len(m.group(0)):j - len(close)], line))
            line += src.count("\n", i, j); i = j; continue
        if c in "\"'":
            j, buf = i + 1, []
            while j < n and src[j] != c:
                if src[j] == "\\" and j + 1 < n:
                    buf.append(src[j:j + 2]); j += 2; continue
                if src[j] == "\n":
                    break
                buf.append(src[j]); j += 1
            out.append(("str", "".join(buf), line)); i = j + 1; continue
        m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", src[i:])
        if m:
            out.append(("name", m.group(0), line)); i += len(m.group(0)); continue
        m = re.match(r"0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+", src[i:])
        if m:
            out.append(("num", m.group(0), line)); i += len(m.group(0)); continue
        m = re.match(r"\.\.\.|\.\.|==|~=|<=|>=|.", src[i:], re.S)
        out.append(("op", m.group(0), line)); i += len(m.group(0))
    return out


def blank_code(tokens):
    """Code lines with every string replaced by "" (for the R4 line regexes)."""
    lines = {}
    for kind, text, line in tokens:
        lines.setdefault(line, []).append('""' if kind == "str" else text)
    return {ln: " ".join(parts) for ln, parts in lines.items()}


def scan_lua(name, src, findings):
    toks = tokenize(src)

    def hit(line, rule, msg):
        findings.append((name, line, rule, msg))

    def check_name(full, line):
        rule = ALL_FORBIDDEN.get(full)
        if rule and (name, full) not in ALLOWED_USES:
            hit(line, rule, "uses " + full)

    for k, (kind, text, line) in enumerate(toks):
        prev = toks[k - 1] if k else ("op", "", 0)
        if kind == "name":
            if prev[1] in (".", ":"):
                # a field: only _G.X and C_Something.X count
                base = toks[k - 2] if k >= 2 else ("op", "", 0)
                if base[0] == "name" and base[1] == "_G":
                    check_name(text, line)
                elif base[0] == "name" and (k < 3 or toks[k - 3][1] not in (".", ":")):
                    check_name(base[1] + "." + text, line)
                continue
            check_name(text, line)
            if text == "_G":
                nxt = toks[k + 1] if k + 1 < len(toks) else ("op", "", 0)
                if nxt[1] == "[":
                    key = toks[k + 2] if k + 2 < len(toks) else ("op", "", 0)
                    after = toks[k + 3] if k + 3 < len(toks) else ("op", "", 0)
                    literal = key[0] == "str" and after[1] == "]"
                    if literal:
                        check_name(key[1], line)
                    elif not (key[0] == "str" and key[1].startswith(_G_WRITE_OK)):
                        hit(line, "R3", "_G indexed with a computed key")
        elif kind == "str":
            # an API name as a whole string is a lookup waiting to happen
            if text in ALL_FORBIDDEN and (name, text) not in ALLOWED_USES:
                hit(line, ALL_FORBIDDEN[text], "string names " + text)
    for i, line in blank_code(toks).items():
        for api in SECRET_APIS:
            if re.search(r"(?<![\w.])%s\s*\([^)]*\)\s*(?:[<>]=?|==|~=|[-+*/%%^]|\.\.)" % api, line) or \
               re.search(r"(?:[<>]=?|==|~=|[-+*/%%^]|\.\.)\s*%s\s*\(" % api, line):
                hit(i, "R4", "compares or computes on " + api)


def xml_scripts(src):
    """Inline Lua in an XML file: <Script> bodies and On* handler bodies or attributes."""
    for m in re.finditer(r"<(Script|Binding|On\w+)([^>]*)>(.*?)</\1>", src, re.S):
        yield src.count("\n", 0, m.start()) + 1, m.group(3)
    for m in re.finditer(r"\b(On\w+)\s*=\s*\"([^\"]*)\"", src):
        yield src.count("\n", 0, m.start()) + 1, m.group(2)


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
        if name.endswith(".lua") and name != "QuestData.lua":
            scan_lua(name, raw, findings)
        elif name.endswith(".xml"):
            for line, body in xml_scripts(raw):
                sub = []
                scan_lua(name, body, sub)
                findings += [(n, line + l - 1, r, "inline script: " + msg) for n, l, r, msg in sub]
                if re.search(r"\bfile\s*=", body):
                    findings.append((name, line, "R3", "script loaded from a file"))
            for m in re.finditer(r"<Script[^>]*\bfile\s*=", raw):
                findings.append((name, raw.count("\n", 0, m.start()) + 1, "R3", "XML loads a script file"))
    qd = os.path.join(addon_dir, "QuestData.lua")
    if os.path.exists(qd):
        text = open(qd, encoding="utf-8").read()
        head = text[:2000]
        if "pfQuest" not in head or "MIT" not in head or "extract_pfquest.py" not in head:
            findings.append(("QuestData.lua", 1, "R6", "pfQuest MIT notice or generator line missing"))
        low = text.lower()
        for other in ("questie", "polestar", "wago.tools", "wowhead", "classicdb", "aowow"):
            at = low.find(other)
            if at >= 0:
                findings.append(("QuestData.lua", text.count("\n", 0, at) + 1, "R6", "data from another source: " + other))
        # data only: the file may hold tables and strings, no calls of its own
        toks = tokenize(text)
        for k, (kind, t, line) in enumerate(toks):
            if kind == "name" and t not in ("local", "return", "true", "false", "nil", "QuestData", "ns",
                                             "select", "Q", "N", "O", "I", "_", "ADDON", "addon") \
                    and k + 1 < len(toks) and toks[k + 1][1] == "(":
                if t not in ("select",):
                    findings.append(("QuestData.lua", line, "R3", "data file calls " + t))
                    break
    return findings


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "OneKeyDruid")
    f = scan(d)
    for x in f:
        print("%s:%d [%s] %s" % x)
    print("%d finding(s)" % len(f))
    sys.exit(1 if f else 0)
