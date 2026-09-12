from pathlib import Path
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


def runtime():
    lua = LuaRuntime()
    lua.globals().root = ROOT.as_posix()
    lua.execute('''
      package.path=root..'/?.lua;'..package.path
      version='1.1.0'
      package.loaded['code/automarket-replay']={version=function()return version end}
      local contract={format='state-7',fingerprint=string.rep('a',64)}
      captures,digests=0,0
      owner={requiredStateVersion=function()return 1 end,
        requiredStateContracts=function()return {aic=contract} end,
        captureRequiredSections=function()
          captures=captures+1;return {['aic/state.bin']='state',['framework/required-state.yml']='manifest'}
        end,
        requiredStateIntegrity=function()
          digests=digests+1
          return {aic={format=contract.format,fingerprint=contract.fingerprint,digest=digest or 'state-1'}}
        end}
      modules={['map-extensions']=owner}
      required=require('code/required-state')
    ''')
    return lua


def test_capture_uses_owner_and_preserves_existing_entries():
    runtime().execute('''
      local entries={['automarket/data.bin']='market'}
      assert(required.capture(entries) and captures==1 and digests==0)
      assert(entries['aic/state.bin']=='state' and entries['automarket/data.bin']=='market')
      assert(not pcall(required.capture,entries))
      version='1.0.0'
      assert(not required.capture({}) and required.integrity()==nil)
      required.validate(nil)
    ''')


def test_preflight_contract_checks_do_not_read_simulation_state():
    runtime().execute('''
      local expected={aic={format='state-7',fingerprint=string.rep('a',64),digest='state-1'}}
      required.validate(expected);assert(digests==0)
      required.check(expected);assert(digests==1)
      digest='state-2';assert(not pcall(required.check,expected))
      assert(not pcall(required.validate,nil))
      expected.aic.format='old';assert(not pcall(required.validate,expected))
      expected.aic.format='state-7';expected.aic.fingerprint=string.rep('b',64)
      assert(not pcall(required.validate,expected))
      assert(not pcall(required.validate,{}))
    ''')
