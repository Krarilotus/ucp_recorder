-- Shared identifying contexts for the existing replay-scope gates.
return {
  {name='weddings',pattern=
    '0F BF 05 ? ? ? ? 99 F7 FE B9 ? ? ? ? 8B 74 94 0C E8 ? ? ? ? 0F BF 05 ? ? ? ? 99 F7 FF B9 ? ? ? ? 8B BC 94 9C 01 00 00 E8 ?'..' '..
    '? ? ?',
    rngFields={{3,0},{11,0},{27,0},{35,0}},
    ownerFields={},sites={
      {name='weddingHusband',offset=19,size=5,kind='call',patch='skip',stream=1},
      {name='weddingWife',offset=46,size=5,kind='call',patch='skip',stream=1},
    }},
  {name='taunt',pattern=
    'B9 ? ? ? ? E8 ? ? ? ? 8B C3 99 F7 FF 33 C0 8D 49 00 8B 4C 84 14 8B F9 69 FF F4 39 00 00 8B BF ? ? ? ? 2B 14 FD ? ? ? ? 78 08 03'..' '..
    'C5 3B C6 7C DF EB 61 8B C1 69 C0 F4 39 00 00 8B 90 ? ? ? ?',
    rngFields={{1,0}},
    ownerFields={},sites={
      {name='aiTauntReply',offset=5,size=5,kind='call',patch='skip',stream=1},
    }},
  {name='headsSelection',pattern=
    '0F BF 05 ? ? ? ? 99 B9 07 00 00 00 F7 F9 B9 ? ? ? ? 89 15 ? ? ? ? E8 ? ? ? ? E9 ? ? ? ?',
    rngFields={{3,0},{16,0}},
    ownerFields={},sites={
      {name='headsSelection',offset=26,size=5,kind='call',patch='skip',stream=1},
    }},
  {name='headsNextPreview',pattern=
    '0F BF 05 ? ? ? ? 99 B9 07 00 00 00 F7 F9 5E 5F 5D B9 ? ? ? ? 5B 89 15 ? ? ? ? 83 C4 08 E9 ? ? ? ?',
    rngFields={{3,0},{19,0}},
    ownerFields={},sites={
      {name='headsNextPreview',offset=33,size=5,kind='tail',patch='return',stream=1},
    }},
  {name='ambientSound',pattern=
    'B9 ? ? ? ? E8 ? ? ? ? F6 05 ? ? ? ? 01 74 04 8B 7C F4 1C 83 C6 01 3B F5 7C D5 8B 1D ? ? ? ? 3B FB 0F 84 ? ? ? ? 83 FF 04 8B'..' '..
    '15 ? ? ? ? 8B 0D ? ? ? ? 75 0C 85 C9 75 08',
    rngFields={{1,0},{12,0}},
    ownerFields={},sites={
      {name='ambientSound',offset=5,size=5,kind='call',patch='skip',stream=1},
    }},
  {name='resourceSpeech',pattern=
    'B9 ? ? ? ? E8 ? ? ? ? 8D 47 FF 83 F8 05 77 72 FF 24 85 ? ? ? ? 83 C6 32 56 B9 ? ? ? ? E8 ? ? ? ? 5E 5F C2 08 00 83 C6 3A 56'..' '..
    'B9 ? ? ? ? E8 ? ? ? ? 5E 5F C2 08 00 83 C6 36',
    rngFields={{1,0}},
    ownerFields={},sites={
      {name='resourceSpeech',offset=5,size=5,kind='call',patch='skip',stream=1},
    }},
  {name='audioLaunch',pattern=
    '0F BF 05 ? ? ? ? 25 03 00 00 80 C7 05 ? ? ? ? 01 00 00 00 79 05 48 83 C8 FC 40 B9 ? ? ? ? A3 ? ? ? ? E8 ? ? ? ? 0F BF 0D ?'..' '..
    '? ? ? 81 E1 03 00 00 80 79 05 49 83 C9 FC 41 8B 15 ? ? ? ? 33 C0 83 C1 01 89 0D ? ? ? ? A3 ? ? ? ? 89 15 ? ? ? ? A3 ? ? ?'..' '..
    '? A3 ? ? ? ? A3 ? ? ? ? A3 ? ? ? ? A3 ? ? ? ? A3 ? ? ? ? A3 ? ? ? ? C3',
    rngFields={{3,0},{30,0},{47,0}},
    ownerFields={{66,'tick'}},sites={
      {name='audioLaunch',offset=39,size=5,kind='call',patch='skip',stream=1},
    }},
  {name='battleMusic',pattern=
    'B9 ? ? ? ? E8 ? ? ? ? 0F BF 05 ? ? ? ? 99 B9 03 00 00 00 F7 F9 2B D3 74 21 83 EA 01 8B CF 74 0D 6A 02 E8 ? ? ? ? 5E 5B 5F C2 04'..' '..
    '00 6A 1C E8 ? ? ? ? 5E 5B 5F C2 04 00 6A 1B 8B CF E8 ? ? ? ? 5E 5B 5F C2 04 00 83 FE 02 0F 85 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ?'..' '..
    '39 1D ? ? ? ? 74 28 53 8B CF E8 ? ? ? ? B8 01 00 00 00 89 9F 54 01 00 00 89 9F 74 32 00 00',
    rngFields={{1,0},{13,0},{87,0}},
    ownerFields={{98,'mode'}},sites={
      {name='battleMusic1',offset=5,size=5,kind='call',patch='skip',stream=1},
      {name='battleMusic2',offset=91,size=5,kind='call',patch='skip',stream=1},
    }},
  {name='ambientMusic',pattern=
    'B9 ? ? ? ? E8 ? ? ? ? 0F BF 05 ? ? ? ? 99 B9 03 00 00 00 F7 F9 3B D7 75 1D C7 05 ? ? ? ? 01 00 00 00 EB 2C 3D 50 C3 00 00 7D 98'..' '..
    '83 C0 01 A3 ? ? ? ? EB 8E 83 EA 01 F7 DA 1B D2',
    rngFields={{1,0},{13,0}},
    ownerFields={},sites={
      {name='ambientMusic',offset=5,size=5,kind='call',patch='skip',stream=1},
    }},
  {name='moodMusic',pattern=
    '53 55 56 8B F1 B9 ? ? ? ? E8 ? ? ? ? A1 ? ? ? ? 8B 0D ? ? ? ? 33 DB 3B C3 74 34 8B D1 69 D2 F4 39 00 00 83 BA ? ? ? ? 32 7D'..' '..
    '23 83 F8 63 75 08 39 1D ? ? ? ? 74 16 0F BF 15 ? ? ? ? 81 E2 03 00 00 80 79 16 4A 83 CA FC 42 EB 0F 0F BF 05 ? ? ? ? 99 BD 05 00 00'..' '..
    '00 F7 FD 3B D3 0F 8E CA 00 00 00 B9 ? ? ? ? E8 ? ? ? ? 0F BF 05 ? ? ? ? 25 01 00 00 80 79 05 48 83 C8 FE 40 B9 ? ? ? ? 75 53 E8'..' '..
    '? ? ? ? 0F BF 0D ? ? ? ? 81 E1 03 00 00 80 79 05 49 83 C9 FC 41 89 0D ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? 0F BF 05 ? ? ? ? 99'..' '..
    'B9 18 00 00 00 F7 F9 8B CE 89 15 ? ? ? ? 83 C2 49 52 E8 ? ? ? ? 89 9E 88 32 00 00 5E 5D 5B C3 E8 ? ? ? ? 0F BF 15 ? ? ? ? 81 E2'..' '..
    '03 00 00 80 79 05 4A 83 CA FC 42 B9 ? ? ? ? 89 15 ? ? ? ? E8 ? ? ? ? 0F BF 05 ? ? ? ? 99 B9 13 00 00 00 F7 F9 8B CE 89 15 ? ?'..' '..
    '? ? 83 C2 61 52 E8 ? ? ? ? 89 9E 88 32 00 00 5E 5D 5B C3 69 C9 F4 39 00 00 83 B9 ? ? ? ? 32 BD 01 00 00 00 7D 68 B9 ? ? ? ? E8 ?'..' '..
    '? ? ? 0F BF 05 ? ? ? ? 99 B9 05 00 00 00 F7 F9 83 FA 04 0F 87 91 00 00 00 FF 24 95 ? ? ? ? 6A 0A 8B CE E8 ? ? ? ? EB 7F 39 1D ?'..' '..
    '? ? ? 74 0B 6A 0D 8B CE E8 ? ? ? ? EB 6C 6A 10 8B CE E8 ? ? ? ? EB 61 6A 0C 8B CE E8 ? ? ? ? EB 56 6A 0B 8B CE E8 ? ? ? ? EB'..' '..
    '4B 39 1D ? ? ? ? 75 09 6A 0E 8B CE E8 ? ? ? ? 39 2D ? ? ? ? 75 09 6A 0F 8B CE E8 ? ? ? ? 83 3D ? ? ? ? 02 75 09 6A 14 8B CE'..' '..
    'E8 ? ? ? ? A1 ? ? ? ? 03 C5 83 F8 02 A3 ? ? ? ? 7E 06 89 1D ? ? ? ? 89 9E 88 32 00 00 01 2D ? ? ? ? 89 9E 88 32 00 00 5E 5D'..' '..
    '5B C3',
    rngFields={{6,0},{65,0},{87,0},{108,0},{120,0},{137,0},{151,0},{175,0},{187,0},{234,0},{252,0},{270,0},{330,0},{342,0}},
    ownerFields={{16,'mode'},{22,'player'}},sites={
      {name='moodMusic1',offset=10,size=5,kind='call',patch='skip',stream=1},
      {name='moodMusic2',offset=112,size=5,kind='call',patch='skip',stream=1},
      {name='moodMusic3',offset=143,size=5,kind='call',patch='skip',stream=1},
      {name='moodMusic4',offset=179,size=5,kind='call',patch='skip',stream=1},
      {name='moodMusic5',offset=226,size=5,kind='call',patch='skip',stream=1},
      {name='moodMusic6',offset=262,size=5,kind='call',patch='skip',stream=1},
      {name='moodMusic7',offset=334,size=5,kind='call',patch='skip',stream=1},
    }},
  {name='dustRNG',pattern=
    'B9 ? ? ? ? E8 ? ? ? ? 83 86 ? ? ? ? 01 8B 8E ? ? ? ? B8 D3 4D 62 10 F7 ED C1 FA 05 8B C2 C1 E8 1F 03 C2 69 C0 F4 01 00 00 8B FD'..' '..
    '2B F8 8B C1 99 BB F4 01 00 00 F7 FB 3B FA 75 23',
    rngFields={{1,0}},
    ownerFields={},sites={
      {name='dustRNG',offset=5,size=5,kind='call',patch='skip',stream=2},
    }},
  {name='dustEntity',pattern=
    '6A 15 6A 00 6A 00 6A 00 52 8D 04 C5 04 00 00 00 50 8D 0C CD 04 00 00 00 51 6A 00 6A 00 6A 00 B9 ? ? ? ? E8 ? ? ? ? 8B 44 24 10 83 C0 01'..' '..
    '83 C3 04 3B 86 ? ? ? ? 89 44 24 10 0F 8C ? ? ? ? 5F 5E 5D 5B 59 C3',
    rngFields={},
    ownerFields={},sites={
      {name='dustEntity',offset=36,size=5,kind='call',patch='cleanup'},
    }},
  {name='motherSound',pattern=
    'B9 ? ? ? ? E8 ? ? ? ? 8B 3D ? ? ? ? 8B C7 69 C0 90 04 00 00 8B 88 ? ? ? ? 3B CB 7F 0C C7 05 ? ? ? ? 01 00 00 00 EB 0C 81 C1'..' '..
    '00 01 00 00 89 88 ? ? ? ? 83 3D ? ? ? ? 63',
    rngFields={{1,0}},
    ownerFields={{60,'mode'}},sites={
      {name='motherSound',offset=5,size=5,kind='call',patch='skip',stream=2},
    }},
  {name='music',pattern=
    'B9 ? ? ? ? E8 ? ? ? ? 0F BF 05 ? ? ? ? 99 B9 13 00 00 00 F7 F9 3B 15 ? ? ? ? 75 08 83 C7 01 83 FF 10 7C D7 89 15 ? ? ? ? 8B'..' '..
    '14 D5 ? ? ? ? 52 8B CE E8 ? ? ? ? A1 ? ? ? ? 83 E8 01 83 F8 03 A3 ? ? ? ? 7E 74 C7 05 ? ? ? ? 00 00 00 00 EB 68 83 3D ? ?'..' '..
    '? ? 00 7E 5F 33 FF 8D 49 00 B9 ? ? ? ? E8 ? ? ? ? 0F BF 05 ? ? ? ? 99 B9 18 00 00 00 F7 F9 3B 15 ? ? ? ? 75 08 83 C7 01 83 FF'..' '..
    '10 7C D7 89 15 ? ? ? ? 8B 14 D5 ? ? ? ? 52 8B CE E8 ? ? ? ?',
    rngFields={{1,0},{13,0},{107,0},{119,0}},
    ownerFields={},sites={
      {name='music2',offset=5,size=5,kind='call',patch='skip',stream=1},
      {name='music1',offset=111,size=5,kind='call',patch='skip',stream=1},
    }},
  {name='music3',pattern=
    'B9 ? ? ? ? E8 ? ? ? ? 0F BF 05 ? ? ? ? 99 F7 FE 8B 74 94 14 83 C6 22 8B 14 F5 ? ? ? ? 8B 4C 24 10 52 E8 ? ? ? ? 8B 6C 24 10'..' '..
    '89 35 ? ? ? ? E9 ? ? ? ? 33 F6 89 1D ? ? ? ?',
    rngFields={{1,0},{13,0}},
    ownerFields={},sites={
      {name='music3',offset=5,size=5,kind='call',patch='skip',stream=1},
    }},
  {name='mothers',pattern=
    '83 3D ? ? ? ? 63 75 2B 83 3C 10 00 74 12 83 3C 16 64 7E 2C C7 04 10 00 00 00 00 E9 ? ? ? ? 83 3C 16 28 0F 8F ? ? ? ? C7 04 10 01 00'..' '..
    '00 00 EB 0D 83 BA 08 21 00 00 00 0F 8F ? ? ? ?',
    rngFields={},
    ownerFields={{2,'mode'}},sites={
      {name='mothers',offset=7,size=6,kind='branch',patch='taken',condition=133},
    }},
}
