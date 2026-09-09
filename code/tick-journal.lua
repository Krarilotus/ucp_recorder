-- Fixed-size observations around native simulation, not render frames. A frame
-- carries both streams before and after the tick: playback may restore the
-- presentation-coupled RNG1 input, but must verify the simulation's output.
local M={SIZE=28}
local function word(value)
  local a=value%256; value=math.floor(value/256)
  local b=value%256; value=math.floor(value/256)
  local c=value%256; value=math.floor(value/256)
  return string.char(a,b,c,value%256)
end
local function integer(data,offset)
  local a,b,c,d=data:byte(offset,offset+3)
  return a+b*256+c*65536+d*16777216
end
function M.state(engine)
  local data=core.readString(engine.rng,4)..core.readString(engine.rng+0x9c48,8)
  assert(#data==12,'Incomplete native RNG boundary')
  return data
end
function M.values(data)
  assert(type(data)=='string' and #data==12,'Invalid native RNG boundary')
  local a,b,c,d=data:byte(1,4)
  local result={a+b*256,c+d*256,integer(data,5),integer(data,9)}
  require('code/validation').rng(result)
  return result
end
function M.frame(tick,before,after)
  require('code/validation').integer(tick,0,2147483646,'observed tick')
  M.values(before); M.values(after)
  return word(tick)..before..after
end
function M.decode(data)
  assert(type(data)=='string' and #data==M.SIZE,'Incomplete recorded simulation tick')
  local tick=integer(data,1)
  require('code/validation').integer(tick,0,2147483646,'observed tick')
  return {time=tick,before=M.values(data:sub(5,16)),after=M.values(data:sub(17,28))}
end

-- Preflight consumes complete frames without allocating playback tables and
-- substring copies for every tick. Packed 16-bit RNG values are valid by
-- construction; the four table indices and clock still require validation.
function M.scan(data,expected)
  assert(type(data)=='string' and #data%M.SIZE==0,'Incomplete recorded simulation tick')
  for offset=1,#data,M.SIZE do
    local tick=integer(data,offset)
    assert(tick<=2147483646,'Invalid replay observed tick')
    assert(tick==expected,'Recorded simulation ticks are not continuous')
    assert(integer(data,offset+8)<20000 and integer(data,offset+12)<20000
      and integer(data,offset+20)<20000 and integer(data,offset+24)<20000,
      'Invalid replay RNG index')
    expected=expected+1
  end
  return expected
end
function M.input(engine,expected)
  require('code/validation').rng(expected)
  local actual=engine:rngState()
  assert(actual[2]%65536==expected[2]%65536 and actual[3]==expected[3],
    'Simulation RNG2 differs before tick or command at '..engine:tick())
  -- Only presentation's current value/index are inputs. Never overwrite the
  -- simulation stream, seed, or random-number table to hide a divergence.
  core.writeSmallInteger(engine.rng,expected[1])
  core.writeInteger(engine.rng+0x9c4c,expected[4])
end
function M.check(engine,expected,phase)
  local actual=engine:rngState()
  for i=1,4 do
    local a,b=actual[i],expected[i]
    if i<=2 then a=a%65536; b=b%65536 end
    assert(a==b,'RNG divergence '..phase..' at tick '..engine:tick()..' (field '..i..')')
  end
end
return M
