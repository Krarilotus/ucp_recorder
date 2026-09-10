import unittest
import test_recorder as fixture


class PlaybackInfoTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check("require('code/platform').milliseconds=function() return clock or 0 end")

    def test_progress_throttles_presentation_but_refreshes_completion_and_new_sessions(self):
        self.check('''
local tick,reads=1,0
local r={status='playing',manifest={startTick=1,lastTick=101},
 engine={tick=function() reads=reads+1; return tick end}}
local hud=require('code/replay-hud').new(r,{})
local label,fraction=hud:progress(); assert(fraction==0 and reads==1)
clock=249; tick=51; label,fraction=hud:progress(); assert(fraction==0 and reads==1)
clock=250; label,fraction=hud:progress(); assert(fraction==0.5 and reads==2)
tick=102; r.status='finished'; label,fraction=hud:progress()
assert(fraction==1 and label=='Replay: 100 / 100 ticks' and reads==3)
r.manifest={startTick=51,lastTick=51}; tick=51
label,fraction=hud:progress(); assert(fraction==1)
r.status='playing'; label,fraction=hud:progress(); assert(fraction==0)
clock=4294967200; hud:progress(); local before=reads
clock=154; hud:progress(); assert(reads==before+1)
''')

    def test_native_portraits_do_not_overlap_or_enter_the_bottom_controls(self):
        self.check('''
local hud=require('code/replay-hud')
for _,height in ipairs({600,720,768,1080,1440}) do
 local bounds={}
 for i=1,8 do
  local x,y=hud.portraitPosition(i,height)
  assert(x>=10 and x+72<=800 and y>=160 and y+72<=height-180)
  for _,other in ipairs(bounds) do
   assert(x>=other[1]+80 or other[1]>=x+80 or y>=other[2]+80 or other[2]>=y+80)
  end
  bounds[#bounds+1]={x,y}
 end
end
''')

    def test_summary_retains_actual_versions_and_omits_transitive_leaf_modules(self):
        self.check('''
local function extension(name,version,kind,deps)
 return {name=name,version=version,type=function() return kind end,definition={dependencies=deps or {}}}
end
local all={extension('Private-Test','0.1.22','PluginLoader',{Ascension='^1.0.0'}),
 extension('Ascension','1.0.11','PluginLoader',{AI='^1.0.0',automarket='^1.0.0'}),
 extension('AI','1.0.0','PluginLoader'),extension('automarket','1.1.0','ModuleLoader'),
 extension('recorder','0.46.0','ModuleLoader')}
local loaded=0; local definition=all[2].definition; all[2].definition=nil
all[2].loadDefinition=function(self) loaded=loaded+1; self.definition=definition end
local info=require('code/playback-info').capture(all,'major: 3\\nminor: 0\\npatch: 7\\n')
assert(loaded==1)
assert(info.framework=='3.0.7' and info.count==5)
assert(info.packs.Ascension=='1.0.11' and info.packs['Private-Test']=='0.1.22')
assert(info.packs.recorder=='0.46.0' and not info.packs.AI and not info.packs.automarket)
assert(all[2].definition.dependencies.automarket=='^1.0.0' and all[4].version=='1.1.0')
local lines=require('code/playback-info').lines({variant='Extreme'},info)
assert(lines[1]=='Extreme 1.41' and lines[#lines]=='5 exact extension versions verified')
''')

    def test_f3_repeat_toggles_once_and_never_changes_simulation_controls(self):
        self.check('''
local available=true; local recorder={}
local hud=require('code/replay-hud').new(recorder,{available=function() return available end})
assert(hud:key(0x100,114) and hud.details)
assert(hud:key(0x100,114) and hud.details)
assert(hud:key(0x101,114)); hud:key(0x100,114); assert(not hud.details)
hud:key(0x101,114); available=false; assert(not hud:key(0x100,114) and not hud.details)
assert(next(recorder)==nil)
''')

    def test_hud_has_visible_player_choices_and_native_right_aligned_progress(self):
        self.check('''
local available=true; local chosen; local controls; local visible; local texts={}
local recorder={status='finished',manifest={startTick=1,lastTick=101,variant='SHC'},
 engine={tick=function() return 101 end},playbackInfo={framework='3.0.7',packs={},count=1}}
local view={available=function() return available end,players=function() return {1,3} end,
 player=function() return chosen or 1 end,select=function(_,slot) chosen=slot end}
local hud=require('code/replay-hud').new(recorder,view)
local ui={activeDialog=function() return -1 end,attachOverlay=function(_,ids,items,predicate,screenInput)
 assert(ids[1]==14 and ids[2]==16 and screenInput); controls=items; visible=predicate end,
 hudText=function(_,label,x,y,alignment) texts[#texts+1]={label,x,y,alignment} end,
 avatarNative=function(slot,x,y) assert(slot==3 and x==10 and y==152) end,
 border=function() end,progressBar=function(_,x,y,width,height,fraction)
  assert(x==390 and y==16 and width==96 and height==10 and fraction==1)
 end}
hud:install(ui); assert(visible())
assert(controls[1].width==72 and controls[1].height==72)
assert(controls[1].visible() and controls[2].visible() and not controls[3].visible())
controls[2].action(); assert(chosen==3); controls[2].render(10,152)
for _,item in ipairs(controls) do assert(not item.frontEnd) end
controls[9].render(390,12)
assert(texts[1][1]=='Replay: 100 / 100 ticks')
for _,text in ipairs(texts) do assert(text[4]==-1 and text[2]==788) end
assert(not controls[10].visible()); hud:key(0x100,114); assert(controls[10].visible())
controls[10].render(54,12); assert(texts[4][1]=='SHC 1.41')
available=false; assert(not visible())
''')
