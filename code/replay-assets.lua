-- Startup/library work only. A version string does not identify the bytes of an
-- unpacked extension. Use the framework's virtual filesystem for ZIPs and folders.
local digest=require('code/native-hash')
local M={PROFILE='ucp-files-v1',MAX_FILE=1024*1024*1024,MAX_FILES=50000}
local function normalized(path)
  assert(type(path)=='string' and not path:find('[%z\r\n]'),'Invalid replay asset path')
  return path:gsub('\\','/'):gsub('/+$','')
end

function M.capture(extensions,config)
  local files,visited,layouts,count={}, {},{},0
  local function add(path)
    path=normalized(path)
    if files[path] then return end
    assert(count<M.MAX_FILES,'Too many replay assets')
    files[path]=digest.file(path,M.MAX_FILE); count=count+1
  end
  local function directory(path,depth)
    path=normalized(path)
    if visited[path] then return end
    assert(depth<=16,'Replay asset directory nesting is too deep')
    visited[path]=true
    for _,file in ipairs(ucp.internal.io.files(path..'/')) do add(file) end
    for _,child in ipairs(ucp.internal.io.directories(path..'/')) do
      child=normalized(child)
      assert(child:sub(1,#path+1)==path..'/','Asset directory escaped its parent')
      -- Folder listings expose nested ZIPs as synthetic directories too. Their
      -- complete archive is already hashed; they are not filesystem children.
      if child:sub(#path+2)~='.git' and not files[child..'.zip'] then directory(child,depth+1) end
    end
  end
  digest.prepare()
  for _,extension in ipairs(extensions) do
    local kind=extension:type()=='ModuleLoader' and 'modules' or 'plugins'
    local root='ucp/'..kind..'/'..extension.name..'-'..extension.version
    -- UCP 3.0.7's ZIP directory listing compares the full virtual path against
    -- relative ZIP members and returns no entries. Hash the archive in that
    -- case, and retain the layout so a folder cannot silently shadow it later.
    local unpacked=#ucp.internal.io.files(root..'/')>0
    layouts[root]=unpacked and 'folder' or 'archive'
    if unpacked then directory(root,0) else add(root..'.zip') end
  end
  -- Resolved option values include aliased paths after the framework's normal
  -- configuration pass. Fingerprint additional readable files/directories too.
  local function options(value)
    if type(value)=='table' then for _,item in pairs(value) do options(item) end
    elseif type(value)=='string' and value:find('[/\\]') and not value:find('[%z\r\n]') then
      local path=normalized(value)
      local opened,file=pcall(io.open,path,'rb')
      if opened and file then assert(file:close()); add(path)
      else
        local ok,children=pcall(ucp.internal.io.files,path..'/')
        if ok and type(children)=='table' then directory(path,0) end
      end
    end
  end
  options(config)
  return {profile=M.PROFILE,files=files,layouts=layouts}
end

function M.verify(snapshot)
  assert(type(snapshot)=='table' and snapshot.profile==M.PROFILE and type(snapshot.files)=='table',
    'Unsupported replay asset inventory')
  local count=0
  for root,layout in pairs(snapshot.layouts or {}) do
    local unpacked=#ucp.internal.io.files(normalized(root)..'/')>0
    assert(layout==(unpacked and 'folder' or 'archive'),'Recorded extension layout changed: '..root)
  end
  for path,expected in pairs(snapshot.files) do
    count=count+1; assert(count<=M.MAX_FILES,'Too many replay assets')
    assert(normalized(path)==path,'Invalid replay asset path')
    require('code/validation').hash(expected,'asset hash')
    local ok,hash=pcall(digest.file,path,M.MAX_FILE)
    assert(ok and hash==expected,'Recorded asset changed or is unavailable: '..path)
  end
end
return M
