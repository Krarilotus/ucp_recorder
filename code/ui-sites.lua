-- Native UI entry points/pointer operands checked against both original executables.
-- Signatures and ABI: UCP ui module ui/game.lua and ui/headers/latest/ui.h.
return {
  SHC = {
    menuConstructor = {address=0x004F4100, bytes={81,83,139,217}},
    modalConstructor = {address=0x004A9E00, bytes={139,84,36,8,139,193,139,76,36,4,137,8}},
    activateModal = {address=0x004A9ED0, bytes={83,85,51,237,57,108,36,16}},
    text = {address=0x00474250, bytes={131,124,36,28,0,83,86,139,241,117,6,199,6,0,0,0,0,139,92,36,12,133,219,116,124}},
    border = {address=0x004711B0, bytes={86,139,241,232,152,122,255,255,139,68,36,24,139,76,36,20,139,84,36,16,80,139,68,36,16,81,139,76,36,16,82,80,81,139,206,232,168,122,255,255,133,192,116,54}},
    buttonState = {address=0x00428615, bytes={139,61,168,49,237,0,141,68,56,101}, value=0x00ED31A8},
    textManager = {address=0x004337DC, bytes={137,21,120,117,21,2,126,5}, value=0x02157578},
    pencil = {address=0x004090B9, bytes={185,32,215,145,1,232,205,125,6,0,57,126,216}, value=0x0191D720},
    gold = {address=0x004679AA, bytes={102,163,216,51,223,0,232,155,254,255,255,106,88}, value=0x00DF33D8},
    modalComposition = {address=0x0042544C, bytes={185,144,124,254,1,232,122,74,8,0,94,91,233,147,114,9,0}, value=0x01FE7C90},
    modalStack = {address=0x004A9E40, bytes={139,21,164,66,223,0,137,80,36}, value=0x00DF42A4},
  },
  Extreme = {
    menuConstructor = {address=0x004F4490, bytes={81,83,139,217}},
    modalConstructor = {address=0x004A9F70, bytes={139,84,36,8,139,193,139,76,36,4,137,8}},
    activateModal = {address=0x004AA040, bytes={83,85,51,237,57,108,36,16}},
    text = {address=0x00474480, bytes={131,124,36,28,0,83,86,139,241,117,6,199,6,0,0,0,0,139,92,36,12,133,219,116,124}},
    border = {address=0x004713D0, bytes={86,139,241,232,168,122,255,255,139,68,36,24,139,76,36,20,139,84,36,16,80,139,68,36,16,81,139,76,36,16,82,80,81,139,206,232,184,122,255,255,133,192,116,54}},
    buttonState = {address=0x00428645, bytes={139,61,40,54,237,0,141,68,56,101}, value=0x00ED3628},
    textManager = {address=0x00433A1C, bytes={137,21,120,170,190,2,126,5}, value=0x02BEAA78},
    pencil = {address=0x004090C9, bytes={185,144,71,53,2,232,221,127,6,0,57,126,216}, value=0x02354790},
    gold = {address=0x00467BDA, bytes={102,163,120,53,223,0,232,155,254,255,255,106,88}, value=0x00DF3578},
    modalComposition = {address=0x004254FC, bytes={185,144,177,167,2,232,58,75,8,0,94,91,233,83,115,9,0}, value=0x02A7B190},
    modalStack = {address=0x004A9FB0, bytes={139,21,60,67,223,0,137,80,36}, value=0x00DF433C},
  },
}
