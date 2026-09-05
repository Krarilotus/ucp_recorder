local native = require("code/native")
--[[
Replay implementation
--]]

local utils = require("code/utils")

local validation = require("code/validation")
local Recorder = {}

-- Recorder class
function Recorder:new(params)
  local o = setmetatable({}, {__index = self})
  o:setName(params.name or "test_recording1")
  o.rngLogMethod = params.rngLogMethod or "trace"
  o.RECORDER_STATES = {NONE = 0, RECORD = 1, PLAYBACK = 2}
  o.mode = "none"
  o.MAX_PACKET_SIZE = validation.MAX_PAYLOAD
  o.commandDataAddress = core.allocate(o.MAX_PACKET_SIZE, true)
  o.nextUpCommandTimeAddress = core.allocate(4, true)
  o.commandRecorderState = core.allocate(4, true)
  o.rngRecorderState = core.allocate(4, true)
  o.infoRecorderState = core.allocate(4, true)

  return o
end

function Recorder:setName(name)
  self.name = name
  self.commandsFileName = self.name .. "-commands.json"
  self.rngFileName = self.name .. "-rng-sync.json"
  self.infoFileName = self.name .. "-infself.json"
end

function Recorder:reset()
  self.mode = "none"
  self.nextCommand, self.cachedRNG, self.info, self.mapSeed = nil, nil, nil, nil
  self.lastCommandTime = nil
  core.writeInteger(self.nextUpCommandTimeAddress, 0)
  for _, address in ipairs({self.commandRecorderState, self.rngRecorderState, self.infoRecorderState}) do
    core.writeInteger(address, self.RECORDER_STATES.NONE)
  end
  for _, key in ipairs({"commandsFile", "rngFile", "infoFile"}) do
    local file = self[key]
    self[key] = nil
    if file then file:close() end
  end
end

-- Open the complete set before committing session state. A failed open must
-- leave the current player and the recorder unchanged.
function Recorder:openFiles(mode)
  assert(self.mode == "none", "A replay session is already active")
  local opened, created = {}, {}
  local ok, message = pcall(function()
    if mode == "w" then
      for _, key in ipairs({"commands", "rng", "info"}) do
        local path = self[key .. "FileName"]
        local existing = io.open(path, "r")
        if existing then existing:close(); error("Cannot overwrite recording: " .. path) end
      end
    end
    for _, key in ipairs({"commands", "rng", "info"}) do
      local path = self[key .. "FileName"]
      local file, reason = io.open(path, mode)
      assert(file, "Cannot open recording " .. path .. ": " .. tostring(reason))
      opened[key .. "File"] = file
      if mode == "w" then created[#created + 1] = path end
    end
    if mode == "r" then
      local line = opened.infoFile:read()
      local info = validation.info(line and json:decode(line))
      opened.infoFile:seek("set", 0)
      -- Read all commands before any native mutation, including late corruption.
      while true do
        local commandLine = opened.commandsFile:read()
        if not commandLine then break end
        validation.command(json:decode(commandLine))
      end
      opened.commandsFile:seek("set", 0)
    end
  end)
  if not ok then
    for _, file in pairs(opened) do file:close() end
    for _, path in ipairs(created) do os.remove(path) end
    error(message)
  end
  self.nextCommand, self.cachedRNG, self.lastCommandTime = nil, nil, nil
  self.firstDesync = nil
  for key, file in pairs(opened) do self[key] = file end
end

function Recorder:startRecording()
  self:openFiles("w")
  self.mode = "record"
  core.writeInteger(self.commandRecorderState, self.RECORDER_STATES.RECORD)
  core.writeInteger(self.rngRecorderState, self.RECORDER_STATES.RECORD)
  core.writeInteger(self.infoRecorderState, self.RECORDER_STATES.RECORD)
end

function Recorder:stopRecording() self:reset() end

function Recorder:startPlayback()
  self:openFiles("r")
  self.mode = "play"
  core.writeInteger(self.commandRecorderState, self.RECORDER_STATES.PLAYBACK)
  core.writeInteger(self.rngRecorderState, self.RECORDER_STATES.PLAYBACK)
  core.writeInteger(self.infoRecorderState, self.RECORDER_STATES.PLAYBACK)
end

function Recorder:stopPlayback() self:reset() end

function Recorder:discardFiles()
	os.remove(self.commandsFileName)
	os.remove(self.rngFileName)
	os.remove(self.infoFileName)
end

function Recorder:saveCommand(commandCategory, time, address, size, player)
  local data = json:encode({
    commandCategory = commandCategory,
    time = time,
    data = utils.tableToHex(core.readBytes(address, size)),
    size = size,
    player = player,
  })
  self.commandsFile:write(data .. "\n")
  self.commandsFile:flush()
end

function Recorder:loadCommand()
  local data = self.commandsFile:read() -- reads a line
  if data == nil then
    return nil
  end
  return json:decode(data) -- note that data is returned, not an address to data
end

function Recorder:saveRNG(time, index1, rng1, index2, rng2, extra)
  local data = json:encode({
    time = time,
    index1 = index1,
    rng1 = rng1,
    index2 = index2,
    rng2 = rng2,
    extra = extra,
  })
  self.rngFile:write(data .. "\n")
  self.rngFile:flush()
end

function Recorder:loadRNG()
  local data = self.rngFile:read()
  if data == nil then
    return nil
  end
  return json:decode(data)
end

function Recorder:saveInfo(gameType, mapSeed, matchSeed, RNGvalue1, RNGvalue2, RNGindex1, RNGindex2) -- Saves RNG starting values to replicate game later
  local data = json:encode({
    gameType = gameType,
	mapSeed = mapSeed,
	matchSeed = matchSeed,
	RNGvalue1 = RNGvalue1,
	RNGvalue2 = RNGvalue2,
	RNGindex1 = RNGindex1,
	RNGindex2 = RNGindex2,
  })
  self.infoFile:write(data .. "\n")
  self.infoFile:flush()
end

function Recorder:loadInfo()
  local data = self.infoFile:read()
  if data == nil then
    return nil
  end
  self.info = json:decode(data) -- store in this object I suppose. It is state
  return self.info
end

function Recorder:ScheduleCommandWrapper(commandCategory, player, time, address)
  self._scheduleCommand(native.addr(0x191d768), commandCategory, player, time, address)
end

function Recorder:scheduleCommand(command)
  validation.command(command)
  local bytes = utils.hexToTable(command.data)
  -- The native scheduler derives its own length. Never let a short record expose
  -- stale bytes from the previous command's allocation.
  for i = #bytes + 1, self.MAX_PACKET_SIZE do bytes[i] = 0 end
  core.writeBytes(self.commandDataAddress, bytes)
  self:ScheduleCommandWrapper(command.commandCategory, command.player, command.time, self.commandDataAddress)
end

function Recorder:peekCommand()

  if self.nextCommand == nil then
    self.nextCommand = self:loadCommand()
  end

  if self.nextCommand == nil then
    -- We have reached the end of file: EOF
    core.writeInteger(self.commandRecorderState, self.RECORDER_STATES.NONE)
  end

  return self.nextCommand
end

function Recorder:peekCommandTime()
  local c = self:peekCommand()
  if c == nil then
    return nil
  end
  return c.time
end

function Recorder:consumeSavedCommand()
  local c = self.nextCommand

  if c == nil then
    c = self:peekCommand()
  end

  self.nextCommand = nil

  return c
end

-- native.addr(0x004428b5) SHC
function Recorder:onStartSkirmish(registers) -- SINGLEPLAYER ONLY (TODO make this work for multiplayer too)
	if core.readInteger(self.commandRecorderState) == self.RECORDER_STATES.RECORD then
		local gameRNG1index = core.readInteger(native.addr(0x01a3160c))
		local gameRNG2index = core.readInteger(native.addr(0x01a31608))
		local gameRNG1 = core.readSmallInteger(native.addr(0x01a279c0))
		local gameRNG2 = core.readSmallInteger(native.addr(0x01a279c2))
		local mapSeed = self.mapSeed
		local matchSeed = core.readInteger(native.addr(0x01a279c4))

		self:saveInfo(0, mapSeed, matchSeed, gameRNG1, gameRNG2, gameRNG1index, gameRNG2index)

		print("Saved skirmish information:")
		print(string.format("Gametype=%d, mapSeed=%d, matchSeed=%d, gameRNG1=%d, gameRNG2=%d, gameRNG1index=%d, gameRNG2index=%d", 0, mapSeed, matchSeed, gameRNG1, gameRNG2, gameRNG1index, gameRNG2index))

	elseif core.readInteger(self.commandRecorderState) == self.RECORDER_STATES.PLAYBACK then
		local skirmishInfo = self:loadInfo()
		local populateRNG1040 = core.exposeCode(native.addr(0x0046a760), 1, 1)

		-- Set SEC_CurrentPlayerSlotID to 0 (Disallows actions during playback) TODO move this
		print("recorder in Playback state")
		--core.writeInteger(native.addr(0x01a275dc), 0)

		-- Load mapSeed and fill RNG table
		core.writeInteger(native.addr(0x01a279c4), skirmishInfo.mapSeed)
		populateRNG1040(native.addr(0x01a279c0));

		-- Load matchSeed (populateRNG1040() is called later in LaunchGame() after the map is setup)
		core.writeInteger(native.addr(0x01a279c4), skirmishInfo.matchSeed)

		-- Load starting RNG values
		core.writeInteger(native.addr(0x01a3160c), skirmishInfo.RNGindex1)
		core.writeInteger(native.addr(0x01a31608), skirmishInfo.RNGindex2)
		core.writeSmallInteger(native.addr(0x01a279c0), skirmishInfo.RNGvalue1)
		core.writeSmallInteger(native.addr(0x01a279c2), skirmishInfo.RNGvalue2)

		print("Loaded skirmish information:")
		print(string.format("Gametype=%d, mapSeed=%d, matchSeed=%d, gameRNG1=%d, gameRNG2=%d, gameRNG1index=%d, gameRNG2index=%d", skirmishInfo.gameType, skirmishInfo.mapSeed, skirmishInfo.matchSeed, skirmishInfo.RNGvalue1, skirmishInfo.RNGvalue2, skirmishInfo.RNGindex1, skirmishInfo.RNGindex2))

  end
  return registers
end

-- native.addr(0x00442877) SHC
function Recorder:onBeforeSetMatchSeed(registers) -- SINGLEPLAYER ONLY (TODO make this work for multiplayer too)
  self.mapSeed = core.readInteger(native.addr(0x01a279c4))
	local setTimeBasedSeed = core.exposeCode(native.addr(0x0046a740), 1, 1)

  -- original code
  setTimeBasedSeed(native.addr(0x01a279c0))
  return registers
end

-- native.addr(0x0042bf4c) SHC
function Recorder:onCustomSkirmishGame(registers) -- SINGLEPLAYER ONLY (TODO test if playerIDs work fine in multiplayer)
  -- Make singleplayer skirmishes use real playerID for commands, not -1
  local DAT_QueuedCommandPlayer = native.addr(0x191de0c)
  core.writeInteger(DAT_QueuedCommandPlayer, 01) -- In Singleplayer multiplayerID is always 01
  return registers
end

function Recorder:scheduleNextCommand(registers)
  print("Consuming command")
  local c = self:consumeSavedCommand()
  if c == nil then
    print("... no command left")
    --self.finishedPlayback = true -- already done by peekCommand higher up in the call hierarchy
    core.writeInteger(self.commandRecorderState, self.RECORDER_STATES.NONE)
    return
  end

  print(string.format("Matchtime now: %d", core.readInteger(native.addr(0x01fe7da8))))
  print(string.format("Scheduling the command: Command<type=%d,time=%d,address=%X,size=%d,multiplayerID=%d>", c.commandCategory, c.time, self.commandDataAddress, c.size, c.player))
  self:scheduleCommand(c)

  print("Peeking at the next command")
  local c = self:peekCommand()
  if c == nil then
    print("... no command left")
    --self.finishedPlayback = true -- already done by peekCommand higher up in the call hierarchy
    core.writeInteger(self.commandRecorderState, self.RECORDER_STATES.NONE)
    return
  end

  print(string.format("Setting next trigger time: %d", c.time))
  core.writeInteger(self.nextUpCommandTimeAddress, c.time)
end

function Recorder:onReceiveAllTransmittedCommandsASM(scheduleNextCommandAddress)
	-- Schedules saved commands if commandRecorderState is in PLAYBACK mode
	return {
  core.AssemblyLambda([[
    startOfFunction:
      mov eax, [commandRecorderState]
      cmp eax, 2
      jne endOfFunction

    checkStarted:
      mov eax, dword [SEC_MatchTime]
      cmp eax, 0
      jle endOfFunction

    checkTime:
      add eax, 64
      mov edx, dword [nextUpCommandTimeAddress]
      cmp eax, edx
      jg takeCommand
      jmp endOfFunction

    takeCommand:
      call scheduleNextCommandAddress
      jmp startOfFunction

    endOfFunction:
  ]], {
    commandRecorderState = self.commandRecorderState,
    SEC_MatchTime = native.addr(0x01fe7da8),
    nextUpCommandTimeAddress = self.nextUpCommandTimeAddress,
    scheduleNextCommandAddress = scheduleNextCommandAddress,
  })
}
end

function Recorder:onCommand(commandCategory, time, address, size, player)
  if core.readInteger(self.commandRecorderState) == 1 and time > 0 then
    print(string.format("Recording Command<type=%d,time=%d,address=%X,size=%d,multiplayerID=%d>", commandCategory, time, address, size, player))
    self:saveCommand(commandCategory, time, address, size, player)
  end
end

 -- on sent commands
function Recorder:onTransmitCommand(registers)
  local commandCategory = core.readInteger(registers.ESP + 4)
  local time = core.readInteger(registers.ESP + 8)
  local address = core.readInteger(registers.ESP + 12)
  local size = core.readInteger(registers.ESP + 16)
  -- local idTo = core.readInteger(registers.ESP + 20)
  local player = core.readInteger(native.addr(0x0191de0c))
  print(string.format("Transmitted Command<type=%d,time=%d,address=%X,size=%d,multiplayerID=%d>", commandCategory, time, address, size, player))

  self:onCommand(commandCategory, time, address, size, player)
end

-- on received commands
function Recorder:onScheduleCommand(registers)
  local commandCategory = core.readInteger(registers.ESP + 4 + 0x10)
  local player = core.readInteger(registers.ESP + 8 + 0x10)
  local time = core.readInteger(registers.ESP + 12 + 0x10)
  local address = core.readInteger(registers.ESP + 16 + 0x10)
  local size = core.readInteger(native.addr(0x0194af98))
  print(string.format("Received Command<type=%d,time=%d,address=%X,size=%d,multiplayerID=%d>", commandCategory, time, address, size, player))

  self:onCommand(commandCategory, time, address, size, player)
end

function Recorder:fakeMultiplayerIdentities(registers)
  if self.originalInMultiplayer then
    registers.EDX = 1 -- multiplayer
  else
    registers.EDX = core.readInteger(registers.ECX + 0x618) -- original game mode
  end
  return registers
end

function Recorder:syncCheck(registers, traceF)
  local actual = {
    time = core.readInteger(native.addr(0x01fe7da8)),
    rng1 = core.readSmallInteger(native.addr(0x01a279c0)),
    rng2 = core.readSmallInteger(native.addr(0x01a279c2)),
    index1 = core.readInteger(native.addr(0x01a3160c)),
    index2 = core.readInteger(native.addr(0x01a31608)),
    extra = {},
  }
  if traceF then actual.extra["ra" .. traceF] = core.readInteger(registers.ESP) end
  if self.mode == "record" and core.readInteger(self.rngRecorderState) == 1 then
    self:saveRNG(actual.time, actual.index1, actual.rng1, actual.index2, actual.rng2, actual.extra)
  elseif self.mode == "play" and core.readInteger(self.rngRecorderState) == 2 then
    local expected = self.cachedRNG or self:loadRNG()
    self.cachedRNG = nil
    if not expected then
      core.writeInteger(self.rngRecorderState, 0)
      return registers
    end
    local reason
    for _, key in ipairs({"time", "rng1", "rng2", "index1", "index2"}) do
      if actual[key] ~= expected[key] then reason = key; break end
    end
    if not reason and traceF and self.rngLogMethod == "trace" then
      if not expected.extra or expected.extra["ra" .. traceF] ~= actual.extra["ra" .. traceF] then
        reason = "RNG call site"
      end
    end
    if reason and not self.firstDesync then
      self.firstDesync = {reason = reason, expected = expected, actual = actual}
      print("REPLAY DESYNC at tick " .. actual.time .. ": " .. reason)
      core.writeInteger(self.rngRecorderState, 0)
      core.writeInteger(self.commandRecorderState, 0)
    end
  end
  return registers
end

return Recorder
