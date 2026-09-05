import subprocess
import unittest

import test_recorder as fixture


class RestartTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check('''
json.encode=function(_,value) request=value; return 'request JSON' end
written={}; spawned=0; preflightOK=true
package.loaded['code/sessions']={ROOT='ucp/replays',
 load=function(id) return {id=id} end,
 preflight=function() assert(preflightOK,'damaged recording') end,
 write=function(path,data) written[path]=data end,
}
package.loaded['code/platform']={
 identity=function() return {executable='C:/game/Crusader.exe',processId=123} end,
 spawnHidden=function(exe,args) spawned=spawned+1; executable=exe; arguments=args end,
}
os.getenv=function(key) if key=='SystemRoot' then return 'C:\\\\Windows' end end
restart=require('code/restart')
''')

    def test_restart_only_queues_hidden_helper_and_preserves_settings(self):
        self.check('''
restart.queue('recording1')
assert(spawned==1 and request.id=='recording1' and request.processId==123)
assert(arguments:find('-WindowStyle Hidden',1,true))
assert(written['ucp/replays/restart-helper.ps1'] and written['ucp/replays/restart-request.json'])
assert(not written['ucp-config.yml'])
assert(not pcall(restart.queue,'recording2') and spawned==1)
''')

    def test_corrupt_session_never_starts_helper(self):
        self.check('''
preflightOK=false
assert(not pcall(restart.queue,'recording1')); assert(spawned==0 and next(written)==nil)
''')

    def test_windows_quoting_matches_standard_library(self):
        quote = self.lua.eval('restart.quote')
        for value in ['C:\\Program Files\\game.exe', 'space and trailing slash\\', 'embedded " quote', 'two\\\\" quotes']:
            with self.subTest(value=value):
                self.assertEqual(quote(value), subprocess.list2cmdline([value]))
        for value in ['bad\nline', 'bad\0path']:
            with self.subTest(value=value):
                ok, _ = self.lua.eval('function(v) return pcall(restart.quote,v) end')(value)
                self.assertFalse(ok)
