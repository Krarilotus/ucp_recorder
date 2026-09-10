import unittest
import test_recorder as fixture


class NativeUITests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def test_progress_uses_native_fill_and_keeps_inclusive_bounds_inside_its_track(self):
        self.check('''
local calls={}
ui.fillNative=function(...) calls[#calls+1]={...} end
ui.border=function(_,x,y,w,h) assert(x==20 and y==30 and w==95 and h==9) end
memory[sites.loadingColor.value]=-1
for _,fraction in ipairs({-1,0,0.5,1,2}) do
 calls={}; ui:progressBar(20,30,96,10,fraction)
 local track=calls[1]
 assert(track[1]==sites.pencil.value and track[2]==20 and track[3]==30)
 assert(track[4]==115 and track[5]==39 and track[6]==0)
 if fraction<=0 then assert(#calls==1)
 else
  local fill=calls[2]; local pixels=math.floor(92*math.min(fraction,1))
  assert(fill[1]==sites.pencil.value and fill[2]==22 and fill[3]==32)
  assert(fill[4]==21+pixels and fill[5]==37 and fill[6]==65535)
 end
end
''')

    def test_loaded_text_manager_marker_and_codepage_share_the_native_font_path(self):
        self.check('''
local calls=0
memory[sites.textManager.value+0x10]=1251
modules={ui={}}
modules.ui.access=function() return {game={Rendering={textManager=sites.textManager.value,
 getTextStringInGroupAtOffset=function(manager,group,entry)
  assert(manager==sites.textManager.value and group==6 and entry==0); calls=calls+1; return 5000
 end}}} end
modules.cffi={cffi=function() return {cast=function(_,value) return value end,tonumber=tonumber,
 string=function(address) assert(address==5000); return 'RUSSIAN' end} end}
data={version={getGameLanguage=function() return 'english' end}}
local l=require('code/locale'); local language,codepage=l.context()
assert(language=='ru' and codepage==1251 and calls==1)
require('code/text-encoding').encode=function(text,page) assert(page==1251); return 'encoded' end
local drawn,measured
ui.widthNative=function(_,_,font) measured=font; return 30 end
ui.textNative=function(...) drawn={...} end
ui:text(l.text('Play'),50,60,1,18,false,100)
assert(drawn[7]==18 and measured==18 and drawn[5]==1)
ui:header(l.text('Replays'),10,20,400)
assert(drawn[7]==15 and measured==15 and drawn[5]==1)
''')

    def test_gameplay_overlay_input_uses_root_view_when_native_dispatches_a_subtab(self):
        self.check('''
local visible=true
ui.overlays={[7000]={visible=function() return visible end,items={{x=10,y=160,width=72,height=72}}}}
ui.inputOverlays={[14]=7000,[16]=7000}
memory[0x1fe7d1c]=14; memory[ui:windowAddress()+0x18]=1920
assert(not ui:updateOverlay(7100,1)) -- unrelated subtab rendering stays native
local overlay=ui:updateOverlay(7100,0)
assert(overlay==ui.overlays[7000] and memory[overlay.array+12]==72)
memory[0x1fe7d1c]=16; assert(ui:updateOverlay(7200,0)==overlay)
visible=false; assert(not ui:updateOverlay(7200,0)) -- modal/ordinary play excluded
visible=true; memory[0x1fe7d1c]=58; assert(not ui:updateOverlay(7200,0))
''')

    def test_responsive_overlay_positions_share_draw_and_native_input_bounds(self):
        self.check('''
ui.overlays={[7000]={visible=function() return true end,items={{x=10,y=160,width=72,height=72,
 position=function(width,height) return width-90,height-252 end}}}}
memory[ui:windowAddress()+0x18]=1920; memory[ui:windowAddress()+0x1c]=1080
local overlay=ui:updateOverlay(7000,1)
assert(memory[overlay.array+4]==1830 and memory[overlay.array+8]==828)
memory[ui:windowAddress()+0x18]=800; memory[ui:windowAddress()+0x1c]=600
ui:updateOverlay(7000,0)
assert(memory[overlay.array+4]==710 and memory[overlay.array+8]==348)
''')

    def test_overlay_layout_writes_only_changes_and_skips_inactive_sessions(self):
        self.check('''
local shown=false; local rowVisible=true; local writes=0
local write=core.writeInteger
core.writeInteger=function(a,v) writes=writes+1; write(a,v) end
local instruction=sites.buildingAndStatus.bytes
local resolution=instruction[3]+instruction[4]*256+instruction[5]*65536+instruction[6]*16777216
memory[resolution-0x44]=1920; memory[resolution-0x3c]=560; memory[resolution-0x38]=240
ui.overlays={[7000]={visible=function() return shown end,items={
 {x=-410,y=12,width=398,height=58,visible=function() return rowVisible end},
 {x=450,y=546,width=160,height=30,frontEnd=true}}}}
assert(not ui:updateOverlay(7000) and writes==0)
shown=true; local overlay=ui:updateOverlay(7000)
assert(memory[overlay.array+4]==1510 and memory[overlay.array+8]==12)
assert(memory[overlay.array+84]==1010 and memory[overlay.array+88]==786)
writes=0; ui:updateOverlay(7000); assert(writes==0)
rowVisible=false; ui:updateOverlay(7000); assert(writes==1 and memory[overlay.array]==-2147483645)
writes=0; memory[resolution-0x44]=1280; ui:updateOverlay(7000)
assert(writes==1 and memory[overlay.array+4]==870)
shown=false; writes=0; assert(not ui:updateOverlay(7000) and writes==0)
shown=true; rowVisible=true; ui:updateOverlay(7000)
assert(writes==1 and memory[overlay.array]==3)
''')

    def test_overlay_uses_its_owner_surface_and_restores_target_even_on_failure(self):
        self.check('''
local hook; local target={[0]=2}; local fail=false; local frontEnd=false
modules={ui={access=function() return {game={Rendering={pDrawBufferChoiceValue=target}}} end}}
ui.updateOverlay=function(_,parent) return {menu=0x6000,items={{frontEnd=frontEnd}}} end
local text=sites.textManager.value
memory[text]=31; memory[text+8]=560; memory[text+12]=1360; memory[text+28]=2
memory[ui:windowAddress()+0x18]=1920
memory[sites.mapViewport.value]=181; memory[sites.mapViewport.value+4]=24
memory[sites.buttonState.value]=10; memory[sites.buttonState.value+4]=110
core.hookCode=function(callback)
 hook=callback
 return function(parent,action)
  if parent==0x6000 then
   assert(action==1)
   ui:renderOverlayItem({frontEnd=frontEnd,render=function(x,y)
    assert(target[0]==(frontEnd and 0 or 1))
    local origin=frontEnd and 0 or 181
    assert(x==10+origin and y==110+(frontEnd and 0 or 24))
    assert(memory[text+28]==target[0] and memory[text+8]==origin and memory[text+12]==1920+origin)
    memory[text]=123 -- native rendering advances its text cursor
    if fail then error('draw failed') end
   end})
  end
 end
end
memory[0x8000+0x4c]=0x7000; memory[0x8000+20]=123
memory[0x7000]=0x9000; memory[0x9000]=0x66
ui:trackVisibility({0x8000},function() return true end)
hook(0x7000,3); assert(target[0]==2)
assert(memory[text]==31 and memory[text+8]==560 and memory[text+12]==1360 and memory[text+28]==2)
frontEnd=true; hook(0x7000,1); assert(target[0]==2)
fail=true; assert(not pcall(hook,0x7000,1) and target[0]==2)
assert(memory[text]==31 and memory[text+8]==560 and memory[text+12]==1360 and memory[text+28]==2)
assert(ui.overlayOriginX==nil and ui.overlayOriginY==nil)
''')

    def test_overlay_tracks_native_viewport_without_moving_input_rectangles(self):
        self.check('''
local target={[0]=0}
modules={ui={access=function() return {game={Rendering={pDrawBufferChoiceValue=target}}} end}}
local item={x=10,y=110,width=36,height=36}
ui.overlays={[7000]={visible=function() return true end,items={item}}}
for _,case in ipairs({{800,0,0},{1920,181,24},{1280,800,400}}) do
 memory[ui:windowAddress()+0x18]=case[1]
 memory[sites.mapViewport.value]=case[2]; memory[sites.mapViewport.value+4]=case[3]
 local overlay=ui:updateOverlay(7000)
 memory[sites.buttonState.value]=memory[overlay.array+4]
 memory[sites.buttonState.value+4]=memory[overlay.array+8]
 item.render=function(x,y) assert(x==10+case[2] and y==110+case[3]) end
 ui:renderOverlay(overlay,function() ui:renderOverlayItem(item) end)
 assert(memory[overlay.array+4]==10 and memory[overlay.array+8]==110)
 assert(target[0]==0 and ui.overlayOriginX==nil)
end
''')

    def test_hud_text_is_opaque_with_a_dark_shadow(self):
        self.check('''
local calls={}; local measured=0; ui.widthNative=function() measured=measured+1; return 80 end
ui.textNative=function(...) calls[#calls+1]={...} end
ui:hudText('Replay: 20 / 100 ticks',788,12,-1,398)
assert(#calls==2 and measured==1)
assert(calls[1][3]==789 and calls[1][4]==13 and calls[1][6]==0 and calls[1][9]==0)
assert(calls[2][3]==788 and calls[2][4]==12 and calls[2][6]==0xCCF4FF and calls[2][9]==0)
assert(calls[1][5]==-1 and calls[2][5]==-1)
''')

    def test_restart_replacement_preserves_initialized_callbacks_and_never_overwrites_recording_row(self):
        self.check('''
local hooks,arrays={},{}; local playing=false; local nextFunction=700
utils.createLuaFunctionWrapper=function() nextFunction=nextFunction+1; return nextFunction end
core.hookCode=function(f,address) hooks[address]=f; return function() return 42 end end
core.copyMemory=function(to,from,size)
 for i=0,size-4,4 do memory[to+i]=memory[from+i] or 0 end
end
core.writeCode=function(_,code) arrays[#arrays+1]=code[1].variables.array end
ui:extendPause('Save',function() end,function() return not playing end,function() return playing end)
local row=arrays[1]+5*80
-- Native construction happens AFTER extendPause. It resolves the callbacks
-- inherited from the interaction group, which are zero in the source template.
memory[row+20]=1001; memory[row+28]=1002; memory[row+76]=0x9000
memory[arrays[1]+9*80+76]=0x9000
local activate=hooks[sites.activateModal.address]
activate(0,5,1); assert(memory[row+20]==1001 and memory[row+28]==1002)
playing=true; activate(0,5,1)
assert(memory[row+20]~=0 and memory[row+28]~=0 and memory[row+28]~=1002)
activate(0,5,1) -- reopening must not replace the saved original with our row
playing=false; activate(0,5,1)
assert(memory[row+20]==1001 and memory[row+28]==1002 and memory[row+76]==0x9000)
''')

    def test_summary_and_book_renderers_share_scoped_view_and_preserve_return_value(self):
        self.check('''
local hooks={}; local scoped=false; local calls={}
core.hookCode=function(callback,address,count,convention,size)
 assert(count==0 and convention==0)
 hooks[address]=callback
 return function() assert(scoped); calls[#calls+1]=address; return address end
end
ui.renderScope=function(run) scoped=true; local result=run(); scoped=false; return result end
ui:installViewRender()
for _,name in ipairs({'playerSummary','buildingAndStatus'}) do
 local address=sites[name].address
 assert(hooks[address]()==address and not scoped)
end
assert(#calls==2 and not hooks[sites.handleMenu.address])
''')

    def test_header_uses_original_banner_abi_and_native_title_font(self):
        self.check('''
local banner,text
ui.headerNative=function(...) banner={...} end
ui.widthNative=function() return 80 end
ui.textNative=function(...) text={...} end
ui:header('Replay controls',40,50,600)
assert(#banner==5 and banner[1]==sites.pencil.value and banner[2]==40 and banner[3]==50)
assert(banner[4]==600 and banner[5]==0)
assert(text[3]==340 and text[4]==72 and text[5]==1 and text[7]==15 and text[9]==0)
''')

    def test_titled_modal_offsets_controls_and_content_below_the_native_banner(self):
        self.check('''
local callbacks={}; local nextCallback=1; local callback
utils.createLuaFunctionWrapper=function(fn)
 local id=nextCallback; nextCallback=id+1; callbacks[id]=fn; return id
end
local buttonY,contentY,headerY
ui.button=function(_,_,x,y) buttonY=y end
ui.menuConstructor=function() end
ui.header=function(_,title,x,y,width) assert(title=='Replays' and width==600); headerY=y end
ui.modalConstructor=function(_,id,x,y,w,h,style,color,draw,menu)
 assert(w==600 and h==272); callback=callbacks[draw]
end
ui:modal({{x=24,y=72,width=552,height=30}},1,600,240,
 function(x,y) contentY=y end,function() return 'Replays' end)
memory[0x9004]=10; memory[0x9008]=20; callback({ESP=0x9000})
assert(headerY==20 and contentY==52 and buttonY==104)
''')

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

    def test_native_overlay_button_uses_viewport_without_moving_its_hitbox(self):
        self.check('''
local functions={}; local id=10; local state=sites.buttonState.value
utils.createLuaFunctionWrapper=function(fn) id=id+1; functions[id]=fn; return id end
local address=core.allocate(80); local textX,textY
ui.text=function(_,_,x,y) textX,textY=x,y end
ui:button(address,100,76,36,28,'+',function() end)
for _,origin in ipairs({{0,0},{181,24},{450,120}}) do
 ui.overlayOriginX,ui.overlayOriginY=origin[1],origin[2]
 memory[state]=100; memory[state+4]=76
 ui.buttonNative=function()
  assert(memory[state]==100+origin[1] and memory[state+4]==76+origin[2])
 end
 functions[memory[address+28]]({})
 assert(textX==118+origin[1] and textY==83+origin[2])
 assert(memory[state]==100 and memory[state+4]==76)
 assert(memory[address+4]==100 and memory[address+8]==76)
end
ui.buttonNative=function() error('draw failure') end
local ok,reason=pcall(functions[memory[address+28]],{})
assert(not ok and tostring(reason):find('draw failure',1,true))
assert(memory[state]==100 and memory[state+4]==76)
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
assert(not pcall(NativeUI.verify))
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

    def test_speed_buttons_reuse_native_key_dispatch_without_reentering_overlay(self):
        self.check('''
local hook,calls,filtered=nil,{},0
core.hookCode=function(callback)
 hook=callback
 return function(ecx,window,message,key,data)
  calls[#calls+1]={ecx,window,message,key,data}
 end
end
ui.onNativeKey=function() filtered=filtered+1; return true end
ui:installInput(function() return true end,function() end)
assert(not pcall(ui.nativeSpeedKey,1))
hook(0,123,0x200,0,0)
ui.nativeSpeedKey(1); ui.nativeSpeedKey(-1)
assert(filtered==1 and #calls==2)
assert(calls[1][2]==123 and calls[1][3]==0x100 and calls[1][4]==107 and calls[1][5]==0)
assert(calls[2][4]==109)
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
