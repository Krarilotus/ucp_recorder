-- One catalogue feeds the original battle-history screen. Legacy game results
-- and replay checkpoints share its native entry layout, but keep separate IDs.
local store=require('code/sessions')
local stats=require('code/battle-statistics')
local native=require('code/native')
local M={}

local function word(raw,offset)
  local a,b,c,d=raw:byte(offset+1,offset+4)
  return a+b*256+c*65536+d*16777216
end

local function validate(raw)
  assert(type(raw)=='string' and #raw==stats.SIZE,'Invalid battle entry size')
  assert(raw:sub(5,1004):find('\0',1,true),'Battle name is not terminated')
  assert(word(raw,0x3f0)<=8,'Battle has too many players')
  return raw
end

function M.new(sites)
  return setmetatable({sites=sites,items={},sortColumn=4,descending=true},{__index=M})
end

function M:refresh()
  local count=core.readInteger(self.sites.storedCount)
  assert(count>=0 and count<=250,'Native battle history count is invalid')
  local items={}
  for index=0,count-1 do
    local raw=validate(core.readString(self.sites.records+index*stats.SIZE,stats.SIZE))
    local id='native-'..sha.sha256(raw)
    items[#items+1]={id=id,raw=raw,
      created=string.format('%04d-%02d-%02dT00:00:00Z',word(raw,0x46c),word(raw,0x468),word(raw,0x464))}
  end
  for _,manifest in ipairs(store.list()) do
    if manifest.variant==native.profile.name and manifest.battle then
      local raw=validate(stats.read(manifest))
      items[#items+1]={id=manifest.id,raw=raw,manifest=manifest,name=manifest.displayName,
        created=manifest.savedAt or manifest.created}
    end
  end
  self.items=items
  self:sort()
  if self.selected then
    local id=self.selected.id; self.selected=nil
    for _,item in ipairs(items) do if item.id==id then self.selected=item; break end end
  end
end

function M:sort(column)
  if column then
    assert(column>=1 and column<=4,'Unknown battle sorting column')
    if column==self.sortColumn then self.descending=not self.descending
    else self.descending=column~=2 end
    self.sortColumn=column
  end
  local function value(item)
    if self.sortColumn==2 then return (item.name or item.raw:sub(5,1004):match('^[^%z]*')):lower() end
    if self.sortColumn==3 then return word(item.raw,0x470) end
    return item.created
  end
  table.sort(self.items,function(a,b)
    local av,bv=value(a),value(b)
    if av==bv then return a.id>b.id end
    if self.descending then return av>bv end
    return av<bv
  end)
end

function M:display(item)
  local raw=item.raw
  if item.name then
    local name=require('code/locale').native(item.name):sub(1,999)
    -- A custom name uses the native map-name branch rather than trail lookup.
    raw=string.rep('\0',4)..name..string.rep('\0',1000-#name)..raw:sub(1005)
  end
  return raw
end

function M:rename(name)
  local item=assert(self.selected,'Choose a battle')
  assert(item.manifest,'Only recordings can be renamed')
  name=require('code/validation').displayName(name)
  item.manifest.displayName=name; store.save(item.manifest)
  self:refresh()
end

function M:title()
  local item=self.selected
  return item and (item.name or item.raw:sub(5,1004):match('^[^%z]*')) or ''
end
return M
