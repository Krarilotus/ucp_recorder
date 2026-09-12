-- Protocol 1.1.0 admission packets are lobby-only. Delayed replies received
-- during a match are explicit no-ops in that owner, not timed replay commands.
local validation=require('code/validation')
local M={}
function M.current()
  if require('code/automarket-replay').version('protocol')~='1.1.0' then return end
  local protocol=assert(modules and modules.protocol,'Protocol admission owner is unavailable')
  assert(type(protocol.multiplayerAdmissionVersion)=='function' and protocol:multiplayerAdmissionVersion()==1,
    'Unsupported Protocol admission API')
  local id=protocol:getProtocolNumber('protocol','content-admission-v1')
  if id==nil then return end
  validation.integer(id,130,2147483647,'admission protocol')
  return {version=1,protocol=id}
end
function M.packet(packet,descriptor)
  if descriptor==nil then return false end
  assert(type(descriptor)=='table' and descriptor.version==1,'Unsupported recorded admission protocol')
  validation.integer(descriptor.protocol,130,2147483647,'recorded admission protocol')
  if type(packet)~='table' or packet.category~=121 or packet.scheduledTime~=0
      or packet.size~=80 or type(packet.data)~='string' or #packet.data~=160
      or packet.data:find('[^%x]') then return false end
  local bytes=require('code/utils').hexToTable(packet.data)
  local function word(offset)
    return bytes[offset+1]+bytes[offset+2]*256+bytes[offset+3]*65536+bytes[offset+4]*16777216
  end
  return word(0)==descriptor.protocol and word(4)<=1
    and word(8)>=1 and word(8)<=2147483647 and word(12)>=1 and word(12)<=8
end
return M
