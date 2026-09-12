-- The game maintains SkirmishStatistics throughout the match. Keep the same
-- observed boundary as the recorder; never invoke victory/defeat processing.
local M={SIZE=0xbf0,RESULTS_SIZE=0x778}

function M.verify()
  return require('code/result-sites').verify().statistics
end

function M.new(engine,layout)
  return setmetatable({engine=engine,layout=layout,buffer=core.allocate(M.SIZE+1,true),
    alive=core.allocate(18,true),backup=core.allocate(M.SIZE,true),
    pack=core.exposeCode(layout.pack,1,0),score=core.exposeCode(layout.score,1,0)},{__index=M})
end

function M:begin()
  -- The native packer only writes this temporary entry (including local date),
  -- reads accumulated statistics, and calculates its existing skirmish score.
  core.copyMemory(self.backup,self.layout.temporary,M.SIZE)
  local ok,reason=pcall(function()
    self.pack(0)
    core.copyMemory(self.buffer,self.layout.temporary,M.SIZE)
  end)
  core.copyMemory(self.layout.temporary,self.backup,M.SIZE)
  assert(ok,reason)
  self.timeOrigin=core.readInteger(self.engine.sites.gameCore+0x236c)
  self:observe()
end

function M:observe()
  -- Fixed-size native copies, no Lua string allocation, hashing or disk work
  -- in the simulation loop. The existing native counters remain read-only.
  core.copyMemory(self.buffer+0x478,self.layout.results,M.RESULTS_SIZE)
  core.copyMemory(self.buffer+0x3f4,self.layout.groups,36)
  core.copyMemory(self.buffer+0x418,self.layout.ai,36)
  core.copyMemory(self.alive,self.layout.alive,18)
  self.tick=self.engine:tick()
  core.writeInteger(self.buffer+0x474,self.tick)
  core.writeInteger(self.buffer+0x3ec,self.score(self.engine:player()))
end

function M:write(manifest)
  local tick=manifest.lastObservedTick or manifest.lastTick
  assert(tick==self.tick,'Battle statistics boundary differs from replay')
  -- gameDuration is refreshed by native save/end processing, not every tick.
  -- Snapshot history needs the same elapsed-time calculation even when no game
  -- save occurred. Keep it in our private record and out of the simulation loop.
  local duration=(require('code/platform').multimediaMilliseconds()-self.timeOrigin)%4294967296
  core.writeInteger(self.buffer+0x470,math.floor(duration/60000))
  local date=os.date('*t')
  manifest.savedAt=os.date('!%Y-%m-%dT%H:%M:%SZ')
  core.writeInteger(self.buffer+0x464,date.day)
  core.writeInteger(self.buffer+0x468,date.month)
  core.writeInteger(self.buffer+0x46c,date.year)
  for slot=0,8 do core.writeInteger(self.buffer+0x43c+slot*4,core.readSmallInteger(self.alive+slot*2)) end
  local raw=core.readString(self.buffer,M.SIZE)
  local path=manifest.path or require('code/sessions').path(manifest.id)
  require('code/sessions').write(path..'/battle.bin',raw)
  manifest.battle={format=1,bytes=M.SIZE,tick=tick,sha256=sha.sha256(raw)}
end

function M.read(manifest)
  local info=assert(manifest.battle,'Recording has no battle statistics')
  assert(info.format==1 and info.bytes==M.SIZE,'Unsupported battle statistics')
  assert(info.tick==(manifest.lastObservedTick or manifest.lastTick),'Battle statistics boundary differs from replay')
  local path=manifest.path or require('code/sessions').path(manifest.id)
  local raw=require('code/world-reader').read(path..'/battle.bin',M.SIZE)
  assert(#raw==M.SIZE and sha.sha256(raw)==info.sha256,'Battle statistics are damaged')
  return raw
end
return M
