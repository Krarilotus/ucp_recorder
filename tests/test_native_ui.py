import unittest
import test_recorder as fixture


class NativeUITests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def test_unavailable_button_uses_native_disabled_style_and_ignores_click(self):
        self.check('''
local functions={}; local nextId=10; local allowed=false; local clicks=0; local rendered
utils.createLuaFunctionWrapper=function(fn) nextId=nextId+1; functions[nextId]=fn; return nextId end
ui.textNative=function(...) rendered={...} end
ui.widthNative=function() return 32 end
ui.buttonNative=function() assert(memory[sites.buttonState.value+16]==0) end
local address=core.allocate(80)
ui:button(address,0,0,140,30,'Play',function() clicks=clicks+1 end,nil,nil,function() return allowed end)
memory[sites.buttonState.value+16]=1
functions[memory[address+20]]({}); assert(clicks==0)
functions[memory[address+28]]({})
assert(rendered[6]==0x7f7f7f and rendered[9]==0 and memory[sites.buttonState.value+16]==1)
allowed=true; functions[memory[address+20]]({}); assert(clicks==1)
''')

    def test_native_font_centering_and_width_fit_use_original_text_parameters(self):
        self.check('''
local text,calls='',{}
core.writeString=function(_,s) text=s end
ui.widthNative=function() return (#text-1)*8 end
ui.textNative=function(...) calls[#calls+1]={...} end
ui:text('A very long replay name',120,24,1,18,true,80)
assert(#text<=11 and text:sub(-4)=='...\\0')
local c=calls[1]
assert(#calls==1 and c[3]==120 and c[4]==24 and c[5]==1)
assert(c[6]==0xCCFAFF and c[7]==18 and c[9]==2)
ui:text('Title',300,20,1,16,false)
c=calls[2]; assert(c[6]==0xC2F0EB and c[7]==16 and c[9]==4)
''')

    def test_player_view_scope_wraps_rendering_but_never_input_or_reset(self):
        self.check('''
local hook; local scoped=false; local seen={}
core.hookCode=function(f) hook=f; return function(_,action) seen[action]=scoped; return 42 end end
memory[0x8000+0x4c]=0x7000; memory[0x8000+20]=123
memory[0x7000]=0x9000; memory[0x9000]=0x66
ui.renderScope=function(run) scoped=true; local result=run(); scoped=false; return result end
ui:trackVisibility({0x8000},function() return true end)
for action=0,3 do assert(hook(0x7000,action)==42) end
assert(not seen[0] and seen[1] and not seen[2] and seen[3])
''')

    def test_optional_ui_resolves_entries_before_recorder_hooks(self):
        self.check('''
local accessed=false
modules={ui={access=function() accessed=true end}}
core.readBytes=function(address,size)
 assert(accessed,'UI callable entries were not resolved before native verification')
 for _,site in pairs(sites) do if site.address==address then return site.bytes end end
 error('unexpected address')
end
assert(NativeUI.verify()==sites)
modules=nil
assert(NativeUI.verify()==sites)
''')

    def test_keyboard_is_consumed_only_in_our_singleplayer_dialogs(self):
        self.check('''
local hook; local forwarded=0; local handled=0; local single=true
core.hookCode=function(callback,address,count,convention,size)
 assert(address==sites.windowProc.address and count==5 and convention==1 and size==8)
 hook=callback
 return function(ecx,window,message,key,data)
   assert(ecx==10 and window==20 and data==30); forwarded=forwarded+1; return 42
 end
end
ui.dialogs[300]=true
ui:installInput(function() return single end,function() handled=handled+1 end)
memory[sites.modalComposition.value+0x2c]=300
for _,message in ipairs({0x100,0x101,0x102}) do assert(hook(10,20,message,65,30)==0) end
assert(handled==3 and forwarded==0)
assert(hook(10,20,0x200,65,30)==42) -- mouse goes to native buttons
assert(hook(10,20,0x104,65,30)==42) -- system/Alt messages remain native
single=false; assert(hook(10,20,0x102,65,30)==42)
single=true; memory[sites.modalComposition.value+0x2c]=5
assert(hook(10,20,0x102,65,30)==42)
assert(handled==3 and forwarded==4)
''')

    def test_multiple_visibility_groups_install_only_one_native_hook(self):
        self.check('''
local installs=0; local hook
core.hookCode=function(callback) installs=installs+1; hook=callback; return function() return 42 end end
memory[0x8000+0x4c]=0x7000; memory[0x8000+20]=123
memory[0x8100+0x4c]=0x7100; memory[0x8100+20]=456
memory[0x7000]=0x9000; memory[0x7100]=0xa000
memory[0x9000]=3; memory[0x9000+20]=123; memory[0x9000+80]=0x66
memory[0xa000]=3; memory[0xa000+20]=456; memory[0xa000+80]=0x66
ui:trackVisibility({0x8000},function() return false end)
ui:trackVisibility({0x8100},function() return true end)
assert(installs==1 and hook(0x7000,0)==42 and hook(0x7100,0)==42)
assert(memory[0x9000]==-2147483645 and memory[0xa000]==3)
''')

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check('''
realNative.profile.name='SHC'
NativeUI=require('code/native-ui')
sites=require('code/ui-sites').SHC
local ranges={}
local allocate=core.allocate
core.allocate=function(size)
 local address=allocate(size); ranges[#ranges+1]={address,address+size}; return address
end
local function checked(address,size)
 if address<0x10000000 then return end
 for _,range in ipairs(ranges) do if address>=range[1] and address+size<=range[2] then return end end
 error('native UI allocation overrun')
end
local writeInteger,writeSmall=core.writeInteger,core.writeSmallInteger
core.writeInteger=function(a,v) checked(a,4); writeInteger(a,v) end
core.writeSmallInteger=function(a,v) checked(a,2); writeSmall(a,v) end
core.writeString=function() end
ui=NativeUI.new(sites,function(reason) error(reason) end)
''')

    def test_modal_items_fit_allocation_and_keep_sentinel(self):
        self.check('''
local menuAddress,arrayAddress
ui.menuConstructor=function(menu,array) menuAddress=menu; arrayAddress=array end
ui.modalConstructor=function(dialog,id,x,y,w,h,style,color,render,menu)
 assert(id==300 and x==-1 and y==-1 and style==512 and menu==menuAddress)
end
local items={}
for i=1,12 do items[i]={x=20,y=i*30,width=200,height=30,label='item',action=function() end} end
ui:modal(items,#items,680,440,function() end)
assert(memory[arrayAddress+12*80]==0x66)
for i=0,11 do assert(memory[arrayAddress+i*80+0x4c]==menuAddress) end
''')

    def test_modal_id_collision_is_avoided(self):
        self.check('''
memory[sites.modalStack.value]=0x1234; memory[0x1234]=300; memory[0x1234+0x24]=0
ui.modalConstructor=function(_,id) assert(id==301) end
assert(ui:modal({},0,680,440,function() end)==301)
''')

    def test_cyclic_modal_list_fails_instead_of_hanging(self):
        self.check('''
memory[sites.modalStack.value]=0x1234; memory[0x1234+0x24]=0x1234
assert(not pcall(function() ui:modal({},0,680,440,function() end) end))
''')

    def test_menu_text_sanitizes_controls_and_bounds_native_buffer(self):
        self.check(r'''
local text
core.writeString=function(_,value) text=value end
ui:text('a\nb\0c'..string.rep('x',200),20,30)
assert(#text==151 and text:sub(1,5)=='a b c' and text:byte(151)==0)
''')

    def test_multiplayer_hides_only_recorder_items_after_array_reallocation(self):
        self.check('''
local hook; local calls=0
core.hookCode=function(callback) hook=callback; return function() calls=calls+1; return 42 end end
local owner,oldItem,array=0x7000,0x8000,0x9000
memory[oldItem+0x4c]=owner; memory[oldItem+20]=123
memory[owner]=array
memory[array]=3; memory[array+20]=123
memory[array+80]=3; memory[array+80+20]=456
memory[array+160]=0x66
local visible=false
ui:trackVisibility({oldItem},function() return visible end)
assert(hook(owner,0)==42)
assert(memory[array]==-2147483645 and memory[array+80]==3 and calls==1)
visible=true; hook(owner,1); assert(memory[array]==3 and memory[array+80]==3)
visible=false; hook(owner+100,0); assert(memory[array]==3)
''')
