"""Deferred snapshots keep the capture boundary, lifetime and publication separate."""
import unittest
import test_snapshot_store as fixture


class SnapshotJobTests(unittest.TestCase):
    setUp=fixture.SnapshotStoreTests.setUp

    def configure(self):
        self.lua.execute('''
milliseconds=0; ready=false; released=0; cancelled=0; published=0; frozen=0
require('code/platform').milliseconds=function() return milliseconds end
package.loaded['code/world-capture']={freeze=function(actual)
 assert(actual==engine); frozen=frozen+1
 return {ready=function() return ready end,cancel=function() cancelled=cancelled+1 end,
  close=function() assert(ready); released=released+1 end,
  write=function(_,path)
   published=published+1
   local data=string.rep('w',2000); require('code/sessions').write(path,data)
   return {bytes=#data,sha256=hash_string(data)}
  end}
end}
jobs=require('code/snapshot-jobs')
function start() return jobs.start(engine,path,12000,4,r:bookmark(),function(p,e) point=p; failure=e end) end
''')

    def test_completion_uses_frozen_boundary_and_does_not_block_or_resample_world(self):
        self.configure()
        self.lua.execute('''
local original=random
local job=assert(start()); assert(not point and published==0)
jobs.poll(); assert(not point and released==0)
local second,reason=start(); assert(not second and reason=='busy' and frozen==1)
tick=999; random=string.rep('z',0x9c50); resources=string.rep('s',800)
ready=true; milliseconds=100; jobs.poll()
assert(point and point.tick==100 and point.rngHash==hash_string(original))
assert(published==1 and released==1 and not failure)
local actual=snapshot.prepare(manifest,point,path)
assert(actual.rng==original)
''')

    def test_cancelled_job_keeps_memory_until_thread_exits_and_never_publishes(self):
        self.configure()
        self.lua.execute('''
local job=assert(start()); job:cancel(); jobs.poll()
assert(cancelled==1 and released==0 and published==0)
local second,reason=start(); assert(not second and reason=='busy')
ready=true; milliseconds=100; jobs.poll()
assert(released==1 and published==0 and not point)
assert(start()); ready=true; milliseconds=200; jobs.poll()
assert(published==1 and point)
''')

    def test_publication_failure_releases_worker_and_reports_optional_failure(self):
        self.configure()
        self.lua.execute('''
require('code/platform').replace=function() error('disk full') end
assert(start()); ready=true; jobs.poll()
assert(not point and failure:find('disk full',1,true) and released==1)
assert(not io.open(path..'.sav','rb') and not io.open(path..'.sav.tmp','rb'))
''')

    def test_freeze_mutation_is_fatal_but_worker_memory_waits_for_completion(self):
        self.configure()
        self.lua.execute('''
local freeze=require('code/world-capture').freeze
require('code/world-capture').freeze=function(engine)
 local reader=freeze(engine); tick=tick+1; return reader
end
local ok,reason=pcall(start)
assert(not ok and reason:find('changed simulation state',1,true))
assert(cancelled==1 and released==0 and published==0)
ready=true; jobs.poll(); assert(released==1 and published==0)
''')
