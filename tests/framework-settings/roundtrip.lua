package.path=frameworkPath..'/?.lua;'..frameworkPath..'/?/init.lua;'..recorderPath..'/?.lua;'..package.path
package.loaded.core={} -- Native memory APIs are not used by this configuration test.
package.loaded.data={} -- Configuration file/discovery helpers are not invoked.
function log() end
json=require('vendor.json.json')
local config=require('config')
local capture=require('code/recorded-settings').capture
local extensions={
 {name='ui',version='1.0.1',type=function() return 'ModuleLoader' end},
 {name='recorder',version='0.25.0',type=function() return 'ModuleLoader' end},
 {name='Ascension-Multiplayer',version='1.0.11',type=function() return 'PluginLoader' end},
}
local options={['recorder-0.25.0']={enabled=false,speed=200,fraction=0.125,negative=-2147483648,
 title='A "quoted" match',path='ucp/plugins/test/maps/',newline='line 1\nline 2',
 nested={contents={value='literal option data'},list={1,2,3}}}}
local serialized,expected=capture(extensions,options)
local decoded=yaml.eval(serialized) -- Actual production C++ YAML-to-Lua conversion.
config.ConfigHandler.validateUserConfig(decoded)
assert(decoded.meta.version=='1.0.0' and decoded.active==true)
local installed={
 {name='ui',version='1.0.1'},{name='ui',version='1.0.9'},
 {name='recorder',version='0.25.0'},{name='recorder',version='0.26.0'},
 {name='Ascension-Multiplayer',version='1.0.11'},{name='Ascension-Multiplayer',version='1.0.12'},
}
local selected={}
for i,requirement in ipairs(decoded['config-full']['load-order']) do
 local chosen=config.matcher.findPreMatchForExtensionRequirement(installed,requirement)
 assert(chosen.name==extensions[i].name and chosen.version==extensions[i].version)
 selected[chosen.name]=chosen.version
end
assert(config.matcher.findPreMatchForExtensionRequirement({installed[2]},decoded['config-full']['load-order'][1])==nil)
local restored={}
for _,category in ipairs({'modules','plugins'}) do
 for name,entry in pairs(decoded['config-full'][category]) do restored[name..'-'..selected[name]]=entry.config end
end
config.ConfigHandler.normalizeContentsValues(restored) -- Actual framework normalization.
local function same(a,b)
 assert(type(a)==type(b),'restored option type differs')
 if type(a)~='table' then assert(a==b); return end
 for key,value in pairs(a) do same(value,b[key]) end
 for key in pairs(b) do assert(a[key]~=nil) end
end
same(expected,restored)
same(decoded['config-full']['load-order'],decoded['config-sparse']['load-order'])
-- The existing native bridge ignores scalar quote tags and coerces these strings.
-- Refuse them before saving instead of silently changing the next game's input.
for _,text in ipairs({'true','false','yes','off','123','0.125','part\0tail'}) do
 options['recorder-0.25.0'].runtimeString=text
 assert(not pcall(capture,extensions,options),'unrestorable string was silently accepted: '..text)
end
options['recorder-0.25.0'].runtimeString=nil
for _,number in ipairs({0/0,math.huge,-math.huge}) do
 options['recorder-0.25.0'].startTroops={Knight=number}
 local ok,reason=pcall(capture,extensions,options)
 assert(not ok and reason:find('recorder-0.25.0/startTroops/Knight',1,true))
end
print('PASS: actual UCP YAML bridge, JSON encoder, version matcher and option normalizer; exact versions, typed values and coercion rejection')
