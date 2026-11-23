-- OneKeyDruid/QuestList.lua: the solo quest list, a window over the plan of
-- QuestHelp.lua. One row per thing to do in this zone, in walking order.
-- Left click: the game's map pin and arrow go to the place, and the chat
-- says what to do there. Right click: leave the quest out for this session.
-- /okd solo opens and closes it; so does the small "Q" button.
--
-- Plain frames only: nothing here is a secure button, so the window may
-- open, close and be clicked in a fight. A click never casts, targets or
-- moves; it sets a waypoint, which the player may also do by hand.

local _, ns = ...
local QH = ns.QH
local QL = {}
ns.QL = QL
if not (QH and QH.Plan) then return end

local ROWS, ROW_H, WIDTH = 10, 30, 430
local COLOR = { solo = "ff7fe07f", new = "ff7fd4ff", hard = "ffffa040", group = "ffff5050", low = "ff9a9a9a",
	hand = "ffffe060", sep = "ffffffff" }
local frame, toggle
local shownRows, offset, isShown = {}, 0, false
local elapsed = 0

local function db()
	OneKeyDruidDB = OneKeyDruidDB or {}
	return OneKeyDruidDB
end
local function fi() return db().lang == "fi" end
local function say(msg) print("|cff7fd4ffOneKey|r " .. msg) end

local function level()
	local l = UnitLevel("player")
	if type(l) ~= "number" or (issecretvalue and issecretvalue(l)) then return 1 end
	return l
end

local function paint()
	if not frame then return end
	local plan = QH.Plan(fi())
	local maxOff = math.max(0, #plan - ROWS)
	if offset > maxOff then offset = maxOff end
	shownRows = {}
	for i = 1, ROWS do
		local r = plan[i + offset]
		local b = frame.rows[i]
		shownRows[i] = r
		if not r then
			b.head:SetText("")
			b.sub:SetText("")
		elseif r.sep then
			b.head:SetText("|c" .. COLOR.sep .. r.sep .. "|r")
			b.sub:SetText("")
		else
			local c = r.e.kind == "hand" and COLOR.hand or COLOR[r.rate] or COLOR.solo
			b.head:SetText("|c" .. c .. r.head .. "|r")
			b.sub:SetText(r.sub or "")
		end
	end
	local zone = GetRealZoneText and GetRealZoneText() or ""
	frame.title:SetText(((fi() and "Yksin tehtävät questit: %s" or "Quests on your own: %s")):format(zone or ""))
	frame.foot:SetText(#plan == 0 and (fi() and "Ei mitään tällä alueella. /okd where kertoo seuraavan alueen."
		or "Nothing in this zone. /okd where names the next zone.")
		or (fi() and "Vasen: karttamerkki ja nuoli · Oikea: ohita · Rulla: selaa"
			or "Left: map pin and arrow · Right: skip · Wheel: scroll"))
end

local function refresh(force)
	if force or QH.Age() > 5 then
		-- the walk through the quest data is for a quiet moment
		if not InCombatLockdown() or force then pcall(QH.Refresh, level()) end
	end
	paint()
end

-- what a click on row i does; button: "LeftButton" / "RightButton"
function QL.Press(i, button)
	local r = shownRows[i]
	if not r or r.sep then return nil end
	if button == "RightButton" then
		local t = QH.Skip(r.e)
		say((fi() and "ohitettu: %s (/okd skip clear palauttaa)" or "left out: %s (/okd skip clear brings it back)"):format(tostring(t)))
		refresh(true)
		return "skip"
	end
	local ok, name = QH.Go(r.e)
	if ok then
		say(r.head)
		if r.sub and r.sub ~= "" then say("  " .. r.sub) end
		say((fi() and "  karttamerkki ja nuoli: %s" or "  map pin and arrow: %s"):format(tostring(name)))
		return "go"
	end
	say(r.head)
	say(fi() and "  paikkaa ei tiedetä; katso pelin omaa questiseurantaa." or "  no place known; see the game's own quest tracker.")
	return "none"
end

local function build()
	frame = CreateFrame("Frame", "OneKeyQuestList", UIParent)
	frame:SetSize(WIDTH, ROWS * ROW_H + 52)
	local p = db().qlPos
	if p then frame:SetPoint(p[1], UIParent, p[2], p[3], p[4]) else frame:SetPoint("LEFT", UIParent, "LEFT", 30, 60) end
	frame:SetFrameStrata("MEDIUM")
	local bg = frame:CreateTexture(nil, "BACKGROUND")
	bg:SetAllPoints(frame)
	bg:SetColorTexture(0, 0, 0, 0.78)
	frame.title = frame:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	frame.title:SetPoint("TOPLEFT", frame, "TOPLEFT", 8, -7)
	frame.foot = frame:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
	frame.foot:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", 8, 6)
	local close = CreateFrame("Button", nil, frame)
	close:SetSize(20, 20)
	close:SetPoint("TOPRIGHT", frame, "TOPRIGHT", -4, -4)
	local x = close:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	x:SetPoint("CENTER")
	x:SetText("x")
	close:SetScript("OnClick", function() QL.Hide() end)
	frame.rows = {}
	for i = 1, ROWS do
		local b = CreateFrame("Button", nil, frame)
		b:SetSize(WIDTH - 12, ROW_H)
		b:SetPoint("TOPLEFT", frame, "TOPLEFT", 6, -26 - (i - 1) * ROW_H)
		b:RegisterForClicks("LeftButtonUp", "RightButtonUp")
		b.head = b:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
		b.head:SetPoint("TOPLEFT", b, "TOPLEFT", 2, -2)
		b.head:SetWidth(WIDTH - 16)
		b.head:SetJustifyH("LEFT")
		b.head:SetWordWrap(false)
		b.sub = b:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
		b.sub:SetPoint("TOPLEFT", b.head, "BOTTOMLEFT", 10, -1)
		b.sub:SetWidth(WIDTH - 26)
		b.sub:SetJustifyH("LEFT")
		b.sub:SetWordWrap(false)
		b:SetScript("OnClick", function(_, button) QL.Press(i, button) end)
		frame.rows[i] = b
	end
	frame:EnableMouseWheel(true)
	frame:SetScript("OnMouseWheel", function(_, delta)
		offset = math.max(0, offset - (delta or 0))
		paint()
	end)
	frame:SetMovable(true)
	frame:EnableMouse(true)
	frame:RegisterForDrag("LeftButton")
	frame:SetScript("OnDragStart", function(f) f:StartMoving() end)
	frame:SetScript("OnDragStop", function(f)
		f:StopMovingOrSizing()
		local a, _, b, px, py = f:GetPoint()
		db().qlPos = { a, b, px, py }
	end)
	frame:SetScript("OnUpdate", function(_, dt)
		if not isShown then return end
		elapsed = elapsed + (dt or 0)
		if elapsed < 1 then return end
		elapsed = 0
		refresh(false)
	end)
	frame:Hide()
end

function QL.Show()
	if not frame then build() end
	isShown, offset = true, 0
	frame:Show()
	refresh(true)
end

function QL.Hide()
	isShown = false
	if frame then frame:Hide() end
end

function QL.Toggle()
	if isShown then QL.Hide() else QL.Show() end
	return isShown
end

function QL.IsShown() return isShown end

-- the rows on screen now: { head, sub, rate, kind } (for the tests and /okd solo print)
function QL.Rows()
	local out = {}
	for i = 1, ROWS do
		local r = shownRows[i]
		if r then out[#out + 1] = r.sep and { sep = r.sep } or { head = r.head, sub = r.sub, rate = r.rate, kind = r.e.kind } end
	end
	return out
end

-- /okd solo [print]: the window, or the same rows in the chat
function QL.Slash(rest)
	if rest == "print" then
		pcall(QH.Refresh, level())
		local plan = QH.Plan(fi())
		if #plan == 0 then say(fi() and "ei mitään tällä alueella." or "nothing in this zone.") end
		for i = 1, math.min(14, #plan) do
			local r = plan[i]
			say(r.sep or r.head)
		end
		return
	end
	if rest == "button" then
		db().questButton = db().questButton == false
		if toggle then if db().questButton == false then toggle:Hide() else toggle:Show() end end
		return
	end
	QL.Toggle()
end

-- the small button that opens the list
local starter = CreateFrame("Frame")
starter:RegisterEvent("PLAYER_LOGIN")
starter:SetScript("OnEvent", function()
	toggle = CreateFrame("Button", "OneKeyQuestButton", UIParent)
	toggle:SetSize(22, 22)
	local p = db().qbPos
	if p then toggle:SetPoint(p[1], UIParent, p[2], p[3], p[4]) else toggle:SetPoint("LEFT", UIParent, "LEFT", 4, 60) end
	local bg = toggle:CreateTexture(nil, "BACKGROUND")
	bg:SetAllPoints(toggle)
	bg:SetColorTexture(0, 0, 0, 0.6)
	local t = toggle:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	t:SetPoint("CENTER")
	t:SetText("Q")
	toggle:RegisterForClicks("LeftButtonUp")
	toggle:SetScript("OnClick", function() QL.Toggle() end)
	toggle:SetMovable(true)
	toggle:RegisterForDrag("LeftButton")
	toggle:SetScript("OnDragStart", function(f) if IsShiftKeyDown() then f:StartMoving() end end)
	toggle:SetScript("OnDragStop", function(f)
		f:StopMovingOrSizing()
		local a, _, b, px, py = f:GetPoint()
		db().qbPos = { a, b, px, py }
	end)
	if db().questButton == false then toggle:Hide() end
end)
