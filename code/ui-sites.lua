-- UI 1.0.1 retains its exported bindings; only missing capabilities use AoB.
local contexts={
  activateModal={pattern='53 55 33 ED 39 6C 24 10 8B D9 75 16 39 2B 75 12 39 2D ? ? ? ? 74 0A B9 ? ? ? ? E8 ? ? ? ? 83 7B 2C 13 75 19 B9 ? ? ? ? C7 43 2C FF FF FF FF E8 ? ? ? ? 85 C0 0F 85 89 01 00 00', size=8, owner='UI.activateModalMenu'},
  avatar={pattern='53 8B 5C 24 08 55 56 33 ED 83 3C 9D ? ? ? ? FF 57 75 07 8B 2C 9D ? ? ? ? 8B 74 24 1C 8B 7C 24 18 56 57 8D 83 22 02 00 00 50 6A 2E B9 ? ? ? ? E8 ? ? ? ? 85 ED 75 78 8B 04 9D ? ? ? ?', size=9},
  basicButton={pattern='8B 44 24 04 83 EC 08 56 8B 35 ? ? ? ? 33 C9 83 F8 20 57 8B 3D ? ? ? ? 0F 84 38 05 00 00 83 F8 FF 75 0B 89 4C 24 14 8D 48 02 8B 44 24 14 8D 84 C0 E0 FE FF FF 03 C0 99 83 E2 1F 55 03 C2', size=16, owner='Rendering.renderButtonBackground'},
  border={pattern='56 8B F1 E8 ? ? ? ? 8B 44 24 18 8B 4C 24 14 8B 54 24 10 50 8B 44 24 10 51 8B 4C 24 10 52 50 51 8B CE E8 ? ? ? ? 85 C0 74 36 57 8B CE E8 ? ? ? ? 8B 56 3C 8B 7E 34 8B CE 89 56 34 E8 ? ? ? ?', size=44, owner='Rendering.drawBorderBox'},
  buildingAndStatus={pattern='83 3D ? ? ? ? 14 C7 05 ? ? ? ? 00 00 00 00 75 14 A1 ? ? ? ? 05 D8 01 00 00 50 6A 00 6A 03 E9 C4 00 00 00 A1 ? ? ? ? 83 F8 01 75 48 0F B7 0D ? ? ? ? A1 ? ? ? ? 51 8B 0D ? ? ? ?', size=7},
  clippedSprite={pattern='8B 44 24 04 8B 54 24 08 53 55 56 57 8B F9 8B 0C 85 ? ? ? ? 69 C0 58 14 00 00 8D 74 11 FF 8B 1C B5 ? ? ? ? 03 5F 78 83 BC 38 30 05 00 00 01 8D AC 38 30 05 00 00 75 27 8B C6 C1 E0 04 0F BF 88 ? ? ? ?', size=12},
  handleMenu={pattern='53 8B D9 56 8B 33 C7 43 14 00 00 00 00 8B 06 83 F8 66 0F 84 B9 01 00 00 57 8B 7C 24 10 8D 49 00 83 F8 64 75 27 A1 ? ? ? ? 39 46 18 0F 84 8E 01 00 00 83 FF 02 0F 84 85 01 00 00 8B 46 20 8D 0C 80', size=13},
  header={pattern='83 44 24 08 08 53 8B 5C 24 08 55 8B 6C 24 14 83 C3 08 83 ED 10 56 33 C0 57 89 44 24 14 8D 49 00 85 C0 75 05 8D 78 30 EB 0F 8B F8 83 EF 38 F7 DF 1B FF 83 E7 FA 83 C7 3C 33 F6 85 ED 7E 4C 8B 4C 24 18', size=25},
  mapViewport={pattern='8B 3D ? ? ? ? 03 CF 03 CE 69 C9 D8 0F 00 00 03 CA 03 0D ? ? ? ? 8B 15 ? ? ? ? 03 0D ? ? ? ? 8D 0C 4A 8B 55 F4 89 4D DC 8B 0A BA D8 0F 00 00 2B D1 03 D2 89 55 EC 8D 14 09 2B C2', size=24, operand=20},
  maskedSprite={pattern='51 83 3D ? ? ? ? 00 8B 15 ? ? ? ? 55 8B E9 56 8B 75 78 89 74 24 08 74 4E 8B 44 24 10 8B 0C 85 ? ? ? ? 8B 54 24 14 8D 4C 11 FF 8B 54 24 28 8B C1 8B 0C 8D ? ? ? ? 52 C1 E0 04 0F BF 90 ? ? ? ?', size=12},
  menuConstructor={pattern='51 53 8B D9 33 C9 56 8B 74 24 10 89 33 89 4B 04 89 4B 08 C7 43 0C E8 03 00 00 89 4B 18 89 4B 34 C7 43 1C 18 FC FF FF 83 3E 66 89 5C 24 08 0F 84 1C 01 00 00 55 57 8D 46 04 EB 09 EB 03 8D 49 00', size=4, owner='UI.Menu'},
  missionBar={pattern='6A 04 68 A4 00 00 00 B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? 6A 00 6A 03 68 A4 00 00 00 8D 56 08 52 57 6A 01 68 A4 00 00 00 B9 ? ? ? ? E8 ? ? ? ? C7 05 ? ? ? ? 01 00 00 00', size=17, operand=8},
  modalConstructor={pattern='8B 54 24 08 8B C1 8B 4C 24 04 89 08 8B 4C 24 0C 89 50 04 8B 54 24 10 89 48 08 8B 4C 24 14 89 50 0C 8B 54 24 18 89 48 10 8B 4C 24 1C 89 50 14 8B 54 24 20 89 48 18 8B 4C 24 24 89 50 1C 89 48 20', size=12, owner='UI.MenuModal'},
  playerSummary={pattern='83 EC 10 8B 0D ? ? ? ? 69 C9 F4 39 00 00 8B 91 ? ? ? ? B8 1F 85 EB 51 F7 EA 8B 81 ? ? ? ? 53 55 8B A9 ? ? ? ? C1 FA 05 56 8B B1 ? ? ? ? 89 4C 24 18 8B 0D ? ? ? ? 8B DA', size=9},
  reportPause={pattern='83 3D ? ? ? ? 00 0F 85 BD 02 00 00 A1 ? ? ? ? BB 01 00 00 00 3B C3 0F 84 8E FE FF FF 83 F8 06 0F 84 85 FE FF FF 83 3D ? ? ? ? 0F 75 0F B9 ? ? ? ? E8 ? ? ? ? A1 ? ? ? ?', size=7, kind='raw', patch='equalFlags'},
  spriteClip={pattern='8B 44 24 04 8B 54 24 08 89 81 54 C8 16 00 8B 44 24 0C 89 91 58 C8 16 00 8B 54 24 10 89 81 5C C8 16 00 89 91 60 C8 16 00 C2 10 00', size=12},
  text={pattern='83 7C 24 1C 00 53 56 8B F1 75 06 C7 06 00 00 00 00 8B 5C 24 0C 85 DB 74 7C 8B C3 8D 50 01 8B FF 8A 08 83 C0 01 84 C9 75 F7 8B 4C 24 20 57 8D 4C C9 12 2B C2 8D 3C 8E 50 53 8B CF E8 ? ? ? ?', size=25, owner='Rendering.renderTextToScreenConst'},
  textWidth={pattern='56 8B 74 24 08 85 F6 75 06 33 C0 5E C2 08 00 8B C6 57 8D 78 01 8A 10 83 C0 01 84 D2 75 F7 2B C7 50 8B 44 24 14 8D 44 C0 12 56 8D 0C 81 E8 ? ? ? ? 5F 5E C2 08 00', size=15},
  updateMenu={pattern='56 57 8B F1 33 FF 39 7E 38 75 03 89 7E 3C 89 7E 38 89 7E 40 57 89 3D ? ? ? ? E8 ? ? ? ? 89 7E 10 5F 5E C3', size=6},
}
local ownerValues={
  textManager='Rendering.textManager', pencil='Rendering.pencilRenderCore',
  gold='Rendering.Colors.pGreyishYellow', buttonState='Rendering.ButtonState',
  buttonSurface='Rendering.alphaAndButtonSurface', mouse='Input.mouseState',
  modalComposition='UI.MenuModalComposition1',
}
local M={}
local function pointer(ffi,value,name)
  assert(value~=nil,'Recorder UI owner is missing '..name)
  local address=ffi.tonumber(ffi.cast('unsigned long',value))
  assert(type(address)=='number' and address>0 and address<0x80000000,
    'Recorder UI owner returned an invalid '..name)
  return address
end
local function member(object,path)
  for key in path:gmatch('[^.]+') do object=object and object[key] end
  return object
end
function M.resolve(api,ffi)
  assert(api and api.game and api.manager,'Recorder requires UI 1.0.1 access')
  local sites={}
  local check=require('code/hook-check')
  for name,context in pairs(contexts) do
    local guard=context.owner
      and check.context(pointer(ffi,member(api.game,context.owner),name),context.pattern,'Recorder UI '..name)
      or check.resolve(context.pattern,'Recorder UI '..name)
    local address=guard.address
    sites[name]={address=address,bytes=core.readBytes(address,context.size),
      kind=context.kind,patch=context.patch,guard=guard}
    if context.operand then sites[name].value=core.readInteger(address+context.operand) end
  end
  for name,path in pairs(ownerValues) do
    sites[name]={value=pointer(ffi,member(api.game,path),name)}
  end
  local state=api.manager.getState()
  sites.modalStack={value=pointer(ffi,state and state.modalMenuStackTop,'modal stack')}
  -- Native update clears this flag immediately before dispatching menu items.
  sites.menuHit={value=core.readInteger(sites.updateMenu.address+23)}
  assert(sites.menuHit.value>0,'Recorder UI has an invalid menu hit flag')
  -- Three calls in the mission strip must address the same texture owner.
  local bar=sites.missionBar
  assert(core.readInteger(bar.address+18)==bar.value and core.readInteger(bar.address+49)==bar.value,
    'Recorder UI mission texture operands disagree')
  local viewport=sites.mapViewport
  assert(core.readInteger(viewport.address+2)==viewport.value+4,
    'Recorder UI viewport coordinate layout differs')
  -- The native building/status selector is WindowState.currentBuildMenu (+0x5c).
  sites.window={value=core.readInteger(sites.buildingAndStatus.address+2)-0x5c}
  assert(sites.window.value>0,'Recorder UI has an invalid window state')
  return sites
end
return M
