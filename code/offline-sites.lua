-- Offline playback owns transport isolation and wall-clock pacing. Keep the
-- actual multiplayer mode visible to native simulation and actor translation.
local M={}
for _,variant in ipairs({'SHC','Extreme'}) do
  local extreme=variant=='Extreme'
  local early=extreme and 0x110 or 0
  local late=extreme and 0x160 or 0
  local cookie=extreme and {176,67,185,0} or {32,66,185,0}
  local mode=extreme and {240,77,53,2} or {128,221,145,1}
  M[variant]={
    pacing={address=0x487a67+early,bytes={139,129,24,6,0,0},patch='constant',value=99},
    pauseMenu={address=extreme and 0x46bf40 or 0x46bd20,
      bytes={161,mode[1],mode[2],mode[3],mode[4]},patch='constant',value=99},
    receive={address=0x490690+late,
      bytes={131,236,104,161,cookie[1],cookie[2],cookie[3],cookie[4]},patch='return'},
    transmit={address=0x487c50+early,bytes={129,236,244,3,0,0},patch='return',pop=20},
    syncMessage={address=0x487e30+early,bytes={86,139,241,139,134,24,6,0,0},patch='return',pop=4},
    syncPacket={address=0x4880ec+early,bytes={139,134,24,6,0,0},patch='constant',value=99},
    autosave={address=0x48c660+early,bytes={86,139,241,139,134,24,6,0,0},patch='return'},
    syncPolling={address=0x490340+late,
      bytes={161,mode[1],mode[2],mode[3],mode[4]},patch='return'},
    lag={address=0x490480+late,bytes={81,83,86,139,241},patch='return'},
  }
end
return M
