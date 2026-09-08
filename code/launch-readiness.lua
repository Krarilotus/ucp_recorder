-- Replay launch checks belong to the library, never the simulation tick hook.
-- Use UCP's virtual file API so installed ZIPs and unpacked modules behave alike.
local store=require('code/sessions')
local tr=require('code/locale').text
local M={}

---@class ReplayLaunchIssue
---@field kind string
---@field name string
---@field version string
---@class ReplayLaunchReadiness
---@field ready boolean
---@field issues ReplayLaunchIssue[]
---@field message string
---@field details string

---@param manifest table A validated, completed replay manifest.
---@return ReplayLaunchReadiness
function M.check(manifest)
  local path=store.path(manifest.id)
  local raw=store.read(path..'/environment.json')
  assert(sha.sha256(raw)==manifest.environmentHash,'Recorded environment is damaged')
  local environment=json:decode(raw)
  assert(type(environment)=='table','Invalid recorded environment')
  local issues={}
  if type(environment.framework)=='string' and store.read('ucp/ucp-version.yml')~=environment.framework then
    issues[#issues+1]={kind='framework',name='UCP',version=environment.framework}
  end
  if manifest.settingsCapture=='resolved-v1' then
    raw=store.read(path..'/replay-config.yml')
    assert(sha.sha256(raw)==manifest.restartSettingsHash,'Recorded launch settings are damaged')
    local document=json:decode(raw)
    local full=type(document)=='table' and document['config-full']
    assert(type(full)=='table' and type(full['load-order'])=='table'
      and type(full.modules)=='table' and type(full.plugins)=='table','Invalid recorded launch settings')
    local seen={}
    for _,requirement in ipairs(full['load-order']) do
      local name,version=requirement.extension,requirement.version
      assert(type(name)=='string' and name:match('^[%w_-]+$') and not seen[name]
        and type(version)=='string' and version:match('^%d+%.%d+%.%d+$'),'Invalid recorded extension identity')
      seen[name]=true
      local module,plugin=full.modules[name]~=nil,full.plugins[name]~=nil
      assert(module~=plugin,'Ambiguous recorded extension type')
      local category=module and 'modules' or 'plugins'
      local ok,definition=pcall(function()
        return yaml.eval(store.read('ucp/'..category..'/'..name..'-'..version..'/definition.yml'))
      end)
      if not ok or type(definition)~='table' or definition.name~=name
        or definition.version~=version then
        issues[#issues+1]={kind='extension',name=name,version=version}
      end
    end
    assert(next(seen),'Recorded launch settings contain no extensions')
  end
  local lines={}
  for _,issue in ipairs(issues) do
    lines[#lines+1]=issue.kind=='framework' and tr('Required UCP framework: %s',issue.version)
      or tr('Missing or unreadable: %s %s',issue.name,issue.version)
  end
  local message=''
  if #issues>0 then
    message=issues[1].kind=='framework' and tr('The recorded UCP framework is required.')
      or tr('Required: %s %s',issues[1].name,issues[1].version)
    if #issues>1 then message=message..tr(' (+%d more)',#issues-1) end
    lines[#lines+1]=tr('Install these exact versions using the UCP launcher or their original releases.')
    lines[#lines+1]=tr('If a required version is no longer available, this replay cannot be played here. Newer versions are not substituted.')
    lines[#lines+1]=tr('Your normal settings have not been changed.')
  end
  return {ready=#issues==0,issues=issues,message=message,details=table.concat(lines,'\n')}
end

function M.requireReady(manifest)
  local result=M.check(manifest)
  if not result.ready then
    store.write(store.ROOT..'/requirements.txt',result.details)
    -- UCP owns the existing Windows error dialog. Display the whole list on an
    -- explicit Play action; selection alone only updates the library summary.
    log(ERROR,result.details)
    error(result.message,0)
  end
end
return M
