-- A short presentation summary accompanies, but never replaces, the complete
-- recorded settings and asset hashes used by replay admission.
local M={}

function M.capture(extensions,framework)
  local nodes,depended={},{}
  for _,extension in ipairs(extensions) do
    local definition=extension.definition or {}
    nodes[extension.name]={name=extension.name,version=extension.version,
      plugin=extension:type()=='PluginLoader',dependencies=definition.dependencies or definition.depends or {}}
  end
  for _,node in pairs(nodes) do
    for name in pairs(node.dependencies) do depended[name]=true end
  end
  local packs={}
  for name,node in pairs(nodes) do
    local containsPlugin=false
    for dependency in pairs(node.dependencies) do
      if nodes[dependency] and nodes[dependency].plugin then containsPlugin=true end
    end
    if not depended[name] or (node.plugin and containsPlugin) then
      packs[name]=node.version
    end
  end
  local version={}
  for _,key in ipairs({'major','minor','patch'}) do version[#version+1]=framework:match(key..':%s*(%d+)') or '?' end
  return {framework=table.concat(version,'.'),packs=packs,count=#extensions}
end

function M.lines(manifest,info)
  local tr=require('code/locale').text
  local lines={manifest.variant..' 1.41',tr('Saved: %s',manifest.savedAt or manifest.created or '?'),
    tr('UCP framework: %s',info.framework),tr('Active packs:')}
  local names={}; for name in pairs(info.packs) do names[#names+1]=name end
  table.sort(names,function(a,b) return a:lower()<b:lower() end)
  for _,name in ipairs(names) do
    local label=#name>34 and name:sub(1,31)..'...' or name
    lines[#lines+1]=label..' '..info.packs[name]
  end
  lines[#lines+1]=tr('%d exact extension versions verified',info.count)
  return lines
end
return M
