-- Actual shipped library and map-extensions handle; only UCP's library-loader
-- bridge and module inventory are stand-ins. No memory hooks or game process.
package.path=sourceRoot..'/?.lua;'..package.path
local library=assert(package.loadlib(testRoot..'/luamemzip.dll','luaopen_luamemzip'))()
core={openLibraryHandle=function(path)
  assert(path=='ucp/modules/map-extensions-1.0.0/luamemzip.dll')
  return {require=function(_,name) assert(name=='luamemzip'); return library end}
end}
allActiveExtensions={{name='automarket',version='1.1.0'},
  {name='protocol',version='1.0.0'},{name='map-extensions',version='1.0.0'}}
modules={protocol={getProtocolNumber=function() return 130 end},['map-extensions']={}}
local chunks={'\2\0\0\0'}
for i=0,2411 do chunks[#chunks+1]=string.char(i%256) end
local payload=table.concat(chunks)
local data=require('code/automarket-container').encode(payload,{version='1.1.0',protocol=130})
local zip=library:MemoryZip(data,nil,'r')
local handles=assert(loadfile(testRoot..'/handles.lua'))()
log=function() end
assert(handles.createReadHandle(zip,'automarket'):get('automarketplayerdata.bin')==payload)
zip:close()
local output=assert(io.open(testRoot..'/automarket.zip','wb'))
assert(output:write(data)); assert(output:close())
