-- Startup/library work only. A version string does not identify the bytes of an
-- unpacked extension. Use the framework's virtual filesystem for ZIPs and folders.
local digest=require('code/native-hash')
local M={PROFILE='ucp-files-v2',MAX_FILE=1024*1024*1024,MAX_FILES=50000}
local function normalized(path)
  assert(type(path)=='string' and not path:find('[%z\r\n]'),'Invalid replay asset path')
  return path:gsub('\\','/'):gsub('/+$','')
end

-- One traversal policy for capture and preflight. Hashing only the old file
-- list would miss newly added scripts/assets that change directory lookup.
local function walker(add,progress)
  local visited,count={},0
  local function directory(path,depth)
    path=normalized(path)
    if visited[path] then return end
    assert(depth<=16,'Replay asset directory nesting is too deep')
    count=count+1; assert(count<=M.MAX_FILES,'Too many replay asset directories')
    visited[path]=true
    if progress then progress('Checking recorded settings...') end
    local present={}
    for _,file in ipairs(ucp.internal.io.files(path..'/')) do
      file=normalized(file)
      assert(file:sub(1,#path+1)==path..'/','Asset file escaped its parent: '..file..' (parent '..path..')')
      present[file]=true; add(file)
    end
    for _,child in ipairs(ucp.internal.io.directories(path..'/')) do
      child=normalized(child)
      assert(child:sub(1,#path+1)==path..'/','Asset directory escaped its parent: '..child..' (parent '..path..')')
      -- Folder handles list ZIPs as synthetic directories, but listFiles on
      -- such a child fails unless a physical folder of that name also exists.
      -- Include that folder: its files can shadow the sibling archive.
      local folder=not present[child..'.zip'] or pcall(ucp.internal.io.files,child..'/')
      if child:sub(#path+2)~='.git' and folder then directory(child,depth+1) end
    end
  end
  return function(path) directory(path,0) end
end

function M.capture(extensions,config)
  local files,roots,layouts,count={},{},{},0
  local function add(path)
    path=normalized(path)
    if files[path] then return end
    assert(count<M.MAX_FILES,'Too many replay assets')
    files[path]=digest.file(path,M.MAX_FILE); count=count+1
  end
  local walk=walker(add)
  local function directory(path)
    -- Listing resolves aliases internally and returns the resolved child paths.
    -- Retain that same parent identity, including aliases naming a folder root.
    path=normalized(ucp.internal.resolveAliasedPath(normalized(path)..'/'))
    roots[path]=true; walk(path)
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
    if unpacked then directory(root) else add(root..'.zip') end
  end
  -- Normalized options still contain UCP aliases (both name/ and name-*/).
  -- Resolve through their framework owner before fingerprinting or containment.
  local function options(value)
    if type(value)=='table' then for _,item in pairs(value) do options(item) end
    elseif type(value)=='string' and value:find('[/\\]') and not value:find('[%z\r\n]') then
      local path=normalized(ucp.internal.resolveAliasedPath((value:gsub('\\','/'))))
      local opened,file=pcall(io.open,path,'rb')
      if opened and file then assert(file:close()); add(path)
      else
        local ok,children=pcall(ucp.internal.io.files,path..'/')
        if ok and type(children)=='table' then directory(path) end
      end
    end
  end
  options(config)
  return {profile=M.PROFILE,files=files,layouts=layouts,roots=roots}
end

function M.verify(snapshot,progress)
  assert(type(snapshot)=='table' and snapshot.profile==M.PROFILE and type(snapshot.files)=='table'
    and type(snapshot.roots)=='table',
    'Unsupported replay asset inventory')
  local count=0
  for root,layout in pairs(snapshot.layouts or {}) do
    if progress then progress('Checking recorded settings...') end
    local unpacked=#ucp.internal.io.files(normalized(root)..'/')>0
    assert(layout==(unpacked and 'folder' or 'archive'),'Recorded extension layout changed: '..root)
    assert(layout~='folder' or snapshot.roots[root]==true,'Missing recorded extension directory: '..root)
  end
  local walk=walker(function(path)
    if progress then progress('Checking recorded settings...') end
    assert(snapshot.files[path],'New asset in a recorded directory: '..path)
  end,progress)
  for root,value in pairs(snapshot.roots) do
    assert(value==true and normalized(root)==root,'Invalid recorded asset directory')
    walk(root)
  end
  for path,expected in pairs(snapshot.files) do
    count=count+1; assert(count<=M.MAX_FILES,'Too many replay assets')
    assert(normalized(path)==path,'Invalid replay asset path')
    require('code/validation').hash(expected,'asset hash')
    local ok,hash=pcall(digest.file,path,M.MAX_FILE,progress and function()
      progress('Checking recorded settings...')
    end)
    assert(ok and hash==expected,'Recorded asset changed or is unavailable: '..path)
  end
end
return M
