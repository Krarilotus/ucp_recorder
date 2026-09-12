-- Presentation positions span recovery segments, even when synchronization
-- restored an earlier native clock. The segment still owns its command stream.
local M={}
local Timeline={}

function M.new(first,worlds)
  local self=setmetatable({entries={},byId={},total=0},{__index=Timeline})
  local manifest=first
  while manifest do
    assert(#self.entries<32 and not self.byId[manifest.id],'Invalid replay timeline')
    local entry={manifest=manifest,offset=self.total}
    self.entries[#self.entries+1]=entry; self.byId[manifest.id]=entry
    self.total=self.total+manifest.lastTick-manifest.startTick
    local nextWorld=worlds and worlds[manifest.nextReplay]
    manifest=nextWorld and nextWorld.manifest
  end
  return self
end

function Timeline:position(id,tick)
  local entry=assert(self.byId[id],'Replay segment is outside the timeline')
  local m=entry.manifest
  return entry.offset+math.max(0,math.min(tick,m.lastTick)-m.startTick),self.total
end

function Timeline:at(fraction)
  assert(type(fraction)=='number' and fraction>=0 and fraction<=1,'Invalid replay position')
  local target=math.floor(self.total*fraction)
  for index,entry in ipairs(self.entries) do
    local m=entry.manifest
    if target<entry.offset+m.lastTick-m.startTick or index==#self.entries then
      return m.id,m.startTick+target-entry.offset
    end
  end
end

return M
