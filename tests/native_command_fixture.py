"""Independent reference expectations, never a production binding fallback."""
def native_command_fixture(variant):
    extreme=variant=='Extreme'
    base=0x23547d8 if extreme else 0x191d768
    return dict(version=1,handler=base,ring=base+0x3c67c,stride=1272,capacity=200,
                writeIndex=base+(0x166370 if extreme else 0x109ee0),currentCommand=base+0x2d824,
                localPlayer=0x24baadc if extreme else 0x1a275dc,
                tick=0x2a7b2a8 if extreme else 0x1fe7da8,receivedParameters=base+0xcdc)
