"""Exercise real history entry/return callbacks with strict native address mapping."""
import unittest
import test_battle_statistics as fixture


class HistoryNativeTests(unittest.TestCase):
    check = fixture.BattleStatisticsTests.check

    def setUp(self):
        fixture.BattleStatisticsTests.setUp(self)
        self.check(r'''
realNative.profile={name='SHC',addresses={[0x191d768]=0x191d768,[0x1fe7d1c]=0x1fe7d1c}}
local store=require('code/sessions'); store.list=function() return {} end
sites=require('code/history-sites').SHC
battle:begin(); nativeRecord=core.readString(battle.buffer,stats.SIZE)
core.writeString(sites.records,nativeRecord); core.writeInteger(sites.storedCount,1)
core.writeInteger(0x191dd80,99)
core.writeInteger(sites.prepare.address+0x2b,0xeb9b58)
core.writeInteger(0x1fe7d1c,58)
core.writeInteger(16000,17000); core.writeInteger(17000,0x66)
core.deallocate=function() end; core.writeCodeInteger=core.writeInteger
modules={ui={access=function() return {manager={lookupMenu=function() return 16000 end}} end},
 cffi={cffi=function() return {tonumber=tonumber,cast=function(_,p) return p end} end}}
local callbacks={}; hooked=callbacks
core.hookCode=function(callback,address)
 callbacks[address]=callback
 if address==sites.prepare.address then return function()
  core.writeInteger(sites.count,core.readInteger(sites.storedCount))
  core.writeInteger(0xeb9b58,core.readInteger(0x191dd80))
 end end
 return function(action)
  if action==11 then core.writeInteger(0x191dd80,core.readInteger(0xeb9b58)); returned=true
  elseif action<8 then core.writeInteger(0x191dd80,123); core.writeInteger(0x1fe7d1c,29) end
 end
end
ui={activeDialog=function() return -1 end,
 attachOverlay=function(_,ids,items) assert(#ids==1 and ids[1]==58); controls=items end}
recorder={mode='none'}
history=require('code/history-native').new(ui,recorder,{},function() renamed=true end)
''')

    def test_entry_preserves_native_results_sets_date_and_returns_to_singleplayer(self):
        self.check('''
hooked[sites.prepare.address]()
assert(core.readInteger(sites.count)==1 and core.readInteger(sites.sort)==4)
assert(core.readString(sites.records,stats.SIZE)==nativeRecord)
assert(core.readString(history.records,stats.SIZE)==nativeRecord)
hooked[sites.action.address](0)
assert(core.readInteger(0x1fe7d1c)==58 and not history.detail)
assert(not controls[1].visible() and not controls[2].visible())
ui.onNativeKey(0x100,113); assert(not renamed)
hooked[sites.action.address](0)
assert(core.readInteger(0x1fe7d1c)==29 and history.detail)
hooked[sites.prepare.address]() -- return from native statistics
assert(core.readInteger(0xeb9b58)==99)
hooked[sites.action.address](11)
assert(returned and core.readInteger(0x191dd80)==99)
''')

    def test_footer_preserves_native_rows_count_scrollbar_and_mirrors_back_hand(self):
        self.check('''
local rename,hand,progress=controls[1],controls[2],controls[3]
local function overlaps(a,b)
 return a.x<b.x+b.width and b.x<a.x+a.width and a.y<b.y+b.height and b.y<a.y+a.height
end
-- Native layout and decoded opaque footprint of GM150 picture69.
local back={x=53,y=526,width=97,height=47}
local row8={x=24,y=461,width=730,height=47}
local scroll={x=755,y=85,width=20,height=494}
local count={x=175,y=550,width=240,height=22}
assert(hand.x==800-back.x-back.width and hand.y==back.y)
assert(hand.width==back.width and hand.height==back.height)
for _,item in ipairs({rename,hand,progress}) do
 for _,nativeItem in ipairs({row8,scroll,count}) do assert(not overlaps(item,nativeItem)) end
end
assert(not overlaps(rename,hand) and not overlaps(progress,hand) and not overlaps(rename,progress))
ui.text=function() error('The hand must not draw a subtitle') end
ui.sprite=function(_,gm,picture,x,y)
 assert(gm==150 and picture==71 and x+46==hand.x and y+67==hand.y)
end
hand.render(hand.x,hand.y)
history.model.selected={manifest={status='complete'}}
assert(hand.visible() and rename.visible())
history.browser.preparation={}; assert(not hand.visible() and not rename.visible())
ui.onNativeKey(0x100,113); assert(not renamed)
history.browser.preparation=nil; history.model.selected.manifest.status='recording'
assert(not hand.visible() and rename.visible())
''')

    def test_sort_icon_updates_heading_and_keeps_native_record_unchanged(self):
        self.check('''
hooked[sites.prepare.address]()
hooked[sites.action.address](21)
assert(core.readInteger(sites.sort)==2 and not history.model.descending)
hooked[sites.action.address](23)
assert(core.readInteger(sites.sort)==4 and history.model.descending)
hooked[sites.action.address](23); assert(not history.model.descending)
assert(core.readString(sites.records,stats.SIZE)==nativeRecord)
''')

    def test_preparation_stays_in_history_and_back_cancels_without_starting(self):
        self.check('''
hooked[sites.prepare.address]()
history.model.selected={id='replay',manifest={status='complete'}}
local browser=history.browser
browser.refresh=function(_,id) assert(id=='replay') end
browser.play=function(self,deferred) assert(deferred); self.preparation=true end
browser.cancelPreparation=function(self) self.cancelled=true end
browser.advancePreparation=function(self,beforeStart)
 self.preparation=nil
 if self.cancelled then return false end
 assert(core.readInteger(0x1fe7d1c)==58 and not returned)
 beforeStart(); assert(returned); return true
end
ui.close=function() closed=true end
history:play(); assert(browser.preparation and not returned)
hooked[sites.action.address](11); assert(browser.cancelled and returned)
history:advance(); assert(not closed and not browser.preparation)
returned=nil; browser.cancelled=nil; history:play(); history:advance()
assert(closed and returned)
''')
