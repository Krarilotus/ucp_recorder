"""Private reference-image expectations; Map Extensions owns runtime discovery."""


def native_save_fixture(variant):
    values={'SHC':(0xf2b3d0,0xb92a58,0x474a20,0x474480),
            'Extreme':(0xf2b850,0xb92be8,0x474c50,0x4746b0)}[variant]
    return dict(version=1,sectionCount=122,descriptorSize=16,readContext=1,
                resources=0x11bf130 if variant=='SHC' else 0x1293c20,
                resourceFileName=0x46c300 if variant=='SHC' else 0x46c520,
                resourceFileNameBytes=bytes.fromhex('8B 81 C4 0B 00 00 69 C0 E9 03 00 00 8D 84 08 E0 AE 07 00 C3'),
                **dict(zip(('packager','sections','readWorld','writeWorld'),values)))
