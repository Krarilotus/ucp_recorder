"""Do not advertise working capture with known unsaved extension state."""
import unittest
import test_recorder as fixture


class SimulationCompatibilityTests(unittest.TestCase):
    check=fixture.RecorderTests.check
    setUp=fixture.RecorderTests.setUp

    def test_no_ucp2_dependency_when_it_is_not_active(self):
        self.check('''
allActiveExtensions={{name='recorder',version='0.45.0'}}; modules={}
require('code/simulation-compatibility').verify()
''')

    def test_legacy_state_loss_is_rejected_with_update_instructions(self):
        self.check('''
allActiveExtensions={{name='ucp2-legacy',version='2.15.1'}}
for _,loaded in ipairs({false,true}) do
 modules=loaded and {['ucp2-legacy']={}} or {}
 local ok,reason=pcall(require('code/simulation-compatibility').verify)
 assert(not ok and reason:find('2.15.2',1,true) and reason:find('map-extensions',1,true)
   and reason:find('record a new replay',1,true))
end
''')

    def test_checks_registered_capability_instead_of_guessing_from_version(self):
        self.check('''
allActiveExtensions={{name='ucp2-legacy',version='2.15.2'}}
modules={['ucp2-legacy']={}}
assert(not pcall(require('code/simulation-compatibility').verify))
modules['ucp2-legacy'].simulationStateFormat=1
assert(not pcall(require('code/simulation-compatibility').verify))
modules['ucp2-legacy'].serializeSimulationState=function() end
require('code/simulation-compatibility').verify()
modules['ucp2-legacy'].simulationStateFormat=2
assert(not pcall(require('code/simulation-compatibility').verify))
''')
