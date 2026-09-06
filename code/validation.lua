-- Validate file-controlled values before crossing the native command boundary.
local M = {MAX_PAYLOAD = 1260}

function M.integer(value, minimum, maximum, label)
  assert(type(value) == "number" and value == math.floor(value)
    and value >= minimum and value <= maximum, "Invalid replay " .. label)
  return value
end

function M.command(command)
  assert(type(command) == "table", "Invalid replay command")
  M.integer(command.commandCategory, 0, 122, "command category")
  M.integer(command.time, 1, 2147483647, "command tick")
  M.integer(command.player, 1, 8, "player slot")
  M.integer(command.size, 0, M.MAX_PAYLOAD, "payload size")
  assert(type(command.data) == "string" and #command.data == command.size * 2
    and not command.data:find("[^%x]"), "Invalid replay payload encoding")
  return command
end

function M.info(info)
  assert(type(info) == "table", "Missing replay match information")
  M.integer(info.gameType, 0, 0, "game type")
  for _, key in ipairs({"mapSeed", "matchSeed"}) do
    M.integer(info[key], -2147483648, 2147483647, key)
  end
  for _, key in ipairs({"RNGvalue1", "RNGvalue2"}) do
    M.integer(info[key], -32768, 65535, key)
  end
  for _, key in ipairs({"RNGindex1", "RNGindex2"}) do
    M.integer(info[key], 0, 19999, key)
  end
  return info
end

-- Single-player simulation commands from OpenSHC's GameCommandType. Protocol,
-- lobby, save/load and unknown extension commands must never run from a replay.
local gameplay = {}
for _,id in ipairs({14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,
  31,34,35,36,38,41,42,43,44,45,68,69,70,71,78,113,119}) do gameplay[id]=true end

function M.sessionCommand(command, manifest)
  M.command(command)
  if command.commandCategory==122 then
    require('code/automarket-replay').command(command,manifest.automarket)
  else
    assert(gameplay[command.commandCategory],
    'Unsupported replay command category '..command.commandCategory..' (save/load and network commands are excluded)')
  end
  assert(command.commandCategory~=119 or manifest.variant=='Extreme','Tactical powers require Extreme')
  assert(command.player==manifest.player,'Replay command uses a different player slot')
  return command
end

function M.rng(values)
  assert(type(values)=='table' and #values==4,'Invalid replay RNG checkpoint')
  M.integer(values[1],-32768,65535,'RNG value 1')
  M.integer(values[2],-32768,65535,'RNG value 2')
  M.integer(values[3],0,19999,'RNG index 2')
  M.integer(values[4],0,19999,'RNG index 1')
end

function M.manifest(value)
  assert(type(value)=='table','Invalid replay manifest')
  if value.displayName~=nil then M.displayName(value.displayName) end
  require('code/automarket-replay').descriptor(value.automarket)
  M.integer(value.player,1,8,'player slot')
  M.integer(value.startTick,0,2147483647,'starting tick')
  M.integer(value.lastTick,value.startTick,2147483647,'ending tick')
  M.integer(value.commandCount,0,2147483647,'command count')
  M.rng(value.finalRng)
  M.resources(value.startResources)
  M.resources(value.finalResources)
  for _,key in ipairs({'settingsHash','environmentHash','snapshotHash','rngHash','finalRngHash','commandsHash','checkpointsHash','infoHash'}) do
    M.hash(value[key],key)
  end
  return value
end

function M.displayName(value)
  assert(type(value)=='string','Enter a replay name')
  value=value:match('^%s*(.-)%s*$')
  assert(#value>=1 and #value<=40,'Use a replay name between 1 and 40 characters')
  assert(not value:find('[^ -~]'),'Use letters, numbers and standard punctuation')
  return value
end

function M.hash(value,label)
  assert(type(value)=='string' and #value==64 and not value:find('[^%x]'),'Invalid replay '..label)
end

function M.resources(values)
  assert(type(values)=='table' and #values==200,'Invalid replay resource state')
  for i=1,200 do M.integer(values[i],-2147483648,2147483647,'resource amount') end
end

return M
