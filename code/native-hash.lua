-- UCP itself imports Advapi32 for signature verification. Reuse its SHA-256
-- provider rather than hashing tens of MiB in the interpreter on a game tick.
local platform=require('code/platform')
local M={CHUNK=65536}
local api,buffers,busy

local function initialize()
  if api then return end
  local functions={}
  for name,count in pairs({CryptAcquireContextA=5,CryptCreateHash=5,CryptHashData=4,
      CryptGetHashParam=5,CryptDestroyHash=1,CryptReleaseContext=2}) do
    functions[name]=platform.stdcall('advapi32.dll',name,count)
  end
  local storage=core.allocate(M.CHUNK+64,true)
  local allocated={input=storage,provider=storage+M.CHUNK+4,
    hash=storage+M.CHUNK+8,digest=storage+M.CHUNK+12,length=storage+M.CHUNK+44}
  -- RPS must copy binary Lua strings by length, including embedded NULs.
  -- Fail before touching game data if an incompatible framework truncates them.
  local bytes={}; for i=0,255 do bytes[#bytes+1]=string.char(i) end
  local probe=table.concat(bytes)
  core.writeString(allocated.input,probe)
  assert(core.readString(allocated.input,#probe)==probe,'Native hashing requires binary string writes')
  api,buffers=functions,allocated
end

function M.prepare()
  initialize()
  assert(M.sha256('abc')=='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    'Windows SHA-256 self-test failed')
end

function M.sha256(data)
  assert(type(data)=='string' and not busy,'Invalid or nested native hashing')
  initialize(); busy=true
  local provider,hash
  local ok,result=pcall(function()
    -- PROV_RSA_AES, CRYPT_VERIFYCONTEXT: ephemeral context, no persisted keys.
    assert(api.CryptAcquireContextA(buffers.provider,0,0,24,-268435456)~=0,'Cannot acquire SHA-256 provider')
    provider=core.readInteger(buffers.provider)
    assert(api.CryptCreateHash(provider,0x800c,0,0,buffers.hash)~=0,'Cannot create SHA-256 hash')
    hash=core.readInteger(buffers.hash)
    for offset=1,#data,M.CHUNK do
      local chunk=data:sub(offset,offset+M.CHUNK-1)
      core.writeString(buffers.input,chunk)
      assert(api.CryptHashData(hash,buffers.input,#chunk,0)~=0,'Cannot update SHA-256 hash')
    end
    core.writeInteger(buffers.length,32)
    assert(api.CryptGetHashParam(hash,2,buffers.digest,buffers.length,0)~=0
      and core.readInteger(buffers.length)==32,'Cannot finish SHA-256 hash')
    local digest=core.readString(buffers.digest,32)
    assert(#digest==32,'Short SHA-256 digest')
    return (digest:gsub('.',function(c) return string.format('%02x',c:byte()) end))
  end)
  -- Release both objects on every error path before allowing the next hash.
  local hashClosed=not hash or api.CryptDestroyHash(hash)~=0
  local providerClosed=not provider or api.CryptReleaseContext(provider,0)~=0
  busy=false
  assert(ok,result)
  assert(hashClosed and providerClosed,'Cannot release SHA-256 context')
  return result
end
return M
