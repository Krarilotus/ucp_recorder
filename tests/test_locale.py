import unittest
import test_recorder as fixture


class LocaleTests(unittest.TestCase):
    setUp=fixture.RecorderTests.setUp
    check=fixture.RecorderTests.check

    def test_launcher_language_precedes_game_language_with_fallback(self):
        self.check('''
local l=require('code/locale')
local environment=nil
os.getenv=function(key) assert(key=='UCP_GUI_LANGUAGE'); return environment end
version={getGameLanguage=function() return 'german' end}
assert(l.language()=='de' and l.text('Play')=='Abspielen')
environment='en'; assert(l.language()=='en' and l.text('Play')=='Play')
environment='de-DE'; assert(l.text('Player %d',4)=='Spieler 4')
environment='xx'; assert(l.language()=='en')
environment=nil; version.getGameLanguage=function() return nil end; assert(l.language()=='en')
version.getGameLanguage=function() error('not initialized') end; assert(l.language()=='en')
assert(l.text('Unknown diagnostic')=='Unknown diagnostic')
''')

    def test_german_native_glyphs_and_format_placeholders(self):
        self.check('''
local l=require('code/locale')
assert(l.native('Zurück')=='Zur'..string.char(252)..'ck')
assert(l.native('ÄÖÜäöüß')==string.char(196,214,220,228,246,252,223))
for key,value in pairs(l.translations.de) do
 local function fields(s) local t={}; for f in s:gmatch('%%[ds]') do t[#t+1]=f end; return table.concat(t) end
 assert(fields(key)==fields(value),key)
end
''')
