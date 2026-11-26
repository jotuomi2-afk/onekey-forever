-- OneKeyDruid/Casting.lua: is the target casting a spell right now?
-- From the client's own cast events for the unit "target" (they fire for
-- enemies too). It only answers a question for the HUD's text: which key
-- holds the interrupt. Nothing is cast, pressed or targeted from here.
local _, ns = ...

local TC = { till = 0, kind = nil }
ns.TargetCast = TC

local function secret(v)
	return v ~= nil and issecretvalue ~= nil and issecretvalue(v) and true or false
end

-- When the cast ends, if the client says so in plain numbers (ms); else a
-- guess: most mob casts are done in three seconds, a channel in five.
local function ends(info, guess, channel)
	local now = GetTime()
	if info then
		-- "not interruptible" is the 8th value of a cast, the 7th of a channel
		local ok, _, _, _, _, endMs, _, v7, v8 = pcall(info, "target")
		local shielded = v8
		if channel then shielded = v7 end
		if ok then
			-- a cast the client marks as not interruptible is not worth a key
			if not secret(shielded) and shielded == true then return 0 end
			if not secret(endMs) and type(endMs) == "number" and endMs / 1000 > now then
				return math.min(endMs / 1000, now + 12)
			end
		end
	end
	return now + guess
end

local function probe()
	-- a new target may be in the middle of a cast: only a plain answer counts
	TC.till, TC.kind = 0, nil
	for kind, info in pairs({ cast = UnitCastingInfo, channel = UnitChannelInfo }) do
		if info then
			local ok, name = pcall(info, "target")
			if ok and not secret(name) and name ~= nil then
				TC.till, TC.kind = ends(info, kind == "cast" and 3 or 5, kind == "channel"), kind
				if TC.till == 0 then TC.kind = nil end
			end
		end
	end
end

function TC.Active(now)
	return (now or GetTime()) < TC.till
end

local f = CreateFrame("Frame")
f:SetScript("OnEvent", function(_, event, unit)
	if event == "PLAYER_TARGET_CHANGED" then
		probe()
	elseif unit ~= "target" then
		return
	elseif event == "UNIT_SPELLCAST_START" then
		TC.till, TC.kind = ends(UnitCastingInfo, 3), "cast"
	elseif event == "UNIT_SPELLCAST_CHANNEL_START" then
		TC.till, TC.kind = ends(UnitChannelInfo, 5, true), "channel"
	elseif event == "UNIT_SPELLCAST_SUCCEEDED" and TC.kind == "channel" then
		-- a channel reports "succeeded" as it begins: it goes on
		return
	else
		-- stopped, done, failed or interrupted
		TC.till, TC.kind = 0, nil
	end
end)
pcall(f.RegisterEvent, f, "PLAYER_TARGET_CHANGED")
for _, e in ipairs({ "UNIT_SPELLCAST_START", "UNIT_SPELLCAST_CHANNEL_START", "UNIT_SPELLCAST_STOP",
	"UNIT_SPELLCAST_CHANNEL_STOP", "UNIT_SPELLCAST_INTERRUPTED", "UNIT_SPELLCAST_FAILED",
	"UNIT_SPELLCAST_SUCCEEDED" }) do
	pcall(f.RegisterUnitEvent, f, e, "target")
end
