"""Resolver contract at relocated synthetic addresses; real images tested separately."""
from pathlib import Path
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT = Path(__file__).resolve().parents[1]


class UIBindingTests(unittest.TestCase):
    def fixture(self, runtime):
        lua = runtime(unpack_returned_tuples=True)
        lua.globals().source_root = ROOT.as_posix()
        lua.execute("""
package.path=source_root..'/?.lua;'..package.path
resolver=require('code/ui-sites')
local contexts
for i=1,20 do
 local name,value=debug.getupvalue(resolver.resolve,i)
 if name=='contexts' then contexts=value end
end
assert(contexts)
local addresses,bytes,integers={},{},{}
local serial=0x10000000
api={game={UI={},Rendering={Colors={}},Input={}},manager={}}
ffi={cast=function(_,p) return p end,tonumber=tonumber}
local function put(path,value)
 local parent=api.game; local parts={}
 for key in path:gmatch('[^.]+') do parts[#parts+1]=key end
 for i=1,#parts-1 do parent=parent[parts[i]] end
 parent[parts[#parts]]=value
end
expected={}; patterns={}; scans=0
for name,c in pairs(contexts) do
 serial=serial+0x1000; expected[name]=serial; patterns[name]=c.pattern
 if c.owner then put(c.owner,serial) else addresses[c.pattern]=serial end
 local i=0
 for token in c.pattern:gmatch('%S+') do
  bytes[serial+i]=token=='?' and 0x11 or tonumber(token,16); i=i+1
 end
end
local bar=expected.missionBar
integers[bar+8]=0x20000000; integers[bar+18]=0x20000000; integers[bar+49]=0x20000000
integers[expected.mapViewport+20]=0x20010000
integers[expected.mapViewport+2]=0x20010004
integers[expected.buildingAndStatus+2]=0x2002005c
integers[expected.updateMenu+23]=0x20030000
api.game.Rendering.textManager=0x20040000
api.game.Rendering.pencilRenderCore=0x20050000
api.game.Rendering.Colors.pGreyishYellow=0x20060000
api.game.Rendering.ButtonState=0x20070000
api.game.Rendering.alphaAndButtonSurface=0x20080000
api.game.Input.mouseState=0x20090000
api.game.UI.MenuModalComposition1=0x200a0000
api.manager.getState=function() return {modalMenuStackTop=0x200b0000} end
core={
 AOBScan=function(pattern) scans=scans+1; assert(addresses[pattern],'owner was scanned');return addresses[pattern] end,
 scanForAOB=function(pattern,start) assert(start==addresses[pattern]+1); return 0 end,
 readBytes=function(a,n) local t={};for i=1,n do t[i]=bytes[a+i-1] or 0 end;return t end,
 readInteger=function(a) return integers[a] or 0 end,
}
function changeByte(address) bytes[address]=0xcc end
function changeOperand(address) integers[address]=123 end
""")
        return lua

    def test_relocated_owner_exports_and_decoded_roots_on_both_lua_runtimes(self):
        for runtime in (Lua54, LuaJIT):
            with self.subTest(runtime=runtime):
                self.fixture(runtime).execute("""
sites=resolver.resolve(api,ffi)
for name,address in pairs(expected) do assert(sites[name].address==address,name) end
assert(scans==13)
assert(sites.window.value==0x20020000 and sites.menuHit.value==0x20030000)
assert(sites.missionBar.value==0x20000000 and sites.mapViewport.value==0x20010000)
assert(sites.modalStack.value==0x200b0000 and sites.textManager.value==0x20040000)
assert(sites.reportPause.kind=='raw' and sites.reportPause.patch=='equalFlags')
assert(#sites.reportPause.bytes==7 and #sites.reportPause.guard.bytes>7)
""")

    def test_missing_ambiguous_owner_and_operand_conflicts_are_rejected(self):
        cases = (
            "core.AOBScan=function() return 0 end",
            "core.scanForAOB=function() return 123 end",
            "api.game.UI.Menu=nil",
            "api.manager.getState=function() return {} end",
            "changeByte(expected.activateModal)",
            "changeByte(expected.handleMenu+20)",
            "changeOperand(expected.missionBar+18)",
            "changeOperand(expected.mapViewport+2)",
        )
        for runtime in (Lua54, LuaJIT):
            for case in cases:
                with self.subTest(runtime=runtime,case=case):
                    self.fixture(runtime).execute(case+"; assert(not pcall(resolver.resolve,api,ffi))")

    def test_hook_rechecks_full_preflight_context_without_scanning(self):
        for runtime in (Lua54, LuaJIT):
            with self.subTest(runtime=runtime):
                self.fixture(runtime).execute("""
local sites=resolver.resolve(api,ffi)
local NativeUI=require('code/native-ui')
local ui=setmetatable({sites=sites},{__index=NativeUI})
local count=scans
assert(ui:site('handleMenu')==sites.handleMenu and scans==count)
-- Change an instruction after the overwritten prologue, not just its first byte.
changeByte(sites.handleMenu.address+20)
assert(not pcall(ui.site,ui,'handleMenu') and scans==count)
""")
