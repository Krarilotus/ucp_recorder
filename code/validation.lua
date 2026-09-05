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

return M
