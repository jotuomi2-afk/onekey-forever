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
  R6 data licence    - QuestData.lua keeps the pfQuest MIT notice, QuestDataNew.lua
                       the All The Things MIT notice; no other source in either.
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
           "C_Timer.NewTimer", "SecureCmdOptionParse", "Click", "securecall", "securecallfunction", "RunBinding",
           "FollowUnit", "TargetLastEnemy", "TargetLastTarget", "ClearTarget", "PetFollow", "PetPassiveMode",
           "DoEmote", "RepopMe", "AcceptResurrect", "AcceptQuest", "CompleteQuest", "GetQuestReward",
           "SelectGossipOption", "ChatEdit_ParseText", "MoveAndSteerStart", "ToggleRun", "SitStandOrDescendStart"],
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
# Findings that were reviewed and are allowed, each a fixed number of times
# in one file: one more of the same in that file is a finding again.
ALLOWED_FINDINGS = {
    ("Core.lua", "R3", "_G used as a value"): (1, "/okd probe walks a dotted API path to show what the client lets an addon read; it only prints"),
    ("Core.lua", "R4", "string names UnitPower"): (1, "/okd probe prints whether the value is secret; it is never compared"),
    ("Core.lua", "R4", "string names UnitHealth"): (1, "/okd probe, as above"),
}
SECRET_APIS = ["UnitHealth", "UnitPower", "UnitHealthPercent", "UnitPowerPercent", "UnitHealthMissing"]
TOKEN_PATTERNS = [r"ghp_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}", r"sk-[A-Za-z0-9]{20,}",
                  r"AKIA[0-9A-Z]{16}", r"xox[baprs]-[A-Za-z0-9-]{10,}", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}"]
ALLOWED_EXT = (".lua", ".toc", ".xml", ".md")
ALLOWED_NAMES = ("LICENSE",)
ALL_FORBIDDEN = {fn: rule for rule, names in FORBIDDEN_CALLS.items() for fn in names}
# the last part of every forbidden name: as a field of any table
# (m.RunMacroText, C_Item.UseItemByName, button:Click) it is the same call
# behind another name. Lua's own library words are left to their bare form.
FORBIDDEN_FIELDS = {fn.split(".")[-1]: rule for fn, rule in ALL_FORBIDDEN.items()
                    if fn.split(".")[-1] not in ("load", "require", "rawget", "rawset")}
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
                    nxt = toks[k + 1] if k + 1 < len(toks) else ("op", "", 0)
                    if text in SECRET_APIS and nxt[1] != "(":
                        hit(line, "R4", "takes " + text + " as a value")
                elif base[0] == "name" and (k < 3 or toks[k - 3][1] not in (".", ":")):
                    check_name(base[1] + "." + text, line)
                rule = FORBIDDEN_FIELDS.get(text)
                if rule and not any(f == name and a.split(".")[-1] == text for f, a in ALLOWED_USES):
                    full = (base[1] + "." if base[0] == "name" else "") + text
                    if not any(n == name and msg == "uses " + full for n, _, _, msg in findings[-2:]):
                        hit(line, rule, "uses " + text + " as a field of " + (base[1] if base[0] == "name" else "a value"))
                continue
            check_name(text, line)
            # /okd probe's helper calls a global by its dotted path: the
            # path must be written out, never put together
            nxt0 = toks[k + 1] if k + 1 < len(toks) else ("op", "", 0)
            arg0 = toks[k + 2] if k + 2 < len(toks) else ("op", "", 0)
            after0 = toks[k + 3] if k + 3 < len(toks) else ("op", "", 0)
            if text == "call" and nxt0[1] == "(" and prev[1] != "function" and \
                    not (arg0[0] == "str" and after0[1] in (",", ")")):
                hit(line, "R3", "call with a path that is not a literal")
            if text in SECRET_APIS:
                # health and power may be called, or handed to pcall; taken
                # as a value under another name they escape the R4 check
                nxt = toks[k + 1] if k + 1 < len(toks) else ("op", "", 0)
                in_pcall = k >= 2 and prev[1] == "(" and toks[k - 2][1] == "pcall"
                # "if UnitHealthPercent then", "UnitHealthPercent and ...": is it there at all
                if nxt[1] not in ("(", "and", "then") and not in_pcall:
                    hit(line, "R4", "takes " + text + " as a value")
            if text == "_G":
                nxt = toks[k + 1] if k + 1 < len(toks) else ("op", "", 0)
                # _G only as _G.NAME or _G["literal"]: under another name,
                # as an argument or as a metatable it hides every lookup
                if nxt[1] not in (".", "["):
                    hit(line, "R3", "_G used as a value")
                if nxt[1] == "[":
                    key = toks[k + 2] if k + 2 < len(toks) else ("op", "", 0)
                    after = toks[k + 3] if k + 3 < len(toks) else ("op", "", 0)
                    literal = key[0] == "str" and after[1] == "]"
                    if literal:
                        check_name(key[1], line)
                    elif not (key[0] == "str" and key[1].startswith(_G_WRITE_OK)):
                        hit(line, "R3", "_G indexed with a computed key")
        elif kind == "str":
            # an API name as a whole string is a lookup waiting to happen;
            # "\97" is "a", so decimal escapes are read first
            plain = re.sub(r"\\(\d{1,3})", lambda m: chr(int(m.group(1)) % 256), text)
            if plain in ALL_FORBIDDEN and (name, plain) not in ALLOWED_USES:
                hit(line, ALL_FORBIDDEN[plain], "string names " + plain)
            elif plain in SECRET_APIS:
                hit(line, "R4", "string names " + plain)
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


DATA_FRAME = {"QuestData.lua": ("local _, ns = ...", "ns.QDB = { q = {", "}, n = {", "}, o = {", "}, i = {", "} }"),
              "QuestDataNew.lua": ("local _, ns = ...", "ns.QDBX = {", "}")}


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
        if name.endswith(".lua") and name not in ("QuestData.lua", "QuestDataNew.lua"):
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
    # the two data files: each from one named MIT source, by its generator
    for fname, marks, what in (("QuestData.lua", ("pfQuest", "MIT", "extract_pfquest.py"), "pfQuest"),
                               ("QuestDataNew.lua", ("All The Things", "MIT", "extract_att.py"), "All The Things")):
        qd = os.path.join(addon_dir, fname)
        if not os.path.exists(qd):
            continue
        text = open(qd, encoding="utf-8").read()
        head = text[:2000]
        if any(m not in head for m in marks):
            findings.append((fname, 1, "R6", what + " MIT notice or generator line missing"))
        low = text.lower()
        others = ["questie", "polestar", "wago.tools", "wowhead", "classicdb", "aowow"]
        others += ["allthethings", "all the things"] if fname == "QuestData.lua" else ["pfquest"]
        for other in others:
            at = low.find(other, 2000 if other == "pfquest" else 0)
            if at >= 0:
                findings.append((fname, text.count("\n", 0, at) + 1, "R6", "data from another source: " + other))
        # data only, line by line: a comment, one of the few lines that
        # open and close the tables, or one record [id]="text",
        for n, ln in enumerate(text.split("\n"), 1):
            if ln == "" or ln.startswith("--") or ln in DATA_FRAME[fname]:
                continue
            if not re.match(r'^\[\d+\]="(?:[^"\\]|\\.)*",$', ln):
                findings.append((fname, n, "R3", "not a data record: " + ln[:40]))
                break
        toks = tokenize(text)
        for k, (kind, t, line) in enumerate(toks):
            if kind == "name" and t not in ("local", "return", "true", "false", "nil", "QuestData", "ns",
                                             "select", "Q", "N", "O", "I", "_", "ADDON", "addon") \
                    and k + 1 < len(toks) and toks[k + 1][1] == "(":
                if t not in ("select",):
                    findings.append((fname, line, "R3", "data file calls " + t))
                    break
    # reviewed exceptions, by count
    seen, kept = {}, []
    for f in findings:
        key = (f[0], f[2], f[3])
        seen[key] = seen.get(key, 0) + 1
        if key in ALLOWED_FINDINGS and seen[key] <= ALLOWED_FINDINGS[key][0]:
            continue
        kept.append(f)
    return kept


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "OneKeyDruid")
    f = scan(d)
    for x in f:
        print("%s:%d [%s] %s" % x)
    print("%d finding(s)" % len(f))
    sys.exit(1 if f else 0)
