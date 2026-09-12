"""Independent reference addresses for native-image assertions, never runtime bindings."""
def native_rng_fixture(variant):
    return {'state':0x1a279c0,'streams':(0x46a800,0x46a7d0)} if variant=='SHC' else {
        'state':0x24baec0,'streams':(0x46aa20,0x46a9f0)}
