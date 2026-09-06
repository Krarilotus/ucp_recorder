-- JSON is a YAML-compatible UCP configuration. Pin the actual loaded extensions
-- and freeze their normalized options, rather than resolving version ranges again.
local M={PROFILE='resolved-v1'}
local function equal(a,b)
  if type(a)~=type(b) then return false end
  if type(a)~='table' then return a==b end
  for key,value in pairs(a) do if not equal(value,b[key]) then return false end end
  for key in pairs(b) do if a[key]==nil then return false end end
  return true
end
function M.capture(extensions,config)
  assert(type(extensions)=='table' and #extensions>0,'Loaded extensions are unavailable for replay settings')
  assert(type(config)=='table','Resolved UCP options are unavailable for replay settings')
  local full={modules={},plugins={},['load-order']={}}
  local resolved,seen={},{}
  for i,extension in ipairs(extensions) do
    local name,version=extension.name,extension.version
    assert(type(name)=='string' and name:match('^[%w_-]+$') and not seen[name],'Invalid or duplicate loaded extension')
    assert(type(version)=='string' and version:match('^%d+%.%d+%.%d+$'),'Invalid loaded extension version')
    local kind=extension:type()
    local category=kind=='ModuleLoader' and 'modules' or kind=='PluginLoader' and 'plugins'
    assert(category,'Unknown loaded extension type')
    local key=name..'-'..version
    local options=config[key] or {}
    assert(type(options)=='table','Invalid resolved extension options')
    -- One contents.value wrapper protects literal options named "contents" from
    -- the framework's recursive configuration normalization on the next launch.
    full[category][name]={config={contents={value=options}}}
    full['load-order'][i]={extension=name,version=version}
    resolved[key]=options
    seen[name]=true
  end
  for key in pairs(config) do assert(resolved[key]~=nil,'Resolved options contain an unloaded extension') end
  local document={meta={version='1.0.0'},active=true,['config-full']=full,['config-sparse']=full}
  local serialized=json:encode(document)
  -- The framework YAML bridge coerces some quoted scalars too. Refuse a profile
  -- that would silently turn a string into a boolean/number or otherwise change it.
  assert(equal(document,yaml.eval(serialized)),'UCP cannot restore these replay option values without changes')
  return serialized,resolved
end
return M
