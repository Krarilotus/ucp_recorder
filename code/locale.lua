-- In-game labels follow UCP's game-language provider, never the launcher locale.
local M={}
local aliases={english='en',american='en',german='de',french='fr',russian='ru',
 hungarian='hu',turkish='tr',chinese='zh',spanish='es',persian='fa',farsi='fa',italian='it',polish='pl',ch='zh'}
M.supported={'en','de','fr','ru','hu','tr','zh','es','fa','it','pl'}
local supported={}; for _,language in ipairs(M.supported) do supported[language]=true end
local function normalize(value)
 if type(value)~='string' then return end
 value=value:lower():gsub('_','-'):match('^%s*(.-)%s*$')
 local language=aliases[value] or value:match('^([a-z]+)%-') or value
 language=aliases[language] or language
 return supported[language] and language or nil
end
local contextReader
-- The renderer supplies the loaded TextManager, not an executable-language
-- guess. Before CR.TEX loads, the game provider may legitimately return nil.
function M.bind(readContext) contextReader=readContext end
function M.context()
 local codepage=1252 -- original bitmap fallback until TextManager is ready
 if contextReader then
  local ok,marker,page=pcall(contextReader)
  if ok and type(page)=='number' and page>0 then
   codepage=page
   local language=normalize(marker)
   if language then return language,codepage end
  end
 end
 local provider=(rawget(_G,'data') or {}).version
 if type(provider)~='table' or type(provider.getGameLanguage)~='function' then provider=rawget(_G,'version') end
 local language
 if type(provider)=='table' and type(provider.getGameLanguage)=='function' then
  local ok,value=pcall(provider.getGameLanguage); if ok then language=normalize(value) end
 end
 return language or 'en',codepage
end
function M.language() local language=M.context(); return language end
M.translations=setmetatable({},{__index=function(self,language)
 if not supported[language] or language=='en' then return end
 local catalog=require('code/locale-'..language); rawset(self,language,catalog); return catalog
end})
local encoding=require('code/text-encoding')
local cache,count={},0
local function encoded(text,codepage)
 if not text:find('[\128-\255]') then return text end
 local key=codepage..':'..text
 if cache[key]~=nil then return cache[key] or nil end
 local ok,value=pcall(encoding.encode,text,codepage)
 if count>=256 then cache={}; count=0 end
 cache[key]=ok and value or false; count=count+1
 return ok and value or nil
end
function M.text(key,...)
 local language,codepage=M.context()
 local catalog=M.translations[language]
 local value=catalog and catalog[key] or key
 -- A translated installation must supply fonts and a matching codepage. If
 -- conversion cannot represent a label, show its English source, not mojibake.
 if not encoded(value,codepage) then value=key end
 return select('#',...)>0 and string.format(value,...) or value
end
local function native(text,codepage)
 return encoded(text,codepage) or (text:gsub('[\128-\255]+','?'))
end
function M.native(text)
 local _,codepage=M.context()
 return native(tostring(text),codepage)
end
function M.fit(text,limit,measure,width)
 local _,codepage=M.context()
 text=tostring(text):gsub('[\r\n%z]',' ')
 return encoding.fit(text,function(value) return native(value,codepage) end,limit,measure,width)
end
return M
