-- Complete instructions for scope-gated simulation changes.
return {
  SHC = {
    {name="dustRNG",address=0x004FC4A3,kind="call",patch="skip",bytes={232,40,227,246,255}, target=0x0046A7D0},
    {name="dustEntity",address=0x004FC627,kind="call",patch="cleanup",bytes={232,180,132,240,255}, target=0x00404AE0},
    {name="motherSound",address=0x005474A3,kind="call",patch="skip",bytes={232,40,51,242,255}, target=0x0046A7D0},
    {name="music1",address=0x0047A8D5,kind="call",patch="skip",bytes={232,38,255,254,255}, target=0x0046A800},
    {name="music2",address=0x0047A86B,kind="call",patch="skip",bytes={232,144,255,254,255}, target=0x0046A800},
    {name="music3",address=0x0047C348,kind="call",patch="skip",bytes={232,179,228,254,255}, target=0x0046A800},
    {name="pause",address=0x0045CEFF,kind="branch",patch="fallthrough",bytes={117,45,161,84,160,254,1}, target=0x0045CF2E, condition=133},
    {name="pausedCamera",address=0x0045CE34,kind="branch",patch="taken",bytes={125,70,185,16,125,254,1}, target=0x0045CE7C, condition=141},
    {name="mothers",address=0x004582ED,kind="branch",patch="taken",bytes={117,43,131,60,16,0}, target=0x0045831A, condition=133},
    {name="seed",address=0x0046A74A,kind="seed",patch="seed",bytes={131,196,4,137,70,4}},
  },
  Extreme = {
    {name="dustRNG",address=0x004FC823,kind="call",patch="skip",bytes={232,200,225,246,255}, target=0x0046A9F0},
    {name="dustEntity",address=0x004FC9A7,kind="call",patch="cleanup",bytes={232,68,129,240,255}, target=0x00404AF0},
    {name="motherSound",address=0x005478C3,kind="call",patch="skip",bytes={232,40,49,242,255}, target=0x0046A9F0},
    {name="music1",address=0x0047AAA5,kind="call",patch="skip",bytes={232,118,255,254,255}, target=0x0046AA20},
    {name="music2",address=0x0047AA3B,kind="call",patch="skip",bytes={232,224,255,254,255}, target=0x0046AA20},
    {name="music3",address=0x0047C518,kind="call",patch="skip",bytes={232,3,229,254,255}, target=0x0046AA20},
    {name="pause",address=0x0045D10F,kind="branch",patch="fallthrough",bytes={117,45,161,84,213,167,2}, target=0x0045D13E, condition=133},
    {name="pausedCamera",address=0x0045D044,kind="branch",patch="taken",bytes={125,70,185,16,178,167,2}, target=0x0045D08C, condition=141},
    {name="mothers",address=0x0045851D,kind="branch",patch="taken",bytes={117,43,131,60,16,0}, target=0x0045854A, condition=133},
    {name="seed",address=0x0046A96A,kind="seed",patch="seed",bytes={131,196,4,137,70,4}},
  },
}
