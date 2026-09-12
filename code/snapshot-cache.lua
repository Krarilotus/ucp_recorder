-- Process lifetime and crash cleanup for disposable worlds. Replay folders
-- are never enumerated. An exclusive native lease protects other live viewers.
local platform=require('code/platform')
local M={ROOT='ucp/replay-cache'}
local process,lease,serial
local suffixes={sav=true,rng=true,['sav.tmp']=true,['rng.tmp']=true}

local function initialize()
  if process then return end
  platform.mkdir(M.ROOT)
  local pid=tostring(platform.identity().processId)
  local own=assert(platform.tryTemporaryLease(M.ROOT..'/'..pid..'.lease'),
    'Snapshot cache owner is unavailable')
  local ok,reason=xpcall(function()
    local owners={}
    for _,entry in ipairs(ucp.internal.io.files(M.ROOT..'/') or {}) do
      local name=entry:gsub('\\','/'):match('([^/]+)$')
      local owner,suffix
      if name then owner,suffix=name:match('^(%d+)%-%d+%.([a-z%.]+)$') end
      -- Use a fixed parent and a strictly generated basename, never a listed
      -- path supplied by a VFS provider or any recursive removal.
      if owner and suffixes[suffix] then
        owners[owner]=owners[owner] or {}; table.insert(owners[owner],name)
      end
    end
    for owner,names in pairs(owners) do
      local release=owner==pid and function() end or platform.tryTemporaryLease(M.ROOT..'/'..owner..'.lease')
      if release then
        local removed,err=pcall(function()
          for _,name in ipairs(names) do
            local deleted,message,code=os.remove(M.ROOT..'/'..name)
            assert(deleted or code==2,message)
          end
        end)
        release(); assert(removed,err)
      end
    end
  end,debug.traceback)
  if not ok then own(); error(reason) end
  process,lease,serial=pid,own,0 -- keep the process lease; the OS closes it on exit/crash
end

function M.allocate()
  initialize()
  serial=serial+1
  return M.ROOT..'/'..process..'-'..serial
end

return M
