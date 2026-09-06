import unittest
import test_recorder as fixture


class NameEditorTests(unittest.TestCase):
    setUp = fixture.RecorderTests.setUp
    check = fixture.RecorderTests.check

    def test_typing_replaces_initial_selection_and_supports_cursor_editing(self):
        self.check('''
local e=require('code/name-editor').new('old ID')
for c in ('Stream'):gmatch('.') do e:input(0x102,c:byte()) end
assert(e.value=='Stream')
e:input(0x100,36); e:input(0x102,65); assert(e.value=='AStream')
e:input(0x100,39); e:input(0x100,46); assert(e.value=='ASream')
e:input(0x102,8); assert(e.value=='Aream')
e:input(0x100,35); e:input(0x102,33); assert(e.value=='Aream!')
assert(e:input(0x102,13)=='save' and e:input(0x102,27)=='cancel')
''')

    def test_name_length_controls_selection_and_repeat_keys_are_bounded(self):
        self.check('''
local e=require('code/name-editor').new('old')
e:input(0x100,46); assert(e.value=='' and e.cursor==0)
for _=1,100 do e:input(0x102,87) end
assert(#e.value==40 and e.cursor==40)
e:input(0x102,0); e:input(0x102,200); assert(#e.value==40)
for _=1,100 do e:input(0x100,37) end
e:input(0x102,8); assert(#e.value==40 and e.cursor==0)
e.selected=true; e:input(0x102,8); assert(e.value=='' and e.cursor==0)
''')
