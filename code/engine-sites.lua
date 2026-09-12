-- Checked native entry points used by session capture and playback.
return {
  SHC = {
    resultsTimer = {address=0x004AFB4A, bytes={61,64,31,0,0}, kind='raw', patch='equalFlags'},
    resultsBranch = {address=0x004AFB4F, bytes={118,41}},
    playerResources = 0x0115C2C8,
    resourceReset = {address=0x0040C334, bytes={137,20,157,200,194,21,1,131,192,1,131,248,25}},
  },
  Extreme = {
    resultsTimer = {address=0x004AFCBA, bytes={61,64,31,0,0}, kind='raw', patch='equalFlags'},
    resultsBranch = {address=0x004AFCBF, bytes={118,41}},
    playerResources = 0x011EEF08,
    resourceReset = {address=0x0040C344, bytes={137,20,157,8,239,30,1,131,192,1,131,248,25}},
  },
}
