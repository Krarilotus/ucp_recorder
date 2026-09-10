-- UTF-8 source -> the loaded TextManager codepage. Reuse Windows conversion
-- through the existing UCP ABI adapter; no shell, system locale or new DLL.
local M={MAX_INPUT=4096}
local api,buffer
local function initialize()
  if api then return end
  local platform=require('code/platform')
  local functions={decode=platform.stdcall('kernel32.dll','MultiByteToWideChar',6),
    encode=platform.stdcall('kernel32.dll','WideCharToMultiByte',8)}
  local allocation=core.allocate(M.MAX_INPUT*7+4,true)
  assert(allocation and allocation~=0,'Text conversion buffer allocation failed')
  api,buffer=functions,allocation
end

function M.encode(text,codepage)
  if not text:find('[\128-\255]') then return text end
  if #text>=M.MAX_INPUT or not codepage or codepage<=0 then return nil end
  -- Legacy Persian CR.TEX/fonts use the Arabic yeh slot in Windows-1256;
  -- Persian yeh has no byte in that codepage. Keep source/UTF-8 text unchanged.
  if codepage==1256 then text=text:gsub('ی','ي') end
  initialize()
  local wide,output,used=buffer+M.MAX_INPUT,buffer+M.MAX_INPUT*3,buffer+M.MAX_INPUT*7
  core.writeString(buffer,text..'\0')
  local count=api.decode(65001,8,buffer,#text,wide,M.MAX_INPUT) -- MB_ERR_INVALID_CHARS
  if count==0 then return nil end
  local unicode=codepage==65001 or codepage==54936
  core.writeInteger(used,0)
  -- Never silently approximate characters in a translated label. UTF-8 and
  -- GB18030 require null default-character arguments and different flags.
  local size=api.encode(codepage,unicode and 128 or 1024,wide,count,
    output,M.MAX_INPUT*4,0,unicode and 0 or used)
  if size==0 or (not unicode and core.readInteger(used)~=0) then return nil end
  return core.readString(output,size)
end

-- Renderer clipping operates on complete UTF-8 characters before conversion.
-- Width measurement receives exactly the bytes the game will draw.
function M.fit(text,encode,limit,measure,maxWidth)
  local function fits(value)
    return #value<=limit and (not measure or measure(value)<=maxWidth)
  end
  local full=encode(text)
  if fits(full) then return full end
  if not fits('...') then return '' end
  local ends={0}
  for position,character in text:gmatch('()([\1-\127\194-\244][\128-\191]*)') do
    ends[#ends+1]=position+#character-1
  end
  local low,high=1,#ends
  while low<high do
    local middle=math.floor((low+high+1)/2)
    if fits(encode(text:sub(1,ends[middle]))..'...') then low=middle else high=middle-1 end
  end
  return encode(text:sub(1,ends[low]))..'...'
end
return M
