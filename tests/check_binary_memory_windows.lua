-- Run with a 32-bit Lua 5.4 executable beside the installation's lua.dll/RPS.dll:
-- lua.exe check_binary_memory_windows.lua <recorder source> <ucp/code>
-- Uses private allocations only; no game process or game executable is needed.
local source,framework=assert(arg[1]),assert(arg[2])
-- Optional installed CFFI DLL: exercise the actual bridge, not an FFI stand-in.
if arg[3] then
  local ffi=assert(package.loadlib(arg[3],'luaopen_cffi'))()
  modules={cffi={cffi=function() return ffi end}}
end
package.path=source..'/?.lua;'..package.path
local rps=require('RPS')
ucp={internal=rps}
core=dofile(framework..'/core.lua')
package.loaded.core=core
utils=dofile(framework..'/utils.lua')
local platform=require('code/platform')
assert(platform.milliseconds()>=0 and platform.multimediaMilliseconds()>=0)
local identity=platform.identity()
assert(identity.processId>0 and #identity.executable>0)
local resolve=ucp.internal.getLibraryProcAddressA
ucp.internal.getLibraryProcAddressA=function() error('Repeated Windows symbol resolution') end
assert(platform.milliseconds()>=0 and platform.multimediaMilliseconds()>=0)
assert(platform.identity().processId==identity.processId)
ucp.internal.getLibraryProcAddressA=resolve
local binary=require('code/binary-memory')
local byteWrites=0
local writeBytes=core.writeBytes
core.writeBytes=function(...) byteWrites=byteWrites+1; return writeBytes(...) end
local values={}; for i=0,255 do values[#values+1]=string.char(i) end
local all=table.concat(values)
local address=core.allocate(65538,true)
core.writeString(address,all)
print('Runtime writeString preserves binary:',core.readString(address,#all)==all)
for _,size in ipairs({0,1,255,256,4095,4096,4097,65535,65536}) do
  local payload=all:rep(256):sub(1,size)
  core.writeByte(address+size+1,0xc5)
  binary.write(address,payload)
  if size>0 then assert(core.readString(address,size)==payload,'Binary copy differs') end
  assert(core.readByte(address+size+1)==0xc5,'Binary copy overflowed its buffer')
end
core.deallocate(address)
local hash=require('code/native-hash')
hash.prepare()
assert(hash.sha256('')=='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
assert(hash.sha256(all)=='40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880')
if arg[3] then assert(byteWrites==0,'Installed CFFI did not provide a binary copy') end
print('PASS: binary transfer boundaries and native hash startup through installed RPS')
if arg[4] then
  -- This console is the running executable. Game-family parsing is covered on
  -- all reference images separately; here verify the real OS path/hash bridge.
  data={version={getGameVersionMajor=function() return '1' end,
    getGameVersionMinor=function() return '41' end,isExtreme=function() return false end}}
  local native=require('code/native')
  local profile=native.verify()
  assert(profile.name=='SHC' and profile.sha256==arg[4])
  print('PASS: native executable identity matches independent console SHA-256',profile.sha256)
end
