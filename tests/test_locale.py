import unittest
import test_recorder as fixture


class LocaleTests(unittest.TestCase):
    check=fixture.RecorderTests.check

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        def encode(text, codepage):
            try:
                if codepage == 1256:
                    text = text.replace('\u06cc', '\u064a')
                return text.encode('utf-8' if codepage == 65001 else f'cp{codepage}')
            except (UnicodeError, LookupError):
                return None
        self.lua.globals().encode_text = encode
        self.check("require('code/text-encoding').encode=encode_text")

    def test_loaded_marker_overrides_executable_language_and_uses_its_codepage(self):
        self.check('''
local l=require('code/locale')
os.getenv=function() error('Launcher language must never be queried') end
data={version={getGameLanguage=function() return 'english' end}}
for _,example in ipairs({{'RUSSIAN',1251,'ru'},{'Hungarian',1250,'hu'},
 {'Turkish',1254,'tr'},{'CHINESE',936,'zh'},{'ch-CN',936,'zh'},{'Farsi',1256,'fa'},
 {'French',1252,'fr'},{'Spanish',1252,'es'},{'Italian',1252,'it'},{'Polish',1250,'pl'}}) do
 l.bind(function() return example[1],example[2] end)
 local language,codepage=l.context()
 assert(language==example[3] and codepage==example[2])
 assert(l.text('Play')==l.translations[language]['Play'])
end
l.bind(function() return 'unknown translation',1252 end); assert(l.language()=='en')
l.bind(function() return 'Russian',0 end); assert(l.language()=='en')
data.version.getGameLanguage=function() return 'fr-FR' end
l.bind(function() error('not loaded') end); assert(l.language()=='fr')
''')

    def test_all_translations_preserve_placeholders_and_encode_for_their_fonts(self):
        self.check('''
local l=require('code/locale')
local pages={de=1252,fr=1252,ru=1251,hu=1250,tr=1254,zh=936,es=1252,fa=1256,it=1252,pl=1250}
local function fields(value)
 local result={}; for field in value:gmatch('%%[ds]') do result[#result+1]=field end
 return table.concat(result)
end
for language,page in pairs(pages) do
 l.bind(function() return language,page end)
 for key in pairs(l.translations.de) do
  local value=l.translations[language][key]
  assert(type(value)=='string' and fields(value)==fields(key),language..': '..key)
  assert(encode_text(value,page),language..': unrepresentable: '..key)
  assert(l.text(key)==value,language..': unexpected fallback: '..key)
 end
end
''')

    def test_unsupported_encoding_falls_back_to_english_without_losing_arguments(self):
        self.check('''
local l=require('code/locale')
l.bind(function() return 'Russian',1252 end)
assert(l.language()=='ru' and l.text('Player %d',7)=='Player 7')
assert(l.native(l.text('Player %d',7))=='Player 7')
assert(l.text('Unknown diagnostic %s','detail')=='Unknown diagnostic detail')
l.bind(function() return 'Russian',1251 end)
assert(l.text('Player %d',7)=='Игрок 7')
''')

    def test_multibyte_clipping_fits_complete_characters_and_handles_tiny_widths(self):
        self.check('''
local l=require('code/locale')
l.bind(function() return 'Chinese',936 end)
local count=0
local function width(bytes) count=count+1; return #bytes*8 end
local text=l.fit(string.rep('回放',100),150,width,80)
assert(#text<=10 and text:sub(-3)=='...' and (#text-3)%2==0)
assert(count<15,'Clipping must not scan one byte at a time')
assert(l.fit('回放',150,width,10)=='')
assert(l.fit('a\\nb\\0c',150)=='a b c')
local utf8=string.rep('回',60)
l.bind(function() return 'Chinese',65001 end)
text=l.fit(utf8,149)
assert(#text<=149 and text:sub(-3)=='...' and (#text-3)%3==0)
''')

    def test_ucp_version_utility_does_not_shadow_game_language(self):
        self.check('''
local l=require('code/locale')
os.getenv=function() return nil end
version={parse=function() error('semantic version utility is unrelated') end}
data={version={getGameLanguage=function() return 'german' end}}
assert(l.language()=='de' and l.text('Auto: on')=='Auto: ein')
version.getGameLanguage=function() return 'english' end
assert(l.language()=='de')
os.getenv=function() return 'en' end
assert(l.language()=='de')
''')

    def test_game_language_ignores_launcher_language(self):
        self.check('''
local l=require('code/locale')
local environment=nil
os.getenv=function(key) assert(key=='UCP_GUI_LANGUAGE'); return environment end
version={getGameLanguage=function() return 'german' end}
assert(l.language()=='de' and l.text('Play')=='Abspielen')
environment='en'; assert(l.language()=='de' and l.text('Play')=='Abspielen')
environment='de-DE'; assert(l.text('Player %d',4)=='Spieler 4')
environment='xx'; assert(l.language()=='de')
version.getGameLanguage=function() return 'english' end
environment='de'; assert(l.language()=='en' and l.text('Play')=='Play')
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
