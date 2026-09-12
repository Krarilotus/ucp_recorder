"""Private reference-image expectations; Map Extensions owns runtime discovery."""


def native_save_fixture(variant):
    values={'SHC':(0xf2b3d0,0xb92a58,0x474a20,0x474480),
            'Extreme':(0xf2b850,0xb92be8,0x474c50,0x4746b0)}[variant]
    return dict(version=1,sectionCount=122,descriptorSize=16,
                **dict(zip(('packager','sections','readWorld','writeWorld'),values)))
