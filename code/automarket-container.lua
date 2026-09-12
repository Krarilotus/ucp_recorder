-- Use map-extensions' existing ZIP implementation and published entry format.
-- Do not invoke serializers against the current game when converting a recording.
local adapter=require('code/automarket-replay')
local M={}

function M.encode(data,descriptor)
  adapter.descriptor(descriptor)
  assert(adapter.compatible(descriptor),
    'Preparing Automarket requires its recorded adapter and map-extensions')
  require('code/native-save').interface()
  assert(type(data)=='string' and #data==2416 and data:sub(1,4)=='\2\0\0\0',
    'Invalid Automarket snapshot')
  return require('code/extension-container').encode({['automarket/automarketplayerdata.bin']=data})
end
return M
