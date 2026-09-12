-- Console-only check: Recorder + actual UI Menu API + installed CFFI/Lua/RPS.
-- lua_rps_host.exe <script> <recorder> <framework code> <cffi.dll> <ui header> <ui/menu.lua>
local source,framework=assert(arg[1]),assert(arg[2])
local ffi=assert(package.loadlib(assert(arg[3]),'luaopen_cffi'))()
local header=assert(io.open(assert(arg[4]),'rb'));ffi.cdef(header:read('*all'));header:close()
package.path=source..'/?.lua;'..package.path
ucp={internal=require('RPS')}
core=dofile(framework..'/core.lua');package.loaded.core=core
utils=dofile(framework..'/utils.lua')
log=function() end
modules={cffi={cffi=function() return ffi end}}
package.loaded['ui.game']={};package.loaded.manager={}
local api=dofile(assert(arg[5]))
local native,old,modal=ffi.new('Menu[1]',{}),ffi.new('MenuItem[10]',{}),ffi.new('struct MenuModal[1]',{})
local function pointer(value) return ffi.tonumber(ffi.cast('unsigned long',value)) end
for i=0,8 do old[i].menuItemType=3;old[i].menuPointer=native end
old[9].menuItemType=0x66;native[0].menuItemArray=old
modal[0].pointerToMenu=native;modal[0].height=357
local restart=pointer(old)+5*80
for offset,value in pairs({[4]=100,[8]=206,[12]=300,[16]=27,[20]=1001,[28]=1002}) do
 core.writeInteger(restart+offset,value)
end
local before=ffi.string(old,9*80)
modules.ui={access=function() return {api=api,manager={lookupModalMenu=function(id)
 assert(id==5);return ffi.cast('struct MenuModal *',modal)
end}} end}
local NativeUI=require('code/native-ui')
local ui=setmetatable({ITEM_SIZE=80,sites={},onError=error},{__index=NativeUI})
ui.trackVisibility=function(_,items,predicate) assert(#items==1 and predicate());ui.item=items[1] end
local playing=false
local state=require('code/pause-menu').attach(ui,'Save',function() end,
 function() return not playing end,function() return playing end)
assert(state.menu.menuItemsIndex==10 and native[0].menuItemArray[10].menuItemType==0x66)
assert(ffi.string(native[0].menuItemArray,9*80)==before)
old=nil;collectgarbage();collectgarbage()
state.activate();state.activate();assert(modal[0].height==405)
playing=true;state.activate();state.activate();assert(modal[0].height==357)
restart=pointer(native[0].menuItemArray)+5*80
assert(core.readInteger(restart+20)~=1001 and core.readInteger(restart+28)~=1002)
local later=api.ui.Menu:fromPointer(native,5)
local extra=ffi.new('MenuItem[1]',{});extra[0].menuItemType=3
later:insertMenuItem(0,extra[0]);collectgarbage();collectgarbage()
restart=pointer(native[0].menuItemArray)+6*80
playing=false;state.activate()
assert(core.readInteger(restart+20)==1001 and core.readInteger(restart+28)==1002)
assert(core.readInteger(restart+76)==pointer(native))
assert(native[0].menuItemArray[11].menuItemType==0x66)
modal[0].height=modal[0].height+20
state.activate();assert(modal[0].height==425)
playing=true;state.activate();assert(modal[0].height==377)
playing=false;state.activate();assert(modal[0].height==425)
assert(core.readInteger(ui.item+76)==pointer(native))
print('PASS: UI-owned pause insertion, native callbacks, restart restore, relocation, height and lifetime')
