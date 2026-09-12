"""Verify the native report-admission branch, without calling simulation or UI stubs."""
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESI, UC_X86_REG_EAX, UC_X86_REG_ESP


def check_report_pause(reader, lua, root, variant):
    site=lua.execute((root/'tests/fixtures/ui-sites.lua').read_text())[variant].reportPause
    engine=lua.execute((root/'tests/fixtures/engine-sites.lua').read_text())[variant]
    emitter=lua.execute((root/'code/scoped-code.lua').read_text())
    start=site.address-25
    original=reader(start,38)
    assert original[:6]==bytes.fromhex('8d46b983f808') # actions 71..79 only
    assert original[25:32]==bytes(site.bytes.values())
    assert original[32:34]==b'\x0f\x85'
    denied=site.address+13+struct.unpack('<i',original[34:38])[0]
    outside=start+12+struct.unpack('<i',original[8:12])[0]
    admitted=site.address+13
    mode=(0x191d768 if variant=='SHC' else 0x23547d8)+0x618
    # Derive the preceding native network-busy field directly from its operand.
    busy=struct.unpack('<I',original[14:18])[0]
    enabled,offline,trampoline=0x4100000,0x4100004,0x4110000
    machine=Uc(UC_ARCH_X86,UC_MODE_32)
    machine.mem_map(0x400000,0x3e00000)
    machine.mem_write(start,original)
    machine.mem_write(trampoline,bytes(emitter.build(site,enabled,mode,None,trampoline,None,offline).values()))
    machine.mem_write(site.address,bytes(emitter.jump(site.address,trampoline,len(site.bytes)).values()))
    reached=[]
    def stop(uc,address,size,user):
        if address in (denied,outside,admitted):
            reached.append(address); uc.emu_stop()
    machine.hook_add(UC_HOOK_CODE,stop)
    def put(address,value): machine.mem_write(address,struct.pack('<I',value))
    cases=0
    for active in (0,1):
      for session_mode,is_offline in ((0,0),(99,0),(2,0),(2,1)):
       for paused in (0,1):
        for action in (70,71,72,77,79,80):
         for network_busy in (0,1):
            put(enabled,active); put(offline,is_offline); put(mode,session_mode)
            put(engine.paused,paused); put(busy,network_busy)
            before=bytes(machine.mem_read(engine.paused,4))
            machine.reg_write(UC_X86_REG_ESI,action)
            machine.reg_write(UC_X86_REG_EAX,0x12345678)
            machine.reg_write(UC_X86_REG_ESP,0x4120000)
            reached.clear(); machine.emu_start(start,0,count=1000)
            replay=active and (session_mode in (0,99) or is_offline)
            expected=outside if action not in range(71,80) else denied if network_busy or (paused and not replay) else admitted
            assert reached==[expected],(variant,active,session_mode,is_offline,paused,action,network_busy,reached)
            assert machine.reg_read(UC_X86_REG_ESI)==action
            assert machine.reg_read(UC_X86_REG_EAX)==(action-71)&0xffffffff
            assert machine.reg_read(UC_X86_REG_ESP)==0x4120000
            assert bytes(machine.mem_read(engine.paused,4))==before
            cases+=1
    print(f'PASS: {variant} {cases} native report-admission cases; only replay reports ignore pause, pause/stack/registers preserved')
